# -*- coding: utf-8 -*-
"""«العقل» · مساهمات «مكتبة القانون العربي» `library_contribution` (2026-11-09).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_library.py

⛔ صفر شبكة وصفر ذكاء حقيقي: `_platform_proxy` و`_v2_write` بدائل محلية. النصوص تجريبية مش قانون حقيقي.
"""
import datetime
import json

import pytest

import app as appmod
from brain2 import producers_library as pl, registry
from brain2.contract import ApplyResult, Ctx, SourceDown, Target
from test_brain2_routes import api, rows, ADMIN   # noqa: F401  (api = fixture)
from test_brain2_engine import env   # noqa: F401  (fixture)

UTC = datetime.timezone.utc
AP = 'eg-administrative-prosecution'


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


def _item(cid='c1', **kw):
    d = {'id': cid, 'kind': 'law', 'kind_other': '', 'title': 'قانون تجريبي رقم 81 لسنة 2016', 'law_number': '81/2016',
         'chars': 5000, 'contributor_name': 'أ. فلان', 'created_at': '2026-11-09',
         'preview': 'مادة 1 - يُعمل بهذا القانون التجريبي. مادة 2 - تختص الجهة التجريبية.',
         'law_key_guess': '81/2016', 'articles_found': 78, 'existing_articles': 0, 'suggested_track': AP}
    d.update(kw)
    return d


def _ctx(plat=None, write=None, actor='admin@test'):
    ns = {'_platform_proxy': plat or FakePlatform(), '_v2_write': write or (lambda *a: ({'articles_added': 78}, 200)),
          '_resp_ok': lambda r: isinstance(r, tuple) and r[1] == 200,
          '_proxy_json': lambda r: r[0] if isinstance(r, tuple) else {}}
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor=actor)


def _plat(items):
    return FakePlatform({('GET', '/api/bridge/library/contributions'): (200, {'items': items})})


def _target(**kw):
    t = pl.gather(_ctx(_plat([_item(**kw)])))
    return t[0]


def _raw(**kw):
    d = {'is_legal': True, 'kind_ok': True, 'is_book': False, 'law_key': '81/2016', 'number_matches': True,
         'duplicate': 'none', 'recommend': 'accept', 'reason_ar': '', 'track': AP}
    d.update(kw)
    return d


# ------------------------------------------------------------------ التسجيل

def test_registered_locked_to_ask_and_on_telegram_default_only():
    p = registry.by_id('library_contribution')
    assert p is not None and p.default_mode == 'ask' and p.may_run_alone is False
    assert p.section == 'home' and p.kind == 'draft' and p.per_run_cap == 5 and callable(p.on_reject)
    assert 'library_contribution' in registry.TELEGRAM_DEFAULT_ON
    assert 'library_contribution' not in registry.TELEGRAM_OK


# ------------------------------------------------------------------ gather

def test_gather_builds_facts_and_skips_bad_items():
    plat = _plat([_item('c1'), _item('bad id!'), _item('c3', title=''), _item('c4', kind='weird'),
                  _item('c5', kind='own_book', law_number='', articles_found=0)])
    out = pl.gather(_ctx(plat))
    assert [t.ref for t in out] == ['libc:c1', 'libc:c5']
    assert plat.calls[0]['params'] == {'status': 'pending', 'limit': 50}
    f = out[0].facts
    assert f['articles_found'] == 78 and f['existing_articles'] == 0 and f['contributor_name'] == 'أ. فلان'
    assert f['suggested_track'] == AP and out[0].meta == {'contribution_id': 'c1'}


def test_gather_fits_the_byte_cap_and_ignores_unknown_track():
    out = pl.gather(_ctx(_plat([_item('c1', preview='نص ' * 5000, suggested_track='other')])))
    f = out[0].facts
    assert len(json.dumps(f, ensure_ascii=False, sort_keys=True).encode('utf-8')) <= pl.FACTS_MAX_BYTES
    assert f['suggested_track'] == ''


def test_gather_404_means_bridge_not_deployed_quietly():
    assert pl.gather(_ctx(FakePlatform())) == []


def test_gather_5xx_and_exception_are_source_down():
    with pytest.raises(SourceDown):
        pl.gather(_ctx(FakePlatform({('GET', '/api/bridge/library/contributions'): (500, {})})))
    with pytest.raises(SourceDown):
        pl.gather(_ctx(FakePlatform({('GET', '/api/bridge/library/contributions'): RuntimeError('x')})))


def test_gather_skips_contribution_already_approved(monkeypatch):
    import brain2.engine as eng

    class _Q(object):
        def filter(self, *a, **k): return self
        def first(self): return object()

    class _Item(object):
        producer = target_ref = status = type('C', (), {'in_': staticmethod(lambda x: True), '__eq__': lambda s, o: True})()
        query = _Q()

    monkeypatch.setattr(eng, '_models', lambda db: (_Item,))
    ctx = _ctx(_plat([_item('c1')]))
    ctx.ns['db'] = object()
    assert pl.gather(ctx) == []


# ------------------------------------------------------------------ prompt

def test_prompt_carries_facts_and_never_invites_invention():
    system, user = pl.prompt(_target())
    assert '81/2016' in user and 'أ. فلان' in user and 'لا تخترع رقمًا' in system


# ------------------------------------------------------------------ validate

def test_validate_accept_builds_card_from_facts():
    b = pl.validate(_raw(), _target())
    lines = b['text'].split('\n')
    assert lines == ['قانون تجريبي رقم 81 لسنة 2016', 'قانوني', 'الرقم مطابق', 'اتقسّم 78 مادة', 'مفيش نسخة', 'من «أ. فلان»']
    assert b['recommend'] == 'accept' and b['track'] == AP and b['law_key'] == '81/2016'
    assert b['approve_label'] == 'ضيفها للمكتبة'
    from brain2.engine import check_body
    assert check_body(b, _target().facts, 'draft') is None      # يعدّي فحوص الصدق بتاعة المحرك


def test_validate_older_copy_line_uses_existing_count():
    t = _target(existing_articles=40)
    b = pl.validate(_raw(duplicate='older_copy'), t)
    assert 'عندنا نسخة قديمة (40 مادة)' in b['text']
    assert pl.validate(_raw(duplicate='none'), t) is None, 'الموديل ما يقولش «مفيش نسخة» والجسر شايف نسخة'
    assert pl.validate(_raw(duplicate='same'), _target(existing_articles=0)) is None


def test_validate_law_key_must_literally_appear():
    assert pl.validate(_raw(law_key='82/2016'), _target()) is None
    assert pl.validate(_raw(law_key='81 لسنة 2016'), _target()) is None
    assert pl.validate(_raw(law_key=''), _target()) is not None
    # الرقم موجود بالأرقام الهندية في العنوان فقط
    t = _target(title='قانون ٨١/٢٠١٦', law_number='', preview='نص', law_key_guess='')
    assert pl.validate(_raw(law_key='81/2016'), t) is not None


def test_validate_reject_needs_reason_and_strict_types():
    assert pl.validate(_raw(recommend='reject', reason_ar=' '), _target()) is None
    b = pl.validate(_raw(recommend='reject', is_legal=False, reason_ar='ده مقال مش نص قانون.'), _target())
    assert b['recommend'] == 'reject' and b['why'] == 'ده مقال مش نص قانون.' and 'مش واضح' in b['text']
    assert pl.validate(_raw(recommend='maybe'), _target()) is None
    assert pl.validate(_raw(is_legal='yes'), _target()) is None
    assert pl.validate(_raw(duplicate='dup'), _target()) is None
    assert pl.validate(_raw(reason_ar='ن' * 161, recommend='reject'), _target()) is None
    assert pl.validate('x', _target()) is None


def test_validate_accept_requires_legal_and_kind_ok():
    assert pl.validate(_raw(is_legal=False), _target()) is None
    assert pl.validate(_raw(kind_ok=False), _target()) is None
    assert pl.validate(_raw(), _target(articles_found=0)) is None, 'نص قانوني ما اتقسّمش ⇒ مش جاهز'
    assert pl.validate(_raw(), _target(kind='other', kind_other='ورقة')) is None


def test_validate_book_never_accepted_unless_kind_is_own_book():
    assert pl.validate(_raw(is_book=True), _target(kind='law')) is None
    t = _target(kind='own_book', law_number='', law_key_guess='', articles_found=0, suggested_track='')
    b = pl.validate(_raw(is_book=True, law_key='', track=AP), t)
    assert b['recommend'] == 'accept' and b['track'] == '' and b['law_key'] == ''
    assert 'من غير تقسيم' in b['text']


def test_validate_track_must_be_known():
    assert pl.validate(_raw(track='eg-unknown'), _target()) is None
    b = pl.validate(_raw(track=''), _target())
    assert b['track'] == AP, 'من اقتراح المنصة لو الموديل ما عرفش'
    assert pl.validate(_raw(track=''), _target(suggested_track=''))['track'] == ''


# ------------------------------------------------------------------ template

def test_template_deterministic_checks():
    b = pl.template(_target(existing_articles=12))
    assert b['recommend'] == 'accept' and b['checks'] == {'is_legal': True, 'number_matches': True,
                                                           'duplicate': 'older_copy', 'articles_found': 78}
    assert 'عندنا نسخة قديمة (12 مادة)' in b['text'] and 'اتقسّم 78 مادة' in b['text']
    from brain2.engine import check_body
    assert check_body(b, _target(existing_articles=12).facts, 'draft') is None
    t0 = _target(articles_found=0, law_key_guess='')
    b0 = pl.template(t0)
    assert b0['recommend'] == 'reject' and b0['why'] and 'الرقم مش مطابق' in b0['text']
    bk = pl.template(_target(kind='own_book', articles_found=0))
    assert bk['recommend'] == 'review' and bk['law_key'] == '' and bk['track'] == ''
    assert pl.template(_target(kind='other', kind_other='ورقة'))['recommend'] == 'review'


# ------------------------------------------------------------------ apply / reject

def test_apply_posts_accept_decision_once():
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append((method, path, body, action, target))
        return ({'status': 'accepted', 'articles_added': 78}, 200)

    res = pl.apply(_ctx(write=write), {'track': AP, 'law_key': '81/2016'}, _target())
    assert res.ok and res.info['articles_added'] == 78 and '78' in res.info['line']
    assert len(seen) == 1
    m, path, body, action, target = seen[0]
    assert (m, path, action, target) == ('POST', '/api/bridge/library/contributions/c1/decision',
                                         'library.contribution_accept', 'c1')
    assert body == {'decision': 'accept', 'track': AP, 'law_key': '81/2016', 'by': 'admin@test'}


def test_apply_sanitizes_and_own_book_sends_no_track_or_key():
    seen = []
    write = lambda m, p, b, a, t, meta: (seen.append(b), ({'articles_added': 0}, 200))[1]   # noqa: E731
    pl.apply(_ctx(write=write), {'track': 'zz', 'law_key': 'bad'}, _target())
    assert seen[0]['track'] == '' and seen[0]['law_key'] == ''
    bt = _target(kind='own_book', articles_found=0)
    pl.apply(_ctx(write=write), {'track': AP, 'law_key': '81/2016'}, bt)
    assert seen[1]['track'] == '' and seen[1]['law_key'] == ''


def test_apply_error_paths():
    bad = lambda *a: ({'error': 'المنصة رفضت'}, 422)    # noqa: E731
    r = pl.apply(_ctx(write=bad), {}, _target())
    assert r.ok is False and r.error == 'المنصة رفضت' and not r.no_reply
    none = lambda *a: ({'no_reply': True}, 502)          # noqa: E731
    assert pl.apply(_ctx(write=none), {}, _target()).no_reply is True
    assert pl.apply(_ctx(), {}, Target(ref='libc:x', label='x', facts={}, meta={})).ok is False


def test_on_reject_posts_reject_with_reason_and_default():
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append((path, body, action))
        return ({'status': 'rejected'}, 200)

    assert pl.on_reject(_ctx(write=write), _target(), 'ده مقال مش نص قانون.').ok
    assert pl.on_reject(_ctx(write=write), _target(), '  ').ok
    path, body, action = seen[0]
    assert path.endswith('/c1/decision') and action == 'library.contribution_reject'
    assert body == {'decision': 'reject', 'reason': 'ده مقال مش نص قانون.', 'by': 'admin@test'}
    assert seen[1][1]['reason'] == pl.DEFAULT_REJECT_REASON, 'المنصة بتشترط سبب'
    assert pl.on_reject(_ctx(write=lambda *a: ({'error': 'x'}, 500)), _target(), 'س').ok is False


# ------------------------------------------------------------------ مسار الرفض في اللوحة

def _lib_producer(hook, recommend='accept', why='سبب'):
    from brain2.contract import Producer
    t = Target(ref='libc:c1', label='x', facts={'title': 'قانون'}, meta={'contribution_id': 'c1'})
    return Producer(id='library_contribution', section='home', kind='draft', label='l', sentence='s', lock_reason='r',
                    may_run_alone=False, default_mode='ask', per_run_cap=5, gather=lambda c: [t],
                    prompt=lambda x: ('', 'u'), validate=lambda d, x: {'text': 'قانون', 'why': why, 'recommend': recommend},
                    apply=lambda c, b, x: ApplyResult(ok=True), on_reject=hook, tag='t', approve_label='ok')


def _seed_reject(monkeypatch, api, hook, **kw):
    import brain2.engine as eng
    from test_brain2_engine import use
    prod = _lib_producer(hook, **kw)
    use(monkeypatch, prod)
    st, _ = eng.start_run(appmod.__dict__, 'admin', ADMIN)
    assert st == 202
    (r,) = rows()
    return r.id


def test_dashboard_reject_calls_on_reject_with_founder_reason(api, monkeypatch):
    calls = []

    def hook(ctx, target, reason):
        calls.append((ctx.actor, target.meta, reason))
        return ApplyResult(ok=True)

    iid = _seed_reject(monkeypatch, api, hook)
    r = api.post('/api/v2/brain/items/%s/reject' % iid, {'confirmed': True, 'reason': 'مكرر عندنا'})
    assert r.status_code == 200 and rows()[0].status == 'rejected'
    assert calls == [(ADMIN, {'contribution_id': 'c1'}, 'مكرر عندنا')]


def test_dashboard_reject_falls_back_to_brain_reason_and_survives_hook_failure(api, monkeypatch):
    calls = []

    def hook(ctx, target, reason):
        calls.append(reason)
        raise RuntimeError('boom')

    iid = _seed_reject(monkeypatch, api, hook, recommend='reject', why='مش نص قانون')
    r = api.post('/api/v2/brain/items/%s/reject' % iid, {'confirmed': True})
    assert r.status_code == 200 and rows()[0].status == 'rejected', 'فشل الإبلاغ ما يلغيش الرفض'
    assert calls == ['مش نص قانون']


def test_a_ruling_without_articles_can_still_be_accepted():
    from brain2 import producers_library as pl
    assert 'ruling' not in pl.SPLIT_KINDS and 'law' in pl.SPLIT_KINDS


# ------------------------------------------------------------------ مراجعة التحقق (2026-11-09)

def test_accept_downgrades_to_review_on_number_mismatch_or_same_copy():
    b = pl.validate(_raw(number_matches=False), _target())
    assert b['recommend'] == 'review' and b['why']
    b = pl.validate(_raw(duplicate='same'), _target(existing_articles=5))
    assert b['recommend'] == 'review'
    assert pl.validate(_raw(), _target())['recommend'] == 'accept'
    # reject يفضل reject
    assert pl.validate(_raw(number_matches=False, recommend='reject', reason_ar='x'), _target())['recommend'] == 'reject'


def test_law_key_match_respects_digit_boundaries():
    t = _target(title='قانون رقم 147/1973', law_number='147/1973', law_key_guess='147/1973',
                preview='مادة 1 - نص تجريبي.')
    assert pl.validate(_raw(law_key='47/1973'), t) is None, '47/1973 جوه 147/1973 مش مطابقة'
    assert pl.validate(_raw(law_key='147/1973'), t) is not None
    t2 = _target(title='قانون 47/19730', law_number='', preview='x')
    assert pl.validate(_raw(law_key='47/1973'), t2) is None


class _NS(dict):
    pass


def _gather_ctx(write, items):
    ns = dict(appmod.__dict__)
    ns.update({'_platform_proxy': _plat(items), '_v2_write': write,
               '_resp_ok': lambda r: isinstance(r, tuple) and r[1] == 200,
               '_proxy_json': lambda r: r[0] if isinstance(r, tuple) else {}})
    return Ctx(ns=ns, now=datetime.datetime.now(UTC), actor=ADMIN)


def test_reject_hook_failure_reports_notified_false_then_gather_retries(api, monkeypatch):
    iid = _seed_reject(monkeypatch, api, lambda c, t, r: ApplyResult(ok=False, error='x'))
    r = api.post('/api/v2/brain/items/%s/reject' % iid, {'confirmed': True, 'reason': 'مكرر عندنا'})
    assert r.status_code == 200
    assert r.get_json() == {'ok': True, 'id': iid, 'status': 'rejected', 'notified': False}
    (row,) = rows()
    assert row.status == 'rejected' and row.last_error == 'notify_failed'
    # الجمع القادم: المنصة لسه بتعرضه pending ⇒ نعيد الإبلاغ (بنفس السبب) ومانقترحوش تاني
    seen = []

    def write(method, path, body, action, target, meta):
        seen.append(body)
        return ({'status': 'rejected'}, 200)

    assert pl.gather(_gather_ctx(write, [_item('c1')])) == []
    assert len(seen) == 1 and seen[0]['decision'] == 'reject' and seen[0]['reason'] == 'مكرر عندنا'
    assert rows()[0].last_error is None
    assert pl.gather(_gather_ctx(write, [_item('c1')])) == [] and len(seen) == 1, 'نجح مرة ⇒ لا إعادة'


def test_reject_hook_success_has_no_notified_flag(api, monkeypatch):
    iid = _seed_reject(monkeypatch, api, lambda c, t, r: ApplyResult(ok=True))
    j = api.post('/api/v2/brain/items/%s/reject' % iid, {'confirmed': True}).get_json()
    assert 'notified' not in j and rows()[0].last_error is None


def test_gather_skips_items_already_decided_by_platform_id(api, monkeypatch):
    for st in ('approved', 'rejected', 'applying', 'unknown'):
        iid = _seed_reject(monkeypatch, api, lambda c, t, r: ApplyResult(ok=True))
        row = rows()[0]
        row.status = st
        appmod.db.session.commit()
        got = pl.gather(_gather_ctx(lambda *a: ({}, 200), [_item('c1')]))
        assert got == [], st
        from brain2 import engine as eng
        eng._models(appmod.db)[0].query.delete()
        appmod.db.session.commit()
    assert len(pl.gather(_gather_ctx(lambda *a: ({}, 200), [_item('c1')]))) == 1
