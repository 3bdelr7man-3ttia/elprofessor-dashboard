# -*- coding: utf-8 -*-
"""R16 — تليجرام اللوحة: المُرسِل الواحد، «جرّب التنبيهات»، سجلّ آخر ٢٠، مراقبة التشغيل، الملخص اليومي، وصفّ «تسجيل جديد».

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r16_tg_ops.py

⛔ صفر شبكة: `requests.post/request/get` مزيّفة في كل اختبار، ولا توكن حقيقي.
"""
import datetime
import os
import re

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod
from app import app as flask_app, db, User
import tg_ops

NS = appmod.__dict__
SECRET = 'test-metrics-secret'
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class R:
    def __init__(self, status=200, body=None, text=''):
        self.status_code = status
        self._body = body
        self.text = text
        self.content = b'x'

    def json(self):
        if self._body is None:
            raise ValueError('no json')
        return self._body


class Net:
    """يلتقط كل نداء HTTP ويردّ من طابور (آخر ردّ يتكرّر)."""
    def __init__(self):
        self.calls = []
        self.replies = []

    def _next(self):
        r = self.replies[0] if self.replies else R(200, {'ok': True})
        if len(self.replies) > 1:
            self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, url, json=None, timeout=None, **k):
        self.calls.append(('POST', url, json, k.get('headers')))
        return self._next()

    def request(self, method, url, json=None, headers=None, timeout=None, **k):
        self.calls.append((method, url, json, headers))
        return self._next()


@pytest.fixture()
def net(monkeypatch):
    n = Net()
    monkeypatch.setattr(tg_ops.requests, 'post', n.post)
    monkeypatch.setattr(tg_ops.requests, 'request', n.request)
    monkeypatch.setattr(tg_ops.requests, 'get', lambda *a, **k: (_ for _ in ()).throw(AssertionError('get ممنوع')))
    monkeypatch.setattr(tg_ops, 'RETRY_DELAYS', (0, 0))
    for v in ('TELEGRAM_OPS_BOT_TOKEN', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_ADMIN_CHAT_ID', 'DASH_WATCH_URLS', 'DASH_SCHEDULER'):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    with flask_app.app_context():
        tg_ops._STATE['model'].query.delete()
        tg_ops._STATE['kv'].query.delete()
        db.session.commit()
        yield n
        tg_ops._STATE['model'].query.delete()
        tg_ops._STATE['kv'].query.delete()
        db.session.commit()


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
                 name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
                 preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = u.dashboard_role = role
    u.is_active = True
    db.session.commit()
    tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


# ───────────────────────────────────────────────────────── الطريق: مباشر أم عبر المنصة

def test_bridge_mode_sends_through_platform_and_logs_reason(net):
    net.replies = [R(200, {'ok': False, 'reason': 'no_chat', 'detail': '', 'tries': 0})]
    out = tg_ops.send(NS, 'نصّ', kind='uptime')
    assert out['mode'] == 'bridge' and out['ok'] is False and out['reason'] == 'no_chat'
    method, url, body, headers = net.calls[0]
    assert url.endswith('/api/bridge/telegram/send') and headers['X-ELP-Metrics-Secret'] == SECRET
    assert body['kind'] == 'uptime'
    rows = tg_ops.recent(NS)
    assert rows[0]['reason'] == 'no_chat' and rows[0]['kind'] == 'uptime' and rows[0]['mode'] == 'bridge'
    assert 'نصّ' not in repr(rows)


def test_bridge_without_secret_says_so(net, monkeypatch):
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    out = tg_ops.send(NS, 'x')
    assert out['reason'] == 'no_bridge_secret' and net.calls == []


def test_direct_mode_retries_network_then_classifies(net, monkeypatch):
    monkeypatch.setenv('TELEGRAM_OPS_BOT_TOKEN', 'TK')
    monkeypatch.setenv('TELEGRAM_ADMIN_CHAT_ID', '42')
    net.replies = [RuntimeError('down'), R(400, {'description': 'Bad Request: chat not found'})]
    out = tg_ops.send(NS, 'x', links=[{'text': 'افتح', 'url': 'https://elprofessor.net/'}, {'url': 'http://bad'}])
    assert out['mode'] == 'direct' and out['reason'] == 'wrong_chat' and out['tries'] == 2
    _, url, body, _ = net.calls[-1]
    assert '/sendMessage' in url and body['reply_markup']['inline_keyboard'] == [[{'text': 'افتح', 'url': 'https://elprofessor.net/'}]]
    assert 'TK' not in repr(tg_ops.recent(NS))


def test_log_keeps_bounded_rows_and_status_shows_twenty(net):
    for _ in range(25):
        tg_ops.send(NS, 'x')
    assert len(tg_ops.recent(NS)) == 20


# ───────────────────────────────────────────────────────── الزرّ: أدمن بس

def test_selftest_and_status_endpoints_are_admin_only(net):
    client = flask_app.test_client()
    with flask_app.app_context():
        admin = _mkuser('r16-admin@x.test', 'admin')
        viewer = _mkuser('r16-viewer@x.test', 'viewer')
    assert client.post('/api/telegram/selftest').status_code == 401
    assert client.post('/api/telegram/selftest', headers=viewer).status_code == 403
    assert client.get('/api/telegram/status', headers=viewer).status_code == 403
    net.replies = [R(200, {'ok': False, 'reason': 'wrong_chat', 'detail': '400 Bad Request: chat not found',
                           'config': {'token_set': True}, 'webhook': {'ok': True, 'url_set': False}})]
    r = client.post('/api/telegram/selftest', headers=admin)
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    js = r.get_json()
    assert js['ok'] is False and js['reason'] == 'wrong_chat' and 'chat not found' in js['detail']
    assert js['platform']['webhook']['url_set'] is False
    st = client.get('/api/telegram/status', headers=admin).get_json()
    assert st['attempts'][0]['kind'] == 'selftest' and st['config']['mode'] == 'bridge'
    assert [u['label'] for u in st['uptime']] == ['التطبيق', 'خادم المنصة', 'الموقع']


def test_signups_inbox_proxy_and_ack(net):
    client = flask_app.test_client()
    with flask_app.app_context():
        admin = _mkuser('r16-admin@x.test', 'admin')
    seen = []

    def proxy(method, path, params=None, json_body=None, timeout=12, **k):
        seen.append((method, path, json_body))
        from flask import jsonify
        return jsonify({'ok': True, 'signups': []})

    old = NS['_platform_proxy']
    NS['_platform_proxy'] = proxy
    try:
        assert client.get('/api/platform-signups', headers=admin).status_code == 200
        assert client.post('/api/platform-signups/u-1/ack', headers=admin).status_code == 200
        assert client.post('/api/platform-signups/bad%20id/ack', headers=admin).status_code == 400
    finally:
        NS['_platform_proxy'] = old
    assert seen[0][:2] == ('GET', '/api/bridge/signups/recent')
    assert seen[1][1] == '/api/bridge/signups/u-1/ack' and seen[1][2]['by'] == 'r16-admin@x.test'


# ───────────────────────────────────────────────────────── مراقبة التشغيل

def test_uptime_alerts_after_two_failures_and_once_on_recovery(net):
    state = {'code': 503}

    def get(url, timeout=None, allow_redirects=True):
        if 'api.elprofessor.net' in url:
            return R(403)               # خلف القفل = شغّال
        return R(state['code'])

    assert tg_ops.check_uptime(NS, get=get) == []                       # فشل أول: لا تنبيه
    sent2 = tg_ops.check_uptime(NS, get=get)
    assert sorted(sent2) == [('down', 'https://app.elprofessor.net/'), ('down', 'https://elprofessor.net/')]
    assert tg_ops.check_uptime(NS, get=get) == []                       # ما زال واقعًا: لا تكرار
    state['code'] = 200
    sent4 = tg_ops.check_uptime(NS, get=get)
    assert sorted(sent4) == [('up', 'https://app.elprofessor.net/'), ('up', 'https://elprofessor.net/')]
    assert tg_ops.check_uptime(NS, get=get) == []
    kinds = [c[2]['kind'] for c in net.calls]
    assert kinds == ['uptime'] * 4
    assert any('مش شغّال' in c[2]['text'] for c in net.calls) and any('رجع يشتغل' in c[2]['text'] for c in net.calls)


def test_network_exception_counts_as_down(net):
    def get(url, **k):
        raise ConnectionError('dns')
    tg_ops.check_uptime(NS, get=get)
    assert len(tg_ops.check_uptime(NS, get=get)) == 3


# ───────────────────────────────────────────────────────── الملخص اليومي

def test_digest_lists_inbox_items_once_a_day(net):
    queue = {'alerts_v2': [{'key': 'signups_new', 'count': 3}, {'key': 'manual_payments', 'count': 1}],
             'enrollments_24h': 2}
    net.replies = [R(200, queue), R(200, {'ok': True, 'reason': 'ok'})]
    out = tg_ops.send_digest(NS)
    assert out['ok'] is True
    text = [c for c in net.calls if c[1].endswith('/api/bridge/telegram/send')][0][2]['text']
    assert 'تسجيلات جديدة لم تُراجع: ٣' in text and 'إيصالات تحويل: ١' in text
    assert not re.search(r'·\s*[٠-٩]|[٠-٩]\s*·', text)
    assert tg_ops.send_digest(NS)['reason'] == 'already_sent'


def test_digest_failure_retries_hourly_not_every_minute(net):
    net.replies = [R(500, None, 'x')]
    first = tg_ops.send_digest(NS)
    assert first['ok'] is False
    n = len(net.calls)
    assert tg_ops.send_digest(NS)['reason'] == 'retry_later' and len(net.calls) == n


# ───────────────────────────────────────────────────────── الحرّاس الثابتة

def test_scheduler_never_starts_under_pytest():
    assert tg_ops.scheduler_allowed() is False


def test_single_sender_no_other_telegram_calls_in_dashboard():
    hits = []
    for base, _dirs, files in os.walk(os.path.join(ROOT, 'backend')):
        if '/tests' in base or '/dist' in base:
            continue
        for f in files:
            if f.endswith('.py') and f != 'tg_ops.py':
                src = open(os.path.join(base, f), encoding='utf-8').read()
                if 'api.telegram.org' in src or '/api/bridge/telegram/send' in src:
                    hits.append(f)
    assert hits == [], hits


def test_dockerfile_ships_tg_ops():
    src = open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()
    assert 'COPY backend/tg_ops.py /app/tg_ops.py' in src


# ───────────────────────────────────────────────────────── الواجهة: الزرّ وصفّ «تسجيل جديد»

def _ui(name):
    return open(os.path.join(ROOT, 'dashboard-cloud', name), encoding='utf-8').read()


def test_settings_has_the_one_button_and_status_list():
    src = _ui('index.html')
    assert 'data-tg="test"' in src and "'/telegram/selftest'" in src
    assert 'data-tg="arm"' in src and "'/telegram/arm-webhook'" in src
    assert "/telegram/status?platform=1" in src and 'tgPanelWire();' in src
    i = src.index('const TG_REASON=')
    block = src[i:src.index('function tgPanelWire()')]
    for r in ('no_token', 'no_chat', 'wrong_chat', 'bad_token', 'bot_not_allowed', 'telegram_error', 'network', 'no_bridge_secret'):
        assert r + ':' in block


def test_signup_rows_reach_the_inbox_with_an_action():
    api = _ui('dashboard-api.js')
    assert 'get("/platform-signups")' in api and 'apiKind: "signup"' in api
    assert 'case "signup":' in api and '"/platform-signups/" + encodeURIComponent(i.apiId) + "/ack"' in api
    logic = _ui('v2-logic.js')
    assert "case 'signup': {" in logic and "label: 'تمام، اطّلعت'" in logic


def test_new_visible_copy_follows_the_rules():
    texts = [open(os.path.join(ROOT, 'backend', 'tg_ops.py'), encoding='utf-8').read(),
             _ui('index.html')[_ui('index.html').index('// R16 «تنبيهات تليجرام»'):_ui('index.html').index('  tgLoad();\n}')]]
    for t in texts:
        assert 'استشار' not in t and 'يقوّم' not in t
        assert not re.search(r'·\s*[٠-٩0-9]|[٠-٩0-9]\s*·', t)
