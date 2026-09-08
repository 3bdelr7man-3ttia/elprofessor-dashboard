# -*- coding: utf-8 -*-
"""F-095 (+ شرط F-122) — مَن يقرأ الدفتر المالي في الداشبورد؟

Run:  cd backend && python3 -m pytest -q tests/test_finance_authz.py

العطل: عشرة مسارات مالية كانت `@roles_required('admin', 'employee')` بينما الكود نفسه
يُعلن العكس (تعليق «employee mode … بلا أرقام مالية»، ولا وحدة `finance` في `ROLE_NAV`)
⇒ الإخفاء كان **واجهةً لا بوّابة**: توكن `employee` يرجع `200` بالإيراد الكامل ورواتب
المؤسّس، بينما `trainer`/`investor`/`viewer` يرجعون `403`.

وF-122 شرطٌ على هذا الإصلاح لا صفٌّ مستقلّ: صفر تستات كانت تثبّت مَن يقرأ المال، فالانحراف
عاد صامتًا مرّتين. المصفوفة أدناه هي الحارس: **كل مسار × كل دور**.

⛔ `/api/ai/snapshot` **دخل القائمة** في الجولة الأخيرة (٢٠٢٦-٠٩-٠٨) بعد ما بان أن القناع
   الداخلي (`else: # employee/viewer: no money at all`) بيصفّر الصفوف وحدها ويسيب
   `raw_bank_revenue_egp`/`raw_bank_expenses_egp` — مصدرهما `Setting` لا الصفوف — تخرج
   كاملةً للموظّف. ونصف قطر الإغلاق صفر: صفر نداء للمسار في `dashboard-cloud/`، وموديولات
   `ROLE_NAV.employee` هي users·courses·topics·tutorials. فبوّابةٌ **وقناع**، لا واحد منهما:
   الدور اتشال من `roles_required`، والقناع نفسه اتسدّ (تست `raw_bank` أسفل الملف).
"""
import datetime

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import (app as flask_app, db, User, Revenue, Expense,  # noqa: E402
                 Payout, Partner, Asset, CashTransaction)

# المسارات المالية العشرة — الطريقة GET في كلّها.
FINANCE_ROUTES = [
    '/api/dashboard',
    '/api/revenues',
    '/api/expenses',
    '/api/assets',
    '/api/cashflow',
    '/api/partners',
    '/api/finance/summary',
    '/api/escrow',
    '/api/disputes',
    '/api/escrow/metrics',
    # الباب الحادي عشر، فتحه مراجعٌ خصم بعد الإصلاح الأوّل: مستشار الأهداف كان
    # `roles_required('admin','employee')` ويردّ `metrics` كاملة + `current` داخل الأهداف
    # المقترحة ⇒ نفس الدفتر من مسارٍ آخر. المصفوفة أدناه هي ما يمنع تكرار ذلك.
    '/api/ai/goals-advisor',
    # والباب الثاني عشر (٠٩-٠٨): لقطة الذكاء — كانت مفتوحةً للموظّف اعتمادًا على قناعٍ
    # داخليٍّ **مثقوب** (`raw_bank_*` من `Setting` تعدّيه). بوّابةً الآن، لا قناعًا وحده.
    '/api/ai/snapshot',
]

NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']

SECRET_REVENUE = 450000.0
SECRET_EXPENSE_LABEL = 'مرتب المؤسس'


def _mkuser(email, role, active=True):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = active
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=active)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id,
                      'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(autouse=True)
def _no_ai_calls(monkeypatch):
    """⛔ لا نداء ذكاء من الطقم أبدًا: `/api/ai/goals-advisor` يسقط على فرعه الحسابي
    حين لا يكون أي مفتاح مزوّدٍ مضبوطًا، فتُنزع المفاتيح الثلاثة من البيئة هنا."""
    import os
    from app import AI_PROVIDERS
    for cfg in AI_PROVIDERS.values():
        monkeypatch.delenv(cfg['env_key'], raising=False)
    assert not any(os.environ.get(c['env_key']) for c in AI_PROVIDERS.values())


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('fin-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('fin-admin@x.test', 'admin'))
        # أرقامٌ يسهل التعرّف عليها في أي جسم استجابة
        if not Revenue.query.filter_by(source='finance-authz-revenue').first():
            db.session.add(Revenue(source='finance-authz-revenue', amount_egp=SECRET_REVENUE,
                                   date=datetime.date(2026, 6, 1), description='إيراد سرّي'))
            db.session.add(Expense(category='رواتب', description=SECRET_EXPENSE_LABEL,
                                   amount_egp=120000.0, date=datetime.date(2026, 6, 1),
                                   is_business=True))
            db.session.add(Partner(name='شريك مؤسس', equity_percent=40.0))
            db.session.add(Asset(name='لابتوب', category='أجهزة', value_egp=90000.0))
            db.session.add(CashTransaction(kind='capital_in', amount_egp=1000.0,
                                           date=datetime.date(2026, 6, 2), description='إيداع'))
            db.session.commit()
        yield {'heads': heads, 'client': flask_app.test_client()}


# ---------------------------------------------------------------- المصفوفة

@pytest.mark.parametrize('route', FINANCE_ROUTES)
@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_no_non_admin_role_may_read_a_finance_route(ctx, route, role):
    r = ctx['client'].get(route, headers=ctx['heads'][role])
    assert r.status_code == 403, (role, route, r.status_code, r.get_data(as_text=True)[:200])


@pytest.mark.parametrize('route', FINANCE_ROUTES)
def test_the_admin_still_reads_every_finance_route(ctx, route):
    """النصف الآخر من الحارس: الإصلاح لا يجوز أن يقفل الشاشة على صاحبها."""
    r = ctx['client'].get(route, headers=ctx['heads']['admin'])
    assert r.status_code == 200, (route, r.status_code, r.get_data(as_text=True)[:200])


@pytest.mark.parametrize('route', FINANCE_ROUTES)
def test_an_anonymous_caller_is_rejected_too(ctx, route):
    r = ctx['client'].get(route)
    assert r.status_code == 401, (route, r.status_code)


def test_the_employee_body_carries_no_money_anymore(ctx):
    """ليس رمز الحالة وحده: لا رقم من الدفتر يتسرّب في أي جسم استجابة لموظّف."""
    for route in FINANCE_ROUTES:
        body = ctx['client'].get(route, headers=ctx['heads']['employee']).get_data(as_text=True)
        assert str(int(SECRET_REVENUE)) not in body, route
        assert SECRET_EXPENSE_LABEL not in body, route


def test_ai_snapshot_is_closed_to_the_employee_and_leaks_no_money_field(ctx):
    """كان اسم هذا التست «يبقى مفتوحًا بلا أرقام» ويؤكّد `200` — وقُلب ولم يُحذف
    (٢٠٢٦-٠٩-٠٨): القناع الداخلي كان مثقوبًا بـ`raw_bank_*`، فصار المسار أدمن-فقط.
    والنفي هنا على **الجسم** لا على رمز الحالة وحده: لا اسم حقلٍ ماليّ يظهر أصلًا."""
    r = ctx['client'].get('/api/ai/snapshot', headers=ctx['heads']['employee'])
    assert r.status_code == 403, r.get_data(as_text=True)[:200]
    body = r.get_data(as_text=True)
    assert str(int(SECRET_REVENUE)) not in body
    assert SECRET_EXPENSE_LABEL not in body
    for key in ('total_revenue_egp', 'total_expenses_egp', 'net_profit_egp', 'payout_cost_egp',
                'cash_balance_egp', 'raw_bank_revenue_egp', 'raw_bank_expenses_egp',
                'financials', 'cashflow', 'payouts'):
        assert key not in body, key
    ok = ctx['client'].get('/api/ai/snapshot', headers=ctx['heads']['admin'])
    assert ok.status_code == 200, ok.get_data(as_text=True)[:200]
    assert 'raw_bank_revenue_egp' in ok.get_json()['financials']


def test_the_snapshot_mask_itself_zeroes_the_raw_bank_numbers_for_a_non_admin(ctx):
    """الطبقة الثانية مقيسة مباشرةً على الدالّة لا على المسار: `raw_bank_*` مصدرها
    `Setting` فتصفيرُ الصفوف ما كانش بيمسّها. لو رجع الدور للمسار يومًا، القناع لا يكذب."""
    from flask import g
    from app import generate_ai_snapshot, Setting

    with flask_app.app_context():
        for key, val in (('raw_bank_revenue_egp', '777777'), ('raw_bank_expenses_egp', '333333')):
            row = Setting.query.get(key)
            if row:
                row.value = val
            else:
                db.session.add(Setting(key=key, value=val))
        db.session.commit()
        employee = User.query.filter_by(email='fin-employee@x.test').first()
        admin = User.query.filter_by(email='fin-admin@x.test').first()
        with flask_app.test_request_context('/api/ai/snapshot'):
            g.user = employee
            masked = generate_ai_snapshot()['financials']
            assert masked['raw_bank_revenue_egp'] == 0
            assert masked['raw_bank_expenses_egp'] == 0
            assert masked['total_revenue_egp'] == 0
        with flask_app.test_request_context('/api/ai/snapshot'):
            g.user = admin
            full = generate_ai_snapshot()['financials']
            # المرساة: الرقم موجودٌ فعلًا وقابلٌ للتسرّب — بدونها التست فوق يمرّ فارغًا
            assert full['raw_bank_revenue_egp'] == 777777
            assert full['raw_bank_expenses_egp'] == 333333


def test_the_route_gates_themselves_no_longer_name_employee():
    """حارس نصّي: تعديلٌ من كلمةٍ واحدة يقدر يعيد `'employee'` إلى أي بوّابة أعلاه،
    وهذا يمسكه حتى لو غيّر أحدهم اسم الدالّة أو رتّب الملفّ."""
    import os
    import re
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')
    src = open(path, encoding='utf-8').read()
    lines = src.split('\n')
    for i, line in enumerate(lines):
        m = re.match(r"@app\.route\('([^']+)', methods=\['GET'\]\)\s*$", line.strip())
        if not m or m.group(1) not in FINANCE_ROUTES:
            continue
        gate = [l for l in lines[i + 1:i + 6] if l.startswith('@roles_required')]
        assert gate, m.group(1)
        assert "'employee'" not in gate[0], (m.group(1), gate[0])


def test_the_goals_advisor_body_carries_no_ledger_metrics_for_an_employee(ctx):
    """الحمولة التي أثبتها المراجع الخصم: `metrics.total_revenue_egp` و`current` داخل
    الأهداف المقترحة. الآن الردّ `403` بلا جسمٍ أصلًا — ويبقى الأدمن يقرأه كاملًا."""
    r = ctx['client'].get('/api/ai/goals-advisor', headers=ctx['heads']['employee'])
    assert r.status_code == 403, r.get_data(as_text=True)[:200]
    body = r.get_data(as_text=True)
    for key in ('total_revenue_egp', 'total_expenses_egp', 'net_profit_egp',
                'last_month_revenue_egp', 'suggested_targets'):
        assert key not in body, key
    ok = ctx['client'].get('/api/ai/goals-advisor', headers=ctx['heads']['admin'])
    assert ok.status_code == 200, ok.get_data(as_text=True)[:200]
    payload = ok.get_json()
    assert payload['source'] == 'heuristic'          # الفرع الحسابي — لا نداء ذكاء
    assert 'total_revenue_egp' in payload['metrics']
