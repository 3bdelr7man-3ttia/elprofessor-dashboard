# -*- coding: utf-8 -*-
"""منتجو «العقل» (ops) — SPEC docs/v2/brain2/SPEC.md §3.2 (P2).

١) `opinion`  — رأي العقل في بطاقة قرار. لا يُشغَّله المُشغِّل (gather يرجع [])؛ يُنادى من مسار `/opinion`
   عبر `opinion_target(kind, card_id, facts)`. نص فقط، لا apply، لا template (الواجهة تحتفظ بسطرها الثابت).
٢) `reply_draft` — مسودة رد على: رسالة عضو (المنصة) · رسالة من الموقع (محلية) · طلب تواصل (المنصة).

قرارات التصميم (للمحرّك والمسارات):
  • `reply_draft.gather` يقرأ كل مصدر على حدة. المصدر الفاشل يُسجَّل في القائمة العامة `last_source_errors`
    (تُفرَّغ وتُملأ في كل نداء، بنفس الكائن)، والمصادر السليمة ترجع أهدافها. تُرمى `SourceDown` فقط إن
    فشلت **كل** المصادر الثلاثة (فلا يُخزَّن شيء ولا يُحسب «لا شيء جديد»). من أراد التفاصيل ينادي
    `gather_with_errors(ctx)` فيأخذ `(targets, errors)` دون حالة مشتركة؛ كل خطأ `{'source','reason'}`.
  • `Target.meta['approve_label']` يحمل نص الزر الخاص بكل هدف (يتغيّر حسب المصدر)؛ و`Producer.approve_label`
    الافتراضي «أرسل الرد». على المحرّك/الواجهة تفضيل `meta['approve_label']` إن وُجد.
  • الإرسال لعضو: `POST /api/bridge/messages/<id>/reply {body, by, confirmed:true}`. الرد ٤٢٢ = المرسل زائر بلا
    حساب ⇒ `ok=False` بنص عربي (والصف يرجع «مقترح» فيُنسخ الرد يدويًا). لا ردّ/انقطاع (٥٠٢ و٥٠٤ أو استثناء) ⇒
    `no_reply=True` (الحالة مجهولة، لا إعادة إرسال تلقائية).
  • رد الموقع لا يُرسَل بالبريد أبدًا: يُحفظ ويُنسخ فقط (كما `admin_message_reply`) ولا نص هنا يقول غير ذلك.
  • الـprompt لا يحمل `meta` ولا بريدًا ولا هاتفًا؛ كل نص يمرّ على `_scrub` عند الجمع وعند بناء الـprompt.
"""
import datetime
import logging
import re

from brain2.contract import ApplyResult, Producer, SourceDown, Target

logger = logging.getLogger(__name__)

# نسخة حرفية من engine.SYSTEM_AR (SPEC §3.1) — محلية كي لا يعتمد هذا الملف على engine.py.
SYSTEM_AR = ('اكتب بالعربية الفصحى البسيطة، بصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا، لجمهور دولي، بلا مصطلحات تقنية. '
             'استعمل الحقائق المعطاة وحدها؛ لا تخترع رقمًا ولا اسمًا ولا تاريخًا ولا وعدًا، ولا تقل إن شيئًا نُفِّذ. '
             'أعد JSON صالحًا فقط بالشكل المطلوب.')

# ---------------------------------------------------------------- تنظيف النصوص

_ARABIC_DIGITS = {ord(c): str(i) for i, c in enumerate('٠١٢٣٤٥٦٧٨٩')}
_ARABIC_DIGITS.update({ord(c): str(i) for i, c in enumerate('۰۱۲۳۴۵۶۷۸۹')})
_EMAIL_RE = re.compile(r'[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+', re.UNICODE)
_PHONE_RE = re.compile(r'(?<![\w])\+?[\d٠-٩۰-۹][\d٠-٩۰-۹\s\-().]{5,}[\d٠-٩۰-۹]')
_WS_RE = re.compile(r'\s+')
_ID_RE = re.compile(r'^[A-Za-z0-9_\-]{1,64}$')


def _phone_sub(m):
    digits = re.sub(r'\D', '', m.group(0).translate(_ARABIC_DIGITS))
    return '[رقم]' if len(digits) >= 7 else m.group(0)


def _scrub(text, limit):
    """نص بلا بريد ولا هاتف، مسافاته مضغوطة، مقصوص عند `limit`."""
    if text is None:
        return ''
    t = _EMAIL_RE.sub('[بريد]', str(text))
    t = _PHONE_RE.sub(_phone_sub, t)
    t = _WS_RE.sub(' ', t).strip()
    return t[:limit]


# ---------------------------------------------------------------- A) opinion

MONEY_KINDS = ('payout', 'manual_payment', 'stuck_payment', 'unactivated', 'legacy', 'file_attention', 'dispute')
DECISION_KINDS = ('trainer', 'join', 'pending_user', 'book_offer', 'book', 'creative', 'topic', 'program')
INFO_KINDS = ('review', 'lead', 'message', 'open_message', 'course', 'live', 'verify', 'founding', 'other')
EXCLUDED_KINDS = ('file_waiting', 'file_late')   # يبقى فيها اختيار الخبير المبني على القواعد

OPINION_COMMON_KEYS = ('tag', 'age', 'sub', 'warn', 'reason', 'static_line', 'facts', 'money_text')
OPINION_MAX_FACTS_BYTES = 3072
OPINION_MAX_STR = 300
OPINION_MAX_LIST = 6

_REC_DECISION = ('approve', 'reject', 'open')
_REC_INFO = ('open', 'wait')

_ROLE_MONEY = 'اكتب رأيك نصًا فقط ولا توصِ بإجراء مالي؛ القرار للمؤسس وحده، ولا تقل إن مبلغًا حُوِّل أو سيُحوَّل أو أُعيد.'
_ROLE_DECISION = 'أنت تساعد المؤسس على قرار ينتظره؛ أوصِ باعتماد الطلب أو رفضه، أو بفتحه للمراجعة أولًا إن نقصت المعلومات.'
_ROLE_INFO = 'أنت تساعد المؤسس على بند لا يحتاج اعتمادًا مباشرًا؛ أوصِ بفتحه الآن أو بتأجيله.'


def _spec(role_ar, rec, extra_keys=()):
    return {'role_ar': role_ar, 'allowed_recommend': tuple(rec),
            'keys': tuple(OPINION_COMMON_KEYS) + tuple(extra_keys)}


OPINION_SPECS = {
    # أموال: نص فقط، لا توصية تُحوَّل إلى زر
    'payout': _spec('اكتب رأيك في طلب تحويل أرباح: ما الذي يجب أن يتأكد منه المؤسس قبل التحويل. ' + _ROLE_MONEY, (),
                    ('method', 'dispute_check', 'fx_alert')),
    'manual_payment': _spec('اكتب رأيك في إيصال تحويل يدوي ينتظر التأكيد. ' + _ROLE_MONEY, ()),
    'stuck_payment': _spec('اكتب رأيك في دفعة بالبطاقة لم تكتمل. ' + _ROLE_MONEY, ()),
    'unactivated': _spec('اكتب رأيك في دفعة وصلت ولم يصل ملفها إلى قائمة التوزيع. ' + _ROLE_MONEY, ()),
    'legacy': _spec('اكتب رأيك في استشارة قديمة أموالها تنتظر قرارًا. ' + _ROLE_MONEY, ()),
    'file_attention': _spec('اكتب رأيك في ملف أمواله متوقفة. ' + _ROLE_MONEY, ()),
    'dispute': _spec('لخّص الطرفين بإنصاف ثم أوصِ', (), ('objection', 'expert_reply', 'hours_held')),
    # قرارات
    'trainer': _spec('اكتب رأيك في طلب مدرّب جديد. ' + _ROLE_DECISION, _REC_DECISION,
                     ('headline', 'specialty', 'years', 'attachments')),
    'join': _spec('اكتب رأيك في طلب انضمام لتقديم خدمة؛ القبول ينشر الاسم على المنصة. ' + _ROLE_DECISION, _REC_DECISION,
                  ('service', 'licensed', 'licence_missing')),
    'pending_user': _spec('اكتب رأيك في زائر مسجَّل ينتظر فتح المنصة له. ' + _ROLE_DECISION, _REC_DECISION),
    'book_offer': _spec('اكتب رأيك في عرض كتاب ينتظر اعتماد الأسعار. ' + _ROLE_DECISION, _REC_DECISION,
                        ('type', 'suggested_price', 'price_note')),
    'book': _spec('اكتب رأيك في كتاب ينتظر المراجعة. ' + _ROLE_DECISION, _REC_DECISION),
    'creative': _spec('اكتب رأيك في عمل إبداعي ينتظر المراجعة. ' + _ROLE_DECISION, _REC_DECISION),
    'topic': _spec('اكتب رأيك في موضوع ينتظر المراجعة. ' + _ROLE_DECISION, _REC_DECISION),
    'program': _spec('اكتب رأيك في طلب برنامج. ' + _ROLE_DECISION, _REC_DECISION),
    # معلومات
    'review': _spec('اكتب رأيك في أول رأي لخبير جديد ينتظر مراجعة المؤسس. ' + _ROLE_INFO, _REC_INFO),
    'lead': _spec('اكتب رأيك في طلب تواصل من عميل محتمل. ' + _ROLE_INFO, _REC_INFO, ('body', 'topic')),
    'message': _spec('اكتب رأيك في رسالة وصلت. ' + _ROLE_INFO, _REC_INFO, ('body', 'topic')),
    'open_message': _spec('اكتب رأيك في رسالة مفتوحة تنتظر الرد. ' + _ROLE_INFO, _REC_INFO),
    'course': _spec('اكتب رأيك في دورة تنتظر الاعتماد. ' + _ROLE_INFO, _REC_INFO),
    'live': _spec('اكتب رأيك في دورة حيّة لم يكتمل حجزها. ' + _ROLE_INFO, _REC_INFO),
    'verify': _spec('اكتب رأيك في طلب توثيق بلا خبير. ' + _ROLE_INFO, _REC_INFO),
    'founding': _spec('اكتب رأيك في طلب خبير مؤسس. ' + _ROLE_INFO, _REC_INFO),
    'other': _spec('اكتب رأيك في بند ينتظر قرار المؤسس. ' + _ROLE_INFO, _REC_INFO),
}

_OPINION_LABELS = {
    'tag': 'الشارة', 'age': 'منذ', 'sub': 'التفاصيل', 'warn': 'تنبيه', 'reason': 'السبب الظاهر',
    'static_line': 'السطر الحالي', 'facts': 'بيانات البطاقة', 'money_text': 'المبلغ',
    'objection': 'اعتراض صاحب الطلب', 'expert_reply': 'رد الخبير', 'hours_held': 'ساعات الحجز',
    'headline': 'العنوان', 'specialty': 'التخصص', 'years': 'الخبرة', 'attachments': 'المرفقات',
    'method': 'الطريقة', 'dispute_check': 'فحص النزاعات', 'fx_alert': 'تنبيه العملة',
    'type': 'النوع', 'suggested_price': 'السعر المقترح', 'price_note': 'ملاحظة السعر',
    'service': 'الخدمة', 'licensed': 'مرخّص', 'licence_missing': 'رقم القيد ناقص',
    'body': 'نص الرسالة', 'topic': 'الموضوع',
}


def opinion_supported(kind):
    return kind in OPINION_SPECS


def _clean_value(v, depth=0):
    """قيمة حقيقة نظيفة: نص ≤300 بلا بريد/هاتف · قائمة ≤6 · قاموس صغير (عمق ≤2) · رقم/منطقي كما هو."""
    if v is None:
        return None
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = _scrub(v, OPINION_MAX_STR)
        return s or None
    if isinstance(v, (list, tuple)):
        out = [x for x in (_clean_value(i, depth + 1) for i in list(v)[:OPINION_MAX_LIST]) if x is not None]
        return out or None
    if isinstance(v, dict) and depth < 2:
        out = {}
        for k in list(v.keys())[:OPINION_MAX_LIST]:
            cv = _clean_value(v[k], depth + 1)
            if cv is not None:
                out[_scrub(k, 40)] = cv
        return out or None
    return None


def clean_opinion_facts(kind, facts):
    """يُبقي المفاتيح المسموحة لهذا النوع فقط ويُنظّف قيمها. نوع غير مدعوم ⇒ ValueError('not_supported')."""
    spec = OPINION_SPECS.get(kind)
    if spec is None:
        raise ValueError('not_supported')
    facts = facts if isinstance(facts, dict) else {}
    out = {}
    for k in spec['keys']:
        if k in facts:
            cv = _clean_value(facts[k])
            if cv is not None:
                out[k] = cv
    return out


def opinion_target(kind, card_id, facts):
    """Target لرأي بطاقة. ref = 'card:<card_id>' و`meta['kind']` يحمل النوع. نوع غير مدعوم ⇒ ValueError('not_supported')."""
    cleaned = clean_opinion_facts(kind, facts)
    card_id = str(card_id or '')
    ref = ('card:' + card_id)[:200]
    label = _scrub(cleaned.get('tag') or kind, 120) if isinstance(cleaned.get('tag'), str) else kind
    return Target(ref=ref, label=label[:120], facts=cleaned, meta={'kind': kind, 'card_id': card_id})


def _kind_of(target):
    k = (target.meta or {}).get('kind')
    if k in OPINION_SPECS:
        return k
    ref = str(target.ref or '')
    if ref.startswith('card:'):
        k = ref[5:].split('|', 1)[0]
        if k in OPINION_SPECS:
            return k
    return None


def _fmt_fact(v):
    if isinstance(v, bool):
        return 'نعم' if v else 'لا'
    if isinstance(v, list):
        parts = []
        for i in v:
            if isinstance(i, dict):
                if 'k' in i and 'v' in i:
                    parts.append('%s: %s' % (i.get('k'), i.get('v')))
                else:
                    parts.append('، '.join('%s: %s' % (a, b) for a, b in i.items()))
            else:
                parts.append(str(i))
        return ' | '.join(parts)
    if isinstance(v, dict):
        return '، '.join('%s: %s' % (a, b) for a, b in v.items())
    return str(v)


def _opinion_prompt(target):
    kind = _kind_of(target)
    spec = OPINION_SPECS.get(kind) if kind else None
    if spec is None:
        raise ValueError('not_supported')
    rec = spec['allowed_recommend']
    if rec:
        schema = '{"opinion":"رأيك في جملتين على الأكثر (حتى ٢٢٠ حرفًا)","recommend":"%s","why":"سبب التوصية في جملة (حتى ١٦٠ حرفًا)"}' % '|'.join(rec)
        rec_help = ('معنى التوصية: approve = اعتماد الطلب أو قبوله · reject = رفضه · open = فتحه ومراجعته أولًا · wait = تأجيله. '
                    'اختر قيمة واحدة من المسموح فقط.')
    else:
        schema = '{"opinion":"رأيك في جملتين على الأكثر (حتى ٢٢٠ حرفًا)","recommend":"","why":"سبب رأيك في جملة (حتى ١٦٠ حرفًا)"}'
        rec_help = 'اترك recommend نصًا فارغًا؛ لا توصية بإجراء هنا.'
    system = '%s\n%s\nالشكل المطلوب: %s\n%s' % (SYSTEM_AR, spec['role_ar'], schema, rec_help)
    lines = []
    for k in spec['keys']:
        if k in target.facts:
            lines.append('%s: %s' % (_OPINION_LABELS.get(k, k), _scrub(_fmt_fact(target.facts[k]), 600)))
    user = 'بيانات البطاقة:\n' + ('\n'.join(lines) if lines else 'لا بيانات إضافية.')
    return system, user


def _opinion_validate(raw, target):
    """{"opinion","recommend","why"} ⇒ جسم {'text','opinion','recommend','why'} أو None.
    'text' = نفس opinion (يفحصه المحرّك). أنواع الأموال: recommend يُسقَط دائمًا ولا يُحوَّل إلى زر."""
    if not isinstance(raw, dict):
        return None
    kind = _kind_of(target)
    spec = OPINION_SPECS.get(kind) if kind else None
    if spec is None:
        return None
    op, why = raw.get('opinion'), raw.get('why')
    if not isinstance(op, str) or not isinstance(why, str):
        return None
    op, why = op.strip(), why.strip()
    if not op or not why or len(op) > 220 or len(why) > 160:
        return None
    allowed = spec['allowed_recommend']
    rec = raw.get('recommend')
    if allowed:
        if not isinstance(rec, str) or rec.strip() not in allowed:
            return None
        rec = rec.strip()
    else:
        rec = ''
    return {'text': op, 'opinion': op, 'recommend': rec, 'why': why}


def _opinion_gather(ctx):
    return []   # يُنادى من /opinion لا من المُشغِّل


# ---------------------------------------------------------------- B) reply_draft

SRC_PMSG, SRC_SMSG, SRC_LEAD = 'pmsg', 'smsg', 'lead'
LABEL_SEND = 'أرسل الرد'
LABEL_COPY = 'انسخ الرد'
LABEL_SAVE_COPY = 'احفظ الرد وانسخه'
LABEL_COPY_RESOLVE = 'انسخ الرسالة وعلّمه تم'
BODY_MAX = 1200
REPLY_MAX = 700
GATHER_LIMIT = 20

# أخطاء المصادر في آخر gather (نفس الكائن دائمًا — يُفرَّغ ويُملأ في مكانه).
last_source_errors = []


def _proxy(ctx):
    fn = ctx.ns.get('_platform_proxy')
    if not callable(fn):
        raise SourceDown('platform proxy missing')
    return fn


def _status_of(resp):
    try:
        if isinstance(resp, tuple):
            return int(resp[1])
        return int(getattr(resp, 'status_code', 200))
    except Exception:
        return 0


def _is_ok(ctx, resp):
    fn = ctx.ns.get('_resp_ok')
    if callable(fn):
        try:
            return bool(fn(resp))
        except Exception:
            pass
    return 200 <= _status_of(resp) < 300


def _json_of(resp):
    try:
        r = resp[0] if isinstance(resp, tuple) else resp
        if isinstance(r, (dict, list)):
            return r
        return r.get_json(silent=True)
    except Exception:
        return None


def _fetch_rows(ctx, path, key):
    """صفوف مصدر منصّة أو SourceDown. الشكل المقبول: {key:[…]} أو […]."""
    try:
        resp = _proxy(ctx)('GET', path, params={'status': 'new'})
    except SourceDown:
        raise
    except Exception as e:
        raise SourceDown('%s: %s' % (path, type(e).__name__))
    if not _is_ok(ctx, resp):
        raise SourceDown('%s: http %s' % (path, _status_of(resp)))
    body = _json_of(resp)
    rows = body.get(key) if isinstance(body, dict) else body
    if not isinstance(rows, list):
        raise SourceDown('%s: bad shape' % path)
    return [r for r in rows if isinstance(r, dict)][:GATHER_LIMIT]


def _gather_pmsg(ctx):
    out = []
    for r in _fetch_rows(ctx, '/api/bridge/messages', 'messages'):
        mid = str(r.get('id') or '').strip()
        body = _scrub(r.get('body'), BODY_MAX)
        if not mid or not body or not _ID_RE.match(mid):
            continue
        email = str(r.get('from_email') or r.get('email') or '').strip()
        has_account = bool(r['has_account']) if 'has_account' in r else bool(email)
        name = _scrub(r.get('from_name'), 60)
        subject = _scrub(r.get('subject'), 150)
        out.append(Target(
            ref='pmsg:' + mid,
            label=('رسالة عضو' + (' من ' + name if name else '') + (' — ' + subject if subject else ''))[:120],
            facts={'subject': subject, 'body': body, 'has_account': has_account},
            meta={'id': mid, 'email': email, 'approve_label': LABEL_SEND if has_account else LABEL_COPY}))
    return out


def _gather_smsg(ctx):
    Message = ctx.ns.get('Message')
    if Message is None:
        raise SourceDown('Message model missing')
    try:
        rows = Message.query.filter_by(status='new').order_by(Message.created_at.desc()).limit(GATHER_LIMIT).all()
    except Exception as e:
        try:
            ctx.ns['db'].session.rollback()
        except Exception:
            pass
        raise SourceDown('messages: %s' % type(e).__name__)
    out = []
    for m in rows:
        body = _scrub(m.body, BODY_MAX)
        if not body:
            continue
        topic = _scrub(m.topic, 150)
        name = _scrub(m.name, 60)
        out.append(Target(
            ref='smsg:%s' % m.id,
            label=('رسالة من الموقع' + (' من ' + name if name else '') + (' — ' + topic if topic else ''))[:120],
            facts={'subject': topic, 'body': body},
            meta={'id': m.id, 'email': m.email or '', 'phone': m.phone or '', 'approve_label': LABEL_SAVE_COPY}))
    return out


def _gather_leads(ctx):
    out = []
    for r in _fetch_rows(ctx, '/api/bridge/leads', 'leads'):
        lid = str(r.get('id') or '').strip()
        want = _scrub(r.get('want'), 600)
        if not lid or not want or not _ID_RE.match(lid):
            continue
        name = _scrub(r.get('full_name'), 60)
        out.append(Target(
            ref='lead:' + lid,
            label=('طلب تواصل' + (' من ' + name if name else ''))[:120],
            facts={'want': want, 'experience': _scrub(r.get('experience'), 300)},
            meta={'id': lid, 'phone': str(r.get('phone') or ''), 'email': str(r.get('from_email') or ''),
                  'approve_label': LABEL_COPY_RESOLVE}))
    return out


def gather_with_errors(ctx):
    """(targets, errors) — كل مصدر مستقل. errors = [{'source','reason'}]. لا ترمي أبدًا."""
    targets, errors = [], []
    for name, fn in ((SRC_PMSG, _gather_pmsg), (SRC_SMSG, _gather_smsg), (SRC_LEAD, _gather_leads)):
        try:
            targets.extend(fn(ctx))
        except SourceDown as e:
            errors.append({'source': name, 'reason': str(e)[:200]})
        except Exception as e:   # مصدر فاسد لا يُسقط الباقي
            logger.exception('brain2 reply_draft source %s', name)
            errors.append({'source': name, 'reason': type(e).__name__})
    return targets, errors


def _reply_gather(ctx):
    """يجمع من المصادر الثلاثة؛ الفاشل يُسجَّل في `last_source_errors`. `SourceDown` فقط إن فشلت كلها."""
    targets, errors = gather_with_errors(ctx)
    last_source_errors[:] = errors
    if len(errors) >= 3:
        raise SourceDown('all reply sources down: ' + ', '.join(e['source'] for e in errors))
    return targets


def _src_of(target):
    return str(target.ref or '').split(':', 1)[0]


def _reply_prompt(target):
    src = _src_of(target)
    f = target.facts or {}
    schema = '{"text":"نص الرد (حتى ٧٠٠ حرف)"}'
    rules = ('اكتب مسودة ردّ من فريق البروفيسور على صاحب الرسالة، بالعربية، بنبرة ودودة ومهنية وموجزة. '
             'اشكره على تواصله وأجب مما في الرسالة وحدها. لا تَعِد بموعد أو سعر أو نتيجة، ولا تذكر بريدًا أو رقم هاتف، '
             'ولا تقل إن الرد أُرسل أو سيُرسل بالبريد. لا تضع توقيعًا باسم شخص.')
    system = '%s\n%s\nالشكل المطلوب: %s' % (SYSTEM_AR, rules, schema)
    if src == SRC_LEAD:
        user = 'طلب تواصل من عميل محتمل.\nما يريده: %s' % _scrub(f.get('want'), 600)
        exp = _scrub(f.get('experience'), 300)
        if exp:
            user += '\nخبرته: ' + exp
    else:
        kind = 'رسالة من عضو' if src == SRC_PMSG else 'رسالة من زائر الموقع'
        user = '%s.\n' % kind
        subj = _scrub(f.get('subject'), 150)
        if subj:
            user += 'الموضوع: %s\n' % subj
        user += 'نص الرسالة: %s' % _scrub(f.get('body'), BODY_MAX)
    return system, user


def _reply_validate(raw, target):
    if not isinstance(raw, dict):
        return None
    t = raw.get('text')
    if not isinstance(t, str):
        return None
    t = t.strip()
    if not t or len(t) > REPLY_MAX:
        return None
    return {'text': t}


# ---- apply

def _bad(msg, **kw):
    return ApplyResult(ok=False, error=msg, **kw)


def _resolve(ctx, kind, rid):
    """علّم مصدر المنصّة «تم». (ok, status)"""
    try:
        resp = _proxy(ctx)('POST', '/api/bridge/%s/%s/resolve' % (kind, rid))
    except Exception:
        return False, 0
    return _is_ok(ctx, resp), _status_of(resp)


def _reply_apply(ctx, body, target):
    text = str((body or {}).get('text') or '').strip()
    if not text:
        return _bad('نص الرد فارغ')
    if len(text) > 900:
        return _bad('نص الرد أطول من المسموح')
    src = _src_of(target)
    meta = target.meta or {}
    rid = meta.get('id')

    if src == SRC_PMSG:
        rid = str(rid or '')
        if not _ID_RE.match(rid):
            return _bad('معرّف الرسالة غير صالح')
        if (target.facts or {}).get('has_account'):
            try:
                resp = _proxy(ctx)('POST', '/api/bridge/messages/%s/reply' % rid,
                                   json_body={'body': text, 'by': str(ctx.actor)[:120], 'confirmed': True})
            except Exception:
                return _bad('تعذّر الاتصال بالمنصة؛ لا نعرف إن وصل الرد. راجع الرسالة قبل المحاولة من جديد.', no_reply=True)
            st = _status_of(resp)
            if _is_ok(ctx, resp):
                _audit(ctx, 'brain.reply_send', rid, {'producer': 'reply_draft', 'ref': target.ref})
                return ApplyResult(ok=True, info={'sent': True})
            if st == 422:
                return _bad('صاحب هذه الرسالة زائر بلا حساب، فلا يصله الرد من المنصة. انسخ الرد وأرسله بنفسك.',
                            copy_text=text, info={'visitor': True})
            if st in (0, 502, 504):
                return _bad('تعذّر الاتصال بالمنصة؛ لا نعرف إن وصل الرد. راجع الرسالة قبل المحاولة من جديد.', no_reply=True)
            return _bad('رفضت المنصة الرد؛ لم يُرسَل شيء.')
        ok, _st = _resolve(ctx, 'messages', rid)
        if not ok:
            return _bad('تعذّر تعليم الرسالة «تم» على المنصة. حاول مرة أخرى.')
        return ApplyResult(ok=True, copy_text=text, info={'copied': True})

    if src == SRC_SMSG:
        Message, db = ctx.ns.get('Message'), ctx.ns.get('db')
        try:
            msg = db.session.get(Message, int(rid))
        except Exception:
            msg = None
        if msg is None:
            return _bad('الرسالة لم تعد موجودة')
        if msg.status == 'replied':
            return _bad('سبق حفظ ردّ على هذه الرسالة')
        try:
            msg.reply_body = text
            msg.status = 'replied'
            msg.replied_at = datetime.datetime.utcnow()
            db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            return _bad('تعذّر حفظ الرد')
        logger.info('Message reply to %s (id=%s) recorded by brain; no email is sent.', msg.email, msg.id)
        return ApplyResult(ok=True, copy_text=text, info={'saved': True})

    if src == SRC_LEAD:
        rid = str(rid or '')
        if not _ID_RE.match(rid):
            return _bad('معرّف الطلب غير صالح')
        ok, _st = _resolve(ctx, 'leads', rid)
        if not ok:
            return _bad('تعذّر تعليم الطلب «تم» على المنصة. حاول مرة أخرى.')
        return ApplyResult(ok=True, copy_text=text, info={'copied': True})

    return _bad('مصدر غير معروف')


def _audit(ctx, action, target, meta):
    fn = ctx.ns.get('_audit')
    if callable(fn):
        try:
            fn(action, target=target, meta=meta, actor=ctx.actor)
        except Exception:
            logger.exception('brain2 audit failed')


# ---------------------------------------------------------------- المنتجون

PRODUCERS = [
    Producer(
        id='opinion', section='home', kind='opinion',
        label='رأي العقل في كل قرار',
        sentence='عندما يظهر قرار ينتظرك، يكتب العقل رأيه فيه من بيانات البطاقة نفسها.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=40,
        gather=_opinion_gather, prompt=_opinion_prompt, validate=_opinion_validate,
        template=None, apply=None, tag='رأي العقل', approve_label=''),
    Producer(
        id='reply_draft', section='people', kind='draft',
        label='مسودات الرد على الرسائل',
        sentence='عندما تصل رسالة أو طلب تواصل، يكتب العقل مسودة رد تراجعها قبل أن تصل إلى صاحبها.',
        lock_reason='يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.',
        may_run_alone=False, default_mode='ask', per_run_cap=6,
        gather=_reply_gather, prompt=_reply_prompt, validate=_reply_validate,
        template=None, apply=_reply_apply, tag='مسودة رد', approve_label=LABEL_SEND),
]
