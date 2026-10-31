# -*- coding: utf-8 -*-
"""«العقل» الجولة ٢ · المسارات والنموذج (SPEC docs/v2/brain2/SPEC.md §2.5–§2.6، §5 P1).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_routes.py

⛔ صفر شبكة وصفر نداء ذكاء حقيقي (نفس تجهيز test_brain2_engine: ناقل Claude مزيّف، و`requests.post/get` ترميان).
"""
import datetime
import json
import os

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod
from app import app as flask_app, db, User, AuditLog
from brain2 import engine, registry
from brain2.contract import ApplyResult, Target
import v2_brain2_routes

from test_brain2_engine import env, fp, use, rows, F1, F2, F3, Script   # noqa: F401  (env = fixture)

NS = appmod.__dict__
SECRET = 'test-metrics-secret'
NON_ADMIN = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


ADMIN = 'brain2-admin@x.test'


@pytest.fixture()
def api(env):          # noqa: F811
    heads = {r: _bearer(_mkuser('brain2-%s@x.test' % r, r)) for r in NON_ADMIN}
    heads['admin'] = _bearer(_mkuser(ADMIN, 'admin'))
    client = flask_app.test_client()

    class Api(object):
        def __init__(self):
            self.heads = heads
            self.script = env

        def call(self, method, path, body=None, role='admin'):
            return client.open(path, method=method, headers=heads[role], json=body)

        def anon(self, method, path, body=None):
            return client.open(path, method=method, json=body)

        def get(self, path, role='admin'):
            return self.call('GET', path, role=role)

        def post(self, path, body=None, role='admin'):
            return self.call('POST', path, body, role=role)

        def put(self, path, body=None, role='admin'):
            return self.call('PUT', path, body, role=role)
    return Api()


@pytest.fixture()
def spy_ai(monkeypatch):
    seen = []

    def spy(*a, **k):
        seen.append(a)
        raise AssertionError('نداء ذكاء ممنوع هنا')
    monkeypatch.setattr(appmod, 'ai_call', spy)
    return seen


def seed(monkeypatch, api, *producers):
    use(monkeypatch, *producers)
    st, pl = engine.start_run(NS, 'admin', ADMIN)
    assert st == 202


def opinion_producer():
    return fp(pid='opinion', kind='opinion', section='home', targets=[], validate=lambda d, t: {'text': d['opinion']})


# ───────────────────────────────────────────────────────────── الباب: أدمن بس · المفتاح · no-store

ID = 'a' * 32
ENDPOINTS = [
    ('GET', '/api/v2/brain/switches', None),
    ('PUT', '/api/v2/brain/switches/fp', {'mode': 'ask', 'confirmed': True}),
    ('GET', '/api/v2/brain/items', None),
    ('POST', '/api/v2/brain/items/%s/approve' % ID, {'confirmed': True}),
    ('POST', '/api/v2/brain/items/%s/reject' % ID, {'confirmed': True}),
    ('POST', '/api/v2/brain/items/%s/discard' % ID, {'confirmed': True}),
    ('POST', '/api/v2/brain/opinion', {'kind': 'review', 'card_id': 'c1', 'facts': {}}),
    ('POST', '/api/v2/brain/opinions/lookup', {'cards': []}),
    ('POST', '/api/v2/brain/run', {'confirmed': True}),
    ('GET', '/api/v2/brain/runs/latest', None),
]


@pytest.mark.parametrize('method,path,body', ENDPOINTS)
def test_admin_only_and_flag_closed_with_no_calls(api, monkeypatch, spy_ai, method, path, body):
    touched = []
    use(monkeypatch, fp(gather=lambda ctx: touched.append(1) or []))
    for role in NON_ADMIN:
        assert api.call(method, path, body, role=role).status_code == 403, (role, path)
    assert api.anon(method, path, body).status_code in (401, 403)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = api.call(method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert spy_ai == [] and touched == [] and rows() == []
    assert engine._models(db)[2].query.count() == 0, 'المفتاح مقفول ⇒ لا جولة'


@pytest.mark.parametrize('method,path,body', [e for e in ENDPOINTS if e[0] == 'GET'])
def test_no_store_on_open(api, method, path, body):
    r = api.call(method, path, body)
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'


def test_run_cron_flag_off_is_404_and_without_secret_is_401(api, monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert api.anon('POST', '/api/v2/brain/run-cron').status_code == 404
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    assert api.anon('POST', '/api/v2/brain/run-cron').status_code == 401
    r = flask_app.test_client().post('/api/v2/brain/run-cron', headers={'X-ELP-Metrics-Secret': 'wrong'})
    assert r.status_code == 401
    r = flask_app.test_client().post('/api/v2/brain/run-cron', headers=dict(api.heads['admin']))
    assert r.status_code == 401, 'توكن الأدمن لا يكفي: الكرون بالسرّ فقط'
    assert rows() == [] and api.script.calls == []


def test_run_cron_with_secret_starts_a_cron_run(api, monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    r = flask_app.test_client().post('/api/v2/brain/run-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 202 and r.headers.get('Cache-Control') == 'no-store'
    run = engine._models(db)[2].query.get(r.get_json()['run_id'])
    assert run.trigger == 'cron' and run.by == 'cron' and run.finished_at is not None
    assert len(rows()) == 1


# ───────────────────────────────────────────────────────────── المفاتيح

def test_switches_list(api, monkeypatch):
    use(monkeypatch, fp(pid='note1', alone=True), fp(pid='draft1', kind='draft', alone=False),
        fp(pid='hidden', alone=False, kind='draft', listed=False))
    d = api.get('/api/v2/brain/switches').get_json()
    by = {s['id']: s for s in d['switches']}
    assert set(by) == {'note1', 'draft1'}, 'المخفي لا يظهر'
    assert set(by['note1']) == {'id', 'section', 'kind', 'label', 'sentence', 'lock_reason', 'may_run_alone', 'mode',
                                'telegram', 'telegram_ok', 'telegram_can_toggle', 'updated_at', 'updated_by'}
    assert by['note1']['mode'] == 'alone' and by['draft1']['mode'] == 'ask'
    assert by['draft1']['lock_reason'] and by['draft1']['may_run_alone'] is False
    assert d['writer'] == 'main' and d['brain_today'] == {'used': 0, 'cap': 60}
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    assert api.get('/api/v2/brain/switches').get_json()['writer'] is None
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'k')
    assert api.get('/api/v2/brain/switches').get_json()['writer'] == 'backup'


def test_switch_put_rules(api, monkeypatch):
    use(monkeypatch, fp(pid='note1', alone=True), fp(pid='draft1', kind='draft', alone=False),
        fp(pid='hidden', alone=False, kind='draft', listed=False))
    p = '/api/v2/brain/switches/'
    assert api.put(p + 'note1', {'mode': 'ask'}).status_code == 400, 'بلا تأكيد'
    assert api.put(p + 'note1', {'mode': 'ask', 'confirmed': 'true'}).status_code == 400
    assert api.put(p + 'nope', {'mode': 'ask', 'confirmed': True}).status_code == 404
    assert api.put(p + 'hidden', {'mode': 'ask', 'confirmed': True}).status_code == 404
    assert api.put(p + 'note1', {'mode': 'weird', 'confirmed': True}).status_code == 400
    r = api.put(p + 'draft1', {'mode': 'alone', 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'] == 'هذا لا يعمل وحده: يسألك دائمًا.'
    assert AuditLog.query.filter_by(action='v2_brain.switch').count() == 0, 'التدقيق عند النجاح فقط'
    r = api.put(p + 'draft1', {'mode': 'off', 'confirmed': True, 'by': 'evil@x.test', 'updated_by': 'evil@x.test'})
    assert r.status_code == 200 and r.get_json()['mode'] == 'off' and r.get_json()['updated_by'] == ADMIN
    Switch = engine._models(db)[1]
    assert Switch.query.get('draft1').updated_by == ADMIN
    a = AuditLog.query.filter_by(action='v2_brain.switch').one()
    assert a.target == 'draft1' and json.loads(a.meta_json) == {'mode': 'off'} and a.actor_email == ADMIN
    d = {s['id']: s for s in api.get('/api/v2/brain/switches').get_json()['switches']}
    assert d['draft1']['mode'] == 'off' and d['draft1']['updated_by'] == ADMIN


# ───────────────────────────────────────────────────────────── العناصر

ITEM_KEYS = {'id', 'producer', 'section', 'kind', 'target_label', 'body', 'status', 'source', 'created_at', 'decided_at',
             'decided_by', 'tag', 'approve_label', 'last_error'}


def test_items_allow_list_has_no_meta_and_no_facts(api, monkeypatch):
    seed(monkeypatch, api, fp(alone=False, kind='draft', section='people',
                              targets=[('m:1', F1, {'email': 'secret@x.test', 'id': 'MSG_1'})]),
         fp(pid='n', section='content', targets=[('n:1', F2)]))
    d = api.get('/api/v2/brain/items?status=all').get_json()['items']
    assert len(d) == 2 and all(set(i) == ITEM_KEYS for i in d)
    blob = json.dumps(d, ensure_ascii=False)
    assert 'secret@x.test' not in blob and 'MSG_1' not in blob
    assert all('meta' not in i and 'facts' not in i for i in d)
    one = [i for i in d if i['producer'] == 'fp'][0]
    assert one['tag'] == 'وسم' and one['approve_label'] == 'اعتمد' and one['body']['text'] == 'ملاحظة مكتوبة'
    assert one['status'] == 'proposed' and one['target_label'] == 'هدف m:1'


def test_items_filters_order_and_limit(api, monkeypatch):
    seed(monkeypatch, api, fp(alone=False, kind='draft', section='people', targets=[('m:1', F1)]),
         fp(pid='n', section='content', targets=[('n:1', F2)]))
    g = lambda q: api.get('/api/v2/brain/items' + q).get_json()['items']
    assert [i['producer'] for i in g('')] == ['fp'], 'الافتراضي proposed'
    assert [i['producer'] for i in g('?status=all&section=content')] == ['n']
    assert [i['producer'] for i in g('?status=done_alone')] == ['n']
    assert g('?status=all&since=2999-01-01T00:00:00Z') == []
    assert len(g('?status=all&since=2000-01-01T00:00:00Z')) == 2
    assert api.get('/api/v2/brain/items?since=bad').status_code == 400
    assert api.get('/api/v2/brain/items?status=bogus').status_code == 400
    Item = engine._models(db)[0]
    for i in range(110):
        db.session.add(Item(id='%032x' % i, producer='zz', section='x', kind='note', target_ref='r%d' % i,
                            input_hash='h%d' % i, status='proposed', created_at=datetime.datetime.utcnow()))
    db.session.commit()
    assert len(g('?status=all')) == 100


# ───────────────────────────────────────────────────────────── الاعتماد والرفض والحذف

def _draft(monkeypatch, api, apply=None, **kw):
    seen = []

    def ap(ctx, body, target):
        seen.append({'actor': ctx.actor, 'text': body['text'], 'meta': target.meta})
        return ApplyResult(ok=True, copy_text='انسخ') if apply is None else apply(ctx, body, target)
    seed(monkeypatch, api, fp(alone=False, kind='draft', targets=[('m:1', F1, {'email': 'e@x.test'})], apply=ap, **kw))
    (r,) = rows()
    return r.id, seen


def test_approve_requires_confirmation_and_validates_text(api, monkeypatch):
    iid, seen = _draft(monkeypatch, api)
    path = '/api/v2/brain/items/%s/approve' % iid
    assert api.post(path, {}).status_code == 400
    assert api.post(path, {'confirmed': 'true'}).status_code == 400
    assert api.post(path, {'confirmed': True, 'text': '   '}).status_code == 400
    assert api.post(path, {'confirmed': True, 'text': 'ا' * 901}).status_code == 400
    assert api.post(path, {'confirmed': True, 'text': 5}).status_code == 400
    r = api.post(path, {'confirmed': True, 'text': 'هذا لا يقوّم شيئًا'})
    assert r.status_code == 400
    assert api.post('/api/v2/brain/items/%s/approve' % ('b' * 32), {'confirmed': True}).status_code == 404
    assert api.post('/api/v2/brain/items/xyz/approve', {'confirmed': True}).status_code == 400
    assert seen == [] and rows()[0].status == 'proposed'


def test_approve_actor_comes_from_the_token_and_double_approve_is_409(api, monkeypatch):
    iid, seen = _draft(monkeypatch, api)
    path = '/api/v2/brain/items/%s/approve' % iid
    r = api.post(path, {'confirmed': True, 'by': 'evil@x.test', 'decided_by': 'evil@x.test'})
    assert r.status_code == 200 and r.get_json()['copy_text'] == 'انسخ' and r.get_json()['status'] == 'approved'
    assert seen == [{'actor': ADMIN, 'text': 'ملاحظة مكتوبة', 'meta': {'email': 'e@x.test'}}]
    assert rows()[0].decided_by == ADMIN
    r2 = api.post(path, {'confirmed': True})
    assert r2.status_code == 409 and r2.get_json()['error'] == 'حُسم هذا الاقتراح من قبل' and len(seen) == 1
    assert AuditLog.query.filter_by(action='brain.approve', target=iid).count() == 1


def test_approve_with_edit(api, monkeypatch):
    iid, seen = _draft(monkeypatch, api)
    r = api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True, 'text': '  نص   معدّل \n\n\n\nسطر  '})
    assert r.status_code == 200 and r.get_json()['status'] == 'edited'
    assert seen[0]['text'] == 'نص معدّل\n\nسطر'


def test_approve_no_reply_and_failed_apply(api, monkeypatch):
    iid, _ = _draft(monkeypatch, api, apply=lambda c, b, t: ApplyResult(ok=False, no_reply=True))
    r = api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert rows()[0].status == 'unknown'
    assert api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True}).status_code == 409


def test_failed_apply_keeps_the_card_and_shows_the_error(api, monkeypatch):
    iid, _ = _draft(monkeypatch, api, apply=lambda c, b, t: ApplyResult(ok=False, error='المنصة رفضت'))
    r = api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True})
    assert r.status_code == 422 and r.get_json() == {'error': 'المنصة رفضت'}
    d = api.get('/api/v2/brain/items').get_json()['items']
    assert d[0]['status'] == 'proposed' and d[0]['last_error'] == 'المنصة رفضت'


def test_reject(api, monkeypatch):
    iid, seen = _draft(monkeypatch, api)
    path = '/api/v2/brain/items/%s/reject' % iid
    assert api.post(path, {}).status_code == 400
    r = api.post(path, {'confirmed': True, 'by': 'evil@x.test'})
    assert r.status_code == 200 and rows()[0].status == 'rejected' and rows()[0].decided_by == ADMIN
    assert api.post(path, {'confirmed': True}).status_code == 409
    assert api.post('/api/v2/brain/items/%s/approve' % iid, {'confirmed': True}).status_code == 409
    assert seen == [] and api.post('/api/v2/brain/items/%s/reject' % ('c' * 32), {'confirmed': True}).status_code == 404


def test_discard_only_done_alone_notes(api, monkeypatch):
    seed(monkeypatch, api, fp(pid='n', targets=[('n:1', F2)]),
         fp(pid='d', alone=False, kind='draft', targets=[('d:1', F1)]), opinion_producer())
    api.script.default = {'opinion': 'رأي'}
    assert engine.submit_opinion(NS, 'review', 'c1', {'tag': 'م'})[2]
    by = {r.producer: r.id for r in rows()}
    by['op'] = by['opinion']
    assert rows(producer='n')[0].status == 'done_alone'
    path = lambda i: '/api/v2/brain/items/%s/discard' % i
    assert api.post(path(by['n']), {}).status_code == 400
    assert api.post(path(by['d']), {'confirmed': True}).status_code == 409, 'المسودة المقترحة لا تُحذف من هنا'
    assert api.post(path(by['op']), {'confirmed': True}).status_code == 409, 'الرأي ليس ملاحظة'
    r = api.post(path(by['n']), {'confirmed': True})
    assert r.status_code == 200 and rows(producer='n')[0].status == 'discarded'
    assert api.post(path(by['n']), {'confirmed': True}).status_code == 409
    assert AuditLog.query.filter_by(action='brain.discard').count() == 1


# ───────────────────────────────────────────────────────────── الآراء

def test_opinion_cleans_facts_and_queues_then_returns_the_cached_item(api, monkeypatch):
    use(monkeypatch, opinion_producer())
    api.script.default = {'opinion': 'رأي قصير'}
    facts = {'tag': 'مراجعة', 'reason': 'راسل who@x.test أو 01001234567', 'password': 'p', 'age': 'يوم'}
    r = api.post('/api/v2/brain/opinion', {'kind': 'review', 'card_id': 'c1', 'facts': facts})
    assert r.status_code == 200 and r.get_json() == {'queued': True}
    (call,) = api.script.calls
    assert 'who@x.test' not in call['user'] and '01001234567' not in call['user'] and 'password' not in call['user']
    assert 'مراجعة' in call['user']
    r = api.post('/api/v2/brain/opinion', {'kind': 'review', 'card_id': 'c1', 'facts': facts})
    it = r.get_json()['item']
    assert set(it) == ITEM_KEYS and it['body']['text'] == 'رأي قصير' and it['status'] == 'done_alone'
    assert len(api.script.calls) == 1
    st = rows(producer='opinion')[0]
    assert 'who@x.test' not in st.facts_json and 'password' not in st.facts_json


def test_opinion_big_facts_and_bad_shapes(api, monkeypatch, spy_ai):
    use(monkeypatch, opinion_producer())
    big = {'facts': ['x' * 2000, 'y' * 2000]}
    r = api.post('/api/v2/brain/opinion', {'kind': 'review', 'card_id': 'c1', 'facts': big})
    assert r.status_code == 400
    for body in ({}, {'kind': 'review'}, {'kind': 'review', 'card_id': 'c', 'facts': []},
                 {'kind': 5, 'card_id': 'c', 'facts': {}}, {'kind': 'review', 'card_id': '', 'facts': {}}):
        assert api.post('/api/v2/brain/opinion', body).status_code == 400, body
    assert spy_ai == []


def test_opinion_reasons(api, monkeypatch):
    use(monkeypatch, opinion_producer())
    post = lambda kind='review', cid='c1': api.post('/api/v2/brain/opinion',
                                                    {'kind': kind, 'card_id': cid, 'facts': {'tag': 'م'}}).get_json()
    assert post('file_waiting') == {'item': None, 'reason': 'not_supported'}
    assert post('zzz') == {'item': None, 'reason': 'not_supported'}
    monkeypatch.setenv('DASH_BRAIN_OPINION_CAP', '0')
    assert post() == {'item': None, 'reason': 'cap'}
    monkeypatch.delenv('DASH_BRAIN_OPINION_CAP')
    monkeypatch.delenv('ANTHROPIC_API_KEY')
    assert post() == {'item': None, 'reason': 'no_writer'}
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'k')
    Switch = engine._models(db)[1]
    db.session.add(Switch(producer='opinion', mode='off'))
    db.session.commit()
    assert post() == {'item': None, 'reason': 'off'}
    assert api.script.calls == []
    use(monkeypatch)       # لا منتج رأي مسجّل
    assert post() == {'item': None, 'reason': 'not_supported'}


def test_lookup_returns_cached_items_only(api, monkeypatch):
    use(monkeypatch, opinion_producer())
    api.script.default = {'opinion': 'رأي'}
    f = {'tag': 'م'}
    api.post('/api/v2/brain/opinion', {'kind': 'review', 'card_id': 'c1', 'facts': f})
    calls_before = len(api.script.calls)
    seen = []
    monkeypatch.setattr(appmod, 'ai_call', lambda *a, **k: seen.append(1) or (_ for _ in ()).throw(AssertionError('x')))
    cards = [{'kind': 'review', 'card_id': 'c1', 'facts': f},
             {'kind': 'review', 'card_id': 'c2', 'facts': f},
             {'kind': 'file_waiting', 'card_id': 'c3', 'facts': f},
             'garbage']
    before = rows()
    r = api.post('/api/v2/brain/opinions/lookup', {'cards': cards})
    items = r.get_json()['items']
    assert r.status_code == 200 and items['c1']['body']['text'] == 'رأي' and set(items['c1']) == ITEM_KEYS
    assert items['c2'] is None and items['c3'] is None
    changed = api.post('/api/v2/brain/opinions/lookup', {'cards': [{'kind': 'review', 'card_id': 'c1', 'facts': {'tag': 'تغيّرت'}}]})
    assert changed.get_json() == {'items': {'c1': None}}, 'تغيّرت البيانات ⇒ لا رأي قديم'
    assert seen == [] and len(api.script.calls) == calls_before and len(rows()) == len(before)


def test_lookup_limits(api, monkeypatch):
    use(monkeypatch, opinion_producer())
    cards = [{'kind': 'review', 'card_id': 'c%d' % i, 'facts': {}} for i in range(41)]
    assert api.post('/api/v2/brain/opinions/lookup', {'cards': cards}).status_code == 400
    assert api.post('/api/v2/brain/opinions/lookup', {'cards': cards[:40]}).status_code == 200
    assert api.post('/api/v2/brain/opinions/lookup', {'cards': 'x'}).status_code == 400
    assert api.post('/api/v2/brain/opinions/lookup', {'cards': []}).get_json() == {'items': {}}


# ───────────────────────────────────────────────────────────── الجولة

def test_run_endpoint(api, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]), fp(pid='two', targets=[('b:1', F2)]))
    assert api.post('/api/v2/brain/run', {}).status_code == 400
    assert api.post('/api/v2/brain/run', {'confirmed': True, 'only': 'nope'}).status_code == 400
    assert api.post('/api/v2/brain/run', {'confirmed': True, 'only': 5}).status_code == 400
    assert rows() == []
    r = api.post('/api/v2/brain/run', {'confirmed': True, 'only': 'two', 'by': 'evil@x.test'})
    assert r.status_code == 202
    run = engine._models(db)[2].query.get(r.get_json()['run_id'])
    assert run.trigger == 'admin' and run.by == ADMIN
    assert [x.producer for x in rows()] == ['two']
    latest = api.get('/api/v2/brain/runs/latest').get_json()
    lr = latest['run']
    assert set(latest) == {'run'} and lr['id'] == run.id and lr['active'] is False
    assert lr['ai_calls'] == 1 and lr['items'] == 1 and lr['trigger'] == 'admin' and lr['finished_at']


def test_run_lock_and_runs_latest_empty(api, monkeypatch):
    assert api.get('/api/v2/brain/runs/latest').get_json() == {'run': None}
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    Run = engine._models(db)[2]
    db.session.add(Run(id='f' * 32, trigger='admin', started_at=datetime.datetime.utcnow()))
    db.session.commit()
    r = api.post('/api/v2/brain/run', {'confirmed': True})
    assert r.status_code == 409 and r.get_json()['error'] == 'العقل يكتب الآن. جرّب بعد قليل'
    assert api.get('/api/v2/brain/runs/latest').get_json()['run']['active'] is True
    assert rows() == [] and api.script.calls == []
    Run.query.update({'started_at': datetime.datetime.utcnow() - datetime.timedelta(minutes=16)})
    db.session.commit()
    assert api.post('/api/v2/brain/run', {'confirmed': True}).status_code == 202


def test_kill_switch_on_run_endpoint(api, monkeypatch):
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    monkeypatch.setenv('DASH_BRAIN_WRITE', '0')
    r = api.post('/api/v2/brain/run', {'confirmed': True})
    assert r.status_code == 409 and rows() == [] and api.script.calls == []


# ───────────────────────────────────────────────────────────── الكرون: kick لا ينتظر

def test_kick_is_non_blocking_and_swallows_failures(api, monkeypatch):
    calls = []
    monkeypatch.setattr(engine, 'start_run', lambda ns, trig, actor, only=None: calls.append((trig, actor)) or (202, {'run_id': 'r'}))
    assert v2_brain2_routes.kick(NS, 'cron') == 'r' and calls == [('cron', 'cron')]
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert v2_brain2_routes.kick(NS, 'cron') is None and len(calls) == 1
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    monkeypatch.setenv('DASH_BRAIN_WRITE', '0')
    assert v2_brain2_routes.kick(NS, 'cron') is None and len(calls) == 1
    monkeypatch.delenv('DASH_BRAIN_WRITE')

    def boom(*a, **k):
        raise RuntimeError('x')
    monkeypatch.setattr(engine, 'start_run', boom)
    assert v2_brain2_routes.kick(NS, 'cron') is None


def test_kick_does_not_wait_for_the_worker(api, monkeypatch):
    """خارج الوضع المضمّن، kick يرجع قبل أي نداء ذكاء: الكتابة في الخيط الخلفي."""
    import queue
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', False)
    monkeypatch.setattr(engine, '_Q', queue.Queue(maxsize=8))
    monkeypatch.setattr(engine, '_PENDING', set())

    class Alive(object):
        def is_alive(self):
            return True
    monkeypatch.setitem(engine._WORKER, 'thread', Alive())
    use(monkeypatch, fp(targets=[('a:1', F1)]))
    assert v2_brain2_routes.kick(NS, 'cron')
    assert api.script.calls == [] and rows() == []


def test_agents_run_cron_calls_the_brain_kick(api, monkeypatch):
    kicks = []
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, '_run_agent', lambda aid: None)
    monkeypatch.setattr(appmod, '_v2_brain2_kick', lambda trig='cron': kicks.append(trig))
    r = flask_app.test_client().post('/api/ai/agents/run-cron', headers={'X-ELP-Metrics-Secret': SECRET}, json={})
    assert r.status_code == 200 and kicks == ['cron']
    assert flask_app.test_client().post('/api/ai/agents/run-cron', json={}).status_code == 401 and kicks == ['cron']


# ───────────────────────────────────────────────────────────── النموذج والمفتاح (§2.6)

@pytest.fixture()
def clean_model_env(monkeypatch):
    for k in ('ANTHROPIC_MODEL', 'DASHBOARD_AI_MODEL', 'DEEPSEEK_MODEL', 'OPENAI_MODEL'):
        monkeypatch.delenv(k, raising=False)


def test_anthropic_default_and_models_list(clean_model_env):
    cfg = appmod.AI_PROVIDERS['anthropic']
    assert cfg['default_model'] == 'claude-sonnet-5-5'
    assert cfg['models'] == ['claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-5-5']
    assert appmod.ai_model_for('anthropic') == 'claude-sonnet-5-5'


def test_model_env_override_works(clean_model_env, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-opus-5-5')
    assert appmod.ai_model_for('anthropic') == 'claude-opus-5-5'
    monkeypatch.setenv('DASHBOARD_AI_MODEL', 'claude-haiku-5-5')
    assert appmod.ai_model_for('anthropic') == 'claude-haiku-5-5'


@pytest.mark.parametrize('retired', ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'])
def test_retired_claude_names_are_ignored(clean_model_env, monkeypatch, retired):
    assert retired in appmod.AI_RETIRED_MODELS
    monkeypatch.setenv('ANTHROPIC_MODEL', retired)
    assert appmod.ai_model_for('anthropic') == 'claude-sonnet-5-5'
    monkeypatch.setenv('DASHBOARD_AI_MODEL', retired)
    assert appmod.ai_model_for('anthropic') == 'claude-sonnet-5-5'


def test_dashboard_model_with_a_mismatched_prefix_is_ignored(clean_model_env, monkeypatch):
    monkeypatch.setenv('DASHBOARD_AI_MODEL', 'deepseek-v4-flash')
    assert appmod.ai_model_for('anthropic') == 'claude-sonnet-5-5'
    monkeypatch.setenv('ANTHROPIC_MODEL', 'claude-opus-5-5')
    assert appmod.ai_model_for('anthropic') == 'claude-opus-5-5', 'يرجع لإعداد المزوّد نفسه'
    monkeypatch.setenv('DASHBOARD_AI_MODEL', 'claude-sonnet-5-5')
    assert appmod.ai_model_for('deepseek') == 'deepseek-v4-flash'
    monkeypatch.setenv('DASHBOARD_AI_MODEL', 'gpt-4.1')
    assert appmod.ai_model_for('deepseek') == 'deepseek-v4-flash'
    assert appmod.ai_model_for('openai') == 'gpt-4.1'
    monkeypatch.setenv('DASHBOARD_AI_MODEL', 'deepseek-v4-pro')
    assert appmod.ai_model_for('deepseek') == 'deepseek-v4-pro'


def test_call_anthropic_sends_the_resolved_model_and_no_temperature(clean_model_env, monkeypatch):
    sent = {}

    class R:
        status_code = 200
        raise_for_status = staticmethod(lambda: None)
        json = staticmethod(lambda: {'content': [{'type': 'text', 'text': 'x'}]})
    monkeypatch.setattr(appmod.requests, 'post', lambda url, **kw: sent.update(kw['json']) or R())
    assert appmod.call_anthropic('k', appmod.ai_model_for('anthropic'), 's', 'u') == 'x'
    assert sent['model'] == 'claude-sonnet-5-5' and 'temperature' not in sent and sent['max_tokens'] == 8000


def test_compose_and_env_example_have_the_new_default():
    compose = open(os.path.join(ROOT, 'docker-compose.yml'), encoding='utf-8').read()
    assert 'ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-claude-sonnet-5-5}' in compose
    assert 'claude-sonnet-4-20250514' not in compose
    envex = open(os.path.join(ROOT, 'backend', '.env.example'), encoding='utf-8').read()
    assert 'ANTHROPIC_MODEL=claude-sonnet-5-5' in envex and 'claude-sonnet-4-20250514' not in envex


def test_visible_arabic_copy_rules():
    """النصوص العربية التي يراها المؤسس من المحرّك والمسارات: بلا «يقوّم» ولا كلمات تقنية ولا اسم مزوّد."""
    texts = [engine.ERR_DECIDED, engine.ERR_RUNNING, engine.ERR_WRITE_OFF, engine.ERR_NO_REPLY, engine.ERR_APPLY_FAILED,
             engine.ERR_WRITE_FAILED, engine.ERR_INVALID_OUTPUT, engine.SYSTEM_AR]
    texts += [getattr(v2_brain2_routes, n) for n in dir(v2_brain2_routes) if n.startswith('ERR_')]
    for t in texts:
        assert not engine.has_banned(t)
        for bad in ('API', 'JSON', 'Claude', 'DeepSeek', 'OpenAI', 'Anthropic', 'null', 'undefined', '⇒', '✓', 'اعكس'):
            if t is not engine.SYSTEM_AR:
                assert bad not in t, (bad, t)


# ───────────────────────────────────────────────────────────── جولة الإصلاح

def test_approve_rejects_a_text_edit_on_proposals_that_carry_site_edits(api, monkeypatch):
    seen = []
    edits = [{'path': 'b1', 'old': 'قديم', 'new': 'جديد', 'why': 'قرار'}]
    seed(monkeypatch, api, fp(pid='site_review', alone=False, kind='draft', section='content',
                              targets=[('site:p', F1, {'page': 'pricing.html'})],
                              validate=lambda d, t: {'text': 'ملخص', 'edits': edits},
                              apply=lambda c, b, t: seen.append(b) or ApplyResult(ok=True)))
    (r,) = rows()
    path = '/api/v2/brain/items/%s/approve' % r.id
    res = api.post(path, {'text': 'نص معدّل', 'confirmed': True})
    assert res.status_code == 400
    assert res.get_json()['error'] == 'لا يُعدّل نص هذا الاقتراح هنا؛ افتح الموقع وعدّل الكتلة نفسها'
    assert seen == [] and rows()[0].status == 'proposed', 'لا تنفيذ ولا تغيير حالة'
    ok = api.post(path, {'confirmed': True})                      # الاعتماد بلا تعديل نص يعمل
    assert ok.status_code == 200 and seen and seen[0]['edits'] == edits


def test_list_sweeps_stale_applying_rows_to_unknown(api, monkeypatch):
    use(monkeypatch)
    Item = engine._models(db)[0]
    now = datetime.datetime.utcnow()
    db.session.add(Item(id='1' * 32, producer='zz', section='x', kind='draft', target_ref='r1', input_hash='h1', status='applying',
                        created_at=now, decided_at=now - datetime.timedelta(minutes=12)))
    db.session.add(Item(id='2' * 32, producer='zz', section='x', kind='draft', target_ref='r2', input_hash='h2', status='applying',
                        created_at=now, decided_at=now - datetime.timedelta(minutes=2)))
    db.session.commit()
    items = {i['id']: i for i in api.get('/api/v2/brain/items?status=all').get_json()['items']}
    assert items['1' * 32]['status'] == 'unknown'
    assert items['1' * 32]['last_error'] == 'لم نتأكد من نتيجة التنفيذ؛ راجع ما حدث قبل إعادة المحاولة'
    assert items['2' * 32]['status'] == 'applying'


@pytest.mark.parametrize('route', ['approve', 'reject'])
def test_approve_and_reject_also_sweep_first(api, monkeypatch, route):
    seed(monkeypatch, api, fp(alone=False, kind='draft', targets=[('m:1', F1)]))
    Item = engine._models(db)[0]
    db.session.add(Item(id='3' * 32, producer='zz', section='x', kind='draft', target_ref='r3', input_hash='h3', status='applying',
                        created_at=datetime.datetime.utcnow(), decided_at=datetime.datetime.utcnow() - datetime.timedelta(minutes=30)))
    db.session.commit()
    (r,) = [x for x in rows() if x.producer == 'fp']
    api.post('/api/v2/brain/items/%s/%s' % (r.id, route), {'confirmed': True})
    db.session.expire_all()
    assert Item.query.get('3' * 32).status == 'unknown'


# ----- مرسل رسالة الموقع (للمنصة فقط)

SENDER = '/api/v2/brain/site-message/%s/sender'
MSG_SECRET = 'test-metrics-secret'


@pytest.fixture()
def sender_env(env, monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', MSG_SECRET)
    m = appmod.Message(name='سمر عبد الله', email='  Samar.Test@Example.COM ', body='نص خاص جدًا', topic='موضوع')
    db.session.add(m)
    db.session.commit()
    yield m.id
    appmod.Message.query.filter_by(id=m.id).delete()
    db.session.commit()


def _sender(mid, secret=MSG_SECRET):
    heads = {'X-ELP-Metrics-Secret': secret} if secret is not None else {}
    return flask_app.test_client().get(SENDER % mid, headers=heads)


def test_site_message_sender_returns_only_the_lowercased_email(sender_env):
    r = _sender(sender_env)
    assert r.status_code == 200 and r.get_json() == {'email': 'samar.test@example.com'}
    assert r.headers.get('Cache-Control') == 'no-store'
    blob = r.get_data(as_text=True)
    assert 'سمر' not in blob and 'نص خاص' not in blob


def test_site_message_sender_auth_is_the_secret_only(sender_env, api):
    assert _sender(sender_env, secret=None).status_code == 401
    assert _sender(sender_env, secret='wrong').status_code == 401
    r = flask_app.test_client().get(SENDER % sender_env, headers=dict(api.heads['admin']))
    assert r.status_code == 401, 'توكن الأدمن لا يكفي'
    appmod.PLATFORM_METRICS_SECRET = ''
    try:
        assert _sender(sender_env, secret='').status_code == 401, 'سرّ غير مضبوط ⇒ رفض'
    finally:
        appmod.PLATFORM_METRICS_SECRET = MSG_SECRET


def test_site_message_sender_flag_off_is_404_before_the_secret_check(sender_env, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    for secret in (MSG_SECRET, 'wrong', None):
        r = _sender(sender_env, secret=secret)
        assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'


def test_site_message_sender_not_found_and_bad_ids(sender_env):
    assert _sender(sender_env + 100000).status_code == 404
    assert _sender(sender_env + 100000).get_json() == {'error': 'not_found'}
    for bad in ('abc', '1a', '-1', '1.5', '١٢٣', '1' * 20, '%20', '0x10'):
        assert _sender(bad).status_code == 404, bad
