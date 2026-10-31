# -*- coding: utf-8 -*-
"""منتجو «العقل» (biz) — SPEC §3.3 / §3.4: مراجعة الدورات · ربط السوق · ملاحظات البحث · الحملات · الأسبوع · التوقعات.

قواعد الملف:
  * كل قراءة تمر بمساعدات `ctx.ns` (قاموس app.py الحي) وقت النداء، لا وقت الاستيراد (التسجيل في app.py أبكر من تعريفها).
  * مصدر لا يُقرأ ⇒ `SourceDown`: لا نكتب شيئًا ولا نخلط «فاضي» بـ«تعذّر».
  * `facts` هي كل ما يراه الذكاء: JSON لا يزيد عن ٤ كيلوبايت، بلا بريد ولا هاتف ولا اسم عميل. المعرّفات والبريد في `meta` فقط.
  * الكتابات الوحيدة: اعتماد دورة وربط طلب بدورة، وكلاهما عبر `_v2_write` (المسار الموجود نفسه) ولا يعمل إلا بعد موافقة المؤسس.
"""
import json
import re
from urllib.parse import quote

from brain2.contract import ApplyResult, Producer, SourceDown, Target

FACTS_MAX_BYTES = 4000          # الحد في المواصفة ٤ك؛ نترك هامشًا صغيرًا

# نسخة احتياطية حرفية من engine.SYSTEM_AR (SPEC §3.1) لو تعذّر استيراد المحرّك.
_SYSTEM_AR_FALLBACK = (
    'اكتب بالعربية الفصحى البسيطة، بصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا، لجمهور دولي، بلا مصطلحات تقنية. '
    'استعمل الحقائق المعطاة وحدها؛ لا تخترع رقمًا ولا اسمًا ولا تاريخًا ولا وعدًا، ولا تقل إن شيئًا نُفِّذ. '
    'أعد JSON صالحًا فقط بالشكل المطلوب.'
)


def _system_ar():
    """المقدمة المشتركة: من المحرّك إن وُجد (يُستورد هنا لا في الأعلى لأن المحرّك يُبنى مع هذا الملف)."""
    try:
        from brain2.engine import SYSTEM_AR
        if isinstance(SYSTEM_AR, str) and SYSTEM_AR.strip():
            return SYSTEM_AR
    except Exception:
        pass
    return _SYSTEM_AR_FALLBACK


# ------------------------------------------------------------------ أدوات صغيرة
_EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_PHONE_RE = re.compile(r'\+?\d[\d\s\-().]{6,}\d')
_URL_RE = re.compile(r'https?://\S+')


def _scrub(value, limit, phones=True):
    """نص حرّ داخل الحقائق: بلا بريد ولا هاتف ولا رابط، وبطول محدود. `phones=False` لنصوص الأرقام المجمّعة (تواريخ ومبالغ)."""
    s = value if isinstance(value, str) else ('' if value is None else str(value))
    s = _URL_RE.sub('', _EMAIL_RE.sub('', s))
    if phones:
        s = _PHONE_RE.sub('', s)      # \d يطابق الأرقام الهندية أيضًا في بايثون ٣
    return re.sub(r'\s+', ' ', s).strip()[:limit]


def _size(facts):
    return len(json.dumps(facts, ensure_ascii=False, sort_keys=True).encode('utf-8'))


def _fit(facts, *list_keys):
    """يقلّص الحقائق حتى تسع في ٤ك: يسحب من آخر القوائم المسمّاة، ثم يقصّ أطول نص."""
    guard = 0
    while _size(facts) > FACTS_MAX_BYTES and guard < 500:
        guard += 1
        for k in list_keys:
            if isinstance(facts.get(k), list) and facts[k]:
                facts[k].pop()
                break
        else:
            longest = max((k for k, v in facts.items() if isinstance(v, str)), key=lambda k: len(facts[k]), default=None)
            if longest is None or len(facts[longest]) <= 20:
                break
            facts[longest] = facts[longest][:len(facts[longest]) // 2]
    return facts


def _fn(ctx, name):
    fn = ctx.ns.get(name)
    if fn is None:
        raise SourceDown(name)
    return fn


def _num(v, default=0):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _clean_num(v):
    n = _num(v)
    return int(n) if n == int(n) else round(n, 2)


def _as_list(payload, *keys):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for k in keys:
            if isinstance(payload.get(k), list):
                return payload[k]
    return None


def _proxy_read(ctx, getter, path, params=None):
    """قراءة JSON من المنصة عبر دالة `getter` (`_platform_proxy` أو `_v2_get`). أي فشل ⇒ SourceDown."""
    ns = ctx.ns
    try:
        resp = getter(path, params=params)
    except SourceDown:
        raise
    except Exception:
        raise SourceDown(path)
    if not ns['_resp_ok'](resp):
        raise SourceDown(path)
    data = ns['_proxy_json'](resp)
    if not isinstance(data, dict):
        raise SourceDown(path)
    return data


def _platform_get(ctx, path, params=None):
    proxy = _fn(ctx, '_platform_proxy')

    def getter(p, params=None):
        return proxy('GET', p, params=params, timeout=12)

    return _proxy_read(ctx, getter, path, params)


def _write_result(ns, resp, info=None):
    """رد `_v2_write` ⇒ ApplyResult: نجاح · «ما وصلناش رد» (no_reply) · رفض بنص عربي."""
    if ns['_resp_ok'](resp):
        return ApplyResult(ok=True, info=info or {})
    js = ns['_proxy_json'](resp)
    err = js.get('error') if isinstance(js.get('error'), str) else ''
    if js.get('no_reply') is True:
        return ApplyResult(ok=False, no_reply=True, error=err)
    return ApplyResult(ok=False, error=err or 'تعذّر التنفيذ الآن')


def _text_of(raw, limit):
    if not isinstance(raw, dict):
        return None
    t = raw.get('text')
    if not isinstance(t, str):
        return None
    t = t.strip()
    if not t or len(t) > limit:
        return None
    return t


def _user_prompt(target, task):
    return '%s\n\nالحقائق:\n%s' % (task, json.dumps(target.facts, ensure_ascii=False, sort_keys=True))


# ================================================================== course_review
_CR_ROLE = (
    ' دورك: مراجعة دورة قُدّمت للنشر. في text اكتب بجملتين أو ثلاث ما ينقص الدورة اعتمادًا على قائمة الفحص والحقائق فقط، '
    'ثم أوصِ بـ publish إن اكتملت كل بنود الفحص، وبـ fix_first إن نقص أي بند. لا تتجاوز ٦٠٠ حرف، ولا تضف أرقامًا من عندك. '
    'الشكل المطلوب: {"text":"…","recommend":"publish|fix_first"}'
)
_CR_RECS = ('publish', 'fix_first')
CR_PUBLISH_LABEL = 'انشر الدورة'
CR_OPEN_LABEL = 'افتح الدورة'


def _gather_course_review(ctx):
    data = _platform_get(ctx, '/api/bridge/courses')
    courses = _as_list(data, 'courses')
    if courses is None:
        raise SourceDown('/api/bridge/courses')
    out = []
    for c in courses:
        if not isinstance(c, dict) or c.get('approval_status') != 'pending':
            continue
        cid = str(c.get('id') or '').strip()
        if not cid:
            continue
        cl = _platform_get(ctx, '/api/bridge/courses/%s/checklist' % quote(cid, safe=''))
        rows = _as_list(cl, 'checklist')
        if rows is None:
            raise SourceDown('checklist')
        checklist = [{'item': _scrub(r.get('item'), 120), 'ok': bool(r.get('ok'))} for r in rows if isinstance(r, dict)]
        outcomes = c.get('outcomes') if isinstance(c.get('outcomes'), list) else []
        facts = {
            'id': cid,
            'title': _scrub(c.get('title'), 120),
            'type': _scrub(c.get('type'), 30),
            'short_description': _scrub(c.get('short_description'), 300),
            'lessons': int(_num(c.get('lesson_count'), 0)),
            'outcomes': [_scrub(o, 120) for o in outcomes[:8] if str(o or '').strip()],
            'level': _scrub(c.get('level'), 40),
            'checklist': checklist,
        }
        _fit(facts, 'outcomes', 'checklist')
        out.append(Target(ref='course:%s' % cid, label=facts['title'][:120] or 'دورة', facts=facts,
                          meta={'course_id': cid, 'slug': str(c.get('slug') or '')}))
    return out


def _prompt_course_review(target):
    return (_system_ar() + _CR_ROLE, _user_prompt(target, 'راجع هذه الدورة قبل النشر.'))


def _failed_items(facts):
    return [r['item'] for r in (facts.get('checklist') or []) if isinstance(r, dict) and not r.get('ok')]


def _cr_body(target, text, rec):
    return {'text': text, 'recommend': rec, 'course_id': target.facts.get('id') or target.meta.get('course_id'),
            'approve_label': CR_PUBLISH_LABEL if rec == 'publish' else CR_OPEN_LABEL}


def _validate_course_review(raw, target):
    text = _text_of(raw, 900)
    if text is None:
        return None
    rec = raw.get('recommend')
    if rec not in _CR_RECS:
        return None
    if rec == 'publish' and _failed_items(target.facts):
        rec = 'fix_first'            # فحص المنصة هو الحَكَم: لا نشر وفي القائمة بند ناقص
    return _cr_body(target, text, rec)


def _template_course_review(target):
    failed = _failed_items(target.facts)
    if failed:
        return _cr_body(target, 'ينقصها: %s' % '، '.join(failed), 'fix_first')
    return _cr_body(target, 'بنود الفحص كلها مكتملة', 'publish')


def _apply_course_review(ctx, body, target):
    """publish ⇒ مسار الاعتماد الموجود (`POST /api/v2/courses/<id>/approve` ⇒ جسر المنصة) عبر `_v2_write`.
    fix_first ⇒ لا كتابة: الزر «افتح الدورة» ونرجّع `info.open_course` فقط."""
    cid = target.meta.get('course_id')
    if not cid:
        return ApplyResult(ok=False, error='تعذّر تحديد الدورة')
    if body.get('recommend') != 'publish':
        return ApplyResult(ok=True, info={'open_course': cid, 'no_write': True})
    path = '/api/bridge/courses/%s/approve' % quote(cid, safe='')
    resp = _fn(ctx, '_v2_write')('POST', path, {'confirmed': True, 'by': ctx.actor}, 'course.approve', cid,
                                 {'payout_model': None, 'via': 'brain'})
    return _write_result(ctx.ns, resp, {'course_id': cid})


# ================================================================== market_match
_MM_ROLE = (
    ' دورك: مطابقة طلب في السوق مع دورة قائمة. اختر من قائمة courses دورة واحدة فقط إن كانت تغطي الطلب بوضوح، '
    'واكتب في text جملة أو جملتين تشرحان سبب المطابقة. إن لم توجد دورة مناسبة فاجعل course_id يساوي null. '
    'انسخ course_id كما هو من القائمة. الشكل المطلوب: {"text":"…","course_id":"<معرّف من القائمة>|null"}'
)
_MM_NONE_TEXT = 'لا توجد دورة مناسبة'


def _gather_market_match(ctx):
    courses_data = _platform_get(ctx, '/api/bridge/courses')
    all_courses = _as_list(courses_data, 'courses')
    if all_courses is None:
        raise SourceDown('/api/bridge/courses')
    active = []
    for c in all_courses:
        if not isinstance(c, dict) or not c.get('is_active') or c.get('archived_at'):
            continue
        if c.get('approval_status') not in (None, '', 'approved'):
            continue
        cid = str(c.get('id') or '').strip()
        title = _scrub(c.get('title'), 70)
        if cid and title:
            active.append({'id': cid, 'title': title})
    active = active[:40]
    if not active:
        return []
    reqs_data = _proxy_read(ctx, _fn(ctx, '_v2_get'), '/api/bridge/market/requests', {'status': 'open', 'limit': 50})
    items = _as_list(reqs_data, 'items')
    if items is None:
        raise SourceDown('/api/bridge/market/requests')
    out = []
    for r in items:
        if not isinstance(r, dict) or r.get('linked_course_id') or r.get('hidden') or r.get('is_test'):
            continue
        if r.get('status') not in (None, '', 'open') or r.get('kind') == 'training_offer':
            continue
        rid = str(r.get('id') or '').strip()
        if not rid:
            continue
        facts = {
            'request': {
                'title': _scrub(r.get('title'), 150),
                'body': _scrub(r.get('body'), 600),
                'need_kind': _scrub(r.get('need_kind'), 30),
                'specialty': _scrub(r.get('specialty'), 80),
            },
            'courses': [dict(c) for c in active],
        }
        _fit_market(facts)
        out.append(Target(ref='mreq:%s' % rid, label=facts['request']['title'][:120] or 'طلب في السوق', facts=facts,
                          meta={'request_id': rid}))
    return out


def _fit_market(facts):
    while _size(facts) > FACTS_MAX_BYTES and facts['courses']:
        facts['courses'].pop()
    if _size(facts) > FACTS_MAX_BYTES:
        facts['request']['body'] = facts['request']['body'][:200]
    return facts


def _prompt_market_match(target):
    return (_system_ar() + _MM_ROLE, _user_prompt(target, 'هل توجد دورة في القائمة تناسب هذا الطلب؟'))


def _validate_market_match(raw, target):
    if not isinstance(raw, dict) or not isinstance(raw.get('text', ''), str):
        return None
    text = (raw.get('text') or '').strip()
    if len(text) > 900:
        return None
    cid = raw.get('course_id')
    if cid is None or (isinstance(cid, str) and cid.strip().lower() in ('', 'null', 'none')):
        # لا دورة مناسبة: المحرّك يخزّن الصف `discarded` بلا بطاقة حين يرى course_id=None.
        return {'text': text or _MM_NONE_TEXT, 'course_id': None}
    if not isinstance(cid, str) or not text:
        return None
    cid = cid.strip()
    by_id = {c['id']: c for c in (target.facts.get('courses') or []) if isinstance(c, dict)}
    if cid not in by_id:
        return None                  # معرّف من خارج القائمة = مخرجات غير صالحة
    return {'text': text, 'course_id': cid, 'course_title': by_id[cid]['title']}


def _apply_market_match(ctx, body, target):
    rid, cid = target.meta.get('request_id'), body.get('course_id')
    if not rid or not cid:
        return ApplyResult(ok=False, error='لا توجد دورة للربط')
    path = '/api/bridge/market/requests/%s/annotate' % quote(rid, safe='')
    resp = _fn(ctx, '_v2_write')('POST', path, {'linked_course_id': cid, 'confirmed': True, 'by': ctx.actor},
                                 'market.link_course', rid, {'course': cid, 'via': 'brain'})
    return _write_result(ctx.ns, resp, {'request_id': rid, 'course_id': cid})


# ================================================================== seo_notes
_SEO_ROLE = (
    ' دورك: كتابة ملاحظات تحسّن ظهور مسودة مقال في البحث، اعتمادًا على نتيجة الفحص المعطاة (score وissues وwords) فقط. '
    'اكتب من سطرين إلى أربعة أسطر قصيرة، في كل سطر إجراء واحد واضح، بلا رموز تعبيرية ولا أرقام من عندك. '
    'الشكل المطلوب: {"lines":["…","…"]}'
)


def _gather_seo_notes(ctx):
    payload = _fn(ctx, '_bridge_get')('/api/bridge/articles', {'limit': 60, 'status': 'draft'})
    arts = _as_list(payload, 'articles', 'items')
    if arts is None:
        raise SourceDown('/api/bridge/articles')
    score_fn = _fn(ctx, '_seo_scorecard')
    cards = []
    for a in arts:
        if not isinstance(a, dict) or not a.get('id'):
            continue
        try:
            sc = score_fn(a)
        except Exception:
            continue
        issues = [_scrub(i, 160, phones=False) for i in (sc.get('issues') or []) if isinstance(i, str)]
        if not issues:
            continue                  # لا ملاحظة تُكتب عن مسودة سليمة
        cards.append((int(_num(sc.get('score'))), str(a['id']), {
            'title': _scrub(sc.get('title') or a.get('title'), 120),
            'score': int(_num(sc.get('score'))),
            'words': int(_num(sc.get('words'))),
            'issues': issues[:6],
        }))
    cards.sort(key=lambda t: (t[0], t[1]))   # الأضعف أولًا
    out = []
    for _, aid, facts in cards:
        _fit(facts, 'issues')
        out.append(Target(ref='article:%s' % aid, label=facts['title'][:120] or 'مسودة مقال', facts=facts,
                          meta={'article_id': aid}))
    return out


def _prompt_seo_notes(target):
    return (_system_ar() + _SEO_ROLE, _user_prompt(target, 'اكتب ملاحظات الظهور في البحث لهذه المسودة.'))


def _validate_seo_notes(raw, target):
    if not isinstance(raw, dict) or not isinstance(raw.get('lines'), list):
        return None
    lines = raw['lines']
    if not 2 <= len(lines) <= 4 or not all(isinstance(x, str) and x.strip() and len(x.strip()) <= 200 for x in lines):
        return None
    text = '\n'.join(x.strip() for x in lines)
    if len(text) > 600:
        return None
    return {'text': text}


def _template_seo_notes(target):
    issues = [re.sub(r'^[^\w؀-ۿ]+', '', i).strip() for i in (target.facts.get('issues') or []) if isinstance(i, str)]
    issues = [i for i in issues if i][:4]
    return {'text': '\n'.join(issues)} if issues else None


# ================================================================== campaign_comment
_CC_ROLE = (
    ' دورك: تعليق قصير على أرقام حملة إعلانية. اكتب في text جملتين أو ثلاثًا تصفان ما تقوله الأرقام المعطاة فقط '
    '(الإنفاق مقابل الميزانية، والنقرات، والعملاء المحتملين، والتحويلات). لا تحسب نسبًا جديدة، ولا تنصح بإنفاق مال. '
    'لا تتجاوز ٤٠٠ حرف. الشكل المطلوب: {"text":"…"}'
)


def _gather_campaign_comment(ctx):
    Campaign = ctx.ns.get('Campaign')
    if Campaign is None:
        raise SourceDown('Campaign')
    try:
        rows = list(Campaign.query.all())
    except Exception:
        raise SourceDown('Campaign')
    live = [c for c in rows if (getattr(c, 'status', '') or '') in ('active', 'paused') and _num(getattr(c, 'spent', 0)) > 0]
    live.sort(key=lambda c: -_num(getattr(c, 'spent', 0)))
    out = []
    for c in live[:20]:
        facts = {
            'name': _scrub(c.name, 80), 'platform': _scrub(c.platform, 30),
            'budget': _clean_num(c.budget), 'spent': _clean_num(c.spent), 'currency': _scrub(c.currency, 5),
            'impressions': int(_num(c.impressions)), 'clicks': int(_num(c.clicks)),
            'leads': int(_num(c.leads)), 'conversions': int(_num(c.conversions)),
            'revenue_attributed': _clean_num(c.revenue_attributed),
        }
        out.append(Target(ref='campaign:%s' % c.id, label=facts['name'][:120] or 'حملة', facts=facts,
                          meta={'campaign_id': c.id}))
    return out


def _prompt_campaign_comment(target):
    return (_system_ar() + _CC_ROLE, _user_prompt(target, 'علّق على أرقام هذه الحملة.'))


def _validate_text_note(limit):
    def validate(raw, target):
        t = _text_of(raw, limit)
        return {'text': t} if t else None
    return validate


# ================================================================== weekly_read
_WR_ROLE = (
    ' دورك: قراءة قصيرة لأرقام الأسبوع الماضي. من السطور المعطاة في lines اكتب في text أربعة إلى ستة أسطر قصيرة '
    'تلخص ما حدث وما يستحق الانتباه. انقل الأرقام كما وردت تمامًا، ولا تحسب أرقامًا جديدة، وما كان «غير متاح بعد» '
    'فاذكره كما هو. لا تتجاوز ٤٥٠ حرفًا. الشكل المطلوب: {"text":"…"}'
)


def _load_weekly_for():
    from v2_reports_routes import weekly_for
    return weekly_for


def _gather_weekly_read(ctx):
    try:
        payload, err = _load_weekly_for()(ctx.ns, None)
    except Exception:
        raise SourceDown('weekly')
    if err or not isinstance(payload, dict) or not isinstance(payload.get('week'), dict):
        raise SourceDown('weekly')
    sources = payload.get('sources') or {}
    if sources and not any(v in ('ok', 'partial') for v in sources.values()):
        raise SourceDown('weekly')
    lines = [_scrub(x, 200, phones=False) for x in str(payload.get('text') or '').split('\n')[1:]]
    lines = [x for x in lines if x]
    if not lines:
        raise SourceDown('weekly')
    facts = {'week': _scrub(payload['week'].get('label'), 80), 'lines': lines}
    _fit(facts, 'lines')
    start = str(payload['week'].get('start') or '')
    if not start:
        raise SourceDown('weekly')
    return [Target(ref='week:%s' % start, label=('قراءة الأسبوع: %s' % facts['week'])[:120], facts=facts,
                   meta={'start': start, 'end': str(payload['week'].get('end') or '')})]


def _prompt_weekly_read(target):
    return (_system_ar() + _WR_ROLE, _user_prompt(target, 'اكتب قراءة الأسبوع.'))


# ================================================================== forecast_comment
_FC_ROLE = (
    ' دورك: تعليق على التوقعات المالية للأشهر القادمة مقارنةً بالأرقام الفعلية المعطاة. اكتب في text ثلاثة أسطر أو أربعة '
    'قصيرة. انقل الأرقام كما وردت تمامًا ولا تحسب أرقامًا جديدة، ولا تنصح بصرف مال ولا تَعِد بنتيجة. '
    'لا تتجاوز ٤٥٠ حرفًا. الشكل المطلوب: {"text":"…"}'
)


def _months_from(now, n=3):
    y, m = now.year, now.month
    out = []
    for _ in range(n):
        out.append('%04d-%02d' % (y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def _gather_forecast_comment(ctx):
    FM = ctx.ns.get('ForecastMonth')
    if FM is None:
        raise SourceDown('ForecastMonth')
    wanted = _months_from(ctx.now, 3)
    try:
        rows = [f for f in FM.query.all() if getattr(f, 'month', None) in wanted]
        snap = _fn(ctx, 'generate_ai_snapshot')()
    except SourceDown:
        raise
    except Exception:
        raise SourceDown('forecast')
    if not rows:
        return []                      # لا توقعات لهذه الأشهر: لا شيء نعلّق عليه
    rows.sort(key=lambda f: f.month)
    fin = (snap or {}).get('financials') or {}
    cash = (snap or {}).get('cashflow') or {}
    facts = {
        'months': [{
            'month': f.month, 'revenue_egp': _clean_num(f.revenue_egp),
            'expenses_egp': _clean_num(_num(f.cogs_egp) + _num(f.marketing_egp) + _num(f.payroll_egp) + _num(f.rent_egp) + _num(f.other_sga_egp)),
            'target_courses': int(_num(f.target_courses)), 'target_students': int(_num(f.target_students)),
        } for f in rows],
        'financials': {k: _clean_num(fin.get(k)) for k in ('total_revenue_egp', 'total_expenses_egp', 'net_profit_egp', 'payout_cost_egp') if k in fin},
        'cashflow': {'balance_egp': _clean_num(cash.get('balance_egp'))} if 'balance_egp' in cash else {},
    }
    _fit(facts, 'months')
    return [Target(ref='forecast:%s' % wanted[0], label=('التوقعات من %s' % wanted[0])[:120], facts=facts,
                   meta={'months': wanted})]


def _prompt_forecast_comment(target):
    return (_system_ar() + _FC_ROLE, _user_prompt(target, 'علّق على هذه التوقعات.'))


# ================================================================== course_lesson_draft (hook)
def _gather_course_lesson_draft(ctx):
    """خطّاف مخفي (listed=False) لجولة لاحقة — لا يعمل في هذه الجولة، ومحرّر الدورة خارجها.

    ما تملؤه الجولة اللاحقة:
      * gather: يقرأ من جسر المنصة الجديد للدروس (دروس ناقصة في دورة) ويرجع Targets بحقائق الدرس.
      * validate: يرجع {'text', 'fields': {'title', 'body'}} والواجهة تعرض body.fields بشكل عام.
      * apply: ينادي الجسر الجديد بـ confirmed:true بعد موافقة المؤسس.
    إلى ذلك الحين: gather ترجع [] و apply تساوي None، فلا يُكتب شيء ولا تُنادى أي خدمة.
    """
    return []


def _prompt_course_lesson_draft(target):
    return (_system_ar(), '')


def _validate_course_lesson_draft(raw, target):
    return None


# ================================================================== السجل
PRODUCERS = [
    Producer(
        id='course_review', section='courses', kind='draft',
        label='مراجعة الدورة قبل النشر',
        sentence='عندما تُقدَّم دورة للنشر، يكتب العقل ما ينقصها ويقترح: انشر أو أصلح أولًا.',
        lock_reason='يسألك دائمًا لأن النشر يظهر للناس.',
        may_run_alone=False, default_mode='ask', per_run_cap=3,
        gather=_gather_course_review, prompt=_prompt_course_review, validate=_validate_course_review,
        template=_template_course_review, apply=_apply_course_review,
        tag='مراجعة دورة', approve_label=CR_PUBLISH_LABEL,
    ),
    Producer(
        id='market_match', section='market', kind='draft',
        label='ربط طلبات السوق بدورة مناسبة',
        sentence='عندما يطلب عضو شيئًا تغطيه دورة لدينا، يقترح العقل ربطه بها.',
        lock_reason='يسألك دائمًا لأنه يغيّر بيانات الطلب على المنصة.',
        may_run_alone=False, default_mode='ask', per_run_cap=3,
        gather=_gather_market_match, prompt=_prompt_market_match, validate=_validate_market_match,
        apply=_apply_market_match, tag='ربط بدورة', approve_label='اربطه بالدورة',
    ),
    Producer(
        id='seo_notes', section='content', kind='note',
        label='ملاحظات الظهور في البحث على المسودات',
        sentence='عندما تنتظر مسودة مقال، يكتب العقل ما يحسّن ظهورها في البحث. لا يُنشر شيء.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=3,
        gather=_gather_seo_notes, prompt=_prompt_seo_notes, validate=_validate_seo_notes,
        template=_template_seo_notes, tag='ملاحظة بحث', approve_label='احتفظ بها',
    ),
    Producer(
        id='campaign_comment', section='marketing', kind='note',
        label='تعليق على الحملات',
        sentence='عندما تتغير أرقام حملة، يكتب العقل تعليقًا قصيرًا عليها.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=3,
        gather=_gather_campaign_comment, prompt=_prompt_campaign_comment, validate=_validate_text_note(500),
        tag='تعليق حملة', approve_label='احتفظ بها',
    ),
    Producer(
        id='weekly_read', section='reports', kind='note',
        label='قراءة الأسبوع',
        sentence='في بداية كل أسبوع، يكتب العقل قراءة قصيرة لأرقام الأسبوع الماضي.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=1,
        gather=_gather_weekly_read, prompt=_prompt_weekly_read, validate=_validate_text_note(550),
        tag='قراءة الأسبوع', approve_label='احتفظ بها',
    ),
    Producer(
        id='forecast_comment', section='company', kind='note',
        label='تعليق على التوقعات',
        sentence='عندما تتغير التوقعات أو الأرقام الفعلية، يكتب العقل تعليقًا عليها.',
        lock_reason='', may_run_alone=True, default_mode='alone', per_run_cap=1,
        gather=_gather_forecast_comment, prompt=_prompt_forecast_comment, validate=_validate_text_note(550),
        tag='تعليق توقعات', approve_label='احتفظ بها',
    ),
    Producer(
        id='course_lesson_draft', section='courses', kind='draft',
        label='مسودات دروس الدورات',
        sentence='عندما ينقص درس في دورة، يكتب العقل مسودته لتراجعها.',
        lock_reason='يسألك دائمًا لأن الدرس يظهر للمتعلمين.',
        may_run_alone=False, default_mode='ask', per_run_cap=3,
        gather=_gather_course_lesson_draft, prompt=_prompt_course_lesson_draft,
        validate=_validate_course_lesson_draft, apply=None,
        tag='مسودة درس', approve_label='اعتمد المسودة', listed=False,
    ),
]
