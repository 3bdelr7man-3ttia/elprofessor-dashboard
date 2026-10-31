# -*- coding: utf-8 -*-
"""«المفاتيح والكاتب» (SPEC-B B1) · التشفير والمسارات وترتيب `ai_call`.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_keys.py

⛔ صفر شبكة وصفر نداء ذكاء حقيقي: `requests.post/get` ترميان (تجهيز `env` من test_brain2_engine)، والناقلان
`call_anthropic` / `call_openai_compatible` مستبدلان بنواقل مزيّفة تسجّل ما وصلها.
المفاتيح كلها نصوص وهمية (`sk-test-…`).
"""
import json
import os
import re
import types

import pytest

import app as appmod
from app import app as flask_app, db, AuditLog, AIDailyUsage, AI_MAX_TOKENS, AIUnavailable
from brain2 import engine, keys as K

from test_brain2_engine import env   # noqa: F401  (fixture)
from test_brain2_routes import api, NON_ADMIN   # noqa: F401  (fixture)

NS = appmod.__dict__
PLAIN_A = 'sk-test-AAAA1111aaaa2222bbbb'
PLAIN_B = 'sk-test-BBBB3333cccc4444dddd'
PLAIN_C = 'sk-test-CCCC5555eeee6666ffff'
KEYS = '/api/v2/brain/keys'
_REAL_ANTHROPIC, _REAL_COMPAT = appmod.call_anthropic, appmod.call_openai_compatible   # قبل أي استبدال بالتجهيزات


@pytest.fixture(autouse=True)
def clean_keys(env, monkeypatch):   # noqa: F811
    monkeypatch.delenv('DASH_KEYS_SECRET', raising=False)
    Key = K._models(db)
    Key.query.delete()
    db.session.commit()
    yield
    db.session.rollback()
    Key.query.delete()
    db.session.commit()


class HTTPFail(Exception):
    """يشبه خطأ requests: يحمل `.response.status_code` و`.text` فقط."""

    def __init__(self, status, text=''):
        super().__init__('boom')
        self.response = types.SimpleNamespace(status_code=status, text=text)


class Transport(object):
    """ناقل مزيّف. `replies`: قائمة (نص | استثناء | دالة). كل نداء يُسجَّل بمعطياته (المفتاح الصريح هنا لاختبار الاختيار فقط)."""

    def __init__(self, name, replies=None, default='تم'):
        self.name, self.replies, self.default, self.calls = name, list(replies or []), default, []

    def __call__(self, *args):
        self.calls.append(args)
        r = self.replies.pop(0) if self.replies else self.default
        if callable(r):
            r = r(*args)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture()
def wires(monkeypatch):
    claude, compat = Transport('claude'), Transport('compat')
    monkeypatch.setattr(appmod, 'call_anthropic', claude)
    monkeypatch.setattr(appmod, 'call_openai_compatible', compat)
    return types.SimpleNamespace(claude=claude, compat=compat)


def add(api, preset='claude', key=PLAIN_A, role='main', **kw):
    body = {'preset': preset, 'key': key, 'role': role, 'confirmed': True}
    body.update(kw)
    r = api.post(KEYS, body)
    assert r.status_code == 200, r.get_json()
    return r.get_json()['key']


def roles(api):
    return {k['id']: k['role'] for k in api.get(KEYS).get_json()['keys']}


def used_today():
    db.session.expire_all()
    row = AIDailyUsage.query.get(appmod._ai_utc_day())
    return int(row.calls) if row else 0


def no_env(monkeypatch):
    for n in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY'):
        monkeypatch.delenv(n, raising=False)


# ───────────────────────────────────────────────────────────── التشفير

def test_roundtrip_versioned_and_never_plain():
    tok = K.encrypt(PLAIN_A, secret='s' * 40)
    assert tok.startswith('v1:') and PLAIN_A not in tok and 'AAAA' not in tok
    assert K.decrypt(tok, secret='s' * 40) == PLAIN_A
    assert K.encrypt(PLAIN_A, secret='s' * 40) != tok, 'nonce عشوائي لكل تشفير'


def test_wrong_secret_tamper_and_unknown_version_are_missing():
    tok = K.encrypt(PLAIN_A, secret='s' * 40)
    assert K.decrypt(tok, secret='t' * 40) is None
    assert K.decrypt(tok[:-3] + 'AAA', secret='s' * 40) is None
    assert K.decrypt('v9:' + tok[3:], secret='s' * 40) is None
    for junk in (None, '', 'v1:', 'v1:!!!', 'plain', 42):
        assert K.decrypt(junk, secret='s' * 40) is None
    with pytest.raises(ValueError):
        K.encrypt('', secret='s' * 40)
    with pytest.raises(ValueError):
        K.encrypt(PLAIN_A, secret='')


def test_secret_is_dash_keys_secret_first_then_secret_key(monkeypatch):
    with flask_app.app_context():
        monkeypatch.delenv('DASH_KEYS_SECRET', raising=False)
        assert K.get_secret() == flask_app.config['SECRET_KEY']
        tok = K.encrypt(PLAIN_A)
        monkeypatch.setenv('DASH_KEYS_SECRET', 'dedicated-keys-secret-0123456789abcdef')
        assert K.get_secret() == 'dedicated-keys-secret-0123456789abcdef'
        assert K.decrypt(tok) is None, 'تغيّر السرّ ⇒ مفقود'
        assert K.decrypt(K.encrypt(PLAIN_B)) == PLAIN_B


# ───────────────────────────────────────────────────────────── القوالب والتحقق

def test_presets_public_have_labels_only_and_other_is_present():
    pub = K.presets_public()
    assert [p['label'] for p in pub] == ['Claude', 'DeepSeek', 'GLM', 'OpenAI', 'OpenRouter', 'أخرى']
    assert {p['id'] for p in pub if p['needs_url']} == {'openrouter', 'other'}
    assert 'http' not in json.dumps(pub)
    glm = K.preset_of('glm')
    assert glm['base_url'] == 'https://api.z.ai/api/paas/v4' and glm['model'] == 'glm-4.6' and glm['kind'] == 'openai_compat'
    assert K.preset_of('claude')['kind'] == 'anthropic' and K.preset_of('claude')['model'] == 'claude-sonnet-5-5'


@pytest.mark.parametrize('url,expected', [
    ('https://llm.example.com/v1', 'https://llm.example.com/v1'),
    ('https://llm.example.com/v1/', 'https://llm.example.com/v1'),
    ('http://llm.example.com/v1', None),
    ('ftp://llm.example.com', None),
    ('llm.example.com/v1', None),
    ('https://', None),
    ('https://user:pw@llm.example.com/v1', None),
    ('https://llm.example.com/v1?x=1', None),
    ('https://localhost/v1', None),
    ('https://127.0.0.1/v1', None),
    ('https://10.0.0.5/v1', None),
    ('https://169.254.169.254/latest', None),
    ('https://intranet/v1', None),
    ('https://host.internal/v1', None),
    ('https://ex ample.com', None),
    ('x' * 250, None),
    (None, None),
    (12, None),
])
def test_normalize_url(url, expected):
    assert K.normalize_url(url) == expected


def test_model_and_key_validators():
    assert K.valid_model('glm-4.6') and K.valid_model('anthropic/claude-sonnet-5.5:beta')
    assert not K.valid_model('') and not K.valid_model('has space') and not K.valid_model('m' * 81) and not K.valid_model(None)
    assert K.valid_key_text('sk-12345678') and not K.valid_key_text('short') and not K.valid_key_text('k' * 401)
    assert not K.valid_key_text('sk-with space-1234') and not K.valid_key_text('مفتاح-عربي-12345')


# ───────────────────────────────────────────────────────────── الباب

ID = 'a' * 32
ENDPOINTS = [
    ('GET', KEYS, None),
    ('POST', KEYS, {'preset': 'claude', 'key': PLAIN_A, 'role': 'main', 'confirmed': True}),
    ('PUT', KEYS + '/' + ID, {'role': 'off', 'confirmed': True}),
    ('DELETE', KEYS + '/' + ID, {'confirmed': True}),
    ('POST', KEYS + '/' + ID + '/test', None),
]


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_admin_only_flag_off_404_no_store_and_no_call(api, monkeypatch, wires, method, path, body):
    for role in NON_ADMIN:
        assert api.call(method, path, body, role=role).status_code == 403, (role, path)
    assert api.anon(method, path, body).status_code in (401, 403)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = api.call(method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert K._models(db).query.count() == 0
    assert wires.claude.calls == [] and wires.compat.calls == []


def test_no_store_on_every_response(api, wires):
    k = add(api)
    for r in (api.get(KEYS), api.put(KEYS + '/' + k['id'], {'model': 'claude-opus-5-5', 'confirmed': True}),
              api.post(KEYS + '/' + k['id'] + '/test'), api.put(KEYS + '/nope', {'confirmed': True}),
              api.call('DELETE', KEYS + '/' + k['id'], {'confirmed': True})):
        assert r.headers.get('Cache-Control') == 'no-store'


def test_writes_require_explicit_confirmed(api):
    k = add(api)
    for bad in ({}, {'confirmed': 'true'}, {'confirmed': 1}, {'confirmed': False}):
        assert api.post(KEYS, dict(bad, preset='claude', key=PLAIN_B, role='backup')).status_code == 400
        assert api.put(KEYS + '/' + k['id'], dict(bad, role='off')).status_code == 400
        assert api.call('DELETE', KEYS + '/' + k['id'], bad).status_code == 400
    assert len(api.get(KEYS).get_json()['keys']) == 1 and roles(api)[k['id']] == 'main'


# ───────────────────────────────────────────────────────────── إضافة وتحقق

def test_add_returns_tail_only_stores_encrypted_and_audits_preset_and_tail(api):
    k = add(api, preset='deepseek', label='كاتبي', model='deepseek-v4-pro')
    assert k['key_tail'] == PLAIN_A[-4:] == 'bbbb' and k['role'] == 'main' and k['label'] == 'كاتبي'
    assert k['model'] == 'deepseek-v4-pro' and k['preset'] == 'deepseek' and k['kind'] == 'openai_compat'
    assert k['base_url'] == '', 'عنوان القوالب الجاهزة لا يخرج للمتصفح'
    assert k['readable'] is True and 'key_enc' not in k and 'notice' not in k
    row = K._models(db).query.get(k['id'])
    assert row.key_enc.startswith('v1:') and PLAIN_A not in row.key_enc and row.base_url == 'https://api.deepseek.com/v1'
    assert row.created_by == 'brain2-admin@x.test'
    a = AuditLog.query.filter_by(action='brain.key_add', target=k['id']).one()
    assert json.loads(a.meta_json) == {'preset': 'deepseek', 'tail': 'bbbb'} and a.actor_email == 'brain2-admin@x.test'
    assert PLAIN_A not in (a.meta_json or '')


def test_defaults_label_and_model_come_from_preset(api):
    k = add(api, preset='glm', key=PLAIN_B, role='backup')
    assert k['label'] == 'GLM' and k['model'] == 'glm-4.6' and k['role'] == 'backup'
    assert K._models(db).query.get(k['id']).base_url == 'https://api.z.ai/api/paas/v4'


def test_other_and_openrouter_urls(api):
    r = api.post(KEYS, {'preset': 'other', 'key': PLAIN_A, 'model': 'my-model', 'role': 'off', 'confirmed': True})
    assert r.status_code == 400 and 'https' in r.get_json()['error']
    r = api.post(KEYS, {'preset': 'other', 'key': PLAIN_A, 'model': 'my-model', 'role': 'off', 'confirmed': True,
                        'base_url': 'http://llm.example.com/v1'})
    assert r.status_code == 400
    k = add(api, preset='other', model='my-model', role='off', base_url='https://llm.example.com/v1/')
    assert k['base_url'] == 'https://llm.example.com/v1' and k['kind'] == 'openai_compat' and k['label'] == 'أخرى'
    assert api.post(KEYS, {'preset': 'openrouter', 'key': PLAIN_B, 'role': 'off', 'confirmed': True}).status_code == 400, 'OpenRouter بلا موديل افتراضي'
    k2 = add(api, preset='openrouter', key=PLAIN_B, model='anthropic/claude-sonnet-5.5', role='off')
    assert K._models(db).query.get(k2['id']).base_url == 'https://openrouter.ai/api/v1'
    k3 = add(api, preset='openrouter', key=PLAIN_C, model='m1', role='off', base_url='https://gw.example.org/api')
    assert k3['base_url'] == 'https://gw.example.org/api'


def test_ready_presets_ignore_a_url_from_the_body(api):
    k = add(api, preset='openai', base_url='https://evil.example.com/v1')
    assert K._models(db).query.get(k['id']).base_url == 'https://api.openai.com/v1' and k['base_url'] == ''


@pytest.mark.parametrize('patch', [
    {'preset': 'nope'}, {'preset': None}, {'preset': 7},
    {'key': 'short'}, {'key': 'k' * 401}, {'key': 'sk-has space-1234'}, {'key': ''}, {'key': None}, {'key': 123456789},
    {'model': 'has space'}, {'model': 'm' * 81},
    {'label': 'ل' * 61},
    {'role': 'owner'}, {'role': 5},
])
def test_validation_rejects_bad_fields_and_stores_nothing(api, patch):
    body = {'preset': 'claude', 'key': PLAIN_A, 'role': 'main', 'confirmed': True}
    body.update(patch)
    r = api.post(KEYS, body)
    assert r.status_code == 400 and isinstance(r.get_json().get('error'), str)
    assert K._models(db).query.count() == 0
    assert PLAIN_A not in json.dumps(r.get_json())


def test_key_cap(api):
    for i in range(K.KEYS_CAP):
        add(api, key='sk-test-%08d' % i, role='off')
    r = api.post(KEYS, {'preset': 'claude', 'key': PLAIN_B, 'role': 'off', 'confirmed': True})
    assert r.status_code == 409


# ───────────────────────────────────────────────────────────── الأدوار

def test_setting_main_demotes_the_old_main_to_backup(api):
    a = add(api, key=PLAIN_A, role='main')
    b = add(api, preset='glm', key=PLAIN_B, role='main')
    assert roles(api) == {a['id']: 'backup', b['id']: 'main'}
    r = api.put(KEYS + '/' + a['id'], {'role': 'main', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['key']['role'] == 'main'
    assert roles(api) == {a['id']: 'main', b['id']: 'backup'}
    a_upd = AuditLog.query.filter_by(action='brain.key_update', target=a['id']).one()
    assert json.loads(a_upd.meta_json) == {'preset': 'claude', 'tail': PLAIN_A[-4:]}


def test_only_one_backup_the_previous_backup_is_switched_off(api):
    a = add(api, key=PLAIN_A, role='main')
    b = add(api, preset='glm', key=PLAIN_B, role='backup')
    c = add(api, preset='deepseek', key=PLAIN_C, role='backup')
    assert roles(api) == {a['id']: 'main', b['id']: 'off', c['id']: 'backup'}
    api.put(KEYS + '/' + b['id'], {'role': 'main', 'confirmed': True})
    assert roles(api) == {a['id']: 'backup', b['id']: 'main', c['id']: 'off'}


def test_put_validation_model_label_and_empty(api):
    a = add(api)
    p = KEYS + '/' + a['id']
    assert api.put(p, {'confirmed': True}).status_code == 400
    assert api.put(p, {'model': 'bad model', 'confirmed': True}).status_code == 400
    assert api.put(p, {'role': 'x', 'confirmed': True}).status_code == 400
    assert api.put(p, {'label': '', 'confirmed': True}).status_code == 400
    r = api.put(p, {'model': 'claude-opus-5-5', 'label': 'الكاتب الكبير', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['key']['model'] == 'claude-opus-5-5' and r.get_json()['key']['label'] == 'الكاتب الكبير'
    assert api.put(KEYS + '/' + 'b' * 32, {'role': 'off', 'confirmed': True}).status_code == 404
    assert api.put(KEYS + '/zz', {'role': 'off', 'confirmed': True}).status_code == 400


def test_delete_removes_row_and_audits_without_the_key(api):
    a = add(api)
    r = api.call('DELETE', KEYS + '/' + a['id'], {'confirmed': True})
    assert r.status_code == 200 and K._models(db).query.count() == 0
    d = AuditLog.query.filter_by(action='brain.key_delete', target=a['id']).one()
    assert json.loads(d.meta_json) == {'preset': 'claude', 'tail': PLAIN_A[-4:]}
    assert api.call('DELETE', KEYS + '/' + a['id'], {'confirmed': True}).status_code == 404


# ───────────────────────────────────────────────────────────── لا نص صريح ولا key_enc في أي رد

def test_no_route_ever_returns_key_enc_or_plaintext(api, wires):
    seen = []

    def grab(r):
        seen.append(r.get_data(as_text=True))
        return r
    a = add(api, key=PLAIN_A, role='main')
    grab(api.post(KEYS, {'preset': 'glm', 'key': PLAIN_B, 'role': 'backup', 'confirmed': True}))
    grab(api.get(KEYS))
    grab(api.put(KEYS + '/' + a['id'], {'role': 'backup', 'model': 'claude-haiku-5-5', 'confirmed': True}))
    grab(api.post(KEYS + '/' + a['id'] + '/test'))
    wires.claude.replies = [HTTPFail(401, 'invalid x-api-key ' + PLAIN_A)]
    grab(api.post(KEYS + '/' + a['id'] + '/test'))
    grab(api.post(KEYS, {'preset': 'claude', 'key': PLAIN_C, 'role': 'main', 'confirmed': False}))
    grab(api.get('/api/v2/brain/switches'))
    grab(api.get('/api/v2/brain/helpers-status'))
    grab(api.call('DELETE', KEYS + '/' + a['id'], {'confirmed': True}))
    blob = '\n'.join(seen)
    assert len(seen) == 9
    for plain in (PLAIN_A, PLAIN_B, PLAIN_C):
        assert plain not in blob
    assert 'key_enc' not in blob and 'v1:' not in blob
    assert '"key_tail"' in blob


# ───────────────────────────────────────────────────────────── سرّ خاطئ ⇒ مفتاح مفقود

def test_wrong_secret_key_is_missing_with_arabic_notice_and_never_used(api, monkeypatch, wires):
    a = add(api, key=PLAIN_A, role='main')
    monkeypatch.setenv('DASH_KEYS_SECRET', 'rotated-secret-0123456789abcdef0123456789')
    row = api.get(KEYS).get_json()['keys'][0]
    assert row['readable'] is False and row['notice'] == 'تعذّرت قراءة هذا المفتاح؛ أضِفه من جديد' and row['key_tail'] == PLAIN_A[-4:]
    assert K.active_chain(db) == []
    r = api.post(KEYS + '/' + a['id'] + '/test')
    assert r.get_json()['ok'] is False and r.get_json()['error'] == K.UNREADABLE_AR
    assert wires.claude.calls == [] and used_today() == 0, 'بلا نداء وبلا حجز من السقف'
    # ai_call يرجع للبيئة كأن المفتاح غير موجود
    assert appmod.ai_call('s', 'u') == 'تم' and len(wires.claude.calls) == 1
    assert wires.claude.calls[0][0] == 'sk-fake-never-called'
    assert appmod.ai_writer_state()['source'] == 'env'


# ───────────────────────────────────────────────────────────── ترتيب ai_call

def chain_rows(api, main=('claude', PLAIN_A), backup=('glm', PLAIN_B), **kw):
    ids = {}
    if main:
        ids['main'] = add(api, preset=main[0], key=main[1], role='main', **kw)['id']
    if backup:
        ids['backup'] = add(api, preset=backup[0], key=backup[1], role='backup')['id']
    return ids


def test_db_main_is_used_before_env_and_backup_is_untouched(api, wires):
    chain_rows(api)
    assert appmod.ai_call('sys', 'usr') == 'تم'
    assert [c[0] for c in wires.claude.calls] == [PLAIN_A], 'مفتاح القاعدة الأساسي لا مفتاح البيئة'
    assert wires.claude.calls[0][1] == 'claude-sonnet-5-5' and wires.compat.calls == []
    assert used_today() == 1


def test_main_error_falls_back_to_backup_once_and_is_logged(api, wires, caplog):
    chain_rows(api)
    wires.claude.replies = [HTTPFail(500)]
    wires.compat.replies = ['من الاحتياطي']
    with caplog.at_level('ERROR'):
        assert appmod.ai_call('sys', 'usr', purpose='t') == 'من الاحتياطي'
    assert len(wires.claude.calls) == 1 and len(wires.compat.calls) == 1
    base_url, key, model, system, user = wires.compat.calls[0]
    assert (base_url, key, model, system, user) == ('https://api.z.ai/api/paas/v4', PLAIN_B, 'glm-4.6', 'sys', 'usr')
    assert any('AI fallback' in r.getMessage() for r in caplog.records)
    assert PLAIN_A not in caplog.text and PLAIN_B not in caplog.text
    assert used_today() == 2, 'البديل كلّف نداءً فعليًّا فيُحسب'


def test_main_empty_reply_falls_back_to_backup(api, wires):
    chain_rows(api)
    wires.claude.replies = ['   ']
    wires.compat.replies = ['ردّ']
    assert appmod.ai_call('s', 'u') == 'ردّ'


def test_both_fail_raises_and_env_is_not_a_third_attempt(api, wires):
    chain_rows(api)
    wires.claude.default = HTTPFail(500)
    wires.compat.default = HTTPFail(401)
    with pytest.raises(AIUnavailable) as ei:
        appmod.ai_call('s', 'u')
    assert ei.value.kind == 'error' and 'تعذّر الاتصال بخدمة الذكاء' in str(ei.value)
    assert len(wires.claude.calls) == 1 and len(wires.compat.calls) == 1, 'بديل واحد لا حلقة محاولات'
    assert PLAIN_A not in str(ei.value) and PLAIN_B not in str(ei.value)


def test_main_error_without_backup_falls_to_env(api, wires, monkeypatch):
    chain_rows(api, backup=None)
    wires.claude.replies = [HTTPFail(500), 'من البيئة']
    assert appmod.ai_call('s', 'u') == 'من البيئة'
    assert [c[0] for c in wires.claude.calls] == [PLAIN_A, 'sk-fake-never-called']
    assert used_today() == 2


def test_main_error_without_backup_and_without_env_raises_the_first_error(api, wires, monkeypatch):
    chain_rows(api, backup=None)
    no_env(monkeypatch)
    wires.claude.default = HTTPFail(500)
    with pytest.raises(AIUnavailable) as ei:
        appmod.ai_call('s', 'u')
    assert ei.value.kind == 'error' and len(wires.claude.calls) == 1


def test_db_main_works_with_no_env_key_at_all(api, wires, monkeypatch):
    no_env(monkeypatch)
    chain_rows(api, backup=None)
    assert appmod.ai_call('s', 'u') == 'تم' and wires.claude.calls[0][0] == PLAIN_A


def test_no_db_keys_is_exactly_the_old_env_behaviour(api, wires, monkeypatch):
    assert appmod.ai_call('s', 'u') == 'تم'
    assert wires.claude.calls[0][0] == 'sk-fake-never-called' and wires.compat.calls == []
    no_env(monkeypatch)
    with pytest.raises(AIUnavailable) as ei:
        appmod.ai_call('s', 'u')
    assert ei.value.kind == 'no_key'


def test_off_role_keys_are_ignored(api, wires):
    add(api, preset='glm', key=PLAIN_B, role='off')
    assert appmod.ai_call('s', 'u') == 'تم' and wires.compat.calls == [] and wires.claude.calls[0][0] == 'sk-fake-never-called'


def test_cap_blocks_db_main_and_never_falls_back(api, wires, monkeypatch):
    chain_rows(api)
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '1')
    assert appmod.ai_call('s', 'u') == 'تم'
    with pytest.raises(AIUnavailable) as ei:
        appmod.ai_call('s', 'u')
    assert ei.value.kind == 'cap' and len(wires.claude.calls) == 1 and wires.compat.calls == []


def test_cap_hit_by_the_fallback_raises_the_first_error(api, wires, monkeypatch):
    chain_rows(api)
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '1')
    wires.claude.replies = [HTTPFail(500)]
    with pytest.raises(AIUnavailable) as ei:
        appmod.ai_call('s', 'u')
    assert ei.value.kind == 'error' and wires.compat.calls == []


def test_max_tokens_and_cap_are_untouched_and_transports_keep_8000(monkeypatch):
    assert AI_MAX_TOKENS == 8000
    posted = {}

    class R(object):
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {'choices': [{'message': {'content': 'x'}}], 'content': [{'type': 'text', 'text': 'x'}]}

    def post(url, **kw):
        posted[url] = kw['json']
        return R()
    monkeypatch.setattr(appmod.requests, 'post', post)
    _REAL_COMPAT('https://api.z.ai/api/paas/v4', 'k', 'glm-4.6', 's', 'u')
    _REAL_ANTHROPIC('k', 'claude-sonnet-5-5', 's', 'u')
    assert posted['https://api.z.ai/api/paas/v4/chat/completions']['max_tokens'] == 8000
    assert posted['https://api.anthropic.com/v1/messages']['max_tokens'] == 8000


def test_anthropic_kind_uses_claude_transport_even_with_custom_model(api, wires):
    ids = chain_rows(api, backup=None)
    api.put(KEYS + '/' + ids['main'], {'model': 'claude-opus-5-5', 'confirmed': True})
    appmod.ai_call('s', 'u')
    assert wires.claude.calls[0][1] == 'claude-opus-5-5'


# ───────────────────────────────────────────────────────────── مسار الاختبار

def test_test_route_counts_in_cap_stores_result_and_audits(api, wires):
    a = add(api)
    r = api.post(KEYS + '/' + a['id'] + '/test')
    d = r.get_json()
    assert r.status_code == 200 and d['ok'] is True and d['error'] == ''
    assert used_today() == 1
    c = wires.claude.calls[0]
    assert c[0] == PLAIN_A and c[1] == 'claude-sonnet-5-5' and 'تم' in c[3]
    k = d['key']
    assert k['last_test_ok'] is True and k['last_test_at'].endswith('+00:00') and k['last_test_error'] == ''
    t = AuditLog.query.filter_by(action='brain.key_test', target=a['id']).one()
    assert json.loads(t.meta_json) == {'preset': 'claude', 'tail': PLAIN_A[-4:]}


@pytest.mark.parametrize('exc,msg', [
    (HTTPFail(401, 'invalid api key'), 'المفتاح غير صحيح'),
    (HTTPFail(403, ''), 'المفتاح غير صحيح'),
    (HTTPFail(404, 'not found'), 'الموديل غير موجود'),
    (HTTPFail(400, '{"error":"unknown model"}'), 'الموديل غير موجود'),
    (HTTPFail(500, 'internal'), 'لم يصل رد'),
    (HTTPFail(429, 'rate'), 'لم يصل رد'),
    (RuntimeError('timeout api.z.ai'), 'لم يصل رد'),
    ('', 'لم يصل رد'),
])
def test_test_route_errors_are_plain_arabic_without_jargon(api, wires, exc, msg):
    k = add(api, preset='glm', key=PLAIN_B, role='backup')
    wires.compat.replies = [exc]
    d = api.post(KEYS + '/' + k['id'] + '/test').get_json()
    assert d['ok'] is False and d['error'] == msg and d['key']['last_test_ok'] is False and d['key']['last_test_error'] == msg
    assert used_today() == 1, 'الفاشل يُحسب أيضًا: قد يكون كلّف'
    again = api.get(KEYS).get_json()['keys'][0]
    assert again['last_test_error'] == msg
    for jargon in ('HTTP', 'api.z.ai', 'invalid', 'timeout'):
        assert jargon not in json.dumps(d, ensure_ascii=False)


def test_test_route_blocked_by_the_daily_cap_makes_no_call(api, wires, monkeypatch):
    a = add(api)
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '1')
    assert api.post(KEYS + '/' + a['id'] + '/test').status_code == 200
    r = api.post(KEYS + '/' + a['id'] + '/test')
    assert r.status_code == 429 and r.get_json()['reason'] == 'cap' and len(wires.claude.calls) == 1


def test_test_route_unknown_and_bad_ids(api):
    assert api.post(KEYS + '/' + 'c' * 32 + '/test').status_code == 404
    assert api.post(KEYS + '/zz/test').status_code == 400


def test_model_change_clears_the_old_test_result(api, wires):
    a = add(api)
    api.post(KEYS + '/' + a['id'] + '/test')
    k = api.put(KEYS + '/' + a['id'], {'model': 'claude-haiku-5-5', 'confirmed': True}).get_json()['key']
    assert k['last_test_ok'] is None and k['last_test_at'] is None


# ───────────────────────────────────────────────────────────── الكاتب في الشاشة

def test_writer_reflects_the_db_key_and_env_fallback_is_unchanged(api, wires, monkeypatch):
    hs = lambda: api.get('/api/v2/brain/helpers-status').get_json()
    sw = lambda: api.get('/api/v2/brain/switches').get_json()
    assert hs()['writer'] == 'main' and 'writer_label' not in hs() and 'writer_label' not in sw(), 'البيئة وحدها = السلوك القديم'
    a = add(api, preset='glm', key=PLAIN_B, role='main', label='GLM')
    assert hs()['writer'] == 'main' and hs()['writer_label'] == 'GLM' and sw()['writer'] == 'main' and sw()['writer_label'] == 'GLM'
    b = add(api, preset='claude', key=PLAIN_A, role='backup')
    api.put(KEYS + '/' + a['id'], {'role': 'off', 'confirmed': True})
    d = hs()
    assert d['writer'] == 'backup' and d['writer_label'] == 'Claude', 'مفتاح احتياطي وحده هو الشغّال ⇒ «الاحتياطي»'
    api.call('DELETE', KEYS + '/' + b['id'], {'confirmed': True})
    api.call('DELETE', KEYS + '/' + a['id'], {'confirmed': True})
    assert 'writer_label' not in hs() and hs()['writer'] == 'main'


def test_db_key_alone_makes_the_brain_configured_and_writable(api, wires, monkeypatch):
    no_env(monkeypatch)
    assert engine.writer_of(NS) is None
    d = api.get('/api/v2/brain/helpers-status').get_json()
    assert d['configured'] is False and d['writer'] is None
    add(api, preset='deepseek', key=PLAIN_B, role='main')
    d = api.get('/api/v2/brain/helpers-status').get_json()
    assert d['configured'] is True and d['writer'] == 'main' and d['writer_label'] == 'DeepSeek'
    assert engine.writer_of(NS) == 'main'


# ───────────────────────────────────────────────────────────── ملفات

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def test_files_registration_requirements_dockerfile():
    assert re.search(r'^cryptography==\d+\.\d+\.\d+$', _read('backend', 'requirements.txt'), re.M)
    assert 'COPY backend/v2_brain2_keys_routes.py /app/v2_brain2_keys_routes.py' in _read('Dockerfile')
    src = _read('backend', 'app.py')
    i = src.index('v2_brain2_routes as _v2_brain2')
    j = src.index('v2_brain2_keys_routes as _v2_brain2_keys')
    assert 0 < j - i < 400 and "logger.exception('v2 brain2 keys routes not loaded')" in src
    assert not re.search(r'\bimport\s+app\b|from app import', _read('backend', 'brain2', 'keys.py')), 'keys.py مستقل ليستعمله MCP'
