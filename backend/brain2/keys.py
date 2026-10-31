# -*- coding: utf-8 -*-
"""«المفاتيح والكاتب» (SPEC-B B1): مفاتيح مزوّدي الذكاء في القاعدة، مشفّرة، ويُبدَّل الكاتب في أي وقت.

* التشفير: AES-GCM (مكتبة `cryptography`) بمفتاح مشتق بـHKDF-SHA256 من `DASH_KEYS_SECRET` وإلا `SECRET_KEY`، info = `b"brain-keys-v1"`.
  النص المخزَّن `v1:<base64url(nonce‖ciphertext)>`؛ البادئة تسمح بالتدوير لاحقًا. فكّ فاشل ⇒ المفتاح «مفقود» (لا استثناء يخرج).
* ⛔ النص الصريح لا يخرج من الخادم أبدًا: الشاشة ترى `key_tail` فقط (آخر ٤ أحرف).
* القوالب (presets) وعناوينها على الخادم؛ المتصفح يأخذ الأسماء فقط. «أخرى» دائمًا موجودة وعنوانها https من المؤسس.
* هذا الملف لا يستورد `app` (يُقرأ كل شيء من `db` الممرَّر)، فتستعمله حزمة MCP (`links.py`) لتشفير توكناتها بنفس الدوال: `encrypt` / `decrypt`.
* ⛔ صفر شبكة هنا: النداء الفعلي في `app.ai_call` (وناقلاه المعروفان) وفي مسار الاختبار.
"""
import base64
import datetime
import ipaddress
import logging
import os
import re
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)

HKDF_INFO = b'brain-keys-v1'
VERSION = 'v1'
UNREADABLE_AR = 'تعذّرت قراءة هذا المفتاح؛ أضِفه من جديد'

KINDS = ('anthropic', 'openai_compat')
ROLES = ('main', 'backup', 'off')
ROLE_LABEL = {'main': 'الأساسي', 'backup': 'الاحتياطي', 'off': 'موقوف'}
LABEL_MAX = 60
MODEL_MAX = 80
URL_MAX = 200
KEY_MIN = 8
KEY_MAX = 400
KEYS_CAP = 12

# القوالب. ⛔ العناوين هنا فقط؛ الواجهة تأخذ (id, label, needs_url, default_model).
PRESETS = (
    {'id': 'claude', 'label': 'Claude', 'kind': 'anthropic', 'base_url': '', 'model': 'claude-sonnet-5-5', 'needs_url': False},
    {'id': 'deepseek', 'label': 'DeepSeek', 'kind': 'openai_compat', 'base_url': 'https://api.deepseek.com/v1', 'model': 'deepseek-v4-flash', 'needs_url': False},
    {'id': 'glm', 'label': 'GLM', 'kind': 'openai_compat', 'base_url': 'https://api.z.ai/api/paas/v4', 'model': 'glm-4.6', 'needs_url': False},
    {'id': 'openai', 'label': 'OpenAI', 'kind': 'openai_compat', 'base_url': 'https://api.openai.com/v1', 'model': 'gpt-4.1-mini', 'needs_url': False},
    {'id': 'openrouter', 'label': 'OpenRouter', 'kind': 'openai_compat', 'base_url': 'https://openrouter.ai/api/v1', 'model': '', 'needs_url': True},
    {'id': 'other', 'label': 'أخرى', 'kind': 'openai_compat', 'base_url': '', 'model': '', 'needs_url': True},
)
_PRESET_BY_ID = {p['id']: p for p in PRESETS}

ERR_PRESET = 'اختر الجهة من القائمة'
ERR_LABEL = 'الاسم أطول من ٦٠ حرفًا'
ERR_MODEL = 'اكتب اسم الموديل (حتى ٨٠ حرفًا، بلا مسافات)'
ERR_URL = 'اكتب عنوانًا يبدأ بـ https://'
ERR_KEY = 'المفتاح غير مكتمل أو فيه مسافات'
ERR_ROLE = 'اختر دور المفتاح'
ERR_NOTHING = 'لا تعديل مطلوب'
ERR_FULL = 'وصلت إلى حدّ المفاتيح المحفوظة. احذف مفتاحًا قبل إضافة غيره'
ERR_BAD_ID = 'معرّف غير صالح'
ERR_NOT_FOUND = 'هذا المفتاح غير موجود'

BAD_KEY_AR = 'المفتاح غير صحيح'
BAD_MODEL_AR = 'الموديل غير موجود'
NO_REPLY_AR = 'لم يصل رد'

_CTRL_RE = re.compile('[\x00-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]')
_MODEL_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._:/@+\-]*$')
_KEY_RE = re.compile(r'^[\x21-\x7e]+$')   # ASCII مرئي بلا مسافات


# ------------------------------------------------------------------ التشفير

def get_secret():
    """`DASH_KEYS_SECRET` إن ضُبط وإلا `SECRET_KEY` (من إعداد Flask الفعلي، وإلا من البيئة)."""
    s = (os.environ.get('DASH_KEYS_SECRET') or '').strip()
    if s:
        return s
    try:
        from flask import current_app
        s = current_app.config.get('SECRET_KEY') or ''
    except Exception:   # noqa: BLE001 — خارج سياق التطبيق
        s = ''
    return str(s or os.environ.get('SECRET_KEY') or '')


def _derive(secret):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=HKDF_INFO).derive(str(secret).encode('utf-8'))


def encrypt(plaintext, secret=None):
    """نص صريح ⇒ `v1:<base64url>`. يرفع ValueError لو لا سرّ مضبوط أو النص فاضي."""
    secret = secret if secret is not None else get_secret()
    if not secret:
        raise ValueError('no secret configured')
    if not isinstance(plaintext, str) or not plaintext:
        raise ValueError('empty plaintext')
    nonce = os.urandom(12)
    ct = AESGCM(_derive(secret)).encrypt(nonce, plaintext.encode('utf-8'), HKDF_INFO)
    return VERSION + ':' + base64.urlsafe_b64encode(nonce + ct).decode('ascii')


def decrypt(token, secret=None):
    """`v1:…` ⇒ النص الصريح، أو None لأي فشل (سرّ مختلف · تلف · إصدار غير معروف). لا استثناء يخرج."""
    try:
        secret = secret if secret is not None else get_secret()
        if not secret or not isinstance(token, str) or not token.startswith(VERSION + ':'):
            return None
        raw = base64.urlsafe_b64decode(token[len(VERSION) + 1:].encode('ascii'))
        if len(raw) < 12 + 16:
            return None
        return AESGCM(_derive(secret)).decrypt(raw[:12], raw[12:], HKDF_INFO).decode('utf-8')
    except Exception:   # noqa: BLE001
        return None


# ------------------------------------------------------------------ الجدول

_MODEL = {}


def _models(db):
    """V2BrainKey — تُعرَّف مرة واحدة (نفس نمط بقية جداول العقل)."""
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class V2BrainKey(db.Model):
        __tablename__ = 'v2_brain_keys'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.String(32), primary_key=True)
        label = db.Column(db.String(LABEL_MAX), nullable=False)
        preset = db.Column(db.String(20))
        kind = db.Column(db.String(16), nullable=False)
        base_url = db.Column(db.String(URL_MAX))
        model = db.Column(db.String(MODEL_MAX))
        key_enc = db.Column(db.Text, nullable=False)
        key_tail = db.Column(db.String(4))
        role = db.Column(db.String(8), nullable=False, default='off', index=True)
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        created_by = db.Column(db.String(255))
        last_test_at = db.Column(db.DateTime)
        last_test_ok = db.Column(db.Boolean)
        last_test_error = db.Column(db.String(200))

    _MODEL['cls'] = V2BrainKey
    return V2BrainKey


# ------------------------------------------------------------------ القوالب والتحقق

def preset_of(preset_id):
    return _PRESET_BY_ID.get(preset_id) if isinstance(preset_id, str) else None


def presets_public():
    """للمتصفح: الاسم وهل يحتاج عنوانًا والموديل الافتراضي — ⛔ لا عناوين."""
    return [{'id': p['id'], 'label': p['label'], 'needs_url': bool(p['needs_url']), 'default_model': p['model']} for p in PRESETS]


def clean_line(s, limit):
    if not isinstance(s, str):
        return ''
    return re.sub(r'\s+', ' ', _CTRL_RE.sub('', s)).strip()[:limit + 1]


def valid_model(m):
    return isinstance(m, str) and 1 <= len(m) <= MODEL_MAX and bool(_MODEL_RE.match(m))


def valid_key_text(k):
    return isinstance(k, str) and KEY_MIN <= len(k) <= KEY_MAX and bool(_KEY_RE.match(k))


def normalize_url(raw):
    """https فقط · بلا بيانات دخول ولا استعلام · لا مضيف محلي/خاص. يرجّع (url|None). شرطة مائلة أخيرة تُحذف."""
    if not isinstance(raw, str):
        return None
    u = raw.strip()
    if not u or len(u) > URL_MAX or re.search(r'[\s\x00-\x1f\x7f]', u):
        return None
    try:
        p = urlparse(u)
        host = (p.hostname or '').lower()
        p.port   # يرفع ValueError لمنفذ غير صالح
    except ValueError:
        return None
    if p.scheme != 'https' or not host or p.username or p.password or p.query or p.fragment or '@' in p.netloc:
        return None
    if host == 'localhost' or host.endswith(('.local', '.internal', '.localhost', '.lan')) or ('.' not in host and ':' not in host):
        return None
    try:
        ip = ipaddress.ip_address(host.strip('[]'))
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return None
    except ValueError:
        pass
    return u.rstrip('/')


def resolve_target(preset, base_url_in):
    """(kind, base_url) للقالب: القوالب الجاهزة عنوانها من الخادم، OpenRouter عنوانه الافتراضي قابل للتبديل، «أخرى» عنوانها إلزامي. (None, None) لو غير صالح."""
    if preset['id'] == 'other' or preset['id'] == 'openrouter':
        if preset['id'] == 'openrouter' and not (isinstance(base_url_in, str) and base_url_in.strip()):
            return preset['kind'], preset['base_url']
        url = normalize_url(base_url_in)
        return (preset['kind'], url) if url else (None, None)
    return preset['kind'], preset['base_url']


def tail_of(key):
    return key[-4:]


# ------------------------------------------------------------------ الاختيار وقت النداء

def row_spec(row, key):
    return {'id': row.id, 'label': row.label, 'preset': row.preset or '', 'kind': row.kind, 'base_url': row.base_url or '',
            'model': row.model or '', 'api_key': key, 'role': row.role}


def active_chain(db):
    """[مواصفة الأساسي، مواصفة الاحتياطي] القابلتين للقراءة فقط (الدور main ثم backup). مفتاح لا يُفكّ ⇒ كأنه غير موجود.
    ⛔ ترجع النص الصريح للمفتاح — للاستعمال الداخلي في ai_call وحده ولا تدخل أي رد HTTP."""
    Key = _models(db)
    chain = []
    for role in ('main', 'backup'):
        row = Key.query.filter_by(role=role).order_by(Key.created_at.desc(), Key.id).first()
        if row is None:
            continue
        key = decrypt(row.key_enc)
        if not key:
            logger.warning('brain keys: %s key %s is unreadable (secret changed?) — treated as missing', role, row.id)
            continue
        chain.append(row_spec(row, key))
    return chain


def classify_error(exc):
    """خطأ ناقل ⇒ إحدى ثلاث جمل عربية بيضاء. ⛔ لا نص من المزوّد ولا مضيف ولا مسار يخرج."""
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    body = ''
    try:
        resp = getattr(exc, 'response', None)
        body = (resp.text or '')[:400].lower() if resp is not None else ''
    except Exception:   # noqa: BLE001
        body = ''
    if status in (401, 403):
        return BAD_KEY_AR
    if status == 404 or (status in (400, 422) and 'model' in body):
        return BAD_MODEL_AR
    return NO_REPLY_AR
