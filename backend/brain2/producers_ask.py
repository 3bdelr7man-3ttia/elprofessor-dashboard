# -*- coding: utf-8 -*-
"""منتج «العقل» لتصحيحات «اسأل» — `ask_correction` («دقة اسأل» 2026-11-09).

ما يراجعه: تقييمات «✗ فيها غلط + إيه الصح؟» تحت إجابات «اسأل» في تخصص عنده قاعدة نصوص (النيابة الإدارية النهارده).
ما يكتبه: مراجعة داخلية للتصحيح (رأي خبير داخلي): يقارنه بأقرب مواد من قاعدة النصوص ويوصي —
  «يتّفق مع النص» ⇒ اعتمده · «يخالف النص» ⇒ ارفضه أو راجعه · «مفيش نص يحسم» ⇒ يستاهل يتعرض على خبرائنا كموضوع —
  + صياغة نظيفة للتصحيح كـ«ملاحظة خبير» من كلام المصحِّح وحده (ولا معلومة ولا رقم من عند العقل).
  ⛔ التصحيح ده **مش** بيتبعت لخبير (اللي بيتبعت للخبراء هو الملفات)؛ ده تعليم لـ«اسأل»، والقرار للمؤسس.
ما ينفذه: بعد اعتماد المؤسس بس ⇒ التصحيح يتكتب على المنصة (`POST /api/bridge/ask/corrections`) ويبقى مصدر يرجعله «اسأل».
مقفول على «يسألني» دايمًا: تصحيح غلط بيعلّم «اسأل» الغلط لكل الناس.

قواعد الملف:
  * القراءة عبر `ctx.ns['_platform_proxy']` وقت النداء. ٤٠٤ (الجسر لسه مش منشور) ⇒ ولا هدف، مش عطل.
  * facts ما فيهاش أي بيانات شخصية للسائل (الجسر نفسه ما بيبعتهاش).
  * الكتابة الوحيدة: تصحيح واحد عبر `_v2_write` (نداء واحد، `by` من الفاعل).
"""
import json
import re

from brain2.contract import ApplyResult, Producer, SourceDown, Target

PRODUCER_ID = 'ask_correction'
LIST_LIMIT = 10
Q_MAX, A_MAX, C_MAX, TEXT_MAX, ART_MAX = 600, 900, 1200, 600, 700
FACTS_MAX_BYTES = 3900
TRACKS = {'eg-administrative-prosecution': 'النيابة الإدارية'}
LABEL_APPROVE = 'اعتمده مصدرًا لـ«اسأل»'
LOCK_REASON = 'يسألك دائمًا لأن التصحيح المعتمد يغيّر إجابات «اسأل» لكل الناس.'
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')

VERDICTS = {'agrees': 'يتّفق مع النص', 'contradicts': 'يخالف النص', 'no_text': 'مفيش نص يحسم'}
_ROLE = (
    ' دورك: مراجع داخلي. مستخدم متخصص قال إن إجابة «اسأل» فيها غلط وكتب الصح (correction). '
    'قارن كلامه بالمواد المعطاة في articles وحدها (إن وُجدت)، ولا تستعمل معلوماتك أنت عن القانون. '
    'في verdict اختر: agrees إن كانت مادة معطاة تقول ما يقوله صراحةً · contradicts إن كانت مادة معطاة تقول عكسه صراحةً · '
    'no_text إن لم تحسم المواد المعطاة المسألة (أو لم تُعطَ مواد). '
    'في why جملة واحدة تذكر المرجع بين المعقوفين كما ورد في articles إن وُجد. '
    'في text صغ كلام المصحِّح «ملاحظة خبير» واضحة في جملة إلى ثلاث جمل (حتى ٦٠٠ حرف) من كلامه وحده: '
    'لا تضف معلومة ولا رقمًا ليس في كلامه. '
    'وفي article_refs ضع أرقام المواد والقوانين كما وردت في كلام المصحِّح حرفيًا فقط، أو قائمة فارغة. '
    'الشكل المطلوب: {"verdict":"agrees|contradicts|no_text","why":"…","text":"…","article_refs":["…"]}'
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
    path = '/api/bridge/ask/feedback'
    try:
        resp = _fn(ctx, '_platform_proxy')('GET', path, params={'verdict': 'wrong', 'limit': 50})
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
    """أقرب ٣ مواد من قاعدة النصوص (نفس بحث «اسأل»). أي عطل ⇒ ولا مادة (المراجعة تقول «مفيش نص يحسم»)."""
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
    """facts ≤ FACTS_MAX_BYTES: نقصّ الإجابة الغلط الأول، وبعدها نصوص المواد، وبعدها التصحيح."""
    for key, floor in (('wrong_answer', 200), ('articles', 0), ('correction', 300)):
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
        fid = str(it.get('id') or '').strip()
        corr = str(it.get('correction') or '').strip()
        track = str(it.get('track') or '')
        if not _ID_RE.match(fid) or len(corr) < 10 or track not in TRACKS:
            continue
        facts = {
            'track': TRACKS[track],
            'question': str(it.get('question') or '')[:Q_MAX],
            'wrong_answer': str(it.get('answer') or '')[:A_MAX],
            'correction': corr[:C_MAX],
            'role': str(it.get('user_role') or '')[:40],
        }
        arts = _articles(ctx, track, facts['question'] + ' ' + facts['correction'])
        if arts:
            facts['articles'] = arts
        _fit(facts)
        out.append(Target(ref='askfb:' + fid, label=('تصحيح «اسأل»: ' + facts['question'])[:120], facts=facts,
                          meta={'feedback_id': fid, 'track': track}))
        if len(out) >= LIST_LIMIT:
            break
    return out


def prompt(target):
    try:
        from brain2.engine import SYSTEM_AR
    except Exception:   # noqa: BLE001
        SYSTEM_AR = ''
    user = 'صغ هذا التصحيح ملاحظة خبير.\n\nالحقائق:\n%s' % json.dumps(target.facts, ensure_ascii=False, sort_keys=True)
    return (SYSTEM_AR or '') + _ROLE, user


def _refs_ok(refs, correction):
    if not isinstance(refs, list) or len(refs) > 10:
        return None
    out = []
    for r in refs:
        if not isinstance(r, str) or not r.strip() or len(r) > 60:
            return None
        if r.strip() not in correction:      # المرجع لازم يكون حرفيًا من كلام المصحِّح
            return None
        out.append(r.strip())
    return out


def validate(raw, target):
    if not isinstance(raw, dict):
        return None
    text = raw.get('text')
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > TEXT_MAX:
        return None
    refs = _refs_ok(raw.get('article_refs') or [], target.facts.get('correction') or '')
    if refs is None:
        return None
    verdict = raw.get('verdict')
    if verdict not in VERDICTS:
        return None
    if verdict != 'no_text' and not target.facts.get('articles'):
        return None                       # حكم «يتّفق/يخالف» من غير مواد معطاة = من ذاكرة الموديل
    why = raw.get('why') if isinstance(raw.get('why'), str) else ''
    return {'text': text.strip(), 'article_refs': refs, 'verdict': verdict,
            'why': (VERDICTS[verdict] + (': ' + why.strip() if why.strip() else ''))[:160],
            'approve_label': LABEL_APPROVE}


def template(target):
    """لو الذكاء وقع: كلام المصحِّح نفسه (مقصوص) — المؤسس يعدّله قبل الاعتماد."""
    corr = (target.facts.get('correction') or '').strip()
    if not corr:
        return None
    return {'text': corr[:TEXT_MAX], 'article_refs': [], 'verdict': 'no_text',
            'why': 'لم تتم المقارنة بالنص — راجعه بنفسك', 'approve_label': LABEL_APPROVE}


def apply(ctx, body, target):
    body = body or {}
    meta = target.meta or {}
    fid, track = meta.get('feedback_id') or '', meta.get('track') or ''
    if not _ID_RE.match(str(fid)) or track not in TRACKS:
        return ApplyResult(ok=False, error='تعذّر تحديد التصحيح')
    text = str(body.get('text') or '').strip()
    if len(text) < 10:
        return ApplyResult(ok=False, error='اكتب نص التصحيح قبل الاعتماد')
    refs = body.get('article_refs') if isinstance(body.get('article_refs'), list) else []
    payload = {'track': track, 'question': target.facts.get('question') or '', 'approved_text': text[:4000],
               'article_refs': [str(r)[:60] for r in refs][:10], 'feedback_id': fid}
    resp = _fn(ctx, '_v2_write')('POST', '/api/bridge/ask/corrections', payload, 'ask.correction_approve', fid,
                                 {'via': 'brain'})
    ns = ctx.ns
    if ns['_resp_ok'](resp):
        return ApplyResult(ok=True, info={'feedback_id': fid, 'line': 'اتعتمد التصحيح، و«اسأل» هيرجعله من دلوقتي'})
    js = ns['_proxy_json'](resp)
    err = js.get('error') if isinstance(js.get('error'), str) else ''
    if js.get('no_reply') is True:
        return ApplyResult(ok=False, no_reply=True, error=err)
    return ApplyResult(ok=False, error=err or 'تعذّر التنفيذ الآن')


PRODUCERS = [
    Producer(
        id=PRODUCER_ID, section='home', kind='draft',
        label='تصحيحات الخبراء لإجابات «اسأل»',
        sentence='عندما يقول متخصص إن إجابة «اسأل» فيها غلط ويكتب الصح، يقارنه العقل بالنص ويوصي، والتصحيح لا يصل «اسأل» إلا باعتمادك.',
        lock_reason=LOCK_REASON, may_run_alone=False, default_mode='ask', per_run_cap=5,
        gather=gather, prompt=prompt, validate=validate, template=template, apply=apply,
        tag='تصحيح «اسأل»', approve_label=LABEL_APPROVE,
    ),
]
