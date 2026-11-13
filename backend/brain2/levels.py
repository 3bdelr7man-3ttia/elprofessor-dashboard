# -*- coding: utf-8 -*-
"""R24 م٣ — مستويات العقل لكل نوع شغل (docs/R24-DASHBOARD-SPEC.md «العقل (المرحلة ٣)»).

لكل نوع شغل مستوى من تلاتة:
  * `alone`   لوحده: العقل بينفّذ ويقولك بعدها، وجنبها «رجّعها».
  * `suggest` يقترح وانت توافق: العقل بيراجع ويجهّز الاقتراح، والتنفيذ بضغطتك.
  * `ask`     يسألك: العقل بيجمع الورق بس ويسيب القرار.

⛔ القواعد دي بتتفرض **هنا في الخادم** (الواجهة بتعرضها بس):
  ١. الفلوس والنشر للناس والرسايل لناس حقيقيين ما تبقاش «لوحده» أبدًا ⇒ ٤٠٩ (جدول `WORK_TYPES` + شبكة أمان بالاسم `_RISKY_ID`).
  ٢. النوع ما يبقاش «لوحده» إلا لو فعله بيتعكس (`reversible` في الجدول الوحيد تحت). ⇒ ٤٠٩.
  ٣. الافتراضي زي النهارده: مستوى المنتج الفعلي من `registry` (default_mode) والمفتاح القديم (`v2_brain_switches`)، مفيش تغيير سلوك من نفسه.

التخزين: `brain_levels(work_type PK, level, updated_by, updated_at)` + `alone_log` (سجل «عمل لوحده» وبيانات الرجوع) +
`brain_learn` (قرارات الأنواع اللي مش منتج عقل: وافقت زي ما هي · عدّلت · رفضت) + `brain_learn_ask` («لا» بتسكّت السؤال ٣٠ يوم).
المنتجات (producers) بتتعلّم من صفوف `v2_brain_items` نفسها (approved/edited/rejected) فمفيش تكرار.
كل الجداول بـ`CREATE TABLE IF NOT EXISTS` (SQLite وPostgres) زي `decision_snooze`.
"""
import datetime
import json
import logging
import re
import uuid
from collections import namedtuple

from sqlalchemy import text

logger = logging.getLogger(__name__)

LEVELS = ('alone', 'suggest', 'ask')
LEVEL_TO_MODE = {'alone': 'alone', 'suggest': 'ask', 'ask': 'off'}     # مفتاح المنتج القديم
MODE_TO_LEVEL = {'alone': 'alone', 'ask': 'suggest', 'off': 'ask'}

LEARN_STREAK = 8               # موافقات متتالية من غير تعديل قبل سؤال «تخليني أعملها لوحدي؟»
LEARN_SUPPRESS_DAYS = 30       # «لا» بتسكّت السؤال المدة دي
STATS_DAYS = 30
ALONE_NOTE_MAX = 300

LOCK_TEXT = 'دايمًا بموافقتك'
LOCK_KIND_AR = {
    'money': 'فيه فلوس',
    'publish': 'بيوصل للناس',
    'message': 'بيبعت لناس حقيقيين',
    'data': 'بيغيّر بيانات حقيقية على المنصة',
}

ERR_UNKNOWN = 'نوع الشغل ده غير معروف'
ERR_BAD_LEVEL = 'اختيار غير صالح'
ERR_NOT_ALLOWED = 'الاختيار ده مش متاح للنوع ده'
FAIL_AR = 'تعذّر الحفظ — حاول تاني'

# ------------------------------------------------------------------ جدول أنواع الشغل (الوحيد)
# reversible: فعل «لوحده» له رجوع حقيقي (رجّعها). غير ذلك ⇒ النوع ده ما يتسمحلوش يبقى «لوحده».
# lock: money|publish|message|data ⇒ دايمًا بموافقتك. levels: المستويات المتاحة فعلًا.
# producer: معرّف منتج `brain2` لو النوع منتج (القراءة/الكتابة من مفتاحه). external: إعداد على المنصة.
# unit: (جمع ٣–١٠، مفرد منصوب ١١+) لجملة سؤال التعلّم.
WorkType = namedtuple('WorkType', 'id group title hint producer default lock reversible levels unit external')


def _wt(id, group, title, hint='', producer='', default='suggest', lock='', reversible=False, levels=None, unit=('عناصر', 'عنصرًا'), external=''):
    if levels is None:
        levels = ('suggest', 'ask') if lock or not reversible else LEVELS
    return WorkType(id, group, title, hint, producer, default, lock, reversible, tuple(levels), unit, external)


GROUPS = (
    ('people', 'الناس'),
    ('files', 'ملفات الخبراء'),
    ('content', 'المحتوى'),
    ('notes', 'ملاحظات العقل'),
    ('locked', 'الفلوس والنشر للناس'),
)

WORK_TYPES = (
    # —— الناس
    _wt('application_review', 'people', 'مراجعة طلب انضمام خبير أو مدرّب', 'السيرة، والفيديو، ورقم القيد، والهوية', producer='application_review',
        default='alone', reversible=True, unit=('طلبات مراجعة', 'طلب مراجعة')),
    _wt('visitor_open', 'people', 'فتح المنصة لزائر عادي', 'إيميل عادي من غير علامة اشتباه', default='suggest', reversible=True, unit=('زوّار', 'زائرًا')),
    _wt('application_decide', 'people', 'قبول طلب انضمام خبير أو مدرّب', 'القبول بينشر الاسم ويوصله إشعار', lock='publish'),
    _wt('identity_verify', 'people', 'توثيق هوية خبير', 'بتظهر علامة التوثيق للناس', lock='publish'),
    _wt('invite_approve', 'people', 'دعوة من عضو', 'الدعوة بتوصل لشخص حقيقي', lock='message'),
    _wt('reply_draft', 'people', 'الرد على رسائل الموقع', 'يكتب الرد وانت تبعته', producer='reply_draft', lock='message'),
    # —— ملفات الخبراء
    _wt('file_assign', 'files', 'توزيع ملف على خبير', 'حسب التخصص والضغط', default='suggest', reversible=True, levels=('alone', 'suggest'),
        external='auto_assign', unit=('ملفات', 'ملفًا')),
    _wt('file_review', 'files', 'مراجعة أول رأي لخبير جديد', 'يراجعه قبل ما يوصل العميل', producer='file_review', lock='message'),
    # —— المحتوى
    _wt('comment_reject_abusive', 'content', 'إخفاء تعليق مسيء بوضوح', 'لما فحص التعليقات يحكم إنه مسيء', default='suggest', reversible=True, unit=('تعليقات', 'تعليقًا')),
    _wt('seo_notes', 'content', 'ملاحظات الظهور في البحث على المسودات', 'ملاحظة داخلية بس', producer='seo_notes', default='alone', reversible=True, unit=('ملاحظات', 'ملاحظة')),
    _wt('site_review', 'content', 'مراجعة نصوص الموقع', 'التعديل بينزل على الموقع', producer='site_review', lock='publish'),
    # —— ملاحظات العقل (داخلية، مفيش حاجة بتوصل لحد)
    _wt('opinion', 'notes', 'رأي العقل في كل قرار', 'سطر على بطاقة القرار', producer='opinion', default='alone', reversible=True, levels=('alone', 'ask')),
    _wt('campaign_comment', 'notes', 'تعليق على الحملات', producer='campaign_comment', default='alone', reversible=True, unit=('تعليقات', 'تعليقًا')),
    _wt('weekly_read', 'notes', 'قراءة الأسبوع', producer='weekly_read', default='alone', reversible=True, unit=('قراءات', 'قراءة')),
    _wt('forecast_comment', 'notes', 'تعليق على التوقعات', producer='forecast_comment', default='alone', reversible=True, unit=('تعليقات', 'تعليقًا')),
    _wt('links_digest', 'notes', 'ملخص الأنظمة المتصلة', producer='links_digest', default='alone', reversible=True, unit=('ملخصات', 'ملخصًا')),
    # —— الفلوس والنشر للناس: دايمًا بموافقتك
    _wt('payout', 'locked', 'تحويل أرباح خبير أو مدرّب', 'يراجع الحساب ويقترح', lock='money'),
    _wt('manual_payment', 'locked', 'تأكيد إيصال تحويل', 'يطابق الإيصال ويقترح', lock='money'),
    _wt('refund', 'locked', 'استرداد أو نزاع', 'يلخّص الطرفين ويقترح', lock='money'),
    _wt('book_offer_price', 'locked', 'اعتماد أسعار عرض كتاب', 'يراجع السعر ويقترح', lock='money'),
    _wt('course_review', 'locked', 'نشر دورة جديدة', 'يراجع الدروس ويكتب ملاحظته', producer='course_review', lock='publish'),
    _wt('course_lesson_draft', 'locked', 'مسودة درس', 'تظهر للمتعلمين بعد اعتمادك', producer='course_lesson_draft', lock='publish'),
    _wt('book_publish', 'locked', 'نشر كتاب أو دليل', lock='publish'),
    _wt('topic_publish', 'locked', 'موضوع من عضو في الساحة', lock='publish'),
    _wt('creative_publish', 'locked', 'عمل إبداعي', lock='publish'),
    _wt('article_publish', 'locked', 'نشر مقال', lock='publish'),
    _wt('ask_correction', 'locked', 'تصحيح خبير لإجابة «اسأل»', 'يقارنه بالنص ويوصي', producer='ask_correction', lock='publish'),
    _wt('library_contribution', 'locked', 'مساهمات «مكتبة القانون العربي»', producer='library_contribution', lock='publish'),
    _wt('training_item', 'locked', 'بنود «جلسة تدريب البروف»', producer='training_item', lock='publish'),
    _wt('ask_topic', 'locked', 'مواضيع للخبراء من تصحيحات «اسأل»', producer='ask_topic', lock='publish'),
    _wt('market_match', 'locked', 'ربط طلبات السوق بدورة مناسبة', producer='market_match', lock='data'),
)
BY_ID = {w.id: w for w in WORK_TYPES}

# شبكة أمان تانية بالاسم: نوع جديد اتنسى يتحط له قفل ⇒ اسمه لو فيه كلمة فلوس/نشر/رسايل بيتقفل لوحده.
_RISKY_ID = re.compile(r'(payout|transfer|refund|price|receipt|payment|publish|course|book|topic|creative|article|message|reply|send|email|invite)')


def lock_of(wt):
    """نوع القفل (`money|publish|message|data`) أو ''. القفل في الجدول يعلو، وبعده شبكة الأمان بالاسم."""
    if wt.lock:
        return wt.lock
    if _RISKY_ID.search(wt.id):
        return 'data'
    return ''


def eligible(wt):
    """يتسمحله يبقى «لوحده» ويظهر له سؤال التعلّم: مش مقفول، فعله بيتعكس، و«لوحده» و«يقترح» الاتنين متاحين."""
    return (not lock_of(wt)) and bool(wt.reversible) and 'alone' in wt.levels and 'suggest' in wt.levels


def catalog():
    """الجدول + أي منتج مسجّل في `registry` ما اتحطّش له صف (يتقفل ما لم يكن ملاحظة داخلية). مستورد كسول: `registry` بيستورد المنتجين."""
    out = list(WORK_TYPES)
    try:
        from brain2 import registry
        known = {w.producer for w in WORK_TYPES if w.producer}
        for p in registry.PRODUCERS:
            if not p.listed or p.id in known:
                continue
            safe = bool(p.may_run_alone) and p.kind == 'note'
            out.append(_wt(p.id, 'notes' if safe else 'locked', p.label or p.id, producer=p.id,
                           default=('alone' if p.default_mode == 'alone' and safe else 'suggest'), lock='' if safe else 'data', reversible=safe))
    except Exception:   # noqa: BLE001
        logger.exception('brain2 levels: registry not readable')
    return out


def get_type(work_type):
    if work_type in BY_ID:
        return BY_ID[work_type]
    for w in catalog():
        if w.id == work_type:
            return w
    return None


# ------------------------------------------------------------------ الحارس (القواعد الصلبة)

def check_level(wt, level):
    """(ok, http_status, رسالة عربية). ⛔ القفل والرجوع هنا — مش في الواجهة."""
    if level not in LEVELS:
        return False, 400, ERR_BAD_LEVEL
    lock = lock_of(wt)
    if level == 'alone':
        if lock:
            return False, 409, '«%s» %s. %s' % (wt.title, LOCK_KIND_AR.get(lock, LOCK_KIND_AR['data']), LOCK_TEXT)
        if not wt.reversible:
            return False, 409, 'مينفعش «%s» يشتغل لوحده لأن فعله ما بيتعكسش' % wt.title
    if level not in wt.levels:
        return False, 400, ERR_NOT_ALLOWED
    return True, 200, ''


# ------------------------------------------------------------------ الجداول

_ENSURED = set()


def _iso(dt):
    """دايمًا بـ٦ خانات ميكروثانية: الترتيب والمقارنة النصّية صحيحين حتى لو قرارين في نفس الثانية."""
    return dt.isoformat(timespec='microseconds') + 'Z'


def _now():
    return datetime.datetime.utcnow()


def _parse(s):
    for fmt in ('%Y-%m-%dT%H:%M:%S.%fZ', '%Y-%m-%dT%H:%M:%SZ'):
        try:
            return datetime.datetime.strptime(str(s), fmt)
        except (TypeError, ValueError):
            continue
    return None


def ensure(db):
    """ينشئ الجداول لو ناقصة (آمن يتكرّر). مرة لكل عملية وقاعدة؛ أي فشل بيترفع للمنادي (الراوت بيرجّع ٥٠٠ بجملة)."""
    key = str(db.engine.url)
    if key in _ENSURED:
        return
    stmts = (
        'CREATE TABLE IF NOT EXISTS brain_levels (work_type TEXT PRIMARY KEY, level TEXT NOT NULL, updated_by TEXT NOT NULL DEFAULT \'\', updated_at TEXT NOT NULL)',
        'CREATE TABLE IF NOT EXISTS alone_log (id TEXT PRIMARY KEY, work_type TEXT NOT NULL, what TEXT NOT NULL, target_ref TEXT NOT NULL DEFAULT \'\', '
        'target_label TEXT NOT NULL DEFAULT \'\', at TEXT NOT NULL, undo_json TEXT NOT NULL DEFAULT \'\', undone_at TEXT NULL, '
        'undone_by TEXT NOT NULL DEFAULT \'\', undo_note TEXT NOT NULL DEFAULT \'\')',
        'CREATE TABLE IF NOT EXISTS brain_learn (id TEXT PRIMARY KEY, work_type TEXT NOT NULL, outcome TEXT NOT NULL, ref TEXT NOT NULL DEFAULT \'\', '
        'at TEXT NOT NULL, by TEXT NOT NULL DEFAULT \'\')',
        'CREATE TABLE IF NOT EXISTS brain_learn_ask (work_type TEXT PRIMARY KEY, answer TEXT NOT NULL, until TEXT NULL, by TEXT NOT NULL DEFAULT \'\', at TEXT NOT NULL)',
    )
    for s in stmts:
        db.session.execute(text(s))
    db.session.commit()
    _ENSURED.add(key)


def _rows(db, sql, **params):
    return db.session.execute(text(sql), params).fetchall()


# ------------------------------------------------------------------ قراءة/كتابة المستوى

def _producer(pid):
    try:
        from brain2 import registry
        return registry.by_id(pid)
    except Exception:   # noqa: BLE001
        return None


def stored(db, work_type):
    """(level, updated_at_iso, updated_by) من `brain_levels` أو None."""
    ensure(db)
    r = _rows(db, 'SELECT level, updated_at, updated_by FROM brain_levels WHERE work_type = :w', w=work_type)
    return (r[0][0], r[0][1], r[0][2]) if r else None


def level_of(ns, wt):
    """المستوى الفعلي: الصف المحفوظ ⇒ مفتاح المنتج القديم ⇒ الافتراضي. «لوحده» على نوع ما يسمحش بيه ⇒ «يقترح» (حزام أمان قراءة)."""
    if isinstance(wt, str):
        wt = get_type(wt)
    if wt is None:
        return 'ask'
    db = ns['db']
    row = stored(db, wt.id)
    level = row[0] if row and row[0] in LEVELS else None
    if level is None and wt.producer:
        p = _producer(wt.producer)
        if p is not None:
            try:
                from brain2 import engine
                sw = engine.get_switch(db, p.id)
                mode = sw.mode if sw is not None else p.default_mode
                level = MODE_TO_LEVEL.get(mode)
            except Exception:   # noqa: BLE001
                level = None
    if level is None:
        level = wt.default
    if level == 'alone' and not check_level(wt, 'alone')[0]:
        level = 'suggest' if 'suggest' in wt.levels else 'ask'
    if level not in wt.levels:
        level = wt.default if wt.default in wt.levels else wt.levels[0]
    return level


def _sync_switch(ns, wt, level, actor):
    """مفتاح المنتج القديم (`v2_brain_switches`) بيمشي مع المستوى — المحرّك بيقرأ منه (`effective_mode`)."""
    if not wt.producer:
        return
    p = _producer(wt.producer)
    if p is None:
        return
    from brain2 import engine
    db = ns['db']
    Switch = engine._models(db)[1]
    engine.ensure_schema(db)
    row = Switch.query.get(p.id)
    mode = LEVEL_TO_MODE[level]
    if row is None:
        row = Switch(producer=p.id, mode=mode)
        db.session.add(row)
    row.mode = mode
    row.updated_at, row.updated_by = datetime.datetime.utcnow(), str(actor)[:255]
    db.session.commit()


def _audit(ns, action, target, meta, actor):
    try:
        ns['_audit'](action, target=target, meta=meta, actor=actor)
    except TypeError:
        try:
            ns['_audit'](action, target=target, meta=meta)
        except Exception:   # noqa: BLE001
            logger.exception('brain2 levels: audit failed')
    except Exception:   # noqa: BLE001
        logger.exception('brain2 levels: audit failed')


def set_level(ns, work_type, level, actor):
    """يغيّر مستوى نوع. يرجع (http_status, payload). ⛔ القفل والرجوع بيتفحصوا هنا قبل أي كتابة."""
    wt = get_type(work_type)
    if wt is None:
        return 404, {'error': ERR_UNKNOWN}
    ok, status, msg = check_level(wt, level)
    if not ok:
        return status, {'error': msg, 'locked': bool(lock_of(wt)), 'lock_text': LOCK_TEXT if lock_of(wt) else ''}
    db = ns['db']
    ensure(db)
    before = level_of(ns, wt)
    if wt.external == 'auto_assign':
        # توزيع الملفات إعداد على المنصة نفسها: نبدّله بنفس نداء شاشة القواعد قبل ما نسجّل أي حاجة عندنا.
        err = _set_auto_assign(ns, level == 'alone', actor)
        if err:
            return 502, {'error': err}
    now = _iso(_now())
    try:
        db.session.execute(text('DELETE FROM brain_levels WHERE work_type = :w'), {'w': wt.id})
        db.session.execute(text('INSERT INTO brain_levels (work_type, level, updated_by, updated_at) VALUES (:w, :l, :b, :a)'),
                           {'w': wt.id, 'l': level, 'b': str(actor)[:255], 'a': now})
        db.session.commit()
        _sync_switch(ns, wt, level, actor)
    except Exception:   # noqa: BLE001
        db.session.rollback()
        logger.exception('brain2 levels: set failed for %s', wt.id)
        return 500, {'error': FAIL_AR}
    _audit(ns, 'brain.level', wt.id, {'from': before, 'to': level}, actor)
    return 200, {'ok': True, 'work_type': wt.id, 'level': level, 'updated_at': now, 'updated_by': str(actor)[:255]}


def _set_auto_assign(ns, value, actor):
    """نفس نداء `PUT /api/platform-expert-files/settings`. يرجع نص خطأ عربي أو ''."""
    fn = ns.get('_ef_bridge') or ns.get('_platform_proxy')
    if not callable(fn):
        return 'تعذّر الاتصال بالمنصة'
    try:
        resp = fn('PUT', '/api/bridge/expert-files/settings', json_body={'auto_assign': bool(value), 'by': str(actor)[:120]})
    except Exception:   # noqa: BLE001
        return 'تعذّر الاتصال بالمنصة'
    if _ok(ns, resp):
        _audit(ns, 'expert_file.auto_assign', 'settings', {'auto_assign': bool(value), 'via': 'brain_levels'}, actor)
        return ''
    js = _json_of(resp)
    msg = js.get('error') if isinstance(js, dict) else ''
    return msg if isinstance(msg, str) and msg else 'تعذّر تغيير التوزيع التلقائي على المنصة'


def _ok(ns, resp):
    fn = ns.get('_resp_ok')
    if callable(fn):
        try:
            return bool(fn(resp))
        except Exception:   # noqa: BLE001
            pass
    try:
        return 200 <= (int(resp[1]) if isinstance(resp, tuple) else int(getattr(resp, 'status_code', 200))) < 300
    except Exception:   # noqa: BLE001
        return False


def _json_of(resp):
    try:
        r = resp[0] if isinstance(resp, tuple) else resp
        if isinstance(r, (dict, list)):
            return r
        return r.get_json(silent=True)
    except Exception:   # noqa: BLE001
        return None


# ------------------------------------------------------------------ قرارات للتعلّم والإحصاء

def _since_iso(now, days):
    return _iso(now - datetime.timedelta(days=days))


def decisions(ns, wt, since_iso=None):
    """قرارات المؤسس على النوع، الأحدث أولًا: [('approved'|'edited'|'rejected', at_iso)].
    المنتجات من صفوف `v2_brain_items`، والباقي من `brain_learn`."""
    db = ns['db']
    out = []
    if wt.producer:
        from brain2 import engine
        Item = engine._models(db)[0]
        q = Item.query.filter(Item.producer == wt.producer, Item.status.in_(('approved', 'edited', 'rejected')), Item.decided_at.isnot(None))
        if since_iso:
            dt = _parse(since_iso)
            if dt:
                q = q.filter(Item.decided_at >= dt)
        for r in q.order_by(Item.decided_at.desc()).limit(500).all():
            out.append((r.status, _iso(r.decided_at)))
        return out
    ensure(db)
    sql = 'SELECT outcome, at FROM brain_learn WHERE work_type = :w'
    params = {'w': wt.id}
    if since_iso:
        sql += ' AND at >= :s'
        params['s'] = since_iso
    sql += ' ORDER BY at DESC, id DESC LIMIT 500'
    return [(r[0], r[1]) for r in _rows(db, sql, **params)]


def record(ns, work_type, outcome, ref, actor):
    """قرار من الواجهة على نوع مش منتج. يرجع (status, payload). المنتجات بتتعلّم من صفوفها (٤٠٠ هنا)."""
    wt = get_type(work_type)
    if wt is None:
        return 404, {'error': ERR_UNKNOWN}
    if wt.producer:
        return 400, {'error': 'نوع الشغل ده بيتعلّم من اقتراحاته نفسها'}
    if outcome not in ('approved', 'edited', 'rejected'):
        return 400, {'error': ERR_BAD_LEVEL}
    db = ns['db']
    ensure(db)
    try:
        db.session.execute(text('INSERT INTO brain_learn (id, work_type, outcome, ref, at, by) VALUES (:i, :w, :o, :r, :a, :b)'),
                           {'i': uuid.uuid4().hex, 'w': wt.id, 'o': outcome, 'r': str(ref or '')[:200], 'a': _iso(_now()), 'b': str(actor)[:255]})
        db.session.commit()
    except Exception:   # noqa: BLE001
        db.session.rollback()
        logger.exception('brain2 levels: learn insert failed')
        return 500, {'error': FAIL_AR}
    return 200, {'ok': True}


def streak(ns, wt):
    """عدد الموافقات المتتالية من غير تعديل (من الأحدث)، بعد آخر تغيير مستوى اختاره المؤسس (اختياره بيصفّر العدّ)."""
    row = stored(ns['db'], wt.id)
    since = row[1] if row else None
    n = 0
    for outcome, _at in decisions(ns, wt, since):
        if outcome != 'approved':
            break
        n += 1
    return n


def suppressed_until(db, work_type):
    ensure(db)
    r = _rows(db, 'SELECT answer, until FROM brain_learn_ask WHERE work_type = :w', w=work_type)
    if not r or r[0][0] != 'no':
        return None
    dt = _parse(r[0][1])
    return dt if dt and dt > _now() else None


def learn_state(ns, wt):
    """{n, show}: `show` = النوع مؤهَّل + على «يقترح» + ٨ متتالية + السؤال مش مسكّت."""
    level = level_of(ns, wt)
    if not eligible(wt) or level != 'suggest':
        return {'n': 0, 'show': False}
    n = streak(ns, wt)
    show = n >= LEARN_STREAK and suppressed_until(ns['db'], wt.id) is None
    return {'n': n, 'show': bool(show)}


def answer_learn(ns, work_type, answer, actor):
    """«آه، خليها لوحده» ⇒ المستوى «لوحده» (بنفس الحارس) · «لا، فضّل اسألني» ⇒ يسكّت السؤال ٣٠ يوم."""
    wt = get_type(work_type)
    if wt is None:
        return 404, {'error': ERR_UNKNOWN}
    if answer not in ('yes', 'no'):
        return 400, {'error': ERR_BAD_LEVEL}
    db = ns['db']
    ensure(db)
    if answer == 'yes':
        if not learn_state(ns, wt)['show']:
            return 409, {'error': 'السؤال ده مش مستحق دلوقتي'}
        status, payload = set_level(ns, wt.id, 'alone', actor)
        if status == 200:
            _audit(ns, 'brain.learn_yes', wt.id, {}, actor)
        return status, payload
    until = _iso(_now() + datetime.timedelta(days=LEARN_SUPPRESS_DAYS))
    try:
        db.session.execute(text('DELETE FROM brain_learn_ask WHERE work_type = :w'), {'w': wt.id})
        db.session.execute(text('INSERT INTO brain_learn_ask (work_type, answer, until, by, at) VALUES (:w, \'no\', :u, :b, :a)'),
                           {'w': wt.id, 'u': until, 'b': str(actor)[:255], 'a': _iso(_now())})
        db.session.commit()
    except Exception:   # noqa: BLE001
        db.session.rollback()
        return 500, {'error': FAIL_AR}
    _audit(ns, 'brain.learn_no', wt.id, {'until': until}, actor)
    return 200, {'ok': True, 'until': until}


def prompts(ns):
    """أنواع لازم تظهر لها شريطة السؤال دلوقتي: [{work_type, n, title, unit}]."""
    out = []
    for wt in catalog():
        if not eligible(wt):
            continue
        st = learn_state(ns, wt)
        if st['show']:
            out.append({'work_type': wt.id, 'n': st['n'], 'title': wt.title, 'unit': list(wt.unit)})
    return out


# ------------------------------------------------------------------ إحصاء ٣٠ يوم + العرض

def stats(ns, wt, now=None):
    now = now or _now()
    since = _since_iso(now, STATS_DAYS)
    db = ns['db']
    if wt.external:
        return {'kind': 'external'}
    if lock_of(wt):
        return {'kind': 'locked'}
    level = level_of(ns, wt)
    if level == 'alone':
        n = _rows(db, 'SELECT COUNT(*) FROM alone_log WHERE work_type = :w AND at >= :s', w=wt.id, s=since)[0][0]
        if wt.producer:
            # ملاحظات وحدها بتتسجّل في alone_log، والرأي مش (كتير): نعدّه من صفوفه.
            from brain2 import engine
            Item = engine._models(db)[0]
            cut = _parse(since)
            n2 = Item.query.filter(Item.producer == wt.producer, Item.status == 'done_alone', Item.created_at >= cut).count()
            n = max(n, n2)
        return {'kind': 'times', 'n': int(n)}
    dec = decisions(ns, wt, since)
    if dec:
        approved = sum(1 for o, _ in dec if o in ('approved', 'edited'))
        return {'kind': 'approvals', 'n': approved, 'of': len(dec)}
    return {'kind': 'none'}


def view(ns, now=None):
    """جسم `GET /api/v2/brain/levels`."""
    ensure(ns['db'])
    rows = []
    for wt in catalog():
        row = stored(ns['db'], wt.id)
        lock = lock_of(wt)
        level = level_of(ns, wt)
        item = {'id': wt.id, 'group': wt.group, 'title': wt.title, 'hint': wt.hint, 'level': level, 'default': wt.default,
                'locked': bool(lock), 'lock': lock, 'lock_text': LOCK_TEXT if lock else '',
                'reversible': bool(wt.reversible), 'eligible': eligible(wt), 'levels': list(wt.levels), 'external': wt.external,
                'unit': list(wt.unit), 'stats': stats(ns, wt, now),
                'learn': learn_state(ns, wt) if eligible(wt) else {'n': 0, 'show': False},
                'updated_at': row[1] if row else None, 'updated_by': (row[2] if row else None) or None}
        rows.append(item)
    return {'types': rows, 'groups': [{'key': k, 'title': t} for k, t in GROUPS], 'streak_needed': LEARN_STREAK}


# ------------------------------------------------------------------ سجل «عمل لوحده» + الرجوع

def log_alone(ns, work_type, what, target_ref='', target_label='', undo=None, at=None):
    """صف في `alone_log` بعد ما العقل ينفّذ فعله بنفسه. `undo` = {kind, ...} بيانات الرجوع. يرجع id أو ''."""
    db = ns['db']
    try:
        ensure(db)
        lid = uuid.uuid4().hex
        db.session.execute(text(
            'INSERT INTO alone_log (id, work_type, what, target_ref, target_label, at, undo_json) VALUES (:i, :w, :x, :r, :l, :a, :u)'),
            {'i': lid, 'w': work_type, 'x': str(what)[:300], 'r': str(target_ref)[:200], 'l': str(target_label)[:200],
             'a': _iso(at or _now()), 'u': json.dumps(undo or {}, ensure_ascii=False)})
        db.session.commit()
        return lid
    except Exception:   # noqa: BLE001
        db.session.rollback()
        logger.exception('brain2 levels: alone log failed')
        return ''


def _row_out(r):
    undo = {}
    try:
        undo = json.loads(r[6]) if r[6] else {}
    except (TypeError, ValueError):
        undo = {}
    undone = bool(r[7])
    can, note = can_undo(undo, undone, r[9])
    wt = get_type(r[1])
    return {'id': r[0], 'work_type': r[1], 'title': wt.title if wt else r[1], 'what': r[2], 'target_ref': r[3], 'target_label': r[4], 'at': r[5],
            'undone': undone, 'undone_at': r[7], 'undone_by': r[8] or '', 'can_undo': can, 'undo_note': (r[9] or note or '')}


def can_undo(undo, undone, note=''):
    """(ممكن؟، جملة لو لأ). ما بنقولش «رجّعها» على حاجة اتلغت أو من غير بيانات رجوع."""
    if undone:
        return False, 'اترجّعت قبل كده'
    if not isinstance(undo, dict) or not undo.get('kind'):
        return False, 'مينفعش ترجّعها دلوقتي'
    return True, ''


_LOG_COLS = 'id, work_type, what, target_ref, target_label, at, undo_json, undone_at, undone_by, undo_note'


def alone_rows(ns, day=None, limit=200):
    """صفوف السجل الأحدث أولًا. `day` = 'today' (بتوقيت القاهرة +٢ بالتقريب: من منتصف الليل UTC+٢) أو None للكل."""
    db = ns['db']
    ensure(db)
    sql = 'SELECT %s FROM alone_log' % _LOG_COLS
    params = {}
    if day == 'today':
        n = _now() + datetime.timedelta(hours=2)
        start = datetime.datetime(n.year, n.month, n.day) - datetime.timedelta(hours=2)
        sql += ' WHERE at >= :s'
        params['s'] = _iso(start)
    sql += ' ORDER BY at DESC, id DESC LIMIT %d' % max(1, min(500, int(limit)))
    return [_row_out(r) for r in _rows(db, sql, **params)]


def undo(ns, log_id, actor):
    """رجوع فعل «عمل لوحده». يرجع (status, payload). لو الرجوع مستحيل دلوقتي بنقول كده بوضوح وما بنعلّمهاش اترجّعت."""
    db = ns['db']
    ensure(db)
    r = _rows(db, 'SELECT %s FROM alone_log WHERE id = :i' % _LOG_COLS, i=str(log_id))
    if not r:
        return 404, {'error': 'السجل ده غير موجود'}
    r = r[0]
    try:
        payload = json.loads(r[6]) if r[6] else {}
    except (TypeError, ValueError):
        payload = {}
    can, note = can_undo(payload, bool(r[7]))
    if not can:
        return 409, {'error': note, 'can_undo': False}
    from brain2 import alone
    ok, msg = alone.run_undo(ns, payload, actor)
    if not ok:
        try:
            db.session.execute(text('UPDATE alone_log SET undo_note = :n WHERE id = :i'), {'n': msg[:ALONE_NOTE_MAX], 'i': r[0]})
            db.session.commit()
        except Exception:   # noqa: BLE001
            db.session.rollback()
        return 409, {'error': msg, 'can_undo': False}
    try:
        db.session.execute(text('UPDATE alone_log SET undone_at = :t, undone_by = :b, undo_note = :n WHERE id = :i'),
                           {'t': _iso(_now()), 'b': str(actor)[:255], 'n': (msg or '')[:ALONE_NOTE_MAX], 'i': r[0]})
        db.session.commit()
    except Exception:   # noqa: BLE001
        db.session.rollback()
        logger.exception('brain2 levels: undo mark failed')
    _audit(ns, 'brain.alone_undo', r[0], {'work_type': r[1]}, actor)
    return 200, {'ok': True, 'id': r[0], 'line': msg or 'اترجّعت'}
