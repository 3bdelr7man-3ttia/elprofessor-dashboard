# -*- coding: utf-8 -*-
"""منتج «العقل» لمساهمات «مكتبة القانون العربي» — `library_contribution` (2026-11-09).

ما يراجعه: مساهمة من مستخدم (قانون/لائحة/قرار/حكم من أي حد، وكتاب من مؤلفه بس) استلمتها المنصة وتنتظر القرار.
  العقل يتأكد من ٤ حاجات (قانونية؟ الرقم مطابق؟ اتقسّمت كام مادة؟ عندنا نسخة؟) ويوصي «ضيفها» أو «ارفض» بسبب.
  أرقام المواد وعدد النسخ تيجي من الجسر (قسمة المنصة نفسها) مش من الموديل، وسطور البطاقة مبنية من الحقائق.
ما ينفذه: بعد اعتماد المؤسس بس ⇒ `POST /api/bridge/library/contributions/{id}/decision` (accept) والمنصة هي اللي بتدخّل المواد.
الرفض: بيعدّي على مسار الرفض العادي في اللوحة، وبعدها `on_reject` (خطّاف اختياري في العقد) بيبلّغ المنصة {decision:'reject', reason}
  علشان المساهم يشوف السبب وما تظهرش المساهمة تاني.
مقفول على «يسألني» دايمًا: إضافة نص للمكتبة بتغيّر إجابات «اسأل» لكل الناس.

قواعد الملف:
  * القراءة عبر `ctx.ns['_platform_proxy']`. ٤٠٤ (الجسر لسه مش منشور) ⇒ ولا هدف، مش عطل.
  * الكتابة الوحيدة: قرار واحد عبر `_v2_write` (نداء واحد، `by` من الفاعل).
"""
import json
import logging
import re

from brain2.contract import ApplyResult, Producer, SourceDown, Target

logger = logging.getLogger(__name__)

PRODUCER_ID = 'library_contribution'
LIST_LIMIT = 10
TITLE_MAX, PREVIEW_MAX, NAME_MAX, NUM_MAX = 150, 1200, 60, 40
FACTS_MAX_BYTES = 3900
TRACKS = {'eg-administrative-prosecution': 'النيابة الإدارية'}
LEGAL_KINDS = ('law', 'regulation', 'decision', 'ruling')
KINDS = LEGAL_KINDS + ('own_book', 'other')
LABEL_APPROVE = 'ضيفها للمكتبة'
LOCK_REASON = 'يسألك دائمًا لأن إضافة نص للمكتبة تغيّر إجابات «اسأل» لكل الناس.'
DEFAULT_REJECT_REASON = 'لم نتمكن من قبول هذه المساهمة في المكتبة.'
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')
_KEY_RE = re.compile(r'^\d{1,5}/\d{4}$')
DUPLICATES = ('none', 'older_copy', 'same')

_ROLE = (
    ' دورك: مراجع داخلي لمساهمة نص للمكتبة. «اسأل» لا يجيب إلا في القانون، فتحقق مما يلي من الحقائق المعطاة وحدها '
    '(العنوان، الرقم، المعاينة preview، عدد المواد articles_found، والمواد الموجودة عندنا existing_articles): '
    'is_legal: هل المعاينة نص قانون أو لائحة أو قرار أو حكم (وليست مقالًا أو كتابًا أو مذكرة)؟ '
    'kind_ok: هل النوع المختار kind مناسب لما في المعاينة؟ '
    'is_book: هل المعاينة كتاب أو مؤلَّف شرح (وليست نصًا رسميًا)؟ '
    'law_key: رقم القانون وسنته بصيغة N/YYYY كما ورد حرفيًا في العنوان أو الرقم أو المعاينة، أو "" إن لم يرد. لا تخترع رقمًا. '
    'number_matches: هل الرقم المكتوب يطابق ما في المعاينة؟ '
    'duplicate: none إن لم توجد عندنا مواد لهذا القانون، older_copy إن وُجدت (existing_articles أكبر من صفر) والمساهمة تبدو أحدث أو أكمل، '
    'same إن وُجدت وتبدو المساهمة نفس ما عندنا. '
    'recommend: accept أو reject. reject يلزمه reason_ar (جملة عربية قصيرة تظهر للمساهم، حتى ١٢٠ حرفًا، بلا أرقام لم ترد في الحقائق). '
    'كتاب المؤلف (kind=own_book) لا يُقسَّم لمواد، وأي kind آخر تبدو معاينته كتابًا فتوصيته reject. '
    'track: أحد المسارات المعروفة أو "" إن لم تعرفه. '
    'الشكل المطلوب: {"is_legal":true,"kind_ok":true,"is_book":false,"law_key":"","number_matches":true,'
    '"duplicate":"none|older_copy|same","recommend":"accept|reject","reason_ar":"…","track":""}'
)


def _fn(ctx, name):
    fn = ctx.ns.get(name)
    if not callable(fn):
        raise SourceDown(name)
    return fn


def _status(resp):
    if isinstance(resp, tuple) and len(resp) >= 2:
        return resp[1]
    return getattr(resp, 'status_code', None)


def _json(resp):
    if isinstance(resp, tuple):
        return resp[0] if isinstance(resp[0], dict) else {}
    try:
        return resp.get_json() or {}
    except Exception:   # noqa: BLE001
        return {}


def _list(ctx):
    path = '/api/bridge/library/contributions'
    try:
        resp = _fn(ctx, '_platform_proxy')('GET', path, params={'status': 'pending', 'limit': 50})
    except SourceDown:
        raise
    except Exception as exc:   # noqa: BLE001
        raise SourceDown('%s: %s' % (path, type(exc).__name__))
    st = _status(resp)
    if st == 404:
        return []
    if st != 200:
        raise SourceDown('%s: http %s' % (path, st))
    items = _json(resp).get('items')
    if not isinstance(items, list):
        raise SourceDown('%s: bad shape' % path)
    return [i for i in items if isinstance(i, dict)]


def _size(facts):
    return len(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def _fit(facts):
    """facts ≤ FACTS_MAX_BYTES: المعاينة هي اللي تتقصّ (الباقي حقائق قصيرة)."""
    while _size(facts) > FACTS_MAX_BYTES:
        v = facts.get('preview') or ''
        if len(v) <= 200:
            break
        facts['preview'] = v[: max(200, int(len(v) * 0.7))]
    return facts


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else 0


def _already_decided(ctx, cid):
    try:
        from brain2.engine import _models
        Item = _models(ctx.ns['db'])[0]
        return Item.query.filter(Item.producer == PRODUCER_ID, Item.target_ref == 'libc:' + cid,
                                 Item.status.in_(('approved', 'edited', 'applying', 'unknown'))).first() is not None
    except Exception:   # noqa: BLE001
        return False


def gather(ctx):
    out = []
    for it in _list(ctx):
        cid = str(it.get('id') or '').strip()
        title = str(it.get('title') or '').strip()
        kind = str(it.get('kind') or '')
        if not _ID_RE.match(cid) or not title or kind not in KINDS:
            continue
        if _already_decided(ctx, cid):
            continue
        track = str(it.get('suggested_track') or '')
        facts = {
            'kind': kind,
            'kind_other': str(it.get('kind_other') or '')[:60],
            'title': title[:TITLE_MAX],
            'law_number': str(it.get('law_number') or '')[:NUM_MAX],
            'law_key_guess': str(it.get('law_key_guess') or '')[:NUM_MAX],
            'articles_found': _int(it.get('articles_found')),
            'existing_articles': _int(it.get('existing_articles')),
            'suggested_track': track if track in TRACKS else '',
            'preview': str(it.get('preview') or '')[:PREVIEW_MAX],
            'contributor_name': str(it.get('contributor_name') or '')[:NAME_MAX],
        }
        _fit(facts)
        out.append(Target(ref='libc:' + cid, label=('مساهمة في المكتبة: ' + facts['title'])[:120], facts=facts,
                          meta={'contribution_id': cid}))
        if len(out) >= LIST_LIMIT:
            break
    return out


def prompt(target):
    try:
        from brain2.engine import SYSTEM_AR
    except Exception:   # noqa: BLE001
        SYSTEM_AR = ''
    user = 'راجع هذه المساهمة.\n\nالحقائق:\n%s' % json.dumps(target.facts, ensure_ascii=False, sort_keys=True)
    return (SYSTEM_AR or '') + _ROLE, user


def _card_text(facts, legal, number_ok, duplicate):
    """سطور البطاقة (مطابقة contrib-2): كلها من الحقائق والفحوص، مفيش رقم من الموديل."""
    lines = [facts.get('title') or '']
    lines.append('قانوني' if legal else 'مش واضح إنها نص قانوني')
    lines.append('الرقم مطابق' if number_ok else 'الرقم مش مطابق')
    n = _int(facts.get('articles_found'))
    if facts.get('kind') == 'own_book':
        lines.append('كتاب مؤلفه: بيتحفظ كمرجع من غير تقسيم لمواد')
    else:
        lines.append('اتقسّم %d مادة' % n if n else 'ما اتقسّمش لمواد')
    ex = _int(facts.get('existing_articles'))
    lines.append('مفيش نسخة' if duplicate == 'none'
                 else ('عندنا نسخة قديمة (%d مادة)' % ex if duplicate == 'older_copy' else 'عندنا نفس النسخة (%d مادة)' % ex))
    name = (facts.get('contributor_name') or '').strip()
    if name:
        lines.append('من «%s»' % name)
    return '\n'.join(lines)


def _literally_in(key, facts):
    hay = ' '.join(str(facts.get(k) or '') for k in ('title', 'law_number', 'preview'))
    try:
        from brain2.engine import norm_digits
        return norm_digits(key) in norm_digits(hay)
    except Exception:   # noqa: BLE001
        return key in hay


def validate(raw, target):
    if not isinstance(raw, dict):
        return None
    f = target.facts
    for k in ('is_legal', 'kind_ok', 'number_matches'):
        if not isinstance(raw.get(k), bool):
            return None
    is_book = raw.get('is_book') if isinstance(raw.get('is_book'), bool) else False
    duplicate, rec = raw.get('duplicate'), raw.get('recommend')
    if duplicate not in DUPLICATES or rec not in ('accept', 'reject'):
        return None
    law_key = raw.get('law_key') if isinstance(raw.get('law_key'), str) else None
    if law_key is None:
        return None
    law_key = law_key.strip()
    if law_key and (not _KEY_RE.match(law_key) or not _literally_in(law_key, f)):
        return None                      # رقم مخترع مش موجود في النص أو العنوان
    track = raw.get('track') if isinstance(raw.get('track'), str) else ''
    if track and track not in TRACKS:
        return None
    reason = raw.get('reason_ar') if isinstance(raw.get('reason_ar'), str) else ''
    reason = reason.strip()
    if len(reason) > 160:
        return None
    if rec == 'reject' and not reason:
        return None
    # النسخ الموجودة حقيقة من الجسر: الموديل ما يخترعش «مفيش نسخة» ولا «عندنا نسخة».
    ex = _int(f.get('existing_articles'))
    if (ex == 0) != (duplicate == 'none'):
        return None
    if rec == 'accept':
        if not (raw['is_legal'] and raw['kind_ok']):
            return None
        if is_book and f.get('kind') != 'own_book':
            return None                  # كتاب مش من مؤلفه ⇒ مفيش قبول
        if f.get('kind') not in KINDS or f.get('kind') == 'other':
            return None
        if f.get('kind') in LEGAL_KINDS and not _int(f.get('articles_found')):
            return None                  # نص قانوني ما اتقسّمش لمواد ⇒ مش جاهز للقبول
    if f.get('kind') == 'own_book':
        track, law_key = '', ''          # الكتاب بيتحفظ كمرجع بس
    elif not track:
        track = f.get('suggested_track') or ''
    return {'text': _card_text(f, raw['is_legal'], raw['number_matches'], duplicate),
            'why': (reason or 'مراجعة العقل: سليمة')[:160], 'recommend': rec, 'track': track, 'law_key': law_key,
            'checks': {'is_legal': raw['is_legal'], 'number_matches': raw['number_matches'],
                       'duplicate': duplicate, 'articles_found': _int(f.get('articles_found'))},
            'approve_label': LABEL_APPROVE}


def template(target):
    """لو الذكاء وقع: نفس الفحوص محسوبة من الحقائق بس، والتوصية «ضيفها» لو اتقسّمت لمواد والنوع قانوني."""
    f = target.facts
    n, ex = _int(f.get('articles_found')), _int(f.get('existing_articles'))
    kind = f.get('kind')
    legal = n > 0
    duplicate = 'older_copy' if ex > 0 else 'none'
    if kind in LEGAL_KINDS and n > 0:
        rec, why = 'accept', 'فحص تلقائي: اتقسّمت لمواد، راجعها بنفسك'
    elif kind in LEGAL_KINDS:
        rec, why = 'reject', 'ما اتقسّمتش لمواد'
    else:
        rec, why = 'review', 'محتاجة مراجعتك بنفسك'
    key = f.get('law_key_guess') or ''
    return {'text': _card_text(f, legal, bool(key), duplicate), 'why': why, 'recommend': rec,
            'track': f.get('suggested_track') or '' if kind != 'own_book' else '',
            'law_key': key if kind != 'own_book' else '',
            'checks': {'is_legal': legal, 'number_matches': bool(key), 'duplicate': duplicate, 'articles_found': n},
            'approve_label': LABEL_APPROVE}


def _decision(ctx, target, payload, action):
    cid = (target.meta or {}).get('contribution_id') or ''
    if not _ID_RE.match(str(cid)):
        return None, ApplyResult(ok=False, error='تعذّر تحديد المساهمة')
    path = '/api/bridge/library/contributions/%s/decision' % cid
    resp = _fn(ctx, '_v2_write')('POST', path, payload, action, cid, {'via': 'brain'})
    ns = ctx.ns
    if ns['_resp_ok'](resp):
        return _json(resp), None
    js = ns['_proxy_json'](resp)
    err = js.get('error') if isinstance(js.get('error'), str) else ''
    if js.get('no_reply') is True:
        return None, ApplyResult(ok=False, no_reply=True, error=err)
    return None, ApplyResult(ok=False, error=err or 'تعذّر التنفيذ الآن')


def apply(ctx, body, target):
    body = body or {}
    track = body.get('track') if isinstance(body.get('track'), str) else ''
    if track not in TRACKS:
        track = ''
    law_key = body.get('law_key') if isinstance(body.get('law_key'), str) else ''
    if law_key and not _KEY_RE.match(law_key):
        law_key = ''
    if target.facts.get('kind') == 'own_book':
        track, law_key = '', ''
    payload = {'decision': 'accept', 'track': track, 'law_key': law_key, 'by': str(ctx.actor)[:120]}
    js, err = _decision(ctx, target, payload, 'library.contribution_accept')
    if err is not None:
        return err
    n = _int((js or {}).get('articles_added')) if isinstance(js, dict) else 0
    line = 'اتضافت للمكتبة (%d مادة)' % n if n else 'اتقبلت وحُفظت في المكتبة'
    return ApplyResult(ok=True, info={'articles_added': n, 'line': line})


def on_reject(ctx, target, reason=''):
    """خطّاف الرفض (اختياري في العقد): بيبلّغ المنصة بالرفض وسببه. أي فشل ⇒ ApplyResult(ok=False) والمسار ما يوقعش."""
    reason = (reason or '').strip()[:300] or DEFAULT_REJECT_REASON
    payload = {'decision': 'reject', 'reason': reason, 'by': str(ctx.actor)[:120]}
    _, err = _decision(ctx, target, payload, 'library.contribution_reject')
    return err if err is not None else ApplyResult(ok=True)


PRODUCERS = [
    Producer(
        id=PRODUCER_ID, section='home', kind='draft',
        label='مساهمات «مكتبة القانون العربي»',
        sentence='عندما يرفع مستخدم قانونًا أو لائحة أو قرارًا أو حكمًا (أو كتابًا من تأليفه)، يراجعه العقل: قانوني؟ الرقم مطابق؟ كام مادة؟ عندنا نسخة؟ والإضافة للمكتبة لا تتم إلا باعتمادك.',
        lock_reason=LOCK_REASON, may_run_alone=False, default_mode='ask', per_run_cap=5,
        gather=gather, prompt=prompt, validate=validate, template=template, apply=apply, on_reject=on_reject,
        tag='مساهمة في المكتبة', approve_label=LABEL_APPROVE,
    ),
]
