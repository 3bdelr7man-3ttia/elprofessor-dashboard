# -*- coding: utf-8 -*-
"""اللوحة كخادم MCP (SPEC-B B5a): `POST /api/mcp` — JSON-RPC 2.0 بلا حالة، بروتوكول `2025-06-18`، ردود JSON عادية بلا SSE.

* الطرق: `initialize` · `notifications/initialized` (٢٠٢ بلا جسم) · `tools/list` · `tools/call` · `ping`. الدفعات (batch) ترفض بـ`-32600`. `GET` ⇒ ٤٠٥.
* الدخول: `Authorization: Bearer <رمز>`. الرموز في `v2_mcp_tokens` كـsha256 فقط (النص الصريح يُعرض مرة واحدة عند الإنشاء ولا يُخزَّن).
  ⛔ لا يمرّ من JWT الأدمن. المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤ قبل أي شيء.
* الصلاحيات: `read` أو `read,propose`. ⛔ لا أداة هنا تعتمد أو ترسل أو تنشر أو تلمس مالًا: أدوات الاقتراح تكتب صفًّا `proposed` يقرره المؤسس.
* الحد: ٦٠ نداء أداة في الساعة لكل رمز (نافذة منزلقة في الذاكرة؛ الخدمة عملية واحدة). كل نداء أداة يُسجَّل في التدقيق `mcp.call` باسم الأداة واسم الرمز.
* ⛔ مخرجات أدوات القراءة: عدّادات وعناوين فقط؛ لا اسم عميل ولا بريد ولا هاتف ولا مبلغ (قائمة بيضاء + مرشّح نهائي على كل نص يخرج).
"""
import datetime
import hashlib
import hmac
import json
import logging
import re
import secrets
import threading
import time
import uuid
from collections import deque

from flask import jsonify, make_response, request

logger = logging.getLogger(__name__)

PROTOCOL = '2025-06-18'
SERVER_INFO = {'name': 'elprofessor-dashboard', 'version': '1.0'}
INSTRUCTIONS = 'لوحة البروفيسور: أدوات للقراءة (أرقام وعناوين بلا بيانات عملاء) واقتراح ملاحظات يقرّرها المؤسس. لا شيء يُنفَّذ من هنا.'
RATE_PER_HOUR = 60
RATE_WINDOW = 3600
BODY_MAX = 64 * 1024
TOKEN_PREFIX = 'elpmcp_'
TOKEN_NAME_MAX = 36              # 'mcp:' + الاسم ≤ ٤٠ حرفًا (عمود المنتج في جدول العقل)
SCOPES = ('read', 'read,propose')
TOKENS_CAP = 20
LAST_USED_EVERY = 60             # ثانية: لا نكتب last_used_at أكثر من مرة في الدقيقة

# أكواد JSON-RPC
E_PARSE, E_REQUEST, E_METHOD, E_PARAMS, E_INTERNAL = -32700, -32600, -32601, -32602, -32603
E_AUTH, E_RATE, E_SCOPE = -32001, -32002, -32003

ERR_AUTH = 'الرمز غير صالح أو أُلغي'
ERR_RATE = 'تجاوز هذا الرمز ٦٠ نداءً في الساعة؛ جرّب لاحقًا'
ERR_SCOPE = 'هذا الرمز لا يملك صلاحية الاقتراح'

_clock = time.time
_HITS = {}
_HITS_LOCK = threading.Lock()


def reset_limits():
    """للاختبار."""
    with _HITS_LOCK:
        _HITS.clear()


# ------------------------------------------------------------------ الجدول والرموز

_MODEL = {}


def _models(db):
    """V2McpToken — تُعرَّف مرة واحدة (نفس نمط بقية جداول العقل)."""
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class V2McpToken(db.Model):
        __tablename__ = 'v2_mcp_tokens'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.String(32), primary_key=True)
        name = db.Column(db.String(TOKEN_NAME_MAX), nullable=False)
        hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
        scopes = db.Column(db.String(20), nullable=False, default='read')
        created_by = db.Column(db.String(255))
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        last_used_at = db.Column(db.DateTime)
        revoked_at = db.Column(db.DateTime)

    _MODEL['cls'] = V2McpToken
    return V2McpToken


def hash_token(raw):
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def new_token():
    """⇒ (النص الصريح، hash). النص الصريح يُعرض مرة واحدة ولا يُخزَّن."""
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def can_propose(row):
    return 'propose' in (row.scopes or '').split(',')


# ------------------------------------------------------------------ المرشّح النهائي (لا بريد ولا هاتف ولا مبلغ)

_MONEY_RE = re.compile(
    r'(?:[$€£]\s*\d[\d.,٬٫]*|\d[\d.,٬٫]*\s*(?:[$€£]|ج\.?\s?م\b|جنيه\w*|دولار\w*|يورو|ريال\w*|درهم\w*|دينار\w*|EGP|USD|SAR|AED|EUR|GBP|KWD|QAR)'
    r'|(?:EGP|USD|SAR|AED|EUR|GBP)\s*\d[\d.,٬٫]*)', re.I)
_MONEY_WORD_RE = re.compile(r'جنيه|دولار|يورو|ريال|درهم|دينار|EGP|USD|SAR|AED|EUR|GBP|[$€£]', re.I)
_LONGDIGITS_RE = re.compile(r'\d{7,}')
_TEXT_MAX = 700


def scrub_text(s, limit=_TEXT_MAX):
    """نص يخرج من الخادم: بلا بريد ولا هاتف (٩ خانات فأكثر) ولا مبلغ ولا رقم طويل. ⛔ يُطبَّق على كل نص في كل أداة."""
    from brain2 import engine
    if not isinstance(s, str):
        return s
    s = engine.strip_contacts(engine.clean_text(s, keep_newlines=False))
    s = _MONEY_RE.sub('', s)
    s = _LONGDIGITS_RE.sub('', s).replace('@', '')
    return re.sub(r'\s{2,}', ' ', s).strip()[:limit]


def sanitize(o):
    """يمرّر كل نصوص المخرج على `scrub_text` (عدا مفاتيح `id`)."""
    if isinstance(o, dict):
        return {k: (v if k == 'id' else sanitize(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [sanitize(x) for x in o]
    if isinstance(o, str):
        return scrub_text(o)
    return o


# ------------------------------------------------------------------ أدوات القراءة

# منتجات عناوينها بلا بيانات أشخاص، ومنتجات نصوصها كذلك. غيرها ⇒ عنوان عام (اسم القاعدة) وبلا نص.
TITLE_SAFE = frozenset({'course_review', 'course_lesson_draft', 'seo_notes', 'weekly_read', 'campaign_comment', 'forecast_comment', 'links_digest'})
TEXT_SAFE = frozenset({'course_review', 'course_lesson_draft', 'seo_notes'})
SECTIONS_ENUM = ('home', 'courses', 'market', 'content', 'marketing', 'reports', 'company', 'people', 'books', 'files')
STATUS_ENUM = ('proposed', 'done_alone', 'approved', 'edited', 'rejected', 'all')
NA = 'غير متاح بعد'


def _now():
    return datetime.datetime.utcnow()


def _hours(dt, now):
    if not isinstance(dt, datetime.datetime):
        return None
    return max(0, int((now - dt).total_seconds() // 3600))


def _item_view(r, now, with_text):
    from brain2 import registry
    p = registry.by_id(r.producer)
    external = r.producer.startswith('mcp:')
    title = (r.target_label or '') if (r.producer in TITLE_SAFE or external) else ((p.label if p else '') or 'اقتراح')
    d = {'id': r.id, 'section': r.section or '', 'kind': r.kind or '', 'tag': ((p.tag or p.label) if p else ''), 'status': r.status,
         'title': scrub_text(title, 120), 'age_hours': _hours(r.created_at, now)}
    if with_text and (r.producer in TEXT_SAFE or external):
        try:
            body = json.loads(r.body_json) if r.body_json else {}
        except (TypeError, ValueError):
            body = {}
        t = body.get('text') if isinstance(body, dict) else None
        if isinstance(t, str):
            d['text'] = scrub_text(t, 600)
    return d


def tool_business_summary(ns, args):
    from sqlalchemy import func
    from brain2 import engine
    db = ns['db']
    Item = engine._models(db)[0]
    now = _now()
    waiting = {sec or 'other': n for sec, n in db.session.query(Item.section, func.count(Item.id)).filter(Item.status == 'proposed').group_by(Item.section).all()}
    wrote = Item.query.filter(Item.status == 'done_alone', Item.created_at >= now - datetime.timedelta(days=7)).count()
    out = {'brain': {'waiting_by_section': waiting, 'waiting_total': sum(waiting.values()), 'notes_last_7_days': wrote}}
    try:
        Article = ns['Article']
        out['content'] = {'published': Article.query.filter(Article.status == 'published').count(),
                          'drafts': Article.query.filter(Article.status == 'draft').count()}
    except Exception:   # noqa: BLE001
        db.session.rollback()
        out['content'] = NA
    out['courses'] = _courses_counts(ns)
    return out


def _platform_list(ns, path, key):
    """قراءة قائمة من المنصة بنداء واحد، أو None (لا نخلط الفشل بالفراغ)."""
    try:
        resp = ns['_platform_proxy']('GET', path, timeout=8)
        if not ns['_resp_ok'](resp):
            return None
        data = ns['_proxy_json'](resp)
    except Exception:   # noqa: BLE001
        return None
    rows = data.get(key) if isinstance(data, dict) else data
    return rows if isinstance(rows, list) else None


def _courses_counts(ns):
    rows = _platform_list(ns, '/api/bridge/courses', 'courses')
    if rows is None:
        return NA
    by = {}
    for c in rows:
        if isinstance(c, dict):
            k = str(c.get('approval_status') or 'unknown')[:20]
            by[k] = by.get(k, 0) + 1
    return {'total': sum(by.values()), 'by_approval': by}


def tool_decisions_waiting(ns, args):
    from brain2 import engine
    Item = engine._models(ns['db'])[0]
    now = _now()
    rows = Item.query.filter(Item.status == 'proposed').order_by(Item.created_at.desc(), Item.id.desc()).limit(30).all()
    items = []
    for r in rows:
        v = _item_view(r, now, with_text=False)
        items.append({'kind': v['tag'] or v['kind'], 'section': v['section'], 'title': v['title'], 'age_hours': v['age_hours']})
    return {'count': Item.query.filter(Item.status == 'proposed').count(), 'shown': len(items), 'items': items}


def tool_brain_items(ns, args):
    from brain2 import engine
    Item = engine._models(ns['db'])[0]
    now = _now()
    q = Item.query
    if args.get('section'):
        q = q.filter(Item.section == args['section'])
    status = args.get('status') or 'proposed'
    if status != 'all':
        q = q.filter(Item.status == status)
    limit = args.get('limit') or 20
    rows = q.order_by(Item.created_at.desc(), Item.id.desc()).limit(limit).all()
    return {'count': len(rows), 'items': [_item_view(r, now, with_text=True) for r in rows]}


def tool_reports_weekly(ns, args):
    import v2_reports_routes as R
    try:
        payload, err = R.weekly_for(ns, None)
    except Exception:   # noqa: BLE001
        payload, err = None, 'down'
    if err or not isinstance(payload, dict) or not isinstance(payload.get('week'), dict):
        return {'available': False, 'message': NA}
    lines = []
    for s in (payload.get('funnel') or {}).get('stages', []):
        if isinstance(s, dict) and s.get('label'):
            extra = ' · '.join(x for x in (s.get('change_text'), s.get('conv_text')) if x)
            lines.append('%s: %s%s' % (s['label'], NA if s.get('cur') is None else R._ar(s['cur']), (' (%s)' % extra) if extra else ''))
    for sec in payload.get('sections') or []:
        v = sec.get('value') if isinstance(sec, dict) else None
        if isinstance(v, dict) and v.get('kind') == 'count' and v.get('text'):
            lines.append('%s: %s' % (sec.get('label', ''), v['text']))
        elif isinstance(v, dict) and v.get('kind') == 'money' and isinstance(v.get('count'), int):
            lines.append('%s: عدد العمليات %s' % (sec.get('label', ''), R._ar(v['count'])))      # عدد فقط؛ ⛔ لا مبلغ
    for b in payload.get('brain') or []:
        t = (b.get('text') or '') if isinstance(b, dict) else ''
        if t and not _MONEY_WORD_RE.search(t) and not _MONEY_RE.search(t):
            lines.append('%s: %s' % (b.get('label', ''), t))
    lines = [scrub_text(x, 200) for x in lines]
    return {'available': True, 'week': scrub_text(str(payload['week'].get('label') or ''), 80),
            'start': str(payload['week'].get('start') or ''), 'end': str(payload['week'].get('end') or ''), 'lines': [x for x in lines if x]}


def tool_content_published(ns, args):
    Article = ns['Article']
    days = args.get('days') or 7
    limit = args.get('limit') or 20
    since = _now() - datetime.timedelta(days=days)
    rows = (Article.query.filter(Article.status == 'published', Article.published_at != None, Article.published_at >= since)   # noqa: E711
            .order_by(Article.published_at.desc()).limit(limit).all())
    items = []
    for a in rows:
        try:
            url = ns['_blog_url'](a)
        except Exception:   # noqa: BLE001
            url = ''
        items.append({'title': scrub_text(a.title or '', 200), 'url': url if isinstance(url, str) and url.startswith('https://') else '',
                      'published_at': a.published_at.replace(microsecond=0).isoformat() + 'Z'})
    return {'days': days, 'count': len(items), 'items': items}


def tool_courses_catalog(ns, args):
    rows = _platform_list(ns, '/api/bridge/courses', 'courses')
    if rows is None:
        return {'available': False, 'message': NA}
    out = []
    for c in rows:
        if not isinstance(c, dict) or c.get('approval_status') != 'approved' or not c.get('is_active') or c.get('archived_at'):
            continue
        out.append({'title': scrub_text(str(c.get('title') or ''), 160), 'slug': str(c.get('slug') or '')[:120], 'type': str(c.get('type') or '')[:30],
                    'level': scrub_text(str(c.get('level') or ''), 40), 'lessons': c.get('lesson_count') if isinstance(c.get('lesson_count'), int) else None,
                    'summary': scrub_text(str(c.get('short_description') or ''), 300)})       # ⛔ لا سعر ولا مدرّب ولا عدد مسجّلين
    return {'available': True, 'count': len(out), 'items': out[:100]}


# ------------------------------------------------------------------ أدوات الاقتراح

PROPOSE_NOTES = {
    'section': 'قسم غير معروف', 'bad': 'اكتب عنوانًا ونصًّا', 'long': 'العنوان أطول من ١٢٠ حرفًا أو النص أطول من ٦٠٠ حرف',
    'banned': 'في النص عبارة غير مقبولة', 'full': 'تراكمت اقتراحات كثيرة تنتظر المؤسس؛ جرّب لاحقًا',
    'exists': 'هذا الاقتراح وصل من قبل',
}
PROPOSED_AR = 'وصل الاقتراح إلى المؤسس ليقرره. لم يُنفَّذ شيء.'


def _propose(ns, token, section, title, text):
    from brain2 import engine
    row, reason = engine.store_external_note(ns, 'mcp:' + token.name, section, title, text, 'mcp:' + token.name)
    if row is None:
        return {'ok': False, 'reason': reason, 'message': PROPOSE_NOTES.get(reason, PROPOSE_NOTES['bad'])}, True
    return {'ok': True, 'id': row.id, 'status': 'proposed', 'message': PROPOSED_AR}, False


def tool_propose_note(ns, args, token):
    return _propose(ns, token, args['section'], args['title'], args['text'])


def tool_propose_campaign_idea(ns, args, token):
    return _propose(ns, token, 'marketing', args['title'], args['text'])


def _str(desc, lo=1, hi=None, enum=None):
    d = {'type': 'string', 'description': desc, 'minLength': lo}
    if hi:
        d['maxLength'] = hi
    if enum:
        d['enum'] = list(enum)
    return d


def _obj(props, required=()):
    return {'type': 'object', 'properties': props, 'required': list(required), 'additionalProperties': False}


TOOLS = {
    'business_summary': {'scope': 'read', 'fn': tool_business_summary,
                         'description': 'أعداد فقط: اقتراحات العقل المنتظرة لكل قسم، والمقالات المنشورة والمسودات، وحالة الدورات. بلا بيانات عملاء.',
                         'schema': _obj({})},
    'decisions_waiting': {'scope': 'read', 'fn': tool_decisions_waiting,
                          'description': 'اقتراحات تنتظر قرار المؤسس: النوع والعنوان والعمر بالساعات. بلا أسماء ولا بريد ولا مبالغ.',
                          'schema': _obj({})},
    'brain_items': {'scope': 'read', 'fn': tool_brain_items,
                    'description': 'اقتراحات العقل وملاحظاته مع الحالة والقسم. النص يظهر لما لا يحمل بيانات أشخاص فقط.',
                    'schema': _obj({'section': _str('قسم اللوحة', enum=SECTIONS_ENUM),
                                    'status': _str('الحالة (الافتراضي proposed)', enum=STATUS_ENUM),
                                    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'description': 'عدد الصفوف (الافتراضي ٢٠)'}})},
    'reports_weekly': {'scope': 'read', 'fn': tool_reports_weekly,
                       'description': 'أرقام الأسبوع الماضي بسطور قصيرة: الأعداد وتغيّرها، بلا مبالغ مالية.', 'schema': _obj({})},
    'content_published': {'scope': 'read', 'fn': tool_content_published,
                          'description': 'عناوين المقالات المنشورة وروابطها وتاريخ نشرها.',
                          'schema': _obj({'days': {'type': 'integer', 'minimum': 1, 'maximum': 31, 'description': 'آخر كم يومًا (الافتراضي ٧)'},
                                          'limit': {'type': 'integer', 'minimum': 1, 'maximum': 50, 'description': 'الحد الأقصى (الافتراضي ٢٠)'}})},
    'courses_catalog': {'scope': 'read', 'fn': tool_courses_catalog,
                        'description': 'الدورات المنشورة للعامة: العنوان والمستوى وعدد الدروس وملخص. بلا أسعار.', 'schema': _obj({})},
    'propose_note': {'scope': 'propose', 'fn': tool_propose_note, 'needs_token': True,
                     'description': 'اقتراح ملاحظة تظهر للمؤسس في شاشة العقل ليقرر فيها. لا يُنفَّذ شيء.',
                     'schema': _obj({'section': _str('القسم', enum=('home', 'courses', 'market', 'content', 'marketing', 'reports', 'company', 'people', 'books')),
                                     'title': _str('عنوان قصير', hi=120), 'text': _str('نص الملاحظة', hi=600)}, ('section', 'title', 'text'))},
    'propose_campaign_idea': {'scope': 'propose', 'fn': tool_propose_campaign_idea, 'needs_token': True,
                              'description': 'اقتراح فكرة حملة تظهر للمؤسس في قسم التسويق ليقرر فيها. لا يُنفَّذ شيء.',
                              'schema': _obj({'title': _str('عنوان قصير', hi=120), 'text': _str('وصف الفكرة', hi=600)}, ('title', 'text'))},
}


def tools_for(token):
    out = []
    for name, t in TOOLS.items():
        if t['scope'] == 'propose' and not can_propose(token):
            continue
        out.append({'name': name, 'description': t['description'], 'inputSchema': t['schema']})
    return out


def validate_args(schema, args):
    """تحقق صغير من الوسائط حسب المخطط. يرجع نص الخطأ أو None."""
    if not isinstance(args, dict):
        return 'الوسائط يجب أن تكون كائنًا'
    props = schema.get('properties', {})
    for k in args:
        if k not in props:
            return 'وسيط غير معروف: ' + str(k)[:40]
    for k in schema.get('required', []):
        if k not in args:
            return 'وسيط ناقص: ' + k
    for k, v in args.items():
        p = props[k]
        if p.get('type') == 'integer':
            if isinstance(v, bool) or not isinstance(v, int) or v < p.get('minimum', v) or v > p.get('maximum', v):
                return 'قيمة غير صالحة: ' + k
        else:
            if not isinstance(v, str) or len(v.strip()) < p.get('minLength', 0) or len(v) > p.get('maxLength', 10 ** 6):
                return 'قيمة غير صالحة: ' + k
            if p.get('enum') and v not in p['enum']:
                return 'قيمة غير صالحة: ' + k
    return None


# ------------------------------------------------------------------ التسجيل

def register(app, ns):
    db = ns['db']
    Token = _models(db)

    def out(payload, status=200, headers=None):
        resp = jsonify(payload)
        for k, v in (headers or {}).items():
            resp.headers[k] = v
        return ns['_v2_ns']((resp, status) if status != 200 else resp)

    def rpc_ok(rid, result):
        return out({'jsonrpc': '2.0', 'id': rid, 'result': result})

    def rpc_err(rid, code, message, status=200, headers=None):
        return out({'jsonrpc': '2.0', 'id': rid, 'error': {'code': code, 'message': message}}, status, headers)

    def authenticate():
        h = request.headers.get('Authorization', '')
        if not h[:7].lower() == 'bearer ':
            return None
        raw = h[7:].strip()
        if not raw or len(raw) > 200:
            return None
        row = Token.query.filter_by(hash=hash_token(raw)).first()
        if row is None or row.revoked_at is not None or not hmac.compare_digest(row.hash, hash_token(raw)):
            return None
        return row

    def touch(row):
        now = _now()
        if row.last_used_at is None or (now - row.last_used_at).total_seconds() >= LAST_USED_EVERY:
            try:
                row.last_used_at = now
                db.session.commit()
            except Exception:   # noqa: BLE001
                db.session.rollback()

    def rate_ok(token_id):
        now = _clock()
        with _HITS_LOCK:
            dq = _HITS.setdefault(token_id, deque())
            while dq and dq[0] <= now - RATE_WINDOW:
                dq.popleft()
            if len(dq) >= RATE_PER_HOUR:
                return False
            dq.append(now)
            return True

    def audit(token, tool, ok, reason=''):
        meta = {'tool': tool, 'token': token.name, 'ok': ok}
        if reason:
            meta['reason'] = reason
        ns['_audit']('mcp.call', target=tool, meta=meta, actor='mcp:' + token.name)

    def call_tool(token, rid, params):
        name = params.get('name') if isinstance(params, dict) else None
        if not isinstance(name, str) or name not in TOOLS:
            return rpc_err(rid, E_PARAMS, 'أداة غير معروفة')
        tool = TOOLS[name]
        if tool['scope'] == 'propose' and not can_propose(token):
            audit(token, name, False, 'scope')
            return rpc_err(rid, E_SCOPE, ERR_SCOPE)
        args = params.get('arguments') if params.get('arguments') is not None else {}
        bad = validate_args(tool['schema'], args)
        if bad:
            return rpc_err(rid, E_PARAMS, bad)
        if not rate_ok(token.id):
            audit(token, name, False, 'rate')
            return rpc_err(rid, E_RATE, ERR_RATE, 429, {'Retry-After': '600'})
        is_error = False
        try:
            if tool.get('needs_token'):
                result, is_error = tool['fn'](ns, args, token)
            else:
                result = tool['fn'](ns, args)
        except Exception:   # noqa: BLE001
            logger.exception('mcp tool failed: %s', name)
            try:
                db.session.rollback()
            except Exception:   # noqa: BLE001
                pass
            audit(token, name, False, 'error')
            return rpc_err(rid, E_INTERNAL, 'تعذّر تنفيذ الأداة الآن')
        result = sanitize(result)
        audit(token, name, not is_error)
        return rpc_ok(rid, {'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}],
                            'structuredContent': result, 'isError': bool(is_error)})

    @app.route('/api/mcp', methods=['GET', 'POST'], endpoint='v2_mcp_endpoint')
    def v2_mcp_endpoint():
        closed = ns['_v2_closed']()
        if closed:
            return closed
        if request.method != 'POST':
            return out({'error': 'استعمل POST'}, 405, {'Allow': 'POST'})
        token = authenticate()
        if token is None:
            return rpc_err(None, E_AUTH, ERR_AUTH, 401, {'WWW-Authenticate': 'Bearer realm="elprofessor-dashboard"'})
        if (request.content_length or 0) > BODY_MAX:
            return rpc_err(None, E_REQUEST, 'الطلب كبير', 413)
        raw = request.get_data(cache=False)
        if len(raw) > BODY_MAX:
            return rpc_err(None, E_REQUEST, 'الطلب كبير', 413)
        try:
            msg = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            return rpc_err(None, E_PARSE, 'JSON غير صالح', 400)
        if isinstance(msg, list):
            return rpc_err(None, E_REQUEST, 'الدفعات غير مدعومة', 400)
        if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0' or not isinstance(msg.get('method'), str):
            return rpc_err(None, E_REQUEST, 'طلب غير صالح', 400)
        rid = msg.get('id')
        if 'id' in msg and (isinstance(rid, bool) or not isinstance(rid, (int, str))):
            return rpc_err(None, E_REQUEST, 'معرّف غير صالح', 400)
        method, params = msg['method'], msg.get('params')
        if 'id' not in msg:                                   # إشعار: لا ردّ، ٢٠٢
            touch(token)
            return ns['_v2_ns'](make_response('', 202))
        if params is not None and not isinstance(params, dict):
            return rpc_err(rid, E_PARAMS, 'الوسائط يجب أن تكون كائنًا')
        touch(token)
        if method == 'initialize':
            return rpc_ok(rid, {'protocolVersion': PROTOCOL, 'capabilities': {'tools': {'listChanged': False}},
                                'serverInfo': SERVER_INFO, 'instructions': INSTRUCTIONS})
        if method == 'ping':
            return rpc_ok(rid, {})
        if method == 'tools/list':
            return rpc_ok(rid, {'tools': tools_for(token)})
        if method == 'tools/call':
            return call_tool(token, rid, params or {})
        return rpc_err(rid, E_METHOD, 'طريقة غير معروفة')
