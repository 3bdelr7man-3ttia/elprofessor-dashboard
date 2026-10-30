# -*- coding: utf-8 -*-
"""شاشات غير الأدمن (المدرّب · المستثمر · فريق المتابعة · الحساب بانتظار التفعيل) — القسم «roles».

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_roles.py

⛔ صفر شبكة: Flask test client فقط، والمنطق النقي (الأعداد · الجمل · التصنيف) بيتشغّل في node على v2-logic.js.
اللي بيثبّته:
  أ. المسارين: `GET /api/v2/roles/config` (لكل دور · مفتاح الأدوار المستقل · `linked` بلا اسم · no-store) و`POST /api/v2/roles/withdraw`
     (مقفول ⇒ ٤٠٤ بلا كتابة · الأدوار المسموحة · `confirmed:true` بالظبط · العملة والمبلغ · الحدّ الأدنى وقاعدة الرصيد من الدالة الموجودة ·
     سطر تدقيق · طلب ثانٍ للرصيد كله يُرفض) + ما فيش قاعدة فلوس مكرّرة في الملف.
  ب. الربط (ثابت): كتلة الأقسام في index.html · أهداف التغليف موجودة · سطر register فوق العلامة · Dockerfile · نطاق قواعد CSS ·
     نصوص roles.js بلا ممنوعات.
  ج. المنطق (node): كل دالة من V2L.roles بحالاتها (مصدر واقع ⇒ null لا صفر · الصفر الحقيقي · أصفار الفرص «غير محدد بعد» · صيغ العدد · الجمل).
"""
import calendar
import datetime
import json
import os
import re
import sys

import jwt
import pytest

from app import app as flask_app, db, User, AuditLog, WithdrawalRequest  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import roles_fixtures as rf   # noqa: E402
import v2_node                # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = calendar.timegm((2026, 10, 30, 12, 0, 0)) * 1000
DAY = 86400e3


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    import app as appmod
    with flask_app.app_context():
        db.create_all()
        users = rf.seed(appmod)
        heads = {k: _bearer(u) for k, u in users.items()}
        yield {'heads': heads, 'client': flask_app.test_client(), 'users': users}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    monkeypatch.delenv('DASH_V2_ROLES_ENABLED', raising=False)


def _cfg(ctx, who):
    return ctx['client'].get('/api/v2/roles/config', headers=ctx['heads'][who] if who else {})


def _wd(ctx, who, body):
    return ctx['client'].post('/api/v2/roles/withdraw', headers=ctx['heads'][who] if who else {}, json=body)


def _rows():
    return WithdrawalRequest.query.count()


# =================================================================== أ) المسارين
@pytest.mark.parametrize('who,role', [('admin', 'admin'), ('employee', 'employee'), ('trainer', 'trainer'), ('investor', 'investor'), ('viewer', 'viewer'),
                                      ('pending', 'pending'), ('split', 'viewer')])
def test_config_open_to_every_signed_in_role(ctx, who, role):
    r = _cfg(ctx, who)
    assert r.status_code == 200
    j = r.get_json()
    assert j['role'] == role and j['enabled'] is True
    assert r.headers.get('Cache-Control') == 'no-store'


def test_config_without_token_is_401(ctx):
    assert _cfg(ctx, None).status_code == 401


def test_config_switch_values(ctx, monkeypatch):
    for main, roles, want in ((None, None, False), ('false', None, False), ('true', None, True), ('true', 'false', False), ('true', 'FALSE', False),
                              ('true', 'true', True), (None, 'true', False), ('1', None, True)):
        for k, v in (('DASH_V2_ENABLED', main), ('DASH_V2_ROLES_ENABLED', roles)):
            if v is None:
                monkeypatch.delenv(k, raising=False)
            else:
                monkeypatch.setenv(k, v)
        assert _cfg(ctx, 'trainer').get_json()['enabled'] is want, (main, roles)


def test_roles_switch_does_not_close_the_admin_dashboard(ctx, monkeypatch):
    monkeypatch.setenv('DASH_V2_ROLES_ENABLED', 'false')
    r = ctx['client'].get('/api/v2/config', headers=ctx['heads']['admin'])
    assert r.status_code == 200 and r.get_json()['enabled'] is True
    assert _cfg(ctx, 'investor').get_json()['enabled'] is False


def test_linked_is_a_boolean_and_never_leaks_the_name(ctx):
    for who, want in (('trainer', True), ('trainer_unlinked', False), ('investor', True), ('investor_unlinked', False), ('viewer', False)):
        r = _cfg(ctx, who)
        assert r.get_json()['linked'] is want, who
        raw = r.get_data(as_text=True)
        assert 'م. سارة' not in raw and 'المستثمر أحمد' not in raw and 'linked_to_name' not in raw
        assert set(r.get_json()) == {'enabled', 'role', 'linked'}


@pytest.mark.parametrize('who', ['admin', 'employee', 'viewer', 'pending'])
def test_withdraw_denied_for_other_roles(ctx, who):
    n = _rows()
    r = _wd(ctx, who, {'amount': 5000, 'currency': 'EGP', 'confirmed': True})
    assert r.status_code == 403 and _rows() == n


def test_withdraw_without_token(ctx):
    assert _wd(ctx, None, {'amount': 5000, 'currency': 'EGP', 'confirmed': True}).status_code == 401


def test_withdraw_closed_switch_404_and_no_row(ctx, monkeypatch):
    n = _rows()
    body = {'amount': 5000, 'currency': 'EGP', 'confirmed': True}
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _wd(ctx, 'investor', body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store' and _rows() == n
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    monkeypatch.setenv('DASH_V2_ROLES_ENABLED', 'false')
    r = _wd(ctx, 'investor', body)
    assert r.status_code == 404 and _rows() == n


@pytest.mark.parametrize('bad', [None, False, 'true', 1, 'yes', 0, [], {}])
def test_withdraw_needs_confirmed_true_exactly(ctx, bad):
    import app as appmod
    n = _rows()
    body = {'amount': 5000, 'currency': 'EGP'}
    if bad is not None:
        body['confirmed'] = bad
    r = _wd(ctx, 'investor', body)
    assert r.status_code == 400 and r.get_json()['error'] == appmod.V2_CONFIRM_AR and _rows() == n
    assert r.headers.get('Cache-Control') == 'no-store'


@pytest.mark.parametrize('amount,cur', [(5000, 'USD'), (5000, 'usd'), (5000, None), (0, 'EGP'), (-5, 'EGP'), ('abc', 'EGP'), ('5000', 'EGP'), (None, 'EGP'),
                                        (True, 'EGP'), (float('nan'), 'EGP')])
def test_withdraw_bad_amount_or_currency(ctx, amount, cur):
    n = _rows()
    body = {'confirmed': True}
    if amount is not None:
        body['amount'] = amount
    if cur is not None:
        body['currency'] = cur
    r = ctx['client'].post('/api/v2/roles/withdraw', headers=ctx['heads']['investor'], data=json.dumps(body).replace('NaN', 'NaN'),
                           content_type='application/json')
    assert r.status_code == 400 and _rows() == n
    assert r.headers.get('Cache-Control') == 'no-store'


def test_withdraw_unlinked_investor(ctx):
    r = _wd(ctx, 'investor_unlinked', {'amount': 5000, 'currency': 'EGP', 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'] == 'هذا الحساب غير مرتبط بمحفظة مستثمر'


def test_withdraw_minimum_and_balance_come_from_the_existing_function(ctx):
    n = _rows()
    r = _wd(ctx, 'investor', {'amount': 1000, 'currency': 'EGP', 'confirmed': True})    # ٢٠ دولارًا
    assert r.status_code == 400 and 'الحد الأدنى' in r.get_json()['error'] and r.headers.get('Cache-Control') == 'no-store'
    r = _wd(ctx, 'investor', {'amount': 9999999, 'currency': 'EGP', 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'] == 'الرصيد المتاح لا يكفي'
    assert _rows() == n


def test_withdraw_happy_path_investor_then_full_balance_is_refused(ctx):
    n = _rows()
    r = _wd(ctx, 'investor', {'amount': 5000, 'currency': 'EGP', 'confirmed': True})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.headers.get('Cache-Control') == 'no-store'
    wid = r.get_json()['id']
    assert _rows() == n + 1
    row = WithdrawalRequest.query.get(wid)
    assert row.status == 'pending' and abs(row.amount - 100.0) < 0.01
    au = AuditLog.query.filter_by(action='roles.withdraw').order_by(AuditLog.id.desc()).first()
    assert au is not None and au.target == str(wid) and au.actor_email == 'investor@roles.test'
    assert json.loads(au.meta_json) == {'amount': 5000, 'currency': 'EGP'}
    # الرصيد نزل بالمعلّق ⇒ طلب بالرصيد القديم كله مرفوض
    wallet = ctx['client'].get('/api/me/investor-wallet', headers=ctx['heads']['investor']).get_json()
    assert wallet['pending_withdrawals'] == 140.0
    r2 = _wd(ctx, 'investor', {'amount': 25000, 'currency': 'EGP', 'confirmed': True})
    assert r2.status_code == 400 and r2.get_json()['error'] == 'الرصيد المتاح لا يكفي'
    assert _rows() == n + 1


def test_withdraw_happy_path_linked_trainer_with_a_wallet(ctx):
    n = _rows()
    r = _wd(ctx, 'trainer', {'amount': 5000, 'currency': 'EGP', 'confirmed': True})
    assert r.status_code == 200 and _rows() == n + 1


def test_withdraw_route_file_holds_no_second_copy_of_the_money_rules():
    src = _read('backend', 'v2_roles_routes.py')
    assert 'WithdrawalRequest(' not in src
    assert not re.search(r'(?<![\w.])50(?![\w])', src), 'حدّ أدنى مكرّر'
    assert "app.view_functions['request_withdrawal']" in src


# =================================================================== ب) الربط
def test_index_has_one_sections_block_with_roles_lines_in_order():
    html = _read('dashboard-cloud', 'index.html')
    assert html.count('<!-- v2 sections begin -->') == 1 and html.count('<!-- v2 sections end -->') == 1
    blk = html.split('<!-- v2 sections begin -->')[1].split('<!-- v2 sections end -->')[0]
    assert '<link rel="stylesheet" href="v2s/roles.css">' in blk and '<script src="v2s/roles.js"></script>' in blk
    keys = re.findall(r'v2s/([a-z0-9_-]+)\.(?:js|css)', blk)
    assert keys == sorted(keys)
    assert html.index('v2-d2.js') < html.index('<!-- v2 sections begin -->')


def test_patch_targets_still_exist_in_the_inline_script():
    html = _read('dashboard-cloud', 'index.html')
    for fn in ('renderView', 'setRole', 'go', 'roleNavFor', 'renderNav', 'viewTHome', 'viewIHome', 'viewUsers', 'viewCourses', 'viewTopics', 'viewTutorials',
               'viewNews', 'viewContent', 'viewComments', 'viewArticlesAuto'):
        assert re.search(r'\bfunction %s\(' % fn, html), fn
    assert 'const V2_SETTERS' in html and 'const ROLE_NAV' in html
    for name in ('topicsTab', 'courseTab', 'current'):
        assert re.search(r'^\s*(?:let|var)\s[^;\n]*\b%s\b\s*=' % name, html, re.M), name


def test_register_line_sits_right_above_the_marker():
    src = _read('backend', 'app.py')
    assert src.count("__import__('v2_roles_routes').register(app)   # v2s:roles") == 1
    assert "register(app)   # v2s:roles\n# ---- v2 section routes end" in src


def test_dockerfile_copies_the_route_files():
    assert 'v2_*_routes.py' in _read('backend', 'Dockerfile')


def _css_rules(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    out, i, depth, buf, at = [], 0, 0, '', []
    for ch in text:
        if ch == '{':
            head = buf.strip()
            if head.startswith('@'):
                at.append(head)
            else:
                out.append((head, at[:]))
            depth += 1
            buf = ''
        elif ch == '}':
            depth -= 1
            if depth < len(at):
                at = at[:depth] if depth >= 0 else []
            buf = ''
        elif ch == ';' and depth == 0:
            buf = ''
        else:
            buf += ch
    return [r for r in out if r[0]]


def test_css_is_fully_scoped():
    css = _read('dashboard-cloud', 'v2s', 'roles.css')
    rules = _css_rules(css)
    assert rules
    ok = ('.app.v2-roles', '.app.v2ro-', '.v2ro', '.v2rom', '#epModal .modal:has(.v2rom)')
    for head, _at in rules:
        for sel in [s.strip() for s in head.split(',') if s.strip()]:
            if sel.startswith('from') or sel.startswith('to') or re.match(r'^\d+%', sel):
                continue
            assert sel.startswith(ok), 'selector خارج النطاق: ' + sel
            assert not re.match(r'^(\.kpi|\.panel|\.row|body|html)\b', sel)
    assert '#notifPanel' in css and '.app.v2-roles #notifPanel' in css


def test_css_important_only_where_an_inline_style_must_be_beaten():
    css = re.sub(r'/\*.*?\*/', '', _read('dashboard-cloud', 'v2s', 'roles.css'), flags=re.S)
    for head, _at in [r for r in _css_rules(css)]:
        pass
    for m in re.finditer(r'([^{}]+)\{([^{}]*!important[^{}]*)\}', css):
        sel = m.group(1)
        assert '[style' in sel or '#menuBtn' in sel, 'important بلا سبب: ' + sel.strip()[:80]
    assert re.search(r'@media\(max-width:599px\)\{[\s\S]*\.row\[style\]\{grid-template-columns:minmax\(0,1fr\)!important\}', css)


def _strip_comments(js):
    js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    return re.sub(r'(?m)(?<![:\'"\w])//.*$', '', js)


FORBIDDEN = ['يقوّم', 'ماركت', 'mirror', 'العقل', 'المدرّب:', 'الحلقات', 'ذكاء', 'Titch']


@pytest.mark.parametrize('rel', [('dashboard-cloud', 'v2s', 'roles.js'), ('dashboard-cloud', 'v2-logic.js')])
def test_visible_copy_rules(rel):
    js = _read(*rel)
    if rel[-1] == 'v2-logic.js':
        js = js.split('// ===== v2s:roles =====')[1].split('// ===== /v2s:roles =====')[0]
    code = _strip_comments(js)
    for bad in FORBIDDEN:
        assert bad not in code, bad
    assert not re.search(r'\bAI\b', code)
    assert not re.search('[\U0001F300-\U0001FAFF☀-➿]', code)


def test_roles_js_never_assigns_the_inline_script_state():
    code = _strip_comments(_read('dashboard-cloud', 'v2s', 'roles.js'))
    for name in ('current', 'topicsTab', 'courseTab', 'role', 'selected'):
        assert not re.search(r'(?<![\w.$-])%s\s*=[^="\']' % name, code), name


# =================================================================== ج) المنطق (node)
def L(fn, *args):
    return v2_node.logic('roles.' + fn, *args)


def S(data=None, state='ready'):
    return {'state': state, 'data': data}


def iso(days_ago):
    return datetime.datetime.utcfromtimestamp((NOW - days_ago * DAY) / 1000).strftime('%Y-%m-%d')


def pay(status, amt, days=5, rel='دورة'):
    return {'status': status, 'total_egp': amt, 'date': iso(days), 'related_to': rel}


@needs_node
def test_trainer_view_numbers_never_zero_on_a_failed_source():
    me = S({'linked': True})
    cs = S([{'title': 'أ', 'students_count': 10, 'status': 'active'}, {'title': 'ب', 'students_count': 5, 'status': 'draft'}])
    ps = S([pay('accrued', 1200), pay('paid', 800), pay('waived', 300), pay('pending', 50), pay('accrued', 700, days=40)])
    v = L('trainerView', {'me': me, 'courses': cs, 'payouts': ps}, NOW)
    assert v['linked'] is True and v['nums'] == {'courses': 2, 'students': 15, 'due': 1200 + 50 + 700}
    v = L('trainerView', {'me': me, 'courses': S(None, 'error'), 'payouts': ps}, NOW)
    assert v['nums']['courses'] is None and v['nums']['students'] is None and v['nums']['due'] == 1950
    v = L('trainerView', {'me': me, 'courses': cs, 'payouts': S(None, 'error')}, NOW)
    assert v['nums']['due'] is None and v['nums']['courses'] == 2
    v = L('trainerView', {'me': me, 'courses': S(None, 'loading'), 'payouts': S(None, 'idle')}, NOW)
    assert v['nums'] == {'courses': None, 'students': None, 'due': None}


@needs_node
def test_trainer_view_unlinked_and_next_lines():
    cs, ps = S([]), S([pay('paid', 100)])
    v = L('trainerView', {'me': S({'linked': False}), 'courses': cs, 'payouts': ps}, NOW)
    assert v['linked'] is False and v['nums'] == {'courses': None, 'students': None, 'due': None} and v['next'] is None
    v = L('trainerView', {'me': S({'linked': True}), 'courses': cs, 'payouts': ps}, NOW)
    assert v['nums']['courses'] == 0 and v['nums']['due'] == 0 and 'لا توجد دورات مربوطة' in v['next']['text']
    v = L('trainerView', {'me': S({'linked': True}), 'courses': S([{'title': 'أ'}]), 'payouts': S([pay('accrued', 2350)])}, NOW)
    assert v['next']['text'] == 'لك في دفتر الإدارة ٢٬٣٥٠ جنيه لم تُحوَّل بعد.' and v['next']['link']['go'] == 't_earnings'
    v = L('trainerView', {'me': S({'linked': True}), 'courses': S([{'title': 'أ'}]), 'payouts': S([pay('paid', 5)])}, NOW)
    assert v['next'] is None


@needs_node
def test_course_row_chip_meta_and_share():
    base = {'title': 'د', 'students_count': 3, 'price_egp': 1500, 'price_usd': 0, 'start_date': '2026-09-01', 'status': 'active',
            'revenue_split': {'trainer_percent': 40}}
    r = L('courseRow', base)
    assert r['chip'] == {'t': 'مفتوحة', 'tone': 'green'} and r['share'] == 'نصيبك من الدورة: ٤٠٪'
    assert r['meta'].startswith('المسجّلون: ٣ · ١٬٥٠٠ جنيه') and 'تبدأ ١ سبتمبر ٢٠٢٦' in r['meta']
    for st, want in (('draft', 'مسودة'), ('completed', 'انتهت'), ('archived', 'مؤرشفة'), ('zzz', 'غير معروفة')):
        assert L('courseRow', dict(base, status=st))['chip']['t'] == want
    for rs in (None, {}, {'trainer_percent': 0}):
        assert L('courseRow', dict(base, revenue_split=rs))['share'] == 'نصيبك من الدورة: غير محدد بعد'
    assert 'دولار' in L('courseRow', dict(base, price_egp=0, price_usd=40))['meta']
    assert 'مجانية' in L('courseRow', dict(base, price_egp=0))['meta']


@needs_node
def test_trainer_earnings_sums_and_waived_is_outside_every_sum():
    ps = S([pay('accrued', 1200, 5), pay('accrued', 450, 12), pay('paid', 800, 25), pay('waived', 300, 10), pay('accrued', 700, 40), pay('pending', 50, 2)])
    e = L('trainerEarnings', {'payouts': ps, 'wallet': S(None, 'error'), 'active': S([])}, NOW)
    assert e['due'] == 1200 + 450 + 700 + 50 and e['paid'] == 800
    assert e['last30'] == 1200 + 450 + 800 + 50, 'waived والقديم بره'
    assert [r['chip']['t'] for r in e['list']][:2] == ['مستحق', 'مستحق'] and len(e['list']) == 6
    assert e['wallet'] is None
    e = L('trainerEarnings', {'payouts': S(None, 'error'), 'wallet': S(None, 'idle'), 'active': S(None, 'idle')}, NOW)
    assert e['due'] is None and e['paid'] is None and e['last30'] is None and e['list'] == []
    e = L('trainerEarnings', {'payouts': S([]), 'wallet': S({'id': None}), 'active': S([])}, NOW)
    assert e['due'] == 0 and e['wallet'] == {'linked': False}


W = {'id': 1, 'balance': 500, 'balance_egp': 25000, 'total_invested': 600, 'total_invested_egp': 30000, 'total_returns': 540, 'total_returns_egp': 27000,
     'pending_withdrawals': 40, 'level': 'silver'}


@needs_node
def test_wallet_view_states_and_rate():
    assert L('walletView', None) is None
    assert L('walletView', dict(W, id=None)) == {'linked': False}
    v = L('walletView', W)
    assert v['linked'] and v['rate'] == 50 and v['canWithdraw'] and v['minEgp'] == 2500 and v['level'] == 'فضي'
    assert v['pending'] == {'value': 'نحو ٢٬٠٠٠ جنيه', 'note': '٤٠ دولار · تراجعه الإدارة'}
    # الرصيد صفر والمستثمَر غير صفر ⇒ السعر من المستثمَر
    z = dict(W, balance=0, balance_egp=0)
    v = L('walletView', z)
    assert v['rate'] == 50 and v['canWithdraw'] is False and v['balanceEgp'] == 0
    # كله صفر ⇒ بلا سعر: الدولار كما هو، والحدّ الأدنى مجهول
    zero = dict(W, balance=0, balance_egp=0, total_invested=0, total_invested_egp=0, total_returns=0, total_returns_egp=0)
    v = L('walletView', zero)
    assert v['rate'] is None and v['minEgp'] is None and v['pending'] == {'value': '٤٠ دولار', 'note': 'تراجعه الإدارة'}
    v = L('walletView', dict(zero, pending_withdrawals=0))
    assert v['pending']['value'] == '٠ جنيه'
    assert L('walletView', dict(W, level='zzz'))['level'] == 'zzz'


@needs_node
def test_opp_card_dollars_and_the_zero_cases():
    o = {'course_title': 'برنامج', 'trainer_name': 'م. ليلى', 'students_count': 25, 'target_amount': 5000, 'current_funded': 300, 'funding_percent': 6,
         'expected_roi': 35, 'min_investment': 200, 'expected_start': '2026-11-10', 'expected_end': None, 'status': 'open'}
    c = L('oppCard', o)
    assert c['showBar'] and c['pct'] == 6 and c['progressText'] == 'جُمع ٣٠٠ دولار من ٥٬٠٠٠ دولار · ٦٪'
    assert c['roiText'] == '٣٥٪' and c['roiNote'] == 'رقم تقديري حدّدته الإدارة' and c['minText'] == '٢٠٠ دولار' and c['end'] == ''
    for st, want in (('hot', 'إقبال مرتفع'), ('invite_only', 'بدعوة'), ('funded', 'اكتمل التمويل'), ('open', 'مفتوحة'), ('zzz', 'غير معروفة')):
        assert L('oppCard', dict(o, status=st))['chip']['t'] == want
    z = L('oppCard', dict(o, expected_roi=0, target_amount=0, min_investment=0, current_funded=150, funding_percent=0))
    assert z['showBar'] is False and z['roiText'] == 'غير محدد بعد' and z['roiNote'] == '' and z['minText'] == 'غير محدد بعد'
    assert z['progressText'] == 'جُمع ١٥٠ دولار · الهدف غير محدد بعد'
    blob = json.dumps(z, ensure_ascii=False)
    assert not re.search('(?<![٠-٩])٠٪', blob) and not re.search('(?<![٠-٩])٠ دولار', blob) and 'جنيه' not in json.dumps(c, ensure_ascii=False)
    assert L('oppCard', dict(o, funding_percent=240))['pct'] == 100


@needs_node
def test_arabic_digits_greeting_and_counts():
    assert '٥٠' in L('arDigits', 'الحد الأدنى للسحب هو 50 دولار') and '50' not in L('arDigits', 'الحد الأدنى للسحب هو 50 دولار')
    assert L('greeting', {'name': '', 'email': 'a@b.c'}) == 'أهلًا بك' and L('greeting', None) == 'أهلًا بك'
    assert L('greeting', {'name': 'سارة', 'email': 'a@b.c'}) == 'أهلًا، سارة'
    assert '@' not in L('greeting', {'name': 'a@b.c'})
    forms = L('COUNT')
    one = {'course': 'دورة واحدة', 'opp': 'فرصة واحدة', 'invest': 'استثمار واحد', 'member': 'عضو واحد', 'request': 'طلب واحد', 'topic': 'موضوع واحد', 'badge': 'شارة واحدة'}
    for k, f in forms.items():
        assert f[0] == one[k] and len(f) == 4 and f[1].endswith(('ان', 'تان'))


@needs_node
def test_investor_next_priority_and_ready_only():
    wl = S(W)
    opps = S([{'status': 'open'}, {'status': 'hot'}, {'status': 'funded'}])
    n = L('investorNext', {'wallet': wl, 'opps': opps})
    assert n['text'].startswith('طلب سحب بقيمة نحو ٢٬٠٠٠ جنيه (٤٠ دولار)') and n['link'] is None
    n = L('investorNext', {'wallet': S(dict(W, pending_withdrawals=0)), 'opps': opps})
    assert n['text'] == 'لك ٢٥٬٠٠٠ جنيه متاحة للسحب.' and n['link'] == {'label': 'اطلب السحب', 'act': 'withdraw'}
    n = L('investorNext', {'wallet': S(dict(W, pending_withdrawals=0, balance=0, balance_egp=0)), 'opps': opps})
    assert n['text'] == 'الفرص المفتوحة الآن: فرصتان.' and n['link']['go'] == 'i_market'
    n = L('investorNext', {'wallet': S(None, 'error'), 'opps': S([{'status': 'open'}])})
    assert n['text'] == 'الفرص المفتوحة الآن: فرصة واحدة.'
    assert L('investorNext', {'wallet': S(None, 'loading'), 'opps': S(None, 'error')}) is None
    assert L('investorNext', {'wallet': S({'id': None}), 'opps': S([])}) is None
    n = L('investorNext', {'wallet': S(dict(W, pending_withdrawals=0)), 'opps': S([])})
    assert 'link' in n and n['link'].get('act') == 'withdraw' and 'go' not in n['link']


@needs_node
def test_investment_row_roi_and_actual_return():
    x = {'course_title': 'دورة', 'invested_total_egp': 10000, 'created_at': '2026-08-10T10:00:00', 'status': 'completed', 'roi_percent': 12.5, 'actual_return': 130}
    r = L('investmentRow', x, 'history')
    assert r['second'] == 'العائد المحسوب حتى الآن: ١٢٫٥٪' and r['actual'] == 'العائد الفعلي: ١٣٠ دولار' and r['chip']['t'] == 'مكتمل'
    assert L('investmentRow', x, 'active')['actual'] == ''
    r = L('investmentRow', dict(x, course_title='', roi_percent=0), 'active')
    assert r['title'] == 'استثمار' and r['second'] == 'العائد: غير متاح بعد'
    # نسبة سالبة: كلمة «خسارة» لا شرطة قبل الأرقام؛ و-١٠٠٪ (عائد صفر بالحساب) ليست خسارة إلا لو حالتها «خسارة»
    assert L('investmentRow', dict(x, roi_percent=-20), 'active')['second'] == 'العائد المحسوب حتى الآن: خسارة ٢٠٪'
    assert L('investmentRow', dict(x, roi_percent=-100, status='active'), 'active')['second'] == 'العائد: غير متاح بعد'
    assert L('investmentRow', dict(x, roi_percent=-100, status='loss'), 'active')['second'] == 'العائد المحسوب حتى الآن: خسارة ١٠٠٪'
    assert L('investmentRow', dict(x, roi_percent=None), 'active')['second'] == 'العائد: غير متاح بعد'
    for bad in ('-', '\u2212'):
        for ro in (-20, -100, -0.5):
            assert bad not in L('investmentRow', dict(x, roi_percent=ro, status='loss'), 'active')['second']
    for st, want, tone in (('active', 'جارٍ', 'green'), ('pending', 'بانتظار', 'amber'), ('accrued', 'قيد الاحتساب', 'amber'), ('paid', 'صُرف', 'green'),
                           ('loss', 'خسارة', 'red'), ('zzz', 'غير معروفة', 'grey')):
        c = L('investmentRow', dict(x, status=st), 'active')['chip']
        assert c == {'t': want, 'tone': tone}


@needs_node
def test_withdraw_check():
    w = {'balanceEgp': 25000.6}
    assert L('withdrawCheck', '5000', w) == {'ok': True, 'amount': 5000}
    assert L('withdrawCheck', '٥٠٠٠', w) == {'ok': True, 'amount': 5000}
    assert L('withdrawCheck', ' 25,000 ', w)['ok'] is True
    assert L('withdrawCheck', '25000', w)['ok'] is True and L('withdrawCheck', '25001', w)['ok'] is False
    for bad in ('0', '', 'abc', '12.5', '-4', '٠'):
        r = L('withdrawCheck', bad, w)
        assert r == {'ok': False, 'error': 'اكتب مبلغًا صحيحًا لا يزيد على رصيدك المتاح.'}, bad


@needs_node
def test_nav_for_perms_variants():
    base = ['users', 'courses', 'topics', 'tutorials']
    assert [i['id'] for i in L('navFor', 'employee', base, None)] == base
    obj = {'employee': {'modules': ['users', 'topics']}}
    assert [i['id'] for i in L('navFor', 'employee', base, obj)] == ['users', 'topics']
    assert [i['id'] for i in L('navFor', 'employee', base, json.dumps(obj))] == ['users', 'topics']
    assert [i['id'] for i in L('navFor', 'employee', base, {'trainer': {'modules': []}})] == base, 'دور بلا إدخال = الأساس كله'
    assert [i['id'] for i in L('navFor', 'employee', base, {'employee': {'modules': ['users', 'courses', 'tutorials']}})] == ['users', 'courses', 'tutorials']
    assert [i['id'] for i in L('navFor', 'employee', base, '{bad json')] == base
    items = L('navFor', 'trainer', ['t_home', 't_courses', 't_earnings'], None)
    assert [i['label'] for i in items] == ['لوحتي', 'دوراتي', 'أرباحي'] and items[0]['img'] is None and items[1]['img'] == 'courses'


PEOPLE = [{'id': 'a', 'full_name': 'هالة سمير', 'email': 'Hala@Example.test', 'phone': '0100', 'role': 'member', 'trainer_status': 'approved', 'plan_id': 'pro', 'created_at': '2026-04-23T00:00:00Z'},
          {'id': 'b', 'full_name': 'كريم', 'email': 'karim@x.test', 'phone': '', 'role': 'member', 'trainer_status': 'pending', 'is_test': True},
          {'id': 'c', 'name': 'نور', 'email': 'nour@x.test', 'role': 'investor'},
          {'id': 'd', 'full_name': 'مدير', 'email': 'adm@x.test', 'role': 'admin'}, {'id': 'e', 'full_name': 'موظف', 'email': 'stf@x.test', 'role': 'staff'}]


@needs_node
def test_people_filter_counts_capped_and_row():
    assert len(L('peopleFilter', PEOPLE, 'all', '')) == 5
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'trainer', '')] == ['a']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'pending', '')] == ['b']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'admin', '')] == ['d', 'e']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'investor', '')] == ['c']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'test', '')] == ['b']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'all', 'HALA@')] == ['a']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'all', '0100')] == ['a']
    assert [u['id'] for u in L('peopleFilter', PEOPLE, 'all', 'نور')] == ['c']
    assert L('peopleCounts', PEOPLE) == {'all': 5, 'trainer': 1, 'pending': 1, 'admin': 2, 'investor': 1, 'test': 1}
    cap = L('peopleCapped', {'users': PEOPLE[:3], 'count': 900})
    assert cap['capped'] and cap['note'] == 'المعروض أحدث ٣ من ٩٠٠ عضوًا؛ ابحث بالاسم أو البريد لعرض غيرهم.'
    assert L('peopleCapped', {'users': PEOPLE[:3], 'count': 3}) == {'capped': False, 'count': 3, 'note': ''}
    row = L('personRow', PEOPLE[0], {'student': 'طلاب'})
    assert row['name'] == 'هالة سمير' and [c['t'] for c in row['chips']] == ['عضو', 'مدرّب'] and row['meta'] == 'انضم ٢٣ أبريل ٢٠٢٦ · احترافية'
    pub = {d['k']: d['v'] for d in row['details']}
    assert pub['يظهر في الدليل العام'] == 'غير متاح بعد' and pub['الهاتف'] == '0100' and pub['الفئة'] == '—'
    assert {d['k']: d['v'] for d in L('personRow', dict(PEOPLE[0], public_ready=True, segment='student'), {'student': 'طلاب'})['details']}['الفئة'] == 'طلاب'
    assert {d['k']: d['v'] for d in L('personRow', dict(PEOPLE[0], public_ready=False))['details']}['يظهر في الدليل العام'] == 'لا'


PC = [{'title': 'أ', 'is_active': True, 'approval_status': 'approved', 'type': 'recorded_paid', 'price_amount': 450, 'price_currency': 'EGP', 'total_enrolled': 24,
       'instructor_name': 'هالة', 'lesson_count': 12, 'story': None},
      {'title': 'ب', 'is_active': False, 'approval_status': 'pending', 'type': 'recorded_paid', 'price_amount': 0, 'total_enrolled': 0, 'lesson_count': 3},
      {'title': 'ج', 'is_active': False, 'approval_status': 'rejected'}, {'title': 'د', 'is_active': False, 'archived_at': '2026-08-01', 'approval_status': 'approved'},
      {'title': 'هـ', 'is_active': False, 'approval_status': 'approved'},
      {'title': 'و', 'is_active': True, 'type': 'recorded_free', 'story': {'lessons': 24}, 'lesson_count': 0, 'total_enrolled': 5}]


@needs_node
def test_course_status_rows_and_filters():
    got = [L('courseStatus', c) for c in PC]
    assert [g['t'] for g in got] == ['منشورة', 'بانتظار الاعتماد', 'مرفوضة', 'مؤرشفة', 'مسودة', 'منشورة']
    assert got[2]['tone'] == 'red' and got[1]['tone'] == 'amber' and got[0]['tone'] == 'green'
    r = L('pcourseRow', PC[0])
    assert r['meta'] == 'هالة · مسجّلة مدفوعة · ٤٥٠ جنيه · المسجّلون: ٢٤ · الدروس: ١٢'
    r = L('pcourseRow', PC[5])
    assert 'بلا مدرّب' in r['meta'] and 'مجانية' in r['meta'] and 'الدروس: ٢٤' in r['meta'] and 'Titch' not in json.dumps(r, ensure_ascii=False)
    assert L('pcourseCounts', PC) == {'all': 6, 'published': 2, 'pending': 1, 'draft': 1}
    assert len(L('pcourseFilter', PC, 'published')) == 2 and len(L('pcourseFilter', PC, 'pending')) == 1 and len(L('pcourseFilter', PC, 'all')) == 6


TP = [{'title': 'أ', 'status': 'published', 'source': 'expert', 'category': 'عقود', 'comments': 4, 'reactions': 21, 'created_at': '2026-10-01T00:00:00Z', 'summary': 'ملخص'},
      {'question': 'سؤال', 'status': 'pending_review', 'source': 'human'}, {'title': 'ج', 'status': 'weird'}, {'title': 'د', 'status': 'draft', 'summary': 'س' * 700}]


@needs_node
def test_topic_rows_counts_and_summary_cut():
    r = L('topicRow', TP[0])
    assert r['chip'] == {'t': 'منشور', 'tone': 'green'} and r['meta'] == 'خبير · عقود · التعليقات: ٤ · التفاعلات: ٢١ · ١ أكتوبر ٢٠٢٦'
    r = L('topicRow', TP[1])
    assert r['title'] == 'سؤال' and r['chip']['t'] == 'بانتظار المراجعة' and 'التعليقات' not in r['meta'], 'لا رقم مختلق لمصدر غائب'
    assert L('topicRow', TP[2])['chip']['t'] == 'مسودة' and L('topicRow', TP[2])['key'] == 'draft'
    s = L('topicRow', TP[3])['summary']
    assert len(s) == 601 and s.endswith('…')
    c = L('topicCounts', TP)
    assert c == {'all': 4, 'published': 1, 'open': 0, 'merged': 0, 'pending_review': 1, 'draft': 2, 'rejected': 0, 'archived': 0}
    assert len(L('topicFilter', TP, 'draft')) == 2 and len(L('topicFilter', TP, 'all')) == 4


@needs_node
def test_tutorial_groups_order_and_default_section():
    rows = [{'title': 'ج', 'section': '', 'order': 3, 'published': False}, {'title': 'أ', 'section': 'البداية', 'order': 1, 'body': 'نص\nسطر'},
            {'title': 'ب', 'section': 'البداية', 'order': 2, 'video_url': 'https://v.test/1'}]
    g = L('tutorialGroups', rows)
    assert [x['section'] for x in g] == ['البداية', 'عام'] and [i['title'] for i in g[0]['items']] == ['أ', 'ب']
    assert g[1]['items'][0]['published'] is False and g[0]['items'][0]['published'] is True and g[0]['items'][1]['video'] == 'https://v.test/1'
    assert L('tutorialGroups', {'tutorials': rows})[0]['section'] == 'البداية'
    assert L('tutorialGroups', {'x': 1}) == []


@needs_node
def test_staff_next_lines_fire_only_on_a_ready_source_and_use_counts():
    pend = [dict(PEOPLE[1])]
    assert L('staffNext', 'users', {'people': S({'users': pend, 'count': 1})})['text'] == 'طلبات تدريب قيد المراجعة لدى الإدارة: طلب واحد.'
    assert L('staffNext', 'users', {'people': S(None, 'error')}) is None
    assert L('staffNext', 'users', {'people': S({'users': PEOPLE[:1], 'count': 1})}) is None
    assert L('staffNext', 'courses', {'pcourses': S({'courses': PC})})['text'] == 'بانتظار اعتماد الإدارة: دورة واحدة.'
    assert L('staffNext', 'courses', {'pcourses': S({'courses': PC[1:2] * 2})})['text'] == 'بانتظار اعتماد الإدارة: دورتان.'
    assert L('staffNext', 'topics', {'topics': S({'topics': TP})})['text'] == 'مقترحات من الأعضاء بانتظار المراجعة: موضوع واحد.'
    assert L('staffNext', 'topics', {'topics': S(None, 'loading')}) is None
    for v in (L('staffNext', 'courses', {'pcourses': S({'courses': PC[1:2] * 3})}), L('staffNext', 'courses', {'pcourses': S({'courses': PC[1:2] * 11})})):
        assert v['link'] is None
    assert L('staffNext', 'courses', {'pcourses': S({'courses': PC[1:2] * 3})})['text'] == 'بانتظار اعتماد الإدارة: ٣ دورات.'
    assert L('staffNext', 'courses', {'pcourses': S({'courses': PC[1:2] * 11})})['text'] == 'بانتظار اعتماد الإدارة: ١١ دورة.'


@needs_node
def test_badges_view():
    b = [{'label': 'أول استثمار', 'earned': True}, {'label': 'x', 'earned': False}, {'label': '٣ دورات', 'earned': True}]
    v = L('badgesView', b)
    assert v['earned'] == ['أول استثمار', '٣ دورات'] and v['line'] == 'الشارات: ٢ من ٣'
    assert L('badgesView', None) is None


@needs_node
def test_nav_constants_labels_and_headers_are_exact():
    nav = L('NAV')
    assert nav['t_home']['label'] == 'لوحتي' and nav['i_market']['label'] == 'فرص الاستثمار' and nav['tutorials']['label'] == 'دليل الاستخدام'
    assert nav['t_earnings']['desc'] == 'مستحقاتك من الدورات، ومحفظتك إن كانت لك استثمارات'
    assert nav['i_invest']['img'] == 'money' and nav['users']['img'] == 'people' and nav['i_home']['img'] is None


# =================================================================== د) جولة التصليح
def test_account_change_resets_cache_and_state_and_ignores_late_replies():
    js = _strip_comments(_read('dashboard-cloud', 'v2s', 'roles.js'))
    assert 'function resetForAccount' in js and 'SRC = {};' in js and 'S = freshState();' in js
    wrapper = js.split('window.setRole = function')[1].split('var origGo')[0]
    assert 'resetForAccount()' in wrapper and 'syncRoleClass()' in wrapper and 'deactivate()' in wrapper
    assert "style.display = 'none'" in wrapper   # شريط الدور القديم يُكتب من جديد مع كل حساب
    load = js.split('function load(')[1].split('function need')[0]
    assert load.count('gen !== GEN') == 2         # رد متأخر من الحساب السابق يُهمَل (نجاح وفشل)


def test_go_wrapper_lets_tutorials_through_only_when_the_role_has_it():
    js = _strip_comments(_read('dashboard-cloud', 'v2s', 'roles.js'))
    go = js.split('window.go = function')[1].split('window.renderView')[0]
    assert "'tutorials'" not in go and 'navIds().indexOf(mod) < 0' in go


def test_trainer_earnings_does_not_load_the_history_it_never_shows():
    js = _strip_comments(_read('dashboard-cloud', 'v2s', 'roles.js'))
    body = js.split('function viewTEarnings')[1].split('// ----')[0]
    assert "need('me', 'payouts', 'wallet', 'active')" in body and "'history'" not in body.split('var E =')[0]


def test_bell_items_fallback_never_changes_the_admin_bell():
    js = _read('dashboard-cloud', 'dashboard-api.js')
    seg = js.split('notifications: function ()')[1].split('goalsAdvisor')[0]
    assert 'isAdmin' in seg and 'r.notifications || (isAdmin ? null : r.items)' in seg


def test_staff_bell_withdrawal_text_says_dollars_in_arabic(ctx):
    r = ctx['client'].get('/api/notifications', headers=ctx['heads']['employee'])
    assert r.status_code == 200
    items = [i for i in r.get_json()['items'] if i['kind'] == 'withdrawal']
    assert items, 'لازم يكون في طلب سحب معلّق في بيانات الاختبار'
    for i in items:
        assert i['detail'].endswith('دولار') and 'USD' not in i['detail']
    # غير الموظف والأدمن: قائمة فاضية بنفس الشكل
    r = ctx['client'].get('/api/notifications', headers=ctx['heads']['trainer'])
    assert r.get_json() == {'count': 0, 'total': 0, 'items': []}
