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
from test_brain2_routes import api, rows, ADMIN   # noqa: F401
from test_brain2_engine import env   # noqa: F401

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
    assert p.section == 'content' and p.kind == 'draft' and p.per_run_cap == 5 and callable(p.on_reject)
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


# ------------------------------------------------------------------ مراجعة التحقق (2026-11-09)

def test_long_question_and_answer_card_fits_draft_limit():
    from brain2.engine import check_body
    f = {'expert_name': 'أ. ' + 'ن' * 80, 'specialty_label': 'ت' * 80, 'type': 'qa', 'question': 'س' * 300,
         'expert_answer': 'ج' * 700, 'source': 'م' * 300}
    t = Target(ref='trainitem:t1', label='x', facts=f, meta={'item_id': 't1', 'track': AP})
    tpl = pt.template(t)
    assert len(tpl['text']) <= 900 and check_body(tpl, f, 'draft') is None
    assert '…' in tpl['text'] and len(f['question']) == 300 and len(f['expert_answer']) == 700, 'الكامل يبقى في facts'
    b = pt.validate({'verdict': 'no_text', 'article_refs': [], 'note_ar': 'ن' * 200}, t)
    assert len(b['text']) <= 900 and check_body(b, f, 'draft') is None
    assert 'س' * 149 + '…' in b['text'] and 'س' * 150 not in b['text']


def test_training_is_not_text_editable_and_route_refuses_edited_text(api, monkeypatch):
    from brain2.contract import Producer
    from test_brain2_engine import use
    import brain2.engine as eng
    assert registry.by_id('training_item').text_editable is False
    t = Target(ref='trainitem:t1', label='x', facts={'question': 'س'}, meta={'item_id': 't1'})
    prod = Producer(id='training_item', section='home', kind='draft', label='l', sentence='s', lock_reason='r',
                    may_run_alone=False, default_mode='ask', per_run_cap=5, gather=lambda c: [t],
                    prompt=lambda x: ('', 'u'), validate=lambda d, x: {'text': 'بند'},
                    apply=lambda c, b, x: pytest.fail('ما يتنفذش'), text_editable=False, tag='t', approve_label='ok')
    use(monkeypatch, prod)
    assert eng.start_run(appmod.__dict__, 'admin', ADMIN)[0] == 202
    (r,) = rows()
    resp = api.post('/api/v2/brain/items/%s/approve' % r.id, {'confirmed': True, 'text': 'نص معدّل'})
    assert resp.status_code == 400 and 'لا يُعدَّل' in resp.get_json()['error']
    assert rows()[0].status == 'proposed'
    item = api.get('/api/v2/brain/items?status=proposed').get_json()['items'][0]
    assert item['text_editable'] is False


def test_gather_skips_decided_training_items_and_retries_failed_reject(api, monkeypatch):
    import brain2.engine as eng
    from brain2.contract import Producer
    from test_brain2_engine import use
    from brain2.contract import ApplyResult
    t = Target(ref='trainitem:t1', label='x', facts={'question': 'س', 'expert_answer': 'ج'}, meta={'item_id': 't1'})
    prod = Producer(id='training_item', section='home', kind='draft', label='l', sentence='s', lock_reason='r',
                    may_run_alone=False, default_mode='ask', per_run_cap=5, gather=lambda c: [t],
                    prompt=lambda x: ('', 'u'), validate=lambda d, x: {'text': 'بند'},
                    apply=lambda c, b, x: ApplyResult(ok=True),
                    on_reject=lambda c, tt, r: ApplyResult(ok=False, error='x'), tag='t', approve_label='ok')
    use(monkeypatch, prod)
    assert eng.start_run(appmod.__dict__, 'admin', ADMIN)[0] == 202
    (r,) = rows()
    j = api.post('/api/v2/brain/items/%s/reject' % r.id, {'confirmed': True}).get_json()
    assert j['notified'] is False and rows()[0].last_error == 'notify_failed'
    seen = []
    ns = dict(appmod.__dict__)
    ns.update({'_platform_proxy': _plat([_item('t1')]), '_resp_ok': lambda r_: r_[1] == 200,
               '_proxy_json': lambda r_: r_[0],
               '_v2_write': lambda m, p, b, a, tg, meta: (seen.append(b), ({'ok': True}, 200))[1]})
    ctx = Ctx(ns=ns, now=datetime.datetime.now(UTC), actor='admin@test')
    assert pt.gather(ctx) == []
    assert len(seen) == 1 and seen[0]['decision'] == 'reject'
    assert rows()[0].last_error is None
    eng._models(appmod.db)[0].query.delete()
    appmod.db.session.commit()
    assert len(pt.gather(ctx)) == 1
