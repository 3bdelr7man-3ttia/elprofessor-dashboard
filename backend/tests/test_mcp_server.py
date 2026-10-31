# -*- coding: utf-8 -*-
"""اللوحة كخادم MCP (SPEC-B B5a) · `POST /api/mcp` + رموز الدخول في مسارات الإدارة.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_mcp_server.py

⛔ صفر شبكة وصفر نداء ذكاء: `requests.*` ترمي (تجهيز `env`)، و`_platform_proxy` بديل محلي بدورات فيها بيانات أشخاص لإثبات أنها لا تخرج.
"""
import datetime
import hashlib
import json
import os
import re
import types

import pytest

import app as appmod
import mcp_server
import v2_reports_routes
from app import app as flask_app, db, AuditLog, Article
from brain2 import engine, registry

from test_brain2_engine import env   # noqa: F401  (fixture)
from test_brain2_routes import api, NON_ADMIN   # noqa: F401  (fixture)

NS = appmod.__dict__
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MCP = '/api/mcp'
TOKENS = '/api/v2/brain/mcp-tokens'
PHONE = '01012345678'
EMAIL = 'ahmed.customer@example.com'
HDR = {'Content-Type': 'application/json'}
REPLY_LABEL = registry.by_id('reply_draft').label


@pytest.fixture(autouse=True)
def clean(env):   # noqa: F811
    Token = mcp_server._models(db)
    Token.query.delete()
    db.session.commit()
    mcp_server.reset_limits()
    yield
    db.session.rollback()
    Token.query.delete()
    db.session.commit()
    mcp_server.reset_limits()


def mint(name='madar', scopes='read'):
    """رمز مباشرة في القاعدة ⇒ (نص صريح، صف)."""
    raw, h = mcp_server.new_token()
    row = mcp_server._models(db)(id=os.urandom(16).hex(), name=name, hash=h, scopes=scopes, created_by='founder@x.test',
                                 created_at=datetime.datetime.utcnow())
    db.session.add(row)
    db.session.commit()
    return raw, row


class Rpc(object):
    def __init__(self):
        self.c = flask_app.test_client()
        self._id = 0

    def post(self, token, payload, headers=None, raw=None):
        h = dict(HDR)
        if token:
            h['Authorization'] = 'Bearer ' + token
        h.update(headers or {})
        if raw is not None:
            return self.c.post(MCP, data=raw, headers=h)
        return self.c.post(MCP, data=json.dumps(payload), headers=h)

    def call(self, token, method, params=None):
        self._id += 1
        msg = {'jsonrpc': '2.0', 'id': self._id, 'method': method}
        if params is not None:
            msg['params'] = params
        return self.post(token, msg)

    def tool(self, token, name, args=None):
        return self.call(token, 'tools/call', {'name': name, 'arguments': args if args is not None else {}})


@pytest.fixture()
def rpc():
    return Rpc()


def result_of(resp):
    body = resp.get_json()
    assert 'error' not in body, body
    return body['result']


def data_of(resp):
    res = result_of(resp)
    assert res['isError'] is False, res
    return res['structuredContent']


def assert_clean(o):
    """لا بريد ولا هاتف ولا مبلغ ولا اسم عميل في أي مكان من المخرج."""
    txt = re.sub(r'[0-9a-f]{32}', 'ID', json.dumps(o, ensure_ascii=False))     # المعرّفات سداسية عشرية وليست أرقامًا
    assert '@' not in txt, txt
    for run in re.findall(r'\d+', txt):
        assert len(run) < 7, 'رقم طويل: ' + run
    assert not re.search(r'(?:جنيه|دولار|ريال|EGP|USD|[$€£])', txt), txt
    assert 'أحمد' not in txt and 'ahmed' not in txt.lower() and PHONE not in txt


# ───────────────────────────────────────────────────────────── بيانات مزروعة (فيها بيانات أشخاص)

def seed_items():
    Item = engine._models(db)[0]
    now = datetime.datetime.utcnow()

    def add(producer, section, kind, label, text, status='proposed', hours=5):
        db.session.add(Item(
            id=os.urandom(16).hex(), producer=producer, section=section, kind=kind, target_ref='r-%s-%s' % (producer, os.urandom(3).hex()),
            target_label=label, input_hash=os.urandom(16).hex(), facts_json='{}', meta_json='{}', body_json=json.dumps({'text': text}, ensure_ascii=False),
            status=status, source='ai', mode='ask', created_at=now - datetime.timedelta(hours=hours)))
    add('reply_draft', 'people', 'draft', 'رد على أحمد محمود %s %s' % (EMAIL, PHONE), 'مرحبًا أحمد، دفعت 500 جنيه، اتصل على %s أو %s' % (PHONE, EMAIL))
    add('course_review', 'courses', 'draft', 'دورة التسويق للمحامين', 'ينقصها وصف للمخرجات. تواصل: %s' % EMAIL)
    add('campaign_comment', 'marketing', 'note', 'حملة الخريف', 'أنفقت الحملة 1200 جنيه', status='done_alone')
    add('opinion_card', 'home', 'opinion', 'بطاقة أحمد محمود', 'رأي عن أحمد 900 دولار', status='done_alone')
    db.session.commit()


def fake_platform(monkeypatch, courses):
    def proxy(method, path, params=None, json_body=None, timeout=12):
        return appmod.jsonify({'courses': courses})
    monkeypatch.setattr(appmod, '_platform_proxy', proxy)


COURSES = [
    {'id': 'c1', 'slug': 'marketing-101', 'title': 'أساسيات التسويق', 'type': 'recorded_paid', 'level': 'مبتدئ', 'lesson_count': 12, 'is_active': True,
     'approval_status': 'approved', 'price_amount': 450.0, 'price_currency': 'EGP', 'total_enrolled': 33, 'instructor_name': 'أحمد محمود',
     'instructor_email': EMAIL, 'short_description': 'دورة عملية. للتواصل ' + EMAIL},
    {'id': 'c2', 'slug': 'hidden', 'title': 'دورة مخفية', 'approval_status': 'approved', 'is_active': False},
    {'id': 'c3', 'slug': 'pend', 'title': 'دورة قيد المراجعة', 'approval_status': 'pending', 'is_active': False},
]


def seed_articles():
    now = datetime.datetime.utcnow()
    Article.query.delete()
    db.session.add(Article(title='كيف تسوّق لمكتب محاماة', status='published', published_at=now - datetime.timedelta(days=1), created_at=now, slug='law-marketing'))
    db.session.add(Article(title='قديم جدًا', status='published', published_at=now - datetime.timedelta(days=60), created_at=now, slug='old-one'))
    db.session.add(Article(title='مسودة', status='draft', created_at=now, slug='draft-one'))
    db.session.commit()


def weekly_payload():
    return ({'week': {'label': '١٨ أكتوبر – ٢٤ أكتوبر', 'start': '2026-10-18', 'end': '2026-10-24'},
             'funnel': {'stages': [{'label': 'زاروا المنصة', 'cur': 1200, 'change_text': '+٢٠٪'}, {'label': 'دفعوا', 'cur': None}]},
             'sections': [{'label': 'الملفات', 'value': {'kind': 'money', 'egp': 5000, 'count': 7, 'text': '٥٠٠٠ جنيه مصري'}},
                          {'label': 'المحتوى', 'value': {'kind': 'count', 'n': 3, 'text': '٣ مقالات نُشرت'}}],
             'brain': [{'label': 'الدخل', 'text': 'الدخل ٥٠٠٠ جنيه'}, {'label': 'الزيارات', 'text': 'الزيارات زادت'},
                       {'label': 'تواصل', 'text': 'اتصل %s %s' % (PHONE, EMAIL)}]}, None)


# ───────────────────────────────────────────────────────────── الباب: المفتاح · الطريقة · الدخول

def test_flag_off_is_404_for_every_method(rpc, monkeypatch):
    raw, _ = mint()
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert rpc.call(raw, 'ping').status_code == 404
    assert rpc.call(None, 'ping').status_code == 404
    assert rpc.c.get(MCP).status_code == 404


def test_get_is_405_and_nothing_is_streamed(rpc):
    r = rpc.c.get(MCP)
    assert r.status_code == 405 and r.headers['Allow'] == 'POST' and r.headers['Cache-Control'] == 'no-store'
    assert 'text/event-stream' not in r.headers.get('Content-Type', '')


def test_missing_invalid_and_revoked_token_are_401_jsonrpc(rpc):
    raw, row = mint()
    for tok in (None, 'nonsense', raw + 'x', raw[:-2]):
        r = rpc.call(tok, 'ping')
        assert r.status_code == 401 and r.headers['WWW-Authenticate'].startswith('Bearer'), tok
        b = r.get_json()
        assert b['jsonrpc'] == '2.0' and b['id'] is None and b['error']['code'] == mcp_server.E_AUTH and 'result' not in b
    assert rpc.call(raw, 'ping').status_code == 200
    row.revoked_at = datetime.datetime.utcnow()
    db.session.commit()
    r = rpc.call(raw, 'ping')
    assert r.status_code == 401 and r.get_json()['error']['code'] == mcp_server.E_AUTH


def test_admin_jwt_is_not_a_mcp_token(rpc, api):
    r = rpc.c.post(MCP, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}), headers=dict(api.heads['admin'], **HDR))
    assert r.status_code == 401, 'لا يمرّ من JWT الأدمن'


def test_bad_json_batch_and_shape(rpc):
    raw, _ = mint()
    assert rpc.post(raw, None, raw=b'{not json').get_json()['error']['code'] == mcp_server.E_PARSE
    r = rpc.post(raw, [{'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}])
    assert r.status_code == 400 and r.get_json()['error']['code'] == mcp_server.E_REQUEST
    for bad in ({'id': 1, 'method': 'ping'}, {'jsonrpc': '2.0', 'id': 1}, {'jsonrpc': '2.0', 'id': True, 'method': 'ping'}, 'text', 5):
        assert rpc.post(raw, bad).get_json()['error']['code'] == mcp_server.E_REQUEST, bad
    assert rpc.post(raw, None, raw=b'x' * (mcp_server.BODY_MAX + 1)).status_code == 413
    assert rpc.call(raw, 'tools/call', ['x']).get_json()['error']['code'] == mcp_server.E_PARAMS


# ───────────────────────────────────────────────────────────── المصافحة والقائمة

def test_handshake_initialize_initialized_ping(rpc):
    raw, _ = mint()
    r = rpc.call(raw, 'initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'x', 'version': '1'}})
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store' and r.headers['Content-Type'].startswith('application/json')
    b = r.get_json()
    assert b['jsonrpc'] == '2.0' and b['id'] == 1
    assert b['result']['protocolVersion'] == '2025-06-18' and 'tools' in b['result']['capabilities']
    assert b['result']['serverInfo']['name'] == 'elprofessor-dashboard'
    n = rpc.post(raw, {'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    assert n.status_code == 202 and n.get_data() == b'' and n.headers['Cache-Control'] == 'no-store'
    assert rpc.call(raw, 'ping').get_json() == {'jsonrpc': '2.0', 'id': 2, 'result': {}}
    e = rpc.call(raw, 'resources/list').get_json()
    assert e['error']['code'] == mcp_server.E_METHOD and e['id'] == 3


def test_tools_list_depends_on_scope_and_has_schemas(rpc):
    r_raw, _ = mint('reader', 'read')
    p_raw, _ = mint('proposer', 'read,propose')
    names = lambda raw: [t['name'] for t in result_of(rpc.call(raw, 'tools/list'))['tools']]
    assert names(r_raw) == ['business_summary', 'decisions_waiting', 'brain_items', 'reports_weekly', 'content_published', 'courses_catalog']
    assert names(p_raw) == names(r_raw) + ['propose_note', 'propose_campaign_idea']
    for t in result_of(rpc.call(p_raw, 'tools/list'))['tools']:
        assert t['description'] and t['inputSchema']['type'] == 'object' and t['inputSchema']['additionalProperties'] is False
    bad = {'approve', 'send', 'pay', 'refund', 'delete', 'reject', 'apply', 'run'}
    assert not any(any(b in n.split('_') for b in bad) for n in names(p_raw)), 'لا أداة تعتمد أو ترسل أو تنشر أو تلمس مالًا'
    assert set(names(p_raw)) <= set(mcp_server.TOOLS) and len(names(p_raw)) == 8
    assert rpc.tool(p_raw, 'approve_item', {}).get_json()['error']['code'] == mcp_server.E_PARAMS


# ───────────────────────────────────────────────────────────── أدوات القراءة: لا بريد ولا هاتف ولا مبلغ

def test_every_read_tool_output_is_clean(rpc, monkeypatch):
    seed_items()
    seed_articles()
    fake_platform(monkeypatch, COURSES)
    monkeypatch.setattr(v2_reports_routes, 'weekly_for', lambda G, w: weekly_payload())
    raw, _ = mint()
    outs = {}
    for name in ('business_summary', 'decisions_waiting', 'brain_items', 'reports_weekly', 'content_published', 'courses_catalog'):
        resp = rpc.tool(raw, name)
        assert resp.status_code == 200
        res = result_of(resp)
        assert res['isError'] is False and json.loads(res['content'][0]['text']) == res['structuredContent']
        outs[name] = res['structuredContent']
        assert_clean(res)
    s = outs['business_summary']
    assert s['brain']['waiting_total'] == 2 and s['brain']['waiting_by_section'] == {'people': 1, 'courses': 1}
    assert s['content'] == {'published': 2, 'drafts': 1} and s['courses'] == {'total': 3, 'by_approval': {'approved': 2, 'pending': 1}}
    d = outs['decisions_waiting']
    assert d['count'] == 2 and {i['title'] for i in d['items']} == {'دورة التسويق للمحامين', REPLY_LABEL}, 'عنوان عام لما قد يحمل اسمًا'
    assert all(set(i) == {'kind', 'section', 'title', 'age_hours'} and i['age_hours'] >= 4 for i in d['items'])
    bi = outs['brain_items']
    texts = {i['title']: i.get('text') for i in bi['items']}
    assert REPLY_LABEL in texts and texts[REPLY_LABEL] is None, 'نص مسودة الرد لا يخرج أبدًا'
    assert 'ينقصها وصف للمخرجات' in texts['دورة التسويق للمحامين']
    w = outs['reports_weekly']
    assert w['available'] is True and w['week'] and 'زاروا المنصة: ١٬٢٠٠' not in json.dumps(w)
    assert any('المحتوى' in x for x in w['lines']) and any('الزيارات زادت' in x for x in w['lines'])
    assert not any('الدخل' in x for x in w['lines']), 'سطر فيه مبلغ يسقط كله'
    c = outs['content_published']
    assert [i['title'] for i in c['items']] == ['كيف تسوّق لمكتب محاماة'] and c['items'][0]['url'].startswith('https://')
    cc = outs['courses_catalog']
    assert cc['count'] == 1 and cc['items'][0]['title'] == 'أساسيات التسويق' and set(cc['items'][0]) == {'title', 'slug', 'type', 'level', 'lessons', 'summary'}


def test_read_tools_report_unavailable_instead_of_empty(rpc, monkeypatch):
    def down(*a, **k):
        return appmod.jsonify({'error': 'x'}), 502
    monkeypatch.setattr(appmod, '_platform_proxy', down)
    monkeypatch.setattr(v2_reports_routes, 'weekly_for', lambda G, w: (None, 'down'))
    raw, _ = mint()
    assert data_of(rpc.tool(raw, 'courses_catalog')) == {'available': False, 'message': 'غير متاح بعد'}
    assert data_of(rpc.tool(raw, 'reports_weekly'))['available'] is False
    assert data_of(rpc.tool(raw, 'business_summary'))['courses'] == 'غير متاح بعد'


def test_args_are_validated(rpc):
    raw, _ = mint()
    for name, args in (('brain_items', {'limit': 0}), ('brain_items', {'limit': 99}), ('brain_items', {'section': 'nope'}), ('brain_items', {'status': 'x'}),
                       ('brain_items', {'extra': 1}), ('content_published', {'days': 40}), ('content_published', {'days': True}), ('business_summary', {'a': 1})):
        r = rpc.tool(raw, name, args)
        assert r.get_json()['error']['code'] == mcp_server.E_PARAMS, (name, args)
    ok = data_of(rpc.tool(raw, 'brain_items', {'status': 'all', 'section': 'courses', 'limit': 5}))
    assert ok['count'] == 0


def test_tool_failure_is_a_clean_internal_error(rpc, monkeypatch):
    raw, _ = mint()
    monkeypatch.setitem(mcp_server.TOOLS['business_summary'], 'fn', lambda ns, a: (_ for _ in ()).throw(RuntimeError('boom ' + PHONE)))
    r = rpc.tool(raw, 'business_summary')
    b = r.get_json()
    assert b['error']['code'] == mcp_server.E_INTERNAL and PHONE not in json.dumps(b) and 'boom' not in json.dumps(b)


# ───────────────────────────────────────────────────────────── أدوات الاقتراح

def test_propose_needs_propose_scope(rpc):
    raw, _ = mint('reader', 'read')
    for name, args in (('propose_note', {'section': 'content', 'title': 'عنوان', 'text': 'نص'}), ('propose_campaign_idea', {'title': 'فكرة', 'text': 'نص'})):
        b = rpc.tool(raw, name, args).get_json()
        assert b['error']['code'] == mcp_server.E_SCOPE
    Item = engine._models(db)[0]
    assert Item.query.count() == 0


def test_propose_creates_a_proposed_note_and_nothing_else(rpc):
    raw, tok = mint('طرف خارجي', 'read,propose')
    d = data_of(rpc.tool(raw, 'propose_note', {'section': 'content', 'title': 'أضيفوا مقالًا عن العقود', 'text': 'اقتراح: مقال عن العقود الذكية.'}))
    assert d['ok'] is True and d['status'] == 'proposed'
    Item = engine._models(db)[0]
    row = Item.query.get(d['id'])
    assert (row.producer, row.kind, row.status, row.section, row.source) == ('mcp:طرف خارجي', 'note', 'proposed', 'content', 'external')
    assert json.loads(row.body_json)['text'] == 'اقتراح: مقال عن العقود الذكية.' and row.target_label == 'أضيفوا مقالًا عن العقود'
    c = data_of(rpc.tool(raw, 'propose_campaign_idea', {'title': 'حملة الشتاء', 'text': 'حملة قصيرة على الدورات.'}))
    assert Item.query.get(c['id']).section == 'marketing'
    assert Item.query.count() == 2 and Item.query.filter(Item.status != 'proposed').count() == 0
    again = result_of(rpc.tool(raw, 'propose_note', {'section': 'content', 'title': 'أضيفوا مقالًا عن العقود', 'text': 'اقتراح: مقال عن العقود الذكية.'}))
    assert again['isError'] is True and again['structuredContent']['reason'] == 'exists' and Item.query.count() == 2


def test_propose_checks_length_banned_word_and_section(rpc):
    raw, _ = mint('x', 'read,propose')
    Item = engine._models(db)[0]
    bad = [{'section': 'content', 'title': 'عنوان', 'text': 'هذا يقوّم الأداء'},
           {'section': 'content', 'title': 'عنوان ' + 'ي' * 10, 'text': 'ن' * 601}]
    res = result_of(rpc.tool(raw, 'propose_note', bad[0]))
    assert res['isError'] is True and res['structuredContent']['reason'] == 'banned'
    assert rpc.tool(raw, 'propose_note', bad[1]).get_json()['error']['code'] == mcp_server.E_PARAMS
    assert rpc.tool(raw, 'propose_note', {'section': 'money', 'title': 'a', 'text': 'b'}).get_json()['error']['code'] == mcp_server.E_PARAMS
    assert engine.store_external_note(NS, 'mcp:x', 'content', 'عنوان', 'ن' * 601, 'a') == (None, 'long')
    assert engine.store_external_note(NS, 'other', 'content', 'عنوان', 'نص', 'a') == (None, 'bad')
    assert engine.store_external_note(NS, 'mcp:x', 'money', 'عنوان', 'نص', 'a') == (None, 'section')
    assert Item.query.count() == 0


def test_open_external_proposals_are_capped(rpc, monkeypatch):
    raw, _ = mint('x', 'read,propose')
    monkeypatch.setattr(engine, 'EXTERNAL_OPEN_CAP', 2)
    for i in range(2):
        data_of(rpc.tool(raw, 'propose_note', {'section': 'home', 'title': 'عنوان %d' % i, 'text': 'نص %d' % i}))
    res = result_of(rpc.tool(raw, 'propose_note', {'section': 'home', 'title': 'ثالث', 'text': 'نص'}))
    assert res['isError'] is True and res['structuredContent']['reason'] == 'full'


def test_founder_can_keep_or_reject_an_external_proposal(rpc, api):
    raw, _ = mint('ext', 'read,propose')
    d = data_of(rpc.tool(raw, 'propose_note', {'section': 'content', 'title': 'عنوان', 'text': 'نص الاقتراح'}))
    d2 = data_of(rpc.tool(raw, 'propose_note', {'section': 'content', 'title': 'عنوان آخر', 'text': 'نص ثان'}))
    items = api.get('/api/v2/brain/items?status=proposed').get_json()['items']
    mine = [i for i in items if i['id'] == d['id']][0]
    assert mine['tag'] == 'من نظام متصل' and mine['approve_label'] == 'احتفظ بها' and mine['producer'] == 'mcp:ext'
    a = api.post('/api/v2/brain/items/%s/approve' % d['id'], {'confirmed': True})
    assert a.status_code == 200 and a.get_json()['status'] == 'approved'
    r = api.post('/api/v2/brain/items/%s/reject' % d2['id'], {'confirmed': True})
    assert r.status_code == 200 and r.get_json()['status'] == 'rejected'


# ───────────────────────────────────────────────────────────── الحد والتدقيق

def test_rate_limit_60_per_hour_per_token(rpc, monkeypatch):
    raw, _ = mint('a')
    other, _ = mint('b')
    now = [1000.0]
    monkeypatch.setattr(mcp_server, '_clock', lambda: now[0])
    for _ in range(60):
        assert rpc.tool(raw, 'decisions_waiting').status_code == 200
    r = rpc.tool(raw, 'decisions_waiting')
    b = r.get_json()
    assert r.status_code == 429 and b['error']['code'] == mcp_server.E_RATE and 'result' not in b and r.headers['Retry-After']
    assert rpc.call(raw, 'ping').status_code == 200, 'المصافحة والقائمة لا تُحسب'
    assert rpc.tool(other, 'decisions_waiting').status_code == 200, 'الحد لكل رمز'
    now[0] += 3601
    assert rpc.tool(raw, 'decisions_waiting').status_code == 200, 'النافذة تنزلق'


def test_every_tool_call_is_audited_with_tool_and_token_name(rpc):
    raw, row = mint('مدار')
    AuditLog.query.filter_by(action='mcp.call').delete()
    db.session.commit()
    rpc.tool(raw, 'decisions_waiting')
    rpc.tool(raw, 'propose_note', {'section': 'content', 'title': 'a', 'text': 'b'})     # مرفوض بالصلاحية ويُسجَّل
    rows = AuditLog.query.filter_by(action='mcp.call').order_by(AuditLog.id).all()
    assert len(rows) == 2
    m0, m1 = json.loads(rows[0].meta_json), json.loads(rows[1].meta_json)
    assert (m0['tool'], m0['token'], m0['ok']) == ('decisions_waiting', 'مدار', True) and rows[0].actor_email == 'mcp:مدار' and rows[0].target == 'decisions_waiting'
    assert (m1['tool'], m1['ok'], m1['reason']) == ('propose_note', False, 'scope')
    assert raw not in json.dumps([m0, m1]) and raw not in rows[0].meta_json
    db.session.expire_all()
    assert mcp_server._models(db).query.get(row.id).last_used_at is not None


# ───────────────────────────────────────────────────────────── رموز الدخول (مسارات الإدارة)

def test_token_routes_are_admin_only_gated_and_no_store(api, monkeypatch):
    assert api.anon('GET', TOKENS).status_code == 401
    for role in NON_ADMIN:
        assert api.get(TOKENS, role=role).status_code == 403
        assert api.post(TOKENS, {'name': 'x', 'scopes': 'read', 'confirmed': True}, role=role).status_code == 403
    r = api.get(TOKENS)
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert api.get(TOKENS).status_code == 404
    assert api.post(TOKENS, {'name': 'x', 'scopes': 'read', 'confirmed': True}).status_code == 404


def test_mint_shows_plaintext_once_and_stores_only_the_hash(api, rpc):
    r = api.post(TOKENS, {'name': 'مدار', 'scopes': 'read', 'confirmed': True})
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    b = r.get_json()
    raw = b['token']
    assert raw.startswith('elpmcp_') and len(raw) > 40 and b['warning'] == 'يظهر الرمز مرة واحدة فقط'
    assert b['item']['name'] == 'مدار' and b['item']['scopes'] == 'read' and b['server_url'] == 'https://dashboard.elprofessor.net/api/mcp'
    row = mcp_server._models(db).query.get(b['item']['id'])
    assert row.hash == hashlib.sha256(raw.encode()).hexdigest() and raw not in (row.hash, row.name, row.scopes, row.created_by)
    lst = api.get(TOKENS)
    txt = lst.get_data(as_text=True)
    assert raw not in txt and row.hash not in txt and '"hash"' not in txt and 'token' not in json.loads(txt)['tokens'][0]
    assert set(lst.get_json()['tokens'][0]) == {'id', 'name', 'scopes', 'can_propose', 'created_at', 'created_by', 'last_used_at', 'revoked_at'}
    assert result_of(rpc.call(raw, 'ping')) == {}, 'الرمز الذي أنشأته اللوحة يعمل'
    assert AuditLog.query.filter_by(action='brain.mcp_token_create').count() >= 1
    assert raw not in ' '.join(a.meta_json or '' for a in AuditLog.query.filter(AuditLog.action.like('brain.mcp%')).all())


def test_mint_validation_and_confirmation(api):
    assert api.post(TOKENS, {'name': 'x', 'scopes': 'read'}).status_code == 400
    assert api.post(TOKENS, {'name': '', 'scopes': 'read', 'confirmed': True}).status_code == 400
    assert api.post(TOKENS, {'name': 'ن' * 37, 'scopes': 'read', 'confirmed': True}).status_code == 400
    for bad in ('admin', 'read,propose,write', '', None, 7):
        assert api.post(TOKENS, {'name': 'x', 'scopes': bad, 'confirmed': True}).status_code == 400, bad
    assert api.post(TOKENS, {'name': 'x', 'scopes': 'propose', 'confirmed': True}).get_json()['item']['scopes'] == 'read,propose'
    assert api.post(TOKENS, {'name': 'x', 'scopes': 'read', 'confirmed': True}).status_code == 409, 'اسم مكرر بين العاملة'
    assert mcp_server._models(db).query.count() == 1


def test_revoke_blocks_the_token_and_keeps_the_record(api, rpc):
    b = api.post(TOKENS, {'name': 'مدار', 'scopes': 'read', 'confirmed': True}).get_json()
    tid, raw = b['item']['id'], b['token']
    assert api.call('DELETE', '%s/%s' % (TOKENS, tid), {}).status_code == 400, 'يطلب confirmed'
    assert api.call('DELETE', '%s/nope' % TOKENS, {'confirmed': True}).status_code == 400
    assert api.call('DELETE', '%s/%s' % (TOKENS, 'a' * 32), {'confirmed': True}).status_code == 404
    r = api.call('DELETE', '%s/%s' % (TOKENS, tid), {'confirmed': True})
    assert r.status_code == 200 and r.get_json()['item']['revoked_at']
    assert rpc.call(raw, 'ping').status_code == 401
    assert api.call('DELETE', '%s/%s' % (TOKENS, tid), {'confirmed': True}).status_code == 409
    assert api.get(TOKENS).get_json()['tokens'][0]['revoked_at']
    assert api.post(TOKENS, {'name': 'مدار', 'scopes': 'read', 'confirmed': True}).status_code == 200, 'يعود الاسم متاحًا بعد الإلغاء'


# ───────────────────────────────────────────────────────────── ملفات

def test_dockerfile_and_app_wiring():
    docker = open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()
    assert 'COPY backend/mcp_server.py /app/mcp_server.py' in docker
    assert 'COPY backend/v2_brain2_mcp_routes.py /app/v2_brain2_mcp_routes.py' in docker
    src = open(os.path.join(ROOT, 'backend', 'app.py'), encoding='utf-8').read()
    assert src.index('_v2_brain2_keys.register') < src.index('_v2_brain2_mcp.register(app, globals())')
    assert "except Exception: logger.exception('v2 brain2 mcp routes not loaded')" in src
    assert '/api/mcp' in [r.rule for r in flask_app.url_map.iter_rules()]


def test_no_real_network_modules_in_the_server():
    src = open(os.path.join(ROOT, 'backend', 'mcp_server.py'), encoding='utf-8').read()
    assert 'import requests' not in src and 'urllib.request' not in src and 'ai_call' not in src


# ───────────────────────────────────────────────────────────── جولة الإصلاح

def test_platform_calls_from_mcp_tools_use_a_timeout_of_8_seconds_at_most(rpc, monkeypatch):
    seen = []

    def proxy(method, path, params=None, json_body=None, timeout=12):
        seen.append(timeout)
        return appmod.jsonify({'courses': COURSES})
    monkeypatch.setattr(appmod, '_platform_proxy', proxy)
    raw, _ = mint()
    for name in ('business_summary', 'courses_catalog'):
        assert rpc.tool(raw, name).status_code == 200
    assert seen and all(t <= 8 for t in seen), seen


def test_backend_dockerfile_copies_the_same_top_level_modules_as_the_root_one():
    backend = open(os.path.join(ROOT, 'backend', 'Dockerfile'), encoding='utf-8').read()
    root_df = open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()
    modules = sorted(set(re.findall(r'COPY backend/([A-Za-z0-9_]+\.py) /app/', root_df)))
    assert 'mcp_server.py' in modules and 'site_edit.py' in modules
    for m in modules:
        assert m in backend or (m.startswith('v2_') and m.endswith('_routes.py')), 'ينقص backend/Dockerfile: ' + m
    assert 'COPY brain2 ./brain2' in backend and 'COPY v2_*_routes.py ./' in backend
