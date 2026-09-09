# -*- coding: utf-8 -*-
"""حارس مساعدي الذكاء في اللوحة — الاسم · التوكنز · السقف اليومي · صدق التعطّل.

Run:  cd backend && python3 -m pytest -q tests/test_ai_model_cap_and_visibility.py

الأعطال التي يحرسها هذا الملف (مراجعة ٢٠٢٦-٠٩-٠٩، AUDIT/dash/03_ai_assistants.md):

- **ع-١** اسم `deepseek-chat` مسحوبٌ من 2026-07-26 ⇒ كل نداء ٤٠٠ ⇒ هبوطٌ صامتٌ على بديلٍ
  ثابت يبدو إجابةً حقيقية. والفخّ التابع: V4 كلّه استدلاليّ، فـ`max_tokens: 1200` = ردٌّ
  فارغ لا خطأ. ⛔ التوكنز **لا تُخفَّض** — 8000 مطابقةً للمنصّة (routes/legal_search.py).
- **الأخطر ماليًّا** لا سقفَ ولا عدّادَ ولا تنبيهَ على نداءات اللوحة (سقف المنصّة F-016 في
  Mongo ولا يرى مفتاح اللوحة إطلاقًا) — أربعة أبوابٍ مفتوحة على رصيدٍ قدره $1.47.
- **صدق التعطّل** كل مساعدٍ كان يهبط صامتًا؛ الآن رسالةٌ عربية بيضاء واحدة + علَمٌ في JSON.

⛔ **صفر نداء ذكاء حقيقي**: كل اختبارٍ هنا يستبدل ناقلَي المزوّد (`call_anthropic` /
`call_openai_compatible`) بدالّةٍ محلّية. لا شبكةَ ولا مفتاحَ حقيقيّ يُقرأ.
"""
import datetime
import io
import os
import re
from pathlib import Path

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import (app as flask_app, db, User, AIDailyUsage, AI_MAX_TOKENS,  # noqa: E402
                 AI_PROVIDERS, AI_UNAVAILABLE_AR, AIUnavailable, ai_call,
                 ai_daily_cap, ai_model_for, ai_provider_in_use, _ai_reserve_call)

DASH_REPO = Path(__file__).resolve().parents[2]          # elprofessor-dashboard
PLAYGROUND = DASH_REPO.parent                            # جارُه المنصّة `elprofessor`


# ═════════════════════════════════════════════════════════════ أدوات مشتركة

def _mkuser(email, role='admin'):
    u = User.query.filter_by(email=email).first()
    if u:
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


@pytest.fixture()
def ctx():
    with flask_app.app_context():
        db.create_all()
        admin = _mkuser('ai-guard-admin@x.test', 'admin')
        yield {'client': flask_app.test_client(), 'admin': _bearer(admin)}


@pytest.fixture()
def deepseek_key(monkeypatch):
    """مفتاحٌ **وهميّ** يجعل `ai_provider_in_use()` يختار DeepSeek بلا أي نداء حقيقي —
    الناقل نفسه مُستبدَلٌ في كل اختبار يصل إلى هذه النقطة."""
    for cfg in AI_PROVIDERS.values():
        monkeypatch.delenv(cfg['env_key'], raising=False)
    monkeypatch.delenv('DASHBOARD_AI_MODEL', raising=False)
    monkeypatch.delenv('AI_PROVIDER', raising=False)
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-not-a-real-key-tests-never-call-out')
    return 'deepseek'


@pytest.fixture()
def isolated_day(monkeypatch, request):
    """يومٌ اصطناعيّ لكل اختبار — عدّادات الاختبارات لا تتلامس ولا تلمس صفَّ اليوم الحقيقي."""
    day = '2099-01-%02d' % ((abs(hash(request.node.name)) % 27) + 1)
    monkeypatch.setattr(appmod, '_ai_utc_day', lambda: day)
    with flask_app.app_context():
        db.create_all()
        row = AIDailyUsage.query.get(day)
        if row:
            db.session.delete(row)
            db.session.commit()
    return day


@pytest.fixture()
def no_network(monkeypatch):
    """⛔ حارسٌ صريح: أي محاولة نداءٍ شبكيّ من داخل هذا الملف تكسر الاختبار."""
    def _boom(*a, **k):   # pragma: no cover - يُنفَّذ فقط عند خرق القاعدة
        raise AssertionError('a test tried to reach the network')
    monkeypatch.setattr(appmod.requests, 'post', _boom)
    monkeypatch.setattr(appmod.requests, 'get', _boom)


# ═════════════════════════════════════════════════ ١) اسم الموديل والتوكنز

def test_deepseek_default_model_is_v4_flash_and_the_retired_aliases_are_gone():
    cfg = AI_PROVIDERS['deepseek']
    assert cfg['default_model'] == 'deepseek-v4-flash'
    assert cfg['models'] == ['deepseek-v4-flash', 'deepseek-v4-pro']
    assert 'deepseek-chat' not in cfg['models']
    assert 'deepseek-reasoner' not in cfg['models']


def test_model_default_and_env_overrides(monkeypatch):
    monkeypatch.delenv('DASHBOARD_AI_MODEL', raising=False)
    monkeypatch.delenv('DEEPSEEK_MODEL', raising=False)
    assert ai_model_for('deepseek') == 'deepseek-v4-flash'
    # التجاوز الخاص بالمزوّد
    monkeypatch.setenv('DEEPSEEK_MODEL', 'deepseek-v4-pro')
    assert ai_model_for('deepseek') == 'deepseek-v4-pro'
    # وتجاوز اللوحة يعلو عليه
    monkeypatch.setenv('DASHBOARD_AI_MODEL', 'deepseek-v4-flash-x')
    assert ai_model_for('deepseek') == 'deepseek-v4-flash-x'


def test_a_retired_model_name_in_the_environment_is_ignored(monkeypatch):
    """⚠️ `docker-compose.yml` و`.env.example` ما زالا يمرّران `DEEPSEEK_MODEL=deepseek-chat`
    (خارج نطاق التعديل المسموح هنا) — فالبيئةُ وحدها كانت كفيلةً بإحياء الاسم الميّت فوق
    الافتراضي الصحيح. الكود يبطلها: اسمٌ مسحوب = يُتجاهَل ويُسجَّل."""
    monkeypatch.delenv('DASHBOARD_AI_MODEL', raising=False)
    for retired in ('deepseek-chat', 'deepseek-reasoner'):
        monkeypatch.setenv('DEEPSEEK_MODEL', retired)
        assert ai_model_for('deepseek') == 'deepseek-v4-flash'
        monkeypatch.setenv('DASHBOARD_AI_MODEL', retired)
        assert ai_model_for('deepseek') == 'deepseek-v4-flash'
        monkeypatch.delenv('DASHBOARD_AI_MODEL', raising=False)


def test_max_tokens_matches_the_platform_and_is_never_lowered(monkeypatch):
    """⛔ V4 استدلاليّ: التوكنز تُستهلك في `reasoning_content` قبل `content`. 1200 = ردٌّ فارغ."""
    assert AI_MAX_TOKENS == 8000
    sent = {}

    class _R:
        status_code = 200

        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {'choices': [{'message': {'content': 'ok'}}],
                    'content': [{'type': 'text', 'text': 'ok'}]}

    def _fake_post(url, **kw):
        sent[url] = kw.get('json') or {}
        return _R()

    monkeypatch.setattr(appmod.requests, 'post', _fake_post)
    appmod.call_openai_compatible('https://api.deepseek.com/v1', 'k', 'deepseek-v4-flash', 's', 'u')
    appmod.call_anthropic('k', 'claude-x', 's', 'u')
    for url, payload in sent.items():
        assert payload['max_tokens'] == 8000, url


def test_the_platform_source_of_truth_still_says_8000():
    """الرقم ليس اختيارًا حرًّا: هو ما ترسله المنصّة في `call_deepseek`. لو تغيّر هناك
    فليتغيّر هنا **بقرار**، لا بانحرافٍ صامت بين المستودعين."""
    p = PLAYGROUND / 'elprofessor' / 'backend' / 'routes' / 'legal_search.py'
    if not p.exists():          # المستودع الشقيق غير موجود في بيئة CI منعزلة
        pytest.skip('platform repo not present')
    src = io.open(p, encoding='utf-8').read()
    assert '"max_tokens": 8000' in src


# ═══════════════════════════════════ ٢) التعطّل مرئيّ — لا هبوطَ صامت

def _fail_transport(monkeypatch, exc=None, text=None):
    """يستبدل ناقلَي المزوّد معًا: إمّا يرميان، وإمّا يرجعان نصًّا (فارغًا لاختبار الفراغ)."""
    def _t(*a, **k):
        if exc is not None:
            raise exc
        return text
    monkeypatch.setattr(appmod, 'call_openai_compatible', _t)
    monkeypatch.setattr(appmod, 'call_anthropic', _t)


def test_ai_call_raises_a_white_arabic_message_on_provider_error(
        ctx, deepseek_key, isolated_day, monkeypatch):
    _fail_transport(monkeypatch, exc=RuntimeError('boom'))
    with pytest.raises(AIUnavailable) as e:
        ai_call('s', 'u', purpose='test')
    assert e.value.message.startswith(AI_UNAVAILABLE_AR + ' — السبب:')
    assert e.value.kind == 'error'
    # ⛔ لا اسمَ مضيفٍ ولا مسار في ما يخرج للعميل (ع-٥)
    assert 'deepseek.com' not in e.value.message
    assert 'boom' not in e.value.message


@pytest.mark.parametrize('empty', ['', '   ', None])
def test_an_empty_reply_is_an_error_not_a_silent_fallback(
        ctx, deepseek_key, isolated_day, monkeypatch, empty):
    _fail_transport(monkeypatch, text=empty)
    with pytest.raises(AIUnavailable) as e:
        ai_call('s', 'u', purpose='test')
    assert e.value.kind == 'empty'
    assert e.value.message.startswith(AI_UNAVAILABLE_AR)


def test_no_key_configured_says_so_by_name(ctx, isolated_day, monkeypatch, no_network):
    for cfg in AI_PROVIDERS.values():
        monkeypatch.delenv(cfg['env_key'], raising=False)
    assert ai_provider_in_use() is None
    with pytest.raises(AIUnavailable) as e:
        ai_call('s', 'u')
    assert e.value.kind == 'no_key'


def test_ai_ask_returns_the_visible_message_and_a_flag_not_a_raw_exception(
        ctx, deepseek_key, isolated_day, monkeypatch):
    _fail_transport(monkeypatch, exc=RuntimeError(
        "HTTPSConnectionPool(host='api.deepseek.com', port=443): Max retries"))
    r = ctx['client'].post('/api/ai/ask', json={'question': 'كام الإيراد؟'},
                           headers=ctx['admin'])
    assert r.status_code == 200
    body = r.get_json()
    assert body['ai_unavailable'] is True
    assert body['response'].startswith(AI_UNAVAILABLE_AR)
    raw = r.get_data(as_text=True)
    assert 'deepseek.com' not in raw and 'HTTPSConnectionPool' not in raw


def test_course_draft_says_unavailable_instead_of_a_generic_retry(
        ctx, deepseek_key, isolated_day, monkeypatch):
    _fail_transport(monkeypatch, exc=RuntimeError('boom'))
    r = ctx['client'].post('/api/courses/ai-draft', json={'idea': 'عقود العمل'},
                           headers=ctx['admin'])
    assert r.status_code == 503
    body = r.get_json()
    assert body['ai_unavailable'] is True
    assert body['error'].startswith(AI_UNAVAILABLE_AR)


def test_goals_advisor_keeps_the_real_numbers_but_declares_the_outage(
        ctx, deepseek_key, isolated_day, monkeypatch):
    _fail_transport(monkeypatch, exc=RuntimeError('boom'))
    r = ctx['client'].get('/api/ai/goals-advisor', headers=ctx['admin'])
    assert r.status_code == 200
    body = r.get_json()
    assert body['ai_unavailable'] is True
    assert body['ai_notice'].startswith(AI_UNAVAILABLE_AR)
    assert body['source'] == 'heuristic'      # الأرقام حسابٌ مباشر لا تلفيق
    assert 'suggested_targets' in body


def test_an_agent_report_names_the_reason_instead_of_blaming_the_key(
        ctx, deepseek_key, isolated_day, monkeypatch):
    """كانت الجملة الوحيدة «المفتاح غير مهيّأ أو الخدمة غير متاحة» تتّهم مفتاحًا سليمًا."""
    monkeypatch.setattr(appmod, '_agent_bundle', lambda a: {'published': 5})
    _fail_transport(monkeypatch, exc=RuntimeError('boom'))
    with flask_app.app_context():
        rep = appmod._run_agent('dev')
    assert rep['source'] == 'data'
    assert rep['ai_unavailable'] is True
    assert rep['summary'].startswith(AI_UNAVAILABLE_AR)
    assert 'أرقام حقيقية' in rep['summary']


# ═════════════════════════════════════════════ ٣) السقف اليومي (SQLite)

def test_the_default_cap_is_150_and_the_env_overrides_it(monkeypatch):
    monkeypatch.delenv('DASHBOARD_AI_DAILY_CAP', raising=False)
    assert ai_daily_cap() == 150
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '7')
    assert ai_daily_cap() == 7
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', 'not-a-number')
    assert ai_daily_cap() == 150      # قيمةٌ فاسدة لا تُسقط السقف ولا ترمي


def test_call_150_passes_and_151_is_blocked_with_the_visible_message(
        ctx, deepseek_key, isolated_day, monkeypatch):
    monkeypatch.delenv('DASHBOARD_AI_DAILY_CAP', raising=False)   # الافتراضي ١٥٠
    with flask_app.app_context():
        for n in range(1, 151):
            allowed, state = _ai_reserve_call()
            assert allowed, n
            assert state['used'] == n
        assert state['remaining'] == 0
        allowed, state = _ai_reserve_call()
        assert allowed is False
        assert state['used'] == 150          # النداء المرفوض لا يُحسب
    # والمرفوض يصل للمؤسس **كرسالة**، لا كـ٥٠٠
    _fail_transport(monkeypatch, text='{"summary":"x"}')
    with pytest.raises(AIUnavailable) as e:
        ai_call('s', 'u')
    assert e.value.kind == 'cap'
    assert 'تجاوزنا سقف اليوم' in e.value.message
    assert e.value.message.startswith(AI_UNAVAILABLE_AR)


def test_a_blocked_call_is_a_200_with_a_message_never_a_500(
        ctx, deepseek_key, isolated_day, monkeypatch, no_network):
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '1')
    with flask_app.app_context():
        assert _ai_reserve_call()[0] is True
        assert _ai_reserve_call()[0] is False
    r = ctx['client'].post('/api/ai/ask', json={'question': 'س'}, headers=ctx['admin'])
    assert r.status_code == 200
    body = r.get_json()
    assert body['ai_unavailable'] is True
    assert 'تجاوزنا سقف اليوم' in body['response']
    r2 = ctx['client'].get('/api/ai/goals-advisor', headers=ctx['admin'])
    assert r2.status_code == 200
    assert 'تجاوزنا سقف اليوم' in r2.get_json()['ai_notice']


def test_the_counter_resets_on_the_next_utc_day(monkeypatch):
    """التصفير بتغيّر مفتاح اليوم (UTC) لا بمؤقّت — فلا شيءَ يُنسى عند إعادة النشر."""
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '2')
    day = {'v': '2099-06-01'}
    monkeypatch.setattr(appmod, '_ai_utc_day', lambda: day['v'])
    with flask_app.app_context():
        db.create_all()
        for d in ('2099-06-01', '2099-06-02'):
            row = AIDailyUsage.query.get(d)
            if row:
                db.session.delete(row)
        db.session.commit()
        assert _ai_reserve_call()[0] is True
        assert _ai_reserve_call()[0] is True
        assert _ai_reserve_call()[0] is False      # اليوم امتلأ
        day['v'] = '2099-06-02'
        allowed, state = _ai_reserve_call()
        assert allowed is True
        assert state['used'] == 1                  # صفٌّ جديد، عدّادٌ من الصفر
        assert state['alerted_80'] is False and state['alerted_100'] is False


def test_a_broken_counter_fails_OPEN(ctx, deepseek_key, isolated_day, monkeypatch):
    """⛔ عدّادٌ مكسور لا يجوز أن يوقف عمل المؤسس — يمرّ النداء ويُسجَّل العطل."""
    class _Boom:
        class query:            # noqa: N801
            @staticmethod
            def get(_):
                raise RuntimeError('counter table is gone')
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '1')
    monkeypatch.setattr(appmod, 'AIDailyUsage', _Boom)
    with flask_app.app_context():
        allowed, state = _ai_reserve_call()
    assert allowed is True
    assert state['counter_error'] == 'RuntimeError'
    _fail_transport(monkeypatch, text='مرّ رغم عطل العدّاد')
    assert ai_call('s', 'u') == 'مرّ رغم عطل العدّاد'


def test_the_80_and_100_alerts_fire_once_each_and_are_persisted(
        isolated_day, monkeypatch, caplog):
    """التنبيه هنا **لوجٌ صارخ** لا تليجرام: اللوحة لا تملك مساعد تليجرام أصلًا،
    وإرسالُه عبر مسار إشعارات المنصّة ممنوع — فالعلَمان يُخزَّنان ويظهران على `/api/health`."""
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '10')
    caplog.set_level('ERROR', logger='elprofessor.dashboard')
    with flask_app.app_context():
        for _ in range(7):
            _ai_reserve_call()
        assert not [r for r in caplog.records if 'CAP 80' in r.getMessage()]
        _ai_reserve_call()                       # ٨ من ١٠ = ٨٠٪
        eighty = [r for r in caplog.records if 'CAP 80' in r.getMessage()]
        assert len(eighty) == 1
        _ai_reserve_call()                       # ٩ — لا تنبيهَ ثانيًا
        assert len([r for r in caplog.records if 'CAP 80' in r.getMessage()]) == 1
        allowed, state = _ai_reserve_call()      # ١٠ من ١٠ = ١٠٠٪
        assert allowed is True and state['used'] == 10
        assert len([r for r in caplog.records if 'CAP REACHED' in r.getMessage()]) == 1
        _ai_reserve_call()                       # محجوب — ولا تنبيهَ مكرّر
        assert len([r for r in caplog.records if 'CAP REACHED' in r.getMessage()]) == 1
        row = AIDailyUsage.query.get(isolated_day)
        assert row.alerted_80 is True and row.alerted_100 is True


# ═══════════════════════════════════════ ٤) الحالة مرئيّة للمؤسس (GET)

def test_health_reports_the_model_in_use_the_cap_state_and_the_last_error(
        ctx, deepseek_key, isolated_day, monkeypatch):
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '5')
    # زائرٌ مجهول لا يرى شيئًا من هذا (نفس سياسة F-021)
    anon = ctx['client'].get('/api/health').get_json()
    assert 'ai' not in anon
    _fail_transport(monkeypatch, exc=RuntimeError('boom'))
    with pytest.raises(AIUnavailable):
        ai_call('s', 'u', purpose='health-test')
    body = ctx['client'].get('/api/health', headers=ctx['admin']).get_json()
    ai = body['ai']
    assert ai['provider'] == 'deepseek'
    assert ai['model'] == 'deepseek-v4-flash'
    assert ai['max_tokens'] == 8000
    assert ai['configured'] is True
    assert ai['daily_cap']['cap'] == 5
    assert ai['daily_cap']['used'] == 1
    assert ai['daily_cap']['day'] == isolated_day
    assert ai['last_error']                      # السبب التقني للمؤسس وحده
    assert ai['alerts_channel'] == 'log'


# ═════════════════════════════ ٥) زرّ القائمة (☰) — حارس ترتيب CSS

def test_the_mobile_menu_button_rule_is_not_overridden_after_the_media_query():
    """نفس الخاصّية (`display`) بنفس القوة تُحسم بترتيب الظهور لا بعرض الشاشة: قاعدة
    `.menu-btn{display:none}` غير المشروطة كانت **بعد** `@media(max-width:760px)`،
    فأخفت الزرّ على كل هاتف وقفلت الـ٢٢ موديول كلها. هذا الحارس يفحص الترتيب نفسه."""
    src = io.open(DASH_REPO / 'dashboard-cloud' / 'index.html',
                  encoding='utf-8').read()
    base = src.index('.menu-btn{display:none')
    media = src.index('@media(max-width:760px){')
    assert base < media, 'the unconditional .menu-btn rule must come BEFORE the media query'
    # والميديا-كويري ما زالت تفتحه فعلًا
    block = src[media:src.index('\n', media)]
    assert '.menu-btn{display:grid}' in block
    # ولا قاعدةَ `.menu-btn` غير مشروطة أخرى بعد الميديا (تعيد فتح نفس الحفرة)
    after = src[src.index('\n', media):]
    for m in re.finditer(r'^\.menu-btn\{[^}]*display\s*:', after, re.M):
        raise AssertionError('a later unconditional .menu-btn display rule reopens the bug: '
                             + after[m.start():m.start() + 60])


# ═════════════════════ ٦) دليل الاستخدام — المسار يصل ويرجع محتوى

def test_the_usage_guide_route_is_reachable_and_renders_content(ctx, monkeypatch):
    """اللوحة تقرأ الدليل من `GET {platform}/api/tutorials` بسرّ الجسر. كان الردّ ٤٠٣
    (المسار خارج قائمة سماح المنصّة المقفولة) ⇒ ٥٠٢ هنا ⇒ شريطٌ أحمر و«٠ قسمًا منشورًا».
    قائمة السماح أُصلحت في المنصّة (`server.py`, وحارسها
    `backend/tests/test_closed_platform_sweep.py`)؛ وهذا يثبّت الطرف الآخر من الجسر."""
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'test-bridge-secret')
    rows = [{'id': 't1', 'title': 'كيف تبدأ', 'body': 'خطوة ١', 'is_published': True, 'order': 0}]
    seen = {}

    class _R:
        status_code = 200
        content = b'[]'

        @staticmethod
        def json():
            return rows

    def _fake_get(url, **kw):
        seen['url'] = url
        seen['params'] = kw.get('params')
        seen['headers'] = kw.get('headers')
        return _R()

    monkeypatch.setattr(appmod.requests, 'get', _fake_get)
    r = ctx['client'].get('/api/tutorials', headers=ctx['admin'])
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert r.get_json() == rows
    assert seen['url'].endswith('/api/tutorials')
    assert seen['params'] == {'include_unpublished': 'true'}
    assert seen['headers']['X-ELP-Metrics-Secret'] == 'test-bridge-secret'


def test_the_platform_allowlist_carries_the_usage_guide_read():
    """الطرف الآخر من نفس العطل، مقروءًا من مصدره لا من نسخةٍ ثانية."""
    p = PLAYGROUND / 'elprofessor' / 'backend' / 'server.py'
    if not p.exists():
        pytest.skip('platform repo not present')
    src = io.open(p, encoding='utf-8').read()
    block = src[src.index('CLOSED_PLATFORM_ALLOW_EXACT_GET = ('):]
    block = block[:block.index(')')]
    assert '"/api/tutorials"' in block
