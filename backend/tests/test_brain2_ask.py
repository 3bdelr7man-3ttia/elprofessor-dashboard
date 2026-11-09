# -*- coding: utf-8 -*-
"""«العقل» · تصحيحات «اسأل» `ask_correction` («دقة اسأل» 2026-11-09).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_ask.py

⛔ صفر شبكة وصفر ذكاء حقيقي: `_platform_proxy` و`_v2_write` بدائل محلية. النصوص تجريبية مش قانون حقيقي.
"""
import datetime
import json

import pytest

import app as appmod
from brain2 import producers_ask as pa, registry
from brain2.contract import Ctx, SourceDown, Target

UTC = datetime.timezone.utc


def _no_net(*a, **k):
    raise AssertionError('شبكة حقيقية ممنوعة')


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    for n in ('post', 'get', 'request'):
        monkeypatch.setattr(appmod.requests, n, _no_net)


class FakePlatform(object):
    def __init__(self, routes=None):
        self.routes = routes or {}
        self.calls = []

    def __call__(self, method, path, params=None, json_body=None, timeout=12):
        self.calls.append({'method': method, 'path': path, 'params': params})
        r = self.routes.get((method, path))
        if r is None:
            return {'error': 'Not Found'}, 404
        if isinstance(r, Exception):
            raise r
        return r[1], r[0]


AP = 'eg-administrative-prosecution'


def _fb(fid='f1', **kw):
    d = {'id': fid, 'verdict': 'wrong', 'question': 'هل تختص الجهة التجريبية بالتحقيق؟',
         'answer': 'لا تختص الجهة التجريبية.', 'correction': 'تختص الجهة التجريبية بالتحقيق طبقًا لنص المادة 4.',
         'track': AP, 'user_role': 'trainer', 'persona': '', 'needs_expert': True, 'updated_at': '2026-11-09'}
    d.update(kw)
    return d


def _ctx(plat, write=None):
    ns = {'_platform_proxy': plat, '_v2_write': write or (lambda *a: ({'ok': True}, 200)),
          '_resp_ok': lambda r: isinstance(r, tuple) and r[1] == 200,
          '_proxy_json': lambda r: r[0] if isinstance(r, tuple) else {}}
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor='admin@test')


def _plat(items, arts=None):
    return FakePlatform({
        ('GET', '/api/bridge/ask/feedback'): (200, {'items': items, 'count': len(items)}),
        ('GET', '/api/bridge/ask/articles/search'): (200, {'items': arts if arts is not None else [
            {'ref': '[ق 999/2099 م 4]', 'text': 'تختص الجهة التجريبية بالتحقيق في المخالفات.'}]}),
    })


def test_registered_locked_to_ask_and_on_telegram():
    p = registry.by_id('ask_correction')
    assert p is not None and p.default_mode == 'ask' and p.may_run_alone is False
    assert 'ask_correction' in registry.TELEGRAM_DEFAULT_ON
    assert 'ask_correction' not in registry.TELEGRAM_OK      # الاعتماد من اللوحة بس


def test_gather_keeps_track_corrections_with_text_and_attaches_articles():
    items = [_fb('f1'), _fb('f2', correction='قصير'), _fb('f3', track='general'), _fb('bad id!')]
    out = pa.gather(_ctx(_plat(items)))
    assert [t.ref for t in out] == ['askfb:f1']
    f = out[0].facts
    assert f['track'] == 'النيابة الإدارية' and f['articles'][0]['ref'] == '[ق 999/2099 م 4]'
    assert out[0].meta == {'feedback_id': 'f1', 'track': AP}
    assert len(json.dumps(f, ensure_ascii=False).encode('utf-8')) <= pa.FACTS_MAX_BYTES


def test_gather_fits_huge_inputs():
    big = _fb('f1', answer='كلام ' * 2000, correction='تصحيح ' * 600)
    arts = [{'ref': '[ق 999/2099 م %d]' % i, 'text': 'نص ' * 400} for i in (1, 2, 3)]
    out = pa.gather(_ctx(_plat([big], arts)))
    assert len(json.dumps(out[0].facts, ensure_ascii=False).encode('utf-8')) <= pa.FACTS_MAX_BYTES


def test_gather_404_means_bridge_not_published_yet():
    assert pa.gather(_ctx(FakePlatform())) == []


def test_gather_5xx_is_source_down():
    plat = FakePlatform({('GET', '/api/bridge/ask/feedback'): (500, {})})
    with pytest.raises(SourceDown):
        pa.gather(_ctx(plat))


def _target(with_articles=True):
    facts = {'track': 'النيابة الإدارية', 'question': 'س', 'wrong_answer': 'ر',
             'correction': 'تختص الجهة التجريبية طبقًا لنص المادة 4.', 'role': ''}
    if with_articles:
        facts['articles'] = [{'ref': '[ق 999/2099 م 4]', 'text': 'نص تجريبي'}]
    return Target(ref='askfb:f1', label='x', facts=facts, meta={'feedback_id': 'f1', 'track': AP})


def test_validate_verdict_rules():
    t = _target()
    ok = pa.validate({'verdict': 'agrees', 'why': 'المادة [ق 999/2099 م 4]', 'text': 'تختص الجهة التجريبية.',
                      'article_refs': ['المادة 4']}, t)
    assert ok['verdict'] == 'agrees' and ok['why'].startswith('يتّفق مع النص') and len(ok['why']) <= 160
    # مرجع مش حرفيًا من كلام المصحِّح ⇒ مرفوض
    assert pa.validate({'verdict': 'agrees', 'text': 'x' * 20, 'article_refs': ['المادة 9']}, t) is None
    # «يتّفق» من غير مواد معطاة = من ذاكرة الموديل ⇒ مرفوض
    assert pa.validate({'verdict': 'agrees', 'text': 'x' * 20, 'article_refs': []}, _target(False)) is None
    assert pa.validate({'verdict': 'no_text', 'text': 'x' * 20, 'article_refs': []}, _target(False))['verdict'] == 'no_text'
    assert pa.validate({'verdict': 'maybe', 'text': 'x' * 20}, t) is None


def test_template_is_the_correction_itself():
    b = pa.template(_target())
    assert b['text'].startswith('تختص الجهة التجريبية') and b['verdict'] == 'no_text'


def test_apply_writes_one_correction_through_v2_write():
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append((method, path, body, action, target))
        return ({'ok': True}, 200)

    res = pa.apply(_ctx(FakePlatform(), write), {'text': 'تختص الجهة التجريبية بالتحقيق.', 'article_refs': ['المادة 4']},
                   _target())
    assert res.ok
    m, path, body, action, target = seen[0]
    assert (m, path, action, target) == ('POST', '/api/bridge/ask/corrections', 'ask.correction_approve', 'f1')
    assert body['track'] == AP and body['feedback_id'] == 'f1' and body['approved_text'].startswith('تختص')


def test_apply_refuses_empty_text():
    res = pa.apply(_ctx(FakePlatform()), {'text': ' '}, _target())
    assert res.ok is False and res.error


# ---------------------------------------------------------------- نقاش المصحِّح مع المراجِع (discussion)

def _disc(n, size=50):
    return [{'role': 'user' if i % 2 == 0 else 'critic', 'text': ('م%d ' % i) * size, 'at': '2026-11-09T10:0%d:00' % i} for i in range(n)]


def test_gather_adds_last_four_discussion_messages_cut_to_300():
    out = pa.gather(_ctx(_plat([_fb('f1', discussion=_disc(6, 200))])))
    d = out[0].facts['discussion']
    assert len(d) == 4 and [m['text'][:2] for m in d] == ['م2', 'م3', 'م4', 'م5'], 'آخر ٤'
    assert all(len(m['text']) <= pa.DISC_MSG_MAX and set(m) == {'role', 'text'} for m in d)


def test_gather_ignores_missing_or_malformed_discussion():
    for bad in (None, 'نص', {'a': 1}, [1, 'x', {'role': 'admin', 'text': 'x'}, {'role': 'user', 'text': ' '}]):
        out = pa.gather(_ctx(_plat([_fb('f1', discussion=bad)])))
        assert 'discussion' not in out[0].facts, bad
    assert 'discussion' not in pa.gather(_ctx(_plat([_fb('f1')])))[0].facts


def test_gather_with_discussion_still_fits_the_byte_cap_and_keeps_correction_whole():
    big = _fb('f1', answer='كلام ' * 2000, correction='تصحيح ' * 150, discussion=_disc(6, 200))
    arts = [{'ref': '[ق 999/2099 م %d]' % i, 'text': 'نص ' * 400} for i in (1, 2, 3)]
    f = pa.gather(_ctx(_plat([big], arts)))[0].facts
    assert len(json.dumps(f, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= pa.FACTS_MAX_BYTES
    assert f['correction'] == ('تصحيح ' * 150).strip()[:pa.C_MAX], 'التصحيح آخر ما يُقصّ'


def test_fit_trims_discussion_before_the_correction():
    f = {'wrong_answer': 'ر' * 200, 'correction': 'ت' * 700, 'discussion': _disc(4, 100)}
    f['discussion'] = [dict(m, text=m['text'][:300]) for m in f['discussion']]
    pa.FACTS_MAX_BYTES, old = 3900, pa.FACTS_MAX_BYTES
    try:
        f['question'] = 'س' * 300
        f['articles'] = [{'ref': 'r', 'text': 'ن' * 140}] * 3
        pa._fit(f)
    finally:
        pa.FACTS_MAX_BYTES = old
    assert len(f['correction']) == 700 and len(f['discussion']) < 4
    assert len(json.dumps(f, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= pa.FACTS_MAX_BYTES


def test_prompt_carries_discussion_and_the_role_tells_the_reviewer_to_weigh_the_cited_ground():
    t = _target()
    t.facts['discussion'] = [{'role': 'user', 'text': 'السند المادة 4 من القانون التجريبي'}]
    system, user = pa.prompt(t)
    assert 'السند المادة 4' in user and 'discussion' in system and 'سندًا' in system
    assert 'لا يُغني عن نص معطى' in system, 'السند المذكور وحده لا يكفي لحكم agrees'


def test_fit_with_discussion_keeps_the_articles():
    big = _fb('f1', answer='ج' * 900, correction='ت' * 250, discussion=_disc(4, 100))
    big['question'] = 'س' * 150
    arts = [{'ref': '[ق 999/2099 م %d]' % i, 'text': 'ن' * 700} for i in (1, 2, 3)]
    f = pa.gather(_ctx(_plat([big], arts)))[0].facts
    assert f.get('articles'), 'النقاش يتقلّص قبل ما أي مادة تتمس'
    assert len(f['articles']) == 3
    assert len(json.dumps(f, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= pa.FACTS_MAX_BYTES


def test_refs_may_come_from_user_discussion_but_not_from_critic():
    t = _target()
    t.facts['correction'] = 'تختص الجهة التجريبية بالأمر.'
    t.facts['discussion'] = [{'role': 'user', 'text': 'السند المادة 4 من القانون'},
                             {'role': 'critic', 'text': 'ربما المادة 7 أيضًا'}]
    body = {'verdict': 'agrees', 'why': 'x', 'text': 'تختص الجهة التجريبية بالأمر.', 'article_refs': ['المادة 4']}
    assert pa.validate(body, t) is not None
    assert pa.validate(dict(body, article_refs=['المادة 7']), t) is None, 'رد المراجِع مش مصدر مراجع'
    assert pa.validate(dict(body, article_refs=[], text='تختص بالمادة 7.'), t) is None, 'رقم من رد المراجِع'
    assert pa.validate(dict(body, article_refs=[], text='السند المادة 4.'), t) is not None


def test_gather_skips_correction_already_approved(monkeypatch):
    import brain2.engine as eng

    class _Q(object):
        def filter(self, *a, **k): return self
        def first(self): return object()

    class _Item(object):
        producer = target_ref = status = type('C', (), {'in_': staticmethod(lambda x: True), '__eq__': lambda s, o: True})()
        query = _Q()

    monkeypatch.setattr(eng, '_models', lambda db: (_Item,))
    ctx = _ctx(_plat([_fb('f1')]))
    ctx.ns['db'] = object()
    assert pa.gather(ctx) == [], 'تصحيح معتمد قبل كده ⇒ لا بطاقة جديدة بعد نقاش'


def test_gather_skips_correction_already_rejected(monkeypatch):
    import brain2.engine as eng
    seen = {}

    class _Col(object):
        def __eq__(self, o): return True
        def in_(self, vals):
            seen['statuses'] = tuple(vals)
            return True

    class _Q(object):
        def filter(self, *a, **k): return self
        def first(self): return object()

    class _Item(object):
        producer = target_ref = _Col()
        status = _Col()
        query = _Q()

    monkeypatch.setattr(eng, '_models', lambda db: (_Item,))
    ctx = _ctx(_plat([_fb('f1')]))
    ctx.ns['db'] = object()
    assert pa.gather(ctx) == []
    assert 'rejected' in seen['statuses']
