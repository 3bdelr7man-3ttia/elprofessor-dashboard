# -*- coding: utf-8 -*-
"""«اسألني على تليجرام» — إرسال اقتراح العقل إلى مجموعة المؤسس وقراءة قراره (SPEC-B §B2).

الاتجاه الأول (هنا): اقتراح جديد بحالة `proposed` ⇒ نداء واحد إلى جسر المنصة `POST /api/bridge/brain/ask`.
الاتجاه الثاني (المنصة): ضغطة زر ⇒ المنصة تنادي مسار الداشبورد `POST /api/v2/brain/telegram-decide` بالسرّ المشترك.

قواعد ثابتة:
  * ⛔ لا رأي (kind=opinion) يُرسل إلى تليجرام أبدًا.
  * ⛔ منتج خارج `registry.TELEGRAM_OK` (فلوس، أو مقفول بقرار) يصله زر «افتح في اللوحة» فقط ولا يعتمده تليجرام.
  * ⛔ نداء واحد لكل اقتراح، بلا إعادة محاولة، وسقف يومي `DASH_BRAIN_TG_CAP` (الافتراضي ٢٠). السقف والتكرار من سجل التدقيق.
  * ⛔ ما يُرسل: عنوان ونص الاقتراح ومقتطف قصير من الرسالة الأصلية (مُنقّاة من الحقائق). لا بريد ولا هاتف ولا `meta`.
  * ⛔ لا ندّعي تنفيذًا لم يحدث: السطر الراجع للمنصة يأتي من نتيجة التنفيذ الفعلية.
"""
import datetime
import json
import logging
import os
import re

from brain2 import engine, registry

logger = logging.getLogger(__name__)

ASK_PATH = '/api/bridge/brain/ask'
OPEN_URL = 'https://dashboard.elprofessor.net/'
AUDIT_ASK = 'brain.tg_ask'
TITLE_MAX, TEXT_MAX, LABEL_MAX = 120, 900, 24
BTN_REJECT = 'ارفض'
BTN_OPEN = 'افتح في اللوحة'
BTN_APPROVE_DEFAULT = 'اعتمد'
SNIPPET_MAX = 260


def tg_cap():
    try:
        return max(0, int((os.environ.get('DASH_BRAIN_TG_CAP') or '').strip() or 20))
    except (TypeError, ValueError):
        return 20


# ------------------------------------------------------------------ الإعداد لكل منتج

def default_on(p):
    return p.id in registry.TELEGRAM_DEFAULT_ON and p.kind != 'opinion'


def enabled(ns, p):
    """هل «اسألني على تليجرام» مفعّل لهذا المنتج؟ الصف يحسم، وإلا الافتراضي. الرأي ⇒ لا دائمًا."""
    if p is None or p.kind == 'opinion':
        return False
    row = engine.get_switch(ns['db'], p.id)
    v = getattr(row, 'telegram', None) if row is not None else None
    return bool(v) if isinstance(v, bool) else default_on(p)


def toggle_allowed(p):
    return p is not None and p.kind != 'opinion'


def decide_allowed_producer(p):
    return p is not None and p.kind != 'opinion' and p.id in registry.TELEGRAM_OK


# ------------------------------------------------------------------ ما يجوز قراره من تليجرام

def _src(ref):
    return str(ref or '').split(':', 1)[0]


def can_decide(p, body, meta, facts, ref):
    """هل يحمل هذا الاقتراح زري اعتمد/ارفض؟ لا ⇒ رابط «افتح في اللوحة» فقط."""
    if not decide_allowed_producer(p):
        return False
    body = body if isinstance(body, dict) else {}
    meta = meta if isinstance(meta, dict) else {}
    facts = facts if isinstance(facts, dict) else {}
    if p.id == 'reply_draft':
        # الاعتماد من تليجرام يجب أن يرسل فعلًا: رد داخل المنصة لعضو بحساب، أو بريد لمن له بريد. غير ذلك رد يُنسخ من اللوحة.
        src = _src(ref)
        if src == 'pmsg' and facts.get('has_account'):
            return True
        return bool(str(meta.get('email') or '').strip()) and src in ('pmsg', 'smsg', 'lead')
    if p.id == 'course_review':
        return body.get('recommend') == 'publish'      # «أصلح أولًا» لا يُنفَّذ منه شيء، فلا زر اعتماد
    return True


# ------------------------------------------------------------------ بناء الرسالة

def _clip(s, n):
    s = engine.clean_text(s, keep_newlines=True) if isinstance(s, str) else ''
    return s if len(s) <= n else s[:n - 1].rstrip() + '…'


_SRC_LABEL = {'pmsg': 'رسالة من المنصة', 'smsg': 'رسالة من الموقع', 'lead': 'عميل محتمل', 'file': 'ملف', 'course': 'دورة'}
_NAME_KEY_RE = re.compile(r'name|customer|client|author|sender', re.I)


def _name_tokens(row, meta, facts):
    """كل ما قد يكون اسمًا في الاقتراح (العنوان واسم العميل...) لنمسحه من نص تليجرام. لا نمسح كلمات قصيرة جدًا."""
    vals = [getattr(row, 'target_label', '') or '']
    for src in (meta, facts):
        if isinstance(src, dict):
            for k, v in src.items():
                if isinstance(v, str) and _NAME_KEY_RE.search(str(k)):
                    vals.append(v)
    toks = set()
    for v in vals:
        v = engine.clean_text(v, keep_newlines=False)
        if len(v) >= 3:
            toks.add(v)
        for w in re.split(r'[\s:،,؛;/|—\-]+', v):
            if len(w) >= 4:
                toks.add(w)
    return sorted(toks, key=len, reverse=True)


def _scrub(s, names):
    """يمسح البريد والهاتف وأسماء العميل من نص يخرج إلى تليجرام."""
    s = engine.strip_contacts(s) if isinstance(s, str) else ''
    for n in names:
        s = s.replace(n, '…')
    return s


def build_ask(p, row, body, meta, facts):
    """(payload|None). `row`: صف الاقتراح. ⛔ لا يخرج بريد ولا هاتف ولا اسم عميل ولا meta؛ والعنوان وسم المنتج + نوع المصدر فقط."""
    src = _SRC_LABEL.get(_src(row.target_ref), '')
    title = _clip(' — '.join(x for x in ((p.tag or p.label), src) if x), TITLE_MAX)
    names = _name_tokens(row, meta, facts)
    parts = []
    orig = facts.get('body') if isinstance(facts, dict) else None
    if isinstance(orig, str) and orig.strip():
        parts.append('الرسالة: ' + _clip(_scrub(orig, names), SNIPPET_MAX))
    text = body.get('text') if isinstance(body, dict) else ''
    parts.append(('المقترح: ' if parts else '') + _clip(_scrub(text, names), 500))
    note = body.get('return_note') if isinstance(body, dict) else ''
    if isinstance(note, str) and note.strip() and body.get('recommend') == 'return':
        parts.append('الملاحظة التي تصل إلى الخبير: ' + _clip(_scrub(note, names), 300))
    out_text = _clip('\n\n'.join(x for x in parts if x), TEXT_MAX)
    if not out_text:
        return None
    buttons = []
    if can_decide(p, body, meta, facts, row.target_ref):
        label = (body.get('approve_label') if isinstance(body, dict) else '') or p.approve_label or BTN_APPROVE_DEFAULT
        buttons.append({'label': str(label).strip()[:LABEL_MAX] or BTN_APPROVE_DEFAULT, 'action': 'approve'})
        buttons.append({'label': BTN_REJECT, 'action': 'reject'})
    buttons.append({'label': BTN_OPEN, 'action': 'open'})
    return {'item_id': row.id, 'title': title, 'text': out_text, 'buttons': buttons, 'open_url': OPEN_URL}


# ------------------------------------------------------------------ الإرسال

def _day_start():
    n = engine.utcnow()
    return datetime.datetime(n.year, n.month, n.day)


def _audit_model(ns):
    return ns.get('AuditLog')


def asks_today(ns):
    A = _audit_model(ns)
    if A is None:
        return 0
    return A.query.filter(A.action == AUDIT_ASK, A.created_at >= _day_start()).count()


def already_asked(ns, item_id):
    A = _audit_model(ns)
    return A is not None and A.query.filter(A.action == AUDIT_ASK, A.target == item_id).count() > 0


def was_sent(ns, item_id):
    """هل أُرسل هذا الاقتراح فعلًا إلى تليجرام (صف تدقيق `brain.tg_ask` بـ`sent:true`)؟"""
    A = _audit_model(ns)
    if A is None:
        return False
    for r in A.query.filter(A.action == AUDIT_ASK, A.target == item_id).all():
        try:
            if (json.loads(r.meta_json or '{}') or {}).get('sent') is True:
                return True
        except (TypeError, ValueError, AttributeError):
            continue
    return False


def admin_ids():
    """`DASH_TG_ADMIN_IDS` (قائمة بفواصل): إن ضُبطت صار معرّف تليجرام لازمًا فيها. فارغة ⇒ None (لا تقييد)."""
    raw = (os.environ.get('DASH_TG_ADMIN_IDS') or '').strip()
    ids = {x.strip() for x in raw.split(',') if x.strip()}
    return ids or None


def _record(ns, item_id, sent, why=''):
    try:
        ns['_audit'](AUDIT_ASK, target=item_id, meta={'sent': bool(sent), 'why': why}, actor='brain')
    except Exception:   # noqa: BLE001
        logger.exception('brain2: telegram audit failed')


def send_ask(ns, item_id):
    """يرجع 'sent' | 'skip:<سبب>' | 'failed'. نداء واحد، بلا إعادة محاولة."""
    db = ns['db']
    Item = engine._models(db)[0]
    row = Item.query.get(item_id)
    if row is None or row.status != 'proposed':
        return 'skip:not_proposed'
    p = registry.by_id(row.producer)
    if p is None or p.kind == 'opinion':
        return 'skip:kind'
    if not enabled(ns, p):
        return 'skip:off'
    if already_asked(ns, item_id):
        return 'skip:duplicate'
    if asks_today(ns) >= tg_cap():
        return 'skip:cap'
    proxy = ns.get('_platform_proxy')
    if not callable(proxy):
        return 'skip:no_proxy'
    body, meta, facts = (engine._loads(row.body_json, {}), engine._loads(row.meta_json, {}),
                         engine._loads(row.facts_json, {}))
    payload = build_ask(p, row, body, meta, facts)
    if payload is None:
        return 'skip:empty'
    sent = False
    try:
        resp = proxy('POST', ASK_PATH, json_body=payload, timeout=10)
        if ns['_resp_ok'](resp):
            js = ns['_proxy_json'](resp)
            sent = js.get('sent') is True
    except Exception:   # noqa: BLE001
        logger.exception('brain2: telegram ask raised')
    _record(ns, item_id, sent)
    return 'sent' if sent else 'failed'


def send_asks(ns, ids):
    for item_id in ids or []:
        try:
            send_ask(ns, item_id)
        except Exception:   # noqa: BLE001
            logger.exception('brain2: telegram ask failed for %s', item_id)
            try:
                ns['db'].session.rollback()
            except Exception:   # noqa: BLE001
                pass


# ------------------------------------------------------------------ سطر النتيجة للمنصة

def result_line(p, info):
    """سطر قصير يعرضه تليجرام بعد الاعتماد، من نتيجة التنفيذ الفعلية فقط."""
    info = info if isinstance(info, dict) else {}
    if isinstance(info.get('line'), str) and info['line'].strip():
        return info['line'].strip()[:200]
    return 'تم التنفيذ'
