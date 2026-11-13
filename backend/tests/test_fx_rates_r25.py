# -*- coding: utf-8 -*-
"""أسعار الصرف لسطر «تقريبًا بالدولار» (r25) — `GET /api/v2/money/rates`.

⛔ صفر شبكة: `fetch_rates` بيتستبدل في كل اختبار، و`requests.get` بيرمي. اللي بيثبّته:
  ١. أول طلب بيجيب الأسعار ويخزّنها (+ التاريخ)؛ طلب تاني في نفس اليوم ما بيندهش المصدر (مرة في اليوم على الأكتر).
  ٢. بعد ٢٤ ساعة بيحدّث؛ ولو التحديث فشل بيفضل على آخر أسعار سليمة بعلامة `stale` ويعرض تاريخها.
  ٣. مفيش أسعار خالص ولا مصدر شغال ⇒ `rates: null` (الواجهة تخفي السطر). رد المصدر الفاسد ما بيتخزّنش.
  ٤. أدمن بس · المفتاح مقفول ٤٠٤.
"""
import datetime
import os

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, Setting  # noqa: E402
import v2_fx_routes as fx  # noqa: E402

GOOD = {'rates': {'USD': 1, 'EGP': 50.0, 'SAR': 3.75, 'AED': 3.6725, 'KWD': 0.31, 'QAR': 3.64, 'OMR': 0.385, 'JPY': 150}, 'date': '2026-11-13'}


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0],
                 role=role, dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = u.dashboard_role = role
    u.is_active = True
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture
def ctx(monkeypatch):
    import app as appmod
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')

    def boom(*a, **k):
        raise AssertionError('نداء شبكة حقيقي ممنوع')
    monkeypatch.setattr(appmod.requests, 'get', boom)
    calls = []
    box = {'next': dict(GOOD)}

    def fake_fetch():
        calls.append(1)
        n = box['next']
        if isinstance(n, Exception):
            raise n
        return n
    monkeypatch.setattr(fx, 'fetch_rates', fake_fetch)
    with flask_app.app_context():
        db.create_all()
        Setting.query.filter_by(key=fx.SETTING_KEY).delete()
        db.session.commit()
        yield {'client': flask_app.test_client(), 'admin': _bearer(_mkuser('fx-admin@x.test', 'admin')),
               'emp': _bearer(_mkuser('fx-emp@x.test', 'employee')), 'calls': calls, 'box': box}
        Setting.query.filter_by(key=fx.SETTING_KEY).delete()
        db.session.commit()


def _get(ctx, who='admin'):
    return ctx['client'].get('/api/v2/money/rates', headers=ctx[who])


def test_first_call_fetches_stores_and_second_call_same_day_does_not(ctx):
    r = _get(ctx)
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    j = r.get_json()
    assert j['rates']['EGP'] == 50.0 and j['rates']['SAR'] == 3.75 and j['rates']['USD'] == 1.0
    assert 'JPY' not in j['rates'], 'عملات اللوحة بس'
    assert j['date'] == '2026-11-13' and j['stale'] is False
    assert len(ctx['calls']) == 1
    _get(ctx)
    _get(ctx)
    assert len(ctx['calls']) == 1, 'مرة في اليوم على الأكتر'


def test_after_a_day_it_refreshes_and_on_failure_keeps_the_last_good_rates(ctx):
    _get(ctx)
    row = Setting.query.get(fx.SETTING_KEY)
    import json
    old = json.loads(row.value)
    old['fetched_at'] = (datetime.datetime.utcnow() - datetime.timedelta(hours=30)).isoformat()
    row.value = json.dumps(old)
    db.session.commit()
    ctx['box']['next'] = RuntimeError('المصدر واقع')
    j = _get(ctx).get_json()
    assert len(ctx['calls']) == 2
    assert j['rates']['EGP'] == 50.0 and j['stale'] is True and j['date'] == '2026-11-13', 'آخر أسعار سليمة + تاريخها'
    # المصدر رجع: بيتحدّث
    ctx['box']['next'] = {'rates': {'USD': 1, 'EGP': 51.5, 'SAR': 3.75}, 'date': '2026-11-14'}
    j = _get(ctx).get_json()
    assert j['rates']['EGP'] == 51.5 and j['date'] == '2026-11-14' and j['stale'] is False


def test_no_rates_at_all_returns_null(ctx):
    ctx['box']['next'] = RuntimeError('down')
    j = _get(ctx).get_json()
    assert j['rates'] is None


@pytest.mark.parametrize('bad', [{'rates': {}, 'date': 'x'}, {'rates': {'EGP': -3}, 'date': 'x'}, {'rates': {'SAR': 3.7}, 'date': 'x'}, {'rates': 'nope', 'date': 'x'}])
def test_a_broken_source_answer_is_never_stored(ctx, bad):
    ctx['box']['next'] = bad
    assert _get(ctx).get_json()['rates'] is None
    assert Setting.query.get(fx.SETTING_KEY) is None


def test_admin_only_and_flag_closed(ctx, monkeypatch):
    assert _get(ctx, 'emp').status_code == 403
    assert ctx['client'].get('/api/v2/money/rates').status_code in (401, 403)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert _get(ctx).status_code == 404 and ctx['calls'] == []


# ───────────── المنطق في الواجهة (node على v2-logic.js) ─────────────
import sys  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
RATES = {'rates': {'USD': 1, 'EGP': 50, 'SAR': 3.75, 'AED': 3.6725}, 'date': '2026-11-13', 'stale': False}
NOW = 1793000000000
REV3 = [{'date': '2026-11-10', 'source': 'course', 'amount_egp': 12000, 'amount_usd': 0},
        {'date': '2026-11-10', 'source': 'course', 'amount_egp': None, 'needs_fx': True, 'currency': 'SAR', 'amount_original': 850},
        {'date': '2026-11-10', 'source': 'course', 'amount_egp': 0, 'amount_usd': 40}]


@needs_node
def test_money_per_currency_line_and_one_usd_line():
    t = v2_node.logic('util.moneyByCurrency', [{'currency': 'USD', 'amount': 40}, {'currency': 'EGP', 'amount': 12000}, {'currency': 'SAR', 'amount': 850}])
    assert t == '١٢٬٠٠٠ ج و٨٥٠ ر.س و٤٠ دولار'
    b = v2_node.logic('v2MoneyBoard', {'revenues': REV3, 'escrow': [], 'payouts': [], 'rates': RATES}, 'year', NOW)
    inc = next(n for n in b['numbers'] if n['key'] == 'income')
    assert inc['text'] == t and inc['others'] == ''
    # ١٢٠٠٠/٥٠ + ٨٥٠/٣٫٧٥ + ٤٠ = ٢٤٠ + ٢٢٦٫٦٧ + ٤٠ = ٥٠٧
    assert inc['usd'] == 507
    assert b['usdLine']['text'].startswith('تقريبًا بالدولار: دخل ') and '٥٠٧' in b['usdLine']['text']
    assert b['usdLine']['ratesText'] == 'أسعار يوم ٢٠٢٦/١١/١٣'


@needs_node
def test_usd_line_hidden_without_rates_and_a_currency_without_a_rate_drops_its_number():
    b = v2_node.logic('v2MoneyBoard', {'revenues': REV3, 'escrow': [], 'payouts': []}, 'year', NOW)
    assert b['usdLine'] is None and all(n['usd'] is None for n in b['numbers'])
    b = v2_node.logic('v2MoneyBoard', {'revenues': REV3, 'escrow': [], 'payouts': [], 'rates': {'rates': None}}, 'year', NOW)
    assert b['usdLine'] is None
    partial = {'rates': {'USD': 1, 'EGP': 50}, 'date': '2026-11-13'}      # مفيش سعر للريال ⇒ رقم الدخل كله مش بيتعرض بالدولار (مش رقم ناقص)
    b = v2_node.logic('v2MoneyBoard', {'revenues': REV3, 'escrow': [{'amount': 100, 'currency': 'EGP', 'status': 'held'}], 'payouts': [], 'rates': partial}, 'year', NOW)
    n = {x['key']: x for x in b['numbers']}
    assert n['income']['usd'] is None and n['held']['usd'] == 2
    assert b['usdLine']['text'] == 'تقريبًا بالدولار: محجوز ٢ دولار'


@needs_node
def test_stale_rates_say_so():
    b = v2_node.logic('v2MoneyBoard', {'revenues': REV3, 'escrow': [], 'payouts': [], 'rates': dict(RATES, stale=True)}, 'year', NOW)
    assert 'آخر أسعار وصلتنا' in b['usdLine']['ratesText']


@needs_node
def test_a_refund_row_nets_out_of_its_currency_total():
    rows = REV3 + [{'date': '2026-11-11', 'source': 'course', 'amount_egp': -2000, 'amount_usd': 0, 'refund_of': 'P1'},
                   {'date': '2026-11-11', 'source': 'course', 'amount_egp': None, 'needs_fx': True, 'currency': 'SAR', 'amount_original': -850, 'refund_of': 'P2'}]
    inc = v2_node.logic('v2Income', rows, 'year', NOW)
    assert {t['currency']: t['amount'] for t in inc['totals']} == {'EGP': 10000, 'USD': 40}, 'الريال اتخصم بالكامل واختفى'


@needs_node
def test_income_bars_show_each_service_per_currency():
    inc = v2_node.logic('v2Income', REV3, 'year', NOW)
    bars = v2_node.logic('v2IncomeBars', inc, None, 'year', RATES)
    courses = next(r for r in bars['rows'] if r['key'] == 'courses')
    assert courses['text'] == '١٢٬٠٠٠ ج و٨٥٠ ر.س و٤٠ دولار' and courses['width'] == 100
    assert bars['total'] == courses['text']
