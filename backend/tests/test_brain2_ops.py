# -*- coding: utf-8 -*-
"""العقل ٢ · منتجو الـops (opinion + reply_draft). SPEC: docs/v2/brain2/SPEC.md §3.2 / §5 P2.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_ops.py

⛔ صفر شبكة حقيقية وصفر ذكاء: `_platform_proxy` بديل محلي يسجّل النداءات؛ `requests.*` يرمي.
"""
import datetime
import json
import re

import pytest

import app as appmod
from app import app as flask_app, db, Message
from brain2 import producers_ops as ops
from brain2.contract import ApplyResult, Ctx, SourceDown, Target

UTC = datetime.timezone.utc
EMAIL_RE = re.compile(r'[\w.+\-]+@[\w\-]+\.[\w.\-]+')
PHONE_RE = re.compile(r'\d{7,}')


def _no_net(*a, **k):
    raise AssertionError('شبكة حقيقية ممنوعة')


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    monkeypatch.setattr(appmod.requests, 'post', _no_net)
    monkeypatch.setattr(appmod.requests, 'get', _no_net)
    monkeypatch.setattr(appmod.requests, 'request', _no_net)


@pytest.fixture
def app_ctx():
    with flask_app.app_context():
        db.create_all()
        Message.query.delete()
        db.session.commit()
        yield
        db.session.rollback()


class FakePlatform(object):
    """بديل `_platform_proxy`: يرد (dict, status). `routes[(method, path)]` = (status, body) أو استثناء."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def __call__(self, method, path, params=None, json_body=None, timeout=12):
        self.calls.append({'method': method, 'path': path, 'params': params, 'json': json_body})
        r = self.routes.get((method, path))
        if r is None:
            return {'error': 'تعذر تنفيذ العملية'}, 404
        if isinstance(r, Exception):
            raise r
        return r[1], r[0]

    def paths(self, method=None):
        return [c['path'] for c in self.calls if method is None or c['method'] == method]


MSGS = {'messages': [
    {'id': 'pm-1', 'from_name': 'ليلى أحمد', 'from_email': 'layla.a@example.test', 'subject': 'سؤال عن الملف',
     'body': 'أرسلت ملفي أمس وراسلوني على layla.a@example.test أو اتصلوا على +201098765432 لو سمحتم', 'contact_phone': '+201098765432'},
    {'id': 'pm-2', 'from_name': '', 'from_email': '', 'subject': '', 'body': 'هل الدورات متاحة بلغات أخرى؟', 'contact_phone': '+971501234567'},
    {'id': 'pm-3', 'from_name': 'x', 'from_email': 'x@x.test', 'subject': 's', 'body': ''},   # بلا نص ⇒ يُهمل
]}
LEADS = {'leads': [
    {'id': 'ld-1', 'full_name': 'سلمى منصور', 'phone': '+201555000111', 'experience': 'محامية منذ خمس سنوات',
     'want': 'استشارة مستعجلة، رقمي 0100 123 4567', 'from_email': 'salma.m@example.test'},
]}


def _plat(msgs=True, leads=True):
    p = FakePlatform()
    if msgs:
        p.routes[('GET', '/api/bridge/messages')] = (200, MSGS)
    if leads:
        p.routes[('GET', '/api/bridge/leads')] = (200, LEADS)
    return p


def _ctx(plat, audit=None, actor='admin@x.test'):
    ns = {'_platform_proxy': plat, '_resp_ok': appmod._resp_ok, '_audit': audit or (lambda *a, **k: None),
          'Message': Message, 'db': db}
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor=actor)


def _seed_msg(**kw):
    m = Message(name=kw.get('name', 'زائر'), email=kw.get('email', 'visitor@example.test'), phone=kw.get('phone', '+201000000000'),
                topic=kw.get('topic', 'استفسار'), body=kw.get('body', 'أريد معرفة الأسعار. بريدي visitor@example.test'),
                status=kw.get('status', 'new'))
    db.session.add(m)
    db.session.commit()
    return m


def _prod(pid):
    return next(p for p in ops.PRODUCERS if p.id == pid)


# ---------------------------------------------------------------- تعريف المنتجين

def test_producer_definitions():
    o, r = _prod('opinion'), _prod('reply_draft')
    assert (o.section, o.kind, o.may_run_alone, o.default_mode, o.lock_reason, o.template, o.apply) == \
           ('home', 'opinion', True, 'alone', '', None, None)
    assert o.label == 'رأي العقل في كل قرار'
    assert o.sentence == 'عندما يظهر قرار ينتظرك، يكتب العقل رأيه فيه من بيانات البطاقة نفسها.'
    assert (r.section, r.kind, r.may_run_alone, r.default_mode, r.per_run_cap) == ('people', 'draft', False, 'ask', 6)
    assert r.label == 'مسودات الرد على الرسائل'
    assert r.lock_reason == 'يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.'
    assert r.approve_label == 'أرسل الرد' and r.template is None and callable(r.apply)
    assert 'يقوّم' not in r.sentence + o.sentence + r.label + o.label


def test_registry_loads_ops():
    from brain2 import registry
    assert {'opinion', 'reply_draft'} <= {p.id for p in registry.PRODUCERS}


# ---------------------------------------------------------------- opinion

def test_opinion_specs_groups():
    for k in ops.MONEY_KINDS:
        assert ops.OPINION_SPECS[k]['allowed_recommend'] == ()
    for k in ops.DECISION_KINDS:
        assert ops.OPINION_SPECS[k]['allowed_recommend'] == ('approve', 'reject', 'open')
    for k in ops.INFO_KINDS:
        assert ops.OPINION_SPECS[k]['allowed_recommend'] == ('open', 'wait')
    for k in ('file_waiting', 'file_late'):
        assert k not in ops.OPINION_SPECS and not ops.opinion_supported(k)
    assert len(ops.OPINION_SPECS) == 7 + 8 + 9
    assert ops.OPINION_SPECS['dispute']['role_ar'] == 'لخّص الطرفين بإنصاف ثم أوصِ'


def test_opinion_keys_per_kind():
    common = set(ops.OPINION_COMMON_KEYS)
    assert common == {'tag', 'age', 'sub', 'warn', 'reason', 'static_line', 'facts', 'money_text'}
    extra = {'dispute': {'objection', 'expert_reply', 'hours_held'}, 'trainer': {'headline', 'specialty', 'years', 'attachments'},
             'payout': {'method', 'dispute_check', 'fx_alert'}, 'book_offer': {'type', 'suggested_price', 'price_note'},
             'join': {'service', 'licensed', 'licence_missing'}, 'lead': {'body', 'topic'}, 'message': {'body', 'topic'}}
    for k, spec in ops.OPINION_SPECS.items():
        assert set(spec['keys']) == common | extra.get(k, set()), k


def test_opinion_target_cleans_facts():
    t = ops.opinion_target('payout', 'payout|p1|', {
        'tag': 'تحويل أرباح', 'money_text': '٦٠٠٫٥ جنيه', 'method': 'فودافون كاش',
        'reason': 'اتصل على 01001234567 أو a@b.com', 'email': 'a@b.com', 'secret': 'x', 'body': 'ليس لهذا النوع',
        'facts': [{'k': 'المبلغ', 'v': '600'}] + [{'k': str(i), 'v': 'v'} for i in range(9)], 'warn': 'ا' * 900})
    assert isinstance(t, Target) and t.ref == 'card:payout|p1|' and t.meta['kind'] == 'payout'
    assert set(t.facts) <= set(ops.OPINION_SPECS['payout']['keys'])
    assert 'email' not in t.facts and 'secret' not in t.facts and 'body' not in t.facts
    blob = json.dumps(t.facts, ensure_ascii=False)
    assert not EMAIL_RE.search(blob) and not PHONE_RE.search(blob)
    assert len(t.facts['facts']) == 6 and len(t.facts['warn']) == 300


def test_opinion_target_unsupported_and_label():
    with pytest.raises(ValueError):
        ops.opinion_target('file_waiting', 'file_waiting|1|', {})
    with pytest.raises(ValueError):
        ops.opinion_target('nope', 'x', {})
    t = ops.opinion_target('trainer', 'trainer|9|r', {'tag': 'مدرّب جديد'})
    assert t.label == 'مدرّب جديد' and len(t.label) <= 120
    assert len(ops.opinion_target('trainer', 'x' * 400, {}).ref) <= 200


def test_opinion_gather_returns_empty():
    assert _prod('opinion').gather(_ctx(FakePlatform())) == []


def test_opinion_prompt_no_email_phone_meta():
    t = ops.opinion_target('lead', 'lead|7|', {'tag': 'عميل محتمل', 'body': 'أريد استشارة', 'topic': 'نفقة'})
    t.meta['email'] = 'secret@x.test'
    t.facts['body'] = 'راسلني على z@z.test أو 01234567890'   # حتى لو تسرّب إلى الحقائق
    system, user = _prod('opinion').prompt(t)
    assert 'secret@x.test' not in system + user and not EMAIL_RE.search(system + user) and not PHONE_RE.search(system + user)
    assert 'open|wait' in system and 'approve' not in system.split('الشكل المطلوب')[1].split('\n')[0]
    assert 'meta' not in user and 'card_id' not in user
    sd, ud = _prod('opinion').prompt(ops.opinion_target('dispute', 'dispute|1|', {'objection': 'تأخر الرأي', 'expert_reply': 'سلمت في موعدي'}))
    assert 'لخّص الطرفين بإنصاف ثم أوصِ' in sd and 'تأخر الرأي' in ud and 'سلمت في موعدي' in ud
    pm = _prod('opinion').prompt(ops.opinion_target('payout', 'payout|1|', {'money_text': '600'}))[0]
    assert '"recommend":""' in pm


def test_opinion_validate_money_text_only():
    v = _prod('opinion').validate
    t = ops.opinion_target('payout', 'payout|1|', {})
    ok = v({'opinion': 'راجع الوجهة قبل التحويل', 'recommend': '', 'why': 'المبلغ كبير'}, t)
    assert ok == {'text': 'راجع الوجهة قبل التحويل', 'opinion': 'راجع الوجهة قبل التحويل', 'recommend': '', 'why': 'المبلغ كبير'}
    # الأموال لا تُحوَّل إلى زر: أي recommend يُسقَط
    assert v({'opinion': 'ا', 'recommend': 'approve', 'why': 'ب'}, t)['recommend'] == ''
    assert v({'opinion': 'ا', 'why': 'ب'}, t)['recommend'] == ''


def test_opinion_validate_enums_and_shapes():
    v = _prod('opinion').validate
    dec = ops.opinion_target('trainer', 'trainer|1|', {})
    info = ops.opinion_target('message', 'message|1|', {})
    for rec in ('approve', 'reject', 'open'):
        assert v({'opinion': 'ا', 'recommend': rec, 'why': 'ب'}, dec)['recommend'] == rec
    assert v({'opinion': 'ا', 'recommend': 'wait', 'why': 'ب'}, dec) is None
    for rec in ('open', 'wait'):
        assert v({'opinion': 'ا', 'recommend': rec, 'why': 'ب'}, info)['recommend'] == rec
    for bad in ('approve', 'reject', '', None, 5, 'OPEN', ['open']):
        assert v({'opinion': 'ا', 'recommend': bad, 'why': 'ب'}, info) is None
    assert v({'opinion': 'ا', 'why': 'ب'}, dec) is None   # recommend ناقص في نوع قرار
    for bad in (None, [], 'x', 5, {}, {'opinion': 'ا'}, {'opinion': '', 'recommend': 'open', 'why': 'ب'},
                {'opinion': 'ا', 'recommend': 'open', 'why': ''}, {'opinion': 3, 'recommend': 'open', 'why': 'ب'},
                {'opinion': 'ا' * 221, 'recommend': 'open', 'why': 'ب'}, {'opinion': 'ا', 'recommend': 'open', 'why': 'ب' * 161}):
        assert v(bad, info) is None
    assert v({'opinion': 'ا' * 220, 'recommend': 'open', 'why': 'ب' * 160}, info) is not None
    # هدف بلا نوع مدعوم ⇒ لا يُقبل شيء
    assert v({'opinion': 'ا', 'recommend': 'open', 'why': 'ب'}, Target(ref='card:zzz|1', label='x', facts={})) is None


def test_opinion_kind_from_ref_when_meta_missing():
    t = ops.opinion_target('trainer', 'trainer|1|', {})
    t.meta = {}
    assert _prod('opinion').validate({'opinion': 'ا', 'recommend': 'reject', 'why': 'ب'}, t)['recommend'] == 'reject'


# ---------------------------------------------------------------- reply_draft · gather

def test_gather_builds_targets_from_all_sources(app_ctx):
    m = _seed_msg()
    p = _plat()
    ts = _prod('reply_draft').gather(_ctx(p))
    by = {t.ref: t for t in ts}
    assert set(by) == {'pmsg:pm-1', 'pmsg:pm-2', 'smsg:%d' % m.id, 'lead:ld-1'}   # pm-3 بلا نص
    assert [c['params'] for c in p.calls] == [{'status': 'new'}, {'status': 'new'}]
    assert [c['path'] for c in p.calls] == ['/api/bridge/messages', '/api/bridge/leads']
    a = by['pmsg:pm-1']
    assert set(a.facts) == {'subject', 'body', 'has_account'} and a.facts['has_account'] is True
    assert a.meta['id'] == 'pm-1' and a.meta['email'] == 'layla.a@example.test' and a.meta['approve_label'] == 'أرسل الرد'
    assert by['pmsg:pm-2'].facts['has_account'] is False and by['pmsg:pm-2'].meta['approve_label'] == 'انسخ الرد'
    s = by['smsg:%d' % m.id]
    assert s.meta['approve_label'] == 'أرسل الرد بالبريد' and s.facts['subject'] == 'استفسار'   # له بريد
    ld = by['lead:ld-1']
    assert set(ld.facts) == {'want', 'experience'} and ld.meta['phone'] == '+201555000111'
    assert ld.meta['approve_label'] == 'أرسل بالبريد'   # له بريد
    for t in ts:
        assert len(t.label) <= 120 and len(t.ref) <= 200 and len(t.facts['body'] if 'body' in t.facts else '') <= 1200
        blob = json.dumps(t.facts, ensure_ascii=False)
        assert not EMAIL_RE.search(blob) and not PHONE_RE.search(blob.replace('+', ''))
    assert last_errors() == []


def last_errors():
    return list(ops.last_source_errors)


def test_gather_body_limit_and_has_account_flag():
    p = FakePlatform()
    p.routes[('GET', '/api/bridge/messages')] = (200, {'messages': [
        {'id': 'm1', 'from_email': '', 'has_account': True, 'subject': 's', 'body': 'ب' * 3000}]})
    p.routes[('GET', '/api/bridge/leads')] = (200, {'leads': []})
    ctx = _ctx(p)
    ctx.ns['Message'] = None   # مصدر الموقع ينهار
    ts = _prod('reply_draft').gather(ctx)
    assert len(ts) == 1 and len(ts[0].facts['body']) == 1200 and ts[0].facts['has_account'] is True


def test_source_down_is_per_source(app_ctx):
    m = _seed_msg()
    # المنصة (رسائل) ساقطة، الباقي سليم
    p = _plat(msgs=False)
    p.routes[('GET', '/api/bridge/messages')] = (503, {'error': 'x'})
    ts = _prod('reply_draft').gather(_ctx(p))
    assert {t.ref for t in ts} == {'smsg:%d' % m.id, 'lead:ld-1'}
    assert [e['source'] for e in ops.last_source_errors] == ['pmsg']
    # الطلبات ساقطة بانقطاع
    p = _plat(leads=False)
    p.routes[('GET', '/api/bridge/leads')] = OSError('boom')
    ts = _prod('reply_draft').gather(_ctx(p))
    assert {t.ref.split(':')[0] for t in ts} == {'pmsg', 'smsg'}
    assert [e['source'] for e in ops.last_source_errors] == ['lead']
    # شكل رد فاسد
    p = _plat()
    p.routes[('GET', '/api/bridge/leads')] = (200, {'leads': 'oops'})
    _prod('reply_draft').gather(_ctx(p))
    assert [e['source'] for e in ops.last_source_errors] == ['lead']
    # الدالة النقية
    targets, errs = ops.gather_with_errors(_ctx(p))
    assert targets and [e['source'] for e in errs] == ['lead']


def test_source_down_when_all_fail(app_ctx):
    p = FakePlatform()
    ctx = _ctx(p)
    ctx.ns['Message'] = None
    with pytest.raises(SourceDown):
        _prod('reply_draft').gather(ctx)
    assert sorted(e['source'] for e in ops.last_source_errors) == ['lead', 'pmsg', 'smsg']


def test_empty_sources_are_not_errors(app_ctx):
    p = FakePlatform()
    p.routes[('GET', '/api/bridge/messages')] = (200, {'messages': []})
    p.routes[('GET', '/api/bridge/leads')] = (200, [])   # شكل قائمة مقبول
    assert _prod('reply_draft').gather(_ctx(p)) == []
    assert ops.last_source_errors == []


# ---------------------------------------------------------------- reply_draft · prompt

def test_prompt_has_no_email_phone_or_meta(app_ctx):
    _seed_msg()
    ts = _prod('reply_draft').gather(_ctx(_plat()))
    assert len(ts) == 4
    for t in ts:
        t.meta['secret_marker'] = 'ZZMETA'
        system, user = _prod('reply_draft').prompt(t)
        both = system + '\n' + user
        assert not EMAIL_RE.search(both) and not PHONE_RE.search(both.replace('+', ''))
        for leak in ('layla.a@example', 'visitor@example', 'salma.m@example', '+201098765432', '+201555000111', 'ZZMETA',
                     'approve_label', 'meta', t.ref):
            assert leak not in both, leak
        assert 'يقوّم' not in both and '"text"' in system
    # حتى لو وُضع بريد/هاتف في الحقائق نفسها يُحجب عند بناء الـprompt
    t = Target(ref='pmsg:z', label='x', facts={'subject': 'a@b.test', 'body': 'اتصل 00201234567890 او a@b.test', 'has_account': False})
    user = _prod('reply_draft').prompt(t)[1]
    assert '@' not in user and not PHONE_RE.search(user)


def test_prompt_lead_and_message_shapes():
    s, u = _prod('reply_draft').prompt(Target(ref='lead:1', label='x', facts={'want': 'عقد شركة', 'experience': 'خمس سنوات'}))
    assert 'عقد شركة' in u and 'خمس سنوات' in u and 'طلب تواصل' in u
    s, u = _prod('reply_draft').prompt(Target(ref='smsg:1', label='x', facts={'subject': 'الأسعار', 'body': 'كم السعر؟'}))
    assert 'الأسعار' in u and 'كم السعر؟' in u and 'زائر الموقع' in u
    assert 'بالبريد' in s   # قاعدة: لا تقل إن الرد أُرسل بالبريد


# ---------------------------------------------------------------- reply_draft · validate

def test_reply_validate():
    v = _prod('reply_draft').validate
    t = Target(ref='lead:1', label='x', facts={})
    assert v({'text': '  شكرًا لتواصلكم.  '}, t) == {'text': 'شكرًا لتواصلكم.'}
    assert v({'text': 'ا' * 700}, t) is not None
    assert v({'text': 'ا' * 701}, t) is None
    for bad in (None, [], 'نص', 5, {}, {'text': ''}, {'text': '   '}, {'text': 5}, {'text': None}, {'text': ['a']}, {'body': 'x'}):
        assert v(bad, t) is None
    assert v({'text': 'مرحبًا', 'extra': 'x'}, t) == {'text': 'مرحبًا'}   # الجسم نص فقط


# ---------------------------------------------------------------- reply_draft · apply

def _pm_target(has_account=True, mid='pm-1'):
    return Target(ref='pmsg:' + mid, label='x', facts={'subject': 's', 'body': 'b', 'has_account': has_account},
                  meta={'id': mid, 'email': 'layla.a@example.test' if has_account else ''})


def test_apply_member_sends_exact_path_and_body_and_audits():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (200, {'ok': True})
    audits = []
    ctx = _ctx(p, audit=lambda *a, **k: audits.append((a, k)), actor='boss@x.test')
    ctx.item_id = ITEM
    t = _pm_target()
    t.meta['email'] = ''      # بلا بريد معروف ⇒ الرد داخل المنصة وحده، ولا نداء بريد
    res = ops.PRODUCERS[1].apply(ctx, {'text': 'شكرًا لرسالتكم.'}, t)
    assert isinstance(res, ApplyResult) and res.ok and not res.no_reply and res.copy_text == ''
    assert p.calls == [{'method': 'POST', 'path': '/api/bridge/messages/pm-1/reply', 'params': None,
                        'json': {'body': 'شكرًا لرسالتكم.', 'by': 'boss@x.test', 'confirmed': True, 'idem_key': ITEM}}]
    assert audits == [(('brain.reply_send',), {'target': 'pm-1', 'meta': {'producer': 'reply_draft', 'ref': 'pmsg:pm-1'}, 'actor': 'boss@x.test'})]


def test_apply_member_visitor_422():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (422, {'error': 'no account'})
    audits = []
    res = _prod('reply_draft').apply(_ctx(p, audit=lambda *a, **k: audits.append(1)), {'text': 'رد'}, _pm_target())
    assert not res.ok and not res.no_reply and res.error and re.search(r'[؀-ۿ]', res.error)
    assert 'زائر' in res.error and res.copy_text == 'رد' and audits == []
    assert len(p.calls) == 1   # لا resolve


@pytest.mark.parametrize('outcome', [OSError('down'), (502, {'error': 'x'}), (504, {'error': 'x'})])
def test_apply_member_no_reply(outcome):
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = outcome
    audits = []
    res = _prod('reply_draft').apply(_ctx(p, audit=lambda *a, **k: audits.append(1)), {'text': 'رد'}, _pm_target())
    assert res.ok is False and res.no_reply is True and res.error and audits == []


def test_apply_member_definite_rejection_is_plain_error():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (400, {'error': 'x'})
    res = _prod('reply_draft').apply(_ctx(p), {'text': 'رد'}, _pm_target())
    assert res.ok is False and res.no_reply is False and res.error


@pytest.mark.parametrize('status', [500, 502, 503, 504, 599, 0])
def test_apply_member_any_5xx_or_timeout_is_no_reply_not_back_to_proposed(status):
    """لا نعرف إن وصل الرد ⇒ unknown (no_reply) لا «رُدّ إلى مقترح» فيُرسَل مرتين."""
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (status, {'error': 'x'})
    res = _prod('reply_draft').apply(_ctx(p), {'text': 'رد'}, _pm_target())
    assert res.ok is False and res.no_reply is True


def test_apply_member_raising_proxy_is_no_reply_and_sends_the_item_id_as_idem_key():
    p = FakePlatform()

    def boom(*a, **k):
        raise TimeoutError('t')
    ctx = _ctx(boom)
    ctx.item_id = ITEM
    assert _prod('reply_draft').apply(ctx, {'text': 'رد'}, _pm_target()).no_reply is True


def test_apply_visitor_without_account_is_copy_only_then_resolve():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-2/resolve')] = (200, {'ok': True})
    audits = []
    res = _prod('reply_draft').apply(_ctx(p, audit=lambda *a, **k: audits.append(1)), {'text': 'مرحبًا بك'}, _pm_target(False, 'pm-2'))
    assert res.ok and res.copy_text == 'مرحبًا بك'
    assert p.calls == [{'method': 'POST', 'path': '/api/bridge/messages/pm-2/resolve', 'params': None, 'json': None}]
    assert audits == []   # لا إرسال ⇒ لا brain.reply_send


def test_apply_visitor_resolve_failure():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-2/resolve')] = (500, {'error': 'x'})
    res = _prod('reply_draft').apply(_ctx(p), {'text': 'رد'}, _pm_target(False, 'pm-2'))
    assert not res.ok and res.copy_text == '' and res.error


def test_apply_lead_copy_and_resolve():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/leads/ld-1/resolve')] = (200, {'ok': True})
    t = Target(ref='lead:ld-1', label='x', facts={'want': 'w', 'experience': ''}, meta={'id': 'ld-1', 'phone': '+201'})
    res = _prod('reply_draft').apply(_ctx(p), {'text': 'مرحبًا سلمى'}, t)
    assert res.ok and res.copy_text == 'مرحبًا سلمى'
    assert [(c['method'], c['path'], c['json']) for c in p.calls] == [('POST', '/api/bridge/leads/ld-1/resolve', None)]
    p2 = FakePlatform()
    p2.routes[('POST', '/api/bridge/leads/ld-1/resolve')] = (502, {'error': 'x'})
    r2 = _prod('reply_draft').apply(_ctx(p2), {'text': 'مرحبًا'}, t)
    assert not r2.ok and r2.error and r2.copy_text == ''


def test_apply_site_message_same_writes_as_admin_reply_no_network(app_ctx):
    m = _seed_msg(email='')          # بلا بريد ⇒ النسخ فقط، ولا أي نداء
    p = FakePlatform()
    t = Target(ref='smsg:%d' % m.id, label='x', facts={'subject': 's', 'body': 'b'}, meta={'id': m.id, 'email': ''})
    before = datetime.datetime.utcnow()
    res = _prod('reply_draft').apply(_ctx(p), {'text': 'شكرًا، سنوافيكم بالتفاصيل.'}, t)
    assert res.ok and res.copy_text == 'شكرًا، سنوافيكم بالتفاصيل.'
    assert p.calls == []   # لا منصة ولا بريد
    row = db.session.get(Message, m.id)
    assert row.reply_body == 'شكرًا، سنوافيكم بالتفاصيل.' and row.status == 'replied' and row.replied_at >= before
    # لا ادعاء إرسال بالبريد في أي نص يرجع للمستخدم
    assert 'بريد' not in res.error and not any('أُرسل' in str(v) for v in res.info.values())
    # مرة ثانية: لا استبدال صامت لرد محفوظ
    again = _prod('reply_draft').apply(_ctx(p), {'text': 'آخر'}, t)
    assert not again.ok and db.session.get(Message, m.id).reply_body == 'شكرًا، سنوافيكم بالتفاصيل.'
    gone = _prod('reply_draft').apply(_ctx(p), {'text': 'x'}, Target(ref='smsg:99999', label='x', facts={}, meta={'id': 99999}))
    assert not gone.ok and gone.error


def test_apply_rejects_empty_text_and_bad_ids():
    p = FakePlatform()
    r = _prod('reply_draft')
    assert not r.apply(_ctx(p), {'text': '  '}, _pm_target()).ok
    assert not r.apply(_ctx(p), {}, _pm_target()).ok
    bad = Target(ref='pmsg:../x', label='x', facts={'has_account': True}, meta={'id': '../../admin'})
    assert not r.apply(_ctx(p), {'text': 'رد'}, bad).ok
    badl = Target(ref='lead:x', label='x', facts={}, meta={'id': 'a/b'})
    assert not r.apply(_ctx(p), {'text': 'رد'}, badl).ok
    assert not r.apply(_ctx(p), {'text': 'رد'}, Target(ref='zzz:1', label='x', facts={}, meta={})).ok
    assert p.calls == []


def test_audit_failure_does_not_break_send():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (200, {'ok': True})

    def boom(*a, **k):
        raise RuntimeError('db')
    res = _prod('reply_draft').apply(_ctx(p, audit=boom), {'text': 'رد'}, _pm_target())
    assert res.ok


# ---------------------------------------------------------------- reply_draft · البريد (SPEC-B §B4)

EMAIL = '/api/bridge/email/send'
ITEM = 'f' * 32


def _ectx(plat, actor='boss@x.test', item_id=ITEM):
    ctx = _ctx(plat, actor=actor)
    if item_id:
        ctx.item_id = item_id
    return ctx


def _emsg(m, email='visitor@example.test'):
    return Target(ref='smsg:%d' % m.id, label='x', facts={'subject': 'استفسار', 'body': 'b'}, meta={'id': m.id, 'email': email})


def _no_acct(mid='pm-2', email='guest@example.test'):
    return Target(ref='pmsg:' + mid, label='x', facts={'subject': 'سؤال', 'body': 'b', 'has_account': False},
                  meta={'id': mid, 'email': email})


def _lead(email='salma.m@example.test'):
    return Target(ref='lead:ld-1', label='x', facts={'want': 'w', 'experience': ''}, meta={'id': 'ld-1', 'phone': '+201', 'email': email})


def _email_calls(p):
    return [c for c in p.calls if c['path'] == EMAIL]


def test_email_body_is_exact_for_site_message(app_ctx):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    audits = []
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'شكرًا لتواصلكم.'}, _emsg(m))
    assert res.ok and res.copy_text == '' and res.info['emailed'] is True and res.info['saved'] is True
    assert res.info['message'] == 'وصل الرد إلى بريد صاحب الرسالة.' and res.info['line'] == 'أُرسل الرد بالبريد'
    assert p.calls == [{'method': 'POST', 'path': EMAIL, 'params': None, 'json': {
        'to_email': 'visitor@example.test', 'subject': 'رد على: استفسار', 'text': 'شكرًا لتواصلكم.', 'by': 'boss@x.test',
        'confirmed': True, 'idem_key': ITEM, 'context': {'kind': 'site_message', 'id': str(m.id)}}}]
    row = db.session.get(Message, m.id)
    assert row.status == 'replied' and row.reply_body == 'شكرًا لتواصلكم.'


def test_email_limits_are_respected_in_the_payload(app_ctx):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    t = _emsg(m)
    t.facts['subject'] = 'ع' * 300
    _prod('reply_draft').apply(_ectx(p), {'text': 'ر' * 900}, t)
    j = _email_calls(p)[0]['json']
    assert len(j['subject']) <= 120 and len(j['text']) <= 4000 and len(j['idem_key']) <= 64 and len(j['by']) <= 120


def test_idem_key_falls_back_to_a_stable_hash_without_an_item_id(app_ctx):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    _prod('reply_draft').apply(_ectx(p, item_id=None), {'text': 'رد'}, _emsg(m))
    k = _email_calls(p)[0]['json']['idem_key']
    assert re.match(r'^[0-9a-f]{32}$', k) and k != ITEM


@pytest.mark.parametrize('outcome,why', [
    ((200, {'sent': False, 'reason': 'not_configured'}), 'خدمة البريد غير مفعّلة بعد'),
    ((200, {'sent': False, 'reason': 'failed'}), 'تعذّر الإرسال الآن'),
    ((200, {'sent': False}), 'تعذّر الإرسال الآن'),
    ((422, {'error': 'هذا البريد غير معروف لدينا'}), 'هذا البريد غير معروف لدينا'),
    ((429, {'error': 'بلغ البريد حدّه اليوم'}), 'بلغ البريد حدّه اليوم'),
    ((404, {'error': 'Not Found'}), 'خدمة البريد غير مفعّلة بعد'),
    ((503, {'error': 'لم يتم ضبط الربط بعد'}), 'خدمة البريد غير مفعّلة بعد'),
    ((403, {'error': 'x'}), 'تعذّر الإرسال الآن')])
def test_site_message_fallback_is_honest_and_keeps_the_copy_behaviour(app_ctx, outcome, why):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = outcome
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد للنسخ'}, _emsg(m))
    assert res.ok and res.copy_text == 'رد للنسخ' and res.info['emailed'] is False and res.info['saved'] is True
    assert res.info['message'] == 'لم يُرسل الرد بالبريد: %s. انسخ الرد وأرسله بنفسك.' % why
    assert 'line' not in res.info and 'أُرسل' not in json.dumps(res.info, ensure_ascii=False)
    row = db.session.get(Message, m.id)
    assert row.status == 'replied' and row.reply_body == 'رد للنسخ'


@pytest.mark.parametrize('outcome', [OSError('down'), (502, {'error': 'x'}), (504, {'error': 'x'}), (500, {'error': 'x'})])
def test_site_message_unknown_outcome_claims_nothing_and_saves_nothing(app_ctx, outcome):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = outcome
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد'}, _emsg(m))
    assert res.ok is False and res.no_reply is True and res.copy_text == 'رد'
    assert 'لا نعرف إن وصل البريد' in res.error and 'أُرسل' not in res.error
    assert db.session.get(Message, m.id).status != 'replied'


def test_telegram_actor_never_falls_back_to_copy(app_ctx):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': False, 'reason': 'not_configured'})
    res = _prod('reply_draft').apply(_ectx(p, actor='telegram:42'), {'text': 'رد'}, _emsg(m))
    assert not res.ok and not res.no_reply and res.copy_text == ''
    assert res.error == 'لم يُرسل الرد بالبريد (خدمة البريد غير مفعّلة بعد). افتح اللوحة لتنسخه وترسله بنفسك.'
    assert db.session.get(Message, m.id).status != 'replied', 'الاقتراح يبقى ليُنسخ من اللوحة'
    assert _email_calls(p)[0]['json']['by'] == 'telegram:42'


def test_pmsg_without_account_sends_email_then_resolves():
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    p.routes[('POST', '/api/bridge/messages/pm-2/resolve')] = (200, {'ok': True})
    audits = []
    res = _prod('reply_draft').apply(_ctx_audit(p, audits), {'text': 'مرحبًا بك'}, _no_acct())
    assert res.ok and res.copy_text == '' and res.info['emailed'] is True
    assert [(c['method'], c['path']) for c in p.calls] == [('POST', EMAIL), ('POST', '/api/bridge/messages/pm-2/resolve')]
    j = p.calls[0]['json']
    assert j['to_email'] == 'guest@example.test' and j['context'] == {'kind': 'message', 'id': 'pm-2'} and j['subject'] == 'رد على: سؤال'
    assert audits == ['brain.reply_email']
    assert 'reply' not in ''.join(c['path'] for c in p.calls), 'لا رد داخلي لمن بلا حساب'


def _ctx_audit(plat, audits, actor='boss@x.test'):
    ctx = _ctx(plat, audit=lambda action, **k: audits.append(action), actor=actor)
    ctx.item_id = ITEM
    return ctx


def test_pmsg_without_account_resolve_failure_after_a_real_send_is_still_ok():
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    p.routes[('POST', '/api/bridge/messages/pm-2/resolve')] = (500, {'error': 'x'})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد'}, _no_acct())
    assert res.ok and res.info['emailed'] is True and 'تعذّر تعليم الرسالة' in res.info['message']


def test_pmsg_without_account_fallback_is_copy_plus_resolve():
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': False, 'reason': 'not_configured'})
    p.routes[('POST', '/api/bridge/messages/pm-2/resolve')] = (200, {'ok': True})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد'}, _no_acct())
    assert res.ok and res.copy_text == 'رد' and res.info['emailed'] is False and 'غير مفعّلة' in res.info['message']
    assert [c['path'] for c in p.calls] == [EMAIL, '/api/bridge/messages/pm-2/resolve']


def test_pmsg_without_account_unknown_email_outcome_does_not_resolve():
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (502, {'error': 'x'})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد'}, _no_acct())
    assert res.no_reply is True and [c['path'] for c in p.calls] == [EMAIL]


def test_pmsg_without_account_and_without_email_stays_copy_only():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-2/resolve')] = (200, {'ok': True})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد'}, _no_acct(email=''))
    assert res.ok and res.copy_text == 'رد' and [c['path'] for c in p.calls] == ['/api/bridge/messages/pm-2/resolve']


def test_pmsg_with_account_replies_in_app_then_emails():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (200, {'ok': True})
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    audits = []
    res = _prod('reply_draft').apply(_ctx_audit(p, audits), {'text': 'شكرًا'}, _pm_target())
    assert res.ok and res.info['sent'] is True and res.info['emailed'] is True and res.copy_text == ''
    assert [c['path'] for c in p.calls] == ['/api/bridge/messages/pm-1/reply', EMAIL]
    assert p.calls[1]['json']['context'] == {'kind': 'message', 'id': 'pm-1'}
    assert audits == ['brain.reply_send', 'brain.reply_email']


@pytest.mark.parametrize('outcome,fragment', [
    ((200, {'sent': False, 'reason': 'not_configured'}), 'لم تُرسل نسخة بالبريد: خدمة البريد غير مفعّلة بعد'),
    ((422, {'error': 'x'}), 'لم تُرسل نسخة بالبريد: هذا البريد غير معروف لدينا'),
    ((502, {'error': 'x'}), 'ولا نعرف إن وصلت نسخة البريد')])
def test_pmsg_with_account_email_failure_never_cancels_or_hides_the_in_app_reply(outcome, fragment):
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (200, {'ok': True})
    p.routes[('POST', EMAIL)] = outcome
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'شكرًا'}, _pm_target())
    assert res.ok and res.info['sent'] is True and res.info['emailed'] is False
    assert res.info['message'].startswith('وصل الرد داخل المنصة.') and fragment in res.info['message']


def test_pmsg_with_account_in_app_failure_sends_no_email():
    p = FakePlatform()
    p.routes[('POST', '/api/bridge/messages/pm-1/reply')] = (500, {'error': 'x'})
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'رد'}, _pm_target())
    assert not res.ok and _email_calls(p) == []


def test_lead_with_email_sends_then_resolves_and_without_email_copies():
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})
    p.routes[('POST', '/api/bridge/leads/ld-1/resolve')] = (200, {'ok': True})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'مرحبًا سلمى'}, _lead())
    assert res.ok and res.copy_text == '' and res.info['emailed'] is True and res.info['message'] == 'وصل الرد إلى بريد صاحب الطلب.'
    assert [c['path'] for c in p.calls] == [EMAIL, '/api/bridge/leads/ld-1/resolve']
    j = p.calls[0]['json']
    assert j['context'] == {'kind': 'lead', 'id': 'ld-1'} and j['subject'] == 'رد على طلب التواصل' and j['to_email'] == 'salma.m@example.test'
    p2 = FakePlatform()
    p2.routes[('POST', '/api/bridge/leads/ld-1/resolve')] = (200, {'ok': True})
    r2 = _prod('reply_draft').apply(_ectx(p2), {'text': 'مرحبًا'}, _lead(email=''))
    assert r2.ok and r2.copy_text == 'مرحبًا' and [c['path'] for c in p2.calls] == ['/api/bridge/leads/ld-1/resolve']


def test_lead_fallback_and_unknown():
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': False, 'reason': 'failed'})
    p.routes[('POST', '/api/bridge/leads/ld-1/resolve')] = (200, {'ok': True})
    res = _prod('reply_draft').apply(_ectx(p), {'text': 'مرحبًا'}, _lead())
    assert res.ok and res.copy_text == 'مرحبًا' and res.info['emailed'] is False and 'تعذّر الإرسال الآن' in res.info['message']
    p2 = FakePlatform()
    p2.routes[('POST', EMAIL)] = OSError('x')
    r2 = _prod('reply_draft').apply(_ectx(p2), {'text': 'مرحبًا'}, _lead())
    assert r2.no_reply is True and [c['path'] for c in p2.calls] == [EMAIL]


def test_email_audit_failure_does_not_break_the_send(app_ctx):
    m = _seed_msg()
    p = FakePlatform()
    p.routes[('POST', EMAIL)] = (200, {'sent': True})

    def boom(*a, **k):
        raise RuntimeError('db')
    ctx = _ctx(p, audit=boom)
    ctx.item_id = ITEM
    assert _prod('reply_draft').apply(ctx, {'text': 'رد'}, _emsg(m)).ok


def test_approve_labels_follow_the_email_path():
    assert ops.LABEL_EMAIL == 'أرسل الرد بالبريد' and ops.LABEL_EMAIL_LEAD == 'أرسل بالبريد'


def test_email_copy_has_no_false_claims():
    src = open(ops.__file__, encoding='utf-8').read()
    assert 'يقوّم' not in src
    for msg in ops._EMAIL_WHY.values():
        assert 'أُرسل' not in msg


# ---------------------------------------------------------------- تكامل مع `_platform_proxy` الحقيقي (requests مزيّف)

class _FakeHTTP(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload).encode()

    def json(self):
        return self._p


def test_works_with_real_platform_proxy_shapes(app_ctx, monkeypatch):
    calls = []

    def fake_request(method, url, params=None, json=None, headers=None, timeout=None):
        calls.append((method, url.split('/api', 1)[1] if '/api' in url else url, json))
        if url.endswith('/api/bridge/messages'):
            return _FakeHTTP(200, MSGS)
        if url.endswith('/api/bridge/leads'):
            return _FakeHTTP(200, LEADS)
        if url.endswith('/pm-1/reply'):
            return _FakeHTTP(422, {'detail': 'visitor'})
        if url.endswith('/pm-9/reply'):
            raise OSError('down')
        return _FakeHTTP(200, {'ok': True})

    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'sec')
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', 'https://platform.test')
    monkeypatch.setattr(appmod.requests, 'request', fake_request)
    ctx = Ctx(ns={'_platform_proxy': appmod._platform_proxy, '_resp_ok': appmod._resp_ok, '_audit': appmod._audit,
                  'Message': Message, 'db': db}, now=datetime.datetime.now(UTC), actor='boss@x.test')
    ts = _prod('reply_draft').gather(ctx)
    assert {t.ref for t in ts} == {'pmsg:pm-1', 'pmsg:pm-2', 'lead:ld-1'}
    ctx.item_id = ITEM
    res = _prod('reply_draft').apply(ctx, {'text': 'رد'}, _pm_target())
    assert not res.ok and not res.no_reply and 'زائر' in res.error      # 422 حقيقي من الوكيل
    res = _prod('reply_draft').apply(ctx, {'text': 'رد'}, _pm_target(True, 'pm-9'))
    assert res.no_reply is True                                           # 502 حقيقي من الوكيل
    sent = [c for c in calls if c[1].endswith('/reply')][0]
    assert sent[2] == {'body': 'رد', 'by': 'boss@x.test', 'confirmed': True, 'idem_key': ITEM}
    # بلا سر مضبوط ⇒ 503 من الوكيل ⇒ لا مصدر منصّة، والموقع المحلي وحده يكفي
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    _seed_msg()
    ts = _prod('reply_draft').gather(ctx)
    assert {t.ref.split(':')[0] for t in ts} == {'smsg'} and sorted(e['source'] for e in ops.last_source_errors) == ['lead', 'pmsg']


def test_copy_has_no_banned_words():
    src = open(ops.__file__, encoding='utf-8').read()
    assert 'يقوّم' not in src and 'يقوم' not in src.replace('يقوم ', '')
    assert 'أُرسل بالبريد' not in src
