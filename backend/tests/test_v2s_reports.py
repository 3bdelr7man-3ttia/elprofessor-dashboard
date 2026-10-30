# -*- coding: utf-8 -*-
"""قسم «التقارير» (الجولة النهائية) — ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_reports.py

⛔ صفر شبكة حقيقية ولا نداء مدفوع: المنصة جدول في الذاكرة (`uiharness/reports_fixtures.ReportsPlatform`) وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
الساعة مفروضة (`v2_reports_routes._clock`). المنطق النقي بيتشغّل في node على v2-logic.js.
"""
import copy
import datetime
import json
import os
import re
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Setting  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import reports_fixtures as rfx   # noqa: E402
import v2_node                   # noqa: E402
import v2_reports_routes as v2r  # noqa: E402

ROOT = os.path.dirname(_HERE)
ROOT = os.path.dirname(ROOT)
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
UTC = datetime.timezone.utc
FROZEN = datetime.datetime(2026, 10, 30, 9, 12, tzinfo=UTC)       # القاهرة: ٣٠ أكتوبر ١١:١٢ (+٠٢:٠٠)
TODAY = datetime.date(2026, 10, 30)


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

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
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role,
             dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2r-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('v2r-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من المنصة المزيّفة. أي عنوان برّه المنصة ⇒ ممنوع."""

    def __init__(self, ef):
        self.ef = ef
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'headers': dict(headers or {}),
                          'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        if out is None:
            return _Resp(200, [])
        return _Resp(*out)

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]

    def clear(self):
        self.seen[:] = []


def _install(monkeypatch, ef, now=FROZEN):
    import app as appmod
    p = Plat(ef)
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    monkeypatch.setattr(v2r, '_clock', lambda: now)
    v2r.clear_cache()
    return p


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    rfx.wipe_dash(appmod)
    rfx.seed_dash(appmod, TODAY)
    p = _install(monkeypatch, rfx.ReportsPlatform(now=FROZEN))
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked
    rfx.wipe_dash(appmod)


def get(ctx, path, role='admin', **kw):
    return ctx['client'].get(path, headers=ctx['heads'][role] if role else {}, **kw)


def summary(ctx, period='month', scope='all', fresh=False):
    r = get(ctx, '/api/v2/reports/summary?period=%s&scope=%s%s' % (period, scope, '&fresh=1' if fresh else ''))
    assert r.status_code == 200, r.get_data(as_text=True)[:400]
    return r.get_json()



def post(ctx, path, body=None, role='admin', method='POST'):
    kw = {'headers': ctx['heads'][role] if role else {}}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


def seed(specs, today=TODAY, articles=()):
    """يمسح بيانات الدفتر ويزرع صفوفًا محددة: (قبل كم يوم، المصدر، جنيه، دولار، (عملة، مبلغ) أو None)."""
    import app as appmod
    rfx.wipe_dash(appmod)
    with flask_app.app_context():
        for i, (ago, source, egp, usd, foreign) in enumerate(specs):
            r = appmod.Revenue(date=today - datetime.timedelta(days=ago), source=source, description='x', amount_egp=None if foreign else egp, amount_usd=usd,
                               payment_id='rp-t-%d-%s' % (i, ago), payment_method='platform')
            if foreign:
                r.amount_original, r.currency, r.needs_fx = foreign[1], foreign[0], True
            db.session.add(r)
        for j, ago in enumerate(articles):
            db.session.add(appmod.Article(title='م%d' % j, status='published', slug='rep-art-t%d' % j,
                                          published_at=datetime.datetime.combine(today - datetime.timedelta(days=ago), datetime.time(10, 0))))
        db.session.commit()


def walk(o, path=''):
    """كل (مسار، قيمة) في JSON."""
    if isinstance(o, dict):
        for k, v in o.items():
            for x in walk(v, path + '/' + str(k)):
                yield x
    elif isinstance(o, list):
        for i, v in enumerate(o):
            for x in walk(v, path + '/%d' % i):
                yield x
    else:
        yield path, o


def texts(payload):
    return [v for _, v in walk(payload) if isinstance(v, str)]


# ---------------------------------------------------------------- ١) الأمان والتحقق

ROUTES = [('GET', '/api/v2/reports/summary'), ('GET', '/api/v2/reports/weekly'),
          ('PUT', '/api/v2/reports/weekly/settings'), ('POST', '/api/v2/reports/weekly/send')]


@pytest.mark.parametrize('method,path', ROUTES)
def test_admin_only_and_closed_switch_and_no_store(ctx, plat, monkeypatch, method, path):
    body = {'enabled': True, 'confirmed': True} if method == 'PUT' else ({'confirmed': True} if method == 'POST' else None)
    kw = dict(method=method)
    for role in NON_ADMIN_ROLES:
        r = ctx['client'].open(path, headers=ctx['heads'][role], json=body, **kw)
        assert r.status_code == 403, (path, role)
    assert ctx['client'].open(path, json=body, **kw).status_code == 401
    assert plat.seen == [], 'نداء للمنصة من غير أدمن'
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = ctx['client'].open(path, headers=ctx['heads']['admin'], json=body, **kw)
    assert r.status_code == 404 and plat.seen == []
    assert r.headers.get('Cache-Control') == 'no-store'
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r = ctx['client'].open(path, headers=ctx['heads']['admin'], json=body, **kw)
    assert r.status_code in (200, 404), r.status_code
    assert r.headers.get('Cache-Control') == 'no-store'


def test_validation_messages(ctx, plat):
    r = get(ctx, '/api/v2/reports/summary?period=year&scope=all')
    assert r.status_code == 400 and r.get_json()['error'] == 'فترة غير معروفة'
    r = get(ctx, '/api/v2/reports/summary?period=week&scope=money')
    assert r.status_code == 400 and r.get_json()['error'] == 'قسم غير معروف'
    assert plat.seen == []
    # ٣٠ أكتوبر ٢٠٢٦ جمعة: آخر أسبوع مكتمل يبدأ الأحد ١٨ أكتوبر
    for bad in ('2026-10-19', '2026-10-25', '2026-11-01', '2026-10-11x', 'abc', '2026-07-26'):
        r = get(ctx, '/api/v2/reports/weekly?week=' + bad)
        assert r.status_code == 400, bad
        assert r.get_json()['error'].startswith('اختر أسبوعًا اكتمل') or r.get_json()['error'].startswith('أقدم أسبوع متاح'), r.get_json()
    assert get(ctx, '/api/v2/reports/weekly?week=2026-10-18').status_code == 200
    oldest = datetime.date(2026, 10, 18) - datetime.timedelta(weeks=11)
    assert oldest.weekday() == 6
    assert get(ctx, '/api/v2/reports/weekly?week=' + oldest.isoformat()).status_code == 200
    r = get(ctx, '/api/v2/reports/weekly?week=' + (oldest - datetime.timedelta(weeks=1)).isoformat())
    assert r.status_code == 400 and r.get_json()['error'].startswith('أقدم أسبوع متاح')


# ---------------------------------------------------------------- ٢) النوافذ

@pytest.mark.parametrize('period,days', [('week', 7), ('month', 30), ('quarter', 91)])
def test_windows_are_full_days_and_adjacent(ctx, plat, period, days):
    d = summary(ctx, period)
    w, p = d['window'], d['prev']
    assert w['days'] == days and w['until'] == '2026-10-30' and w['tz'] == 'Africa/Cairo'
    f, u = datetime.date.fromisoformat(w['from']), datetime.date.fromisoformat(w['until'])
    assert (u - f).days == days
    pf, pu = datetime.date.fromisoformat(p['from']), datetime.date.fromisoformat(p['until'])
    assert pu == f and (pu - pf).days == days
    assert d['generated_at'].endswith('+02:00')
    if period == 'quarter':
        assert len(d['daily']['rows']) == 13 and d['daily']['bucket'] == 'week'
        assert [r['from'] for r in d['daily']['rows']][0] == w['from']
    else:
        assert len(d['daily']['rows']) == days and d['daily']['bucket'] == 'day'
    labels = {'week': 'آخر ٧ أيام كاملة', 'month': 'آخر ٣٠ يومًا كاملة', 'quarter': 'آخر ١٣ أسبوعًا'}
    assert w['label'].startswith(labels[period]) and 'إلى ٢٩ أكتوبر' in w['label']
    assert d['prev']['label'].endswith('التي قبلها')


@pytest.mark.parametrize('now,expect_until', [
    (datetime.datetime(2026, 7, 15, 23, 30, tzinfo=UTC), '2026-07-16'),     # صيف +٣ ⇒ ٠٢:٣٠ اليوم التالي
    (datetime.datetime(2026, 12, 15, 23, 30, tzinfo=UTC), '2026-12-16'),    # شتاء +٢ ⇒ ٠١:٣٠ اليوم التالي
    (datetime.datetime(2026, 12, 15, 21, 30, tzinfo=UTC), '2026-12-15'),    # شتاء: ٢٣:٣٠ لسه نفس اليوم
    (datetime.datetime(2026, 7, 15, 21, 30, tzinfo=UTC), '2026-07-16'),     # صيف: ٠٠:٣٠ اليوم التالي
])
def test_cairo_day_boundary_summer_and_winter(ctx, monkeypatch, now, expect_until):
    p = _install(monkeypatch, rfx.ReportsPlatform(now=now), now=now)
    d = summary(ctx, 'week')
    assert d['window']['until'] == expect_until
    assert d['generated_at'].endswith('+03:00' if now.month == 7 else '+02:00')


def test_a_row_dated_today_is_in_today_and_in_no_bucket(ctx, plat):
    seed([(0, 'consultation', 700.0, 0, None), (1, 'consultation', 100.0, 0, None)])
    d = summary(ctx, 'week')
    assert d['today']['income_egp'] == 700.0
    assert sum(r['income_egp'] for r in d['daily']['rows']) == 100.0
    assert d['daily']['rows'][-1]['from'] == '2026-10-29'
    assert [s for s in d['sections'] if s['key'] == 'files'][0]['value']['egp'] == 100.0


def test_timezone_database_loads_and_failure_falls_back_to_utc_days(ctx, plat, monkeypatch):
    import zoneinfo
    assert zoneinfo.ZoneInfo('Africa/Cairo') is not None
    assert 'tzdata' in _read('backend', 'requirements.txt')
    monkeypatch.setattr(v2r, 'ZoneInfo', lambda name: (_ for _ in ()).throw(KeyError(name)))
    d = summary(ctx, 'week', fresh=True)
    assert d['sources']['window'] == 'failed' and d['window']['tz'] == 'UTC'
    assert d['window']['until'] == '2026-10-30' and d['generated_at'].endswith('+00:00')


# ---------------------------------------------------------------- ٣) الدفتر

def section(d, key):
    return [s for s in d['sections'] if s['key'] == key][0]


def test_ledger_currencies_are_never_summed_and_total_egp_never_read(ctx, plat):
    seed([(2, 'course', 1000.0, 0, None), (3, 'course', 0, 30.0, None), (4, 'course', 0, 0, ('SAR', 300.0)), (5, 'course', 0, 0, ('SAR', 100.0)),
          (40, 'course', 500.0, 0, None)])
    d = summary(ctx)
    c = section(d, 'courses')
    assert c['value']['egp'] == 1000.0 and c['value']['count'] == 4
    assert {(o['currency'], o['amount']) for o in c['value']['others']} == {('USD', 30.0), ('SAR', 400.0)}
    assert c['prev'] == {'egp': 500.0, 'count': 1}
    assert c['chip_hint'] == 'النسبة بالجنيه فقط'
    assert d['daily']['income_other'] and {(o['currency'], o['amount']) for o in d['daily']['income_other']} == {('USD', 30.0), ('SAR', 400.0)}
    import app as appmod
    with flask_app.app_context():
        db.session.add(appmod.Revenue(date=TODAY - datetime.timedelta(days=2), source='course', description='y', amount_egp=0, amount_usd=0,
                                      payment_id='rp-t-onlytotal'))
        db.session.commit()
    v2r.clear_cache()
    assert section(summary(ctx), 'courses')['value']['count'] == 4          # صف بلا أي مبلغ لا يُعدّ ولا يدخل


def test_rows_outside_the_window_are_excluded_and_other_sources_never_count_as_paid(ctx, plat):
    seed([(1, 'consultation', 100.0, 0, None), (31, 'consultation', 50.0, 0, None), (61, 'consultation', 999.0, 0, None),
          (2, 'ads_deposit', 5000.0, 0, None), (3, 'subscription', 200.0, 0, None), (4, 'sale', 300.0, 0, None), (5, 'manual', 400.0, 0, None),
          (6, 'weird_unknown', 600.0, 0, None)])
    d = summary(ctx)
    paid = [s for s in d['funnel']['stages'] if s['key'] == 'paid'][0]
    assert paid['cur'] == 1 and paid['prev'] == 1
    assert section(d, 'files')['value']['egp'] == 100.0 and section(d, 'files')['prev']['egp'] == 50.0
    assert section(d, 'courses')['value']['egp'] == 0.0 and section(d, 'books')['value']['egp'] == 0.0
    assert sum(r['income_egp'] for r in d['daily']['rows']) == 100.0
    assert d['today']['income_egp'] == 0.0
    blob = json.dumps(d, ensure_ascii=False)
    assert '٥٬٠٠٠' not in blob and '٦٠٠' not in blob and '٣٠٠' not in blob       # لا مبلغ من خانة «أخرى» في أي سطر ولا جملة


@pytest.mark.parametrize('source,svc', [('consultation', 'experts'), ('consulting', 'experts'), ('expert_file', 'experts'), ('expert_case', 'experts'),
                                        ('course', 'courses'), ('course_offer', 'courses'), ('program', 'courses'), ('book', 'books'), ('knowledge', 'books'),
                                        ('ads_deposit', 'other'), ('', 'other'), (None, 'other'), ('BOOK', 'books')])
def test_service_mapping_goes_through_one_function(source, svc):
    assert v2r._service_of(source) == svc


@needs_node
def test_service_mapping_parity_with_the_dashboard_logic():
    sources = ['consultation', 'consulting', 'expert_file', 'expert_case', 'course', 'course_offer', 'program', 'book', 'knowledge', 'ads_deposit',
               'subscription', 'sale', '', 'Book', ' book ', 'COURSE', 'x']
    rows = [{'date': '2026-10-05', 'source': s, 'amount_egp': 10.0, 'amount_usd': 0} for s in sources]
    out = v2_node.logic('v2Income', rows, 'month', int(FROZEN.timestamp() * 1000))
    for svc in ('experts', 'courses', 'books', 'other'):
        py = sum(1 for s in sources if v2r._service_of(s) == svc)
        js = out['services'][svc][0]['amount'] / 10 if out['services'][svc] else 0
        assert py == js, svc


@needs_node
def test_ledger_sums_equal_the_dashboard_income_for_a_calendar_month(ctx, plat):
    import app as appmod
    r = get(ctx, '/api/revenues')
    rows = r.get_json()
    out = v2_node.logic('v2Income', rows, 'month', int(FROZEN.timestamp() * 1000))
    py = v2r.read_ledger(vars(appmod), {'prev_from': datetime.date(2026, 10, 1), 'today': TODAY})
    agg = v2r.aggregate_ledger(py, datetime.date(2026, 10, 1), datetime.date(2026, 11, 1))
    for svc in ('experts', 'courses', 'books', 'other'):
        mine = {(t['currency'], t['amount']) for t in agg[svc]['totals']}
        theirs = {(t['currency'], t['amount']) for t in out['services'][svc]}
        assert mine == theirs, (svc, mine, theirs)
    assert sum(agg[s]['count'] for s in agg) == out['count']


# ---------------------------------------------------------------- ٤) الحسابات والسوق

def stage(d, key):
    return [s for s in d['funnel']['stages'] if s['key'] == key][0]


def test_users_completeness_rule(ctx, monkeypatch):
    now = FROZEN
    # ١٠٠٠ صف كلها داخل النافذة (والأقدم بعد بدايتها) ⇒ لا رقم، لا ١٠٠٠
    ef = rfx.ReportsPlatform(now=now)
    ef.r_users = [{'id': 'u%d' % i, 'email': 'u%d@example.test' % i, 'created_at': (now - datetime.timedelta(hours=1 + (i % 300))).isoformat()} for i in range(1000)]
    p = _install(monkeypatch, ef)
    seed([])
    d = summary(ctx)
    assert stage(d, 'signed_up')['cur'] is None and stage(d, 'signed_up')['prev'] is None
    assert d['sources']['users'] == 'partial' and d['daily']['signups_available'] is False
    assert all(r['signups'] is None for r in d['daily']['rows']) and d['today']['signups'] is None
    # ٩٩٩ صفًّا ⇒ العدّ كامل
    ef.r_users = ef.r_users[:999]
    v2r.clear_cache()
    d = summary(ctx)
    def cairo(u):
        return (datetime.datetime.fromisoformat(u['created_at']) + datetime.timedelta(hours=2)).date()
    exp = sum(1 for u in ef.r_users if datetime.date(2026, 9, 30) <= cairo(u) < TODAY)
    assert stage(d, 'signed_up')['cur'] == exp and exp < 999 and d['sources']['users'] == 'ok'
    assert d['today']['signups'] == sum(1 for u in ef.r_users if cairo(u) == TODAY) > 0
    # ١٠٠٠ صف والأقدم قبل بداية الفترة السابقة ⇒ الفترتان دقيقتان
    ef.r_users = [{'id': 'u%d' % i, 'email': 'u%d@example.test' % i, 'created_at': (now - datetime.timedelta(hours=1 + i * 2)).isoformat()} for i in range(1000)]
    v2r.clear_cache()
    d = summary(ctx)
    assert stage(d, 'signed_up')['cur'] is not None and stage(d, 'signed_up')['prev'] is not None and d['sources']['users'] == 'ok'


def test_market_counts_and_query_params(ctx, plat):
    d = summary(ctx)
    call = plat.calls('/api/bridge/market/requests')[0]
    assert call['params'] == {'author_kind': 'member', 'include_test': 'false', 'limit': 500}
    m = section(d, 'market')
    ef = plat.ef
    win_from = datetime.datetime(2026, 9, 30, tzinfo=UTC) - datetime.timedelta(hours=3)
    # العدّ بالحرف من المصدر نفسه
    def cairo_date(iso):
        return (datetime.datetime.fromisoformat(iso) + datetime.timedelta(hours=2)).date()
    mine = [r for r in ef.r_market if datetime.date(2026, 9, 30) <= cairo_date(r['created_at']) < datetime.date(2026, 10, 30)]
    assert m['value']['n'] == len(mine)
    unanswered = sum(1 for r in mine if r['status'] == 'open' and r['offer_count'] == 0)
    if unanswered:
        assert m['chip']['tone'] == 'bad' and ('بلا عرض' in m['chip']['text'])
    assert not any('is_test' in str(c['params']) and c['params'].get('include_test') != 'false' for c in plat.seen)


def test_market_completeness_rule(ctx, monkeypatch):
    ef = rfx.ReportsPlatform(now=FROZEN)
    ef.r_market = [{'id': 'm%d' % i, 'status': 'open', 'offer_count': 0, 'need_kind': 'expert', 'created_at': (FROZEN - datetime.timedelta(hours=2 + i % 40)).isoformat()}
                   for i in range(60)]
    _install(monkeypatch, ef)
    seed([])
    d = summary(ctx)
    exp = sum(1 for r in ef.r_market if datetime.date(2026, 9, 30) <= (datetime.datetime.fromisoformat(r['created_at']) + datetime.timedelta(hours=2)).date() < TODAY)
    assert section(d, 'market')['value']['n'] == exp and exp > 0 and d['sources']['market'] == 'ok'
    ef.rp_force[('GET', '/api/bridge/market/requests')] = (200, {'items': ef.r_market[:50], 'total': 600, 'counts': {}})     # صفحة مقصوصة
    v2r.clear_cache()
    d = summary(ctx)
    assert section(d, 'market')['value'] is None and d['sources']['market'] == 'partial'


# ---------------------------------------------------------------- ٥) النزاعات: نفس رقم شارة اللوحة

QUEUES = {
    'zero': {'expert_files_disputed': 0, 'expert_files_case_disputed': 0, 'consultation_disputes': 0},
    'files_only': {'expert_files_disputed': 2, 'expert_files_case_disputed': 0, 'consultation_disputes': 0},
    'mixed': {'expert_files_disputed': 1, 'expert_files_case_disputed': 1, 'consultation_disputes': {'count': 3}},
}


@needs_node
@pytest.mark.parametrize('name', sorted(QUEUES))
def test_disputes_total_equals_the_board_tile(ctx, plat, name):
    Q = QUEUES[name]
    plat.ef.rp_force[('GET', '/api/bridge/ops/queue')] = (200, Q)
    d = summary(ctx)
    total = sum((v['count'] if isinstance(v, dict) else v) for v in Q.values())
    tile = [t for t in v2_node.logic('v2Tiles', Q, {'inbox': [], 'now': 0}) if t['key'] == 'disputes'][0]
    assert tile['hot'] == (total > 0)
    chip = section(d, 'satisfaction')['chip']
    if total:
        assert tile['next'].startswith(v2_node.logic('util.U', total, ['نزاع واحد', 'نزاعان', 'نزاعات', 'نزاعًا']))
        assert chip['text'] == v2_node.logic('util.U', total, ['نزاع مفتوح', 'نزاعان مفتوحان', 'نزاعات مفتوحة', 'نزاعًا مفتوحًا']) and chip['tone'] == 'bad'
    else:
        assert chip['text'] == 'لا نزاع مفتوح' and chip['tone'] == 'mute'
    assert plat.calls('/api/bridge/consultations') == []


def test_disputes_missing_key_is_unavailable_not_zero(ctx, plat):
    plat.ef.rp_force[('GET', '/api/bridge/ops/queue')] = (200, {'expert_files_disputed': 1, 'consultation_disputes': 1})
    d = summary(ctx)
    assert d['sources']['disputes'] == 'failed' and section(d, 'satisfaction')['chip'] == {'text': 'غير متاح بعد', 'tone': 'na'}


# ---------------------------------------------------------------- ٦) كل مصدر يفشل لوحده

def baseline(ctx):
    return summary(ctx, fresh=True)


FAILURES = {
    'users': ('/api/bridge/users', None),
    'market': ('/api/bridge/market/requests', None),
    'disputes': ('/api/bridge/ops/queue', None),
    'chat': ('/api/bridge/chat-insights', None),
}


@pytest.mark.parametrize('src', sorted(FAILURES))
@pytest.mark.parametrize('how', [(500, {'detail': 'x'}), (502, {'detail': 'x'}), (401, {'detail': 'x'}), (200, 'not-an-object')])
def test_a_failed_source_is_null_and_never_zero(ctx, plat, src, how):
    base = baseline(ctx)
    path = FAILURES[src][0]
    plat.ef.rp_force[('GET', path)] = how
    d = summary(ctx, fresh=True)
    assert d['sources'][src] == 'failed', (src, how, d['sources'])
    if src == 'users':
        assert stage(d, 'signed_up')['cur'] is None and stage(d, 'signed_up')['prev'] is None
        assert all(r['signups'] is None for r in d['daily']['rows']) and d['today']['signups'] is None and d['daily']['signups_available'] is False
        assert stage(d, 'paid') == stage(base, 'paid')
    if src == 'market':
        assert section(d, 'market')['value'] is None and section(d, 'market')['chip']['text'] == 'غير متاح بعد'
        assert section(d, 'files') == section(base, 'files')
    if src == 'disputes':
        assert section(d, 'satisfaction')['chip']['text'] == 'غير متاح بعد' and section(d, 'market') == section(base, 'market')
    if src == 'chat':
        assert [b for b in d['brain'] if b['key'] == 'opportunity'][0]['text'] is None
    for k in ('files', 'courses', 'books'):
        assert section(d, k) == section(base, k)
    assert d['daily']['rows'] == base['daily']['rows'] or src == 'users'
    # لا صفر مكان رقم مجهول: كل حقل يتبع المصدر الفاشل null
    nums = [(p, v) for p, v in walk(d) if v == 0 and not isinstance(v, bool)]
    bad = [p for p, v in nums if (src == 'users' and ('signups' in p or 'signed_up' in p or p.startswith('/funnel/stages/2')))
           or (src == 'market' and '/sections/3/' in p and 'value' in p)]
    assert bad == [], bad


def test_ledger_and_content_failures(ctx, plat, monkeypatch):
    base = baseline(ctx)
    real_ledger = v2r.read_ledger

    def boom(*a, **k):
        raise RuntimeError('db')
    monkeypatch.setattr(v2r, 'read_ledger', boom)
    d = summary(ctx, fresh=True)
    assert d['sources']['ledger'] == 'failed'
    for k in ('files', 'courses', 'books'):
        s = section(d, k)
        assert s['value'] is None and s['prev'] is None and s['chip']['text'] == 'غير متاح بعد'
    assert stage(d, 'paid')['cur'] is None and all(r['income_egp'] is None for r in d['daily']['rows']) and d['today']['income_egp'] is None
    assert stage(d, 'signed_up') == stage(base, 'signed_up')
    assert d['daily']['ledger'] is False and 'الدخل بالجنيه: غير متاح بعد' in v2_leg(d)
    monkeypatch.setattr(v2r, 'read_ledger', real_ledger)
    monkeypatch.setattr(v2r, 'read_content', boom)
    d = summary(ctx, fresh=True)
    assert d['sources']['content'] == 'failed' and section(d, 'content')['value'] is None


def v2_leg(d):
    out = []
    dl = d['daily']
    if dl.get('ledger') is False:
        out.append('الدخل بالجنيه: غير متاح بعد')
    return out


# ---------------------------------------------------------------- ٧) جسر الرحلة (N3)

def test_funnel_bridge_absent_is_silent_and_uses_interim(ctx, plat):
    d = summary(ctx)
    assert d['sources']['funnel'] == 'absent' and d['layout'] == 'compact' and d['funnel']['mode'] == 'compact'
    assert d['funnel']['missing'] == 3 and d['funnel']['missing_text'] == '٣ خطوات تكتمل حين تسجّل المنصة الزيارات'
    assert stage(d, 'signed_up')['cur'] == 90 and stage(d, 'paid')['sub']
    assert section(d, 'files')['note'] == 'تشمل الاستشارات العادية'
    assert d['origins']['channels'] is None and d['daily']['visits_available'] is False


def test_funnel_bridge_ok_replaces_interim_values(ctx, plat):
    plat.ef.funnel_on = True
    d = summary(ctx)
    assert d['sources']['funnel'] == 'ok' and d['layout'] == 'full' and d['funnel']['mode'] == 'full' and d['funnel']['missing'] == 0
    assert stage(d, 'visits')['cur'] == 12400 and stage(d, 'signed_up')['cur'] == 1240          # من الجسر لا من الحسابات (٩٠)
    assert stage(d, 'paid')['cur'] == 268 and stage(d, 'paid')['sub'] is None                    # paid_people
    assert stage(d, 'asked')['conv_text'] == '٢٥٪ من الزوار' and stage(d, 'signed_up')['conv_text'] == '٤٠٪ ممن سألوا'
    f = section(d, 'files')
    assert f['value']['egp'] == 112400.0 and f['note'] is None
    assert not any(b['label'] == 'ما يشمله الرقم' for ln in d['brain'] for b in ln['basis'])
    assert [c['label'] for c in d['origins']['channels']] == ['بحث جوجل', 'فيسبوك وإنستجرام', 'واتساب', 'دخلوا مباشرة', 'دعوات الخبراء', 'مواقع أخرى']
    assert sum(c['pct'] for c in d['origins']['channels']) in (99, 100, 101)
    assert d['origins']['countries'][0]['label'] == 'مصر' and d['origins']['countries'][-1]['label'] == 'بلاد أخرى'
    assert len(d['origins']['top_pages']) == 3
    assert d['daily']['visits_available'] is True and d['daily']['rows'][0]['visits'] is not None
    assert len(plat.ef.funnel_calls) == 2 and {c['scope'] for c in plat.ef.funnel_calls} == {'all'} and plat.ef.funnel_calls[0]['tz'] == 'Africa/Cairo'


def test_funnel_bridge_error_is_a_warning_and_compact(ctx, plat):
    plat.ef.funnel_on = True
    plat.ef.rp_force[('GET', '/api/bridge/reports/funnel')] = (500, {'detail': 'x'})
    d = summary(ctx)
    assert d['sources']['funnel'] == 'failed' and d['layout'] == 'compact' and stage(d, 'signed_up')['cur'] == 90
    assert section(d, 'files')['value']['egp'] == 13500.0


def test_section_scopes_have_their_own_journey(ctx, plat):
    for scope, title, keys in (('files', 'رحلة ملفات الخبراء', ['asked', 'opened', 'paid']), ('courses', 'رحلة الدورات', ['page_visits', 'enrolled', 'paid']),
                               ('books', 'رحلة الكتب', ['page_visits', 'buy_clicks', 'paid']), ('market', 'رحلة سوق الخدمات', ['new', 'with_offers', 'matched']),
                               ('content', 'رحلة المحتوى', ['published', 'visits', 'signups_from_articles'])):
        v2r.clear_cache()
        d = summary(ctx, 'month', scope)
        assert d['funnel']['title'] == title and [s['key'] for s in d['funnel']['stages']] == keys, scope
    d = summary(ctx, 'month', 'market')
    assert [s['cur'] is not None for s in d['funnel']['stages']] == [True, True, True] and d['funnel']['missing'] == 0
    d = summary(ctx, 'month', 'books')
    assert stage(d, 'paid')['cur'] == 0 and d['funnel']['missing'] == 2
    # التسويق: لا نداء ولا أرقام
    plat.clear()
    d = summary(ctx, 'month', 'marketing')
    assert plat.seen == [] and d['funnel'] is None
    assert [b['na_reason'] for b in d['brain']] == ['تكتمل مع ربط الحملات في قسم التسويق'] * 3 and all(b['text'] is None for b in d['brain'])


# ---------------------------------------------------------------- ٨) قواعد العقل

def fig(money=None, signups=None, market=None, unmet=None, failed=None, foreign=False, caveat=True):
    f = {'money': money or {}, 'signups': signups, 'market': market, 'unmet': unmet, 'foreign': foreign, 'files_caveat': caveat,
         'failed': {'ledger': False, 'users': False, 'market': False, 'chat': False}}
    f['failed'].update(failed or {})
    return f


def M(cur_egp, cur_count, prev_egp, prev_count):
    return {'cur_egp': cur_egp, 'cur_count': cur_count, 'prev_egp': prev_egp, 'prev_count': prev_count}


def mk(new=0, unanswered=0, course_need=0, course_unanswered=0, with_offers=0, matched=0):
    return {'new': new, 'unanswered': unanswered, 'course_need': course_need, 'course_unanswered': course_unanswered, 'with_offers': with_offers, 'matched': matched}


def line(lines, key):
    return [x for x in lines if x['key'] == key][0]


def test_brain_working_prefers_largest_increase_and_handles_small_numbers():
    f = fig(money={'files': M(15720.0, 8, 12000.0, 5), 'courses': M(9000.0, 6, 5000.0, 4), 'books': M(600.0, 4, 150.0, 1)})
    lines, _ = v2r.build_brain(f, 'all')
    w = line(lines, 'working')
    assert w['text'] == 'دخل الدورات زاد ٨٠٪: من ٥٬٠٠٠ إلى ٩٬٠٠٠ جنيه.' and w['action']['section'] == 'courses'
    f = fig(money={'files': M(100.0, 8, 100.0, 5), 'courses': M(100.0, 8, 100.0, 5), 'books': M(600.0, 4, 150.0, 1)})
    lines, _ = v2r.build_brain(f, 'all')
    assert line(lines, 'working')['text'] == 'الكتب: ٤ عمليات بيع مقابل عملية واحدة في الفترة التي قبلها.'      # لا نسبة مع أرقام صغيرة
    assert '٪' not in line(lines, 'working')['text']


def test_brain_working_thresholds_and_fallbacks():
    f = fig(money={'files': M(109.0, 5, 100.0, 5)})                                     # ٩٪ فقط
    lines, _ = v2r.build_brain(f, 'files')
    assert line(lines, 'working')['text'] is None and line(lines, 'working')['empty_text'] == 'لا نموّ واضح في هذه الفترة.'
    f = fig(money={'files': M(200.0, 1, 100.0, 5)})                                     # عملية واحدة فقط
    assert line(v2r.build_brain(f, 'files')[0], 'working')['text'] is None
    f = fig(money={s: M(0.0, 0, 0.0, 0) for s in ('files', 'courses', 'books')}, signups={'cur': 124, 'prev': 105})
    assert line(v2r.build_brain(f, 'all')[0], 'working')['text'] == 'الحسابات الجديدة زادت ١٨٪: ١٢٤ مقابل ١٠٥.'
    f = fig(money={s: M(0.0, 0, 0.0, 0) for s in ('files', 'courses', 'books')}, market={'cur': mk(new=18), 'prev': mk(new=15)})
    assert line(v2r.build_brain(f, 'all')[0], 'working')['text'] == 'طلبات السوق زادت ٢٠٪: ١٨ مقابل ١٥.'
    f = fig(money={s: M(0.0, 0, 0.0, 0) for s in ('files', 'courses', 'books')}, signups={'cur': 124, 'prev': 4})
    assert line(v2r.build_brain(f, 'all')[0], 'working')['text'] is None            # السابق أقل من ٥


def test_brain_stalled_rules_in_order():
    base = {s: M(0.0, 0, 0.0, 0) for s in ('files', 'courses', 'books')}
    f = fig(money=dict(base, books=M(0.0, 0, 450.0, 3)), market={'cur': mk(new=5, unanswered=4), 'prev': mk()})
    s = line(v2r.build_brain(f, 'all')[0], 'stalled')
    assert s['text'] == 'الكتب: لا بيع في هذه الفترة، وكان ٣ عمليات في الفترة التي قبلها.' and s['action']['section'] == 'books'
    f = fig(money=dict(base, courses=M(7800.0, 6, 10000.0, 6)))
    s = line(v2r.build_brain(f, 'all')[0], 'stalled')
    assert s['text'] == 'دخل الدورات نزل ٢٢٪: من ١٠٬٠٠٠ إلى ٧٬٨٠٠ جنيه.'
    f = fig(money=base, market={'cur': mk(new=20, unanswered=11), 'prev': mk()})
    s = line(v2r.build_brain(f, 'all')[0], 'stalled')
    assert s['text'] == '١١ طلبًا في السوق بلا عرض من خبير.' and s['action']['section'] == 'market'
    f = fig(money=base, signups={'cur': 92, 'prev': 105})
    assert line(v2r.build_brain(f, 'all')[0], 'stalled')['text'] == 'الحسابات الجديدة نزلت ١٢٪: ٩٢ مقابل ١٠٥.'
    s = line(v2r.build_brain(fig(money=base), 'all')[0], 'stalled')
    assert s['text'] is None and s['empty_text'] == 'لا تراجع واضح في هذه الفترة.'


def test_brain_opportunity_rules():
    base = {s: M(0.0, 0, 0.0, 0) for s in ('files', 'courses', 'books')}
    f = fig(money=base, unmet={'label': 'تأسيس الشركات', 'count': 41}, market={'cur': mk(course_need=5, course_unanswered=4), 'prev': mk()})
    o = line(v2r.build_brain(f, 'all')[0], 'opportunity')
    assert o['text'] == '٤١ سؤالًا عن «تأسيس الشركات» ولا نقدّم له خدمة بعد.' and o['action']['section'] == 'courses'
    assert any(b['value'] == 'كل الأسئلة منذ البداية' for b in o['basis'])
    f = fig(money=base, market={'cur': mk(course_need=5, course_unanswered=4), 'prev': mk()})
    o = line(v2r.build_brain(f, 'all')[0], 'opportunity')
    assert o['text'] == '٥ طلبات في السوق تطلب دورة، ولا يوجد عرض لأغلبها.' and o['action']['section'] == 'market'
    f = fig(money=base, market={'cur': mk(course_need=5, course_unanswered=2), 'prev': mk()})          # ليس أغلبها
    assert line(v2r.build_brain(f, 'all')[0], 'opportunity')['text'] is None
    f = fig(money=base, market={'cur': mk(course_need=2, course_unanswered=2), 'prev': mk()})          # أقل من ٣
    o = line(v2r.build_brain(f, 'all')[0], 'opportunity')
    assert o['text'] is None and o['empty_text'] == 'لا فرصة واضحة في الأسئلة والطلبات حتى الآن.'
    for sc in ('books', 'content'):
        assert line(v2r.build_brain(fig(money=base, unmet={'label': 'x', 'count': 9}), sc)[0], 'opportunity')['text'] is None


def test_brain_skips_failed_sources_with_a_reason():
    f = fig(money={}, failed={'ledger': True, 'users': True, 'market': True, 'chat': True})
    lines, primary = v2r.build_brain(f, 'all')
    assert primary is None
    for ln in lines:
        assert ln['text'] is None and ln['empty_text'] is None and ln['na_reason'].startswith('تعذّر جلب ')
    assert 'دفتر الإيرادات' in line(lines, 'working')['na_reason'] and 'أسئلة المحادثة' in line(lines, 'opportunity')['na_reason']
    f = fig(money={'files': M(0.0, 0, 0.0, 0), 'courses': M(0.0, 0, 0.0, 0), 'books': M(0.0, 0, 0.0, 0)}, failed={'chat': True})
    o = line(v2r.build_brain(f, 'all')[0], 'opportunity')
    assert o['text'] is None and 'أسئلة المحادثة' in o['na_reason']


def test_brain_scope_filtering_and_priority(ctx, plat):
    d = summary(ctx, 'month', 'books')
    blob = ' '.join(texts(d['brain']))
    assert 'الدورات' not in blob and 'ملفات' not in blob
    assert [b for b in d['brain'] if b['key'] == 'stalled'][0]['text'].startswith('الكتب:')
    d = summary(ctx, 'month', 'all')
    assert d['brain_primary'] == 'stalled'
    f = fig(money={'files': M(3000.0, 5, 1000.0, 5)}, unmet={'label': 'أ', 'count': 5})
    assert v2r.build_brain(f, 'all')[1] == 'opportunity'
    f = fig(money={'files': M(3000.0, 5, 1000.0, 5)})
    assert v2r.build_brain(f, 'all')[1] == 'working'
    assert v2r.build_brain(fig(money={'files': M(0.0, 0, 0.0, 0)}), 'files')[1] is None


def test_every_files_sentence_carries_the_inclusion_caveat_while_from_the_ledger():
    f = fig(money={'files': M(15720.0, 8, 12000.0, 5), 'courses': M(0.0, 0, 0.0, 0), 'books': M(0.0, 0, 0.0, 0)})
    for t in (v2r.build_brain(f, 'all')[0][0],):
        assert {'label': 'ما يشمله الرقم', 'value': 'ملفات الخبراء والاستشارات العادية', 'source': 'دفتر الإيرادات'} in t['basis']
    f2 = fig(money={'files': M(0.0, 0, 450.0, 3), 'courses': M(0.0, 0, 0.0, 0), 'books': M(0.0, 0, 0.0, 0)})
    assert any(b['label'] == 'ما يشمله الرقم' for b in v2r.build_brain(f2, 'all')[0][1]['basis'])
    f3 = fig(money={'files': M(15720.0, 8, 12000.0, 5)}, caveat=False)
    assert not any(b['label'] == 'ما يشمله الرقم' for b in v2r.build_brain(f3, 'all')[0][0]['basis'])


def test_copy_rules_in_every_sentence(ctx, plat):
    plat.ef.funnel_on = True
    seen = []
    for sc in v2r.SCOPES:
        for per in ('week', 'month', 'quarter'):
            v2r.clear_cache()
            seen += texts(summary(ctx, per, sc))
    seen += texts(get(ctx, '/api/v2/reports/weekly').get_json())
    for t in seen:
        assert not t.startswith('الذكاء') and not t.upper().startswith('AI'), t
        for bad in ('يقوّم', 'جايين', 'منين', 'بالذكاء', 'يصعد'):
            assert bad not in t, (bad, t)
    for ln in [b for t in seen for b in [t]]:
        pass
    sentences = [t for t in seen if t.endswith('.') and len(t) > 25]
    assert sentences
    for t in sentences:
        assert not re.search(r'[0-9]', t), t                 # أرقام هندية فقط


def test_no_personal_data_in_any_response(ctx, plat):
    plat.ef.funnel_on = True
    blob = json.dumps([summary(ctx, 'month', 'all'), get(ctx, '/api/v2/reports/weekly').get_json()], ensure_ascii=False)
    for e in rfx.USER_EMAILS[:50] + [rfx.ASKER_EMAIL, rfx.ASKER_NAME]:
        assert e not in blob
    for qt in rfx.QUESTION_TEXTS:
        assert qt not in blob
    assert 'كيف أؤسس شركة في الخليج' not in blob                  # مثال السؤال لا يصل الشاشة من هنا
    assert '@' not in blob and 'phone' not in blob


def test_every_outbound_call_is_a_bridge_read_and_classify_never_called(ctx, plat):
    plat.ef.funnel_on = True
    plat.ef.delivery_on = True
    summary(ctx)
    get(ctx, '/api/v2/reports/weekly')
    assert plat.seen and all(c['path'].startswith('/api/bridge/') and c['method'] == 'GET' for c in plat.seen)
    assert all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)
    assert plat.calls('/api/bridge/chat-insights/classify') == []
    assert all(c['timeout'] in (12, None) or c['timeout'] <= 12 for c in plat.seen)


def test_summary_cache(ctx, plat):
    summary(ctx)
    n = len(plat.seen)
    assert n > 0
    summary(ctx)
    assert len(plat.seen) == n
    summary(ctx, fresh=True)
    assert len(plat.seen) > n
    n2 = len(plat.seen)
    summary(ctx, 'week')
    assert len(plat.seen) > n2                                  # مفتاح مختلف ⇒ نداء جديد


# ---------------------------------------------------------------- ٩) تقرير الأحد والإرسال

def weekly(ctx, week=None):
    r = get(ctx, '/api/v2/reports/weekly' + ('?week=' + week if week else ''))
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    return r.get_json()


def test_weekly_defaults_to_the_last_complete_sunday_week(ctx, plat):
    w = weekly(ctx)
    assert w['week'] == {'start': '2026-10-18', 'end': '2026-10-24', 'label': 'من الأحد ١٨ أكتوبر إلى السبت ٢٤ أكتوبر ٢٠٢٦'}
    assert w['nav']['next'] is None and w['nav']['prev'] == '2026-10-11'
    assert w['window']['from'] == '2026-10-18' and w['window']['until'] == '2026-10-25' and w['prev']['from'] == '2026-10-11'
    assert len(w['daily']['rows']) == 7 and w['today'] is None
    for lab in ('شغّال', 'واقف', 'فرصة', 'ملخص العقل', 'الأرقام'):
        assert lab in w['text']
    for sec in w['sections']:
        assert sec['label'] in w['text']
    w2 = weekly(ctx, '2026-10-11')
    assert w2['nav']['next'] == '2026-10-18'
    old = datetime.date(2026, 10, 18) - datetime.timedelta(weeks=11)
    assert weekly(ctx, old.isoformat())['nav']['prev'] is None


def test_weekly_numbers_are_cached_but_delivery_is_reread(ctx, plat):
    weekly(ctx)
    n = len(plat.seen)
    plat.clear()
    weekly(ctx)
    assert [c['path'] for c in plat.seen] == ['/api/bridge/reports/weekly/delivery']
    assert n > 1


DELIVERY_ROWS = [
    ({'setting': False, 'bridge': 'absent', 'platform_enabled': None, 'last_sent_week': None}, 'الإرسال كل أحد: غير متاح بعد — ينتظر تجهيز الإرسال على المنصة'),
    ({'setting': True, 'bridge': 'absent', 'platform_enabled': None, 'last_sent_week': None}, 'الإرسال كل أحد: غير متاح بعد — ينتظر تجهيز الإرسال على المنصة'),
    ({'setting': True, 'bridge': 'failed', 'platform_enabled': None, 'last_sent_week': None}, 'الإرسال كل أحد: تعذّر التحقق الآن'),
    ({'setting': False, 'bridge': 'ok', 'platform_enabled': True, 'last_sent_week': None}, 'الإرسال كل أحد: متوقف'),
    ({'setting': True, 'bridge': 'ok', 'platform_enabled': True, 'last_sent_week': None}, 'يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام'),
    ({'setting': True, 'bridge': 'ok', 'platform_enabled': True, 'last_sent_week': '2026-10-18'},
     'يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام · آخر إرسال: أسبوع ١٨ أكتوبر'),
    ({'setting': True, 'bridge': 'ok', 'platform_enabled': False, 'last_sent_week': None}, 'الإرسال مفعّل هنا، والمنصة لم تفعّله بعد'),
]


@pytest.mark.parametrize('d,text', DELIVERY_ROWS)
def test_delivery_status_text(d, text):
    assert v2r.delivery_text(d) == text


@needs_node
@pytest.mark.parametrize('d,text', DELIVERY_ROWS)
def test_delivery_status_text_parity_with_the_screen(d, text):
    assert v2_node.logic('v2r.deliveryText', d) == text


def set_delivery(ctx, on):
    r = post(ctx, '/api/v2/reports/weekly/settings', {'enabled': on, 'confirmed': True}, method='PUT')
    assert r.status_code == 200, r.get_data(as_text=True)
    return r


def audits(action):
    with flask_app.app_context():
        return AuditLog.query.filter_by(action=action).count()


def test_settings_put(ctx, plat):
    for bad in (None, False, 'true', 1, 'yes'):
        b = {'enabled': True}
        if bad is not None:
            b['confirmed'] = bad
        assert post(ctx, '/api/v2/reports/weekly/settings', b, method='PUT').status_code == 400
    for bad in ('yes', 1, None, 'true'):
        r = post(ctx, '/api/v2/reports/weekly/settings', {'enabled': bad, 'confirmed': True}, method='PUT')
        assert r.status_code == 400 and r.get_json()['error'] == 'اختر تشغيل الإرسال أو إيقافه'
    assert plat.seen == []
    n0 = audits('reports.weekly_delivery')
    set_delivery(ctx, True)
    assert audits('reports.weekly_delivery') == n0 + 1 and plat.seen == []
    with flask_app.app_context():
        assert Setting.query.filter_by(key='v2r_weekly_delivery').first().value == '1'
    assert weekly(ctx)['delivery']['setting'] is True
    set_delivery(ctx, False)
    with flask_app.app_context():
        assert Setting.query.filter_by(key='v2r_weekly_delivery').first() is None
    assert weekly(ctx)['delivery']['setting'] is False


def test_manual_send(ctx, plat):
    assert post(ctx, '/api/v2/reports/weekly/send', {}).status_code == 400
    assert post(ctx, '/api/v2/reports/weekly/send', {'confirmed': 'true'}).status_code == 400
    assert plat.seen == []
    n0 = audits('reports.weekly_send')
    r = post(ctx, '/api/v2/reports/weekly/send', {'confirmed': True})                  # المنصة بلا جسر الإرسال ⇒ ٤٠٤
    assert r.status_code == 404 and r.get_json() == {'error': 'غير متاح بعد', 'na': True} and audits('reports.weekly_send') == n0
    plat.ef.delivery_on = True
    plat.clear()
    text = weekly(ctx)['text']
    plat.clear()
    r = post(ctx, '/api/v2/reports/weekly/send', {'confirmed': True, 'by': 'attacker@evil.test'})
    assert r.status_code == 200 and r.get_json() == {'sent': True, 'already': False}
    posts = [c for c in plat.seen if c['method'] == 'POST']
    assert len(posts) == 1 and posts[0]['path'] == '/api/bridge/reports/weekly/deliver'
    j = posts[0]['json']
    assert j['confirmed'] is True and j['week_start'] == '2026-10-18' and j['text'] == text and j['by'] == 'v2r-admin@x.test'
    assert audits('reports.weekly_send') == n0 + 1
    r = post(ctx, '/api/v2/reports/weekly/send', {'confirmed': True, 'week': '2026-10-19'})
    assert r.status_code == 400


def test_cron_route(ctx, plat, monkeypatch):
    c = ctx['client']
    path = '/api/v2/reports/weekly/deliver'
    set_delivery(ctx, False)
    plat.clear()
    assert c.post(path).status_code == 401 and c.post(path, headers={'X-ELP-Metrics-Secret': 'wrong'}).status_code == 401
    assert c.post(path, headers=ctx['heads']['admin']).status_code == 401
    assert plat.seen == []
    ok = {'X-ELP-Metrics-Secret': SECRET}
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert c.post(path, headers=ok).status_code == 404 and plat.seen == []
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r = c.post(path, headers=ok)
    assert r.status_code == 200 and r.get_json() == {'sent': False, 'reason': 'off'} and plat.seen == []
    set_delivery(ctx, True)
    n0 = audits('reports.weekly_cron')
    r = c.post(path, headers=ok)                                                          # جسر المنصة غائب
    assert r.status_code == 200 and r.get_json() == {'sent': False, 'na': 'غير متاح بعد'} and audits('reports.weekly_cron') == n0
    plat.ef.delivery_on = True
    v2r.clear_cache()
    plat.clear()
    r = c.post(path, headers=ok)
    assert r.status_code == 200 and r.get_json() == {'sent': True, 'already': False}
    posts = [x for x in plat.seen if x['method'] == 'POST']
    assert len(posts) == 1 and posts[0]['json']['by'] == 'cron' and posts[0]['json']['confirmed'] is True and posts[0]['json']['week_start'] == '2026-10-18'
    assert audits('reports.weekly_cron') == n0 + 1
    plat.ef.rp_force[('POST', '/api/bridge/reports/weekly/deliver')] = (500, {'detail': 'x'})
    assert c.post(path, headers=ok).status_code == 502
    set_delivery(ctx, False)


# ---------------------------------------------------------------- ١٠) حساب الأيام والأرقام (منفرد)

def test_arabic_number_helper():
    assert v2r._ar(1234567) == '١٬٢٣٤٬٥٦٧' and v2r._ar(0) == '٠' and v2r._ar(12.5) == '١٢٫٥' and v2r._ar(0.05) == '٠٫٠٥' and v2r._ar(None) == ''
    assert v2r._u(1, ['أ', 'ب', 'ج', 'د']) == 'أ' and v2r._u(2, ['أ', 'ب', 'ج', 'د']) == 'ب' and v2r._u(3, ['أ', 'ب', 'ج', 'د']) == '٣ ج' and v2r._u(11, ['أ', 'ب', 'ج', 'د']) == '١١ د'


def test_change_lines_python():
    assert v2r.change_of(124, 105)[0] == '▲ ١٨٪' and v2r.change_of(92, 105)[0] == '▼ ١٢٪'
    assert v2r.change_of(100, 100)[0] == 'كما هو' and v2r.change_of(100, 0)[0] == 'جديد' and v2r.change_of(0, 0)[0] == 'كما هو'
    assert v2r.change_of(None, 5) == (None, None, None) and v2r.change_of(5, None) == (None, None, None)
    assert v2r.change_of(1005, 1000)[0] == 'كما هو' and v2r.change_of(1010, 1000)[0] == '▲ ١٪'


def test_missing_text_forms_python():
    assert v2r.missing_text(1) == 'خطوة واحدة تكتمل حين تسجّل المنصة الزيارات'
    assert v2r.missing_text(2) == 'خطوتان تكتملان حين تسجّل المنصة الزيارات'
    assert v2r.missing_text(3) == '٣ خطوات تكتمل حين تسجّل المنصة الزيارات'
    assert v2r.missing_text(11) == '١١ خطوة تكتمل حين تسجّل المنصة الزيارات'


# ================================================================ المنطق النقي (node)

def NODE(js):
    import subprocess
    script = "const L=require(%s);\n%s" % (json.dumps(os.path.join(ROOT, 'dashboard-cloud', 'v2-logic.js')), js)
    p = subprocess.run([v2_node.NODE, '-e', script], capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


@needs_node
@pytest.mark.parametrize('t,text,tone', [({'key': 'up', 'pct': 31}, 'ينمو ٣١٪', 'up'), ({'key': 'down', 'pct': -22}, 'يتراجع ٢٢٪', 'down'),
                                         ({'key': 'flat', 'pct': 2}, 'ثابت', 'flat'), ({'key': 'new', 'pct': None}, 'جديد', 'up'),
                                         ({'key': 'none', 'pct': None}, 'لا بيع', 'mute'), ({'key': 'na', 'pct': None}, 'غير متاح بعد', 'na')])
def test_trend_chip(t, text, tone):
    out = v2_node.logic('v2r.trendChip', t)
    assert out == {'text': text, 'tone': tone}
    assert v2r.trend_chip(t) == out                              # الخادم والشاشة يتفقان


@needs_node
def test_stage_view_change_and_conversion():
    sv = lambda st, pk=None: v2_node.logic('v2r.stageView', st, pk)
    assert sv({'key': 'signed_up', 'cur': 124, 'prev': 105}, {'key': 'asked', 'cur': 310}) == {'changeText': '▲ ١٨٪', 'tone': 'up', 'convText': '٤٠٪ ممن سألوا'}
    assert sv({'key': 'paid', 'cur': 92, 'prev': 105}, None) == {'changeText': '▼ ١٢٪', 'tone': 'down', 'convText': ''}
    assert sv({'key': 'paid', 'cur': 5, 'prev': 0}) ['changeText'] == 'جديد' and sv({'key': 'paid', 'cur': 0, 'prev': 0})['changeText'] == 'كما هو'
    assert sv({'key': 'paid', 'cur': 100, 'prev': 100.5})['changeText'] == 'كما هو'
    assert sv({'key': 'paid', 'cur': 5, 'prev': None}) == {'changeText': '', 'tone': '', 'convText': ''}      # السابق مجهول: لا سطر تغيير
    assert sv({'key': 'paid', 'cur': None, 'prev': 5}, {'key': 'opened', 'cur': 3}) == {'changeText': '', 'tone': '', 'convText': ''}
    assert sv({'key': 'paid', 'cur': 5, 'prev': 4}, {'key': 'opened', 'cur': None})['convText'] == ''
    assert sv({'key': 'paid', 'cur': 5, 'prev': 4}, {'key': 'opened', 'cur': 0})['convText'] == ''
    assert sv({'key': 'visits', 'cur': 5, 'prev': 4}, {'key': 'x', 'cur': 9})['convText'] == ''


@needs_node
@pytest.mark.parametrize('cur,prev', [(124, 105), (92, 105), (100, 100), (5, 0), (0, 0), (1005, 1000), (1010, 1000), (7, 9), (3, 2), (1, 200), (1000, 1)])
def test_stage_change_parity_server_and_screen(cur, prev):
    py = v2r.change_of(cur, prev)
    js = v2_node.logic('v2r.stageView', {'key': 'paid', 'cur': cur, 'prev': prev}, None)
    assert py[0] == js['changeText'] and (py[1] or '') == js['tone']


@needs_node
@pytest.mark.parametrize('n,text', [(1, 'خطوة واحدة تكتمل حين تسجّل المنصة الزيارات'), (2, 'خطوتان تكتملان حين تسجّل المنصة الزيارات'),
                                    (3, '٣ خطوات تكتمل حين تسجّل المنصة الزيارات'), (11, '١١ خطوة تكتمل حين تسجّل المنصة الزيارات')])
def test_funnel_compact_forms(n, text):
    stages = [{'key': 'a', 'cur': 5}] + [{'key': 'b%d' % i, 'cur': None} for i in range(n)]
    out = v2_node.logic('v2r.funnelCompact', stages)
    assert out['text'] == text and out['missing'] == n and [s['key'] for s in out['rows']] == ['a']
    assert v2r.missing_text(n) == text
    assert v2_node.logic('v2r.funnelCompact', [{'key': 'a', 'cur': 0}])['text'] == '' and len(v2_node.logic('v2r.funnelCompact', [{'key': 'a', 'cur': 0}])['rows']) == 1   # الصفر الحقيقي رقم


@needs_node
def test_chart_points_scale_drop_and_flat():
    rows = [{'income_egp': 0, 'signups': 1, 'visits': None}, {'income_egp': 500, 'signups': 3, 'visits': None}, {'income_egp': 1000, 'signups': 2, 'visits': None}]
    c = v2_node.logic('v2r.chartPoints', rows, 560, 300)
    assert c['visits'] is None and c['income']['max'] == 1000 and c['signups']['max'] == 3
    ys = [p[1] for p in c['income']['pts']]
    assert ys[0] == c['base'] and ys[2] == c['top'] and ys[0] > ys[1] > ys[2]
    xs = [p[0] for p in c['income']['pts']]
    assert xs[0] == c['padX'] and xs[2] == 560 - c['padX'] and abs(xs[1] - 280) < 1
    zero = v2_node.logic('v2r.chartPoints', [{'income_egp': 0, 'signups': None}] * 4, 560, 300)
    assert zero['income']['flat'] is True and {p[1] for p in zero['income']['pts']} == {zero['base']} and zero['signups'] is None
    partial = v2_node.logic('v2r.chartPoints', [{'income_egp': 1, 'signups': 2}, {'income_egp': None, 'signups': 3}], 560, 300)
    assert partial['income'] is None and partial['signups'] is not None                    # سلسلة فيها مجهول لا تُرسم
    assert v2_node.logic('v2r.chartPoints', [], 560, 300)['income'] is None


@needs_node
def test_legend_lists_only_drawn_series():
    f = lambda d, sc='all': v2_node.logic('v2r.legendItems', d, sc)
    base = {'ledger': True, 'signups_available': True, 'visits_available': False}
    assert [i['key'] for i in f(base)['items']] == ['income', 'signups'] and f(base)['notes'] == ['الزوار: غير متاح بعد']
    assert [i['key'] for i in f(dict(base, visits_available=True))['items']] == ['income', 'signups', 'visits']
    out = f(dict(base, signups_available=False))
    assert [i['key'] for i in out['items']] == ['income'] and 'الحسابات الجديدة: غير متاح بعد' in out['notes']
    out = f(dict(base, signups_available=False), 'courses')
    assert 'الحسابات الجديدة: غير متاح بعد' not in out['notes']
    out = f(dict(base, ledger=False))
    assert 'income' not in [i['key'] for i in out['items']] and 'الدخل بالجنيه: غير متاح بعد' in out['notes']


NOW_MS = int(FROZEN.timestamp() * 1000)
RECENT = [
    {'id': 'a', 'segment': 'lawyer', 'country': 'egypt', 'category': 'مدني', 'needs_expert': True, 'created_at': '2026-10-29T09:00:00+00:00'},
    {'id': 'b', 'segment': 'student', 'country': 'saudi', 'category': 'تجاري', 'needs_expert': False, 'created_at': '2026-10-20T09:00:00+00:00'},
    {'id': 'c', 'segment': 'lawyer', 'country': None, 'category': '', 'needs_expert': False, 'created_at': '2026-09-01T09:00:00+00:00'},
    {'id': 'd', 'segment': '', 'country': 'unknown', 'category': 'مدني', 'needs_expert': True, 'created_at': None},
]


@needs_node
def test_demand_filter_matches_the_old_screen():
    old = _read('dashboard-cloud', 'index.html')
    # الشروط القديمة بالحرف من viewAnalysis (إن تغيّرت يفشل هذا الاختبار قبل أن تختلف الشاشتان)
    for frag in ("anFilters.seg!=='all'&&(r.segment||'')!==anFilters.seg", "anFilters.country!=='all'&&(r.country||'unknown')!==anFilters.country",
                 "anFilters.cat!=='all'&&(r.category||'')!==anFilters.cat", "anFilters.ne==='yes'&&!r.needs_expert", "anFilters.ne==='no'&&r.needs_expert",
                 "anWithin(r.created_at,anFilters.time==='7'?7:30)"):
        assert frag in old
    js = """
    const recent=%s, now=%d;
    const anWithin=(iso,days)=>{if(!iso)return false;const t=Date.parse(iso);return !isNaN(t)&&(now-t)<=days*86400000;};
    function oldF(anFilters){return recent.filter(r=>{
      if(anFilters.seg!=='all'&&(r.segment||'')!==anFilters.seg)return false;
      if(anFilters.country!=='all'&&(r.country||'unknown')!==anFilters.country)return false;
      if(anFilters.cat!=='all'&&(r.category||'')!==anFilters.cat)return false;
      if(anFilters.ne==='yes'&&!r.needs_expert)return false;
      if(anFilters.ne==='no'&&r.needs_expert)return false;
      if(anFilters.time!=='all'&&!anWithin(r.created_at,anFilters.time==='7'?7:30))return false;
      return true;}).map(r=>r.id);}
    const out=[];
    const base={seg:'all',country:'all',cat:'all',ne:'all',time:'all'};
    for(const dim of [['seg','lawyer'],['seg','student'],['country','egypt'],['country','unknown'],['cat','مدني'],['ne','yes'],['ne','no'],['time','7'],['time','30']]){
      const f=Object.assign({},base,{[dim[0]]:dim[1]});
      out.push([dim, oldF(f), L.v2r.demandFilter(recent,f,now).map(r=>r.id)]);
    }
    const combo=Object.assign({},base,{seg:'lawyer',ne:'yes',time:'7'});
    out.push([['combo'], oldF(combo), L.v2r.demandFilter(recent,combo,now).map(r=>r.id)]);
    process.stdout.write(JSON.stringify(out));
    """ % (json.dumps(RECENT, ensure_ascii=False), NOW_MS)
    for dim, a, b in NODE(js):
        assert a == b, (dim, a, b)
    assert NODE("process.stdout.write(JSON.stringify([L.v2r.hiddenFilters({seg:'x',country:'all',cat:'all',ne:'no',time:'7'}), L.v2r.hiddenFilters({seg:'all',country:'all',cat:'all',ne:'yes',time:'all'})]))") == [3, 0]


@needs_node
def test_demand_numbers_line():
    d = {'total': 1840, 'needs_expert': 412, 'needs_expert_rate': 0.224, 'anonymous': 1310, 'authed': 530, 'by_country': [{'country': 'egypt', 'count': 5}, {'country': 'saudi', 'count': 2},
                                                                                                                      {'country': 'unknown', 'count': 9}, {'country': 'uae', 'count': 0}],
         'expert_opinions': {'requested': 112, 'paid': 61, 'conversion_rate': 0.545}}
    t = v2_node.logic('v2r.demandNumbers', d)
    assert t == '١٬٨٤٠ سؤالًا · ٤١٢ تحتاج رأي خبير (٢٢٪) · ٥٣٠ عضو و١٬٣١٠ زائر · دفع ٦١ من ١١٢ مقابل رأي خبير (٥٥٪) · من بلدين'.replace('١٬٨٤٠', '١٬٨٤٠'), t
    d.pop('expert_opinions')
    t = v2_node.logic('v2r.demandNumbers', d)
    assert 'الدفع مقابل رأي خبير: غير متاح بعد' in t and '· دفع ' not in t
    assert not re.search('[0-9]', t)


# ================================================================ الخريطة والعنوان والملفات

@needs_node
def test_section_map_and_old_links():
    secs = {s['key']: s for s in NODE("process.stdout.write(JSON.stringify(L.SECTIONS))")}
    tabs = [[t['key'], t['label'], t['mod']] for t in secs['reports']['tabs']]
    assert tabs == [['report', 'التقرير', 'analysis'], ['demand', 'ما يسأل عنه الناس', 'v2r_demand'], ['sunday', 'تقرير الأحد', 'v2r_sunday']]
    assert not any(t['label'] == 'كل السجلات' for t in secs['reports']['tabs'])
    assert secs['reports']['desc'] == 'ما الذي يعمل، وما الذي توقّف، وأين الفرصة'
    assert v2_node.logic('sectionFor', 'analysis') == {'section': 'reports', 'tab': 'report', 'mod': 'analysis', 'st': {}}
    for h, tab in (('#s/reports/demand', 'demand'), ('#s/reports/sunday', 'sunday'), ('#s/reports/report', 'report'), ('#s/reports', 'report'), ('#analysis', 'report')):
        r = v2_node.logic('routeFor', h, {})
        assert r['section'] == 'reports' and r['tab'] == tab, h
    for tab in ('report', 'demand', 'sunday'):
        assert v2_node.logic('routeFor', v2_node.logic('sectionHash', 'reports', tab), {})['tab'] == tab


@needs_node
def test_hash_query_state_whitelist_and_old_hashes_unchanged():
    r = v2_node.logic('routeFor', '#s/reports/report?scope=courses&period=week', {})
    assert r['tab'] == 'report' and r['q'] == {'scope': 'courses', 'period': 'week'}
    r = v2_node.logic('routeFor', '#s/reports/report?scope=Courses&period=week&x=1&scope2=a&period=%20', {})
    assert r.get('q') == {'period': 'week'} or 'q' not in r or r['q'].get('scope') is None
    r = v2_node.logic('routeFor', '#s/reports/report?scope=courses1&other=zz', {})
    assert 'q' not in r
    h = v2_node.logic('sectionHash', 'reports', 'report', None, {'period': 'week', 'scope': 'courses', 'evil': 'x'})
    assert h == '#s/reports/report?scope=courses&period=week'
    assert v2_node.logic('routeFor', h, {})['q'] == {'scope': 'courses', 'period': 'week'}
    assert v2_node.logic('sectionHash', 'reports', 'report', None, {'scope': 'a-b'}) == '#s/reports/report'
    assert v2_node.logic('sectionHash', 'reports', 'sunday') == '#s/reports/sunday'
    for s in NODE("process.stdout.write(JSON.stringify(L.SECTIONS.map(s=>[s.key,s.tabs.map(t=>t.key)])))"):
        for tk in s[1]:
            p = v2_node.logic('parseSectionHash', '#s/%s/%s' % (s[0], tk))
            assert 'q' not in p and p['section'] == s[0], (s[0], tk, p)
    assert v2_node.logic('sectionHash', 'people', 'person', 'A@B.test') == '#s/people/person/a%40b.test'


def test_visible_copy_scan():
    import ast
    strings = []
    src = _read('backend', 'v2_reports_routes.py')
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.search('[؀-ۿ]', n.value):
            strings.append(n.value)
    js = _read('dashboard-cloud', 'v2s', 'reports.js')
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"", js):
        t = m.group(1) if m.group(1) is not None else m.group(2)
        if re.search('[؀-ۿ]', t):
            strings.append(t)
    block = _read('dashboard-cloud', 'v2-logic.js')
    block = block[block.index('// ===== v2s:reports ====='):block.index('// ===== /v2s:reports =====')]
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*)'", block):
        if re.search('[؀-ۿ]', m.group(1)):
            strings.append(m.group(1))
    assert len(strings) > 150
    for t in strings:
        for bad in ('يقوّم', 'AI', 'API', 'null', 'جايين', 'منين', 'بالذكاء', 'يصعد'):
            assert bad not in t, (bad, t)
        assert not re.match(r'^\s*(الذكاء|AI)', t), t


def test_wiring_in_the_shared_files():
    html = _read('dashboard-cloud', 'index.html')
    block = html[html.index('<!-- v2 sections begin -->'):html.index('<!-- v2 sections end -->')]
    assert '<link rel="stylesheet" href="v2s/reports.css">' in block and '<script src="v2s/reports.js"></script>' in block
    assert html.index('<script src="v2-d2.js"></script>') < html.index('<!-- v2 sections begin -->')
    assert "if(window.V2_ON&&window.V2SEC){const _k=Object.keys(V2SEC).find(function(k){return V2SEC[k].owns(current);});if(_k)return V2SEC[_k].render(current,v);}" in html
    assert "if(window.V2SEC&&Object.keys(V2SEC).some(function(k){return V2SEC[k].owns(current);}))ap.classList.add('v2-bare');" in html
    app = _read('backend', 'app.py')
    i = app.index('# ---- v2 section routes end')
    assert "import v2_reports_routes as _v2r; _v2r.register(app, globals())  # v2s:reports" in app[:i]
    assert app.index('v2_book_request_patch') < i < app.index("@app.route('/api/platform-pnl'")
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    assert 'D3.openSheet = openSheet; D3.twoStage = twoStage;' in d3
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        t = _read(df)
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in t and 'COPY backend/v2_reports_routes.py /app/v2_reports_routes.py' in t and 'COPY backend/v2_*_routes.py' not in t
    assert 'v2s/[a-z_]+\\.js' in _read('backend', 'tests', 'test_xss_hardening.py')
    assert 'tzdata==2024.1' in _read('backend', 'requirements.txt')


def test_with_the_switch_off_the_old_analysis_screen_is_untouched():
    js = _read('dashboard-cloud', 'v2s', 'reports.js')
    assert "R.owns = function (mod) { return !!MODS[mod] && !!(window.V2SHELL && window.V2SHELL.on); };" in js
    html = _read('dashboard-cloud', 'index.html')
    assert "if(current==='analysis')return viewAnalysis(v);" in html and 'function viewAnalysis(v){' in html
    assert 'EP.runDemandClassify' in html                                                    # الشاشة القديمة بحالها
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    assert 'window.openModal' in d3
    # reports.js لا يستدعي النافذة القديمة مباشرة ولا يطلب شبكة خارج المسارات المحددة
    assert 'openModal(' not in js and 'fetch(' not in js
    paths = set(re.findall(r"E\.api\('([^'?]+)", js)) | set(re.findall(r"E\.api\('([^']+)'", js))
    assert paths <= {'/platform-chat-insights/', '/platform-chat-insights/classify', '/v2/reports/weekly/settings', '/v2/reports/weekly/send',
                     '/v2/reports/summary', '/v2/reports/weekly', '/platform-chat-insights/classify?limit=100'}, paths


# ---------------------------------------------------------------- جولة التصليح (مراجعة الجودة)
def test_print_rules_are_scoped_to_the_reports_screen():
    css = _read('dashboard-cloud', 'v2s', 'reports.css')
    i = css.index('@media print{')
    block = css[i + len('@media print{'):].rstrip().rstrip('}')
    sels = [m.group(1) for m in re.finditer(r'(?m)^\s*([^{}\n]+)\{', block)]
    assert sels
    for sel in sels:
        for part in sel.split(','):
            assert re.match(r'^(html|body):has\(\.v2r\)(\s|$)', part.strip()), part
    assert '@media print' not in css[:i]
    # لا اسم صنف عام بلا بادئة v2r
    assert not re.search(r'(?m)^\.sr\{', css) and 'class="sr"' not in _read('dashboard-cloud', 'v2s', 'reports.js')


def test_scope_without_rules_says_not_available_never_a_judgement():
    base = {s: M(0.0, 0, 0.0, 0) for s in ('files', 'courses', 'books')}
    lines, primary = v2r.build_brain(fig(money=base), 'content')
    assert primary is None
    for ln in lines:
        assert ln['text'] is None and ln['empty_text'] is None and ln['na_reason']
    lines, _ = v2r.build_brain(fig(money=base), 'books')
    assert line(lines, 'working')['empty_text'] and line(lines, 'opportunity')['empty_text'] is None and line(lines, 'opportunity')['na_reason']


def test_failed_source_stage_is_shown_not_counted_as_not_recorded(ctx, plat):
    plat.ef.rp_force[('GET', '/api/bridge/users')] = (500, {'detail': 'x'})
    d = summary(ctx, fresh=True)
    s = stage(d, 'signed_up')
    assert s['cur'] is None and s['failed'] is True
    others = [x for x in d['funnel']['stages'] if x['key'] != 'signed_up' and x['cur'] is None]
    assert all(x['failed'] is False for x in others)
    assert d['funnel']['missing'] == len(others)
    plat.ef.rp_force.clear()
    ok = baseline(ctx)
    assert all(x['failed'] is False for x in ok['funnel']['stages'])


@needs_node
def test_funnel_compact_keeps_failed_stage_rows():
    out = v2_node.logic('v2r.funnelCompact', [{'key': 'a', 'cur': 5}, {'key': 'u', 'cur': None, 'failed': True}, {'key': 'v', 'cur': None}])
    assert [s['key'] for s in out['rows']] == ['a', 'u'] and out['missing'] == 1
    out = v2_node.logic('v2r.funnelCompact', [{'key': 'u', 'cur': None, 'failed': True}])
    assert out['missing'] == 0 and out['text'] == '' and len(out['rows']) == 1


@needs_node
def test_constant_series_is_drawn_mid_height_and_named():
    rows = [{'income_egp': 0, 'signups': 3, 'visits': None, 'label': 'a'} for _ in range(5)]
    c = v2_node.logic('v2r.chartPoints', rows, 560, 300)
    mid = (c['top'] + c['base']) / 2
    assert c['signups']['constant'] is True and {p[1] for p in c['signups']['pts']} == {mid}
    assert c['income']['flat'] is True and c['income']['constant'] is False
    moving = v2_node.logic('v2r.chartPoints', [{'income_egp': 1, 'signups': 3}, {'income_egp': 2, 'signups': 4}], 560, 300)
    assert moving['signups']['constant'] is False
    leg = v2_node.logic('v2r.legendItems', {'ledger': True, 'signups_available': True, 'visits_available': False, 'bucket': 'day', 'rows': rows}, 'all')
    assert 'الحسابات الجديدة ثابت: ٣ يوميًا' in leg['notes']
    wk = v2_node.logic('v2r.legendItems', {'ledger': True, 'signups_available': True, 'visits_available': False, 'bucket': 'week', 'rows': rows}, 'all')
    assert 'الحسابات الجديدة ثابت: ٣ أسبوعيًا' in wk['notes']


def test_sheets_use_the_brand_buttons_and_neutral_wording():
    js = _read('dashboard-cloud', 'v2s', 'reports.js')
    assert 'class="v3-btn1" data-a="cgo"' in js and 'class="v3-btn2" data-a="cno"' in js
    assert 'btn-primary' not in js and 'السائل' not in js and 'من سأل' not in js
    assert "heads: ['البند', 'الآن', 'بعد الإرسال']" in js and 'last_sent_week === d.week.start' in js
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    assert 'diffTable(r.lines, r.heads)' in d3


def test_settings_put_returns_the_full_delivery_object(ctx, plat):
    r = post(ctx, '/api/v2/reports/weekly/settings', {'enabled': True, 'confirmed': True}, method='PUT')
    dl = r.get_json()['delivery']
    assert dl == {'setting': True, 'bridge': None, 'platform_enabled': None, 'last_sent_week': None} and plat.seen == []
