# -*- coding: utf-8 -*-
"""«العقل» · مواضيع خبراء من تصحيحات «اسأل» `ask_topic` (2026-11-09).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_ask_topic.py

⛔ صفر شبكة وصفر ذكاء حقيقي. الصفوف المحلية تُكتب في قاعدة الاختبار، و`_v2_write` بديل محلي.
"""
import datetime
import json
import uuid

import pytest

import app as appmod
from brain2 import engine as eng, producers_topics_from_ask as pt, registry
from brain2.contract import Ctx, Target
from test_brain2_engine import env   # noqa: F401

UTC = datetime.timezone.utc
TITLE = 'هل يجوز للجهة الإدارية توقيع جزاء على موظف قبل سماع أقواله؟'
QUESTION = 'تناقش المسألة حدود سلطة الجهة الإدارية في توقيع الجزاء التأديبي على موظف قبل التحقيق معه وسماع دفاعه.'


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    def no_net(*a, **k):
        raise AssertionError('شبكة حقيقية ممنوعة')
    for n in ('post', 'get', 'request'):
        monkeypatch.setattr(appmod.requests, n, no_net)


def _ctx(write=None):
    ns = dict(appmod.__dict__)
    ns.update({'_v2_write': write or (lambda *a: ({'ok': True, 'created': [{'title': 'x'}], 'skipped': []}, 200)),
               '_resp_ok': lambda r: isinstance(r, tuple) and r[1] == 200,
               '_proxy_json': lambda r: r[0] if isinstance(r, tuple) else {}})
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor='admin@test')


def _add(producer, ref, status='approved', verdict='no_text', source='ai', facts=None, meta=None, h=None):
    Item = eng._models(appmod.db)[0]
    row = Item(id=uuid.uuid4().hex, producer=producer, section='home', kind='draft', target_ref=ref,
               target_label='x', input_hash=h or uuid.uuid4().hex, facts_json=json.dumps(facts or {}, ensure_ascii=False),
               meta_json=json.dumps(meta or {}), body_json=json.dumps({'text': 't', 'verdict': verdict}),
               status=status, source=source, mode='ask', created_at=datetime.datetime.utcnow())
    appmod.db.session.add(row)
    appmod.db.session.commit()
    return row


def _corr(fid, **kw):
    kw.setdefault('facts', {'question': 'سؤال المستخدم الخاص', 'correction': 'تصحيح المستخدم الخاص'})
    kw.setdefault('meta', {'feedback_id': fid, 'track': 'eg-administrative-prosecution'})
    return _add('ask_correction', 'askfb:' + fid, **kw)


def test_registered_ask_locked_and_telegram_default_only():
    p = registry.by_id('ask_topic')
    assert p.default_mode == 'ask' and p.may_run_alone is False and p.per_run_cap == 3 and p.kind == 'draft'
    assert p.section == 'home' and p.template is None and p.approve_label == 'انشره موضوع للخبراء'
    assert 'ask_topic' in registry.TELEGRAM_DEFAULT_ON and 'ask_topic' not in registry.TELEGRAM_OK


def test_gather_only_no_text_ai_and_all_decision_statuses(env):
    _corr('a1', status='approved')
    _corr('a2', status='rejected')
    _corr('a3', status='proposed')
    _corr('a4', status='edited')
    _corr('ag', verdict='agrees')
    _corr('ct', verdict='contradicts')
    _corr('tp', source='template')
    _corr('ex', status='expired')
    _corr('fl', status='failed')
    got = pt.gather(_ctx())
    assert sorted(t.ref for t in got) == ['asktopic:a1', 'asktopic:a2', 'asktopic:a3', 'asktopic:a4']
    assert got[0].facts == {'question': 'سؤال المستخدم الخاص', 'correction': 'تصحيح المستخدم الخاص'}


def test_gather_dedupes_per_feedback_and_skips_existing_topic_cards(env):
    _corr('d1', h='h1')
    _corr('d1', h='h2')           # نفس التصحيح بنقاش جديد
    _corr('d2')
    _corr('d3')
    _add('ask_topic', 'asktopic:d2', status='rejected')
    _add('ask_topic', 'asktopic:d3', status='failed')     # الفاشل يُعاد بعد يوم
    refs = sorted(t.ref for t in pt.gather(_ctx()))
    assert refs == ['asktopic:d1', 'asktopic:d3']


def test_gather_includes_training_no_text(env):
    _add('training_item', 'trainitem:i9', facts={'question': 'س تدريب', 'expert_answer': 'جواب خبير'},
         meta={'item_id': 'i9', 'track': ''})
    _add('training_item', 'trainitem:i8', verdict='agrees', facts={'question': 's', 'expert_answer': 'a'},
         meta={'item_id': 'i8'})
    (t,) = pt.gather(_ctx())
    assert t.ref == 'asktopic:t-i9' and t.facts['correction'] == 'جواب خبير'


def test_gather_skips_rows_without_ids_or_text(env):
    _corr('', facts={'question': 'q', 'correction': 'c'}, meta={'feedback_id': ''})
    _corr('e1', facts={'question': '', 'correction': 'c'})
    assert pt.gather(_ctx()) == []


@pytest.mark.parametrize('title,question', [
    ('هل يجوز فصل موظف في ٢٠٢٥ دون تحقيق؟', QUESTION),                       # رقم عربي
    ('هل يجوز فصل موظف في 2025 دون تحقيق؟', QUESTION),                        # رقم لاتيني
    (TITLE, QUESTION + ' وفق المادة ٤ فقط.'),                                  # رقم في السؤال
    ('هل يجوز فصل موظف according للقانون؟', QUESTION),                        # لاتيني
    ('هل يجوز لي فصل موظف أنا دون تحقيق معه؟', QUESTION),                      # علامة شخصية
    (TITLE, 'ابني موظف في جهة إدارية وتم جزاؤه قبل سماع أقواله، فما الحكم في ذلك؟'),
    (TITLE, 'تناقش المسألة سلطة جهة إدارية. راجع http بالرابط للتفاصيل الكاملة.'),
    ('قصير', QUESTION),
    (TITLE, 'قصير'),
    ('ع' * 91, QUESTION),
    (TITLE, 'ع' * 401),
])
def test_validate_rejects_unsafe_or_bad_lengths(title, question):
    raw = {'title_ar': title, 'question_ar': question, 'why_ar': 'مسألة خلافية'}
    assert pt.validate(raw, Target(ref='asktopic:x', label='x', facts={})) is None


def test_validate_accepts_clean_and_shapes_body():
    b = pt.validate({'title_ar': TITLE, 'question_ar': QUESTION, 'why_ar': 'مسألة خلافية تحتاج رأي خبير'},
                    Target(ref='asktopic:x', label='x', facts={}))
    assert b['text'] == TITLE + '\n' + QUESTION and b['approve_label'] == 'انشره موضوع للخبراء'
    assert b['why'].startswith('من تصحيح على إجابة اسأل مفيش نص بيحسمه') and len(b['why']) <= 160
    assert eng.check_body(b, {}, 'draft') is None
    assert pt.validate('x', Target(ref='r', label='x', facts={})) is None
    # سبب غير آمن ⇒ يسقط السبب بس، البطاقة تفضل
    b2 = pt.validate({'title_ar': TITLE, 'question_ar': QUESTION, 'why_ar': 'سنة 2025'}, Target(ref='r', label='x', facts={}))
    assert b2['why'] == pt.FOOTER


def test_prompt_has_facts_and_no_template():
    t = Target(ref='asktopic:x', label='x', facts={'question': 'سؤال', 'correction': 'تصحيح'})
    system, user = pt.prompt(t)
    assert 'title_ar' in system and 'تصحيح' in user
    assert pt.PRODUCERS[0].template is None


def test_apply_payload_shape_and_created_line():
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append((method, path, body, action))
        return ({'ok': True, 'created': [{'title': TITLE}], 'skipped': []}, 200)
    res = pt.apply(_ctx(write), {'text': TITLE + '\n' + QUESTION}, Target(ref='asktopic:f1', label='x', facts={},
                                                                         meta={'source_id': 'f1'}))
    assert res.ok and res.info['line'] == 'اتنشر موضوع'
    (m, path, body, action), = seen
    assert (m, path, action) == ('POST', '/api/bridge/topics/seed', 'ask.topic_seed')
    assert body == {'items': [{'title': TITLE, 'question': QUESTION}], 'apply': True}
    assert 'f1' not in json.dumps(body)       # لا معرّف تصحيح ولا أي شيء شخصي للجسر العام


def test_apply_skipped_line_and_failures():
    t = Target(ref='asktopic:f1', label='x', facts={})
    body = {'text': TITLE + '\n' + QUESTION}
    r = pt.apply(_ctx(lambda *a: ({'ok': True, 'created': [], 'skipped': [{'title': TITLE}]}, 200)), body, t)
    assert r.ok and r.info['line'] == 'الموضوع موجود قبل كده'
    r = pt.apply(_ctx(lambda *a: ({'ok': True, 'created': [], 'skipped': []}, 200)), body, t)
    assert not r.ok and r.no_reply
    r = pt.apply(_ctx(lambda *a: ({'error': 'مشغول'}, 422)), body, t)
    assert not r.ok and r.error == 'مشغول' and not r.no_reply
    r = pt.apply(_ctx(lambda *a: ({'error': 'x', 'no_reply': True}, 502)), body, t)
    assert not r.ok and r.no_reply


def test_apply_sends_edited_text_and_revalidates_it():
    seen = []
    ctx = _ctx(lambda m, p, b, a, tg, meta: (seen.append(b), ({'created': [1]}, 200))[1])
    t = Target(ref='asktopic:f1', label='x', facts={})
    edited_title = 'ما حكم توقيع الجزاء على موظف دون تمكينه من الدفاع؟'
    edited = edited_title + '\nسطر أول من السؤال المعدل\nوسطر ثان من نفس السؤال بعد التعديل.'
    assert pt.apply(ctx, {'text': edited}, t).ok
    assert seen[0]['items'][0] == {'title': edited_title,
                                   'question': 'سطر أول من السؤال المعدل وسطر ثان من نفس السؤال بعد التعديل.'}
    for bad in (TITLE, TITLE + '\nسؤال فيه رقم ٥ ورقم آخر هنا في الجملة', 'عنوان فيه ABC كلام كثير يكفي\n' + QUESTION,
                'هل يجوز لي هذا العنوان الطويل كفاية؟\n' + QUESTION):
        n = len(seen)
        r = pt.apply(ctx, {'text': bad}, t)
        assert not r.ok and len(seen) == n


def test_end_to_end_run_stores_card_from_model_json(env, monkeypatch):
    _corr('z1')
    monkeypatch.setattr(registry, 'PRODUCERS', [pt.PRODUCERS[0]])
    ns = appmod.__dict__
    monkeypatch.setitem(ns, 'ai_call', lambda system, user, purpose='': json.dumps(
        {'title_ar': TITLE, 'question_ar': QUESTION, 'why_ar': 'مسألة خلافية'}, ensure_ascii=False))
    (t,) = pt.gather(_ctx())
    assert eng.process_target(ns, pt.PRODUCERS[0], t, eng._new_state()) == 'ai'
    Item = eng._models(appmod.db)[0]
    (row,) = Item.query.filter_by(producer='ask_topic').all()
    body = json.loads(row.body_json)
    assert row.status == 'proposed' and row.source == 'ai' and row.target_ref == 'asktopic:z1'
    assert body['text'] == TITLE + '\n' + QUESTION
    assert pt.gather(_ctx()) == []        # بعد وجود البطاقة ما يتولدش تاني
