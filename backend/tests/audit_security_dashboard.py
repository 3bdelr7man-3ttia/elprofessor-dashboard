# -*- coding: utf-8 -*-
"""AUDIT (workstream security_dashboard, 2026-09-08) — characterisation tests for the
dashboard SERVER's authorization, session and public-writer surface.

These are AUDIT artifacts, not project tests: several of them assert the CURRENT (wrong)
behaviour on purpose, so the ledger has an executable record of each finding and so the
day a fix lands the assertion flips loudly instead of silently. Every such test is marked
`@pytest.mark.xfail(strict=False)`-free and instead asserts the observed value with a
comment naming the finding id — read the docstring before "fixing" one.

NOT collected by the default suite (`python_files = test_*.py`); run it explicitly:

    cd ~/Documents/Playground/elprofessor-dashboard/backend && \
        python3 -m pytest -q tests/audit_security_dashboard.py

Findings exercised here:
  F-095  employee reads the whole finance ledger from the API
  F-011  login: no per-account lockout, no is_active check, IP key depends on a proxy
  F-107  RESOLVED 2026-09-10 — /api/auth/sso removed entirely (the platform's own
         /api/lms/sso/verify was deleted the same day, commit 6733465; the route here
         had already been 403-dead for months and nothing minted a `?sso=` link).
         See tests/test_sso_route_removed.py.
  F-108  30-day token, no jti, no server logout, password rotation does not revoke
  F-118  /robots.txt is swallowed by the SPA catch-all
  F-119  GET /api/content/prerender-cron is public
  NEW    public /api/auth/register is an account-existence oracle + no password floor
Negative results pinned so nobody re-investigates them:
  no path traversal through the static catch-all; no raw-SQL injection surface;
  no file-upload surface; the bridge secret is never echoed in any response body.
"""
import datetime
import os
import re

import jwt
import pytest
from werkzeug.security import generate_password_hash as _gph

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog, Revenue, Expense  # noqa: E402

APP_PY = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app.py')


def gph(pw):
    return _gph(pw, method='pbkdf2:sha256')


def mkuser(email, role, active=True, linked='', pw='P@ssw0rd'):
    u = User.query.filter_by(email=email).first()
    if u:
        return u
    u = User(email=email, password_hash=gph(pw), name=email.split('@')[0], role=role,
             dashboard_role=role, linked_to_name=linked, preferred_currency='AUTO',
             is_active=active)
    db.session.add(u)
    db.session.commit()
    return u


def bearer(user):
    tok = jwt.encode({'user_id': user.id,
                      'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture
def ctx():
    with flask_app.app_context():
        db.create_all()
        users = {
            'admin': mkuser('audit-admin@x.test', 'admin'),
            'employee': mkuser('audit-emp@x.test', 'employee'),
            'trainer': mkuser('audit-tr@x.test', 'trainer', linked='مدرب واحد'),
            'investor': mkuser('audit-inv@x.test', 'investor'),
            'viewer': mkuser('audit-vw@x.test', 'viewer'),
            'disabled': mkuser('audit-fired@x.test', 'employee', active=False),
        }
        if not Revenue.query.filter_by(source='audit-secret-revenue').first():
            db.session.add(Revenue(source='audit-secret-revenue', amount_egp=450000.0,
                                   date=datetime.date(2026, 6, 1), description='رقم لا يراه غير المؤسس'))
            db.session.add(Expense(category='رواتب', description='مرتب المؤسس',
                                   amount_egp=120000.0, date=datetime.date(2026, 6, 1)))
            db.session.commit()
        hdrs = {k: bearer(u) for k, u in users.items() if k != 'disabled'}
        ids = {k: u.id for k, u in users.items()}
    appmod._RATE_BUCKETS.clear()
    # B7/F-011: قفلُ الحساب حالةٌ في الذاكرة أيضًا — بلا مسحها تُسرِّب تستاتُ الدخول
    # الفاشل قفلًا إلى صفوفٍ لاحقة (F-108) فتفشل لسببٍ ليس سببها.
    appmod._LOGIN_FAILURES.clear()
    appmod._LOGIN_LOCKED_UNTIL.clear()
    yield {'client': flask_app.test_client(), 'h': hdrs, 'ids': ids}
    appmod._RATE_BUCKETS.clear()
    appmod._LOGIN_FAILURES.clear()
    appmod._LOGIN_LOCKED_UNTIL.clear()


# --------------------------------------------------------------- F-095 · the finance ledger

# The eleven routes the gap report named, plus /api/audit as the control (admin-only).
LEDGER = ['/api/dashboard', '/api/revenues', '/api/expenses', '/api/assets', '/api/cashflow',
          '/api/partners', '/api/ai/snapshot', '/api/finance/summary', '/api/escrow',
          '/api/escrow/metrics',
          # أُضيف بعد مراجعةٍ خصم: بابٌ حادي عشر على نفس الأرقام (`metrics` + `current`)
          '/api/ai/goals-advisor']


@pytest.fixture(autouse=True)
def _no_ai_calls(monkeypatch):
    """⛔ لا نداء ذكاء من الطقم: goals-advisor يسقط على فرعه الحسابي بلا مفاتيح مزوّدين."""
    from app import AI_PROVIDERS
    for cfg in AI_PROVIDERS.values():
        monkeypatch.delenv(cfg['env_key'], raising=False)


def test_f095_employee_no_longer_reads_the_company_ledger(ctx):
    """FIXED (prelaunch B7). كان: `roles_required('admin','employee')` على كل مسار مالي
    بينما تعليق الكود نفسه يَعِد الموظّف «بلا أرقام مالية» — إخفاءُ عنصر القائمة ليس بوّابة.
    الآن: الاثنا عشر كلُّها `403`. و`/api/ai/snapshot` كان الاستثناءَ الأخير (اعتمادًا على
    قناعٍ داخليّ) حتى بان أن القناع يسيب `raw_bank_*` — مصدرُهما `Setting` لا الصفوف — فصار
    أدمن-فقط هو أيضًا (٢٠٢٦-٠٩-٠٨).
    ⛔ حُدِّث هنا بأمرٍ من نصّ التست القديم نفسه: «change it to assert 403 then, do not
    delete it». المصفوفة الكاملة (مسار × دور) في tests/test_finance_authz.py."""
    codes = {p: ctx['client'].get(p, headers=ctx['h']['employee']).status_code
             for p in LEDGER}
    assert set(codes.values()) == {403}, codes
    snap = ctx['client'].get('/api/ai/snapshot', headers=ctx['h']['employee'])
    assert snap.status_code == 403
    assert 'audit-secret-revenue' not in snap.get_data(as_text=True)
    # والأدمن ما زال يقرأ — لا يُثبَّت غيابٌ وحده أبدًا
    admin_codes = {p: ctx['client'].get(p, headers=ctx['h']['admin']).status_code
                   for p in LEDGER}
    assert set(admin_codes.values()) == {200}, admin_codes


@pytest.mark.parametrize('role', ['trainer', 'investor', 'viewer'])
def test_f095_control_every_other_non_admin_role_is_denied(ctx, role):
    """The control that proves the gate itself works — only 'employee' is over-granted."""
    codes = {p: ctx['client'].get(p, headers=ctx['h'][role]).status_code for p in LEDGER}
    assert set(codes.values()) == {403}, codes


def test_audit_log_is_admin_only_for_every_role(ctx):
    for role in ('employee', 'trainer', 'investor', 'viewer'):
        assert ctx['client'].get('/api/audit', headers=ctx['h'][role]).status_code == 403


# ------------------------------------------------------------------ F-011 · the login door

def _login_burst(client, n, env_of, email=None):
    """B7/F-011: البريد يختلف في كل محاولة افتراضيًّا. قفلُ الحساب الجديد مفتاحه البريد،
    فبريدٌ واحدٌ لأربع عشرة محاولة كان سيُظهر ٤٢٩ من قفل الحساب لا من دلو العنوان —
    وهذه التستات تقيس **دلو العنوان** وحده. مرّر `email=` صراحةً لقياس القفل نفسه."""
    appmod._LOGIN_FAILURES.clear()
    appmod._LOGIN_LOCKED_UNTIL.clear()
    return [client.post('/api/auth/login',
                        json={'email': email or ('burst%d@x.test' % i), 'password': 'wrong%d' % i},
                        environ_overrides=env_of(i)).status_code for i in range(n)]


def test_f011_fixed_slice_forged_left_xff_no_longer_buys_unlimited_guesses(ctx):
    """FIXED by e4aace6: `_client_ip` now takes the RIGHTMOST X-Forwarded-For entry — the one
    the proxy appended — so rotating the forged left entries no longer mints a fresh bucket."""
    appmod._RATE_BUCKETS.clear()
    codes = _login_burst(ctx['client'], 14,
                         lambda i: {'HTTP_X_FORWARDED_FOR': 'evil%d.%d.%d.%d, 203.0.113.7' % (i, i, i, i)})
    assert codes.count(429) == 4 and codes[:10] == [401] * 10, codes


def test_f011_fixed_slice_cf_header_is_ignored_without_trust_cf_headers(ctx):
    appmod._RATE_BUCKETS.clear()
    codes = _login_burst(ctx['client'], 14,
                         lambda i: {'HTTP_CF_CONNECTING_IP': '10.0.0.%d' % i,
                                    'REMOTE_ADDR': '203.0.113.7'})
    assert 429 in codes, codes


def test_f011_open_slice_the_fix_holds_only_while_a_proxy_appends_the_real_ip(ctx):
    """OPEN (environment-dependent). If ANY request reaches gunicorn without a proxy having
    appended the connecting address (direct container access, or a proxy configured not to
    append), the rightmost entry is again attacker-chosen and the limit evaporates. Pinning
    the behaviour so the dependency is never forgotten."""
    appmod._RATE_BUCKETS.clear()
    codes = _login_burst(ctx['client'], 14,
                         lambda i: {'HTTP_X_FORWARDED_FOR': '10.0.0.%d' % i,
                                    'REMOTE_ADDR': '203.0.113.7'})
    assert codes == [401] * 14, codes          # no 429 anywhere


def test_f011_fixed_slice_a_per_account_lockout_now_exists(ctx):
    """FIXED (prelaunch B7). كان: مفتاح الدلو `login:<ip>` وحده، فاثنا عشر عنوانًا =
    اثنتا عشرة محاولة مجّانية على أدمن معروف (قِيست: `[401]*12`). الآن عدّادٌ ثانٍ مفتاحه
    **البريد** يقفل الحساب بعد `LOGIN_FAIL_LIMIT` محاولة مهما تغيّر العنوان."""
    src = open(APP_PY, encoding='utf-8').read()
    # ⚠️ حُدِّثت صياغة السطرين بعد مراجعةٍ خصم (العنوان صار متغيّرًا كي يُمرَّر إلى القفل
    # فلا يُحجَب جهازٌ سبق أن نجح منه دخول)؛ **السلوك المُثبَّت هو هو**: دلو العنوان باقٍ،
    # والقفل مفتاحه البريد. الفحص السلوكي أسفل الدالّة هو الحكم لا نصّ السطر.
    assert "client_ip = _client_ip()" in src
    assert "_rate_ok('login:' + client_ip, 10, 300)" in src         # دلو العنوان باقٍ
    assert '_login_locked(email, client_ip)' in src and '_login_failed(email)' in src
    appmod._RATE_BUCKETS.clear()
    appmod._LOGIN_FAILURES.clear()
    appmod._LOGIN_LOCKED_UNTIL.clear()
    per_ip = [ctx['client'].post('/api/auth/login',
                                 json={'email': 'audit-admin@x.test', 'password': 'x'},
                                 environ_overrides={'REMOTE_ADDR': '198.51.100.%d' % i}).status_code
              for i in range(12)]
    n = appmod.LOGIN_FAIL_LIMIT
    assert per_ip[:n - 1] == [401] * (n - 1), per_ip
    assert set(per_ip[n - 1:]) == {429}, per_ip


def test_f011_fixed_slice_a_disabled_account_gets_no_token_and_an_honest_audit_row(ctx):
    """FIXED (prelaunch B7). كان: `login()` لا يفحص `is_active` إطلاقًا ⇒ حسابٌ موقوف
    يأخذ `200` وتوكنًا ثلاثينيًّا وسطرَ تدقيقٍ يُقرأ **كنجاح**. التوكن كان عقيمًا (قارئو
    `Authorization` يفحصون `is_active`) فالضرر كان صدقَ الدفتر وواجهةً تكذب — وهذا ما أُصلح."""
    appmod._RATE_BUCKETS.clear()
    appmod._LOGIN_FAILURES.clear()
    appmod._LOGIN_LOCKED_UNTIL.clear()
    r = ctx['client'].post('/api/auth/login',
                           json={'email': 'audit-fired@x.test', 'password': 'P@ssw0rd'},
                           environ_overrides={'REMOTE_ADDR': '203.0.113.44'})
    assert r.status_code == 403, r.get_data(as_text=True)[:200]
    assert 'token' not in r.get_json()
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='auth.login',
                                        actor_email='audit-fired@x.test').count() == 0
        assert AuditLog.query.filter_by(action='auth.login_blocked_inactive',
                                        actor_email='audit-fired@x.test').count() >= 1


# --------------------------------------------------- NEW · public register is an oracle

def test_register_tells_an_anonymous_visitor_which_emails_exist(ctx):
    """NEW FINDING. 409 «هذا البريد مسجل بالفعل» vs 201 separates a real staff address from a
    made-up one, with no auth, five probes an hour per address. `login` is careful to answer
    401 for both cases — this route undoes that."""
    appmod._RATE_BUCKETS.clear()
    env = {'REMOTE_ADDR': '198.51.100.77'}
    known = ctx['client'].post('/api/auth/register',
                               json={'email': 'audit-admin@x.test', 'password': 'Xx123456', 'name': 'z'},
                               environ_overrides=env)
    unknown = ctx['client'].post('/api/auth/register',
                                 json={'email': 'no-such-person@x.test', 'password': 'Xx123456', 'name': 'z'},
                                 environ_overrides=env)
    assert known.status_code == 409 and unknown.status_code == 201


def test_register_accepts_a_one_character_password(ctx):
    """NEW FINDING (P3). No strength floor: the account is inactive until an admin activates
    it, but the password it was created with survives activation unchanged."""
    appmod._RATE_BUCKETS.clear()
    r = ctx['client'].post('/api/auth/register',
                           json={'email': 'audit-weak@x.test', 'password': '1', 'name': 'z'},
                           environ_overrides={'REMOTE_ADDR': '198.51.100.78'})
    assert r.status_code == 201


# ------------------------------------------------------------------- public contact form

def test_messages_rate_limit_is_real_and_two_tiered(ctx):
    """FIXED by e4aace6 — pinned: five VALID messages an hour per real IP, and a loose sixty
    per hour that a malformed payload cannot dodge."""
    appmod._RATE_BUCKETS.clear()
    good = [ctx['client'].post('/api/messages',
                               json={'name': 'n', 'email': 'a@b.co', 'body': 'رسالة حقيقية'},
                               environ_overrides={'HTTP_X_FORWARDED_FOR': 'forged, 198.51.100.5'}
                               ).status_code for _ in range(8)]
    assert good[:5] == [200] * 5 and good[5:] == [429] * 3, good
    appmod._RATE_BUCKETS.clear()
    junk = [ctx['client'].post('/api/messages', json={},
                               environ_overrides={'HTTP_X_FORWARDED_FOR': '198.51.100.6'}
                               ).status_code for _ in range(64)]
    assert junk.index(429) == 60, junk.index(429)


# --------------------------------------------------------------------------- F-107 · SSO

def test_f107_sso_route_removed(ctx):
    """RESOLVED 2026-09-10 — the finding is moot because the route it described is gone:
    `sso_login`/`/api/auth/sso` were deleted from app.py the same day the platform deleted
    its own `/api/lms/sso/verify` (commit 6733465). No account-resurrection path remains
    because there is no SSO entry point left at all. Full coverage (rule gone from
    url_map, `lms/sso` string gone, plain login unaffected) lives in
    tests/test_sso_route_removed.py — this stub only keeps the finding id traceable in
    the ledger. (405, not 404: the SPA catch-all still matches the path for GET, so
    Werkzeug answers method-not-allowed — same as any other unrouted path.)"""
    assert not hasattr(appmod, 'sso_login')
    r = ctx['client'].post('/api/auth/sso', json={'sso': 'anything'})
    assert r.status_code == 405


# ----------------------------------------------------------------------- F-108 · sessions

def test_f108_token_is_thirty_days_with_no_jti_and_no_server_logout(ctx):
    appmod._RATE_BUCKETS.clear()
    tok = ctx['client'].post('/api/auth/login',
                             json={'email': 'audit-admin@x.test', 'password': 'P@ssw0rd'}
                             ).get_json()['token']
    claims = jwt.decode(tok, flask_app.config['SECRET_KEY'], algorithms=['HS256'])
    assert sorted(claims) == ['exp', 'user_id']           # no jti, no iat, no iss/aud
    life = datetime.datetime.utcfromtimestamp(claims['exp']) - datetime.datetime.utcnow()
    assert 29 <= life.days <= 30
    assert ctx['client'].post('/api/auth/logout',
                              headers={'Authorization': 'Bearer ' + tok}).status_code == 405


def test_f108_rotating_the_password_does_not_revoke_a_live_token(ctx):
    appmod._RATE_BUCKETS.clear()
    tok = ctx['client'].post('/api/auth/login',
                             json={'email': 'audit-admin@x.test', 'password': 'P@ssw0rd'}
                             ).get_json()['token']
    with flask_app.app_context():
        u = User.query.filter_by(email='audit-admin@x.test').first()
        u.password_hash = gph('a-brand-new-password')
        db.session.commit()
    assert ctx['client'].get('/api/revenues',
                             headers={'Authorization': 'Bearer ' + tok}).status_code == 200
    # deactivation, by contrast, DOES take effect immediately — do not describe the session
    # model as «unrevocable» without this caveat.
    with flask_app.app_context():
        u = User.query.filter_by(email='audit-admin@x.test').first()
        u.is_active = False
        db.session.commit()
    assert ctx['client'].get('/api/revenues',
                             headers={'Authorization': 'Bearer ' + tok}).status_code == 401
    with flask_app.app_context():
        u = User.query.filter_by(email='audit-admin@x.test').first()
        u.is_active = True
        u.password_hash = gph('P@ssw0rd')
        db.session.commit()


# ------------------------------------------------------- F-118 / F-119 · exposed surfaces

def test_f118_robots_txt_is_swallowed_by_the_spa_catch_all(ctx):
    r = ctx['client'].get('/robots.txt')
    assert r.status_code == 200
    assert 'X-Robots-Tag' not in r.headers


def test_f119_prerender_cron_status_is_public_on_get(ctx):
    r = ctx['client'].get('/api/content/prerender-cron')
    assert r.status_code == 200 and 'ready' in r.get_json()
    assert ctx['client'].post('/api/content/prerender-cron').status_code == 401


# ----------------------------------------------------- negative results (do not re-open)

@pytest.mark.parametrize('path', ['/../app.py', '/..%2fapp.py', '/%2e%2e/app.py',
                                  '/static/../app.py'])
def test_no_path_traversal_through_the_spa_catch_all(ctx, path):
    """send_from_directory's safe_join refuses every spelling — pinned so a future
    hand-rolled `open(os.path.join(...))` in serve_frontend is caught."""
    r = ctx['client'].get(path)
    assert r.status_code == 404


def test_no_raw_sql_is_built_from_request_data():
    """Every `text(...)` in app.py is a constant DDL migration; the single f-string
    interpolates a name from a hard-coded tuple (app.py:7083-7086)."""
    src = open(APP_PY, encoding='utf-8').read()
    for m in re.finditer(r'text\(\s*f?["\']', src):
        line = src[:m.start()].count('\n') + 1
        frag = src[m.start():m.start() + 200]
        assert 'request.' not in frag and 'd.get' not in frag, 'line %d: %s' % (line, frag[:80])


def test_no_file_upload_surface_exists():
    src = open(APP_PY, encoding='utf-8').read()
    assert 'request.files' not in src and 'secure_filename' not in src


def test_the_bridge_secret_is_never_echoed_to_a_client(ctx):
    """The platform<->dashboard service secret lives only in the environment: it is not a row
    in `settings`, so even an admin's GET /api/settings cannot surface it."""
    body = ctx['client'].get('/api/settings', headers=ctx['h']['admin']).get_json()
    assert appmod.PLATFORM_METRICS_SECRET not in repr(body)
    assert not any('metrics' in str(k).lower() and 'secret' in str(k).lower() for k in body)
    for role in ('employee', 'trainer', 'investor', 'viewer'):
        assert ctx['client'].get('/api/settings', headers=ctx['h'][role]).get_json() \
            .keys() <= {appmod.ROLE_PERMISSIONS_KEY}


# ------------------------------------- NEW · employee ⇒ admin, through an unescaped sink

DASHBOARD_HTML = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'dashboard-cloud', 'index.html')
XSS = '<img src=x onerror="fetch(\'/steal?t=\'+localStorage.token)">'


def test_new_employee_can_store_html_in_a_course_title_and_trainer_name(ctx):
    """NEW FINDING, first half. `POST /api/courses` is open to 'employee' (app.py:4358-4360)
    and stores the title/trainer verbatim. Second half is the grep below: `drawCourse`'s
    native-course branch interpolates them with no esc(). Chained with the 30-day localStorage
    token this is employee ⇒ admin."""
    r = ctx['client'].post('/api/courses', headers=ctx['h']['employee'],
                           json={'title': XSS, 'trainer_name': XSS, 'price_egp': 0})
    assert r.status_code in (200, 201), r.get_data(as_text=True)[:200]
    rows = ctx['client'].get('/api/courses', headers=ctx['h']['admin']).get_json()
    rows = rows if isinstance(rows, list) else rows.get('courses', [])
    assert any(c.get('title') == XSS for c in rows)


def test_new_the_course_drawer_now_escapes_the_title_and_the_instructor(ctx):
    """FIXED (prelaunch B7 · F-135). الفروع الشقيقة في نفس الدالّة (`esc(p.title)` ·
    `esc(tr.name)` · `esc(sc.title)`) كانت الدليل أنّه سهوٌ لا تصميم — والآن الفرع `c`
    مثلها. الدالّة نفسها تُشغَّل في tests/test_xss_sinks_round2.py."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    assert '<h3>${c.title}</h3>' not in src
    assert '<div class="val">${c.inst}</div>' not in src
    assert '<h3>${esc(c.title)}</h3>' in src        # drawCourse, native-course branch
    assert '<div class="val">${esc(c.inst)}</div>' in src


def test_new_the_price_offers_screen_escapes_all_three_fields(ctx):
    """FIXED (prelaunch B7 · F-142). صياغة `renderUsers` نُسخت حرفيًّا على تعبير الصفة،
    وعنوانُ الدورة والمشتري صارا مهرَّبين في الصفّ والدرج معًا."""
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    assert '<div class="parties">${o.course}</div>' not in src
    assert '${o.buyer} · ${SEG_LABEL[o.segment]||o.segment}' not in src
    assert '<div class="parties">${esc(o.course)}</div>' in src
    assert '${esc(o.buyer)} · ${SEG_LABEL[o.segment]||esc(o.segment)}' in src
    assert 'SEG_LABEL[u.segment]||esc(u.segment)' in src        # التوأم المهرَّب أصلًا


def test_new_the_escrow_screen_escapes_bridge_written_names(ctx):
    """NEW FINDING (P3 today — no live producer). `student_name`/`expert_name` reach the DB
    through `POST /api/escrow/hold` and `POST /api/metrics/finance-event` (kind=escrow_hold),
    i.e. over the SHARED SECRET, not from an admin's keyboard — so classifying these sinks as
    «self-XSS, admin-written» (F-114) is wrong. FIXED (prelaunch B7 · F-144): the five sinks
    are escaped and both names are capped at 255 on the way in."""
    r = ctx['client'].post('/api/escrow/hold',
                           headers={'X-ELP-Metrics-Secret': appmod.PLATFORM_METRICS_SECRET},
                           json={'amount': 100, 'student_name': XSS, 'expert_name': XSS,
                                 'expert_email': 'e@x.test', 'currency': 'EGP'})
    assert r.status_code == 201, r.get_data(as_text=True)[:200]
    rows = ctx['client'].get('/api/escrow', headers=ctx['h']['admin']).get_json()
    rows = rows if isinstance(rows, list) else rows.get('sessions', [])
    # التخزين ما زال حرفيًّا — الدفاع هروبٌ عند الرسم لا تشويهٌ عند الكتابة
    assert any(e.get('student_name') == XSS for e in rows)
    src = open(DASHBOARD_HTML, encoding='utf-8').read()
    assert '${e.student}<span class="arr">←</span><span class="exp">${e.expert}</span>' not in src
    assert '${esc(e.student)}<span class="arr">←</span><span class="exp">${esc(e.expert)}</span>' in src


def test_new_rate_limit_buckets_are_never_pruned(ctx):
    """NEW FINDING (P3). `_rate_ok` expires timestamps inside a bucket but never removes an
    empty bucket, so `_RATE_BUCKETS` grows one key per distinct IP per route, forever, in a
    single-worker gunicorn that is not restarted between deploys."""
    appmod._RATE_BUCKETS.clear()
    for i in range(200):
        ctx['client'].post('/api/messages', json={},
                           environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.%d.%d' % (i // 250, i % 250)})
    assert len(appmod._RATE_BUCKETS) >= 200
