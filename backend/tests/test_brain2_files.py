# -*- coding: utf-8 -*-
"""«العقل» · مراجعة آراء «ملف للخبير» `file_review` + قراءة التفاصيل للخادم (SPEC-B §B3).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_files.py

⛔ صفر شبكة وصفر ذكاء حقيقي: `_platform_proxy` بديل محلي يسجّل النداءات، و`requests.*` ترمي.
"""
import datetime
import json
import re

import pytest

import app as appmod
from app import app as flask_app, db, AuditLog
from brain2 import ef_detail, engine, producers_files as pf, registry
from brain2.contract import ApplyResult, Ctx, SourceDown, Target

UTC = datetime.timezone.utc
NS = appmod.__dict__
EMAIL_RE = re.compile(r'[\w.+\-]+@[\w\-]+\.[\w.\-]+')


def _no_net(*a, **k):
    raise AssertionError('شبكة حقيقية ممنوعة')


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    for n in ('post', 'get', 'request'):
        monkeypatch.setattr(appmod.requests, n, _no_net)


class FakePlatform(object):
    """بديل `_platform_proxy`: `routes[(method, path)]` = (status, body) أو استثناء."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def __call__(self, method, path, params=None, json_body=None, timeout=12):
        self.calls.append({'method': method, 'path': path, 'params': params, 'json': json_body})
        r = self.routes.get((method, path))
        if r is None:
            return {'error': 'Not Found'}, 404
        if isinstance(r, Exception):
            raise r
        return r[1], r[0]


def _row(fid, status='in_review', **kw):
    return dict({'id': fid, 'status': status, 'title': 'تعويض عن حادثة', 'client_first_name': 'سمر',
                 'client_email': 'samar@clients.test'}, **kw)


def _detail(fid='ef-1', **kw):
    d = {'id': fid, 'status': 'in_review', 'title': 'تعويض عن حادثة عربية',
         'client_name': 'سمر عبد الله', 'client_first_name': 'سمر', 'counterparty_name': 'شركة التأمين الأهلية',
         'client_email': 'samar@clients.test', 'client_phone': '+201000000000',
         'facts': ['وقعت الحادثة في ٢٠٢٥ وسمر أصيبت', {'text': 'تقرير المستشفى متوفر'}, 5, {'k': 'x'}],
         'questions': [{'text': 'هل أستطيع رفع الدعوى على شركة التأمين؟'}, 'هل هناك ميعاد؟'],
         'pending_opinion': {
             'answers': [{'question_id': 'q1', 'question': 'هل أستطيع رفع الدعوى؟', 'text': 'نعم ترفع على شركة التأمين مباشرة. اتصل بي على samar@clients.test'},
                         {'question_id': 'q2', 'question': 'هل هناك ميعاد؟', 'text': 'الدعوى تسقط بعد ٣ سنين.'}],
             'next_step': 'specialist', 'next_step_label': 'محامي متخصص', 'next_step_note': 'يتابع تقرير الطب الشرعي لسمر',
             'stance': 'الموقف قوي', 'todo': ['جهّز التقرير', {'text': 'احضر المحضر'}, 5], 'slots': [{'start_at': 'x'}], 'meeting_url': 'https://m.test/x'},
         'review': {'round': 2, 'returns': 1, 'note': 'ملاحظة داخلية'},
         'money': {'payment_id': 'pay-1'}, 'docs': [{'name': 'x.pdf'}]}
    d.update(kw)
    return d


def _plat(rows=None, details=None):
    p = FakePlatform()
    p.routes[('GET', '/api/bridge/expert-files')] = (200, {'files': rows if rows is not None else [_row('ef-1')], 'count': 1})
    for fid, d in (details if details is not None else {'ef-1': _detail('ef-1')}).items():
        p.routes[('GET', '/api/bridge/expert-files/' + fid)] = (200, d)
    return p


def _ctx(plat, **extra):
    ns = {'_platform_proxy': plat, '_resp_ok': appmod._resp_ok, '_proxy_json': appmod._proxy_json}
    ns.update(extra)
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor='boss@x.test')


# ───────────────────────────────────────────────────────────── التعريف والتسجيل

def test_producer_definition_and_registry():
    (p,) = pf.PRODUCERS
    assert (p.id, p.section, p.kind, p.may_run_alone, p.default_mode) == ('file_review', 'files', 'draft', False, 'ask')
    assert p.lock_reason == 'يسألك دائمًا لأن الاعتماد يرسل الرأي إلى العميل.'
    assert p.approve_label == 'اعتمد الرأي وأرسله' and p.template is None and callable(p.apply)
    assert registry.by_id('file_review') is p and p.listed
    assert 'file_review' in registry.TELEGRAM_OK and 'file_review' in registry.TELEGRAM_DEFAULT_ON
    assert 'يقوّم' not in p.label + p.sentence + p.lock_reason


def test_browser_detail_keys_are_unchanged():
    assert appmod._EF_DETAIL_KEYS == ('id', 'title', 'status', 'file_no', 'dispute', 'opinion', 'revision', 'pending_opinion', 'review')
    assert 'facts' not in appmod._EF_DETAIL_KEYS and 'questions' not in appmod._EF_DETAIL_KEYS


# ───────────────────────────────────────────────────────────── _ef_detail_for_brain

def test_detail_reads_the_exact_path_and_keeps_only_what_the_brain_needs():
    p = _plat()
    d = ef_detail._ef_detail_for_brain(_ctx(p).ns, 'ef-1')
    assert p.calls == [{'method': 'GET', 'path': '/api/bridge/expert-files/ef-1', 'params': None, 'json': None}]
    assert set(d) == {'id', 'title', 'status', 'facts', 'questions', 'pending_opinion', 'round'}
    assert d['title'] == 'تعويض عن حادثة عربية' and d['round'] == 2
    assert d['facts'] == ['وقعت الحادثة في ٢٠٢٥ والعميل أصيبت', 'تقرير المستشفى متوفر']
    assert d['questions'] == ['هل أستطيع رفع الدعوى على شركة التأمين؟', 'هل هناك ميعاد؟']
    po = d['pending_opinion']
    assert set(po) == {'answers', 'stance', 'case_note', 'todo', 'next_step'}
    assert po['stance'] == 'الموقف قوي' and po['next_step'] == 'محامي متخصص'
    assert po['case_note'] == 'يتابع تقرير الطب الشرعي للعميل' and po['todo'] == ['جهّز التقرير', 'احضر المحضر']
    assert [a['question'] for a in po['answers']] == ['هل أستطيع رفع الدعوى؟', 'هل هناك ميعاد؟']
    blob = json.dumps(d, ensure_ascii=False)
    for leak in ('samar@clients.test', 'سمر', 'عبد الله', '+201000000000', 'pay-1', 'https://m.test', 'x.pdf', 'ملاحظة داخلية',
                 'شركة التأمين الأهلية'):
        assert leak not in blob, leak


@pytest.mark.parametrize('outcome', [(404, {'detail': 'Not Found'}), (500, {'x': 1}), (503, {'error': 'لم يتم ضبط الربط بعد'}),
                                     OSError('down'), (200, ['not a dict'])])
def test_detail_failure_is_source_down(outcome):
    p = FakePlatform()
    p.routes[('GET', '/api/bridge/expert-files/ef-1')] = outcome
    with pytest.raises(SourceDown):
        ef_detail._ef_detail_for_brain(_ctx(p).ns, 'ef-1')


@pytest.mark.parametrize('bad', ['', '../x', 'a/b', 'a' * 65, None, 'a b'])
def test_detail_bad_id_makes_no_call(bad):
    p = FakePlatform()
    with pytest.raises(SourceDown):
        ef_detail._ef_detail_for_brain(_ctx(p).ns, bad)
    assert p.calls == []


def test_detail_without_proxy_is_source_down():
    with pytest.raises(SourceDown):
        ef_detail._ef_detail_for_brain({}, 'ef-1')


# ───────────────────────────────────────────────────────────── gather

def test_gather_exact_paths_and_facts_shape():
    p = _plat()
    (t,) = pf.gather(_ctx(p))
    assert [(c['method'], c['path'], c['params']) for c in p.calls] == [
        ('GET', '/api/bridge/expert-files', {'status': 'review'}), ('GET', '/api/bridge/expert-files/ef-1', None)]
    assert t.ref == 'file:ef-1' and t.meta == {'file_id': 'ef-1'} and 0 < len(t.label) <= 120
    assert set(t.facts) == {'title', 'questions', 'facts', 'pending_opinion', 'round'}
    assert t.facts['round'] == 2
    blob = json.dumps(t.facts, ensure_ascii=False)
    assert not EMAIL_RE.search(blob) and 'سمر' not in blob
    assert len(blob.encode('utf-8')) <= engine.FACTS_MAX_BYTES
    assert 'ef-1' not in blob, 'المعرّف في meta فقط'


def test_gather_skips_files_not_in_review_or_without_an_opinion():
    p = _plat(rows=[_row('ef-1'), _row('ef-2', status='delivered'), _row('ef-3'), _row('bad/id'), {'id': ''}],
              details={'ef-1': _detail('ef-1'), 'ef-3': _detail('ef-3', pending_opinion=None), 'ef-2': _detail('ef-2')})
    ts = pf.gather(_ctx(p))
    assert [t.ref for t in ts] == ['file:ef-1']
    assert '/api/bridge/expert-files/ef-2' not in [c['path'] for c in p.calls]


def test_gather_list_404_means_no_files_not_an_error():
    p = FakePlatform()
    assert pf.gather(_ctx(p)) == []


@pytest.mark.parametrize('outcome', [(500, {'x': 1}), (503, {'error': 'x'}), OSError('down'), (200, {'files': 'no'})])
def test_gather_list_failure_is_source_down(outcome):
    p = FakePlatform()
    p.routes[('GET', '/api/bridge/expert-files')] = outcome
    with pytest.raises(SourceDown):
        pf.gather(_ctx(p))


def test_gather_one_bad_detail_does_not_hide_the_others_but_all_bad_is_source_down():
    p = _plat(rows=[_row('ef-1'), _row('ef-2')], details={'ef-2': _detail('ef-2')})
    assert [t.ref for t in pf.gather(_ctx(p))] == ['file:ef-2']
    p2 = _plat(rows=[_row('ef-1'), _row('ef-2')], details={})
    with pytest.raises(SourceDown):
        pf.gather(_ctx(p2))


def test_gather_empty_list_is_empty_not_source_down():
    assert pf.gather(_ctx(_plat(rows=[], details={}))) == []


def test_gather_caps_files_and_fits_big_facts():
    rows = [_row('ef-%d' % i) for i in range(30)]
    big = _detail('ef-0', facts=['و' * 300] * 12, questions=['س' * 200] * 8,
                  pending_opinion={'answers': [{'question': 'ص' * 200, 'text': 'ج' * 500}] * 8, 'todo': ['خ' * 200] * 8})
    p = _plat(rows=rows, details={'ef-%d' % i: big for i in range(30)})
    ts = pf.gather(_ctx(p))
    assert len(ts) == pf.LIST_LIMIT
    for t in ts:
        assert len(json.dumps(t.facts, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= pf.FACTS_MAX_BYTES


# ───────────────────────────────────────────────────────────── prompt / validate

def _target():
    (t,) = pf.gather(_ctx(_plat()))
    return t


def test_prompt_has_facts_and_no_meta_or_client_data():
    t = _target()
    system, user = pf.prompt(t)
    assert system.startswith(engine.SYSTEM_AR) and 'approve|return' in system
    assert json.dumps(t.facts, ensure_ascii=False, sort_keys=True) in user
    assert 'ef-1' not in system + user and 'samar' not in system + user and 'سمر' not in system + user


def test_validate_approve_and_return():
    t = _target()
    a = pf.validate({'text': 'الرأي مكتمل', 'recommend': 'approve', 'return_note': 'تجاهل'}, t)
    assert a['recommend'] == 'approve' and a['return_note'] == '' and a['approve_label'] == 'اعتمد الرأي وأرسله'
    assert a['file_id'] == 'ef-1' and a['text'] == 'الرأي مكتمل'
    r = pf.validate({'text': 'ينقص ميعاد', 'recommend': 'return', 'return_note': 'أضف الميعاد'}, t)
    assert r['recommend'] == 'return' and r['return_note'] == 'أضف الميعاد' and r['approve_label'] == 'أرجِعه بالملاحظة'
    assert r['notes_sha'] and r['notes_sha'] != a['notes_sha']


@pytest.mark.parametrize('raw', [
    None, [], {}, {'text': 'x', 'recommend': 'maybe'}, {'text': '', 'recommend': 'approve'}, {'text': '  ', 'recommend': 'approve'},
    {'text': 5, 'recommend': 'approve'}, {'text': 'ا' * 601, 'recommend': 'approve'},
    {'text': 'ينقص', 'recommend': 'return'}, {'text': 'ينقص', 'recommend': 'return', 'return_note': ''},
    {'text': 'ينقص', 'recommend': 'return', 'return_note': '   '}, {'text': 'ينقص', 'recommend': 'return', 'return_note': 7},
    {'text': 'ينقص', 'recommend': 'return', 'return_note': 'ا' * 601},
    {'text': 'ينقص', 'recommend': 'return', 'return_note': 'هذا لا يقوّم شيئًا'},
    {'text': 'ينقص', 'recommend': 'return', 'return_note': 'مدّتها ٩٩٩ يومًا'},          # رقم غير موجود في الحقائق
    {'text': 'ينقص', 'recommend': 'return', 'return_note': 'راجع القسم Z'},               # لاتينية غير موجودة في الحقائق
    {'text': 'ينقص', 'recommend': 'return', 'return_note': 'راسل a@b.test'},
])
def test_validate_rejects(raw):
    assert pf.validate(raw, _target()) is None


def test_validate_return_note_may_use_numbers_that_are_in_the_facts():
    r = pf.validate({'text': 'ينقص', 'recommend': 'return', 'return_note': 'وضّح الميعاد: ٣ سنين'}, _target())
    assert r is not None


# ───────────────────────────────────────────────────────────── مع المحرّك (فحوص الصدق على text)

from test_brain2_engine import env, use, rows, run   # noqa: F401,E402  (env = fixture)


def _engine_run(env_, monkeypatch, plat, reply):
    monkeypatch.setattr(appmod, '_platform_proxy', plat)
    use(monkeypatch, pf.PRODUCERS[0])
    env_.default = reply
    run()
    return rows()


def test_engine_stores_a_proposed_card_with_the_label_of_its_recommendation(env, monkeypatch):
    (a,) = _engine_run(env, monkeypatch, _plat(), {'text': 'الرأي أجاب السؤالين ويتبع الوقائع', 'recommend': 'approve'})
    assert a.status == 'proposed' and a.kind == 'draft' and a.section == 'files' and a.mode == 'ask'
    body = json.loads(a.body_json)
    assert body['approve_label'] == 'اعتمد الرأي وأرسله' and body['recommend'] == 'approve'
    assert json.loads(a.meta_json) == {'file_id': 'ef-1'}
    assert env.calls and 'ef-1' not in env.calls[0]['user'] and 'samar' not in env.calls[0]['user']


def test_engine_return_card_carries_the_return_note_and_button(env, monkeypatch):
    (a,) = _engine_run(env, monkeypatch, _plat(), {'text': 'لم يُذكر الميعاد بوضوح', 'recommend': 'return',
                                                    'return_note': 'وضّح أن الدعوى تسقط بعد ٣ سنين'})
    body = json.loads(a.body_json)
    assert a.status == 'proposed' and body['return_note'] == 'وضّح أن الدعوى تسقط بعد ٣ سنين'
    assert body['approve_label'] == 'أرجِعه بالملاحظة'


@pytest.mark.parametrize('reply', [
    {'text': 'الرأي في ٩٨٧ صفحة', 'recommend': 'approve'},            # رقم ليس في الحقائق ⇒ فحص المحرّك
    {'text': 'راجع approve الآن', 'recommend': 'approve'},             # لاتينية ليست في الحقائق
    {'text': 'لا يقوّم', 'recommend': 'approve'},                       # عبارة ممنوعة
    {'text': 'ناقص', 'recommend': 'return', 'return_note': 'اكتب ٩٨٧ كلمة'},   # ملاحظة الإرجاع تُفحص أيضًا
    {'text': 'ناقص', 'recommend': 'return'},                             # بلا ملاحظة
])
def test_engine_drops_dishonest_or_incomplete_output(env, monkeypatch, reply):
    (a,) = _engine_run(env, monkeypatch, _plat(), reply)
    assert a.status == 'failed' and a.last_error


def test_engine_source_down_stores_nothing(env, monkeypatch):
    p = FakePlatform()
    p.routes[('GET', '/api/bridge/expert-files')] = (500, {'x': 1})
    assert _engine_run(env, monkeypatch, p, {'text': 'ن', 'recommend': 'approve'}) == [] and env.calls == []


def test_engine_ask_has_approve_reject_open_and_the_return_note(env, monkeypatch):
    plat = _plat()
    _engine_run(env, monkeypatch, plat, {'text': 'لم يُذكر الميعاد', 'recommend': 'return', 'return_note': 'وضّح الميعاد ٣ سنين'})
    # الطلب الوحيد على `/brain/ask` سجّله `FakePlatform` (٤٠٤ ⇒ لا إرسال) — نتحقق من الجسم المبعوث
    ask = [c for c in plat.calls if c['path'] == '/api/bridge/brain/ask']
    assert len(ask) == 1
    j = ask[0]['json']
    assert [b['action'] for b in j['buttons']] == ['approve', 'reject', 'open']
    assert j['buttons'][0]['label'] == 'أرجِعه بالملاحظة' and 'وضّح الميعاد' in j['text']


# ───────────────────────────────────────────────────────────── apply

class FakeWrite(object):
    """بديل `_v2_write`: يسجّل الوسائط ويرجع ردًّا حقيقيًا (jsonify)."""

    def __init__(self, status=200, payload=None):
        self.status, self.payload, self.calls = status, payload if payload is not None else {'ok': True, 'status': 'delivered'}, []

    def __call__(self, method, path, platform_body, audit_action, target, meta, params=None):
        self.calls.append((method, path, platform_body, audit_action, target, meta))
        r = appmod.jsonify(self.payload)
        return r if self.status == 200 else (r, self.status)


def _apply(body, write, fid='ef-1'):
    ctx = _ctx(FakePlatform(), _v2_write=write)
    with flask_app.app_context():
        return pf.apply(ctx, body, Target(ref='file:' + fid, label='x', facts={}, meta={'file_id': fid}))


def test_apply_approve_exact_call():
    w = FakeWrite()
    res = _apply({'recommend': 'approve', 'text': 'الرأي مكتمل', 'notes_sha': pf._sha('الرأي مكتمل')}, w)
    assert res.ok and res.info == {'file_id': 'ef-1', 'action': 'approve', 'line': 'اعتُمد الرأي وأُرسل إلى العميل'}
    assert w.calls == [('POST', '/api/bridge/expert-files/ef-1/review', {'action': 'approve', 'note': ''},
                        'expert_file.review_approve', 'ef-1', {'via': 'brain'})]


def test_apply_return_uses_the_brain_note_unless_the_founder_edited():
    text = 'ينقص ميعاد'
    body = {'recommend': 'return', 'text': text, 'notes_sha': pf._sha(text), 'return_note': 'أضف الميعاد'}
    w = FakeWrite()
    res = _apply(body, w)
    assert res.ok and res.info['action'] == 'return' and res.info['line'] == 'أُرجع الملف إلى الخبير بالملاحظة'
    assert w.calls == [('POST', '/api/bridge/expert-files/ef-1/review', {'action': 'return', 'note': 'أضف الميعاد'},
                        'expert_file.review_return', 'ef-1', {'via': 'brain'})]
    w2 = FakeWrite()
    _apply(dict(body, text='ملاحظتي أنا: وضّح الميعاد'), w2)
    assert w2.calls[0][2] == {'action': 'return', 'note': 'ملاحظتي أنا: وضّح الميعاد'}


def test_apply_return_without_any_note_is_refused_before_calling():
    w = FakeWrite()
    res = _apply({'recommend': 'return', 'text': '', 'notes_sha': 'x', 'return_note': ''}, w)
    assert not res.ok and res.error and w.calls == []


@pytest.mark.parametrize('body,fid', [({'recommend': 'maybe'}, 'ef-1'), ({}, 'ef-1'), ({'recommend': 'approve'}, '../x'),
                                      ({'recommend': 'approve'}, '')])
def test_apply_bad_inputs_make_no_call(body, fid):
    w = FakeWrite()
    res = _apply(body, w, fid=fid)
    assert not res.ok and res.error and w.calls == []


def test_apply_platform_rejection_and_no_reply():
    res = _apply({'recommend': 'approve'}, FakeWrite(409, {'error': 'سبق الاعتماد'}))
    assert not res.ok and not res.no_reply and res.error == 'سبق الاعتماد'
    res = _apply({'recommend': 'approve'}, FakeWrite(502, {'error': 'ما وصلناش رد', 'no_reply': True}))
    assert not res.ok and res.no_reply is True
    res = _apply({'recommend': 'approve'}, FakeWrite(500, {}))
    assert not res.ok and res.error == 'تعذّر التنفيذ الآن'


def test_apply_through_the_real_v2_write(monkeypatch):
    """المسار الحقيقي: `_v2_write` ⇒ `_platform_proxy` ⇒ جسم {action, note, by} ومهلة ٢٥ وتدقيق عند النجاح فقط."""
    seen = []

    def proxy(method, path, params=None, json_body=None, timeout=12):
        seen.append((method, path, json_body, timeout))
        return appmod.jsonify({'ok': True, 'status': 'delivered'})
    monkeypatch.setattr(appmod, '_platform_proxy', proxy)
    ctx = Ctx(ns=NS, now=datetime.datetime.now(UTC), actor='boss@x.test')
    from types import SimpleNamespace
    from flask import g
    with flask_app.test_request_context('/'):
        g.user = SimpleNamespace(email='boss@x.test')
        AuditLog.query.filter_by(action='expert_file.review_approve', target='ef-9').delete()
        db.session.commit()
        res = pf.apply(ctx, {'recommend': 'approve'}, Target(ref='file:ef-9', label='x', facts={}, meta={'file_id': 'ef-9'}))
        assert res.ok
        assert seen == [('POST', '/api/bridge/expert-files/ef-9/review', {'action': 'approve', 'note': '', 'by': 'boss@x.test'}, 25)]
        a = AuditLog.query.filter_by(action='expert_file.review_approve', target='ef-9').one()
        assert a.actor_email == 'boss@x.test' and json.loads(a.meta_json) == {'via': 'brain'}


def test_no_banned_words_in_visible_copy():
    p = pf.PRODUCERS[0]
    assert not engine.has_banned(' '.join((pf.LABEL_APPROVE, pf.LABEL_RETURN, pf.LOCK_REASON, p.label, p.sentence, p.tag)))


# ───────────────────────────────────────────────────────────── الموقف بالعربية (لا حرف لاتيني على بطاقة المؤسس)

_LATIN = re.compile(r'[A-Za-z]')


def _stance_facts(**po_kw):
    d = _detail('ef-1')
    d['pending_opinion'] = dict(d['pending_opinion'], **po_kw)
    (t,) = pf.gather(_ctx(_plat(details={'ef-1': d})))
    return t.facts['pending_opinion']


@pytest.mark.parametrize('raw,ar', [
    ('favorable', 'في صالح العميل'), ('unfavorable', 'ليس في صالح العميل'), ('mixed', 'مختلط'),
    ('cautious', 'مشروط'), ('conditional', 'مشروط'), ('Favorable', 'في صالح العميل'),
])
def test_english_stance_values_become_arabic(raw, ar):
    po = _stance_facts(stance=raw)
    assert po['stance'] == ar and not _LATIN.search(po['stance'])


def test_stance_label_from_the_platform_wins_and_is_not_duplicated():
    po = _stance_facts(stance='favorable', stance_label='موقف جيد للعميل')
    assert po['stance'] == 'موقف جيد للعميل' and 'stance_label' not in po
    # تسمية لاتينية لا تُقبل، ونرجع لخريطتنا
    po = _stance_facts(stance='mixed', stance_label='Mixed')
    assert po['stance'] == 'مختلط'


def test_unknown_latin_stance_is_dropped_and_arabic_kept():
    assert _stance_facts(stance='weird_value')['stance'] == ''
    assert _stance_facts(stance='الموقف قوي')['stance'] == 'الموقف قوي'
    d = _detail('ef-1')
    d['pending_opinion'] = {k: v for k, v in d['pending_opinion'].items() if k != 'stance'}
    (t,) = pf.gather(_ctx(_plat(details={'ef-1': d})))
    assert t.facts['pending_opinion']['stance'] == ''
