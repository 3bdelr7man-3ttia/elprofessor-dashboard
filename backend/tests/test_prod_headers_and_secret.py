# -*- coding: utf-8 -*-
"""F-021 — الترويسات الإنتاجية ومفتاح التوقيع.

Run:  cd backend && python3 -m pytest -q tests/test_prod_headers_and_secret.py

القياس الحيّ الذي فتح الصفّ: `dashboard.elprofessor.net` يخرج بـCSP وX-Frame-Options
وnosniff و**بلا** `Strict-Transport-Security`، بينما `api.*` عبر نفس الحافّة يخرج بها ⇒
الحافّة لا تحذفها، والتطبيق لا يُصدرها ⇒ `IS_PRODUCTION=False` في الحاوية المنشورة.

فالدرس المثبَّت هنا: **علمٌ لا يُضبَط في الإنتاج يعني أن كل ما خلفه لا يُشحن أبدًا.**
كل ترويسة أمانٍ يجب أن تخرج بلا شرطٍ على ذلك العلم، ويبقى العلم نفسه **معلَنًا** على
`/api/health` كي يُقاس من الخارج بدل أن يُخمَّن.
"""
import pytest

import app as appmod  # noqa: E402
from app import app as flask_app, db  # noqa: E402


@pytest.fixture
def client():
    with flask_app.app_context():
        db.create_all()
    return flask_app.test_client()


def test_this_suite_runs_with_is_production_false():
    """الشرط الذي يجعل بقيّة الملفّ ذا معنى: نحن في نفس إعداد الحاوية المنشورة."""
    assert appmod.IS_PRODUCTION is False


def test_hsts_ships_even_when_is_production_is_false(client):
    r = client.get('/api/health')
    assert r.headers.get('Strict-Transport-Security') == 'max-age=31536000; includeSubDomains'


def test_hsts_is_on_every_response_not_only_the_api(client):
    for path in ('/', '/api/messages', '/api/does-not-exist'):
        r = client.get(path)
        assert r.headers.get('Strict-Transport-Security'), (path, dict(r.headers))


def test_the_other_baseline_headers_are_unconditional_too(client):
    r = client.get('/api/health')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('X-Frame-Options') == 'DENY'
    assert r.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'
    assert r.headers.get('Content-Security-Policy')


def test_csp_carries_form_action_self(client):
    """F-141: بدونها POST علويٌّ يبنيه كودٌ محقون يُخرج رمز الأدمن رغم `connect-src 'self'`."""
    csp = client.get('/api/health').headers.get('Content-Security-Policy')
    assert "form-action 'self'" in csp, csp


# ---------------------------------------------------------------- مفتاح التوقيع

def _op_headers():
    """ترويسة الجسر — نفس ما يمرّره المؤسس في curl على بقيّة مسارات الجسر."""
    return {'X-ELP-Metrics-Secret': appmod.PLATFORM_METRICS_SECRET}


def test_health_stays_a_plain_health_check_for_anonymous_callers(client):
    """⛔ الأعلام ليست عامّة: `secret_key_placeholder=true` يخبر أي زائرٍ مجهول أن مفتاح
    التوقيع هو النصّ المنشور في docker-compose.yml ⇒ دعوةٌ لتزوير توكن أدمن."""
    body = client.get('/api/health').get_json()
    assert body == {'status': 'ok', 'version': '1.0.0'}


def test_health_reports_the_secret_key_state_to_the_bridge_secret(client):
    """الحقيقة التي لا تُقاس إلا من داخل الحاوية تُعلَن هنا — أعلامٌ منطقية فقط."""
    body = client.get('/api/health', headers=_op_headers()).get_json()
    assert body['status'] == 'ok'
    assert set(body) >= {'is_production', 'secret_key_configured', 'secret_key_placeholder'}
    assert body['is_production'] is appmod.IS_PRODUCTION
    # هذا الطقم يعمل بـSECRET_KEY مضبوطة من conftest
    assert body['secret_key_configured'] is True


def test_health_reports_the_secret_key_state_to_an_admin_token(client):
    """المخرج الثاني: توكن أدمن — كي لا يحتاج المؤسس السرّ ليقرأ حالة لوحته."""
    import datetime
    import jwt
    from werkzeug.security import generate_password_hash
    with flask_app.app_context():
        u = appmod.User.query.filter_by(email='health-admin@x.test').first()
        if not u:
            u = appmod.User(email='health-admin@x.test',
                            password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
                            name='health', role='admin', dashboard_role='admin',
                            linked_to_name='', preferred_currency='AUTO', is_active=True)
            db.session.add(u)
            db.session.commit()
        tok = jwt.encode({'user_id': u.id,
                          'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                         flask_app.config['SECRET_KEY'], algorithm='HS256')
    body = client.get('/api/health', headers={'Authorization': 'Bearer ' + tok}).get_json()
    assert body['secret_key_configured'] is True
    assert 'is_production' in body


def test_health_hides_the_flags_from_a_wrong_secret_and_a_non_admin_token(client):
    for headers in ({'X-ELP-Metrics-Secret': 'not-the-secret'},
                    {'Authorization': 'Bearer garbage'},
                    {'Authorization': 'Bearer '}):
        body = client.get('/api/health', headers=headers).get_json()
        assert body == {'status': 'ok', 'version': '1.0.0'}, headers


def test_health_never_leaks_the_secret_itself(client):
    """إعلانُ الحالة لا يجوز أن يصير إعلانًا للقيمة ولا لجزءٍ منها ولا لطولها."""
    raw = client.get('/api/health', headers=_op_headers()).get_data(as_text=True)
    secret = flask_app.config['SECRET_KEY']
    assert secret not in raw
    assert secret[:8] not in raw
    assert str(len(secret)) not in raw.replace('1.0.0', '')


def test_health_reports_an_ephemeral_key_when_secret_key_is_missing(client, monkeypatch):
    """المحاكاة الوحيدة الممكنة بلا إعادة استيراد الوحدة: أعلام الوحدة نفسها هي ما يُقرأ."""
    monkeypatch.setattr(appmod, 'SECRET_KEY_IS_EPHEMERAL', True)
    body = client.get('/api/health', headers=_op_headers()).get_json()
    assert body['secret_key_configured'] is False


def test_health_reports_the_repo_placeholder_as_a_placeholder(client, monkeypatch):
    monkeypatch.setattr(appmod, 'SECRET_KEY_IS_PLACEHOLDER', True)
    body = client.get('/api/health', headers=_op_headers()).get_json()
    assert body['secret_key_placeholder'] is True


@pytest.mark.parametrize('value, ephemeral, placeholder', [
    (None, True, False),                                          # المتغيّر غير موجود أصلًا
    ('', True, False),                                            # غائبة
    ('   ', True, False),                                         # فراغٌ لا يُحسب مفتاحًا
    ('change-this-in-coolify-to-a-long-random-secret', False, True),  # قيمة docker-compose
    ('CHANGE-ME', False, True),
    ('short', False, True),                                       # أقصر من ٣٢ محرفًا
    ('a' * 31, False, True),                                      # الحدّ ناقصًا واحدًا
    ('a' * 32, False, False),                                     # الحدّ بالضبط
    ('f' * 64, False, False),
])
def test_the_classifier_that_health_reports(value, ephemeral, placeholder):
    """⛔ يُستدعى **تصنيف app.py نفسه** لا نسخةٌ منه: إعادةُ كتابة الشرط هنا كانت تعني أن
    خفضَ الحدّ في الشحنة (مثلًا `< 8`) يُبقي الطقم أخضر — فخّ «تطبيقان لمنطقٍ واحد».
    التصنيف يجري مرّةً واحدة عند الاستيراد، فالدالّة هي المنفذ الوحيد لقياسه بقيمٍ أخرى."""
    assert appmod._classify_secret_key(value) == (ephemeral, placeholder)


def test_the_boot_flags_come_from_that_same_classifier():
    """الوصلة التي تجعل التست أعلاه ذا معنى: علما الإقلاع مخرجا الدالّة نفسها، لا شرطٌ
    مكرَّر بجانبها. ⛔ لا يُقاس بمقارنة `os.environ` وقت التست: وحداتٌ مسطّحة في هذا الطقم
    (test_escrow.py:22 وأخواتها) تعيد كتابة `SECRET_KEY` **بعد** استيراد `app`، فالمقارنة
    كانت ستفشل لسببٍ لا علاقة له بالمنطق. القياس السلوكي في التست التالي (عملية فرعية)."""
    src = open(appmod.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
    assert ('SECRET_KEY_IS_EPHEMERAL, SECRET_KEY_IS_PLACEHOLDER = '
            '_classify_secret_key(_secret_key)') in src
    # ولا نسخة ثانية من الشرط في الملفّ كلّه
    assert src.count('_SECRET_KEY_PLACEHOLDERS') == 2      # التعريف + استعمالٌ واحد داخل الدالّة


def test_the_classifier_survives_a_real_process_boot():
    """وضابطٌ أخير من خارج العملية: تُستورَد الوحدة بقيم SECRET_KEY مختلفة في عمليةٍ فرعية
    ويُقرأ العلمان كما يراهما الإقلاع فعلًا — لا monkeypatch ولا استيرادٌ مُعاد."""
    import json
    import os
    import subprocess
    import sys
    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = ('import json, app; '
            'print(json.dumps([app.SECRET_KEY_IS_EPHEMERAL, app.SECRET_KEY_IS_PLACEHOLDER]))')
    for value, expected in (('', [True, False]),
                            ('change-me', [False, True]),
                            ('z' * 64, [False, False])):
        # F-021 (٠٩-٠٨): القفل الصارم عاد — هذا التست يقرأ التصنيف لا يختبر الرفض،
        # فيمرّ بصمّام التشغيل المحلّي؛ الرفض نفسه مُختبَر في test_secret_key_fail_fast.py.
        env = dict(os.environ, SECRET_KEY=value, DATABASE_URL='sqlite:///:memory:',
                   ALLOW_WEAK_SECRET_KEY='1')
        out = subprocess.run([sys.executable, '-c', code], cwd=backend, env=env,
                             capture_output=True, text=True, timeout=180)
        assert out.returncode == 0, out.stderr[-800:]
        assert json.loads(out.stdout.strip().splitlines()[-1]) == expected, (value, out.stdout)


def test_a_missing_secret_key_no_longer_kills_the_boot():
    """قرارٌ مقصود: الحارس يصرخ ولا يُسقط الخدمة الحيّة. لو أُعيد الإسقاطُ لاحقًا
    (بعد تأكيد المؤسس أنّ المتغيّر مضبوط) فليُحدَّث هذا التست عمدًا لا سهوًا."""
    src = open(appmod.__file__.replace('.pyc', '.py'), encoding='utf-8').read()
    head = src[:src.index("app.config['SECRET_KEY']")]
    assert 'raise RuntimeError' not in head, 'the boot guard became fatal again'
    assert 'SECRET_KEY_IS_EPHEMERAL' in head
    assert 'SECRET_KEY_IS_PLACEHOLDER' in head
