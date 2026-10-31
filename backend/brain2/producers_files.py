# -*- coding: utf-8 -*-
"""منتج «العقل» لمراجعة آراء «ملف للخبير» قبل أن تصل العميل — `file_review` (SPEC-B §B3).

ما يراجعه: ملفات `in_review` أي أول آراء خبير جديد تنتظر المؤسس.
ما يكتبه: ملاحظات مراجعة (هل أُجيب كل سؤال؟ هل الموقف يتبع الوقائع؟ هل تنقص خطوة تالية؟) + توصية: اعتمد أو أرجِع.
ما ينفذه: لا شيء إلا بعد اعتماد المؤسس (أو ضغطته من تليجرام). الاعتماد يرسل الرأي للعميل، لذلك المنتج مقفول على «يسألني».
العقل يراجع ويوصي فقط. لا فلوس تُمس هنا.

قواعد الملف:
  * القراءة عبر `ctx.ns['_platform_proxy']` وقت النداء (لا وقت الاستيراد). التفاصيل عبر `ef_detail._ef_detail_for_brain` (خادم فقط).
  * facts لا تحوي اسم العميل ولا بريده ولا هاتفه؛ المعرّف في `meta` فقط.
  * الكتابة الوحيدة: مراجعة ملف واحد عبر `_v2_write` (نداء واحد، `by` من الفاعل، لا إعادة محاولة).
"""
import hashlib
import json
import re
from urllib.parse import quote

from brain2.contract import ApplyResult, Producer, SourceDown, Target
from brain2 import ef_detail

PRODUCER_ID = 'file_review'
FACTS_MAX_BYTES = 3900
LIST_LIMIT = 10
TEXT_MAX = 600
NOTE_MAX = 600
RECS = ('approve', 'return')
LABEL_APPROVE = 'اعتمد الرأي وأرسله'
LABEL_RETURN = 'أرجِعه بالملاحظة'
LOCK_REASON = 'يسألك دائمًا لأن الاعتماد يرسل الرأي إلى العميل.'
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')

_SYSTEM_FALLBACK = (
    'اكتب بالعربية الفصحى البسيطة، بصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا، لجمهور دولي، بلا مصطلحات تقنية. '
    'استعمل الحقائق المعطاة وحدها؛ لا تخترع رقمًا ولا اسمًا ولا تاريخًا ولا وعدًا، ولا تقل إن شيئًا نُفِّذ. '
    'أعد JSON صالحًا فقط بالشكل المطلوب.'
)
_ROLE = (
    ' دورك: مراجعة رأي كتبه خبير جديد قبل أن يصل إلى العميل. افحص ثلاثة أشياء فقط، اعتمادًا على الحقائق المعطاة وحدها: '
    'هل أُجيب كل سؤال من الأسئلة؟ هل الموقف المكتوب يتبع الوقائع؟ هل تنقص خطوة تالية واضحة؟ '
    'في text اكتب ملاحظاتك بجملتين إلى أربع جمل (حتى ٦٠٠ حرف). '
    'أوصِ بـ approve إن اكتمل الرأي في الأشياء الثلاثة، وبـ return إن نقص شيء منها، '
    'وعندها اكتب في return_note ملاحظة تصل إلى الخبير كما هي: واضحة ومهذبة وتقول ما يلزم إكماله. '
    'لا تذكر اسم العميل. لا تضف أرقامًا من عندك. '
    'الشكل المطلوب: {"text":"…","recommend":"approve|return","return_note":"… (مطلوب عند return)"}'
)


def _system_ar():
    try:
        from brain2.engine import SYSTEM_AR
        if isinstance(SYSTEM_AR, str) and SYSTEM_AR.strip():
            return SYSTEM_AR
    except Exception:   # noqa: BLE001
        pass
    return _SYSTEM_FALLBACK


def _fn(ctx, name):
    fn = ctx.ns.get(name)
    if not callable(fn):
        raise SourceDown(name)
    return fn


def _size(facts):
    return len(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def _longest_str(o, best=None):
    """(حاوية, مفتاح, نص) لأطول نص داخل البنية."""
    items = o.items() if isinstance(o, dict) else (enumerate(o) if isinstance(o, list) else ())
    for k, v in items:
        if isinstance(v, str):
            if best is None or len(v) > len(best[2]):
                best = (o, k, v)
        elif isinstance(v, (dict, list)):
            best = _longest_str(v, best)
    return best


def _fit(facts):
    """يقلّص الحقائق حتى تسع: يسحب من آخر الوقائع والمهام والأسئلة والإجابات (يبقى واحد من الأسئلة والإجابات)،
    ثم يقصّ أطول نص إلى نصفه."""
    po = facts.get('pending_opinion') or {}
    guard = 0
    while _size(facts) > FACTS_MAX_BYTES and guard < 600:
        guard += 1
        if facts.get('facts'):
            facts['facts'].pop()
        elif po.get('todo'):
            po['todo'].pop()
        elif len(facts.get('questions') or []) > 1:
            facts['questions'].pop()
        elif len(po.get('answers') or []) > 1:
            po['answers'].pop()
        else:
            best = _longest_str(facts)
            if best is None or len(best[2]) <= 40:
                break
            best[0][best[1]] = best[2][:max(40, len(best[2]) // 2)]
    return facts


# ------------------------------------------------------------------ الموقف بالعربية
_STANCE_AR = {
    'favorable': 'في صالح العميل', 'unfavorable': 'ليس في صالح العميل', 'mixed': 'مختلط',
    'cautious': 'مشروط', 'conditional': 'مشروط',
}
_LATIN_RE = re.compile(r'[A-Za-z]')


def _stance_ar(po):
    """الموقف الذي يراه المؤسس عربي دائمًا: `stance_label` من المنصة إن كان عربيًا، وإلا ترجمة القيمة الإنجليزية المعروفة.
    قيمة لاتينية غير معروفة تُحذف (لا حرف لاتيني على البطاقة)."""
    label = po.get('stance_label')
    if isinstance(label, str) and label.strip() and not _LATIN_RE.search(label):
        return label.strip()
    raw = po.get('stance')
    raw = raw.strip() if isinstance(raw, str) else ''
    if raw.lower() in _STANCE_AR:
        return _STANCE_AR[raw.lower()]
    return '' if _LATIN_RE.search(raw) else raw


# ------------------------------------------------------------------ gather

def _list_rows(ctx):
    """ملفات `in_review` من قائمة الجسر. ٤٠٤ (الجسر لسه غير منشور) ⇒ لا ملفات، وليس عطلًا. غير ذلك ⇒ SourceDown."""
    path = '/api/bridge/expert-files'
    try:
        resp = _fn(ctx, '_platform_proxy')('GET', path, params={'status': 'review'})
    except SourceDown:
        raise
    except Exception as exc:   # noqa: BLE001
        raise SourceDown('%s: %s' % (path, type(exc).__name__))
    if ef_detail._status_of(resp) == 404:
        return []
    if not ef_detail._ok(ctx.ns, resp):
        raise SourceDown('%s: http %s' % (path, ef_detail._status_of(resp)))
    body = ef_detail._json_of(resp)
    rows = body.get('files') if isinstance(body, dict) else body
    if not isinstance(rows, list):
        raise SourceDown('%s: bad shape' % path)
    return [r for r in rows if isinstance(r, dict)]


def gather(ctx):
    rows = []
    for r in _list_rows(ctx):
        fid = str(r.get('id') or '').strip()
        if not _ID_RE.match(fid) or (r.get('status') and r.get('status') != 'in_review'):
            continue
        rows.append(fid)
        if len(rows) >= LIST_LIMIT:
            break
    out, failed = [], 0
    for fid in rows:
        try:
            d = ef_detail._ef_detail_for_brain(ctx.ns, fid)
        except SourceDown:
            failed += 1
            continue
        po = d.get('pending_opinion') or {}
        if d.get('status') != 'in_review' or not po.get('answers'):
            continue
        po = dict(po, stance=_stance_ar(po))
        po.pop('stance_label', None)
        facts = {'title': d['title'], 'questions': d['questions'], 'facts': d['facts'], 'pending_opinion': po}
        if d.get('round'):
            facts['round'] = d['round']
        _fit(facts)
        out.append(Target(ref='file:' + fid, label=('مراجعة رأي: ' + (d['title'] or 'ملف'))[:120], facts=facts,
                          meta={'file_id': fid}))
    if rows and failed == len(rows):
        raise SourceDown('expert-file details unreadable')
    return out


# ------------------------------------------------------------------ prompt / validate

def prompt(target):
    user = 'راجع هذا الرأي قبل أن يصل إلى العميل.\n\nالحقائق:\n%s' % json.dumps(target.facts, ensure_ascii=False, sort_keys=True)
    return _system_ar() + _ROLE, user


def _sha(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]


def _honest(text, facts):
    """نفس فحوص الصدق على نص لا يفحصه المحرّك (ملاحظة الإرجاع تصل إلى الخبير كما هي)."""
    from brain2 import engine
    return engine.check_body({'text': text}, facts, 'note') is None


def validate(raw, target):
    if not isinstance(raw, dict):
        return None
    text = raw.get('text')
    rec = raw.get('recommend')
    if not isinstance(text, str) or rec not in RECS:
        return None
    text = text.strip()
    if not text or len(text) > TEXT_MAX:
        return None
    body = {'text': text, 'recommend': rec, 'return_note': '', 'notes_sha': _sha(text),
            'file_id': (target.meta or {}).get('file_id') or '',
            'approve_label': LABEL_APPROVE if rec == 'approve' else LABEL_RETURN}
    if rec == 'return':
        note = raw.get('return_note')
        if not isinstance(note, str):
            return None
        note = note.strip()
        if not note or len(note) > NOTE_MAX or not _honest(note, target.facts):
            return None
        body['return_note'] = note
    return body


# ------------------------------------------------------------------ apply

def _bad(msg, **kw):
    return ApplyResult(ok=False, error=msg, **kw)


def _write_result(ns, resp, info):
    if ns['_resp_ok'](resp):
        return ApplyResult(ok=True, info=info)
    js = ns['_proxy_json'](resp)
    err = js.get('error') if isinstance(js.get('error'), str) else ''
    if js.get('no_reply') is True:
        return ApplyResult(ok=False, no_reply=True, error=err)
    return ApplyResult(ok=False, error=err or 'تعذّر التنفيذ الآن')


def apply(ctx, body, target):
    """approve ⇒ يعتمد الرأي ويصل العميل. return ⇒ يرجعه للخبير بملاحظة (ملاحظة المؤسس المعدّلة إن عدّل، وإلا ملاحظة العقل).
    مسار المراجعة الموجود نفسه على المنصة، عبر `_v2_write` (نداء واحد · `by` · تدقيق عند النجاح · «ما وصلناش رد»)."""
    body = body or {}
    fid = (target.meta or {}).get('file_id') or ''
    if not _ID_RE.match(str(fid)):
        return _bad('تعذّر تحديد الملف')
    rec = body.get('recommend')
    if rec not in RECS:
        return _bad('توصية غير معروفة')
    if rec == 'approve':
        payload, action = {'action': 'approve', 'note': ''}, 'approve'
    else:
        text = str(body.get('text') or '').strip()
        edited = bool(text) and _sha(text) != body.get('notes_sha')
        note = (text if edited else str(body.get('return_note') or '').strip())[:1000]
        if not note:
            return _bad('اكتب ملاحظة للخبير')
        payload, action = {'action': 'return', 'note': note}, 'return'
    path = '/api/bridge/expert-files/%s/review' % quote(str(fid), safe='')
    resp = _fn(ctx, '_v2_write')('POST', path, payload, 'expert_file.review_' + action, fid, {'via': 'brain'})
    line = 'اعتُمد الرأي وأُرسل إلى العميل' if action == 'approve' else 'أُرجع الملف إلى الخبير بالملاحظة'
    return _write_result(ctx.ns, resp, {'file_id': fid, 'action': action, 'line': line})


PRODUCERS = [
    Producer(
        id=PRODUCER_ID, section='files', kind='draft',
        label='مراجعة آراء الخبراء الجدد',
        sentence='عندما ينتظرك أول رأي لخبير جديد، يراجعه العقل ويقترح: اعتمده أو أرجِعه بملاحظة.',
        lock_reason=LOCK_REASON, may_run_alone=False, default_mode='ask', per_run_cap=3,
        gather=gather, prompt=prompt, validate=validate, template=None, apply=apply,
        tag='مراجعة رأي', approve_label=LABEL_APPROVE,
    ),
]
