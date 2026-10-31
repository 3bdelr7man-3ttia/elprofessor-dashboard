# -*- coding: utf-8 -*-
"""«العقل» الجولة ٢ · المحرّك (SPEC docs/v2/brain2/SPEC.md §2.3–§2.6، §5 P1).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_engine.py

⛔ صفر شبكة وصفر نداء ذكاء حقيقي: `requests.post/get` ترميان، والناقل `call_anthropic` مستبدل بنصوص JSON مجدولة.
المنتجون هنا مزيّفون ويُحقنون في `registry.PRODUCERS`؛ لا اعتماد على `producers_ops` ولا `producers_biz`.
"""
import datetime
import json
import queue
import threading

import pytest

import app as appmod
from app import app as flask_app, db
from brain2 import engine, registry
from brain2.contract import ApplyResult, Producer, SourceDown, Target

NS = appmod.__dict__
ACTOR = 'founder@x.test'


# ───────────────────────────────────────────────────────────── أدوات

class Script(object):
    """ناقل Claude المزيّف: يسجّل النداءات ويردّ بما جُدول (نص، أو استثناء يُرمى، أو دالة)."""

    def __init__(self, replies=None, default=None):
        self.replies = list(replies or [])
        self.default = default
        self.calls = []

    def __call__(self, api_key, model, system_prompt, user_content):
        self.calls.append({'model': model, 'system': system_prompt, 'user': user_content})
        r = self.replies.pop(0) if self.replies else self.default
        if callable(r):
            r = r(system_prompt, user_content)
        if isinstance(r, Exception):
            raise r
        if isinstance(r, dict):
            r = json.dumps(r, ensure_ascii=False)
        return r


def fp(pid='fp', kind='note', alone=True, targets=None, default_mode=None, per_run_cap=10, template=None,
       apply=None, validate=None, gather=None, section='content', **kw):
    """منتج مزيّف. `targets`: قائمة (ref, facts[, meta])."""
    ts = [Target(ref=t[0], label='هدف ' + t[0], facts=t[1], meta=(t[2] if len(t) > 2 else {})) for t in (targets or [])]

    def _validate(data, t):
        txt = data.get('text')
        return {'text': txt} if isinstance(txt, str) else None
    return Producer(
        id=pid, section=section, kind=kind, label='منتج ' + pid, sentence='عندما يحدث شيء.',
        lock_reason='' if alone else 'يسألك دائمًا.', may_run_alone=alone,
        default_mode=default_mode or ('alone' if alone else 'ask'), per_run_cap=per_run_cap,
        gather=gather or (lambda ctx: list(ts)), prompt=lambda t: ('دورك: اكتب.', 'الحقائق: ' + json.dumps(t.facts, ensure_ascii=False)),
        validate=validate or _validate, template=template, apply=apply, tag='وسم', approve_label='اعتمد', **kw)


@pytest.fixture()
def env(monkeypatch, request):
    for name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'AI_PROVIDER', 'DASHBOARD_AI_MODEL',
                 'ANTHROPIC_MODEL', 'DASH_BRAIN_RUN_CAP', 'DASH_BRAIN_DAY_CAP', 'DASH_BRAIN_OPINION_CAP',
                 'DASH_BRAIN_WRITE'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-fake-never-called')
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')

    def _boom(*a, **k):   # pragma: no cover - يُنفَّذ فقط عند خرق القاعدة
        raise AssertionError('نداء شبكة حقيقي ممنوع')
    monkeypatch.setattr(appmod.requests, 'post', _boom)
    monkeypatch.setattr(appmod.requests, 'get', _boom)
    monkeypatch.setattr(appmod.requests, 'request', _boom)
    # سؤال تليجرام (B2) يمرّ من `_platform_proxy`: بديل محلي يسجّل ولا يخرج لأي شبكة.
    asks = []

    def _fake_proxy(method, path, params=None, json_body=None, timeout=12):
        asks.append({'method': method, 'path': path, 'json': json_body})
        return appmod.jsonify({'sent': True})
    monkeypatch.setattr(appmod, '_platform_proxy', _fake_proxy)
    script = Script(default={'text': 'ملاحظة مكتوبة'})
    script.asks = asks
    monkeypatch.setattr(appmod, 'call_anthropic', script)
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', True)
    day = '2098-02-%02d' % ((abs(hash(request.node.name)) % 27) + 1)
    monkeypatch.setattr(appmod, '_ai_utc_day', lambda: day)
    with flask_app.app_context():
        db.create_all()
        Item, Switch, Run = engine._models(db)
        for M in (Item, Switch, Run):
            M.query.delete()
        row = appmod.AIDailyUsage.query.get(day)
        if row:
            db.session.delete(row)
        db.session.commit()
        yield script
        for M in (Item, Switch, Run):
            M.query.delete()
        db.session.commit()


def use(monkeypatch, *producers):
    monkeypatch.setattr(registry, 'PRODUCERS', list(producers))


def run(only=None, trigger='admin'):
    status, payload = engine.start_run(NS, trigger, ACTOR, only)
    assert status == 202, payload
    return payload['run_id']


def rows(**flt):
    Item = engine._models(db)[0]
    db.session.expire_all()
    return Item.query.filter_by(**flt).order_by(Item.created_at, Item.id).all()


def last_run(run_id):
    db.session.expire_all()
    return engine._models(db)[2].query.get(run_id)


def skipped(run_id):
    return json.loads(last_run(run_id).skipped_json or '{}')


F1 = {'title': 'مقال أول', 'score': 40}
F2 = {'title': 'مقال ثان', 'score': 55}
F3 = {'title': 'مقال ثالث', 'score': 70}


# ───────────────────────────────────────────────────────────── البصمة والتكرار

def test_hash_is_stable_sorted_and_versioned():
    p = fp()
    a = engine.input_hash(p, {'a': 1, 'b': 'ب'})
    assert a == engine.input_hash(p, {'b': 'ب', 'a': 1})
    assert a != engine.input_hash(p, {'a': 2, 'b': 'ب'})
    import dataclasses
    assert a != engine.input_hash(dataclasses.replace(p, version=2), {'a': 1, 'b': 'ب'})
    assert len(a) == 64


def test_second_run_makes_zero_calls(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1), ('a:2', F2)]))
    r1 = run()
    assert len(env.calls) == 2 and last_run(r1).ai_calls == 2 and last_run(r1).items == 2
    run_obj = last_run(r1)
    assert run_obj.finished_at is not None
    r2 = run()
    assert len(env.calls) == 2, 'نفس البصمة ⇒ لا نداء'
    assert last_run(r2).ai_calls == 0
    assert len(rows()) == 2


def test_new_hash_expires_the_old_proposed_row(env, monkeypatch):
    t1 = [('a:1', F1)]
    use(monkeypatch, fp(alone=False, kind='draft', targets=t1))
    run()
    use(monkeypatch, fp(alone=False, kind='draft', targets=[('a:1', dict(F1, score=41))]))
    run()
    st = sorted(r.status for r in rows())
    assert st == ['expired', 'proposed']


def test_system_prompt_carries_the_shared_preamble(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    run()
    assert env.calls[0]['system'].startswith(engine.SYSTEM_AR)
    assert 'دورك: اكتب.' in env.calls[0]['system']


def test_every_ai_call_goes_through_ns_ai_call(env, monkeypatch):
    seen = []

    def spy(system, user, purpose='ai'):
        seen.append(purpose)
        return json.dumps({'text': 'ملاحظة'}, ensure_ascii=False)
    monkeypatch.setattr(appmod, 'ai_call', spy)
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    run()
    assert seen == ['brain2.fp'] and env.calls == []


# ───────────────────────────────────────────────────────────── السقوف

def test_run_cap(env, monkeypatch):
    monkeypatch.setenv('DASH_BRAIN_RUN_CAP', '2')
    use(monkeypatch, fp(targets=[('a:%d' % i, {'n': i}) for i in range(5)]))
    rid = run()
    assert len(env.calls) == 2 and len(rows()) == 2
    assert skipped(rid)['_stop'] == 'run_cap'
    run()                      # جولة جديدة تكمل الباقي
    assert len(env.calls) == 4


def test_day_cap_counts_ai_rows_and_failed_rows(env, monkeypatch):
    monkeypatch.setenv('DASH_BRAIN_DAY_CAP', '3')
    use(monkeypatch, fp(targets=[('a:%d' % i, {'n': i}) for i in range(6)]))
    rid = run()
    assert len(env.calls) == 3 and skipped(rid)['_stop'] == 'day_cap'
    assert engine.brain_today(db) == 3
    # صف فاشل يُحسب أيضًا
    use(monkeypatch, fp(pid='g', targets=[('b:1', {'n': 1})], validate=lambda d, t: None))
    monkeypatch.setenv('DASH_BRAIN_DAY_CAP', '10')
    env.default = {'text': 'x'}
    run()
    assert engine.brain_today(db) == 4 and rows(producer='g')[0].status == 'failed'


def test_template_rows_do_not_count_toward_the_day_cap_rows_but_do_inside_the_run(env, monkeypatch):
    monkeypatch.setenv('DASH_BRAIN_DAY_CAP', '2')
    env.default = RuntimeError('boom')
    tpl = lambda t: {'text': 'قالب ' + t.facts['title']}
    use(monkeypatch, fp(targets=[('a:1', F1), ('a:2', F2), ('a:3', F3)], template=tpl))
    rid = run()
    assert len(env.calls) == 2 and skipped(rid)['_stop'] == 'day_cap'
    assert {r.source for r in rows()} == {'template'}


def test_per_run_cap(env, monkeypatch):
    use(monkeypatch, fp(per_run_cap=2, targets=[('a:%d' % i, {'n': i}) for i in range(5)]),
        fp(pid='other', targets=[('o:1', {'n': 9})]))
    rid = run()
    assert len(env.calls) == 3, 'منتجان: ٢ + ١'
    assert skipped(rid)['fp:per_run_cap'] == 3


def test_opinion_cap_inside_the_day_cap(env, monkeypatch):
    monkeypatch.setenv('DASH_BRAIN_OPINION_CAP', '1')
    use(monkeypatch, fp(pid='opinion', kind='opinion', section='home', targets=[]))
    item, reason, queued = engine.submit_opinion(NS, 'review', 'c1', {'tag': 'مراجعة'})
    assert queued and reason is None
    assert [r.status for r in rows(producer='opinion')] == ['done_alone']
    item, reason, queued = engine.submit_opinion(NS, 'review', 'c2', {'tag': 'مراجعة'})
    assert item is None and reason == 'cap' and not queued
    assert len(env.calls) == 1


def test_reserve_stops_before_the_call(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    monkeypatch.setattr(appmod, 'ai_daily_usage_state', lambda: {'remaining': 24})
    rid = run()
    assert env.calls == [] and skipped(rid)['_stop'] == 'reserve' and rows() == []
    monkeypatch.setattr(appmod, 'ai_daily_usage_state', lambda: {'remaining': 25})
    run()
    assert len(env.calls) == 1
    monkeypatch.setattr(appmod, 'ai_daily_usage_state', lambda: {'remaining': None})
    use(monkeypatch, fp(targets=[('a:2', F2)]))
    run()
    assert len(env.calls) == 2


def test_kill_switch_stops_all_writing(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    monkeypatch.setenv('DASH_BRAIN_WRITE', '0')
    status, payload = engine.start_run(NS, 'admin', ACTOR)
    assert status == 409 and payload['error'] == engine.ERR_WRITE_OFF
    assert env.calls == [] and rows() == []
    use(monkeypatch, fp(pid='opinion', kind='opinion', targets=[]))
    assert engine.submit_opinion(NS, 'review', 'c1', {})[1] == 'off'


# ───────────────────────────────────────────────────────────── الفشل

def test_cap_and_no_key_stop_the_whole_run(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1), ('a:2', F2)]), fp(pid='second', targets=[('s:1', F3)]))
    def capped(system, user, purpose='ai'):
        env.calls.append({'user': user})
        raise appmod.AIUnavailable('سقف', kind='cap')
    monkeypatch.setattr(appmod, 'ai_call', capped)
    rid = run()
    assert len(env.calls) == 1 and rows() == [] and skipped(rid)['_stop'] == 'cap'
    # لا مفتاح: لا نداء أصلًا والجولة تتوقف
    monkeypatch.undo()   # يرجع ai_call الحقيقي
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', True)
    use(monkeypatch, fp(targets=[('a:1', F1), ('a:2', F2)]), fp(pid='second', targets=[('s:1', F3)]))
    env.calls.clear()
    rid = run()
    assert env.calls == [] and rows() == [] and skipped(rid)['_stop'] == 'no_key'


def test_real_daily_cap_from_ai_call_stops_the_run(env, monkeypatch):
    monkeypatch.setenv('DASHBOARD_AI_DAILY_CAP', '1')
    use(monkeypatch, fp(targets=[('a:1', F1), ('a:2', F2)]))
    rid = run()
    # الاحتياطي (٢٥) يمنع أصلًا قبل النداء حين السقف اليومي صغير
    assert env.calls == [] and skipped(rid)['_stop'] == 'reserve'


def test_failed_row_blocks_the_same_hash_until_next_utc_day(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    env.replies = ['ليس JSON']
    run()
    (r,) = rows()
    assert r.status == 'failed' and r.source == 'ai' and r.last_error
    run()
    assert len(env.calls) == 1, 'الفاشل يحجب البصمة نفسها اليوم'
    r.created_at = r.created_at - datetime.timedelta(days=1)
    db.session.commit()
    env.replies = [{'text': 'نجحت'}]
    run()
    assert len(env.calls) == 2
    (r2,) = rows()
    assert r2.status == 'done_alone' and r2.id != r.id


def test_ai_error_without_template_is_a_failed_row_without_card(env, monkeypatch):
    use(monkeypatch, fp(alone=False, kind='draft', targets=[('a:1', F1)]))
    env.replies = [RuntimeError('boom')]
    run()
    (r,) = rows()
    assert r.status == 'failed' and json.loads(r.body_json) == {}


def test_template_row_is_marked_source_template(env, monkeypatch):
    tpl = lambda t: {'text': 'ينقصها: ' + t.facts['title']}
    use(monkeypatch, fp(targets=[('a:1', F1), ('a:2', F2)], template=tpl))
    env.replies = [RuntimeError('boom'), 'ليس JSON']
    run()
    rs = rows()
    assert [r.source for r in rs] == ['template', 'template']
    assert json.loads(rs[0].body_json)['text'] == 'ينقصها: مقال أول'
    assert len(env.calls) == 2, 'لا إعادة محاولة'


def test_template_that_fails_the_checks_becomes_failed(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)], template=lambda t: {'text': 'رقم 9999 مخترع'}))
    env.replies = [RuntimeError('boom')]
    run()
    assert rows()[0].status == 'failed'


def test_source_down_stores_nothing_and_other_producers_still_run(env, monkeypatch):
    def down(ctx):
        raise SourceDown('x')
    use(monkeypatch, fp(pid='bad', gather=down), fp(targets=[('a:1', F1)]))
    rid = run()
    assert skipped(rid)['bad:source_down'] == 1
    assert [r.producer for r in rows()] == ['fp']


def test_off_mode_skips_gather(env, monkeypatch):
    touched = []

    def g(ctx):
        touched.append(1)
        return [Target('a:1', 'x', F1)]
    use(monkeypatch, fp(gather=g))
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='fp', mode='off'))
    db.session.commit()
    rid = run()
    assert touched == [] and env.calls == [] and skipped(rid)['fp:off'] == 1


def test_only_filters_the_producers_and_opinion_is_never_run(env, monkeypatch):
    use(monkeypatch, fp(pid='one', targets=[('a:1', F1)]), fp(pid='two', targets=[('b:1', F2)]),
        fp(pid='opinion', kind='opinion', targets=[('c:1', F3)]))
    run(only=['two'])
    assert [r.producer for r in rows()] == ['two']
    run()
    assert sorted(r.producer for r in rows()) == ['one', 'two']


# ───────────────────────────────────────────────────────────── فحوص الصدق

FACTS = {'title': 'Contract law', 'score': 40, 'contact': 'who@x.test', 'phone': '+201001234567'}


@pytest.mark.parametrize('text,code', [
    ('الدرجة ٤١ من مئة', 'number'),
    ('الدرجة 99', 'number'),
    ('تحسين Marketing للمقال', 'latin'),
    ('هذا لا يقوّم المقال', 'banned'),
    ('هذا لا يُقَوِّمُ المقال', 'banned'),
    ('الذكاء يقول إن المقال جيد', 'lead'),
    ('«AI» says fine', 'lead'),
    ('اكتب إلى x@x.test', 'email'),
    ('اتصل على 0111 111 111', 'phone'),
    ('', 'empty'),
    ('ا' * 601, 'long'),
])
def test_honesty_checks_reject(text, code):
    facts = dict(FACTS, ai='AI says fine', more='0111 and 111')
    assert engine.check_body({'text': text}, facts, 'note') == code


def test_honesty_checks_accept_facts_digits_latin_and_contacts():
    ok = 'الدرجة ٤٠ في Contract law والبريد who@x.test'
    assert engine.check_body({'text': ok}, FACTS, 'note') is None
    assert engine.check_body({'text': 'الهاتف +201001234567'}, FACTS, 'note') is None
    assert engine.check_body({'text': 'a'}, {}, 'note') == 'latin'


def test_limits_per_kind_and_why():
    assert engine.check_body({'text': 'ا' * 220}, {}, 'opinion') is None
    assert engine.check_body({'text': 'ا' * 221}, {}, 'opinion') == 'long'
    assert engine.check_body({'text': 'ا' * 900}, {}, 'draft') is None
    assert engine.check_body({'text': 'ب', 'why': 'ا' * 161}, {}, 'opinion') == 'why'
    assert engine.check_body({'text': 'ب', 'recommend': 'approve'}, {}, 'opinion') is None, 'recommend ليس نصًّا مفحوصًا'
    assert engine.check_body({'text': 'ب', 'fields': {'body': 'خمسة 5'}}, {}, 'draft') == 'number'


def test_invalid_output_goes_through_the_failure_rule(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    env.replies = [{'text': 'الدرجة 777'}]
    run()
    assert rows()[0].status == 'failed'


def test_validate_returning_none_or_raising_is_invalid(env, monkeypatch):
    def boom(d, t):
        raise ValueError('x')
    use(monkeypatch, fp(targets=[('a:1', F1)], validate=boom), fp(pid='n', targets=[('n:1', F1)], validate=lambda d, t: None))
    run()
    assert {r.status for r in rows()} == {'failed'} and len(rows()) == 2


# ───────────────────────────────────────────────────────────── الأوضاع والأقفال

def test_alone_note_is_done_alone_and_ask_note_is_proposed(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    run()
    assert rows()[0].status == 'done_alone' and rows()[0].mode == 'alone'
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='fp', mode='ask'))
    db.session.commit()
    use(monkeypatch, fp(targets=[('a:2', F2)]))
    run()
    assert rows(target_ref='a:2')[0].status == 'proposed'


def test_a_draft_never_becomes_done_alone(env, monkeypatch):
    use(monkeypatch, fp(kind='draft', alone=True, targets=[('a:1', F1)]))   # حتى لو may_run_alone
    run()
    assert rows()[0].status == 'proposed'


def test_locked_producer_is_coerced_to_ask_even_with_a_tampered_row(env, monkeypatch):
    p = fp(alone=False, kind='note', targets=[('a:1', F1)])
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='fp', mode='alone'))
    db.session.commit()
    assert engine.effective_mode(NS, p) == 'ask'
    use(monkeypatch, p)
    run()
    (r,) = rows()
    assert r.status == 'proposed' and r.mode == 'ask'


def test_mode_is_rechecked_at_store_time(env, monkeypatch):
    """المفتاح ينقلب إلى متوقّف أثناء النداء ⇒ لا يُخزَّن شيء."""
    Switch = engine._models(db)[1]

    def flip(system, user):
        db.session.add(Switch(producer='fp', mode='off'))
        db.session.commit()
        return {'text': 'ملاحظة'}
    env.replies = [flip]
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    run()
    assert rows() == []


def test_opinion_status_is_always_done_alone_and_money_kinds_lose_recommend(env, monkeypatch):
    def val(d, t):
        return {'text': d['opinion'], 'recommend': d.get('recommend'), 'why': d.get('why')}
    use(monkeypatch, fp(pid='opinion', kind='opinion', section='home', targets=[], validate=val))
    env.replies = [{'opinion': 'رأي قصير', 'recommend': 'approve', 'why': 'سبب'},
                   {'opinion': 'رأي قصير', 'recommend': 'wait', 'why': 'سبب'}]
    assert engine.submit_opinion(NS, 'payout', 'c1', {'tag': 'سحب'})[2]
    assert engine.submit_opinion(NS, 'trainer', 'c2', {'tag': 'مدرّب'})[2]
    by_ref = {r.target_ref: r for r in rows(producer='opinion')}
    assert by_ref['card:c1'].status == 'done_alone'
    assert 'recommend' not in json.loads(by_ref['card:c1'].body_json), 'المال نص فقط'
    assert by_ref['card:c2'].status == 'failed', 'توصية خارج القايمة المسموحة ⇒ مرفوض'


def test_opinion_flow_cache_and_reasons(env, monkeypatch):
    def val(d, t):
        return {'text': d['opinion']}
    use(monkeypatch, fp(pid='opinion', kind='opinion', section='home', targets=[], validate=val))
    env.default = {'opinion': 'رأي'}
    facts = {'tag': 'مراجعة', 'age': 'منذ يوم'}
    assert engine.submit_opinion(NS, 'review', 'c1', facts)[2] is True
    item, reason, queued = engine.submit_opinion(NS, 'review', 'c1', facts)
    assert item is not None and not queued and len(env.calls) == 1, 'المخبّأ لا يستدعي'
    assert engine.submit_opinion(NS, 'file_waiting', 'c9', facts)[1] == 'not_supported'
    assert engine.submit_opinion(NS, 'nonsense', 'c9', facts)[1] == 'not_supported'
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    assert engine.submit_opinion(NS, 'review', 'c3', facts)[1] == 'no_writer'
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='opinion', mode='off'))
    db.session.commit()
    assert engine.submit_opinion(NS, 'review', 'c4', facts)[1] == 'off'


def test_opinion_facts_cleaning():
    dirty = {'tag': 'مدرّب جديد', 'reason': 'راسله على who@x.test أو 01001234567 الآن', 'secret': 'x',
             'facts': ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], 'sub': 'ا' * 500, 'age': 5, 'headline': 'غير مسموح للنوع'}
    c = engine.clean_opinion_facts('review', dirty)
    assert 'secret' not in c and 'headline' not in c
    assert '@' not in c['reason'] and '01001234567' not in c['reason']
    assert len(c['facts']) == 6 and len(c['sub']) == 300 and c['age'] == 5
    assert 'headline' in engine.clean_opinion_facts('trainer', dirty)


# ───────────────────────────────────────────────────────────── الاعتماد

def _proposed(env, monkeypatch, apply, **kw):
    use(monkeypatch, fp(alone=False, kind='draft', targets=[('m:1', F1, {'email': 'x@y.test'})], apply=apply, **kw))
    run()
    (r,) = rows()
    assert r.status == 'proposed'
    return r.id


def test_apply_runs_exactly_once_and_double_approve_is_409(env, monkeypatch):
    calls = []

    def ap(ctx, body, target):
        calls.append((ctx.actor, body['text'], target.meta))
        return ApplyResult(ok=True, copy_text='انسخ هذا')
    rid = _proposed(env, monkeypatch, ap)
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 200 and pl['status'] == 'approved' and pl['copy_text'] == 'انسخ هذا'
    assert calls == [(ACTOR, 'ملاحظة مكتوبة', {'email': 'x@y.test'})]
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 409 and pl['error'] == 'حُسم هذا الاقتراح من قبل' and len(calls) == 1
    r = rows()[0]
    assert r.decided_by == ACTOR and r.decided_at is not None


def test_apply_concurrent_conditional_update_loses_cleanly(env, monkeypatch):
    """صف انتقل إلى applying من مسار آخر قبل التحديث الشرطي ⇒ ٤٠٩ ولا apply."""
    calls = []
    rid = _proposed(env, monkeypatch, lambda c, b, t: calls.append(1) or ApplyResult(ok=True))
    Item = engine._models(db)[0]
    Item.query.filter_by(id=rid).update({'status': 'applying'})
    db.session.commit()
    assert engine.apply_item(NS, rid, ACTOR)[0] == 409 and calls == []


def test_edited_text_is_applied_and_marks_edited(env, monkeypatch):
    seen = []
    rid = _proposed(env, monkeypatch, lambda c, b, t: seen.append(b['text']) or ApplyResult(ok=True))
    st, pl = engine.apply_item(NS, rid, ACTOR, 'نص عدّله المؤسس')
    assert st == 200 and pl['status'] == 'edited' and seen == ['نص عدّله المؤسس']
    assert json.loads(rows()[0].body_json)['text'] == 'نص عدّله المؤسس'


def test_no_reply_marks_unknown(env, monkeypatch):
    rid = _proposed(env, monkeypatch, lambda c, b, t: ApplyResult(ok=False, no_reply=True))
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 502 and pl['no_reply'] is True and 'لم يصل رد' in pl['error']
    assert rows()[0].status == 'unknown'
    assert engine.apply_item(NS, rid, ACTOR)[0] == 409, 'unknown لا يُنفَّذ ثانية من غير تحقق المؤسس'


def test_failed_apply_returns_to_proposed_with_last_error(env, monkeypatch):
    rid = _proposed(env, monkeypatch, lambda c, b, t: ApplyResult(ok=False, error='المنصة رفضت'))
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 422 and pl['error'] == 'المنصة رفضت'
    r = rows()[0]
    assert r.status == 'proposed' and r.last_error == 'المنصة رفضت'


def test_apply_exception_is_treated_as_unknown(env, monkeypatch):
    def boom(c, b, t):
        raise RuntimeError('x')
    rid = _proposed(env, monkeypatch, boom)
    assert engine.apply_item(NS, rid, ACTOR)[0] == 502
    assert rows()[0].status == 'unknown'


def test_apply_none_just_records_the_decision(env, monkeypatch):
    rid = _proposed(env, monkeypatch, None)
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 200 and rows()[0].status == 'approved'


def test_approve_is_audited(env, monkeypatch):
    rid = _proposed(env, monkeypatch, lambda c, b, t: ApplyResult(ok=True))
    engine.apply_item(NS, rid, ACTOR)
    a = appmod.AuditLog.query.filter_by(action='brain.approve', target=rid).first()
    assert a is not None and json.loads(a.meta_json) == {'producer': 'fp', 'edited': False}


def test_discarded_when_no_course_matches(env, monkeypatch):
    def val(d, t):
        return {'text': d.get('text', ''), 'course_id': d.get('course_id')}
    use(monkeypatch, fp(alone=False, kind='draft', targets=[('r:1', F1)], validate=val))
    env.replies = [{'text': '', 'course_id': None}]
    run()
    (r,) = rows()
    assert r.status == 'discarded'
    assert engine.apply_item(NS, r.id, ACTOR)[0] == 409


# ───────────────────────────────────────────────────────────── الجولة والخيط

def test_run_lock_returns_409_for_fifteen_minutes(env, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    Run = engine._models(db)[2]
    old = datetime.datetime.utcnow() - datetime.timedelta(minutes=20)
    db.session.add(Run(id='a' * 32, trigger='admin', started_at=old))
    db.session.commit()
    assert engine.start_run(NS, 'admin', ACTOR)[0] == 202, 'القفل القديم لا يحجب'
    Run.query.delete()
    db.session.add(Run(id='b' * 32, trigger='admin', started_at=datetime.datetime.utcnow()))
    db.session.commit()
    st, pl = engine.start_run(NS, 'admin', ACTOR)
    assert st == 409 and pl['error'] == 'العقل يكتب الآن. جرّب بعد قليل'


def test_queue_is_bounded_deduped_and_reports_busy(env, monkeypatch):
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', False)
    monkeypatch.setattr(engine, '_Q', queue.Queue(maxsize=engine.QUEUE_SIZE))
    monkeypatch.setattr(engine, '_PENDING', set())

    class Alive(object):
        def is_alive(self):
            return True
    monkeypatch.setitem(engine._WORKER, 'thread', Alive())     # لا خيط يستهلك
    fn = lambda: None
    assert engine.QUEUE_SIZE == 8
    for i in range(8):
        assert engine.submit(NS, 'k%d' % i, fn) == {'queued': True}
    assert engine.submit(NS, 'k3', fn).get('duplicate') is True
    assert engine.submit(NS, 'k9', fn) == {'queued': False, 'reason': 'busy'}


def test_worker_thread_runs_the_job_inside_an_app_context(env, monkeypatch):
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', False)
    monkeypatch.setattr(engine, '_Q', queue.Queue(maxsize=engine.QUEUE_SIZE))
    monkeypatch.setattr(engine, '_PENDING', set())
    monkeypatch.setitem(engine._WORKER, 'thread', None)
    from flask import has_app_context
    done = threading.Event()
    box = {}

    def job():
        box['ctx'] = has_app_context()
        box['thread'] = threading.current_thread().name
        done.set()
    assert engine.submit(NS, 'real', job) == {'queued': True}
    assert done.wait(5)
    assert box == {'ctx': True, 'thread': 'brain2-worker'}


def test_http_threads_never_call_ai_when_not_inline(env, monkeypatch):
    """خارج الوضع المضمّن: start_run يرجع قبل أي نداء (النداء في الخيط الخلفي)."""
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', False)
    monkeypatch.setattr(engine, '_Q', queue.Queue(maxsize=engine.QUEUE_SIZE))
    monkeypatch.setattr(engine, '_PENDING', set())

    class Alive(object):
        def is_alive(self):
            return True
    monkeypatch.setitem(engine._WORKER, 'thread', Alive())
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    st, pl = engine.start_run(NS, 'admin', ACTOR)
    assert st == 202 and env.calls == [] and rows() == []


def test_writer_label_never_names_a_provider(monkeypatch):
    for k in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'AI_PROVIDER'):
        monkeypatch.delenv(k, raising=False)
    assert engine.writer_of(NS) is None
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'k')
    assert engine.writer_of(NS) == 'backup'
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'k')
    assert engine.writer_of(NS) == 'main'


def test_tables_exist_with_the_spec_columns():
    with flask_app.app_context():
        Item, Switch, Run = engine._models(db)
        assert Item.__tablename__ == 'v2_brain_items' and Switch.__tablename__ == 'v2_brain_switches' and Run.__tablename__ == 'v2_brain_runs'
        assert {c.name for c in Item.__table__.columns} == {
            'id', 'producer', 'section', 'kind', 'target_ref', 'target_label', 'input_hash', 'facts_json', 'meta_json',
            'body_json', 'status', 'source', 'mode', 'run_id', 'created_at', 'decided_at', 'decided_by', 'last_error',
            'applied_json'}
        assert {c.name for c in Run.__table__.columns} == {'id', 'trigger', 'started_at', 'finished_at', 'ai_calls',
                                                            'items', 'skipped_json', 'by'}
        assert {c.name for c in Switch.__table__.columns} == {'producer', 'mode', 'updated_at', 'updated_by', 'telegram'}


# ───────────────────────────────────────────────────────────── تكامل P2/P3

def test_approve_label_prefers_meta_then_body_then_producer(env, monkeypatch):
    def val(d, t):
        out = {'text': d['text']}
        if d.get('label'):
            out['approve_label'] = d['label']
        return out
    use(monkeypatch,
        fp(pid='one', alone=False, kind='draft', targets=[('a:1', F1, {'approve_label': 'أرسل الرد'})], validate=val),
        fp(pid='two', alone=False, kind='draft', targets=[('b:1', F2)], validate=val),
        fp(pid='three', alone=False, kind='draft', targets=[('c:1', F3)], validate=val))
    env.replies = [{'text': 'أ', 'label': 'من الجسم'}, {'text': 'ب', 'label': 'انشر الدورة'}, {'text': 'ج'}]
    run()
    lab = {r.producer: json.loads(r.body_json)['approve_label'] for r in rows()}
    assert lab == {'one': 'أرسل الرد', 'two': 'انشر الدورة', 'three': 'اعتمد'}


def test_gather_with_errors_records_the_failed_source_only_for_the_real_ops_gather(env, monkeypatch):
    import types
    mod = types.SimpleNamespace(__name__='fakeops')

    def gather(ctx):      # pragma: no cover - لا يُنادى: يُفضَّل gather_with_errors
        raise AssertionError('gather_with_errors أولًا')

    def gwe(ctx):
        return [Target('pmsg:1', 'رسالة', F1)], [{'source': 'leads', 'reason': 'down'}]
    gather.__module__ = 'fakeops'
    mod.gather_with_errors = gwe
    monkeypatch.setattr(engine, '_ops', lambda: mod)
    use(monkeypatch, fp(pid='reply_draft', alone=False, kind='draft', gather=gather))
    rid = run()
    assert skipped(rid) == {'reply_draft:leads:down': 1} and len(rows()) == 1
    # منتج مزيّف بالاسم نفسه وغير معرّف في الوحدة ⇒ يُستعمل gather الخاص به
    use(monkeypatch, fp(pid='reply_draft', alone=False, kind='draft', targets=[('pmsg:2', F2)]))
    run()
    assert sorted(r.target_ref for r in rows()) == ['pmsg:1', 'pmsg:2']


def test_failed_apply_with_copy_text_returns_it(env, monkeypatch):
    rid = _proposed(env, monkeypatch, lambda c, b, t: ApplyResult(ok=False, error='زائر بلا حساب', copy_text='انسخ'))
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 422 and pl == {'error': 'زائر بلا حساب', 'copy_text': 'انسخ'}
    assert rows()[0].status == 'proposed'


def test_ok_with_no_write_info_is_approved(env, monkeypatch):
    rid = _proposed(env, monkeypatch, lambda c, b, t: ApplyResult(ok=True, info={'no_write': True}))
    st, pl = engine.apply_item(NS, rid, ACTOR)
    assert st == 200 and pl['info'] == {'no_write': True} and rows()[0].status == 'approved'


def test_ops_opinion_helpers_are_used_lazily_when_present(env, monkeypatch):
    import types
    seen = {}

    def clean(kind, facts):
        seen['clean'] = kind
        return {'tag': 'نظيف'}

    def target(kind, card_id, facts):
        if kind == 'bad':
            raise ValueError('not_supported')
        seen['target'] = (kind, card_id)
        return Target(ref='card:' + card_id, label='بطاقة', facts=dict(facts, kind=kind), meta={'kind': kind})
    mod = types.SimpleNamespace(__name__='fakeops', clean_opinion_facts=clean, opinion_target=target,
                                opinion_supported=lambda k: k != 'bad', OPINION_MAX_FACTS_BYTES=500)
    monkeypatch.setattr(engine, '_ops', lambda: mod)
    assert engine.clean_opinion_facts('review', {'tag': 'x'}) == {'tag': 'نظيف'}
    assert engine.opinion_max_bytes() == 500
    assert engine.opinion_spec('bad') is None and engine.opinion_target('bad', 'c', {}) is None
    use(monkeypatch, fp(pid='opinion', kind='opinion', section='home', targets=[],
                        validate=lambda d, t: {'text': d['opinion']}))
    env.default = {'opinion': 'رأي'}
    assert engine.submit_opinion(NS, 'review', 'c1', {'tag': 'نظيف'})[2]
    assert seen['target'] == ('review', 'c1') and rows(producer='opinion')[0].status == 'done_alone'
    assert engine.submit_opinion(NS, 'bad', 'c2', {})[1] == 'not_supported'
