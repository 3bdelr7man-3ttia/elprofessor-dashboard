# -*- coding: utf-8 -*-
"""أداة «ملف للخبير» للواجهة — من غير ولا منفذ ولا سيرفر (الجولة ٦ · SPEC §١١).

    from ef_route_harness import Harness
    h = Harness(ef_fixtures.EFPlatform())          # قبل أي استيراد لـ app لو أمكن
    ctx = h.context(browser, role='admin', viewport={'width': 1440, 'height': 900})

⛔ صفر طلبات حقيقية — على الطبقتين:
  ١. المتصفح: `context.route('**/*')` — `https://dash.test/api/*` بيتنفّذ جوه العملية بـ`app.test_client()`،
     و`https://dash.test/<ملف>` من `dashboard-cloud/` على الديسك (الملف المعدَّل نفسه، مش نسخة مبنية)،
     وأي أصل تاني ⇒ `route.abort()` ويتسجّل في `blocked` (خطوط جوجل بتتقفل هنا كمان).
  ٢. الخادم: `requests.request` و`requests.Session.request` ⇒ `https://platform.test` بس (منصّة في الذاكرة
     من `ef_fixtures.EFPlatform` + فاضي صادق لباقي الجسور)، وأي عنوان تاني ⇒ استثناء ويتسجّل في `blocked_inproc`.
  والسرّ اللي بيتبعت للمنصة المزيّفة `shots-secret` — مش سرّ حقيقي.
"""
import datetime
import json
import mimetypes
import os
import sys
import tempfile
import threading
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(_HERE))
ROOT = os.path.dirname(BACKEND)
DC = os.path.join(ROOT, 'dashboard-cloud')
DASH = 'https://dash.test'
PLATFORM = 'https://platform.test'
SECRET = 'shots-secret'
ALLOWED_ABORTS = ('fonts.googleapis.com', 'fonts.gstatic.com')

_ENV_DROP_PREFIXES = ('SFTP', 'SSH', 'TELEGRAM', 'BREVO', 'STRIPE', 'HOSTINGER', 'DEEPSEEK', 'OPENAI',
                      'ANTHROPIC', 'GEMINI', 'SMTP', 'N8N', 'COOLIFY')


def _prepare_env():
    """قبل استيراد app (لو لسه ما اتستوردش): قاعدة مؤقتة + سرّ تجريبي + منصة وهمية + ولا مفتاح حقيقي."""
    if 'app' in sys.modules:
        return
    os.environ['DATABASE_URL'] = 'sqlite:///' + os.path.join(tempfile.mkdtemp(), 'ef_shots.db')
    os.environ['SECRET_KEY'] = 'ef-shots-secret-key-0123456789abcdefghijklmnop'
    os.environ['METRICS_SECRET'] = SECRET
    os.environ['PLATFORM_API_URL'] = PLATFORM
    os.environ['ADMIN_EMAIL'] = 'admin@local.test'
    os.environ['ADMIN_PASSWORD'] = 'LocalShots!2026'
    os.environ.pop('SEED_DEMO_DATA', None)
    os.environ.pop('RESET_BUSINESS_DATA', None)
    for k in list(os.environ):
        if k.endswith('_API_KEY') or k.startswith(_ENV_DROP_PREFIXES):
            os.environ.pop(k, None)


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.text = self.content.decode('utf-8')
        self.headers = {'Content-Type': 'application/json'}
        self.ok = 200 <= status < 300

    def json(self):
        return self._p


class Harness(object):
    def __init__(self, ef):
        _prepare_env()
        if BACKEND not in sys.path:
            sys.path.insert(0, BACKEND)
        import app as appmod   # noqa: E402
        import requests        # noqa: E402
        self.app = appmod
        self.requests = requests
        self.ef = ef
        self.blocked = []          # المتصفح: أصول اتقفلت (url)
        self.blocked_inproc = []   # الخادم: عناوين اتمنعت
        self.platform_calls = []   # (method, path, params, json)
        self.dash_calls = []       # (method, path) من المتصفح للداشبورد
        self.hold = set()          # (method, path) — الطلب يستنى لحد `release_held()`
        self.held = []
        self._lock = threading.Lock()
        self._saved = {}
        self.client = appmod.app.test_client()
        self._install()
        self.tokens = self._seed()

    # ---------------------------------------------------------------- الخادم: المنصة المزيّفة
    def _fake(self, method, url, params=None, json=None, headers=None, timeout=None, **_kw):
        if not str(url).startswith(PLATFORM + '/'):
            with self._lock:
                self.blocked_inproc.append(str(url))
            raise RuntimeError('طلب حقيقي ممنوع: %s' % url)
        if (headers or {}).get('X-ELP-Metrics-Secret') != SECRET:
            raise RuntimeError('السرّ اللي اتبعت مش سرّ الأداة')
        path = str(url)[len(PLATFORM):]
        with self._lock:
            self.platform_calls.append((method, path, dict(params or {}), json))
        out = self.ef.handle(method, path, params or {}, json or {})
        if out is None:
            out = self._default(method, path)
        return _Resp(*out)

    @staticmethod
    def _default(method, path):
        if path == '/api/admin/metrics':
            return 200, {'customers': {'total': 12}}
        # أي جسر تاني: فاضي صادق (لا صفوف مخترعة) — زي fake_platform.py.
        return 200, []

    def _install(self):
        req = self.requests
        harness = self

        def session_request(sess, method, url, *a, **kw):
            return harness._fake(method, url, params=kw.get('params'), json=kw.get('json'),
                                 headers=kw.get('headers'), timeout=kw.get('timeout'))

        self._saved = {'request': req.request, 'Session.request': req.Session.request,
                       'PLATFORM_API_URL': self.app.PLATFORM_API_URL,
                       'PLATFORM_METRICS_SECRET': self.app.PLATFORM_METRICS_SECRET}
        req.request = self._fake
        req.Session.request = session_request
        self.app.PLATFORM_API_URL = PLATFORM
        self.app.PLATFORM_METRICS_SECRET = SECRET

    def uninstall(self):
        if not self._saved:
            return
        self.requests.request = self._saved['request']
        self.requests.Session.request = self._saved['Session.request']
        self.app.PLATFORM_API_URL = self._saved['PLATFORM_API_URL']
        self.app.PLATFORM_METRICS_SECRET = self._saved['PLATFORM_METRICS_SECRET']
        self._saved = {}

    # ---------------------------------------------------------------- البذرة
    def _seed(self):
        import jwt
        from werkzeug.security import generate_password_hash
        m = self.app
        out = {}
        with m.app.app_context():
            m.db.create_all()
            for email, role in (('admin@local.test', 'admin'), ('staff@local.test', 'employee')):
                u = m.User.query.filter_by(email=email).first()
                if u is None:
                    u = m.User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
                               name='المؤسس' if role == 'admin' else 'موظف المتابعة', role=role,
                               dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
                    m.db.session.add(u)
                else:
                    u.role = role
                    u.dashboard_role = role
                    u.is_active = True
                m.db.session.commit()
                out[role] = jwt.encode({'user_id': u.id,
                                        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                                       m.app.config['SECRET_KEY'], algorithm='HS256')
        return out

    # ---------------------------------------------------------------- المتصفح
    def _api(self, route):
        req = route.request
        u = urlparse(req.url)
        path = u.path + ('?' + u.query if u.query else '')
        headers = {}
        auth = req.headers.get('authorization')
        if auth:
            headers['Authorization'] = auth
        body = req.post_data_buffer
        resp = self.client.open(path, method=req.method, headers=headers, data=body,
                                content_type=req.headers.get('content-type') or None)
        route.fulfill(status=resp.status_code, headers={'content-type': resp.content_type or 'application/json'},
                      body=resp.get_data())

    def _route(self, route):
        req = route.request
        u = urlparse(req.url)
        origin = '%s://%s' % (u.scheme, u.netloc)
        if origin != DASH:
            with self._lock:
                self.blocked.append(req.url)
            return route.abort()
        if u.path.startswith('/api/'):
            key = (req.method, u.path)
            with self._lock:
                self.dash_calls.append(key)
            if key in self.hold:
                self.held.append(route)
                return None
            return self._api(route)
        rel = 'index.html' if u.path in ('', '/') else u.path.lstrip('/')
        full = os.path.normpath(os.path.join(DC, rel))
        if not full.startswith(DC + os.sep) or not os.path.isfile(full):
            return route.fulfill(status=404, body='not found')
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        if ctype.startswith('text/') or ctype.endswith('javascript'):
            ctype += '; charset=utf-8'
        with open(full, 'rb') as fh:
            return route.fulfill(status=200, headers={'content-type': ctype}, body=fh.read())

    def release_held(self):
        """يفكّ الطلبات المحجوزة (صورة «بيرجع…» / ضغطتين ورا بعض) — كل واحد بيتنفّذ دلوقتي."""
        held, self.held = self.held, []
        for r in held:
            self._api(r)
        return len(held)

    def context(self, browser, role='admin', viewport=None, mobile=False):
        opts = {'viewport': viewport or {'width': 1440, 'height': 900}, 'locale': 'ar-EG'}
        if mobile:
            opts.update({'device_scale_factor': 2, 'is_mobile': True, 'has_touch': True})
        ctx = browser.new_context(**opts)
        tok = self.tokens[role]
        ctx.add_init_script("try{localStorage.setItem('token',%s);localStorage.setItem('ep_dash_token',%s);}catch(e){}"
                            % (json.dumps(tok), json.dumps(tok)))
        ctx.route('**/*', self._route)
        return ctx

    def blocked_report(self):
        """{أصل: عدد} للي اتقفل في المتصفح + اللي اتمنع جوه العملية."""
        rep = {}
        for url in self.blocked:
            host = urlparse(url).netloc or url
            rep[host] = rep.get(host, 0) + 1
        return rep

    def unexpected_blocked(self):
        return [u for u in self.blocked if urlparse(u).netloc not in ALLOWED_ABORTS] + list(self.blocked_inproc)
