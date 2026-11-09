# -*- coding: utf-8 -*-
"""«العقل» · بنود «جلسة تدريب البروف» `training_item` (2026-11-09).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_training.py

⛔ صفر شبكة وصفر ذكاء حقيقي: `_platform_proxy` و`_v2_write` بدائل محلية. النصوص تجريبية مش قانون حقيقي.
"""
import datetime
import json

import pytest

import app as appmod
from brain2 import producers_training as pt, registry
from brain2.contract import Ctx, SourceDown, Target

UTC = datetime.timezone.utc
AP = 'eg-administrative-prosecution'


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def no_net(*a, **k):
        raise AssertionError('شبكة حقيقية ممنوعة')
    for n in ('post', 'get', 'request'):
        monkeypatch.setattr(appmod.requests, n, no_net)


class FakePlatform(object):
    def __init__(self, routes=None):
        self.routes, self.calls = routes or {}, []

    def __call__(self, method, path, params=None, json_body=None, timeout=12):
        self.calls.append({'method': method, 'path': path, 'params': params})
        r = self.routes.get((method, path))
        if r is None:
            return {'error': 'Not Found'}, 404
        if isinstance(r, Exception):
            raise r
        return r[1], r[0]


def _item(iid='t1', **kw):
    d = {'id': iid, 'session_id': 's1', 'expert_name': 'أ. فلان', 'specialty': AP, 'specialty_label': 'النيابة الإدارية',
         'type': 'qa', 'question': 'هل تختص الجهة التجريبية بالتحقيق؟', 'answer': 'نعم تختص طبقًا للمادة 4.',
         'source': 'ق 999/2099', 'topic': '', 'status': 'pending', 'created_at': '2026-11-09'}
    d.update(kw)
    return d


def _ctx(plat, write=None):
    ns = {'_platform_proxy': plat, '_v2_write': write or (lambda *a: ({'ok': True}, 200)),
          '_resp_ok': lambda r: isinstance(r, tuple) and r[1] == 200,
          '_proxy_json': lambda r: r[0] if isinstance(r, tuple) else {}}
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor='admin@test')


def _plat(items, arts=None):
    return FakePlatform({
        ('GET', '/api/bridge/training/items'): (200, {'items': items}),
        ('GET', '/api/bridge/ask/articles/search'): (200, {'items': arts if arts is not None else [
            {'ref': '[ق 999/2099 م 4]', 'text': 'تختص الجهة التجريبية بالتحقيق.'}]}),
    })


def _target(with_articles=True, track=AP):
    facts = {'expert_name': 'أ. فلان', 'specialty_label': 'النيابة الإدارية', 'type': 'qa', 'question': 'س؟',
             'expert_answer': 'نعم تختص طبقًا للمادة 4.', 'source': 'ق 999/2099'}
    if with_articles:
        facts['articles'] = [{'ref': '[ق 999/2099 م 4]', 'text': 'تختص الجهة التجريبية.'}]
    return Target(ref='trainitem:t1', label='x', facts=facts, meta={'item_id': 't1', 'track': track})


def test_registered_locked_to_ask_and_telegram_default_only():
    p = registry.by_id('training_item')
    assert p is not None and p.default_mode == 'ask' and p.may_run_alone is False
    assert p.section == 'home' and p.kind == 'draft' and p.per_run_cap == 5 and callable(p.on_reject)
    assert p.approve_label == 'اعتمدها للبروف'
    assert 'training_item' in registry.TELEGRAM_DEFAULT_ON and 'training_item' not in registry.TELEGRAM_OK


def test_gather_builds_facts_attaches_articles_and_skips_bad():
    plat = _plat([_item('t1'), _item('bad id!'), _item('t3', answer=''), _item('t4', specialty='other')])
    out = pt.gather(_ctx(plat))
    assert [t.ref for t in out] == ['trainitem:t1', 'trainitem:t4']
    assert plat.calls[0]['params'] == {'status': 'pending', 'limit': 50}
    f = out[0].facts
    assert f['expert_name'] == 'أ. فلان' and f['articles'][0]['ref'] == '[ق 999/2099 م 4]'
    assert out[0].meta == {'item_id': 't1', 'track': AP}
    assert 'articles' not in out[1].facts and out[1].meta['track'] == ''
    assert sum(1 for c in plat.calls if 'articles' in c['path']) == 1


def test_gather_fits_byte_cap():
    arts = [{'ref': '[ق 999/2099 م %d]' % i, 'text': 'نص ' * 400} for i in (1, 2, 3)]
    out = pt.gather(_ctx(_plat([_item('t1', answer='كلام ' * 1000, question='سؤال ' * 300)], arts)))
    assert len(json.dumps(out[0].facts, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= pt.FACTS_MAX_BYTES


def test_gather_404_nothing_and_5xx_source_down():
    assert pt.gather(_ctx(FakePlatform())) == []
    with pytest.raises(SourceDown):
        pt.gather(_ctx(FakePlatform({('GET', '/api/bridge/training/items'): (500, {})})))


def test_validate_builds_arabic_card_and_verdict_rules():
    t = _target()
    ok = pt.validate({'verdict': 'agrees', 'article_refs': ['ق 999/2099'], 'note_ar': 'تطابق المادة 4.'}, t)
    assert ok['verdict'] == 'agrees' and ok['why'] == 'بتتفق مع النص'
    lines = ok['text'].split('\n')
    assert lines[0] == 'من جلسة تدريب: أ. فلان، النيابة الإدارية'
    assert 'جواب الخبير: نعم تختص طبقًا للمادة 4.' in lines and 'المصدر: ق 999/2099' in lines
    assert lines[-1].startswith('بتتفق مع النص')
    assert pt.validate({'verdict': 'contradicts', 'article_refs': []}, t)['text'].split('\n')[-1] == 'بتخالف النص'
    # مرجع مش من كلام الخبير ولا المواد
    assert pt.validate({'verdict': 'agrees', 'article_refs': ['المادة 9']}, t) is None
    assert pt.validate({'verdict': 'agrees', 'article_refs': ['[ق 999/2099 م 4]']}, t) is not None
    # حكم من غير مواد
    assert pt.validate({'verdict': 'agrees', 'article_refs': []}, _target(False)) is None
    assert pt.validate({'verdict': 'no_text', 'article_refs': []}, _target(False))['text'].endswith('مفيش نص يحسم')
    assert pt.validate({'verdict': 'maybe'}, t) is None
    # رقم مخترع في الملاحظة
    assert pt.validate({'verdict': 'agrees', 'article_refs': [], 'note_ar': 'المادة 77'}, t) is None
    assert pt.validate('x', t) is None


def test_template_shows_item_as_is_with_no_text():
    b = pt.template(_target())
    assert b['verdict'] == 'no_text' and 'جواب الخبير: نعم تختص' in b['text'] and b['text'].endswith('مفيش نص يحسم')
    assert pt.template(Target(ref='r', label='l', facts={}, meta={})) is None


def test_prompt_carries_facts():
    system, user = pt.prompt(_target())
    assert 'نعم تختص' in user and 'verdict' in system


def test_apply_accepts_with_track_only_for_that_specialty():
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append((method, path, body, action, target))
        return ({'status': 'accepted', 'correction_written': True}, 200)

    assert pt.apply(_ctx(FakePlatform(), write), {}, _target()).ok
    m, path, body, action, tgt = seen[0]
    assert (m, path, action, tgt) == ('POST', '/api/bridge/training/items/t1/decision', 'training.item_accept', 't1')
    assert body == {'decision': 'accept', 'track': AP, 'by': 'admin@test'}
    pt.apply(_ctx(FakePlatform(), write), {}, _target(track=''))
    assert seen[1][2] == {'decision': 'accept', 'by': 'admin@test'}


def test_apply_failures():
    assert pt.apply(_ctx(FakePlatform()), {}, Target(ref='x', label='x', facts={}, meta={})).ok is False
    res = pt.apply(_ctx(FakePlatform(), lambda *a: ({'error': 'مقرر قبل كده'}, 409)), {}, _target())
    assert res.ok is False and res.error == 'مقرر قبل كده'
    res = pt.apply(_ctx(FakePlatform(), lambda *a: ({'no_reply': True}, 502)), {}, _target())
    assert res.ok is False and res.no_reply is True


def test_on_reject_posts_reason_with_default_for_short():
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append((path, body, action))
        return ({'status': 'rejected'}, 200)

    assert pt.on_reject(_ctx(FakePlatform(), write), _target(), 'الجواب مش دقيق.').ok
    assert pt.on_reject(_ctx(FakePlatform(), write), _target(), ' x ').ok
    path, body, action = seen[0]
    assert path.endswith('/t1/decision') and action == 'training.item_reject'
    assert body == {'decision': 'reject', 'reason': 'الجواب مش دقيق.', 'by': 'admin@test'}
    assert seen[1][1]['reason'] == pt.DEFAULT_REJECT_REASON, 'المنصة بتشترط ٣ حروف'
    assert pt.on_reject(_ctx(FakePlatform(), lambda *a: ({'error': 'x'}, 500)), _target(), 'سبب').ok is False
