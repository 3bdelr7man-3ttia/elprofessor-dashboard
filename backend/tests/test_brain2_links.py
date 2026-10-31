# -*- coding: utf-8 -*-
"""«الأنظمة المتصلة» (SPEC-B B5b) · عميل MCP ومسارات الإدارة والمنتج `links_digest`.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_links.py

⛔ صفر شبكة: `requests.*` ترمي (تجهيز `env`) ونقل العميل دالة مزيّفة تسجّل كل طلب. الرموز كلها نصوص وهمية.
"""
import json
import os
import re
import sys
import types

import pytest

import app as appmod
from app import app as flask_app, db, AuditLog
from brain2 import engine, keys as K, links as LK, producers_links as PL, registry

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uiharness'))
import v2_node   # noqa: E402
from test_brain2_engine import env, run, rows   # noqa: F401  (fixture)
from test_brain2_routes import api, NON_ADMIN   # noqa: F401  (fixture)

NS = appmod.__dict__
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINKS = '/api/v2/brain/links'
SECRET_TOKEN = 'madar-secret-token-ZZZ999'
URL = 'https://madar.example.com/mcp'
BRAND = '5b0c7a3e-1111-2222-3333-444455556666'


@pytest.fixture(autouse=True)
def clean(env):   # noqa: F811
    Link = LK._models(db)
    Link.query.delete()
    db.session.commit()
    LK.set_transport(None)
    yield
    LK.set_transport(None)
    db.session.rollback()
    Link.query.delete()
    db.session.commit()


# ───────────────────────────────────────────────────────────── نقل مزيّف

class Remote(object):
    """خادم MCP بعيد مزيّف. `tools`: {اسم: (inputSchema, نتيجة)}. يسجّل كل طلب: (طريقة، وسائط، رأس الدخول)."""

    def __init__(self, tools=None, sse=False, status=200, fail=None, server_name='madar'):
        self.tools = tools if tools is not None else {}
        self.sse, self.status, self.fail, self.server_name = sse, status, fail, server_name
        self.requests = []

    def __call__(self, url, headers, body, timeout):
        msg = json.loads(body.decode('utf-8'))
        self.requests.append({'url': url, 'method': msg.get('method'), 'params': msg.get('params'), 'auth': headers.get('Authorization'),
                              'timeout': timeout, 'accept': headers.get('Accept'), 'session': headers.get('Mcp-Session-Id')})
        if self.fail:
            raise self.fail
        if 'id' not in msg:
            return 202, {}, ''
        if self.status != 200:
            return self.status, {}, '{"error":"secret server detail %s"}' % SECRET_TOKEN
        m = msg['method']
        if m == 'initialize':
            res = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, 'serverInfo': {'name': self.server_name, 'version': '1'}}
            hdr = {'Mcp-Session-Id': 'sess-1'}
        elif m == 'tools/list':
            res = {'tools': [{'name': n, 'description': n, 'inputSchema': sc} for n, (sc, _r) in self.tools.items()]}
            hdr = {}
        elif m == 'tools/call':
            name = msg['params']['name']
            res = {'content': [{'type': 'text', 'text': json.dumps(self.tools[name][1], ensure_ascii=False)}], 'isError': False}
            hdr = {}
        else:
            return 200, {}, json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'error': {'code': -32601, 'message': 'x'}})
        payload = json.dumps({'jsonrpc': '2.0', 'id': msg['id'], 'result': res}, ensure_ascii=False)
        if self.sse:
            hdr['Content-Type'] = 'text/event-stream'
            return 200, hdr, 'event: message\ndata: %s\n\n' % payload
        hdr['Content-Type'] = 'application/json'
        return 200, hdr, payload

    def methods(self):
        return [r['method'] for r in self.requests]

    def called_tools(self):
        return [r['params']['name'] for r in self.requests if r['method'] == 'tools/call']


NO_ARGS = {'type': 'object', 'properties': {}}
BRAND_ARGS = {'type': 'object', 'properties': {'brand_id': {'type': 'string'}}, 'required': ['brand_id']}
MADAR_TOOLS = {
    'jobs_health': (NO_ARGS, {'ok': True}),
    'kpis_get': (BRAND_ARGS, {'tiles': [{'label': 'عملاء محتملون', 'value': 42}, {'label': 'زيارات', 'value': 1300}]}),
    'metrics_get': (BRAND_ARGS, {'points': [1, 2, 3]}),
    'alerts_list': (NO_ARGS, {'alerts': [{'text': 'ربط ميتا يحتاج تجديدًا', 'level': 'warn'}]}),
}


def add_link(name='مدار', url=URL, token=SECRET_TOKEN, **kw):
    Link = LK._models(db)
    row = Link(id=os.urandom(16).hex(), name=name, url=url, token_enc=K.encrypt(token), enabled=kw.pop('enabled', True), **kw)
    db.session.add(row)
    db.session.commit()
    return row


# ───────────────────────────────────────────────────────────── العميل

def test_client_handshake_list_and_call_with_bearer_and_timeout():
    rem = Remote(MADAR_TOOLS)
    c = LK.McpClient(URL, SECRET_TOKEN, transport=rem)
    info = c.initialize()
    assert info['serverInfo']['name'] == 'madar'
    assert [t['name'] for t in c.list_tools()] == list(MADAR_TOOLS)
    assert c.call_tool('alerts_list') == MADAR_TOOLS['alerts_list'][1]
    assert rem.methods() == ['initialize', 'notifications/initialized', 'tools/list', 'tools/call']
    assert all(r['auth'] == 'Bearer ' + SECRET_TOKEN and r['timeout'] == 15 and 'text/event-stream' in r['accept'] for r in rem.requests)
    assert rem.requests[0]['params']['protocolVersion'] == '2025-06-18'
    assert rem.requests[2]['session'] == 'sess-1', 'معرّف الجلسة يُرسل بعد المصافحة'


def test_client_parses_sse_first_event_and_plain_json():
    rem = Remote(MADAR_TOOLS, sse=True)
    c = LK.McpClient(URL, SECRET_TOKEN, transport=rem)
    c.initialize()
    assert len(c.list_tools()) == 4 and c.call_tool('jobs_health') == {'ok': True}
    text = ('event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress","params":{}}\n\n'
            'event: message\ndata: {"jsonrpc":"2.0","id":7,"result":{"ok":1}}\n\ndata: {"jsonrpc":"2.0","id":7,"result":{"ok":2}}\n\n')
    assert LK.parse_reply(text, 'text/event-stream', 7)['result'] == {'ok': 1}, 'أول حدث يطابق المعرّف'
    assert LK.parse_reply('data: {"id":1,"result":{}}\n\n', '', 1)['result'] == {}, 'SSE يُعرف من الشكل ولو غاب نوع المحتوى'
    assert LK.parse_reply('data: {"a":\ndata: 1}\n\n', 'text/event-stream')['a'] == 1, 'أسطر data المتتالية تُضمّ'
    assert LK.parse_reply('{"jsonrpc":"2.0","id":1,"result":{}}', 'application/json', 1)['id'] == 1
    for bad in ('', '   ', 'not json', '[1,2]', 'data: nope\n\n', 'event: x\n\n'):
        with pytest.raises(LK.LinkError):
            LK.parse_reply(bad, '', 1)


def test_client_errors_are_white_arabic_sentences_without_server_text():
    for status, msg in ((401, LK.ERR_AUTH), (403, LK.ERR_AUTH), (404, LK.ERR_NOT_FOUND), (500, LK.ERR_CONNECT)):
        c = LK.McpClient(URL, SECRET_TOKEN, transport=Remote(MADAR_TOOLS, status=status))
        with pytest.raises(LK.LinkError) as ei:
            c.initialize()
        assert ei.value.message == msg and SECRET_TOKEN not in str(ei.value) and 'secret server detail' not in ei.value.message
    for exc, msg in ((TimeoutError('slow'), LK.ERR_TIMEOUT), (ConnectionError('refused'), LK.ERR_CONNECT), (RuntimeError('weird ' + SECRET_TOKEN), LK.ERR_CONNECT)):
        c = LK.McpClient(URL, SECRET_TOKEN, transport=Remote(fail=exc))
        with pytest.raises(LK.LinkError) as ei:
            c.initialize()
        assert ei.value.message == msg and SECRET_TOKEN not in ei.value.message
    c = LK.McpClient(URL, SECRET_TOKEN, transport=Remote(MADAR_TOOLS))
    c.initialize()
    with pytest.raises(LK.LinkError) as ei:
        c.request('nope/nope')
    assert ei.value.message == LK.ERR_REMOTE


def test_no_retry_one_attempt_per_request():
    rem = Remote(fail=TimeoutError('t'))
    with pytest.raises(LK.LinkError):
        LK.McpClient(URL, SECRET_TOKEN, transport=rem).initialize()
    assert len(rem.requests) == 1


def test_tool_error_result_raises_and_text_result_is_wrapped():
    def transport(url, headers, body, timeout):
        m = json.loads(body)
        if m['method'] == 'tools/call' and m['params']['name'] == 'bad':
            r = {'content': [{'type': 'text', 'text': 'server said ' + SECRET_TOKEN}], 'isError': True}
        else:
            r = {'content': [{'type': 'text', 'text': 'just words'}]}
        return 200, {'Content-Type': 'application/json'}, json.dumps({'jsonrpc': '2.0', 'id': m['id'], 'result': r})
    c = LK.McpClient(URL, SECRET_TOKEN, transport=transport)
    with pytest.raises(LK.LinkError) as ei:
        c.call_tool('bad')
    assert ei.value.message == LK.ERR_REMOTE and SECRET_TOKEN not in ei.value.message
    assert c.call_tool('ok') == {'text': 'just words'}


def test_real_transport_reads_first_sse_event_and_never_follows_redirects(monkeypatch):
    seen = {}

    class Resp(object):
        status_code = 200
        headers = {'Content-Type': 'text/event-stream'}

        def iter_content(self, chunk_size=0):
            yield b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'
            raise AssertionError('لا ننتظر إغلاق الاتصال بعد أول حدث')

        def close(self):
            seen['closed'] = True

    def post(url, **kw):
        seen.update(kw)
        return Resp()
    monkeypatch.setattr(appmod.requests, 'post', post)
    monkeypatch.setattr(LK, '_host_is_public', lambda h: True)
    status, headers, text = LK._real_transport(URL, {'Authorization': 'Bearer x'}, b'{}', 15)
    assert status == 200 and '"ok":true' in text and seen['allow_redirects'] is False and seen['timeout'] == 15 and seen['closed']
    monkeypatch.setattr(LK, '_host_is_public', lambda h: False)
    with pytest.raises(LK.LinkError) as ei:
        LK._real_transport(URL, {}, b'{}', 15)
    assert ei.value.message == LK.ERR_PRIVATE


def test_real_transport_maps_timeouts(monkeypatch):
    import requests

    def post(url, **kw):
        raise requests.exceptions.Timeout('x')
    monkeypatch.setattr(appmod.requests, 'post', post)
    monkeypatch.setattr(LK, '_host_is_public', lambda h: True)
    with pytest.raises(LK.LinkError) as ei:
        LK._real_transport(URL, {}, b'{}', 15)
    assert ei.value.message == LK.ERR_TIMEOUT


def test_host_guard_refuses_private_addresses():
    assert LK._host_is_public('localhost') is False and LK._host_is_public('127.0.0.1') is False
    assert LK._host_is_public('192.168.1.5') is False and LK._host_is_public('10.0.0.1') is False


# ───────────────────────────────────────────────────────────── المسارات

def post_link(api, **kw):
    body = {'name': 'مدار', 'url': URL, 'token': SECRET_TOKEN, 'confirmed': True}
    body.update(kw)
    return api.post(LINKS, body)


def test_routes_are_admin_only_flag_gated_and_no_store(api, monkeypatch):
    assert api.anon('GET', LINKS).status_code == 401
    for role in NON_ADMIN:
        assert api.get(LINKS, role=role).status_code == 403
    r = api.get(LINKS)
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    for role in NON_ADMIN:
        assert api.post(LINKS, {'name': 'x', 'url': URL, 'token': SECRET_TOKEN, 'confirmed': True}, role=role).status_code == 403
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert api.get(LINKS).status_code == 404
    assert api.post(LINKS, {'name': 'x', 'url': URL, 'token': SECRET_TOKEN, 'confirmed': True}).status_code == 404
    assert api.post(LINKS + '/' + 'a' * 32 + '/test').status_code == 404


def test_crud_never_returns_the_token_and_stores_it_encrypted(api):
    Link = LK._models(db)
    Link.query.delete()
    db.session.commit()
    r = post_link(api, brand_id=BRAND)
    assert r.status_code == 200, r.get_json()
    body = r.get_data(as_text=True)
    link = r.get_json()['link']
    assert SECRET_TOKEN not in body and 'token_enc' not in body and 'v1:' not in body
    assert link['name'] == 'مدار' and link['url'] == URL and link['enabled'] is True and link['readable'] is True and link['known'] is True
    assert link['brand_id'] == BRAND and link['last_ok_at'] is None and link['last_error'] == ''
    row = Link.query.get(link['id'])
    assert row.token_enc.startswith('v1:') and SECRET_TOKEN not in row.token_enc and K.decrypt(row.token_enc) == SECRET_TOKEN
    lst = api.get(LINKS)
    assert SECRET_TOKEN not in lst.get_data(as_text=True) and 'token' not in json.dumps(lst.get_json()['links'][0])
    # تعديل: تبديل الرمز والعنوان ثم إيقاف
    new_token = 'another-secret-token-QQQ111'
    p = api.put('%s/%s' % (LINKS, link['id']), {'token': new_token, 'url': 'https://madar2.example.com/mcp', 'confirmed': True})
    assert p.status_code == 200 and new_token not in p.get_data(as_text=True)
    db.session.expire_all()
    assert K.decrypt(Link.query.get(link['id']).token_enc) == new_token and Link.query.get(link['id']).url == 'https://madar2.example.com/mcp'
    p = api.put('%s/%s' % (LINKS, link['id']), {'enabled': False, 'name': 'مدار الجديد', 'brand_id': '', 'confirmed': True})
    assert p.get_json()['link']['enabled'] is False and p.get_json()['link']['name'] == 'مدار الجديد' and p.get_json()['link']['brand_id'] == ''
    assert K.decrypt(Link.query.get(link['id']).token_enc) == new_token, 'تعديل بلا رمز يُبقي الرمز'
    d = api.call('DELETE', '%s/%s' % (LINKS, link['id']), {'confirmed': True})
    assert d.status_code == 200 and Link.query.count() == 0
    acts = [a.action for a in AuditLog.query.filter(AuditLog.action.like('brain.link_%')).all()]
    assert {'brain.link_add', 'brain.link_update', 'brain.link_delete'} <= set(acts)
    audit_text = ' '.join(a.meta_json or '' for a in AuditLog.query.filter(AuditLog.action.like('brain.link_%')).all())
    assert SECRET_TOKEN not in audit_text and new_token not in audit_text


def test_validation_and_confirmation(api):
    assert api.post(LINKS, {'name': 'x', 'url': URL, 'token': SECRET_TOKEN}).status_code == 400
    for bad_url in ('http://madar.example.com/mcp', 'https://localhost/mcp', 'https://127.0.0.1/mcp', 'https://u:p@madar.example.com/', 'https://madar.example.com/mcp?x=1', 'ftp://x.y', '', None):
        assert post_link(api, url=bad_url).status_code == 400, bad_url
    for bad_tok in ('', 'short', 'has space in it 123', 'عربي-token-12345', None):
        assert post_link(api, token=bad_tok).status_code == 400, bad_tok
    assert post_link(api, name='').status_code == 400
    assert post_link(api, name='ن' * 61).status_code == 400
    assert post_link(api, brand_id='bad id!').status_code == 400
    assert LK._models(db).query.count() == 0
    assert api.put(LINKS + '/nope', {'confirmed': True}).status_code == 400
    assert api.put(LINKS + '/' + 'a' * 32, {'name': 'x', 'confirmed': True}).status_code == 404
    row = add_link()
    assert api.put('%s/%s' % (LINKS, row.id), {'confirmed': True}).status_code == 400, 'لا تعديل مطلوب'
    assert api.put('%s/%s' % (LINKS, row.id), {'name': 'x'}).status_code == 400, 'يطلب confirmed'
    assert api.put('%s/%s' % (LINKS, row.id), {'enabled': 'yes', 'confirmed': True}).status_code == 400
    assert api.call('DELETE', '%s/%s' % (LINKS, row.id), {}).status_code == 400
    assert api.call('DELETE', '%s/%s' % (LINKS, 'b' * 32), {'confirmed': True}).status_code == 404


def test_links_cap(api, monkeypatch):
    monkeypatch.setattr(LK, 'LINKS_CAP', 2)
    assert post_link(api, name='a').status_code == 200 and post_link(api, name='b').status_code == 200
    assert post_link(api, name='c').status_code == 409


def test_unreadable_token_is_flagged_and_test_makes_no_call(api):
    row = add_link()
    row.token_enc = 'v1:AAAA'
    db.session.commit()
    rem = Remote(MADAR_TOOLS)
    LK.set_transport(rem)
    lst = api.get(LINKS).get_json()['links'][0]
    assert lst['readable'] is False and lst['notice'] == LK.ERR_UNREADABLE
    r = api.post('%s/%s/test' % (LINKS, row.id))
    assert r.get_json()['ok'] is False and r.get_json()['error'] == LK.ERR_UNREADABLE and rem.requests == []


def test_test_route_runs_initialize_and_tools_list_only(api):
    row = add_link()
    rem = Remote(MADAR_TOOLS)
    LK.set_transport(rem)
    before = AuditLog.query.filter_by(action='brain.link_test').count()
    r = api.post('%s/%s/test' % (LINKS, row.id))
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    b = r.get_json()
    assert b['ok'] is True and b['count'] == 4 and b['tools'] == list(MADAR_TOOLS) and b['server'] == 'madar' and b['error'] == ''
    assert b['link']['last_ok_at'] and b['link']['last_error'] == ''
    assert rem.methods() == ['initialize', 'notifications/initialized', 'tools/list'], '⛔ لا نداء أداة من «جرّب الاتصال»'
    assert SECRET_TOKEN not in r.get_data(as_text=True)
    assert AuditLog.query.filter_by(action='brain.link_test').count() == before + 1


@pytest.mark.parametrize('fail,expected', [(None, LK.ERR_AUTH), (TimeoutError('t'), LK.ERR_TIMEOUT)])
def test_test_route_failure_records_a_white_sentence(api, fail, expected):
    row = add_link()
    LK.set_transport(Remote(MADAR_TOOLS, status=401 if fail is None else 200, fail=fail))
    r = api.post('%s/%s/test' % (LINKS, row.id))
    b = r.get_json()
    assert r.status_code == 200 and b['ok'] is False and b['error'] == expected and b['link']['last_error'] == expected
    assert SECRET_TOKEN not in r.get_data(as_text=True) and 'secret server detail' not in r.get_data(as_text=True)
    assert api.post('%s/%s/test' % (LINKS, 'c' * 32)).status_code == 404
    assert api.post('%s/nope/test' % LINKS).status_code == 400


def test_sse_server_also_passes_the_test_route(api):
    row = add_link()
    LK.set_transport(Remote(MADAR_TOOLS, sse=True))
    assert api.post('%s/%s/test' % (LINKS, row.id)).get_json()['count'] == 4


# ───────────────────────────────────────────────────────────── المنتج links_digest

def test_producer_shape_and_registration():
    p = registry.by_id('links_digest')
    assert p is not None and p.id == 'links_digest'
    assert (p.kind, p.section, p.may_run_alone, p.default_mode, p.lock_reason) == ('note', 'reports', True, 'alone', '')
    assert p.label == 'من الأنظمة المتصلة' and p.sentence == 'يقرأ العقل أرقام الأنظمة المتصلة ويكتب ملخصًا قصيرًا.'
    assert PL.KNOWN_SYSTEMS['madar']['tools'] == ('kpis_get', 'alerts_list')
    assert PL.system_of('مدار') == 'madar' and PL.system_of('Madar Marketing') == 'madar' and PL.system_of('نظام آخر') is None


def test_gather_calls_only_the_allow_list_and_skips_unknown_systems():
    madar = add_link('مدار', brand_id=BRAND)
    other = add_link('نظام آخر', url='https://other.example.com/mcp')
    off = add_link('مدار قديم', url='https://old.example.com/mcp', enabled=False)
    remotes = {}

    def transport(url, headers, body, timeout):
        remotes.setdefault(url, Remote(MADAR_TOOLS))
        return remotes[url](url, headers, body, timeout)
    LK.set_transport(transport)
    ctx = types.SimpleNamespace(ns=NS, now=None, actor='cron')
    targets = PL.gather(ctx)
    assert list(remotes) == [URL], 'النظام غير المعروف والمعطّل لا يُنادَيان أصلًا'
    rem = remotes[URL]
    assert rem.called_tools() == ['kpis_get', 'alerts_list'], 'القائمة البيضاء وحدها (لا metrics_get ولا jobs_health)'
    assert [r['params']['arguments'] for r in rem.requests if r['method'] == 'tools/call'] == [{'brand_id': BRAND}, {}]
    assert len(targets) == 1 and targets[0].ref == 'link:%s' % madar.id and targets[0].facts['system'] == 'مدار'
    assert targets[0].facts['results']['kpis_get']['tiles'][0] == {'label': 'عملاء محتملون', 'value': 42}
    assert len(json.dumps(targets[0].facts, ensure_ascii=False).encode()) <= 4096
    db.session.expire_all()
    assert LK._models(db).query.get(madar.id).last_ok_at is not None and LK._models(db).query.get(other.id).last_ok_at is None


def test_tool_needing_brand_without_brand_is_skipped_not_guessed():
    add_link('مدار')
    rem = Remote(MADAR_TOOLS)
    LK.set_transport(rem)
    targets = PL.gather(types.SimpleNamespace(ns=NS, now=None, actor='cron'))
    assert rem.called_tools() == ['alerts_list'] and list(targets[0].facts['results']) == ['alerts_list']


def test_allow_listed_tool_missing_or_failing_is_skipped_and_all_failing_is_source_down():
    from brain2.contract import SourceDown
    row = add_link('مدار', brand_id=BRAND)
    LK.set_transport(Remote({'alerts_list': MADAR_TOOLS['alerts_list']}))
    t = PL.gather(types.SimpleNamespace(ns=NS, now=None, actor='cron'))
    assert list(t[0].facts['results']) == ['alerts_list']
    LK.set_transport(Remote(MADAR_TOOLS, status=401))
    with pytest.raises(SourceDown):
        PL.gather(types.SimpleNamespace(ns=NS, now=None, actor='cron'))
    db.session.expire_all()
    assert LK._models(db).query.get(row.id).last_error == LK.ERR_AUTH
    LK.set_transport(Remote({'unrelated': (NO_ARGS, {'x': 1})}))
    with pytest.raises(SourceDown):
        PL.gather(types.SimpleNamespace(ns=NS, now=None, actor='cron'))


def test_no_links_or_only_unknown_links_means_no_targets_and_no_calls():
    rem = Remote(MADAR_TOOLS)
    LK.set_transport(rem)
    ctx = types.SimpleNamespace(ns=NS, now=None, actor='cron')
    assert PL.gather(ctx) == []
    add_link('نظام آخر', url='https://other.example.com/mcp')
    assert PL.gather(ctx) == [] and rem.requests == []


def test_facts_are_scrubbed_and_capped():
    big = {'tiles': [{'label': 'مبيعات تواصل a@b.com 01012345678', 'value': i, 'note': 'x' * 400} for i in range(60)]}
    add_link('مدار', brand_id=BRAND)
    LK.set_transport(Remote(dict(MADAR_TOOLS, kpis_get=(BRAND_ARGS, big))))
    t = PL.gather(types.SimpleNamespace(ns=NS, now=None, actor='cron'))
    txt = json.dumps(t[0].facts, ensure_ascii=False)
    assert '@' not in txt and '01012345678' not in txt and len(txt.encode()) <= 4096


def test_full_run_writes_a_done_alone_note_through_the_engine(monkeypatch, env):   # noqa: F811
    add_link('مدار', brand_id=BRAND)
    LK.set_transport(Remote(MADAR_TOOLS))
    monkeypatch.setattr(registry, 'PRODUCERS', [registry.by_id('links_digest')])
    env.default = {'text': 'من مدار هذا الأسبوع: عملاء محتملون 42، زيارات 1300. تنبيه واحد: ربط ميتا يحتاج تجديدًا.'}
    rid = run(only='links_digest')
    got = rows(producer='links_digest')
    assert len(got) == 1 and got[0].status == 'done_alone' and got[0].section == 'reports' and got[0].kind == 'note'
    body = json.loads(got[0].body_json)
    assert body['text'].startswith('من مدار هذا الأسبوع')
    assert len(env.calls) == 1 and 'kpis_get' in env.calls[0]['user'] and SECRET_TOKEN not in env.calls[0]['user'] and BRAND not in env.calls[0]['user']
    # نفس الأرقام ⇒ نفس البصمة ⇒ لا اقتراح جديد ولا نداء ذكاء ثانٍ
    run(only='links_digest')
    assert len(rows(producer='links_digest')) == 1 and len(env.calls) == 1


def test_validate_rejects_empty_and_too_long():
    p = registry.by_id('links_digest')
    t = types.SimpleNamespace(facts={})
    assert p.validate({'text': 'من مدار هذا الأسبوع: كذا'}, t) == {'text': 'من مدار هذا الأسبوع: كذا'}
    assert p.validate({'text': ''}, t) is None and p.validate({'text': 'ن' * 600}, t) is None and p.validate('x', t) is None


def test_files_wiring():
    docker = open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()
    assert 'COPY backend/brain2 /app/brain2' in docker
    assert 'import requests' not in open(os.path.join(ROOT, 'backend', 'brain2', 'producers_links.py'), encoding='utf-8').read()


# ───────────────────────────────────────────────────────────── الواجهة (node): مساعدات نقية وعقد brain.js

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = 1793000000000     # لحظة ثابتة (ms)


def _iso(delta_min):
    import datetime
    return (datetime.datetime.utcfromtimestamp(NOW / 1000.0) - datetime.timedelta(minutes=delta_min)).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def _links_resp():
    return {'links': [
        {'id': 'l1', 'name': 'مدار', 'url': 'https://Madar.Example.com/mcp', 'enabled': True, 'known': True, 'readable': True, 'brand_id': 'b1', 'last_ok_at': _iso(3), 'last_error': ''},
        {'id': 'l2', 'name': 'نظام آخر', 'url': 'https://other.example.com', 'enabled': False, 'known': False, 'readable': True, 'last_ok_at': None, 'last_error': 'الرمز غير مقبول عند النظام الآخر'},
        {'id': 'l3', 'name': 'قديم', 'url': 'https://old.example.com', 'enabled': True, 'known': False, 'readable': False, 'notice': 'تعذّرت قراءة الرمز المحفوظ؛ أضِف النظام من جديد'},
    ]}


@needs_node
def test_ui_links_rows_states_and_failed_source_is_null():
    r = v2_node.logic('v2sBrainLinks', _links_resp(), NOW)
    rows = {x['id']: x for x in r['rows']}
    assert rows['l1']['host'] == 'madar.example.com' and rows['l1']['stateLabel'] == 'مفعّل' and rows['l1']['known'] is True
    assert rows['l1']['test'] == {'state': 'ok', 'text': 'آخر اتصال ناجح منذ ٣ دقائق'} and 'يقرأ العقل أرقامه' in rows['l1']['autoText']
    assert rows['l2']['stateLabel'] == 'موقوف' and rows['l2']['test']['state'] == 'fail' and rows['l2']['test']['text'].startswith('آخر محاولة لم تنجح: ')
    assert 'لا يقرأ العقل منه تلقائيًا' in rows['l2']['autoText']
    assert rows['l3']['readable'] is False and rows['l3']['tone'] == 'stop' and rows['l3']['notice'].startswith('تعذّرت قراءة الرمز')
    assert 'token' not in json.dumps(r) and r['full'] is False
    for bad in (None, {}, {'links': 'x'}, {'tokens': []}, 'x'):
        assert v2_node.logic('v2sBrainLinks', bad, NOW) is None, bad
    assert v2_node.logic('v2sBrainLinks', {'links': []}, NOW)['rows'] == []
    assert v2_node.logic('v2sBrainLinks', {'links': [{'id': 'x%d' % i, 'name': 'n'} for i in range(10)]}, NOW)['full'] is True


@needs_node
def test_ui_link_form_validates_like_the_server():
    f = lambda **kw: v2_node.logic('v2sBrainLinkForm', dict({'name': 'مدار', 'url': URL, 'token': SECRET_TOKEN, 'brand_id': ''}, **kw))
    ok = f()
    assert ok['ok'] and ok['body'] == {'name': 'مدار', 'url': URL, 'token': SECRET_TOKEN, 'confirmed': True}
    assert f(brand_id=BRAND)['body']['brand_id'] == BRAND
    for field, kw in (('name', {'name': '  '}), ('name', {'name': 'ن' * 61}), ('url', {'url': ''}), ('url', {'url': 'http://x.example.com'}), ('url', {'url': 'https://a b.com'}),
                      ('url', {'url': 'https://'}), ('token', {'token': ''}), ('token', {'token': 'short'}), ('token', {'token': 'has space in token'}), ('token', {'token': 'عربي-1234567'}),
                      ('brand_id', {'brand_id': 'bad id'})):
        r = f(**kw)
        assert r['ok'] is False and r['field'] == field and r['error'] and r['body'] is None, (field, kw)
    assert v2_node.logic('v2sBrainLinkForm', None)['field'] == 'name'


@needs_node
def test_ui_tokens_rows_server_address_and_form():
    resp = {'tokens': [
        {'id': 't1', 'name': 'قديم', 'scopes': 'read', 'can_propose': False, 'last_used_at': None, 'revoked_at': _iso(60)},
        {'id': 't2', 'name': 'مدار', 'scopes': 'read,propose', 'can_propose': True, 'last_used_at': _iso(5), 'revoked_at': None},
        {'id': 't3', 'name': 'تقارير', 'scopes': 'read', 'can_propose': False, 'last_used_at': None, 'revoked_at': None},
    ], 'server_url': 'https://dashboard.elprofessor.net/api/mcp', 'tools': ['business_summary']}
    r = v2_node.logic('v2sBrainMcpTokens', resp, NOW)
    assert [x['id'] for x in r['rows']] == ['t2', 't3', 't1'] and r['active'] == 2, 'العاملة أولًا'
    by = {x['id']: x for x in r['rows']}
    assert by['t2']['scopeLabel'] == 'للقراءة والاقتراح' and by['t2']['usedText'] == 'آخر استعمال منذ ٥ دقائق' and by['t2']['stateLabel'] == 'عامل'
    assert by['t3']['scopeLabel'] == 'للقراءة فقط' and by['t3']['usedText'] == 'لم يُستعمل بعد'
    assert by['t1']['revoked'] is True and by['t1']['stateLabel'] == 'أُلغي' and by['t1']['usedText'].startswith('توقف عن الدخول')
    assert r['serverUrl'] == 'https://dashboard.elprofessor.net/api/mcp' and r['tools'] == ['business_summary']
    assert v2_node.logic('v2sBrainMcpTokens', dict(resp, server_url='http://x.com/api/mcp'), NOW)['serverUrl'] == ''
    assert 'hash' not in json.dumps(r) and 'token"' not in json.dumps(r)
    for bad in (None, {}, {'tokens': 'x'}, {'links': []}):
        assert v2_node.logic('v2sBrainMcpTokens', bad, NOW) is None, bad
    f = lambda **kw: v2_node.logic('v2sBrainMcpTokenForm', dict({'name': 'مدار', 'scopes': 'read'}, **kw))
    assert f()['body'] == {'name': 'مدار', 'scopes': 'read', 'confirmed': True} and f(scopes='read,propose')['ok']
    for field, kw in (('name', {'name': ' '}), ('name', {'name': 'ن' * 37}), ('scopes', {'scopes': 'admin'}), ('scopes', {'scopes': ''}), ('scopes', {'scopes': None})):
        assert f(**kw)['field'] == field and f(**kw)['ok'] is False, kw


@needs_node
def test_ui_confirm_sheets_name_what_happens():
    sh = lambda a, name='مدار': v2_node.logic('v2sBrainMcpSheet', a, {'name': name})
    d = sh('link-delete')
    assert d['title'] == 'حذف النظام' and d['go'] == 'نعم، احذفه' and '«مدار»' in d['lead'] and 'لا يتغيّر شيء عند النظام الآخر' in d['lead']
    t = sh('link-test')
    assert t['title'] == 'جرّب الاتصال' and 'قائمة أدواته فقط' in t['lead'] and 'لا تُقرأ أرقام' in t['lead']
    rv = sh('token-revoke')
    assert rv['title'] == 'إلغاء الرمز' and rv['go'] == 'نعم، ألغِه' and 'فورًا' in rv['lead'] and '«مدار»' in rv['lead']


def test_ui_contract_in_brain_js_and_css():
    js = open(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'brain.js'), encoding='utf-8').read()
    css = open(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'brain.css'), encoding='utf-8').read()
    # تحت بطاقة المفاتيح لا فوقها
    assert js.index("'</section>'\n      + connectedCard();") > js.index('<h2>المفاتيح والكاتب</h2>')
    assert '<h2>الأنظمة المتصلة</h2>' in js and 'أضف نظامًا' in js and 'جرّب الاتصال' in js and 'احذفه' in js and 'رموز الدخول لهذه اللوحة' in js
    assert 'أنشئ رمزًا' in js and 'ألغِه' in js and 'انسخ الرمز' in js and 'يظهر الرمز مرة واحدة فقط' in js
    # رمز النظام الآخر: كلمة سر تُمسح بعد الحفظ ومع الإغلاق
    assert 'id="v2sblTok" type="password"' in js and 'autocomplete="new-password"' in js
    assert "r.body.token = ''" in js and "f.token.value = ''" in js
    # رمز الدخول إلى اللوحة: يُمسح عند الإغلاق ولا يدخل أي مخزن
    assert "d.token = ''" in js and 'function wipe()' in js and "q('#v2sbDone', s).onclick = function () { wipe();" in js
    assert not re.search(r"(localStorage|sessionStorage)\.setItem\([^)]*(token|tok|Tok)", js)
    assert not re.search(r"S\.[A-Za-z]*[tT]oken\s*=", js), 'الرمز لا يُحفظ في حالة الشاشة'
    # العنوان للمؤسس يأتي من الخادم لا من نص ثابت
    assert 'ti.serverUrl' in js and 'dashboard.elprofessor.net' not in js
    # كل كتابة بتأكيد صريح، والمسارات في مكانها
    for frag in ("'/v2/brain/links', { method: 'POST', body: r.body }", "'/v2/brain/mcp-tokens', { method: 'POST', body: r.body }",
                 "method: 'DELETE', body: { confirmed: true }", "{ enabled: !row.enabled, confirmed: true }"):
        assert frag in js, frag
    assert js.count("{ method: 'POST', body: {} }") >= 2 and "/test', { method: 'POST', body: {} }" in js
    # تحميل كسول للمصدرين في تبويب المساعدين
    assert "load('links', false); load('mcpTokens', false)" in js
    # أهداف اللمس وعرض الموبايل
    assert '.v2sb-addrr .v3-btn2{width:100%;min-height:52px}' in css and '.v2sb-addrv{' in css and 'overflow-wrap:anywhere' in css
