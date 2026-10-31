# -*- coding: utf-8 -*-
"""«الأنظمة المتصلة» (SPEC-B B5b): اللوحة عميل MCP لأنظمة أخرى (مدار وغيرها).

* الجدول `v2_brain_links`: الاسم · العنوان (https) · الرمز مشفّرًا بنفس `keys.encrypt` (AES-GCM) · مفعّل · آخر نجاح · آخر خطأ.
  ⛔ النص الصريح للرمز لا يخرج من الخادم أبدًا ولا يدخل سجلًّا ولا رسالة خطأ.
* العميل: JSON-RPC 2.0 بسيط (`initialize` ثم `tools/list` و`tools/call`) بمهلة ١٥ ثانية ولا إعادة محاولة. يقرأ ردّ JSON، أو أول حدث `data:` لو ردّ الخادم بـSSE.
* ⛔ هذا الملف لا يستورد `app`. الشبكة كلها في دالة نقل واحدة قابلة للاستبدال (`set_transport`)، فالاختبارات صفر شبكة.
  النقل الحقيقي يرفض إعادة التوجيه، ويرفض مضيفًا يشير إلى عنوان خاص أو محلي.
* أخطاء العميل جمل عربية بيضاء (`LinkError.message`): لا نص من الخادم الآخر ولا مضيف ولا رمز.
"""
import datetime
import json
import logging
import re
import time
from urllib.parse import urlparse

from brain2 import keys as K

logger = logging.getLogger(__name__)

PROTOCOL = '2025-06-18'
TIMEOUT = (5, 10)                 # (اتصال، قراءة) بالثواني — مهلة كل طلب
READ_DEADLINE = 20               # سقف زمن قراءة الرد كله (يمنع التنقيط البطيء من تجميد الخادم)
TEST_BUDGET = 30                 # سقف «جرّب الاتصال» كله
READ_MAX = 1024 * 1024            # أكبر رد نقرؤه (١ ميغابايت)
NAME_MAX = 60
BRAND_MAX = 64
LINKS_CAP = 10
TOOLS_SHOWN = 40                  # أسماء الأدوات التي نعرضها في «جرّب الاتصال»
CLIENT_INFO = {'name': 'elprofessor-dashboard', 'version': '1.0'}

ERR_TIMEOUT = 'لم يصل رد في الوقت المناسب'
ERR_CONNECT = 'تعذّر الاتصال بهذا العنوان'
ERR_AUTH = 'الرمز غير مقبول عند النظام الآخر'
ERR_NOT_FOUND = 'العنوان غير صحيح عند النظام الآخر'
ERR_BAD_REPLY = 'جاء رد غير مفهوم من النظام الآخر'
ERR_REMOTE = 'رفض النظام الآخر الطلب'
ERR_UNREADABLE = 'تعذّرت قراءة الرمز المحفوظ؛ أضِف النظام من جديد'
ERR_PRIVATE = 'هذا العنوان غير مسموح به'

_CTRL_RE = re.compile('[\x00-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]')


class LinkError(Exception):
    """فشل عميل MCP. `message` عربي أبيض يُعرض كما هو."""

    def __init__(self, message, status=0):
        super().__init__(message)
        self.message = message
        self.status = status


# ------------------------------------------------------------------ الجدول

_MODEL = {}


def _models(db):
    """V2BrainLink — تُعرَّف مرة واحدة (نفس نمط بقية جداول العقل)."""
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class V2BrainLink(db.Model):
        __tablename__ = 'v2_brain_links'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.String(32), primary_key=True)
        name = db.Column(db.String(NAME_MAX), nullable=False)
        url = db.Column(db.String(K.URL_MAX), nullable=False)
        token_enc = db.Column(db.Text, nullable=False)
        enabled = db.Column(db.Boolean, nullable=False, default=True)
        brand_id = db.Column(db.String(BRAND_MAX))       # اختياري: بعض الأنظمة (مدار) تطلب معرّف العلامة في أدوات الأرقام
        last_ok_at = db.Column(db.DateTime)
        last_error = db.Column(db.String(200))
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        created_by = db.Column(db.String(255))

    _MODEL['cls'] = V2BrainLink
    return V2BrainLink


def clean_name(s):
    if not isinstance(s, str):
        return ''
    return re.sub(r'\s+', ' ', _CTRL_RE.sub('', s)).strip()[:NAME_MAX + 1]


def clean_brand(s):
    if not isinstance(s, str):
        return None
    s = s.strip()
    return s if re.match(r'^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$', s) else None


def token_of(row):
    """النص الصريح للرمز من الصف، أو None لو لا يُفكّ. ⛔ للاستعمال الداخلي في العميل وحده."""
    return K.decrypt(row.token_enc)


# ------------------------------------------------------------------ النقل

_TRANSPORT = {'fn': None}


def set_transport(fn):
    """للاختبار: دالة `(url, headers, body_bytes, timeout) -> (status, headers, text)` تحلّ محل الشبكة. None = الحقيقي."""
    _TRANSPORT['fn'] = fn


def _host_is_public(host):
    """لا نتصل بمضيف يشير إلى عنوان خاص أو محلي (حماية من توجيه الاسم إلى الشبكة الداخلية). المنطق المشترك في `keys.host_is_public`."""
    return K.host_is_public(host)


def _real_transport(url, headers, body, timeout):
    import requests
    host = (urlparse(url).hostname or '').lower()
    if not _host_is_public(host):
        raise LinkError(ERR_PRIVATE)
    total = READ_DEADLINE
    if isinstance(timeout, tuple) and len(timeout) == 3:
        timeout, total = timeout[:2], timeout[2]
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=timeout, allow_redirects=False, stream=True)
    except requests.exceptions.Timeout:
        raise LinkError(ERR_TIMEOUT)
    except requests.exceptions.RequestException:
        raise LinkError(ERR_CONNECT)
    try:
        ctype = (resp.headers.get('Content-Type') or '').lower()
        buf = b''
        deadline = time.monotonic() + total
        for chunk in resp.iter_content(chunk_size=4096):
            buf += chunk
            if time.monotonic() > deadline:
                raise LinkError(ERR_TIMEOUT)
            if len(buf) > READ_MAX:
                break
            if 'text/event-stream' in ctype and _sse_has_reply(buf):
                break          # أول حدث فيه الرد يكفي؛ لا ننتظر إغلاق الاتصال
        return resp.status_code, dict(resp.headers), buf[:READ_MAX].decode('utf-8', 'replace')
    except requests.exceptions.Timeout:
        raise LinkError(ERR_TIMEOUT)
    except requests.exceptions.RequestException:
        raise LinkError(ERR_CONNECT)
    finally:
        try:
            resp.close()
        except Exception:   # noqa: BLE001
            pass


def _sse_has_reply(buf):
    try:
        t = buf.decode('utf-8', 'ignore')
    except Exception:   # noqa: BLE001
        return False
    return '\n\n' in t.replace('\r\n', '\n') and ('"result"' in t or '"error"' in t)


# ------------------------------------------------------------------ قراءة الردود

def sse_events(text):
    """أحداث `data:` من نص SSE: كل حدث نصّ بيانات واحد (أسطر data المتتالية تُضمّ بسطر جديد)."""
    out, cur = [], []
    for line in str(text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if line == '':
            if cur:
                out.append('\n'.join(cur))
                cur = []
        elif line.startswith('data:'):
            cur.append(line[5:].lstrip(' ') if line[5:6] == ' ' else line[5:])
    if cur:
        out.append('\n'.join(cur))
    return out


def parse_reply(text, content_type='', req_id=None):
    """ردّ JSON، أو أول حدث `data:` يطابق معرّف الطلب (وإلا أول حدث). يرجع dict أو يرفع LinkError."""
    t = str(text or '').strip()
    if not t:
        raise LinkError(ERR_BAD_REPLY)
    looks_sse = 'text/event-stream' in (content_type or '').lower() or t.startswith(('data:', 'event:', 'id:', ':'))
    if looks_sse:
        found = None
        for ev in sse_events(t):
            try:
                obj = json.loads(ev)
            except ValueError:
                continue
            if not isinstance(obj, dict):
                continue
            if found is None:
                found = obj
            if req_id is None or obj.get('id') == req_id:
                return obj
        if found is None:
            raise LinkError(ERR_BAD_REPLY)
        return found
    try:
        obj = json.loads(t)
    except ValueError:
        raise LinkError(ERR_BAD_REPLY)
    if not isinstance(obj, dict):
        raise LinkError(ERR_BAD_REPLY)
    return obj


# ------------------------------------------------------------------ العميل

class McpClient(object):
    """عميل JSON-RPC صغير. كل طلب نداء HTTP واحد بمهلة ثابتة ولا إعادة محاولة."""

    def __init__(self, url, token, transport=None, timeout=TIMEOUT, budget=None):
        self.url, self._token, self.timeout = url, token, timeout
        self._deadline = (time.monotonic() + budget) if budget else None
        self._transport = transport
        self._id = 0
        self._session = ''
        self._initialized = False

    def _post(self, payload):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
                   'Authorization': 'Bearer ' + self._token, 'MCP-Protocol-Version': PROTOCOL}
        if self._session:
            headers['Mcp-Session-Id'] = self._session
        fn = self._transport or _TRANSPORT['fn'] or _real_transport
        tmo = self.timeout
        if self._deadline is not None:
            left = self._deadline - time.monotonic()
            if left <= 0:
                raise LinkError(ERR_TIMEOUT)
            tmo = (tmo[0], min(tmo[1], left), min(READ_DEADLINE, left))     # الثالث: سقف قراءة الرد كله ضمن ميزانية الاختبار
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        try:
            status, rh, text = fn(self.url, headers, body, tmo)
        except LinkError:
            raise
        except TimeoutError:
            raise LinkError(ERR_TIMEOUT)
        except OSError:
            raise LinkError(ERR_CONNECT)
        except Exception as exc:   # noqa: BLE001 — مهلة/اتصال من مكتبة أخرى؛ لا نص منها يخرج
            logger.warning('brain link transport failed: %s', type(exc).__name__)
            raise LinkError(ERR_TIMEOUT if 'timeout' in type(exc).__name__.lower() else ERR_CONNECT)
        return int(status or 0), {str(k).lower(): v for k, v in (rh or {}).items()}, text

    def _check_status(self, status):
        if status in (401, 403):
            raise LinkError(ERR_AUTH, status)
        if status in (404, 405, 410):
            raise LinkError(ERR_NOT_FOUND, status)
        if status == 429:
            raise LinkError('النظام الآخر يطلب التمهّل؛ جرّب بعد قليل', status)
        if status >= 400 or status == 0:
            raise LinkError(ERR_CONNECT, status)

    def request(self, method, params=None):
        self._id += 1
        rid = self._id
        payload = {'jsonrpc': '2.0', 'id': rid, 'method': method}
        if params is not None:
            payload['params'] = params
        status, rh, text = self._post(payload)
        self._check_status(status)
        if method == 'initialize' and rh.get('mcp-session-id'):
            self._session = str(rh['mcp-session-id'])[:200]
        obj = parse_reply(text, rh.get('content-type', ''), rid)
        if isinstance(obj.get('error'), dict):
            raise LinkError(ERR_REMOTE, status)
        if 'result' not in obj:
            raise LinkError(ERR_BAD_REPLY, status)
        return obj['result']

    def initialize(self):
        res = self.request('initialize', {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': CLIENT_INFO})
        self._initialized = True
        try:       # إشعار الجاهزية: يُرسل مرة واحدة وفشله لا يوقف شيئًا
            self._post({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        except LinkError:
            pass
        return res if isinstance(res, dict) else {}

    def list_tools(self):
        """⇒ قائمة أدوات `[{name, description, inputSchema}]` (حتى صفحة واحدة)."""
        res = self.request('tools/list', {})
        tools = res.get('tools') if isinstance(res, dict) else None
        if not isinstance(tools, list):
            raise LinkError(ERR_BAD_REPLY)
        return [t for t in tools if isinstance(t, dict) and isinstance(t.get('name'), str)]

    def call_tool(self, name, arguments=None):
        """⇒ نتيجة الأداة: `structuredContent` إن وُجد وإلا JSON النص الأول وإلا النص نفسه."""
        res = self.request('tools/call', {'name': name, 'arguments': arguments or {}})
        if not isinstance(res, dict):
            raise LinkError(ERR_BAD_REPLY)
        if res.get('isError') is True:
            raise LinkError(ERR_REMOTE)
        if isinstance(res.get('structuredContent'), (dict, list)):
            return res['structuredContent']
        for part in res.get('content') or []:
            if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str):
                try:
                    return json.loads(part['text'])
                except ValueError:
                    return {'text': part['text'][:2000]}
        return {}


def client_for(row, transport=None):
    """عميل لصف رابط. يرفع LinkError(ERR_UNREADABLE) لو الرمز لا يُفكّ."""
    token = token_of(row)
    if not token:
        raise LinkError(ERR_UNREADABLE)
    return McpClient(row.url, token, transport=transport)


def probe(row, transport=None):
    """`initialize` + `tools/list` ⇒ {'tools': [names], 'count': n, 'server': name}. يرفع LinkError عند الفشل."""
    c = client_for(row, transport)
    c._deadline = time.monotonic() + TEST_BUDGET
    info = c.initialize()
    tools = c.list_tools()
    names = [t['name'][:80] for t in tools]
    srv = info.get('serverInfo') if isinstance(info.get('serverInfo'), dict) else {}
    return {'count': len(names), 'tools': names[:TOOLS_SHOWN], 'server': clean_name(srv.get('name')) if isinstance(srv.get('name'), str) else ''}


def mark(db, row, ok, error=''):
    """يسجّل نتيجة آخر اتصال على الصف. أي فشل في الحفظ يُسجَّل ولا يكسر المنادي."""
    try:
        if ok:
            row.last_ok_at, row.last_error = datetime.datetime.utcnow(), None
        else:
            row.last_error = (error or ERR_CONNECT)[:200]
        db.session.commit()
    except Exception:   # noqa: BLE001
        db.session.rollback()
        logger.exception('brain links: mark failed')
