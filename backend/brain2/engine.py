# -*- coding: utf-8 -*-
"""«العقل» الجولة ٢ — المحرّك (SPEC docs/v2/brain2/SPEC.md §2.3–§2.6).

المنتِج (`Producer`) يحوّل بيانات حقيقية إلى كتابة واحدة: رأي على بطاقة قرار، أو مسودة تذهب لعميل/للعامة، أو ملاحظة داخلية.
المحرّك هنا: الجداول · البصمة · الأوضاع · السقوف · فحوص الصدق · الخيط الخلفي الوحيد · تنفيذ الاعتماد.

قواعد ثابتة:
  * ⛔ كل نداء ذكاء يمرّ من `ns['ai_call']` وحدها، تُقرأ وقت النداء لا وقت الاستيراد (التسجيل في app.py أبكر من تعريفها).
  * ⛔ لا إعادة محاولة. `AIUnavailable` بسبب `cap` أو `no_key` توقف الجولة؛ أي فشل آخر ⇒ صف قالب أو صف فاشل.
  * ⛔ منتج لا يعمل «وحده» لا يُخزَّن بحالة `done_alone` أبدًا، حتى لو كان صف مفتاحه في القاعدة `alone`.
  * ⛔ `meta` لا يصل للذكاء ولا للمتصفح ولا يدخل البصمة.
  * ⛔ التنفيذ الفعلي (`producer.apply`) لا يُستدعى إلا من اعتماد المؤسس.
"""
import datetime
import hashlib
import json
import sys
import logging
import os
import queue
import re
import threading
import uuid

from brain2 import registry
from brain2.contract import Ctx, Target, MODES

logger = logging.getLogger(__name__)

SYSTEM_AR = ('اكتب بالعربية الفصحى البسيطة، بصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا، لجمهور دولي، بلا مصطلحات تقنية. '
             'استعمل الحقائق المعطاة وحدها؛ لا تخترع رقمًا ولا اسمًا ولا تاريخًا ولا وعدًا، ولا تقل إن شيئًا نُفِّذ. '
             'أعد JSON صالحًا فقط بالشكل المطلوب.')

STATUSES = ('proposed', 'done_alone', 'applying', 'approved', 'edited', 'rejected',
            'discarded', 'expired', 'failed', 'unknown')

TEXT_LIMIT = {'opinion': 220, 'draft': 900, 'note': 600}
WHY_LIMIT = 160
EDIT_MIN, EDIT_MAX = 1, 900
FACTS_MAX_BYTES = 4096          # facts المنتِج
OPINION_FACTS_MAX_BYTES = 3072  # facts البطاقة القادمة من المتصفح
RESERVE_MIN = 25
RUN_LOCK_MINUTES = 15
QUEUE_SIZE = 8
OPINION_FACT_STR_MAX = 300
OPINION_FACT_LIST_MAX = 6

ERR_DECIDED = 'حُسم هذا الاقتراح من قبل'
ERR_RUNNING = 'العقل يكتب الآن. جرّب بعد قليل'
ERR_WRITE_OFF = 'كتابة العقل متوقّفة الآن'
ERR_NO_REPLY = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى'
ERR_APPLY_FAILED = 'تعذّر التنفيذ الآن. حاول بعد قليل'
ERR_WRITE_FAILED = 'تعذّرت الكتابة الآن'
ERR_INVALID_OUTPUT = 'جاء المكتوب غير صالح فلم يُحفظ'

# ------------------------------------------------------------------ بيئة

def _int_env(name, default):
    try:
        return max(0, int((os.environ.get(name) or '').strip() or default))
    except (TypeError, ValueError):
        return default


def run_cap():
    return _int_env('DASH_BRAIN_RUN_CAP', 20)


def day_cap():
    return _int_env('DASH_BRAIN_DAY_CAP', 60)


def opinion_cap():
    return _int_env('DASH_BRAIN_OPINION_CAP', 40)


def writes_enabled():
    """`DASH_BRAIN_WRITE=0` يوقف كل كتابة للعقل (مفتاح الطوارئ)، ويُقرأ وقت الطلب."""
    return (os.environ.get('DASH_BRAIN_WRITE') or '').strip() != '0'


def utcnow():
    return datetime.datetime.utcnow()


def _aware(dt=None):
    return (dt or utcnow()).replace(tzinfo=datetime.timezone.utc)


# ------------------------------------------------------------------ الجداول

_MODEL = {}


def _models(db):
    """(Item, Switch, Run) — تُعرَّف مرة واحدة (نفس نمط `v2_brain_routes._model`)."""
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class V2BrainItem(db.Model):
        __tablename__ = 'v2_brain_items'
        __table_args__ = (db.UniqueConstraint('producer', 'target_ref', 'input_hash', name='uq_v2_brain_item_key'),
                          {'extend_existing': True})
        id = db.Column(db.String(32), primary_key=True)
        producer = db.Column(db.String(40), nullable=False, index=True)
        section = db.Column(db.String(20))
        kind = db.Column(db.String(10))
        target_ref = db.Column(db.String(200), nullable=False)
        target_label = db.Column(db.String(200))
        input_hash = db.Column(db.String(64), nullable=False, index=True)
        facts_json = db.Column(db.Text)
        meta_json = db.Column(db.Text)
        body_json = db.Column(db.Text)
        status = db.Column(db.String(12), nullable=False, index=True)
        source = db.Column(db.String(10))
        mode = db.Column(db.String(8))
        run_id = db.Column(db.String(32))
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        decided_at = db.Column(db.DateTime)
        decided_by = db.Column(db.String(255))
        last_error = db.Column(db.String(300))
        applied_json = db.Column(db.Text)

    class V2BrainSwitch(db.Model):
        __tablename__ = 'v2_brain_switches'
        __table_args__ = {'extend_existing': True}
        producer = db.Column(db.String(40), primary_key=True)
        mode = db.Column(db.String(8), nullable=False)
        updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
        updated_by = db.Column(db.String(255))
        telegram = db.Column(db.Boolean)    # «اسألني على تليجرام» (SPEC-B §B2): None ⇒ الافتراضي حسب المنتج

    class V2BrainRun(db.Model):
        __tablename__ = 'v2_brain_runs'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.String(32), primary_key=True)
        trigger = db.Column(db.String(8))
        started_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
        finished_at = db.Column(db.DateTime)
        ai_calls = db.Column(db.Integer, default=0)
        items = db.Column(db.Integer, default=0)
        skipped_json = db.Column(db.Text)
        by = db.Column(db.String(255))

    _MODEL['cls'] = (V2BrainItem, V2BrainSwitch, V2BrainRun)
    return _MODEL['cls']


# ------------------------------------------------------------------ البصمة والنصوص

def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def input_hash(p, facts):
    payload = json.dumps({'p': p.id, 'v': p.version, 'f': facts}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


_DIGIT_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def norm_digits(s):
    return s.translate(_DIGIT_MAP) if isinstance(s, str) else s


_CTRL_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]')
_EMAIL_RE = re.compile(r'[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+')
_PHONE_RE = re.compile(r'(?<![\w])\+?\d[\d \-().]{6,}\d')
_LATIN_RE = re.compile(r'[A-Za-z]+')
_DIGITS_RE = re.compile(r'\d+')
# «يقوّم» بأي ترتيب للشدّة والحركة: الشدّة بين الواو والميم.
_BANNED_RE = re.compile('ي[\u064b-\u0652]*ق[\u064b-\u0652]*و[\u064b-\u0652]*\u0651[\u064b-\u0652]*م')
_AI_START_RE = re.compile(r'^[\s«"\'(\[\-*]*(?:الذكاء|AI\b)')


def clean_text(s, keep_newlines=True):
    """يمسح محارف التحكم ويجمع الفراغات. السطور تبقى (المسودات تحتاجها) بحدّ أقصى سطر فاضي واحد."""
    if not isinstance(s, str):
        return ''
    s = _CTRL_RE.sub('', s.replace('\r\n', '\n').replace('\r', '\n'))
    if keep_newlines:
        s = re.sub(r'[ \t ]+', ' ', s)
        s = re.sub(r' ?\n ?', '\n', s)
        s = re.sub(r'\n{3,}', '\n\n', s)
    else:
        s = re.sub(r'\s+', ' ', s)
    return s.strip()


def has_banned(s):
    return bool(isinstance(s, str) and _BANNED_RE.search(s))


def strip_contacts(s):
    """يمسح الإيميلات والأرقام الشبيهة بالهاتف (٩ خانات فأكثر) من نصّ، ويوحّد الأرقام إلى اللاتينية."""
    s = _EMAIL_RE.sub('', norm_digits(s))

    def _ph(m):
        return '' if len(re.sub(r'\D', '', m.group(0))) >= 9 else m.group(0)
    return re.sub(r'\s{2,}', ' ', _PHONE_RE.sub(_ph, s)).strip()


def _flatten_values(o, out):
    if isinstance(o, dict):
        for v in o.values():
            _flatten_values(v, out)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _flatten_values(v, out)
    elif o is not None and not isinstance(o, bool):
        out.append(str(o))
    return out


def _body_strings(body):
    out = []
    for k in ('text', 'why'):
        if isinstance(body.get(k), str):
            out.append(body[k])
    fields = body.get('fields')
    if isinstance(fields, dict):
        out.extend(v for v in fields.values() if isinstance(v, str))
    return out


def check_body(body, facts, kind):
    """فحوص الصدق (SPEC §2.4 «Parse»). يرجع None لو سليم، وإلا رمز العلّة."""
    if not isinstance(body, dict):
        return 'shape'
    text = body.get('text')
    if not isinstance(text, str) or not text.strip():
        return 'empty'
    limit = TEXT_LIMIT.get(kind, 600)
    if len(text) > limit:
        return 'long'
    if 'why' in body and body['why'] is not None:
        if not isinstance(body['why'], str) or len(body['why']) > WHY_LIMIT:
            return 'why'
    fields = body.get('fields')
    if fields is not None:
        if not isinstance(fields, dict) or any(not isinstance(v, str) or len(v) > EDIT_MAX for v in fields.values()):
            return 'fields'
    strings = _body_strings(body)
    facts_json = norm_digits(canon(facts))
    facts_lower = facts_json.lower()
    values_lower = norm_digits(' '.join(_flatten_values(facts, []))).lower()
    for s in strings:
        n = norm_digits(s)
        if has_banned(s):
            return 'banned'
        for run in _DIGITS_RE.findall(n):
            if run not in facts_json:
                return 'number'
        for w in _LATIN_RE.findall(n):
            if w.lower() not in values_lower:
                return 'latin'
        for m in _EMAIL_RE.findall(n):
            if m.lower() not in facts_lower:
                return 'email'
        digits_only_facts = re.sub(r'[ \-().]', '', facts_json)
        for m in _PHONE_RE.findall(n):
            if len(re.sub(r'\D', '', m)) >= 9:
                if m not in facts_json and re.sub(r'[ \-().]', '', m) not in digits_only_facts:
                    return 'phone'
    if _AI_START_RE.match(text):
        return 'lead'
    return None


# ------------------------------------------------------------------ الأوضاع

_SCHEMA = {'ok': False}


def ensure_schema(db):
    """عمود `telegram` على `v2_brain_switches` لقاعدة قائمة قبله (create_all لا يضيف أعمدة). مرة واحدة لكل عملية؛ أي فشل يُسجَّل
    ولا يكسر شيئًا (الاستعلام نفسه يفشل حينها ويُلتقط عند مستدعيه كما قبل)."""
    if _SCHEMA['ok']:
        return
    try:
        from sqlalchemy import inspect as _inspect, text as _text
        insp = _inspect(db.engine)
        if 'v2_brain_switches' in insp.get_table_names():
            if 'telegram' not in {c['name'] for c in insp.get_columns('v2_brain_switches')}:
                with db.engine.begin() as conn:
                    conn.execute(_text('ALTER TABLE v2_brain_switches ADD COLUMN telegram BOOLEAN'))
        _SCHEMA['ok'] = True
    except Exception:   # noqa: BLE001
        logger.exception('brain2: ensure_schema failed')


def get_switch(db, producer_id):
    ensure_schema(db)
    return _models(db)[1].query.get(producer_id)


def effective_mode(ns, p):
    """الصف يحسم، وإلا `default_mode`. و«وحده» على منتج مقفول ⇒ «يسألني» دائمًا (يُعاد الفحص عند التخزين)."""
    row = get_switch(ns['db'], p.id)
    mode = row.mode if row is not None and row.mode in MODES else p.default_mode
    if mode not in MODES:
        mode = 'ask'
    if mode == 'alone' and not p.may_run_alone:
        mode = 'ask'
    return mode


def writer_state(ns):
    """{'writer': 'main'|'backup'|None, 'label': اسم مفتاح القاعدة|None}. مفتاح القاعدة يعلو؛ وبدونه السلوك القديم (البيئة)."""
    try:
        fn = ns.get('ai_writer_state')
        if fn is not None:
            st = fn()
            return {'writer': st.get('writer'), 'label': st.get('label')}
    except Exception:   # noqa: BLE001
        pass
    try:
        prov = ns['ai_provider_in_use']()
    except Exception:
        return {'writer': None, 'label': None}
    if not prov:
        return {'writer': None, 'label': None}
    return {'writer': 'main' if prov == 'anthropic' else 'backup', 'label': None}


def writer_of(ns):
    """'main' لو الكاتب الأساسي · 'backup' للاحتياطي · None لا أحد. لا اسم مزوّد من البيئة يخرج أبدًا."""
    return writer_state(ns)['writer']


# ------------------------------------------------------------------ العدّادات

def _day_start():
    n = utcnow()
    return datetime.datetime(n.year, n.month, n.day)


def _counted(q, Item):
    return q.filter(Item.created_at >= _day_start(),
                    ((Item.source == 'ai') | (Item.status == 'failed')))


def brain_today(db, kind=None):
    """عدد كتابات اليوم (UTC): صفوف `source='ai'` + الفاشلة. `kind` للعدّ داخل السقف (الآراء)."""
    Item = _models(db)[0]
    q = Item.query
    if kind:
        q = q.filter(Item.kind == kind)
    return _counted(q, Item).count()


# ------------------------------------------------------------------ تخزين

class StopRun(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _new_state(run_cap_value=None):
    return {'calls': 0, 'items': 0, 'run_cap': run_cap_value, 'per': {}, 'skipped': {}, 'template_calls': 0, 'asks': []}


def _skip(state, key):
    state['skipped'][key] = state['skipped'].get(key, 0) + 1


def _dump(o):
    return json.dumps(o, ensure_ascii=False, default=str)


def _store(ns, p, t, ref, label, h, fj, body, source, state, run_id, failed_error=None):
    """يخزّن صفًّا واحدًا. يعيد حالة الوضع عند التخزين. يرجع (outcome, row|None)."""
    db = ns['db']
    Item = _models(db)[0]
    mode = effective_mode(ns, p)
    if mode == 'off' and failed_error is None:
        return 'off', None
    if failed_error is not None:
        status = 'failed'
    elif isinstance(body, dict) and 'course_id' in body and not body.get('course_id'):
        status = 'discarded'   # لا دورة مناسبة ⇒ لا بطاقة
    elif p.kind == 'opinion':
        status = 'done_alone'
    elif p.kind == 'note' and mode == 'alone' and p.may_run_alone:
        status = 'done_alone'
    else:
        status = 'proposed'
    if failed_error is None and isinstance(body, dict) and status in ('proposed', 'done_alone'):
        label_btn = ((t.meta or {}).get('approve_label') if isinstance(t.meta, dict) else None) \
            or body.get('approve_label') or p.approve_label
        if isinstance(label_btn, str) and label_btn.strip():
            body = dict(body, approve_label=label_btn.strip()[:60])
    row = Item(id=uuid.uuid4().hex, producer=p.id, section=p.section, kind=p.kind, target_ref=ref,
               target_label=label, input_hash=h, facts_json=fj, meta_json=_dump(t.meta or {}),
               body_json=_dump(body if body is not None else {}), status=status, source=source, mode=mode,
               run_id=run_id, created_at=utcnow(), last_error=(failed_error or None))
    try:
        if status == 'proposed':
            Item.query.filter(Item.producer == p.id, Item.target_ref == ref, Item.status == 'proposed',
                              Item.input_hash != h).update({'status': 'expired'}, synchronize_session=False)
        db.session.add(row)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('brain2: store failed for %s %s', p.id, ref)
        return 'exists', None
    state['items'] += 1
    if status == 'proposed' and failed_error is None and p.kind != 'opinion':
        state.setdefault('asks', []).append(row.id)     # سؤال تليجرام واحد لكل اقتراح جديد (يُرسَل بعد الجولة في الخيط الخلفي)
    return ('failed' if failed_error is not None else source), row


def process_target(ns, p, t, state, run_id=None):
    """هدف واحد: بصمة ⇒ سقوف ⇒ نداء ذكاء واحد ⇒ فحوص ⇒ تخزين. يرفع `StopRun` لإيقاف الجولة كلها.
    يرجع: 'exists' | 'skip' | 'ai' | 'template' | 'failed' | 'off'."""
    db = ns['db']
    Item = _models(db)[0]
    try:
        fj = canon(t.facts)
    except (TypeError, ValueError):
        _skip(state, p.id + ':bad_facts')
        return 'skip'
    if len(fj.encode('utf-8')) > FACTS_MAX_BYTES:
        _skip(state, p.id + ':big_facts')
        return 'skip'
    ref = (t.ref or '')[:200]
    label = (t.label or '')[:120]
    if not ref:
        _skip(state, p.id + ':no_ref')
        return 'skip'
    h = input_hash(p, t.facts)
    row = Item.query.filter_by(producer=p.id, target_ref=ref, input_hash=h).first()
    if row is not None:
        # الفاشل يحجب نفس البصمة حتى اليوم التالي (UTC) ثم يُعاد الحساب.
        if row.status == 'failed' and row.created_at is not None and row.created_at < _day_start():
            db.session.delete(row)
            db.session.commit()
        else:
            return 'exists'
    if p.kind != 'opinion' and state['per'].get(p.id, 0) >= p.per_run_cap:
        _skip(state, p.id + ':per_run_cap')
        return 'skip'
    if not writes_enabled():
        raise StopRun('off')
    if state['run_cap'] is not None and state['calls'] >= state['run_cap']:
        raise StopRun('run_cap')
    if brain_today(db) + state['template_calls'] >= day_cap():
        raise StopRun('day_cap')
    if p.kind == 'opinion' and brain_today(db, 'opinion') >= opinion_cap():
        raise StopRun('opinion_cap')
    try:
        remaining = ns['ai_daily_usage_state']().get('remaining')
    except Exception:
        remaining = None
    if remaining is not None and remaining < RESERVE_MIN:
        raise StopRun('reserve')

    state['calls'] += 1
    state['per'][p.id] = state['per'].get(p.id, 0) + 1
    body, err = None, None
    try:
        sys_ar, user_ar = p.prompt(t)
        system = sys_ar if SYSTEM_AR in (sys_ar or '') else SYSTEM_AR + '\n' + (sys_ar or '')
        text = ns['ai_call'](system, user_ar, purpose='brain2.' + p.id)
    except Exception as exc:   # noqa: BLE001
        if getattr(exc, 'kind', None) in ('cap', 'no_key'):
            raise StopRun(exc.kind)
        logger.error('brain2: ai call failed for %s (%s)', p.id, type(exc).__name__)
        err = 'ai_error'
        text = None
    if err is None:
        body, err = _parse(ns, p, t, text)
    if err is None:
        return _store(ns, p, t, ref, label, h, fj, body, 'ai', state, run_id)[0]
    # فشل: قالب لو للمنتج قالب، وإلا صف فاشل بلا بطاقة. لا إعادة محاولة.
    tb = None
    if p.template is not None:
        try:
            tb = p.template(t)
            if isinstance(tb, dict) and check_body(tb, t.facts, p.kind) is not None:
                tb = None
        except Exception:   # noqa: BLE001
            logger.exception('brain2: template failed for %s', p.id)
            tb = None
    if isinstance(tb, dict):
        state['template_calls'] += 1
        return _store(ns, p, t, ref, label, h, fj, tb, 'template', state, run_id)[0]
    failed_error = ERR_INVALID_OUTPUT if err == 'invalid' else ERR_WRITE_FAILED
    if err == 'invalid':
        # منتج بيتحقق من مكتوبه عند المنصة (مسودة الدرس): سبب الرفض العربي أوضح للمؤسس من الجملة العامة.
        try:
            mod = sys.modules.get(getattr(p.validate, '__module__', '') or '')
            why = mod.preview_detail(ref) if mod is not None and hasattr(mod, 'preview_detail') else ''
            if isinstance(why, str) and why.strip():
                failed_error = (ERR_INVALID_OUTPUT + ': ' + why.strip())[:300]
        except Exception:   # noqa: BLE001
            pass
    return _store(ns, p, t, ref, label, h, fj, None, 'ai', state, run_id,
                  failed_error=failed_error)[0]


def _parse(ns, p, t, text):
    """(body, err). err ∈ None | 'invalid'."""
    try:
        data = ns['_extract_json_block'](text)
    except Exception:   # noqa: BLE001
        data = None
    if not isinstance(data, dict):
        return None, 'invalid'
    try:
        body = p.validate(data, t)
    except Exception:   # noqa: BLE001
        logger.exception('brain2: validate raised for %s', p.id)
        return None, 'invalid'
    if not isinstance(body, dict):
        return None, 'invalid'
    if 'course_id' in body and not body.get('course_id'):
        return body, None           # «لا دورة مناسبة»: يُخزَّن discarded بلا فحص نص
    if p.kind == 'opinion':
        body = _opinion_recommend(body, t)
        if body is None:
            return None, 'invalid'
    if check_body(body, t.facts, p.kind) is not None:
        return None, 'invalid'
    try:
        json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        return None, 'invalid'
    return body, None


def _opinion_recommend(body, t):
    """توصية الرأي من القايمة المسموحة لنوعه فقط؛ ونوع المال (قايمة فاضية) يُحذف منه الحقل: نص فقط."""
    spec = opinion_spec(t.meta.get('kind') if isinstance(t.meta, dict) else None)
    allowed = list((spec or {}).get('allowed_recommend') or [])
    body = dict(body)
    if 'recommend' in body:
        if not allowed:
            body.pop('recommend', None)
        elif body['recommend'] not in allowed:
            return None
    return body


# ------------------------------------------------------------------ آراء البطاقات

COMMON_KEYS = ('tag', 'age', 'sub', 'warn', 'reason', 'static_line', 'facts', 'money_text')
_EXTRA_KEYS = {
    'dispute': ('objection', 'expert_reply', 'hours_held'),
    'trainer': ('headline', 'specialty', 'years', 'attachments'),
    'payout': ('method', 'dispute_check', 'fx_alert'),
    'book_offer': ('type', 'suggested_price', 'price_note'),
    'join': ('service', 'licensed', 'licence_missing'),
    'lead': ('body', 'topic'),
    'message': ('body', 'topic'),
}
_MONEY_KINDS = ('payout', 'manual_payment', 'stuck_payment', 'unactivated', 'legacy', 'file_attention', 'dispute')
_DECISION_KINDS = ('trainer', 'join', 'pending_user', 'book_offer', 'book', 'creative', 'topic', 'program')
_INFO_KINDS = ('review', 'lead', 'message', 'open_message', 'course', 'live', 'verify', 'founding', 'other')
EXCLUDED_KINDS = ('file_waiting', 'file_late')


def _fallback_specs():
    out = {}
    for k in _MONEY_KINDS:
        out[k] = {'role_ar': '', 'allowed_recommend': [], 'keys': list(COMMON_KEYS + _EXTRA_KEYS.get(k, ()))}
    for k in _DECISION_KINDS:
        out[k] = {'role_ar': '', 'allowed_recommend': ['approve', 'reject', 'open'],
                  'keys': list(COMMON_KEYS + _EXTRA_KEYS.get(k, ()))}
    for k in _INFO_KINDS:
        out[k] = {'role_ar': '', 'allowed_recommend': ['open', 'wait'],
                  'keys': list(COMMON_KEYS + _EXTRA_KEYS.get(k, ()))}
    return out


def opinion_specs():
    """`producers_ops.OPINION_SPECS` لو موجودة (يصدّرها P2)، وإلا الجدول المبني من المواصفة."""
    try:
        from brain2 import producers_ops
        specs = getattr(producers_ops, 'OPINION_SPECS', None)
    except Exception:   # noqa: BLE001
        specs = None
    if isinstance(specs, dict) and specs:
        return specs
    return _fallback_specs()


def _ops():
    try:
        from brain2 import producers_ops
        return producers_ops
    except Exception:   # noqa: BLE001
        return None


def opinion_spec(kind):
    if not isinstance(kind, str) or kind in EXCLUDED_KINDS:
        return None
    mod = _ops()
    fn = getattr(mod, 'opinion_supported', None)
    if callable(fn):
        try:
            if not fn(kind):
                return None
        except Exception:   # noqa: BLE001
            return None
    return opinion_specs().get(kind)


def opinion_max_bytes():
    v = getattr(_ops(), 'OPINION_MAX_FACTS_BYTES', None)
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else OPINION_FACTS_MAX_BYTES


def _clean_value(v, depth=0):
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        return strip_contacts(clean_text(v, keep_newlines=False))[:OPINION_FACT_STR_MAX]
    if depth >= 3:
        return None
    if isinstance(v, (list, tuple)):
        out = [_clean_value(x, depth + 1) for x in list(v)[:OPINION_FACT_LIST_MAX]]
        return [x for x in out if x is not None]
    if isinstance(v, dict):
        out = {}
        for k, x in list(v.items())[:12]:
            if isinstance(k, str) and 0 < len(k) <= 40:
                cx = _clean_value(x, depth + 1)
                if cx is not None:
                    out[k] = cx
        return out
    return None


def clean_opinion_facts(kind, facts):
    """قايمة بيضا بالمفاتيح + حدود الطول + مسح الإيميلات والهواتف. يرجع dict (قد يكون فاضيًا).
    دالة P2 (`producers_ops.clean_opinion_facts`) لو موجودة هي المرجع، وإلا النسخة المبنية من المواصفة."""
    fn = getattr(_ops(), 'clean_opinion_facts', None)
    if callable(fn):
        try:
            out = fn(kind, facts)
            if isinstance(out, dict):
                return out
        except Exception:   # noqa: BLE001
            logger.exception('brain2: ops clean_opinion_facts failed')
    return _clean_opinion_facts_local(kind, facts)


def _clean_opinion_facts_local(kind, facts):
    spec = opinion_spec(kind) or {}
    allowed = set(COMMON_KEYS) | set(spec.get('keys') or ())
    if not isinstance(facts, dict):
        return {}
    out = {}
    for k in sorted(facts):
        if k in allowed:
            cv = _clean_value(facts[k])
            if cv is not None and cv != '' and cv != [] and cv != {}:
                out[k] = cv
    return out


def opinion_target(kind, card_id, facts, label=''):
    """هدف الرأي. `producers_ops.opinion_target` لو موجودة (ترفع ValueError لنوع غير مدعوم) وإلا النسخة المحلية.
    يرجع None لنوع غير مدعوم."""
    if opinion_spec(kind) is None:
        return None
    fn = getattr(_ops(), 'opinion_target', None)
    if callable(fn):
        try:
            t = fn(kind, card_id, facts)
            if isinstance(t, Target):
                return t
        except ValueError:
            return None
        except Exception:   # noqa: BLE001
            logger.exception('brain2: ops opinion_target failed')
    cid = str(card_id)[:190]
    return Target(ref='card:' + cid, label=(label or cid)[:120],
                  facts=dict(facts, kind=kind), meta={'kind': kind, 'card_id': cid})


def opinion_lookup(ns, kind, card_id, facts):
    """صف الرأي الجاهز لهذه البطاقة وبياناتها، أو None. ⛔ لا يكتب ولا يستدعي الذكاء."""
    p = registry.by_id('opinion')
    if p is None or opinion_spec(kind) is None or not card_id:
        return None
    t = opinion_target(kind, card_id, facts)
    if t is None:
        return None
    Item = _models(ns['db'])[0]
    return Item.query.filter_by(producer=p.id, target_ref=t.ref[:200], input_hash=input_hash(p, t.facts)).first()


# ------------------------------------------------------------------ الخيط الخلفي

_Q = queue.Queue(maxsize=QUEUE_SIZE)
_PENDING = set()
_LOCK = threading.Lock()
_WORKER = {'thread': None}


def _worker_loop(app, db):
    while True:
        key, fn = _Q.get()
        try:
            with app.app_context():
                try:
                    fn()
                except Exception:   # noqa: BLE001
                    logger.exception('brain2: job failed')
                finally:
                    try:
                        db.session.remove()
                    except Exception:   # noqa: BLE001
                        pass
        finally:
            with _LOCK:
                _PENDING.discard(key)
            _Q.task_done()


def submit(ns, key, fn):
    """يسلّم العمل لخيط واحد. يرجع {'queued': True} أو {'queued': False, 'reason': 'busy'}.
    `app.config['BRAIN_INLINE']` ⇒ ينفَّذ فورًا في الخيط الحالي (للاختبارات)."""
    app = ns['app']
    if app.config.get('BRAIN_INLINE'):
        try:
            from flask import has_app_context
            if has_app_context():
                fn()
            else:
                with app.app_context():
                    fn()
        except Exception:   # noqa: BLE001
            logger.exception('brain2: inline job failed')
        return {'queued': True}
    with _LOCK:
        if key in _PENDING:
            return {'queued': True, 'duplicate': True}
        if _WORKER['thread'] is None or not _WORKER['thread'].is_alive():
            th = threading.Thread(target=_worker_loop, args=(app, ns['db']), name='brain2-worker', daemon=True)
            _WORKER['thread'] = th
            th.start()
        try:
            _Q.put_nowait((key, fn))
        except queue.Full:
            return {'queued': False, 'reason': 'busy'}
        _PENDING.add(key)
    return {'queued': True}


# ------------------------------------------------------------------ الجولة

def active_run(db):
    Run = _models(db)[2]
    since = utcnow() - datetime.timedelta(minutes=RUN_LOCK_MINUTES)
    return Run.query.filter(Run.finished_at.is_(None), Run.started_at > since).order_by(Run.started_at.desc()).first()


def start_run(ns, trigger, actor, only=None):
    """يفتح صف جولة ويسلّم التنفيذ للخيط. يرجع (http_status, payload)."""
    db = ns['db']
    Run = _models(db)[2]
    if not writes_enabled():
        return 409, {'error': ERR_WRITE_OFF}
    if active_run(db) is not None:
        return 409, {'error': ERR_RUNNING}
    run = Run(id=uuid.uuid4().hex, trigger=trigger, started_at=utcnow(), ai_calls=0, items=0, by=str(actor)[:255])
    db.session.add(run)
    db.session.commit()
    run_id = run.id
    sub = submit(ns, 'run', lambda: execute_run(ns, run_id, only, actor))
    if not sub.get('queued'):
        _finish_run(ns, run_id, 0, 0, {'_stop': 'busy'})
        return 409, {'error': ERR_RUNNING}
    return 202, {'run_id': run_id}


def _finish_run(ns, run_id, calls, items, skipped):
    db = ns['db']
    Run = _models(db)[2]
    try:
        run = Run.query.get(run_id)
        if run is not None:
            run.finished_at = utcnow()
            run.ai_calls = calls
            run.items = items
            run.skipped_json = _dump(skipped)
            db.session.commit()
    except Exception:   # noqa: BLE001
        db.session.rollback()
        logger.exception('brain2: finishing run failed')


def _gather(p, ctx, state):
    """`gather` المنتج. مسودات الرد (P2) تعرض `gather_with_errors` ⇒ نسجّل المصدر الفاشل في سجل الجولة
    والباقي يعمل. لا نستعملها إلا لو `p.gather` معرّفة داخل producers_ops نفسها (لا لمنتج مزيّف بالاسم)."""
    mod = _ops()
    fn = getattr(mod, 'gather_with_errors', None)
    if p.id == 'reply_draft' and callable(fn) and getattr(p.gather, '__module__', None) == getattr(mod, '__name__', ''):
        targets, errors = fn(ctx)
        for e in errors or []:
            if isinstance(e, dict):
                _skip(state, 'reply_draft:%s:%s' % (str(e.get('source', '?'))[:20], str(e.get('reason', 'down'))[:20]))
        return targets
    return p.gather(ctx)


def execute_run(ns, run_id, only, actor):
    state = _new_state(run_cap())
    ctx = Ctx(ns=ns, now=_aware(), actor=str(actor))
    only_set = set([only] if isinstance(only, str) else (only or []))
    try:
        for p in list(registry.PRODUCERS):
            if p.kind == 'opinion' or (only_set and p.id not in only_set):
                continue
            try:
                mode = effective_mode(ns, p)
            except Exception:   # noqa: BLE001
                logger.exception('brain2: mode failed for %s', p.id)
                continue
            if mode == 'off':
                _skip(state, p.id + ':off')
                continue
            try:
                targets = _gather(p, ctx, state)
            except Exception as exc:   # noqa: BLE001
                if exc.__class__.__name__ != 'SourceDown':
                    logger.exception('brain2: gather failed for %s', p.id)
                _skip(state, p.id + (':source_down' if exc.__class__.__name__ == 'SourceDown' else ':gather_error'))
                continue
            seen = set()
            for t in targets or []:
                if not isinstance(t, Target) or t.ref in seen:
                    continue
                seen.add(t.ref)
                try:
                    process_target(ns, p, t, state, run_id)
                except StopRun:
                    raise
                except Exception:   # noqa: BLE001
                    ns['db'].session.rollback()
                    logger.exception('brain2: target failed %s %s', p.id, t.ref)
                    _skip(state, p.id + ':error')
    except StopRun as stop:
        state['skipped']['_stop'] = stop.reason
    except Exception:   # noqa: BLE001
        logger.exception('brain2: run crashed')
        state['skipped']['_stop'] = 'error'
    finally:
        _finish_run(ns, run_id, state['calls'], state['items'], state['skipped'])
        _send_asks(ns, state.get('asks'))


def _send_asks(ns, ids):
    """أسئلة تليجرام للاقتراحات الجديدة، في الخيط الخلفي بعد ختم الجولة. أي فشل يُسجَّل ولا يكسر الجولة."""
    if not ids:
        return
    try:
        from brain2 import telegram
        telegram.send_asks(ns, ids)
    except Exception:   # noqa: BLE001
        logger.exception('brain2: telegram asks failed')


def submit_opinion(ns, kind, card_id, facts):
    """يرجع (item|None, reason|None, queued). ⛔ لا يستدعي الذكاء في خيط الطلب: يسلّم للخيط الخلفي."""
    p = registry.by_id('opinion')
    if p is None or opinion_spec(kind) is None:
        return None, 'not_supported', False
    if not writes_enabled():
        return None, 'off', False
    if effective_mode(ns, p) == 'off':
        return None, 'off', False
    existing = opinion_lookup(ns, kind, card_id, facts)
    if existing is not None:
        if existing.status == 'failed' and existing.created_at is not None and existing.created_at < _day_start():
            pass
        elif existing.status == 'failed':
            return None, 'failed', False
        else:
            return existing, None, False
    if writer_of(ns) is None:
        return None, 'no_writer', False
    db = ns['db']
    if brain_today(db) >= day_cap() or brain_today(db, 'opinion') >= opinion_cap():
        return None, 'cap', False
    try:
        remaining = ns['ai_daily_usage_state']().get('remaining')
    except Exception:   # noqa: BLE001
        remaining = None
    if remaining is not None and remaining < RESERVE_MIN:
        return None, 'cap', False
    t = opinion_target(kind, card_id, facts)
    if t is None:
        return None, 'not_supported', False
    h = input_hash(p, t.facts)

    def job():
        state = _new_state(None)
        try:
            process_target(ns, p, t, state)
        except StopRun as stop:
            logger.info('brain2: opinion stopped (%s)', stop.reason)
        except Exception:   # noqa: BLE001
            ns['db'].session.rollback()
            logger.exception('brain2: opinion job failed')

    sub = submit(ns, 'op:' + h, job)
    if not sub.get('queued'):
        return None, 'busy', False
    return None, None, True


# ------------------------------------------------------------------ الاعتماد

def _loads(s, default):
    try:
        v = json.loads(s) if s else default
        return v if isinstance(v, type(default)) else default
    except (TypeError, ValueError):
        return default


def apply_item(ns, item_id, actor, edited_text=None):
    """proposed ⇒ applying (تحديث شرطي) ⇒ approved/edited/unknown/proposed. يرجع (status_code, payload)."""
    from brain2.contract import ApplyResult
    db = ns['db']
    Item = _models(db)[0]
    row = Item.query.get(item_id)
    if row is None:
        return 404, {'error': 'هذا الاقتراح غير موجود'}
    if row.status != 'proposed':
        return 409, {'error': ERR_DECIDED}
    p = registry.by_id(row.producer)
    body = _loads(row.body_json, {})
    edited = False
    if edited_text is not None:
        body = dict(body)
        edited = edited_text != body.get('text')
        body['text'] = edited_text
    changed = Item.query.filter(Item.id == item_id, Item.status == 'proposed').update(
        {'status': 'applying'}, synchronize_session=False)
    db.session.commit()
    if changed != 1:
        return 409, {'error': ERR_DECIDED}
    target = Target(ref=row.target_ref, label=row.target_label or '', facts=_loads(row.facts_json, {}),
                    meta=_loads(row.meta_json, {}))
    ctx = Ctx(ns=ns, now=_aware(), actor=str(actor))
    ctx.item_id = item_id      # للتنفيذ فقط (مفتاح عدم تكرار البريد = معرّف الاقتراح)؛ العقد لا يتغيّر
    unknown = False
    if p is None:
        res = ApplyResult(ok=False, error=ERR_APPLY_FAILED)
    elif p.apply is None:
        res = ApplyResult(ok=True)     # لا فعل خارجي: الاعتماد قرار المؤسس فقط (مثل «احتفظ بها»)
    else:
        try:
            res = p.apply(ctx, body, target)
        except Exception:   # noqa: BLE001
            logger.exception('brain2: apply raised for %s', row.producer)
            res, unknown = ApplyResult(ok=False, no_reply=True), True   # لا نعرف هل تم الفعل
        if not isinstance(res, ApplyResult):
            res, unknown = ApplyResult(ok=False, no_reply=True), True
    now = utcnow()
    db.session.expire_all()
    row = Item.query.get(item_id)
    if res.ok:
        row.status = 'edited' if edited else 'approved'
        row.decided_at, row.decided_by, row.last_error = now, str(actor)[:255], None
        if edited:
            row.body_json = _dump(body)
        row.applied_json = _dump({'copy_text': res.copy_text or '', 'info': res.info or {}})
        db.session.commit()
        _audit(ns, 'brain.approve', item_id, {'producer': row.producer, 'edited': edited}, actor)
        return 200, {'ok': True, 'id': item_id, 'status': row.status, 'copy_text': res.copy_text or '',
                     'info': res.info or {}}
    if res.no_reply or unknown:
        row.status = 'unknown'
        row.decided_at, row.decided_by = now, str(actor)[:255]
        row.last_error = (res.error or ERR_NO_REPLY)[:300]
        db.session.commit()
        _audit(ns, 'brain.approve_unknown', item_id, {'producer': row.producer}, actor)
        pl = {'error': res.error or ERR_NO_REPLY, 'no_reply': True}
        if res.copy_text:
            pl['copy_text'] = res.copy_text
        return 502, pl
    row.status = 'proposed'
    row.last_error = (res.error or ERR_APPLY_FAILED)[:300]
    db.session.commit()
    pl = {'error': res.error or ERR_APPLY_FAILED}
    if res.copy_text:
        pl['copy_text'] = res.copy_text     # زائر بلا حساب: الرد لم يُرسل لكن النص ينسخه المؤسس بنفسه
    return 422, pl


def _audit(ns, action, target, meta, actor):
    try:
        ns['_audit'](action, target=target, meta=meta)
    except Exception:   # noqa: BLE001
        logger.exception('brain2: audit failed')
