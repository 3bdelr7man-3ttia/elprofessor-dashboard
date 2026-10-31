# -*- coding: utf-8 -*-
"""«العقل» · اسألني على تليجرام (SPEC-B §B2): سؤال المحرّك · مسار القرار · مفتاح المنتج.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_telegram.py

⛔ صفر شبكة وصفر ذكاء حقيقي: `_platform_proxy` بديل محلي يسجّل (في fixture `env`)، و`requests.*` ترمي.
"""
import dataclasses
import json
import re

import pytest

import app as appmod
from app import app as flask_app, db, AuditLog
from brain2 import engine, registry, telegram
from brain2.contract import ApplyResult, Target

from test_brain2_engine import env, fp, use, rows, run, F1, F2, F3   # noqa: F401  (env = fixture)
from test_brain2_routes import api, seed, opinion_producer, ADMIN, NS   # noqa: F401  (api = fixture)

SECRET = 'test-metrics-secret'
DECIDE = '/api/v2/brain/telegram-decide'
ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,50}$')


def _asks(env_):
    return [a for a in env_.asks if a['path'] == '/api/bridge/brain/ask']


def tg(api, body, secret=SECRET):
    headers = {'X-ELP-Metrics-Secret': secret} if secret is not None else {}
    return flask_app.test_client().post(DECIDE, headers=headers, json=body)


@pytest.fixture(autouse=True)
def _secret(env, monkeypatch):      # noqa: F811
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.delenv('DASH_BRAIN_TG_CAP', raising=False)
    AuditLog.query.delete()          # سقف تليجرام اليومي يُعدّ من سجل التدقيق: كل اختبار يبدأ من صفر
    db.session.commit()
    yield
    AuditLog.query.delete()
    db.session.commit()


def draft(pid='file_review', n=1, apply=None, **kw):
    """منتج مسودة مقفول بمعرّف يحمل افتراض تليجرام (`file_review` ضمن TELEGRAM_OK)."""
    def ap(ctx, body, target):
        ap.seen.append({'actor': ctx.actor, 'item_id': getattr(ctx, 'item_id', None), 'text': body['text']})
        return ApplyResult(ok=True, info={'line': 'تم الاعتماد'}) if apply is None else apply(ctx, body, target)
    ap.seen = []
    prod = fp(pid=pid, alone=False, kind='draft', targets=[('m:%d' % i, {'title': 'عنوان %d' % i, 'n': i}) for i in range(1, n + 1)],
              apply=ap, **kw)
    return prod, ap.seen


# ───────────────────────────────────────────────────────────── الإعداد الافتراضي

def test_registry_flags():
    assert registry.TELEGRAM_OK == {'reply_draft', 'file_review', 'course_review'}
    assert registry.TELEGRAM_DEFAULT_ON == {'reply_draft', 'file_review', 'course_review'}
    assert 'opinion' not in registry.TELEGRAM_OK
    ids = [p.id for p in registry.PRODUCERS]
    assert 'file_review' in ids and len(ids) == len(set(ids))


def test_default_on_only_for_the_three_and_never_for_opinions(env):
    for pid in ('reply_draft', 'file_review', 'course_review'):
        assert telegram.enabled(NS, fp(pid=pid, alone=False, kind='draft')) is True
    assert telegram.enabled(NS, fp(pid='market_match', alone=False, kind='draft')) is False
    assert telegram.enabled(NS, fp(pid='opinion', kind='opinion')) is False
    assert telegram.toggle_allowed(fp(pid='opinion', kind='opinion')) is False


# ───────────────────────────────────────────────────────────── خطّاف المحرّك

def test_new_proposed_item_queues_exactly_one_ask(env, monkeypatch):
    prod, _ = draft()
    use(monkeypatch, prod)
    run()
    (item,) = rows()
    (ask,) = _asks(env)
    p = ask['json']
    assert ask['method'] == 'POST' and p['item_id'] == item.id and ID_RE.match(p['item_id'])
    assert len(p['title']) <= 120 and 0 < len(p['text']) <= 900 and p['open_url'].startswith('https://dashboard.elprofessor.net/')
    assert [b['action'] for b in p['buttons']] == ['approve', 'reject', 'open'] and len(p['buttons']) <= 3
    assert all(len(b['label']) <= 24 for b in p['buttons'])
    assert p['buttons'][0]['label'] == 'اعتمد'          # approve_label المنتج الوهمي
    assert p['text'] == 'ملاحظة مكتوبة'
    # نفس البصمة ⇒ لا اقتراح جديد ⇒ لا سؤال ثانٍ
    run()
    assert len(_asks(env)) == 1
    # وكذلك نداء مباشر ثانٍ على نفس الاقتراح يتجاهله
    assert telegram.send_ask(NS, item.id) == 'skip:duplicate'
    assert len(_asks(env)) == 1


def test_ask_audited_once_per_item(env, monkeypatch):
    prod, _ = draft(n=2)
    use(monkeypatch, prod)
    run()
    ids = {r.id for r in rows()}
    audits = AuditLog.query.filter_by(action='brain.tg_ask').all()
    assert {a.target for a in audits} >= ids and all(json.loads(a.meta_json)['sent'] is True for a in audits if a.target in ids)


def test_never_for_opinions(env, monkeypatch):
    env.default = {'opinion': 'رأي'}
    use(monkeypatch, opinion_producer())
    assert engine.submit_opinion(NS, 'review', 'c1', {'tag': 'م'})[2]
    assert rows()[0].status == 'done_alone'
    assert _asks(env) == []
    # ولو نودي مباشرة على صف الرأي
    assert telegram.send_ask(NS, rows()[0].id) == 'skip:not_proposed'


def test_notes_running_alone_get_no_ask(env, monkeypatch):
    use(monkeypatch, fp(pid='file_review', alone=True, kind='note', targets=[('n:1', F1)]))
    run()
    assert rows()[0].status == 'done_alone' and _asks(env) == []


def test_off_switch_default_off_and_failed_rows_send_nothing(env, monkeypatch):
    prod, _ = draft(pid='market_match')
    use(monkeypatch, prod)
    run()
    assert len(rows()) == 1 and _asks(env) == [], 'منتج افتراضه مطفأ'
    use(monkeypatch, fp(pid='file_review', alone=False, kind='draft', targets=[('x:1', F2)], validate=lambda d, t: None))
    run()
    assert _asks(env) == [], 'صف فاشل لا يُسأل عنه'


def test_telegram_switch_off_for_default_on_producer(env, monkeypatch):
    prod, _ = draft()
    use(monkeypatch, prod)
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='file_review', mode='ask', telegram=False))
    db.session.commit()
    run()
    assert len(rows()) == 1 and _asks(env) == []


def test_enabled_for_non_default_producer_sends_open_link_only(env, monkeypatch):
    prod, _ = draft(pid='market_match')
    use(monkeypatch, prod)
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='market_match', mode='ask', telegram=True))
    db.session.commit()
    run()
    (ask,) = _asks(env)
    assert [b['action'] for b in ask['json']['buttons']] == ['open']


def test_daily_cap(env, monkeypatch):
    monkeypatch.setenv('DASH_BRAIN_TG_CAP', '2')
    prod, _ = draft(n=4)
    use(monkeypatch, prod)
    run()
    assert len(rows()) == 4 and len(_asks(env)) == 2
    # سقف اليوم ثابت عبر الجولات
    prod2, _ = draft(n=5)
    use(monkeypatch, prod2)
    run()
    assert len(_asks(env)) == 2


def test_cap_default_is_twenty(monkeypatch):
    monkeypatch.delenv('DASH_BRAIN_TG_CAP', raising=False)
    assert telegram.tg_cap() == 20
    monkeypatch.setenv('DASH_BRAIN_TG_CAP', 'x')
    assert telegram.tg_cap() == 20
    monkeypatch.setenv('DASH_BRAIN_TG_CAP', '0')
    assert telegram.tg_cap() == 0


def test_platform_says_not_sent_or_raises_no_retry(env, monkeypatch):
    calls = []

    def proxy(method, path, params=None, json_body=None, timeout=12):
        calls.append(path)
        if len(calls) == 1:
            raise OSError('down')
        return appmod.jsonify({'sent': False})
    monkeypatch.setattr(appmod, '_platform_proxy', proxy)
    prod, _ = draft(n=2)
    use(monkeypatch, prod)
    run()
    assert len(calls) == 2 and len(rows()) == 2, 'فشل الإرسال لا يكسر الجولة ولا يُعاد'
    run()
    assert len(calls) == 2
    metas = [json.loads(a.meta_json) for a in AuditLog.query.filter_by(action='brain.tg_ask').all()]
    assert metas.count({'sent': False, 'why': ''}) >= 2


def test_ask_text_never_carries_contacts_or_meta(env, monkeypatch):
    prod = fp(pid='reply_draft', alone=False, kind='draft', section='people',
              targets=[('pmsg:9', {'subject': 'س', 'body': 'كلموني على 0100 123 4567 أو a@b.test', 'has_account': True},
                        {'id': '9', 'email': 'secret@mail.test'})],
              validate=lambda d, t: {'text': d['text']}, apply=lambda c, b, t: ApplyResult(ok=True))
    use(monkeypatch, prod)
    run()
    (ask,) = _asks(env)
    blob = json.dumps(ask['json'], ensure_ascii=False)
    assert 'secret@mail.test' not in blob and 'a@b.test' not in blob and '4567' not in blob
    assert 'الرسالة:' in ask['json']['text'] and 'المقترح:' in ask['json']['text']


def test_reply_draft_without_a_real_send_path_gets_link_only(env, monkeypatch):
    prod = fp(pid='reply_draft', alone=False, kind='draft', section='people',
              targets=[('smsg:1', {'subject': 'س', 'body': 'ب'}, {'id': 1, 'email': ''}),
                       ('smsg:2', {'subject': 'س', 'body': 'ج'}, {'id': 2, 'email': 'v@x.test'}),
                       ('lead:3', {'want': 'د'}, {'id': '3', 'email': ''}),
                       ('pmsg:4', {'subject': 'س', 'body': 'هـ', 'has_account': True}, {'id': '4', 'email': ''})],
              validate=lambda d, t: {'text': d['text']}, apply=lambda c, b, t: ApplyResult(ok=True))
    use(monkeypatch, prod)
    run()
    acts = {a['json']['title'].split(' — ', 1)[1]: [b['action'] for b in a['json']['buttons']] for a in _asks(env)}
    assert acts == {'هدف smsg:1': ['open'], 'هدف smsg:2': ['approve', 'reject', 'open'],
                    'هدف lead:3': ['open'], 'هدف pmsg:4': ['approve', 'reject', 'open']}


def test_file_review_return_note_is_in_the_ask_and_label_follows_the_recommendation():
    class Row(object):
        id = 'a' * 32
        target_label = 'مراجعة رأي: عنوان'
        target_ref = 'file:f1'
    p = registry.by_id('file_review')
    body = {'text': 'ينقص سؤال', 'recommend': 'return', 'return_note': 'أجب السؤال الثاني', 'approve_label': 'أرجِعه بالملاحظة'}
    out = telegram.build_ask(p, Row, body, {}, {})
    assert out['buttons'][0] == {'label': 'أرجِعه بالملاحظة', 'action': 'approve'}
    assert 'الملاحظة التي تصل إلى الخبير: أجب السؤال الثاني' in out['text']


def test_course_review_fix_first_has_no_approve_button():
    p = registry.by_id('course_review')
    assert telegram.can_decide(p, {'recommend': 'publish'}, {}, {}, 'course:1') is True
    assert telegram.can_decide(p, {'recommend': 'fix_first'}, {}, {}, 'course:1') is False


# ───────────────────────────────────────────────────────────── مسار القرار: الباب

def test_decide_auth_is_secret_only(api, monkeypatch):
    prod, seen = draft()
    seed(monkeypatch, api, prod)
    (item,) = rows()
    body = {'item_id': item.id, 'action': 'approve', 'tg_user_id': 42}
    assert tg(api, body, secret=None).status_code == 401
    assert tg(api, body, secret='wrong').status_code == 401
    r = flask_app.test_client().post(DECIDE, headers=dict(api.heads['admin']), json=body)
    assert r.status_code == 401, 'توكن الأدمن لا يكفي'
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    assert tg(api, body, secret='').status_code == 401, 'سرّ غير مضبوط ⇒ رفض لا قبول'
    assert seen == [] and rows()[0].status == 'proposed'
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert tg(api, body).status_code == 404 and seen == []


@pytest.mark.parametrize('body', [
    {}, {'item_id': 'zz', 'action': 'approve', 'tg_user_id': 1},
    {'item_id': 'a' * 32, 'action': 'delete', 'tg_user_id': 1},
    {'item_id': 'a' * 32, 'action': 'approve'}, {'item_id': 'a' * 32, 'action': 'approve', 'tg_user_id': 'x1'},
    {'item_id': 'a' * 32, 'action': 'approve', 'tg_user_id': True}, {'item_id': 5, 'action': 'approve', 'tg_user_id': 1}])
def test_decide_bad_body(api, body):
    r = tg(api, body)
    assert r.status_code == 400 and r.get_json()['ok'] is False and r.get_json()['reason'] == 'bad_request'


def test_decide_unknown_item(api):
    r = tg(api, {'item_id': 'a' * 32, 'action': 'approve', 'tg_user_id': 1})
    assert r.status_code == 200 and r.get_json() == {'ok': False, 'reason': 'not_found'}


# ───────────────────────────────────────────────────────────── مسار القرار: الفعل

def test_decide_approve_runs_the_same_apply_with_the_telegram_actor(api, monkeypatch):
    prod, seen = draft()
    seed(monkeypatch, api, prod)
    (item,) = rows()
    r = tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 42, 'by': 'evil@x.test'})
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    assert r.get_json() == {'ok': True, 'line': 'تم الاعتماد'}
    assert seen == [{'actor': 'telegram:42', 'item_id': item.id, 'text': 'ملاحظة مكتوبة'}]
    row = rows()[0]
    assert row.status == 'approved' and row.decided_by == 'telegram:42' and row.decided_at is not None
    a = AuditLog.query.filter_by(action='brain.approve', target=item.id).one()
    assert a.actor_email == 'telegram:42'
    # مرة ثانية ⇒ حُسم
    r2 = tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 42})
    assert r2.status_code == 200 and r2.get_json() == {'ok': False, 'reason': 'decided'} and len(seen) == 1


def test_decide_reject(api, monkeypatch):
    prod, seen = draft()
    seed(monkeypatch, api, prod)
    (item,) = rows()
    r = tg(api, {'item_id': item.id, 'action': 'reject', 'tg_user_id': '77'})
    assert r.status_code == 200 and r.get_json()['ok'] is True and seen == []
    row = rows()[0]
    assert row.status == 'rejected' and row.decided_by == 'telegram:77'
    a = AuditLog.query.filter_by(action='brain.reject', target=item.id).one()
    assert a.actor_email == 'telegram:77' and json.loads(a.meta_json)['via'] == 'telegram'
    assert tg(api, {'item_id': item.id, 'action': 'reject', 'tg_user_id': 77}).get_json() == {'ok': False, 'reason': 'decided'}
    assert tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 77}).get_json() == {'ok': False, 'reason': 'decided'}


def test_decide_open_is_a_noop(api, monkeypatch):
    prod, seen = draft()
    seed(monkeypatch, api, prod)
    (item,) = rows()
    r = tg(api, {'item_id': item.id, 'action': 'open', 'tg_user_id': 1})
    assert r.status_code == 200 and r.get_json()['ok'] is True
    assert rows()[0].status == 'proposed' and seen == []


def test_decide_refuses_producers_outside_the_allow_set(api, monkeypatch):
    prod, seen = draft(pid='market_match')
    seed(monkeypatch, api, prod)
    (item,) = rows()
    for action in ('approve', 'reject'):
        r = tg(api, {'item_id': item.id, 'action': action, 'tg_user_id': 1})
        assert r.status_code == 200 and r.get_json() == {'ok': False, 'reason': 'not_allowed'}
    assert rows()[0].status == 'proposed' and seen == []


def test_decide_failed_apply_keeps_item_proposed(api, monkeypatch):
    prod, seen = draft(apply=lambda c, b, t: ApplyResult(ok=False, error='المنصة رفضت'))
    seed(monkeypatch, api, prod)
    (item,) = rows()
    r = tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 1})
    assert r.status_code == 200 and r.get_json() == {'ok': False, 'reason': 'failed', 'line': 'المنصة رفضت'}
    assert rows()[0].status == 'proposed'


def test_decide_no_reply_marks_unknown(api, monkeypatch):
    prod, seen = draft(apply=lambda c, b, t: ApplyResult(ok=False, no_reply=True))
    seed(monkeypatch, api, prod)
    (item,) = rows()
    r = tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 1})
    assert r.get_json()['ok'] is False and r.get_json()['reason'] == 'unknown'
    assert rows()[0].status == 'unknown'


def test_decide_default_line_never_claims_more_than_the_result(api, monkeypatch):
    prod, _ = draft(apply=lambda c, b, t: ApplyResult(ok=True))
    seed(monkeypatch, api, prod)
    (item,) = rows()
    assert tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 1}).get_json() == {'ok': True, 'line': 'تم التنفيذ'}


def test_platform_write_by_is_the_telegram_actor(api, monkeypatch):
    """الفاعل يصل إلى المنصة في `by` وإلى سجل التدقيق (g.user) حتى بلا توكن لوحة."""
    from brain2 import producers_files
    sent = []

    def proxy(method, path, params=None, json_body=None, timeout=12):
        sent.append((method, path, json_body))
        return appmod.jsonify({'ok': True, 'status': 'delivered'})
    monkeypatch.setattr(appmod, '_platform_proxy', proxy)
    prod = producers_files.PRODUCERS[0]
    facts = {'title': 'ت', 'questions': ['س'], 'facts': ['و'], 'pending_opinion': {'answers': [{'question': 'س', 'text': 'ج'}]}}
    api.script.default = {'text': 'الرأي مكتمل', 'recommend': 'approve'}
    use(monkeypatch, dataclasses.replace(prod, gather=lambda ctx: [Target(ref='file:f1', label='ملف', facts=facts, meta={'file_id': 'f1'})]))
    st, _ = engine.start_run(NS, 'admin', ADMIN)
    assert st == 202
    (item,) = rows()
    sent.clear()
    r = tg(api, {'item_id': item.id, 'action': 'approve', 'tg_user_id': 42})
    assert r.get_json() == {'ok': True, 'line': 'اعتُمد الرأي وأُرسل إلى العميل'}
    assert sent == [('POST', '/api/bridge/expert-files/f1/review', {'action': 'approve', 'note': '', 'by': 'telegram:42'})]
    assert AuditLog.query.filter_by(action='expert_file.review_approve', target='f1').one().actor_email == 'telegram:42'


# ───────────────────────────────────────────────────────────── مفتاح «اسألني على تليجرام»

def test_switches_show_telegram_state(api, monkeypatch):
    use(monkeypatch, fp(pid='file_review', alone=False, kind='draft'), fp(pid='market_match', alone=False, kind='draft'),
        fp(pid='opinion', kind='opinion', section='home'))
    by = {s['id']: s for s in api.get('/api/v2/brain/switches').get_json()['switches']}
    assert by['file_review']['telegram'] is True and by['file_review']['telegram_ok'] is True
    assert by['market_match']['telegram'] is False and by['market_match']['telegram_ok'] is False
    assert by['opinion']['telegram'] is False and by['opinion']['telegram_can_toggle'] is False
    assert by['file_review']['telegram_can_toggle'] is True


def test_switch_put_telegram_toggle(api, monkeypatch):
    use(monkeypatch, fp(pid='file_review', alone=False, kind='draft'), fp(pid='opinion', kind='opinion', section='home'))
    path = '/api/v2/brain/switches/'
    assert api.put(path + 'file_review', {'telegram': False}).status_code == 400, 'بلا تأكيد'
    assert api.put(path + 'file_review', {'telegram': 'no', 'confirmed': True}).status_code == 400
    assert api.put(path + 'file_review', {'confirmed': True}).status_code == 400, 'لا mode ولا telegram'
    assert api.put(path + 'opinion', {'telegram': True, 'confirmed': True}).status_code == 400
    assert api.put(path + 'nope', {'telegram': True, 'confirmed': True}).status_code == 404
    assert AuditLog.query.filter_by(action='v2_brain.switch').count() == 0
    r = api.put(path + 'file_review', {'telegram': False, 'confirmed': True, 'by': 'evil@x.test'})
    assert r.status_code == 200 and r.get_json()['telegram'] is False and r.get_json()['mode'] == 'ask'
    assert r.get_json()['updated_by'] == ADMIN
    Switch = engine._models(db)[1]
    row = Switch.query.get('file_review')
    assert row.telegram is False and row.mode == 'ask'
    a = AuditLog.query.filter_by(action='v2_brain.switch').one()
    assert json.loads(a.meta_json) == {'telegram': False} and a.actor_email == ADMIN
    by = {s['id']: s for s in api.get('/api/v2/brain/switches').get_json()['switches']}
    assert by['file_review']['telegram'] is False
    # تغيير الوضع لا يمسّ تليجرام، وتفعيله من جديد يعمل
    r = api.put(path + 'file_review', {'mode': 'off', 'confirmed': True})
    assert r.status_code == 200 and Switch.query.get('file_review').telegram is False
    r = api.put(path + 'file_review', {'telegram': True, 'mode': 'ask', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['telegram'] is True and r.get_json()['mode'] == 'ask'
    assert json.loads(AuditLog.query.filter_by(action='v2_brain.switch').order_by(AuditLog.id.desc()).first().meta_json) == \
        {'mode': 'ask', 'telegram': True}


def test_toggle_applies_to_the_next_ask(api, monkeypatch):
    prod, _ = draft()
    use(monkeypatch, prod)
    assert api.put('/api/v2/brain/switches/file_review', {'telegram': False, 'confirmed': True}).status_code == 200
    run()
    assert _asks(api.script) == []
    assert api.put('/api/v2/brain/switches/file_review', {'telegram': True, 'confirmed': True}).status_code == 200
    prod2, _ = draft(n=2)
    use(monkeypatch, prod2)
    run()
    assert len(_asks(api.script)) == 1, 'اقتراح جديد واحد فقط (الأول موجود)'


# ───────────────────────────────────────────────────────────── ترحيل العمود لقاعدة قديمة

def test_ensure_schema_adds_the_column_to_an_old_table(monkeypatch):
    import sqlalchemy as sa
    eng = sa.create_engine('sqlite://')
    with eng.begin() as c:
        c.execute(sa.text('CREATE TABLE v2_brain_switches (producer VARCHAR(40) PRIMARY KEY, mode VARCHAR(8) NOT NULL, '
                          'updated_at DATETIME, updated_by VARCHAR(255))'))

    class FakeDB(object):
        engine = eng
    monkeypatch.setitem(engine._SCHEMA, 'ok', False)
    engine.ensure_schema(FakeDB)
    assert engine._SCHEMA['ok'] is True
    assert 'telegram' in {c['name'] for c in sa.inspect(eng).get_columns('v2_brain_switches')}
    engine.ensure_schema(FakeDB)           # مرة ثانية بلا خطأ
    monkeypatch.setitem(engine._SCHEMA, 'ok', True)
