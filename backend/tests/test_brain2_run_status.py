# -*- coding: utf-8 -*-
"""R16 «المخ يعالج ويشتغل»: لا تشغيل يمرّ بلا أثر يراه المؤسس.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_run_status.py

يغطّي: سجل «آخر تشغيل» لكل منتج (كتب · لا جديد · لا شيء · متوقّف · تعذّر مصدره · لم يصل إليه الدور) · المفتاح الناقص
بالمكان بالضبط وبلا نداء ولا عدّ · توقف أخطاء الموديل المتتالية · نتائج تليجرام · المشغّل التلقائي بمواعيد القاهرة ·
كرون n8n: العقل أولًا وبلا مساعدين لو `agent=brain` · ختم الجولة حتى لو تعطّلت الجلسة · نصوص بلا عبارات ممنوعة.

⛔ صفر شبكة وصفر نداء ذكاء حقيقي (نفس تجهيز test_brain2_engine).
"""
import datetime
import json
import re

import pytest

import app as appmod
from app import app as flask_app, db
from brain2 import autorun, engine, run_report
from brain2.contract import SourceDown, Target
import v2_brain2_routes

from test_brain2_engine import env, fp, use, rows, F1, F2, F3   # noqa: F401  (env = fixture)
from test_brain2_routes import api, ADMIN, SECRET   # noqa: F401  (api = fixture)

NS = appmod.__dict__


def latest(api_):
    r = api_.get('/api/v2/brain/runs/latest')
    assert r.status_code == 200
    return r.get_json()['run']


def raw_report(run_id):
    db.session.expire_all()
    row = engine._models(db)[2].query.get(run_id)
    return json.loads(row.skipped_json or '{}').get('_report')


def draft(pid, targets):
    return fp(pid=pid, alone=False, kind='draft', targets=targets)


def down_producer(pid='down'):
    def g(ctx):
        raise SourceDown('/api/bridge/secret-path: http 500')
    return fp(pid=pid, gather=g)


# ───────────────────────────────────────────────────────────── سجل كل منتج

def test_every_producer_ends_with_a_visible_state(api, monkeypatch):
    use(monkeypatch,
        draft('writes', [('w:1', F1), ('w:2', F2)]),
        fp(pid='empty', targets=[]),
        fp(pid='stopped', targets=[('s:1', F3)]),
        down_producer())
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='stopped', mode='off'))
    db.session.commit()
    r = api.post('/api/v2/brain/run', {'confirmed': True})
    assert r.status_code == 202
    rep = raw_report(r.get_json()['run_id'])
    by = rep['producers']
    assert by['writes']['state'] == 'done' and by['writes']['proposed'] == 2 and by['writes']['targets'] == 2
    assert by['empty']['state'] == 'none' and by['stopped']['state'] == 'off' and by['down']['state'] == 'source_down'
    assert rep['writer'] == 'main' and 'stop' not in rep
    run = latest(api)
    s = run['report']
    assert '_report' not in run['skipped'], 'الرموز القديمة فقط في skipped'
    assert s['state'] == 'partial' and s['headline'] == 'عمل العقل وكتب كتابتين، وتعذّر جزء.'
    assert '«منتج writes»: كتب اقتراحين تنتظر قرارك.' in s['done']
    assert '«منتج empty»: لا يوجد ما يُكتب عنه الآن.' in s['done']
    assert '«منتج stopped»: متوقّف من القواعد.' in s['done']
    assert '«منتج down»: تعذّرت قراءة بياناته من المنصة الآن.' in s['failed']
    assert 'secret-path' not in json.dumps(run, ensure_ascii=False), 'لا تفاصيل تقنية في الشاشة'
    # تشغيل ثانٍ بلا جديد ⇒ «لا جديد» لا صمت
    r2 = api.post('/api/v2/brain/run', {'confirmed': True, 'only': 'writes'})
    assert r2.status_code == 202
    s2 = latest(api)['report']
    assert s2['state'] == 'nothing' and s2['done'] == ['«منتج writes»: لا جديد؛ ما كُتب من قبل ما زال صالحًا.']


def test_gather_crash_is_recorded_and_the_run_is_sealed(api, monkeypatch):
    def boom(ctx):
        raise RuntimeError('db exploded')
    use(monkeypatch, fp(pid='crash', gather=boom), fp(pid='after', targets=[('a:1', F1)]))
    r = api.post('/api/v2/brain/run', {'confirmed': True})
    run = latest(api)
    assert run['finished_at'] and run['active'] is False and run['items'] == 1
    assert '«منتج crash»: حدث عطل أثناء جمع بياناته.' in run['report']['failed']
    assert '«منتج after»: كتب ملاحظة واحدة.' in run['report']['done']
    assert engine.active_run(db) is None


# ───────────────────────────────────────────────────────────── المفتاح الناقص

def test_missing_key_says_exactly_where_and_makes_no_call(api, monkeypatch):
    monkeypatch.setattr(appmod, 'ai_writer_state', lambda: {'writer': None, 'label': None, 'source': None})
    use(monkeypatch, fp(pid='first', targets=[('a:1', F1)]), fp(pid='second', targets=[('b:1', F2)]))
    r = api.post('/api/v2/brain/run', {'confirmed': True})
    assert r.status_code == 202
    assert api.script.calls == [] and rows() == []
    assert engine.brain_today(db) == 0, 'لا عدّ نداء بلا مفتاح'
    rep = raw_report(r.get_json()['run_id'])
    assert rep['stop'] == 'no_key' and rep['writer'] is None
    assert rep['producers']['first']['state'] == 'done' and rep['producers']['second']['state'] == 'not_reached'
    s = latest(api)['report']
    assert s['state'] == 'failed' and s['failed'][0] == run_report.KEY_MISSING and s['fix'] == run_report.KEY_WHERE
    assert '«منتج second»: لم يصل إليه الدور لأن التشغيل توقّف.' in s['failed']
    assert 'من يكتب للعقل' in s['fix'] and 'أضف مفتاحًا' in s['fix'] and 'الأساسي' in s['fix']
    sw = api.get('/api/v2/brain/switches').get_json()
    assert sw['writer'] is None and sw['writer_fix'] == {'text': run_report.KEY_MISSING, 'where': run_report.KEY_WHERE}
    assert 'sk-' not in json.dumps(sw) and 'API_KEY' not in json.dumps(sw, ensure_ascii=False)


def test_switches_carry_autorun_and_no_fix_when_a_writer_exists(api):
    sw = api.get('/api/v2/brain/switches').get_json()
    assert sw['writer'] == 'main' and 'writer_fix' not in sw and sw['writes_on'] is True
    assert set(sw['autorun']) == {'on', 'next_at', 'hours'} and sw['autorun']['hours'] == [9, 20]


# ───────────────────────────────────────────────────────────── أخطاء الموديل المتتالية

def test_three_model_errors_in_a_row_stop_the_run_with_the_reason(api, monkeypatch):
    def down(system, user, purpose='ai'):
        api.script.calls.append({'user': user})
        raise appmod.AIUnavailable('تعذّر الاتصال بخدمة الذكاء', kind='error')
    monkeypatch.setattr(appmod, 'ai_call', down)
    use(monkeypatch, fp(targets=[('a:%d' % i, {'title': 'م', 'score': i}) for i in range(6)]))
    r = api.post('/api/v2/brain/run', {'confirmed': True})
    assert len(api.script.calls) == engine.AI_ERR_STOP
    rep = raw_report(r.get_json()['run_id'])
    assert rep['stop'] == 'ai_error' and rep['ai_reason'] == 'تعذّر الاتصال بخدمة الذكاء'
    s = latest(api)['report']
    assert s['failed'][0].startswith('لم يرد الموديل أكثر من مرة متتالية (تعذّر الاتصال بخدمة الذكاء)')
    assert 'جرّبه' in s['fix']


# ───────────────────────────────────────────────────────────── تليجرام

def test_telegram_outcomes_show_in_the_run(api, monkeypatch):
    use(monkeypatch, draft('reply_draft', [('pmsg:1', F1), ('pmsg:2', F2)]))
    api.post('/api/v2/brain/run', {'confirmed': True})
    s = latest(api)['report']
    assert 'تليجرام: أُرسل سؤالين للقرار.' in s['done']


def test_telegram_failure_is_visible_with_what_to_check(api, monkeypatch):
    monkeypatch.setattr(appmod, '_platform_proxy', lambda *a, **k: appmod.jsonify({'sent': False}))
    use(monkeypatch, draft('reply_draft', [('pmsg:1', F1)]))
    api.post('/api/v2/brain/run', {'confirmed': True})
    s = latest(api)['report']
    assert 'تليجرام: لم يصل سؤالًا واحدًا؛ المنصة لم تؤكّد الإرسال.' in s['failed']
    assert 'بوت تليجرام' in s['fix'] and 'ابدأ القرارات' in s['fix']
    assert rows()[0].status == 'proposed', 'الاقتراح نفسه في الوارد («ابدأ القرارات») حتى لو لم يصل تليجرام'


def test_send_asks_uses_the_public_helper_and_counts(monkeypatch, env):
    import brain2.telegram as tgmod
    seen = []
    replies = iter(['sent', 'skip:cap', 'failed'])
    monkeypatch.setattr(tgmod, 'send_ask', lambda ns, i: seen.append(i) or next(replies))
    out = engine._send_asks(NS, ['a', 'b', 'c'])
    assert seen == ['a', 'b', 'c'] and out == {'sent': 1, 'failed': 1, 'skipped': {'cap': 1}}
    assert engine._send_asks(NS, []) is None


# ───────────────────────────────────────────────────────────── ختم الجولة والجولة العالقة

def test_finish_run_seals_even_after_a_broken_session(env, monkeypatch):
    Run = engine._models(db)[2]
    db.session.add(Run(id='e' * 32, trigger='admin', started_at=engine.utcnow()))
    db.session.commit()
    real = db.session.commit
    calls = {'n': 0}

    def flaky():
        calls['n'] += 1
        if calls['n'] == 1:
            raise RuntimeError('session broken')
        return real()
    monkeypatch.setattr(db.session, 'commit', flaky)
    engine._finish_run(NS, 'e' * 32, 0, 0, {'_stop': 'error'})
    monkeypatch.setattr(db.session, 'commit', real)
    db.session.expire_all()
    assert Run.query.get('e' * 32).finished_at is not None and engine.active_run(db) is None


def test_interrupted_run_reads_stale_not_running(api):
    Run = engine._models(db)[2]
    db.session.add(Run(id='d' * 32, trigger='cron', by='auto',
                       started_at=engine.utcnow() - datetime.timedelta(minutes=20)))
    db.session.commit()
    run = latest(api)
    assert run['active'] is False and run['by'] == 'تلقائي'
    assert run['report']['state'] == 'stale' and 'شغّل الآن' in run['report']['fix']


# ───────────────────────────────────────────────────────────── المشغّل التلقائي

def test_autorun_slots_in_cairo_time(monkeypatch):
    monkeypatch.delenv('DASH_BRAIN_AUTORUN_HOURS', raising=False)
    # ١٠ مارس (القاهرة +٢): ١٨:٣٠ UTC = ٢٠:٣٠ القاهرة ⇒ آخر موعد ٢٠:٠٠ (١٨:٠٠ UTC) والقادم ٠٩:٠٠ غدًا (٠٧:٠٠ UTC)
    now = datetime.datetime(2098, 3, 10, 18, 30)
    assert autorun.last_slot(now) == datetime.datetime(2098, 3, 10, 18, 0)
    assert autorun.next_slot(now) == datetime.datetime(2098, 3, 11, 7, 0)
    early = datetime.datetime(2098, 3, 10, 5, 0)          # ٠٧:٠٠ القاهرة ⇒ آخر موعد أمس ٢٠:٠٠
    assert autorun.last_slot(early) == datetime.datetime(2098, 3, 9, 18, 0)
    monkeypatch.setenv('DASH_BRAIN_AUTORUN_HOURS', '25, x, 14')
    assert autorun.hours() == [14]
    monkeypatch.setenv('DASH_BRAIN_AUTORUN_HOURS', 'bad')
    assert autorun.hours() == [9, 20]


def test_autorun_tick_starts_one_run_per_slot(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    now = datetime.datetime(2098, 3, 10, 18, 30)
    monkeypatch.setattr(engine, 'utcnow', lambda: now)
    rid = autorun.tick(NS, now)
    assert rid and len(rows()) == 1
    Run = engine._models(db)[2]
    r = Run.query.get(rid)
    assert r.trigger == 'cron' and r.by == 'auto' and r.finished_at is not None
    assert autorun.tick(NS, now) is None, 'موعد واحد ⇒ جولة واحدة'
    assert autorun.tick(NS, now + datetime.timedelta(hours=13)) is not None, 'الموعد التالي ⇒ جولة جديدة'


def test_autorun_respects_switches(env, monkeypatch):
    now = datetime.datetime(2098, 3, 10, 18, 30)
    monkeypatch.setenv('DASH_BRAIN_AUTORUN', '0')
    assert autorun.tick(NS, now) is None and autorun.status(NS, now)['on'] is False
    monkeypatch.delenv('DASH_BRAIN_AUTORUN')
    monkeypatch.setenv('DASH_BRAIN_WRITE', '0')
    assert autorun.tick(NS, now) is None
    monkeypatch.delenv('DASH_BRAIN_WRITE')
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert autorun.tick(NS, now) is None
    assert engine._models(db)[2].query.count() == 0
    assert autorun.start(NS) is False, 'لا خيط داخل الاختبارات'


def test_autorun_status_next_at(env, monkeypatch):
    now = datetime.datetime(2098, 3, 10, 18, 30)
    st = autorun.status(NS, now)
    assert st == {'on': True, 'next_at': '2098-03-11T07:00:00Z', 'hours': [9, 20]}


# ───────────────────────────────────────────────────────────── كرون n8n

def test_agents_cron_kicks_the_brain_first_even_if_agents_crash(api, monkeypatch):
    order = []
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)

    def agent(aid):
        order.append('agent')
        raise RuntimeError('agent crashed')
    monkeypatch.setattr(appmod, '_run_agent', agent)
    monkeypatch.setattr(appmod, '_v2_brain2_kick', lambda trig='cron': order.append('brain'))
    r = flask_app.test_client().post('/api/ai/agents/run-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200 and order[:2] == ['brain', 'agent']


def test_agents_cron_brain_only_skips_the_eleven_agents(api, monkeypatch):
    order = []
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, '_run_agent', lambda aid: order.append('agent'))
    monkeypatch.setattr(appmod, '_v2_brain2_kick', lambda trig='cron': order.append('brain'))
    r = flask_app.test_client().post('/api/ai/agents/run-cron?agent=brain', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'ran': []} and order == ['brain']
    assert flask_app.test_client().post('/api/ai/agents/run-cron?agent=brain').status_code == 401 and order == ['brain']


def test_brain_cron_route_starts_a_real_run(api, monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    r = flask_app.test_client().post('/api/v2/brain/run-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 202 and len(rows()) == 1
    assert latest(api)['report']['trigger_text'] == 'تلقائيًا'


# ───────────────────────────────────────────────────────────── النصوص

def _strings():
    out = [run_report.KEY_WHERE, run_report.KEY_MISSING, run_report.KEY_TEST]
    for reason in ('no_key', 'cap', 'day_cap', 'run_cap', 'reserve', 'off', 'ai_error', 'error', 'busy', 'x'):
        out.extend(run_report.stop_text(reason, run_cap=20, ai_reason='سبب'))
    return [s for s in out if s]


def test_copy_rules_on_run_report_strings():
    for s in _strings():
        assert not re.search(r'[A-Za-z]', s), s
        assert 'يقوّم' not in s and 'استشار' not in s and '·' not in s and not s.startswith('الذكاء'), s
        assert not re.search(r'[0-9]', s), 'أرقام عربية فقط: ' + s


def test_counts_are_arabic_and_grammatical():
    c = run_report.count
    assert c(1, run_report.F_PROPOSAL) == 'اقتراحًا واحدًا' and c(2, run_report.F_PROPOSAL) == 'اقتراحين'
    assert c(3, run_report.F_PROPOSAL) == '٣ اقتراحات' and c(11, run_report.F_PROPOSAL) == '١١ اقتراحًا'
    assert c(20, run_report.F_WRITE) == '٢٠ كتابة' and c(103, run_report.F_NOTE) == '١٠٣ ملاحظات'
