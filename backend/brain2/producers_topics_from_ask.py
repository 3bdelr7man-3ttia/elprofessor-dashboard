# -*- coding: utf-8 -*-
"""منتج «العقل» لتحويل تصحيحات «اسأل» اللي «مفيش نص يحسمها» لمواضيع خبراء — `ask_topic` (2026-11-09).

المصدر: بنود العقل المحلية `ask_correction` (وبنود `training_item`) اللي حكم العقل فيها `no_text`.
  الحكم متخزّن في `body_json['verdict']` للصف المحلي (`v2_brain_items`)؛ نقبل بس الصفوف اللي حكمها جاي من الموديل
  (`source='ai'`): حكم القالب «لم تتم المقارنة بالنص» مش حكمًا.
ما يكتبه الموديل: موضوع عام للخبراء (عنوان + سؤال معمّم + سبب) من سؤال المستخدم وتصحيحه. ⛔ ولا بيانات شخصية: التحقق صارم
  (أي رقم، أي حرف لاتيني، علامات شخصية ⇒ مرفوض) وما فيش قالب بديل: التعميم الآمن محتاج الموديل (لا موديل ⇒ لا بطاقة).
ما ينفذه: بعد اعتماد المؤسس بس ⇒ `POST /api/bridge/topics/seed` (موضوع عام حيّ باسم «المنصة»، متفرّد بالعنوان).
  نص البطاقة قابل للتعديل: السطر الأول = العنوان، والباقي = السؤال، ويُعاد التحقق عليه قبل الإرسال.
⛔ الجسر عام: لا شيء شخصي يوصله أبدًا (لا معرّف تصحيح ولا اسم ولا نص المستخدم)؛ يوصله العنوان والسؤال بعد التحقق فقط.
"""
import json
import re

from brain2.contract import ApplyResult, Producer, Target

PRODUCER_ID = 'ask_topic'
SOURCE_PRODUCERS = ('ask_correction', 'training_item')
SOURCE_STATUSES = ('approved', 'edited', 'rejected', 'proposed')
LIST_LIMIT = 10
Q_MAX, C_MAX = 500, 800
TITLE_MIN, TITLE_MAX, QUESTION_MIN, QUESTION_MAX, WHY_MAX = 10, 90, 20, 400, 160
LABEL_APPROVE = 'انشره موضوع للخبراء'
TAG = 'موضوع مقترح للخبراء'
FOOTER = 'من تصحيح على إجابة اسأل مفيش نص بيحسمه'
LOCK_REASON = 'يسألك دائمًا لأن الموضوع بيتنشر علنًا باسم المنصة.'
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')

_MARKERS = ('أنا', 'لي', 'نفسي', 'انا', 'اني', 'إني', 'ابني', 'ابنتي', 'بنتي', 'مراتي', 'زوجتي', 'زوجي', 'جوزي', 'شركتي', 'اسمي',
            'اسمه', 'اسمها', 'أخي', 'اخويا', 'أختي', 'اختي', 'أبي', 'والدي', 'والدتي', 'أمي', 'عندي', 'معي',
            'موكلي', 'عميلي', 'صديقي', 'صاحبي', 'جاري', 'مديري', 'زميلي', 'قريبي', 'بيتي', 'منزلي', 'موظفي',
            'السيد', 'السيدة', 'الأستاذ', 'الأستاذة', 'الدكتور', 'المدعو', 'المدعوة')
_MARKER_RE = re.compile(r'(?<![؀-ۿ])(?:[وفبل]?)(?:%s)(?![؀-ۿ])' % '|'.join(map(re.escape, _MARKERS)))
_DIGIT_RE = re.compile(r'[0-9٠-٩۰-۹]')
_LATIN_RE = re.compile(r'[A-Za-z]')
_LINK_RE = re.compile(r'https?:|www\.|@')

_ROLE = (
    ' دورك: محرّر موضوعات للخبراء. أمامك سؤال مستخدم في القانون وتصحيح كُتب عليه لم تحسمه نصوص قاعدتنا. '
    'حوّله إلى موضوع عام يناقشه الخبراء علنًا: لا تذكر أي اسم ولا مكان ولا تاريخ ولا مبلغ ولا رقم هاتف ولا رقم مادة، '
    'ولا واقعة السائل الخاصة، وعمّم الأطراف («موظف»، «جهة إدارية»، «عامل»…). ⛔ ممنوع أي رقم أو حرف لاتيني نهائيًا. '
    'ولا تتكلم بصيغة المتكلم. title_ar: سؤال قانوني محايد حتى ٩٠ حرفًا. '
    'question_ar: صياغة عامة للمسألة حتى ٤٠٠ حرف. why_ar: جملة واحدة حتى ١٦٠ حرفًا لماذا يستحق النقاش. '
    'الشكل المطلوب: {"title_ar":"…","question_ar":"…","why_ar":"…"}'
)


def _loads(s, default):
    try:
        v = json.loads(s) if isinstance(s, str) and s else default
        return v if isinstance(v, type(default)) else default
    except Exception:   # noqa: BLE001
        return default


def _unsafe(s):
    return bool(_DIGIT_RE.search(s) or _LATIN_RE.search(s) or _LINK_RE.search(s) or _MARKER_RE.search(s))


def check_topic(title, question):
    """(title, question) نظيفين أو None. صارم: أي رقم/لاتيني/علامة شخصية/رابط ⇒ None."""
    if not isinstance(title, str) or not isinstance(question, str):
        return None
    title, question = re.sub(r'\s+', ' ', title).strip(), re.sub(r'\s+', ' ', question).strip()
    if not (TITLE_MIN <= len(title) <= TITLE_MAX) or not (QUESTION_MIN <= len(question) <= QUESTION_MAX):
        return None
    if _unsafe(title) or _unsafe(question):
        return None
    return title, question


def _split(text):
    """السطر الأول عنوان والباقي سؤال (أسطر الباقي تُدمج بمسافة)."""
    lines = [ln.strip() for ln in str(text or '').strip().split('\n') if ln.strip()]
    if len(lines) < 2:
        return None, None
    return lines[0], ' '.join(lines[1:])


def _source_rows(ctx):
    from brain2.engine import _models
    Item = _models(ctx.ns['db'])[0]
    return Item.query.filter(Item.producer.in_(SOURCE_PRODUCERS), Item.status.in_(SOURCE_STATUSES),
                             Item.source == 'ai').order_by(Item.created_at.desc()).limit(200).all()


def _existing_refs(ctx):
    from brain2.engine import _models
    Item = _models(ctx.ns['db'])[0]
    return {r.target_ref for r in Item.query.filter(Item.producer == PRODUCER_ID, Item.status != 'failed').all()}


def gather(ctx):
    try:
        rows = _source_rows(ctx)
        taken = _existing_refs(ctx)
    except Exception:   # noqa: BLE001
        return []
    out, seen = [], set()
    for r in rows:
        body = _loads(r.body_json, {})
        if body.get('verdict') != 'no_text':
            continue
        facts = _loads(r.facts_json, {})
        meta = _loads(r.meta_json, {})
        if r.producer == 'ask_correction':
            key, question, corr = meta.get('feedback_id'), facts.get('question'), facts.get('correction')
        else:
            key, question, corr = meta.get('item_id'), facts.get('question'), facts.get('expert_answer')
            key = ('t-%s' % key) if key else key
        key = str(key or '').strip()
        question, corr = str(question or '').strip(), str(corr or '').strip()
        if not _ID_RE.match(key) or not question or not corr:
            continue
        ref = 'asktopic:' + key
        if ref in taken or ref in seen:
            continue
        seen.add(ref)
        out.append(Target(ref=ref, label=('موضوع من «اسأل»: ' + question)[:120],
                          facts={'question': question[:Q_MAX], 'correction': corr[:C_MAX]},
                          meta={'source_id': key, 'source_producer': r.producer}))
        if len(out) >= LIST_LIMIT:
            break
    return out


def prompt(target):
    try:
        from brain2.engine import SYSTEM_AR
    except Exception:   # noqa: BLE001
        SYSTEM_AR = ''
    user = 'حوّل هذا إلى موضوع عام للخبراء.\n\nالحقائق:\n%s' % json.dumps(target.facts, ensure_ascii=False, sort_keys=True)
    return (SYSTEM_AR or '') + _ROLE, user


def validate(raw, target):
    if not isinstance(raw, dict):
        return None
    ok = check_topic(raw.get('title_ar'), raw.get('question_ar'))
    if ok is None:
        return None
    title, question = ok
    why = raw.get('why_ar')
    why = re.sub(r'\s+', ' ', why).strip() if isinstance(why, str) else ''
    if why and (len(why) > WHY_MAX or _unsafe(why)):
        why = ''
    foot = FOOTER + ((' — ' + why) if why else '')
    foot = foot if len(foot) <= WHY_MAX else FOOTER
    return {'text': '%s\n%s' % (title, question), 'title': title, 'question': question,
            'why': foot, 'approve_label': LABEL_APPROVE}


def apply(ctx, body, target):
    title, question = _split((body or {}).get('text'))
    ok = check_topic(title, question)
    if ok is None:
        return ApplyResult(ok=False, error='العنوان والسؤال لازم يبقوا عامين: سطر للعنوان وبعده السؤال، بلا أرقام ولا أسماء ولا حروف لاتينية')
    title, question = ok
    payload = {'items': [{'title': title, 'question': question}], 'apply': True}
    fn = ctx.ns.get('_v2_write')
    if not callable(fn):
        return ApplyResult(ok=False, error='تعذّر التنفيذ الآن')
    resp = fn('POST', '/api/bridge/topics/seed', payload, 'ask.topic_seed', PRODUCER_ID, {'via': 'brain'})
    ns = ctx.ns
    js = ns['_proxy_json'](resp)
    js = js if isinstance(js, dict) else {}
    if ns['_resp_ok'](resp):
        if js.get('created'):
            return ApplyResult(ok=True, info={'line': 'اتنشر موضوع'})
        if js.get('skipped'):
            return ApplyResult(ok=True, info={'line': 'الموضوع موجود قبل كده'})
        return ApplyResult(ok=False, no_reply=True, error='المنصة ما أكدتش نشر الموضوع')
    err = js.get('error') if isinstance(js.get('error'), str) else ''
    if js.get('no_reply') is True:
        return ApplyResult(ok=False, no_reply=True, error=err)
    return ApplyResult(ok=False, error=err or 'تعذّر التنفيذ الآن')


PRODUCERS = [
    Producer(
        id=PRODUCER_ID, section='content', kind='draft',
        label='مواضيع للخبراء من تصحيحات «اسأل»',
        sentence='عندما يقول العقل إن تصحيحًا على إجابة «اسأل» لا يحسمه نص، يقترح موضوعًا عامًا للخبراء، ولا ينشر إلا باعتمادك.',
        lock_reason=LOCK_REASON, may_run_alone=False, default_mode='ask', per_run_cap=3,
        gather=gather, prompt=prompt, validate=validate, template=None, apply=apply,
        tag=TAG, approve_label=LABEL_APPROVE,
    ),
]
