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
DISC_MAX_MSGS, DISC_MSG_MAX = 4, 300      # نقاش المصحِّح مع المراجِع: آخر ٤ رسايل، كل واحدة ≤٣٠٠ حرف
FACTS_MAX_BYTES = 3900
# ‏`general` = أي سؤال برّه تخصص له قاعدة مواد (المنصة: `detect_track(q) or corpus.GENERAL`).
# ⛔ (2026-11-13) كان مش هنا ⇒ كل «عندي إضافة» على سؤال عام أو قطاع خاص كانت بتتشال بصمت ولا توصل المؤسس.
TRACKS = {'eg-administrative-prosecution': 'النيابة الإدارية', 'general': 'عام'}
LABEL_APPROVE = 'اعتمده مصدرًا لـ«اسأل»'
LOCK_REASON = 'يسألك دائمًا لأن التصحيح المعتمد يغيّر إجابات «اسأل» لكل الناس.'
_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,80}$')

VERDICTS = {'agrees': 'يتّفق مع النص', 'contradicts': 'يخالف النص', 'no_text': 'مفيش نص يحسم'}
_ROLE = (
    ' دورك: مراجع داخلي. مستخدم متخصص قال إن إجابة «اسأل» فيها غلط وكتب الصح (correction). '
    'قارن كلامه بالمواد المعطاة في articles وحدها (إن وُجدت)، ولا تستعمل معلوماتك أنت عن القانون. '
    'في verdict اختر: agrees إن كانت مادة معطاة تقول ما يقوله صراحةً · contradicts إن كانت مادة معطاة تقول عكسه صراحةً · '
    'no_text إن لم تحسم المواد المعطاة المسألة (أو لم تُعطَ مواد). '
    'قد يوجد في discussion نقاش قصير بين المصحِّح (user) والمراجِع (critic): إن ذكر المصحِّح فيه سندًا '
    '(رقم مادة أو قانون أو حكم) فاعتبره في المقارنة مع articles، لكنه لا يُغني عن نص معطى في articles: '
    'سنده المذكور لا يجعلك تحكم agrees إلا إذا أيّدته مادة معطاة. '
    'في why جملة واحدة تذكر المرجع بين المعقوفين كما ورد في articles إن وُجد. '
    'في text صغ كلام المصحِّح «ملاحظة خبير» واضحة في جملة إلى ثلاث جمل (حتى ٦٠٠ حرف) من كلامه وحده: '
    'لا تضف معلومة ولا رقمًا ليس في كلامه. '
    'وفي article_refs ضع أرقام المواد والقوانين كما وردت حرفيًا في تصحيحه أو في رسائله هو في النقاش (ليس في ردود المراجِع)، أو قائمة فارغة. '
    'وأضف points: من ٢ إلى ٤ نقط قصيرة (حتى ١٠٠ حرف للنقطة) تقول ما راجعته، كل نقطة {"ok":true|false,"text":"…"}: ok=true لما تحقّق وok=false لما نقص أو اختلف. '
    'الشكل المطلوب: {"verdict":"agrees|contradicts|no_text","why":"…","text":"…","article_refs":["…"],"points":[{"ok":true,"text":"…"}]}'
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
    """facts ≤ FACTS_MAX_BYTES: نقصّ الإجابة الغلط الأول، وبعدها النقاش (يتقلّص لرسالة قصيرة أو يختفي)،
    وبعدها نصوص المواد، وآخرًا التصحيح. المواد أهم من النقاش: من غيرها المراجعة تبقى «مفيش نص يحسم»."""
    for key, floor in (('wrong_answer', 200), ('discussion', 0), ('articles', 0), ('correction', 300)):
        while _size(facts) > FACTS_MAX_BYTES:
            if key == 'discussion':
                disc = facts.get('discussion') or []
                if not disc:
                    break
                if len(disc) > 1:
                    disc.pop(0)                 # الأقدم الأول
                elif len(disc[0]['text']) > 80:
                    disc[0]['text'] = disc[0]['text'][:80]
                else:
                    facts.pop('discussion', None)
                continue
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


def _discussion(raw):
    """آخر ٤ رسايل من خيط النقاش (لو الجسر رجّعه)، كل واحدة مقصوصة. شكل غير مفهوم ⇒ لا نقاش."""
    if not isinstance(raw, list):
        return []
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        text = str(m.get('text') or '').strip()
        role = m.get('role')
        if text and role in ('user', 'critic'):
            out.append({'role': role, 'text': text[:DISC_MSG_MAX]})
    return out[-DISC_MAX_MSGS:]


def _already_decided(ctx, fid):
    """اتعتمد/اتنفّذ قبل كده لنفس التصحيح؟ (نمنع بطاقة تانية بعد نقاش جديد ⇒ تصحيح مكرر في «اسأل»)."""
    try:
        from brain2.engine import _models
        Item = _models(ctx.ns['db'])[0]
        return Item.query.filter(Item.producer == PRODUCER_ID, Item.target_ref == 'askfb:' + fid,
                                 Item.status.in_(('approved', 'edited', 'applying', 'unknown', 'rejected'))).first() is not None
    except Exception:   # noqa: BLE001
        return False


def gather(ctx):
    out = []
    for it in _list(ctx):
        fid = str(it.get('id') or '').strip()
        corr = str(it.get('correction') or '').strip()
        track = str(it.get('track') or '')
        if not _ID_RE.match(fid) or len(corr) < 10 or track not in TRACKS:
            continue
        if _already_decided(ctx, fid):
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
        disc = _discussion(it.get('discussion'))
        if disc:
            facts['discussion'] = disc
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


def _refs_source(facts):
    """النص اللي المراجع تتطابق معاه: التصحيح + رسايل المصحِّح (user) في النقاش. ردود المراجِع (critic) خارج."""
    parts = [facts.get('correction') or '']
    for m in facts.get('discussion') or []:
        if isinstance(m, dict) and m.get('role') == 'user':
            parts.append(str(m.get('text') or ''))
    return '\n'.join(parts)


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


def _numbers_from_corrector(text, facts):
    """كل رقم في الصياغة لازم يكون في كلام المصحِّح (التصحيح + رسايله)، مش في رد المراجِع."""
    try:
        from brain2.engine import norm_digits
    except Exception:   # noqa: BLE001
        return True
    src = norm_digits(_refs_source(facts))
    return all(run in src for run in re.findall(r'\d+', norm_digits(text)))


def validate(raw, target):
    if not isinstance(raw, dict):
        return None
    text = raw.get('text')
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > TEXT_MAX:
        return None
    refs = _refs_ok(raw.get('article_refs') or [], _refs_source(target.facts))
    if refs is None:
        return None
    if not _numbers_from_corrector(text, target.facts):
        return None
    verdict = raw.get('verdict')
    if verdict not in VERDICTS:
        return None
    if verdict != 'no_text' and not target.facts.get('articles'):
        return None                       # حكم «يتّفق/يخالف» من غير مواد معطاة = من ذاكرة الموديل
    why = raw.get('why') if isinstance(raw.get('why'), str) else ''
    body = {'text': text.strip(), 'article_refs': refs, 'verdict': verdict,
            'why': (VERDICTS[verdict] + (': ' + why.strip() if why.strip() else ''))[:160],
            'approve_label': LABEL_APPROVE}
    try:      # R24 م٣: «راجعت…» على البطاقة (اختياري: لو مش سليم المراجعة تفضل صالحة من غيره)
        from brain2.engine import safe_points
        pts = safe_points(raw.get('points'), target.facts)
    except Exception:   # noqa: BLE001
        pts = None
    if pts:
        body['points'] = pts
    return body


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
        id=PRODUCER_ID, section='content', kind='draft',
        label='تصحيحات الخبراء لإجابات «اسأل»',
        sentence='عندما يقول متخصص إن إجابة «اسأل» فيها غلط ويكتب الصح، يقارنه العقل بالنص ويوصي، والتصحيح لا يصل «اسأل» إلا باعتمادك.',
        lock_reason=LOCK_REASON, may_run_alone=False, default_mode='ask', per_run_cap=5,
        gather=gather, prompt=prompt, validate=validate, template=template, apply=apply,
        tag='تصحيح «اسأل»', approve_label=LABEL_APPROVE,
    ),
]
