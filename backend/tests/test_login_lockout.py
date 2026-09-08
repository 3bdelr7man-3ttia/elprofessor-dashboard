# -*- coding: utf-8 -*-
"""F-011 — الشقّان المتبقّيان في دخول الداشبورد: قفلٌ لكل حساب، وفحص `is_active`.

Run:  cd backend && python3 -m pytest -q tests/test_login_lockout.py

ما قِيس قبل الإصلاح (جولة الفجوات ٠٩-٠٨):
  • ١٢-١٤ محاولة خاطئة من **عناوين مختلفة** على نفس البريد ⇒ صفر منع؛ حدّ المعدّل
    مفتاحه العنوان وحده، فتغييرُ العنوان يُبطله. الآن المفتاح هو **البريد نفسه**.
  • حسابٌ `is_active=False` ⇒ `200` + توكن صالح ثلاثين يومًا + سطر تدقيق `auth.login`
    مكتوبٌ **كنجاح**. التوكن عقيمٌ (قارئو `Authorization` الثلاثة يفحصون `is_active`)،
    لكن الأثر باقٍ: دفتر تدقيقٍ يكذب، وواجهةٌ تُدخِل المستخدم ثم تطرده.

⛔ القفل مفتاحه **البريد المُرسَل** لا حسابٌ موجود — وإلّا صار عرّافًا يقول «هذا مسجَّل».
"""
import datetime
import time

import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog  # noqa: E402

PW = 'CorrectHorse#42'
EMAIL = 'lockout-user@x.test'
DISABLED = 'lockout-disabled@x.test'


def _mkuser(email, active=True, role='admin'):
    u = User.query.filter_by(email=email).first()
    if u:
        u.is_active = active
        u.password_hash = generate_password_hash(PW, method='pbkdf2:sha256')
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash(PW, method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=active)
    db.session.add(u)
    db.session.commit()
    return u


def _reset_login_state():
    appmod._RATE_BUCKETS.clear()
    appmod._LOGIN_FAILURES.clear()
    appmod._LOGIN_LOCKED_UNTIL.clear()
    appmod._LOGIN_STRIKES.clear()
    appmod._LOGIN_KNOWN_IPS.clear()
    appmod._LOGIN_SWEEP_AT[0] = 0.0


@pytest.fixture
def client():
    with flask_app.app_context():
        db.create_all()
        _mkuser(EMAIL)
        _mkuser(DISABLED, active=False)
    _reset_login_state()
    yield flask_app.test_client()
    _reset_login_state()


def _login(client, email, password, ip='203.0.113.1'):
    return client.post('/api/auth/login', json={'email': email, 'password': password},
                       environ_overrides={'HTTP_X_FORWARDED_FOR': ip})


# ---------------------------------------------------------------- (أ) القفل لكل حساب

def test_wrong_passwords_from_many_different_ips_still_lock_the_account(client):
    """جوهر العطل: عنوانٌ جديد لكل محاولة كان يمنح مفتاح حدٍّ جديدًا ⇒ تخمينٌ بلا سقف."""
    codes = []
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        # عنوانٌ حقيقيّ مختلف في كل مرّة (أقصى اليمين هو ما يقرأه _client_ip)
        codes.append(_login(client, EMAIL, 'wrong-%d' % i, ip='198.51.100.%d' % i).status_code)
    assert codes[:-1] == [401] * (appmod.LOGIN_FAIL_LIMIT - 1), codes
    assert codes[-1] == 429, codes


def test_once_locked_even_the_correct_password_is_refused(client):
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)
    r = _login(client, EMAIL, PW, ip='198.51.100.200')
    assert r.status_code == 429, r.get_json()
    assert 'token' not in r.get_json()
    assert r.get_json()['error'] == appmod.LOGIN_LOCK_MESSAGE


def test_the_cooldown_expires_and_the_account_comes_back(client):
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)
    assert _login(client, EMAIL, PW).status_code == 429
    # التهدئة انتهت (بدل انتظار ربع ساعة حقيقية)
    appmod._LOGIN_LOCKED_UNTIL[EMAIL] = time.time() - 1
    r = _login(client, EMAIL, PW, ip='198.51.100.201')
    assert r.status_code == 200, r.get_json()
    assert r.get_json().get('token')
    # ...ولم يبقَ أثرٌ للقفل في الذاكرة (لا تتراكم المفاتيح للأبد)
    assert EMAIL not in appmod._LOGIN_LOCKED_UNTIL
    assert EMAIL not in appmod._LOGIN_FAILURES


def test_a_successful_login_clears_the_failure_history(client):
    """المستخدم الشرعي الذي أخطأ سبع مرّات ثم دخل، لا يورَّث قفلًا من محاولاته القديمة."""
    for i in range(appmod.LOGIN_FAIL_LIMIT - 1):
        assert _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i).status_code == 401
    assert _login(client, EMAIL, PW, ip='198.51.100.210').status_code == 200
    assert EMAIL not in appmod._LOGIN_FAILURES
    # ...والعدّاد بدأ من الصفر: سبعُ محاولاتٍ أخرى ما زالت ٤٠١ لا ٤٢٩
    for i in range(appmod.LOGIN_FAIL_LIMIT - 1):
        assert _login(client, EMAIL, 'wrong', ip='198.51.100.1%02d' % i).status_code == 401


def test_locking_one_account_does_not_lock_another(client):
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)
    r = _login(client, DISABLED, 'anything', ip='198.51.100.220')
    assert r.status_code == 401, r.get_json()      # خطأ اعتماد، لا قفلٌ موروث


def test_the_lock_is_keyed_on_the_submitted_email_so_it_is_not_an_existence_oracle(client):
    """بريدٌ غير مسجَّل يُقفل تمامًا كالمسجَّل — وإلّا لصار فرقُ الردّ إجابةً على
    «هل هذا الحساب موجود؟»."""
    ghost = 'no-such-account@x.test'
    codes = [_login(client, ghost, 'wrong', ip='198.51.100.%d' % i).status_code
             for i in range(appmod.LOGIN_FAIL_LIMIT)]
    assert codes[-1] == 429, codes
    real = [_login(client, EMAIL, 'wrong', ip='198.51.100.1%02d' % i).status_code
            for i in range(appmod.LOGIN_FAIL_LIMIT)]
    assert real == codes, (real, codes)


def test_the_ip_rate_limit_still_works_on_top_of_the_account_lock(client):
    """الطبقة القديمة لم تُستبدل: عشر محاولات من **نفس** العنوان ⇒ ٤٢٩ كذلك."""
    codes = [_login(client, 'a%d@x.test' % i, 'wrong', ip='203.0.113.77').status_code
             for i in range(11)]
    assert codes[-1] == 429, codes


# ---------------------------------------------------------------- (ب) فحص is_active

def test_a_disabled_account_gets_no_token(client):
    r = _login(client, DISABLED, PW, ip='203.0.113.9')
    assert r.status_code == 403, r.get_json()
    body = r.get_json()
    assert 'token' not in body
    assert body['error'] == 'الحساب غير مُفعَّل — بانتظار موافقة الإدارة'


def test_a_disabled_login_is_audited_as_blocked_not_as_a_successful_login(client):
    with flask_app.app_context():
        before = AuditLog.query.filter_by(actor_email=DISABLED).count()
    _login(client, DISABLED, PW, ip='203.0.113.10')
    with flask_app.app_context():
        rows = AuditLog.query.filter_by(actor_email=DISABLED).all()
        assert len(rows) == before + 1
        assert rows[-1].action == 'auth.login_blocked_inactive'
        assert AuditLog.query.filter_by(actor_email=DISABLED, action='auth.login').count() == 0


def test_a_self_registered_pending_account_cannot_log_in(client):
    """التسجيل العامّ يُنشئ `pending` + `is_active=False`؛ قبل الإصلاح كان يأخذ توكنًا
    ثلاثينيًّا يبدو صالحًا للواجهة."""
    email = 'pending-signup@x.test'
    with flask_app.app_context():
        u = User.query.filter_by(email=email).first()
        if u:
            db.session.delete(u)
            db.session.commit()
    r = client.post('/api/auth/register',
                    json={'email': email, 'password': PW, 'name': 'زائر جديد'},
                    environ_overrides={'HTTP_X_FORWARDED_FOR': '203.0.113.30'})
    assert r.status_code == 201, r.get_json()
    r2 = _login(client, email, PW, ip='203.0.113.31')
    assert r2.status_code == 403, r2.get_json()
    assert 'token' not in r2.get_json()


def test_an_active_account_still_logs_in_and_is_audited(client):
    with flask_app.app_context():
        before = AuditLog.query.filter_by(actor_email=EMAIL, action='auth.login').count()
    r = _login(client, EMAIL, PW, ip='203.0.113.40')
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body['token'] and body['user']['email'] == EMAIL
    with flask_app.app_context():
        after = AuditLog.query.filter_by(actor_email=EMAIL, action='auth.login').count()
    assert after == before + 1


def test_both_new_messages_actually_reach_the_login_screen():
    """⛔ «مكتوبٌ صحيحًا وبلا طريقٍ للشاشة»: رسالتان جديدتان بالعربية لا تنفعان إن ابتلعتهما
    طبقة الشبكة. المسار المثبَّت هنا: جسم الردّ ⇒ `e2.message` ⇒ `showErr` ⇒ نصّ العنصر.
    وهو يعمل لأن ٤٢٩ و٤٠٣ ليسا ٤٠١ (الـ٤٠١ وحده يُستبدَل بنصٍّ ثابت)."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    api = open(os.path.join(base, 'dashboard-cloud', 'dashboard-api.js'), encoding='utf-8').read()
    # (١) جسم الخطأ يصير رسالة الاستثناء
    assert 'var e2 = new Error((data && data.error) || ("HTTP " + r.status));' in api
    # (٢) شاشة الدخول ترسم تلك الرسالة نصًّا لكل ما ليس ٤٠١
    assert 'showErr((e && e.status === 401) ? "بيانات الدخول غير صحيحة." ' \
           ': ((e && e.message) || "تعذّر الاتصال بالخادم."));' in api
    assert 'function showErr(t) { errEl.textContent = t; errEl.classList.add("show"); }' in api


def test_the_issued_token_still_lasts_the_documented_thirty_days(client):
    """لم يُمَسّ عمر التوكن في هذا الإصلاح (F-108 صفٌّ منفصل) — يُثبَّت كي لا يتغيّر سهوًا."""
    import jwt
    r = _login(client, EMAIL, PW, ip='203.0.113.41')
    claims = jwt.decode(r.get_json()['token'], flask_app.config['SECRET_KEY'], algorithms=['HS256'])
    left = datetime.datetime.utcfromtimestamp(claims['exp']) - datetime.datetime.utcnow()
    assert 29 <= left.days <= 30, left


# ------------------------------------------------- (أ-٢) المقايضة: قفلٌ لا يصير حجبَ خدمة
# مفتاح القفل بريدٌ **يكتبه المهاجم**، فمن يعرف بريد المؤسس كان يقدر يقفل لوحته ربع ساعة
# بثماني محاولات، ويكرّرها بلا نهاية. الضمانتان أدناه تُبقيان منعَ التخمين وتنزعان السلاح.

def test_the_first_lock_is_one_minute_not_a_quarter_of_an_hour(client):
    """تهدئةٌ متصاعدة: أوّل خطأٍ بريءٍ يكلّف دقيقة، لا ربع ساعة."""
    now = time.time()
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)
    left = appmod._LOGIN_LOCKED_UNTIL[EMAIL] - now
    assert appmod.LOGIN_LOCK_BASE - 5 <= left <= appmod.LOGIN_LOCK_BASE + 5, left


def test_the_cooldown_doubles_with_every_consecutive_lock_up_to_the_cap(client):
    """والتخمين المُصرّ وحده يصل للسقف: ٦٠ ⇒ ١٢٠ ⇒ ٢٤٠ ⇒ ٤٨٠ ⇒ ٩٠٠ (سقفًا)."""
    seen = []
    for rnd in range(5):
        for i in range(appmod.LOGIN_FAIL_LIMIT):
            _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % (rnd * 8 + i))
        now = time.time()
        seen.append(round(appmod._LOGIN_LOCKED_UNTIL[EMAIL] - now))
        appmod._LOGIN_LOCKED_UNTIL[EMAIL] = now - 1     # انتهت، والضربة محفوظة
    assert seen == [60, 120, 240, 480, 900], seen
    assert seen[-1] == appmod.LOGIN_LOCK_MAX


def test_a_stale_strike_decays_so_the_escalation_restarts(client):
    """قفلٌ لم يتكرّر خلال ساعة يُنسى — وإلّا ورث المستخدمُ الشرعيّ تصاعدًا أبديًّا."""
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)
    appmod._LOGIN_LOCKED_UNTIL[EMAIL] = time.time() - 1
    # الضربة صارت قديمة (أكثر من ساعة)
    n, _at = appmod._LOGIN_STRIKES[EMAIL]
    appmod._LOGIN_STRIKES[EMAIL] = (n, time.time() - appmod.LOGIN_STRIKE_DECAY - 1)
    now = time.time()
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.1%02d' % i)
    left = appmod._LOGIN_LOCKED_UNTIL[EMAIL] - now
    assert appmod.LOGIN_LOCK_BASE - 5 <= left <= appmod.LOGIN_LOCK_BASE + 5, left


def test_a_known_device_is_never_locked_out_by_someone_elses_guessing(client):
    """جوهر المقايضة: المهاجم يقفل الحساب من عناوينه، والمؤسس يدخل من جهازه المعتاد."""
    home = '203.0.113.55'
    assert _login(client, EMAIL, PW, ip=home).status_code == 200      # العنوان صار معروفًا
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)        # المهاجم يقفل
    assert appmod._LOGIN_LOCKED_UNTIL.get(EMAIL, 0) > time.time()     # القفل قائمٌ فعلًا
    stranger = _login(client, EMAIL, PW, ip='198.51.100.99')
    assert stranger.status_code == 429, stranger.get_json()           # الغريب ممنوع
    r = _login(client, EMAIL, PW, ip=home)
    assert r.status_code == 200, r.get_json()                         # وصاحب الحساب يدخل
    assert r.get_json().get('token')


def test_a_known_device_still_needs_the_right_password(client):
    """الاستثناء يخصّ القفل وحده — لا يصير بابًا خلفيًّا لكلمة سرّ خاطئة."""
    home = '203.0.113.56'
    assert _login(client, EMAIL, PW, ip=home).status_code == 200
    assert _login(client, EMAIL, 'wrong', ip=home).status_code == 401


def test_the_known_ip_list_is_capped_per_account(client):
    """قائمةٌ مربوطة بالبريد لا تنمو بلا حدّ — آخر خمسة عناوين فقط."""
    for i in range(appmod.LOGIN_KNOWN_IPS_PER_ACCOUNT + 3):
        _login(client, EMAIL, PW, ip='203.0.113.%d' % (100 + i))
    assert len(appmod._LOGIN_KNOWN_IPS[EMAIL]) == appmod.LOGIN_KNOWN_IPS_PER_ACCOUNT


# ------------------------------------------------- (أ-٣) الخريطتان مفتاحهما نصُّ المهاجم

def test_the_failure_and_lock_maps_do_not_grow_for_ever(client):
    """صنف F-145: مفتاحٌ يكتبه المهاجم يبقى صفًّا للأبد في عاملٍ واحد لا يُعاد تشغيله.
    الكنسة الدوريّة تمسح المنتهي حتى لو لم يُسأل عن المفتاح ثانيةً."""
    old = time.time() - appmod.LOGIN_FAIL_WINDOW - 10
    for i in range(200):
        appmod._LOGIN_FAILURES['ghost-%d@x.test' % i] = appmod.deque([old])
        appmod._LOGIN_LOCKED_UNTIL['locked-%d@x.test' % i] = old
        appmod._LOGIN_STRIKES['strike-%d@x.test' % i] = (3, time.time() - appmod.LOGIN_STRIKE_DECAY - 10)
    assert len(appmod._LOGIN_FAILURES) >= 200
    appmod._LOGIN_SWEEP_AT[0] = 0.0                   # حان موعد الكنسة
    appmod._login_sweep()
    assert appmod._LOGIN_FAILURES == {}, list(appmod._LOGIN_FAILURES)[:3]
    assert appmod._LOGIN_LOCKED_UNTIL == {}, list(appmod._LOGIN_LOCKED_UNTIL)[:3]
    assert appmod._LOGIN_STRIKES == {}, list(appmod._LOGIN_STRIKES)[:3]


def test_the_sweep_never_drops_a_live_lock(client):
    """النصف الآخر: الكنسة لا تُطلق سراح حسابٍ ما زال في تهدئته."""
    for i in range(appmod.LOGIN_FAIL_LIMIT):
        _login(client, EMAIL, 'wrong', ip='198.51.100.%d' % i)
    appmod._LOGIN_SWEEP_AT[0] = 0.0
    appmod._login_sweep()
    assert EMAIL in appmod._LOGIN_LOCKED_UNTIL
    assert _login(client, EMAIL, PW, ip='198.51.100.98').status_code == 429


def test_the_sweep_is_throttled_not_run_on_every_call(client):
    """لا تُمشَّط الخريطتان في كل نداء دخول — كنسةٌ كل عشر دقائق تكفي."""
    appmod._LOGIN_SWEEP_AT[0] = 0.0
    appmod._login_sweep()
    first = appmod._LOGIN_SWEEP_AT[0]
    assert first >= time.time() + appmod.LOGIN_SWEEP_EVERY - 5
    appmod._LOGIN_STRIKES['stale@x.test'] = (1, 0.0)
    appmod._login_sweep()                              # لم يحن الموعد ⇒ لا شيء يُمسح
    assert 'stale@x.test' in appmod._LOGIN_STRIKES
    assert appmod._LOGIN_SWEEP_AT[0] == first
