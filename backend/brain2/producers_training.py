# -*- coding: utf-8 -*-
"""منتج «العقل» لـ«جلسة تدريب البروف» — `training_item` (2026-11-09).

ما يراجعه: بنود (سؤال/جواب أو تصحيح) علّمها خبير للمساعد في جلسة تدريب وتنتظر قرار المؤسس.
  العقل يقارن جواب الخبير ومصدره المذكور بأقرب مواد من قاعدة النصوص (إن وُجدت) ويقول:
  «بتتفق مع النص» · «بتخالف النص» · «مفيش نص يحسم». نص البطاقة مبني من الحقائق (مش من الموديل).
ما ينفذه: بعد اعتماد المؤسس بس ⇒ `POST /api/bridge/training/items/{id}/decision` (accept) والمنصة تكتب التصحيح لو لزم.
الرفض: على مسار الرفض العادي ثم `on_reject` ⇒ {decision:'reject', reason}.
مقفول على «يسألني» دائمًا: ما يتعلمه البروف من خبير يغيّر إجابات «اسأل» لكل الناس.

قواعد الملف:
  * القراءة عبر `ctx.ns['_platform_proxy']`. ٤٠٤ (الجسر لسه مش منشور) ⇒ ولا هدف، مش عطل.
  * الكتابة الوحيدة: قرار واحد عبر `_v2_write` (نداء واحد، `by` من الفاعل).
"""
import json
import re

from brain2.contract import ApplyResult, Producer, SourceDown, Target

PRODUCER_ID = 'training_item'
LIST_LIMIT = 10
Q_MAX, A_MAX, SRC_MAX, NAME_MAX, ART_MAX, NOTE_MAX = 600, 1200, 300, 80, 700, 200
FACTS_MAX_BYTES = 3900
TRACK = 'eg-administrative-prosecution'
TRACKS = {TRACK: 'النيابة الإدارية'}
LABEL_APPROVE = 'اعتمدها للبروف'
LOCK_REASON = 'يسألك دائمًا لأن ما يتعلمه البروف من الخبير يغيّر إجابات «اسأل» لكل الناس.'
DEFAULT_REJECT_REASON = 'لم نتمكن من اعتماد هذا البند في تدريب البروف.'
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')

VERDICTS = {'agrees': 'بتتفق مع النص', 'contradicts': 'بتخالف النص', 'no_text': 'مفيش نص يحسم'}
_ROLE = (
    ' دورك: مراجع داخلي. خبير علّم المساعد جوابًا (expert_answer) وقد يذكر مصدره (source). '
    'قارن جوابه ومصدره بالمواد المعطاة في articles وحدها (إن وُجدت)، ولا تستعمل معلوماتك أنت عن القانون. '
    'verdict: agrees إن كانت مادة معطاة تقول ما يقوله صراحةً · contradicts إن كانت مادة معطاة تقول عكسه صراحةً · '
    'no_text إن لم تحسم المواد المعطاة المسألة (أو لم تُعطَ مواد). '
    'article_refs: أرقام المواد أو القوانين كما وردت حرفيًا في كلام الخبير أو في مراجع articles، أو قائمة فارغة. '
    'note_ar: جملة عربية واحدة (حتى ٢٠٠ حرف) تشرح الحكم، بلا رقم لم يرد في الحقائق. '
    'الشكل المطلوب: {"verdict":"agrees|contradicts|no_text","article_refs":["…"],"note_ar":"…"}'
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
    path = '/api/bridge/training/items'
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


def _articles(ctx, track, text):
    """أقرب ٣ مواد من قاعدة النصوص. أي عطل ⇒ ولا مادة (الحكم «مفيش نص يحسم»)."""
    try:
        resp = _fn(ctx, '_platform_proxy')('GET', '/api/bridge/ask/articles/search',
                                           params={'track': track, 'q': text[:1400], 'limit': 3})
    except Exception:   # noqa: BLE001
        return []
    if _status(resp) != 200:
        return []
    out = []
    for it in _json(resp).get('items') or []:
        if isinstance(it, dict) and it.get('ref') and it.get('text'):
            out.append({'ref': str(it['ref'])[:60], 'text': str(it['text'])[:ART_MAX]})
    return out


def _size(facts):
    return len(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def _fit(facts):
    """facts ≤ FACTS_MAX_BYTES: نقصّ نصوص المواد الأول (الأطول)، وبعدها السؤال، وآخرًا جواب الخبير."""
    for key, floor in (('articles', 0), ('question', 150), ('expert_answer', 300)):
        while _size(facts) > FACTS_MAX_BYTES:
            if key == 'articles':
                arts = facts.get('articles') or []
                if not arts:
                    break
                longest = max(arts, key=lambda a: len(a['text']))
                if len(longest['text']) <= 150:
                    arts.pop()
                    if not arts:
                        facts.pop('articles', None)
                    continue
                longest['text'] = longest['text'][: int(len(longest['text']) * 0.7)]
            else:
                v = facts.get(key) or ''
                if len(v) <= floor:
                    break
                facts[key] = v[: max(floor, int(len(v) * 0.7))]
    return facts


def gather(ctx):
    out = []
    for it in _list(ctx):
        iid = str(it.get('id') or '').strip()
        question = str(it.get('question') or '').strip()
        answer = str(it.get('answer') or '').strip()
        if not _ID_RE.match(iid) or not question or not answer:
            continue
        spec = str(it.get('specialty') or '')
        facts = {
            'expert_name': str(it.get('expert_name') or '')[:NAME_MAX],
            'specialty_label': str(it.get('specialty_label') or '')[:NAME_MAX],
            'type': 'correction' if it.get('type') == 'correction' else 'qa',
            'question': question[:Q_MAX],
            'expert_answer': answer[:A_MAX],
            'source': str(it.get('source') or '').strip()[:SRC_MAX],
        }
        if spec in TRACKS:
            arts = _articles(ctx, spec, facts['question'] + ' ' + facts['expert_answer'])
            if arts:
                facts['articles'] = arts
        _fit(facts)
        out.append(Target(ref='trainitem:' + iid, label=('تدريب البروف: ' + facts['question'])[:120], facts=facts,
                          meta={'item_id': iid, 'track': spec if spec in TRACKS else ''}))
        if len(out) >= LIST_LIMIT:
            break
    return out


def prompt(target):
    try:
        from brain2.engine import SYSTEM_AR
    except Exception:   # noqa: BLE001
        SYSTEM_AR = ''
    user = 'قارن جواب الخبير بالنص.\n\nالحقائق:\n%s' % json.dumps(target.facts, ensure_ascii=False, sort_keys=True)
    return (SYSTEM_AR or '') + _ROLE, user


def _card(facts, verdict, note=''):
    head = 'من جلسة تدريب: %s' % (facts.get('expert_name') or 'خبير')
    if facts.get('specialty_label'):
        head += '، ' + facts['specialty_label']
    lines = [head, 'السؤال: ' + (facts.get('question') or ''), 'جواب الخبير: ' + (facts.get('expert_answer') or '')]
    if facts.get('source'):
        lines.append('المصدر: ' + facts['source'])
    lines.append(VERDICTS[verdict] + ((' — ' + note) if note else ''))
    return '\n'.join(lines)


def _expert_words(facts):
    return '\n'.join([facts.get('expert_answer') or '', facts.get('source') or ''])


def _refs_ok(refs, facts):
    if not isinstance(refs, list) or len(refs) > 10:
        return None
    allowed = _expert_words(facts) + '\n' + '\n'.join(a.get('ref', '') for a in facts.get('articles') or [])
    out = []
    for r in refs:
        if not isinstance(r, str) or not r.strip() or len(r) > 60:
            return None
        if r.strip() not in allowed:
            return None
        out.append(r.strip())
    return out


def _numbers_from_facts(text, facts):
    try:
        from brain2.engine import norm_digits
    except Exception:   # noqa: BLE001
        return True
    src = [_expert_words(facts), facts.get('question') or '']
    for a in facts.get('articles') or []:
        src += [a.get('ref', ''), a.get('text', '')]
    src = norm_digits('\n'.join(src))
    return all(run in src for run in re.findall(r'\d+', norm_digits(text)))


def validate(raw, target):
    if not isinstance(raw, dict):
        return None
    verdict = raw.get('verdict')
    if verdict not in VERDICTS:
        return None
    if verdict != 'no_text' and not target.facts.get('articles'):
        return None                       # حكم «يتفق/يخالف» من غير مواد معطاة = من ذاكرة الموديل
    refs = _refs_ok(raw.get('article_refs') or [], target.facts)
    if refs is None:
        return None
    note = raw.get('note_ar') if isinstance(raw.get('note_ar'), str) else ''
    note = note.strip()
    if len(note) > NOTE_MAX or not _numbers_from_facts(note, target.facts):
        return None
    return {'text': _card(target.facts, verdict, note), 'article_refs': refs, 'verdict': verdict,
            'why': VERDICTS[verdict], 'approve_label': LABEL_APPROVE}


def template(target):
    """لو الذكاء وقع: البند كما هو بحكم «مفيش نص يحسم» — المؤسس يقرر بنفسه."""
    f = target.facts
    if not f.get('question') or not f.get('expert_answer'):
        return None
    return {'text': _card(f, 'no_text'), 'article_refs': [], 'verdict': 'no_text',
            'why': 'لم تتم المقارنة بالنص — راجعه بنفسك', 'approve_label': LABEL_APPROVE}


def _decision(ctx, target, payload, action):
    iid = (target.meta or {}).get('item_id') or ''
    if not _ID_RE.match(str(iid)):
        return ApplyResult(ok=False, error='تعذّر تحديد البند')
    path = '/api/bridge/training/items/%s/decision' % iid
    resp = _fn(ctx, '_v2_write')('POST', path, payload, action, iid, {'via': 'brain'})
    ns = ctx.ns
    if ns['_resp_ok'](resp):
        return ApplyResult(ok=True, info={'item_id': iid, 'line': 'اتعتمدت، والبروف هيتعلمها' if payload['decision'] == 'accept'
                                          else 'اتبلّغ الرفض'})
    js = ns['_proxy_json'](resp)
    err = js.get('error') if isinstance(js.get('error'), str) else ''
    if js.get('no_reply') is True:
        return ApplyResult(ok=False, no_reply=True, error=err)
    return ApplyResult(ok=False, error=err or 'تعذّر التنفيذ الآن')


def apply(ctx, body, target):
    payload = {'decision': 'accept', 'by': str(ctx.actor)[:120]}
    if (target.meta or {}).get('track') == TRACK:
        payload['track'] = TRACK
    return _decision(ctx, target, payload, 'training.item_accept')


def on_reject(ctx, target, reason=''):
    """خطّاف الرفض: بيبلّغ المنصة بالرفض وسببه (مطلوب ≥٣ حروف). أي فشل ⇒ ok=False والمسار ما يوقعش."""
    reason = (reason or '').strip()[:300]
    if len(reason) < 3:
        reason = DEFAULT_REJECT_REASON
    return _decision(ctx, target, {'decision': 'reject', 'reason': reason, 'by': str(ctx.actor)[:120]},
                     'training.item_reject')


PRODUCERS = [
    Producer(
        id=PRODUCER_ID, section='home', kind='draft',
        label='بنود «جلسة تدريب البروف»',
        sentence='ما يعلّمه الخبراء للبروف في جلسة التدريب يقارنه العقل بالنص ويوصي، ولا يتعلمه البروف إلا باعتمادك.',
        lock_reason=LOCK_REASON, may_run_alone=False, default_mode='ask', per_run_cap=5,
        gather=gather, prompt=prompt, validate=validate, template=template, apply=apply, on_reject=on_reject,
        tag='تدريب البروف', approve_label=LABEL_APPROVE,
    ),
]
