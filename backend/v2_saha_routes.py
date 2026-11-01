# -*- coding: utf-8 -*-
"""«الساحة» و«الديوان» و«الفرص» في الداشبورد — مربّعات الإدارة (docs/v2/saha-tiles/SPEC.md). بروكسيات رفيعة فوق جسور المنصة
(`/api/bridge/*`، سرّ الجسر) — ملف واحد يسجّل الجزأين:

    import v2_saha_routes as _v2s_saha; _v2s_saha.register(app, globals())

الساحة (`/api/v2/saha/*`):
    الأخبار      GET news · PUT news/<id> (اعتماد/إلغاء/تعديل) · POST news/run (تشغيل الخط الآلي)
    النقاشات     GET topics (للاختيار) · الآراء GET opinions · POST opinions/<id>/hide · POST opinions/<id>/restore
    الفرص        GET opportunities · GET/PUT/DELETE opportunities/<id> · POST opportunities · POST opportunities/<id>/decide
    الإعداد      GET/PUT settings (رابط دورة «جهّز طلبك بالإنجليزية»)
    الاستيراد    POST opportunities/seed/preview (تجربة بلا كتابة) · POST opportunities/seed/import (حقيقي)
    التذكير      GET reminders (آخر تشغيل) · POST reminders/run (الآن) · POST reminders/cron (كل ساعة، بالسرّ)
الديوان (`/api/v2/diwan/*`):
    الأعمال      GET works · POST works (رفع الفريق) · POST works/<id>/decide · PUT works/<id> (تمييز/إخفاء/قفل التعليقات)
    التعليقات    GET comments · POST comments/<id>/hide
    التحديات     GET/POST challenges · PUT challenges/<id> · POST challenges/<id>/winners
    التقرير      GET report

نفس قواعد `v2_market4_routes.py` بالحرف:
  * الأدمن بس في كل المسارات (فيها إيميلات الناس) — إلا `reminders/cron` فمحروس بسرّ الجسر المشترك (مثل `/api/content/sync-cron` و`/api/ai/agents/run-cron`).
  * المفتاح (`DASH_V2_ENABLED`) مقفول ⇒ ٤٠٤ بلا أي نداء للمنصة · `Cache-Control: no-store` على كل رد.
  * كل كتابة تطلب `confirmed: true` بالظبط قبل أي نداء، ولا تُرسَل للمنصة أبدًا. `by` من التوكن وحده (اللي في الجسم بيتجاهل).
  * الجسم المبعوت قايمة بيضا بالحقول بعد التحقق هنا، والردود مفلترة بقايمة بيضا (ولا حقل زيادة بيعدّي، والروابط http(s) بس).
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) على كتابة ⇒ ٥٠٢ و`no_reply:true` «لم يصل رد…» مش «اترفض».
    نص `detail` العربي من المنصة (٤٠٤ · ٤٠٩ · ٤٢٢) بيعدّي كما هو بنفس الكود.
  * قراءة غابت من المنصة (٤٠٤ «Not Found» بلا ردّ عن عنصر) ⇒ `bridge_missing:true` والشاشة تكتب «غير متاح بعد» مش «لا شيء».
  * تدقيق عند النجاح بس، بالإجراء وبمفاتيح وأعداد (لا نص حر): `saha.*` و`diwan.*` (والرد الضايع `saha.no_reply` / `diwan.no_reply`).
  * الاستيراد: التجربة (`dry_run=true`) لا تكتب ولا تحتاج تأكيدًا؛ الاستيراد الحقيقي يطلب `confirmed:true`. جسم الاستيراد لا يحمل `by`
    (جسم غير فاضي عند المنصة = الـseed نفسه، وإلا ضاع ملف المستودع).
  * التذكير: المسار الدوري لا يكتب تدقيقًا إلا لو أُرسل شيء أو حصل خطأ (٢٤ سطرًا في اليوم ضجيج)، والمنصة مقفولة ⇒ رد `enabled:false` ولا شيء يحدث.
⛔ لا نداء لأي موديل ذكاء من هنا (مسوّدة التحدّي من سطر واحد خارج هذه الجولة). لا يلمس `prerender.py` ولا قالب الموقع.
"""
import datetime
import json
import re
import secrets
from urllib.parse import quote

NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
MISSING_AR = 'هذا القسم غير متاح بعد على المنصة'
BAD_ID_AR = 'معرّف غير صالح'
BAD_REPLY_AR = 'تعذر قراءة رد المنصة'
NOT_SET_AR = 'لم يتم ضبط الربط بعد'

NEWS_CATEGORIES = ('مسابقات وتعيينات', 'قوانين جديدة', 'أحكام', 'أخرى')
NEWS_STATUSES = ('draft', 'published')
TOPIC_STATUSES = ('draft', 'pending_review', 'open', 'merged', 'published', 'rejected', 'archived')
OPINION_STATUSES = ('pending', 'approved', 'rejected', 'all')
KINDS = ('job', 'grant', 'fellowship', 'training', 'competition', 'other')
KIND_FILTERS = ('all', 'grants', 'job', 'training', 'competition', 'other')
REVIEW_STATUSES = ('pending', 'published', 'rejected', 'draft', 'all')
LANGUAGES = ('en', 'fr', 'ar', 'other')
FUNDING = ('full', 'partial', 'none', 'varies')
WORK_KINDS = ('film', 'poem', 'story', 'book', 'other')
WORK_STATUSES = ('pending_review', 'published', 'rejected', 'hidden')
COMMENT_STATUSES = ('visible', 'hidden')
CHALLENGE_STATUSES = ('draft', 'open', 'closed', 'results')
PRIZE_TYPES = ('certificate', 'course_seat', 'featured_week', 'book')

LAST_KEY = 'v2saha_reminders_last'        # آخر تشغيل للتذكير (جدول الإعدادات) — الشاشة تقرأ منه «التذكير مقفول»
SEED_ITEMS_MAX = 500
SEED_BYTES_MAX = 2 * 1024 * 1024
NEWS_RUN_COUNTRIES_MAX = 10

ID_OK = re.compile(r'^[^\s$/\\?#%]{1,200}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
COUNTRY_RE = re.compile(r'^(?:[a-z]{2}|online|various)$', re.I)
ISO2_RE = re.compile(r'^[A-Za-z]{2}$')
HTTPS_RE = re.compile(r'^https://[^\s/$.?#][^\s]*$', re.I)
HTTP_RE = re.compile(r'^https?://[^\s]+$', re.I)

NEWS_FIELDS = ('id', 'title', 'summary', 'body', 'source_name', 'country', 'specialty', 'target_audience', 'status', 'is_published',
               'created_at', 'published_at', 'category', 'featured', 'topic_id')
TOPIC_FIELDS = ('id', 'title', 'status', 'source', 'opinions_count', 'expert_opinions_count', 'created_at', 'news_id', 'source_article_slug')
OPINION_FIELDS = ('id', 'topic_id', 'topic_title', 'author_email', 'body', 'status', 'is_expert', 'author_kind', 'kind', 'created_at', 'edited', 'side')
JOB_FIELDS = ('id', 'title', 'title_en', 'employer', 'place', 'country', 'employment_type', 'specialty', 'body', 'source_label', 'posted_at',
              'expires_at', 'expired', 'logo_initial', 'status', 'opp_status', 'created_at', 'updated_at', 'kind', 'provider', 'language',
              'funding', 'covers_ar', 'deadline', 'deadline_text', 'days_left', 'source_name', 'verified_at', 'featured', 'review_status',
              'reject_reason', 'submitted_by', 'note', 'decided_at', 'seed_id')
WORK_FIELDS = ('id', 'slug', 'title', 'kind', 'creator_email', 'creator_name', 'pen_name', 'publish_as', 'body', 'about', 'book_store_slug',
               'ai_assisted', 'duration_minutes', 'status', 'reject_reason', 'review_note', 'reviewed_by', 'reviewed_at', 'comments_locked',
               'likes', 'comments_count', 'views', 'featured', 'featured_until', 'member_submitted', 'challenge_id', 'licence_version',
               'terms_accepted_at', 'is_active', 'created_at', 'updated_at')
COMMENT_FIELDS = ('id', 'work_id', 'work_title', 'user_email', 'display_name', 'body', 'status', 'created_at', 'hidden_at')
CHALLENGE_FIELDS = ('id', 'slug', 'title', 'brief', 'kind_allowed', 'word_cap', 'opens_at', 'closes_at', 'results_at', 'status', 'created_at',
                    'updated_at', 'entries_count')
REMINDER_COUNTS = ('opportunities', 'sent', 'skipped_already', 'skipped_toggle_off', 'errors')
REPORT_NUMBERS = ('window_days', 'visitors', 'legal_open_share', 'signups', 'share_card_clicks', 'return_7d')


def _ar(n):
    """الرقم بالأرقام الهندية في أي نص يراه المستخدم."""
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


class Bad(Exception):
    def __init__(self, msg, code=422):
        Exception.__init__(self, msg)
        self.msg = msg
        self.code = code


# ------------------------------------------------------------------ أدوات صغيرة
def _pick(d, keys):
    return {k: d[k] for k in keys if k in d} if isinstance(d, dict) else {}


def _http_url(u):
    """رابط يُعرض في الشاشة: http(s) بس. أي شيء تاني ⇒ '' (ولا رابط javascript: يوصل الشاشة)."""
    u = u.strip() if isinstance(u, str) else ''
    return u[:2000] if HTTP_RE.match(u) else ''


def _int(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _rows(d, key):
    """الجسور بعضها يرد قائمة مباشرة وبعضها `{key: [...]}` — نقرأ الاتنين، وغير كده None."""
    if isinstance(d, list):
        return d
    if isinstance(d, dict) and isinstance(d.get(key), list):
        return d[key]
    return None


def _count(d, items):
    return d.get('count') if isinstance(d, dict) and _int(d.get('count')) is not None else len(items)


def _utc(s):
    """نص تاريخ ISO ⇒ datetime بتوقيت UTC، أو None. (بايثون ٣٫٩ لا يقرأ Z)."""
    try:
        dt = datetime.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:   # noqa: BLE001
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


# ------------------------------------------------------------------ التحقق (قبل أي نداء)
def v_text(v, label, mx, mn=0):
    if v is None:
        v = ''
    if not isinstance(v, str):
        raise Bad('%s غير صالح' % label)
    v = v.strip()
    if len(v) < mn or len(v) > mx:
        raise Bad('%s: من %s إلى %s حرف' % (label, _ar(mn), _ar(mx)) if mn else '%s: حتى %s حرف' % (label, _ar(mx)))
    return v


def v_https(v, label, mx=2000):
    """'' مسموح (يمسح). غير ذلك https بس."""
    if v is None:
        return ''
    if not isinstance(v, str):
        raise Bad('%s غير صالح' % label)
    v = v.strip()
    if not v:
        return ''
    if len(v) > mx or not HTTPS_RE.match(v):
        raise Bad('يجب أن يبدأ %s بـ https' % label)
    return v


def v_bool(v, label):
    if not isinstance(v, bool):
        raise Bad('%s: اختر نعم أو لا' % label)
    return v


def v_enum(v, label, choices, allow_empty=False):
    if allow_empty and (v is None or v == ''):
        return ''
    if not isinstance(v, str) or v.strip() not in choices:
        raise Bad('%s: اختر قيمة من القائمة' % label)
    return v.strip()


def v_date(v, label):
    """YYYY-MM-DD حقيقي، أو '' (يمسح)."""
    if v is None or v == '':
        return ''
    if not isinstance(v, str) or not DATE_RE.match(v.strip()):
        raise Bad('%s: اكتب التاريخ بصيغة سنة-شهر-يوم' % label)
    try:
        datetime.date.fromisoformat(v.strip())
    except ValueError:
        raise Bad('%s: تاريخ غير موجود' % label)
    return v.strip()


def v_dt(v, label, allow_empty=False):
    """تاريخ ISO (يوم فقط أو يوم ووقت). '' ⇒ يمسح لو مسموح."""
    if v is None or v == '':
        if allow_empty:
            return ''
        raise Bad('%s مطلوب' % label)
    if not isinstance(v, str) or len(v.strip()) > 40 or _utc(v.strip()) is None:
        raise Bad('%s: تاريخ غير صالح' % label)
    return v.strip()


def v_int(v, label, lo, hi):
    if isinstance(v, bool) or not isinstance(v, int) or v < lo or v > hi:
        raise Bad('%s: رقم صحيح من %s إلى %s' % (label, _ar(lo), _ar(hi)))
    return v


def v_lines(v, label, max_lines, max_len):
    if v is None:
        return []
    if not isinstance(v, list):
        raise Bad('%s غير صالح' % label)
    out = []
    for line in v:
        if not isinstance(line, str):
            raise Bad('%s غير صالح' % label)
        line = line.strip()
        if not line:
            continue
        if len(line) > max_len:
            raise Bad('%s: السطر حتى %s حرف' % (label, _ar(max_len)))
        out.append(line)
    if len(out) > max_lines:
        raise Bad('%s: حتى %s أسطر' % (label, _ar(max_lines)))
    return out


def v_country(v):
    if v is None or v == '':
        return ''
    if not isinstance(v, str) or not COUNTRY_RE.match(v.strip()):
        raise Bad('البلد غير صالح، اختر من القائمة')
    v = v.strip()
    return v.upper() if ISO2_RE.match(v) else v.lower()


# حقول الفرصة: اسم الحقل ⇒ (تسمية عربية، الحد الأقصى، الحد الأدنى)
_OPP_TEXT = {'title': ('العنوان', 200, 3), 'title_en': ('العنوان بالإنجليزية', 200, 0), 'employer': ('الجهة', 200, 0), 'place': ('المكان', 200, 0),
             'provider': ('الجهة المنظِّمة', 200, 0), 'employment_type': ('نوع الدوام', 40, 0), 'source_label': ('تسمية المصدر', 40, 0),
             'body': ('الوصف', 5000, 0), 'specialty': ('التخصص', 80, 0), 'covers_ar': ('ما تغطيه', 300, 0), 'deadline_text': ('نص الموعد', 80, 0),
             'source_name': ('اسم المصدر', 80, 0), 'logo_initial': ('الحرف', 2, 0)}


def clean_opportunity(b, create):
    """جسم الإنشاء/التعديل ⇒ قاموس مرسَل (قايمة بيضا). create ⇒ النوع والنشر والرابط صريحين (لا نشر ضمني للوظيفة)."""
    out = {}
    if create:
        out['kind'] = v_enum(b.get('kind'), 'النوع', KINDS)
        out['publish'] = v_bool(b.get('publish'), 'النشر')
        out['title'] = v_text(b.get('title'), 'العنوان', 200, 3)
    for key in ('title', 'kind', 'publish'):
        if not create and b.get(key) is not None:
            out[key] = (v_text(b[key], 'العنوان', 200, 3) if key == 'title'
                        else v_enum(b[key], 'النوع', KINDS) if key == 'kind' else v_bool(b[key], 'النشر'))
    for key, (label, mx, mn) in _OPP_TEXT.items():
        if key == 'title' or b.get(key) is None:
            continue
        out[key] = v_text(b[key], label, mx, mn)
    if b.get('country') is not None:
        out['country'] = v_country(b['country'])
    if b.get('language') is not None:
        out['language'] = v_enum(b['language'], 'اللغة', LANGUAGES, allow_empty=True)
    if b.get('funding') is not None:
        out['funding'] = v_enum(b['funding'], 'التمويل', FUNDING, allow_empty=True)
    if b.get('eligibility_ar') is not None:
        out['eligibility_ar'] = v_lines(b['eligibility_ar'], 'الشروط', 8, 160)
    for key, label in (('deadline', 'الموعد'), ('verified_at', 'تاريخ التحقق')):
        if b.get(key) is not None:
            out[key] = v_date(b[key], label)
    for key, label in (('official_url', 'الرابط الرسمي'), ('source_url', 'رابط المصدر'), ('image', 'الصورة')):
        if b.get(key) is not None:
            out[key] = v_https(b[key], label)
    if b.get('featured') is not None:
        out['featured'] = v_bool(b['featured'], 'التمييز')
    if create and b.get('expires_in_days') is not None:
        out['expires_in_days'] = v_int(b['expires_in_days'], 'مدة الإعلان بالأيام', 1, 365)
    if create and not (out.get('official_url') or out.get('source_url')):
        raise Bad('الرابط الرسمي https مطلوب')
    if not create and not out:
        raise Bad('لا يوجد تغيير')
    return out


def clean_news_patch(b):
    out = {}
    if b.get('title') is not None:
        out['title'] = v_text(b['title'], 'العنوان', 300, 1)
    if b.get('summary') is not None:
        out['summary'] = v_text(b['summary'], 'الملخص', 2000)
    if b.get('category') is not None:
        out['category'] = v_enum(b['category'], 'التصنيف', NEWS_CATEGORIES)
    if b.get('featured') is not None:
        out['featured'] = v_bool(b['featured'], 'التمييز')
    if b.get('status') is not None:
        out['status'] = v_enum(b['status'], 'الحالة', NEWS_STATUSES)
    if 'cover_url' in b:
        out['cover_url'] = v_https(b.get('cover_url'), 'رابط الغلاف')
    if 'related_product' in b:
        rp = b.get('related_product')
        if rp is None:
            out['related_product'] = None
        else:
            if not isinstance(rp, dict):
                raise Bad('المنتج المرتبط غير صالح')
            out['related_product'] = {'kind': v_enum(rp.get('kind'), 'نوع المنتج', ('book', 'course')),
                                      'slug': v_text(rp.get('slug'), 'رابط المنتج', 120, 1), 'label': v_text(rp.get('label'), 'اسم المنتج', 120)}
    if not out:
        raise Bad('لا يوجد تغيير')
    return out


def clean_news_run(b):
    out = {}
    if b.get('per_country_limit') is not None:
        out['per_country_limit'] = v_int(b['per_country_limit'], 'عدد الأخبار لكل بلد', 1, 8)
    if b.get('derive_topics') is not None:
        out['derive_topics'] = v_bool(b['derive_topics'], 'فتح النقاش')
    if b.get('countries') is not None:
        cs = b['countries']
        if not isinstance(cs, list) or len(cs) > NEWS_RUN_COUNTRIES_MAX or not all(isinstance(c, str) and ISO2_RE.match(c.strip()) for c in cs):
            raise Bad('البلاد غير صالحة')
        out['countries'] = sorted({c.strip().upper() for c in cs})
    return out


def clean_work_upload(b):
    out = {'title': v_text(b.get('title'), 'العنوان', 300, 1), 'kind': v_enum(b.get('kind'), 'النوع', WORK_KINDS),
           'ai_assisted': v_bool(b.get('ai_assisted'), 'الاستعانة بالذكاء')}
    if b.get('creator_name') is not None:
        out['creator_name'] = v_text(b['creator_name'], 'اسم صاحب العمل', 120)
    if b.get('media_url') is not None:
        mu = v_text(b['media_url'], 'رابط العمل', 600)
        if mu and not HTTP_RE.match(mu):
            raise Bad('يجب أن يبدأ رابط العمل بـ http أو https')
        out['media_url'] = mu
    if b.get('body') is not None:
        out['body'] = v_text(b['body'], 'النص', 20000)
    if b.get('about') is not None:
        out['about'] = v_text(b['about'], 'كلمة عن العمل', 600)
    if b.get('cover_url') is not None:
        out['cover_url'] = v_https(b['cover_url'], 'رابط الغلاف', 500)
    if b.get('book_store_slug') is not None:
        out['book_store_slug'] = v_text(b['book_store_slug'], 'رابط الكتاب في المتجر', 120)
    if b.get('duration_minutes') is not None:
        out['duration_minutes'] = v_int(b['duration_minutes'], 'المدة بالدقائق', 1, 600)
    if b.get('featured') is not None:
        out['featured'] = v_bool(b['featured'], 'التمييز')
    if b.get('featured_until') is not None:
        out['featured_until'] = v_dt(b['featured_until'], 'نهاية التمييز', allow_empty=True)
    return out


def clean_work_patch(b):
    out = {}
    if b.get('featured') is not None:
        out['featured'] = v_bool(b['featured'], 'التمييز')
    if 'featured_until' in b and b['featured_until'] is not None:
        out['featured_until'] = v_dt(b['featured_until'], 'نهاية التمييز', allow_empty=True)
    if b.get('status') is not None:
        out['status'] = v_enum(b['status'], 'الحالة', ('hidden', 'published'))
    if b.get('comments_locked') is not None:
        out['comments_locked'] = v_bool(b['comments_locked'], 'قفل التعليقات')
    if not out:
        raise Bad('لا يوجد تغيير')
    return out


def _clean_prizes(v):
    if not isinstance(v, list) or len(v) > 6:
        raise Bad('الجوائز: حتى ٦')
    out = []
    for p in v:
        if not isinstance(p, dict):
            raise Bad('الجوائز غير صالحة')
        row = {'type': v_enum(p.get('type'), 'نوع الجائزة', PRIZE_TYPES), 'label': v_text(p.get('label'), 'اسم الجائزة', 80),
               'ref': v_text(p.get('ref'), 'مرجع الجائزة', 120)}
        place = p.get('place')
        if place is not None:
            row['place'] = v_int(place, 'مركز الجائزة', 1, 3)
        out.append(row)
    return out


def _clean_jury(v):
    if not isinstance(v, list) or len(v) > 6:
        raise Bad('اللجنة: حتى ٦')
    out = []
    for j in v:
        if not isinstance(j, dict):
            raise Bad('اللجنة غير صالحة')
        out.append({'name': v_text(j.get('name'), 'اسم المحكّم', 80, 1), 'title': v_text(j.get('title'), 'صفة المحكّم', 80)})
    return out


def clean_challenge(b, create):
    out = {}
    if create or b.get('title') is not None:
        out['title'] = v_text(b.get('title'), 'عنوان التحدّي', 120, 1)
    if b.get('brief') is not None:
        out['brief'] = v_text(b['brief'], 'وصف التحدّي', 600)
    if b.get('kind_allowed') is not None:
        ks = b['kind_allowed']
        if not isinstance(ks, list) or not 1 <= len(ks) <= 5:
            raise Bad('اختر نوع عمل واحدًا على الأقل')
        out['kind_allowed'] = list(dict.fromkeys(v_enum(k, 'نوع العمل', WORK_KINDS) for k in ks))      # بلا تكرار وبترتيب الإدخال
    if 'word_cap' in b:
        out['word_cap'] = None if b['word_cap'] is None else v_int(b['word_cap'], 'سقف الكلمات', 1, 20000)
    for key, label in (('opens_at', 'تاريخ البدء'), ('closes_at', 'تاريخ الإغلاق')):
        if create or b.get(key) is not None:
            out[key] = v_dt(b.get(key), label)
    if b.get('results_at') is not None:
        out['results_at'] = v_dt(b['results_at'], 'تاريخ النتائج', allow_empty=True)
    if b.get('status') is not None:
        out['status'] = v_enum(b['status'], 'الحالة', ('draft', 'open') if create else ('draft', 'open', 'closed'))
    if b.get('prizes') is not None:
        out['prizes'] = _clean_prizes(b['prizes'])
    if b.get('jury') is not None:
        out['jury'] = _clean_jury(b['jury'])
    if 'sponsor' in b:
        sp = b.get('sponsor')
        if sp is None:
            out['sponsor'] = None
        elif isinstance(sp, dict):
            out['sponsor'] = {'name': v_text(sp.get('name'), 'اسم الراعي', 80, 1), 'logo_url': v_https(sp.get('logo_url'), 'شعار الراعي', 500)}
        else:
            raise Bad('الراعي غير صالح')
    if b.get('cover_url') is not None:
        out['cover_url'] = v_https(b['cover_url'], 'رابط الغلاف', 500)
    if create:
        out.setdefault('kind_allowed', ['story'])
    o, c = out.get('opens_at'), out.get('closes_at')
    if o and c and _utc(c) <= _utc(o):
        raise Bad('يجب أن يكون الإغلاق بعد البدء')
    if out.get('status') == 'open' and create and len(out.get('jury') or []) != 3:
        raise Bad('يجب أن تتكون لجنة التحكيم من ثلاثة أعضاء قبل فتح التحدّي')
    if not create and not out:
        raise Bad('لا يوجد تغيير')
    return out


def clean_winners(b):
    ws = b.get('winners')
    if not isinstance(ws, list) or not 1 <= len(ws) <= 3:
        raise Bad('اختر من فائز إلى ثلاثة')
    out, places, works = [], set(), set()
    for w in ws:
        if not isinstance(w, dict):
            raise Bad('الفائزون غير صالحين')
        place = v_int(w.get('place'), 'المركز', 1, 3)
        wid = v_text(w.get('work_id'), 'العمل', 40, 1)
        if not ID_OK.match(wid):
            raise Bad('العمل غير صالح')
        if place in places or wid in works:
            raise Bad('المراكز والأعمال لا تتكرر')
        places.add(place)
        works.add(wid)
        out.append({'place': place, 'work_id': wid, 'jury_line': v_text(w.get('jury_line'), 'سطر اللجنة', 140)})
    return sorted(out, key=lambda r: r['place'])


def check_seed(seed):
    """شكل الـseed قبل ما نبعته: قاموس فيه items قايمة قواميس ≤٥٠٠ وحجمه معقول. التفاصيل تتحقق عند المنصة."""
    if not isinstance(seed, dict) or not isinstance(seed.get('items'), list):
        raise Bad('الملف غير صالح: لا توجد فيه قائمة عناصر')
    if len(seed['items']) > SEED_ITEMS_MAX:
        raise Bad('الملف أكبر من %s عنصر' % _ar(SEED_ITEMS_MAX))
    if not all(isinstance(i, dict) for i in seed['items']):
        raise Bad('الملف غير صالح: بعض عناصره غير مفهومة')
    if len(json.dumps(seed, ensure_ascii=False)) > SEED_BYTES_MAX:
        raise Bad('الملف كبير جدًا')
    return seed


# ------------------------------------------------------------------ عرض الردود (قوايم بيضا)
def view_news(r):
    row = _pick(r, NEWS_FIELDS)
    row['source_url'] = _http_url(r.get('source_url'))
    row['cover_url'] = _http_url(r.get('cover_url'))
    row['extra_sources'] = [{'name': str(s.get('name') or '')[:200], 'url': _http_url(s.get('url'))} for s in (r.get('extra_sources') or [])
                            if isinstance(s, dict)][:10]
    rp = r.get('related_product')
    row['related_product'] = _pick(rp, ('kind', 'slug', 'label')) if isinstance(rp, dict) else None
    return row


def view_topic(r):
    return _pick(r, TOPIC_FIELDS)


def view_opinion(r):
    return _pick(r, OPINION_FIELDS)


def view_job(r):
    row = _pick(r, JOB_FIELDS)
    for k in ('source_url', 'official_url', 'image'):
        row[k] = _http_url(r.get(k))
    row['eligibility_ar'] = [str(x)[:160] for x in (r.get('eligibility_ar') or []) if isinstance(x, str)][:8]
    return row


def view_work(r):
    row = _pick(r, WORK_FIELDS)
    row['media_url'] = _http_url(r.get('media_url'))
    row['cover_url'] = _http_url(r.get('cover_url'))
    m = r.get('media')
    row['media'] = _pick(m, ('provider', 'video_id')) if isinstance(m, dict) else None
    return row


def view_comment(r):
    return _pick(r, COMMENT_FIELDS)


def view_challenge(r):
    row = _pick(r, CHALLENGE_FIELDS)
    row['prizes'] = [_pick(p, ('type', 'label', 'ref', 'place')) for p in (r.get('prizes') or []) if isinstance(p, dict)]
    row['jury'] = [_pick(j, ('name', 'title')) for j in (r.get('jury') or []) if isinstance(j, dict)]
    sp = r.get('sponsor')
    row['sponsor'] = {'name': sp.get('name', ''), 'logo_url': _http_url(sp.get('logo_url'))} if isinstance(sp, dict) else None
    row['cover_url'] = _http_url(r.get('cover_url'))
    row['winners'] = [_pick(w, ('place', 'work_id', 'jury_line')) for w in (r.get('winners') or []) if isinstance(w, dict)]
    row['awards'] = [_pick(a, ('type', 'label', 'ref', 'place', 'work_id', 'granted')) for a in (r.get('awards') or []) if isinstance(a, dict)]
    return row


def view_report(d):
    out = {k: _num(d.get(k)) for k in REPORT_NUMBERS}          # الغايب أو null يفضل null (مش صفر)
    epc = d.get('entries_per_challenge')
    out['entries_per_challenge'] = ([_pick(e, ('challenge_id', 'slug', 'title', 'entries')) for e in epc if isinstance(e, dict)]
                                    if isinstance(epc, list) else None)
    wa = d.get('works_acceptance')
    out['works_acceptance'] = ({k: _num(wa.get(k)) for k in ('submitted', 'accepted', 'ratio')} if isinstance(wa, dict) else None)
    out['generated_at'] = d.get('generated_at') if isinstance(d.get('generated_at'), str) else None
    return out


def view_reminders(d):
    """رد تشغيل التذكير. `enabled` صريح: غير `true` ⇒ مقفول (الشاشة تكتب «التذكير مقفول»)."""
    d = d if isinstance(d, dict) else {}
    out = {k: (_int(d.get(k)) or 0) for k in REMINDER_COUNTS}
    out['enabled'] = d.get('enabled') is True
    return out


def view_seed(d, dry_run):
    d = d if isinstance(d, dict) else {}
    out = {k: (_int(d.get(k)) or 0) for k in ('created', 'filled', 'skipped_unverified', 'unchanged')}
    out['warnings'] = [str(w)[:300] for w in (d.get('warnings') or []) if isinstance(w, str)][:200]
    out['dry_run'] = bool(dry_run)
    return out


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']
    request = g['request']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def q(x):
        return quote(x, safe='')

    def admin(f):
        """مسار الأدمن: توكن ثم دور، وأي تحقق فاشل ⇒ رسالة عربية بلا نداء."""
        def w(*a, **k):
            try:
                return f(*a, **k)
            except Bad as e:
                return err(e.msg, e.code)
        w.__name__ = f.__name__
        return token_required(roles_required('admin')(w))

    def guard(ids=(), mode='write'):
        """mode: read (بلا جسم) · body (جسم بلا تأكيد) · write (جسم + `confirmed:true`)."""
        closed = g['_v2_closed']()
        if closed:
            return closed, None
        for i in ids:
            if not ID_OK.match(i or ''):
                return err(BAD_ID_AR), None
        body = g['_v2_body']() if mode != 'read' else {}
        if mode == 'write':
            bad = g['_v2_confirmed'](body)
            if bad:
                return bad, None
        return None, body

    def read(path, params=None, item=False):
        resp = g['_platform_proxy']('GET', path, params=params, timeout=20)
        if g['_resp_ok'](resp):
            return resp.get_json(silent=True), None
        if isinstance(resp, tuple) and int(resp[1]) == 404:
            body = resp[0].get_json(silent=True) if hasattr(resp[0], 'get_json') else None
            msg = (body or {}).get('error') if isinstance(body, dict) else None
            if not item or msg in (None, '', 'Not Found'):
                return None, ns((jsonify({'error': MISSING_AR, 'bridge_missing': True}), 404))
        return None, ns(g['_v2_mask_auth'](resp))

    def send(method, path, body, action, target, area, params=None, timeout=25, by=True):
        """نداء كتابة واحد بلا إعادة محاولة ⇒ (بيانات الرد | None، رد الخطأ الجاهز | None)."""
        if by:
            body = dict(body or {})
            body['by'] = (by if isinstance(by, str) else g['_actor_email']())[:80]
        resp = g['_platform_proxy'](method, path, params=params, json_body=body, timeout=timeout)
        if g['_resp_ok'](resp):
            data = resp.get_json(silent=True)
            return (data if isinstance(data, dict) else {}), None
        if g['_ef_no_reply'](resp):
            g['_audit'](area + '.no_reply', target=target, meta={'attempt': action})
            return None, ns((jsonify({'error': NO_REPLY_AR, 'no_reply': True}), 502))
        return None, ns(g['_v2_mask_auth'](resp))

    def done(action, target, meta, payload):
        g['_audit'](action, target=target, meta=meta)
        return ns(jsonify(payload))

    def list_reply(data, key, view, extra=None):
        rows = _rows(data, key)
        if rows is None:
            return err(BAD_REPLY_AR, 502)
        items = [view(r) for r in rows if isinstance(r, dict)]
        out = {'items': items, 'total': _count(data, items)}
        out.update(extra or {})
        return ns(jsonify(out))

    def pick_enum(name, choices, default):
        v = (request.args.get(name) or default).strip()
        return v if v in choices else default

    # ================================================================== الساحة · الأخبار
    @app.route('/api/v2/saha/news', methods=['GET'], endpoint='v2saha_news')
    @admin
    def v2saha_news():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        status = pick_enum('status', NEWS_STATUSES + ('all',), 'draft')
        data, fail = read('/api/bridge/news', {'status': status} if status != 'all' else None)
        return fail or list_reply(data, 'news', view_news, {'status': status})

    @app.route('/api/v2/saha/news/<nid>', methods=['PUT'], endpoint='v2saha_news_edit')
    @admin
    def v2saha_news_edit(nid):
        bad, b = guard([nid])
        if bad:
            return bad
        fields = clean_news_patch(b)
        status = fields.get('status')
        action = 'saha.news_approve' if status == 'published' else 'saha.news_unpublish' if status == 'draft' else 'saha.news_edit'
        data, fail = send('PUT', '/api/bridge/news/%s' % q(nid), fields, action, nid, 'saha')
        if fail:
            return fail
        return done(action, nid, {'fields': sorted(fields)}, view_news(data))

    @app.route('/api/v2/saha/news/run', methods=['POST'], endpoint='v2saha_news_run')
    @admin
    def v2saha_news_run():
        bad, b = guard()
        if bad:
            return bad
        fields = clean_news_run(b)
        data, fail = send('POST', '/api/bridge/news/run', fields, 'saha.news_run', 'news', 'saha', timeout=110)
        if fail:
            return fail
        per = [_pick(p, ('country', 'fetched', 'created', 'errors')) for p in (data.get('per_country') or []) if isinstance(p, dict)]
        total = _int(data.get('total_created')) or 0
        return done('saha.news_run', 'news', {'total_created': total, 'countries': len(per)},
                    {'ok': True, 'ran_at': data.get('ran_at') if isinstance(data.get('ran_at'), str) else None, 'total_created': total, 'per_country': per})

    # ================================================================== الساحة · النقاشات والآراء
    @app.route('/api/v2/saha/topics', methods=['GET'], endpoint='v2saha_topics')
    @admin
    def v2saha_topics():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        status = pick_enum('status', TOPIC_STATUSES + ('all',), 'open')
        data, fail = read('/api/bridge/topics', {'status': status} if status != 'all' else None)
        if fail:
            return fail
        rows = _rows(data, 'topics')
        if rows is None:
            return err(BAD_REPLY_AR, 502)
        items = [view_topic(r) for r in rows if isinstance(r, dict)][:200]
        return ns(jsonify({'items': items, 'total': len(rows), 'status': status}))

    @app.route('/api/v2/saha/opinions', methods=['GET'], endpoint='v2saha_opinions')
    @admin
    def v2saha_opinions():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        status = pick_enum('status', OPINION_STATUSES, 'pending')
        params = {'status': status}
        topic_id = (request.args.get('topic_id') or '').strip()
        if topic_id:
            if not ID_OK.match(topic_id):
                return err(BAD_ID_AR)
            params['topic_id'] = topic_id
        data, fail = read('/api/bridge/opinions', params)
        return fail or list_reply(data, 'opinions', view_opinion, {'status': status})

    def opinion_move(oid, path, action):
        bad, _b = guard([oid])
        if bad:
            return bad
        data, fail = send('POST', '/api/bridge/opinions/%s/%s' % (q(oid), path), {}, action, oid, 'saha')
        if fail:
            return fail
        return done(action, oid, {'status': data.get('status') if isinstance(data.get('status'), str) else ''}, view_opinion(data))

    @app.route('/api/v2/saha/opinions/<oid>/hide', methods=['POST'], endpoint='v2saha_opinion_hide')
    @admin
    def v2saha_opinion_hide(oid):
        return opinion_move(oid, 'reject', 'saha.opinion_hide')          # الإخفاء = رفض الرأي عند المنصة (يخفيه من القراءة والعدّادات)

    @app.route('/api/v2/saha/opinions/<oid>/restore', methods=['POST'], endpoint='v2saha_opinion_restore')
    @admin
    def v2saha_opinion_restore(oid):
        return opinion_move(oid, 'approve', 'saha.opinion_restore')      # الإظهار = اعتماده (المنصة تمنح نقاطه وتبلّغ صاحب النقاش)

    # ================================================================== الساحة · الفرص (وظائف ومنح وزمالات وتدريب ومسابقات وأخرى)
    @app.route('/api/v2/saha/opportunities', methods=['GET'], endpoint='v2saha_opps')
    @admin
    def v2saha_opps():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        review = pick_enum('review_status', REVIEW_STATUSES, 'pending')
        kind = pick_enum('kind', KIND_FILTERS, 'all')
        params = {}
        if review != 'all':
            params['review_status'] = review
        if kind != 'all':
            params['kind'] = kind
        feat = (request.args.get('featured') or '').strip().lower()
        if feat in ('true', 'false'):
            params['featured'] = feat
        data, fail = read('/api/bridge/jobs', params or None)
        return fail or list_reply(data, 'jobs', view_job, {'review_status': review, 'kind': kind})

    @app.route('/api/v2/saha/opportunities/<oid>', methods=['GET'], endpoint='v2saha_opp')
    @admin
    def v2saha_opp(oid):
        bad, _ = guard([oid], mode='read')
        if bad:
            return bad
        data, fail = read('/api/bridge/jobs/%s' % q(oid), item=True)
        if fail:
            return fail
        if not isinstance(data, dict):
            return err(BAD_REPLY_AR, 502)
        return ns(jsonify(view_job(data)))

    @app.route('/api/v2/saha/opportunities', methods=['POST'], endpoint='v2saha_opp_create')
    @admin
    def v2saha_opp_create():
        bad, b = guard()
        if bad:
            return bad
        fields = clean_opportunity(b, create=True)
        data, fail = send('POST', '/api/bridge/jobs', fields, 'saha.opportunity_create', '', 'saha')
        if fail:
            return fail
        row = view_job(data)
        return done('saha.opportunity_create', str(row.get('id') or ''), {'kind': fields['kind'], 'publish': fields['publish']}, row)

    @app.route('/api/v2/saha/opportunities/<oid>', methods=['PUT'], endpoint='v2saha_opp_edit')
    @admin
    def v2saha_opp_edit(oid):
        bad, b = guard([oid])
        if bad:
            return bad
        fields = clean_opportunity(b, create=False)
        action = 'saha.opportunity_publish' if fields.get('publish') is True else 'saha.opportunity_unpublish' if fields.get('publish') is False else 'saha.opportunity_edit'
        data, fail = send('PUT', '/api/bridge/jobs/%s' % q(oid), fields, action, oid, 'saha')
        if fail:
            return fail
        return done(action, oid, {'fields': sorted(fields)}, view_job(data))

    @app.route('/api/v2/saha/opportunities/<oid>', methods=['DELETE'], endpoint='v2saha_opp_delete')
    @admin
    def v2saha_opp_delete(oid):
        bad, _b = guard([oid])
        if bad:
            return bad
        data, fail = send('DELETE', '/api/bridge/jobs/%s' % q(oid), {}, 'saha.opportunity_delete', oid, 'saha')
        if fail:
            return fail
        return done('saha.opportunity_delete', oid, {}, {'ok': True, 'deleted': oid})

    @app.route('/api/v2/saha/opportunities/<oid>/decide', methods=['POST'], endpoint='v2saha_opp_decide')
    @admin
    def v2saha_opp_decide(oid):
        bad, b = guard([oid])
        if bad:
            return bad
        decision = v_enum(b.get('decision'), 'القرار', ('approve', 'reject'))
        fields = {'decision': decision}
        if decision == 'reject':
            fields['reason'] = v_text(b.get('reason'), 'سبب الرفض', 140)
        data, fail = send('POST', '/api/bridge/jobs/%s/decide' % q(oid), fields, 'saha.opportunity_' + decision, oid, 'saha')
        if fail:
            return fail
        return done('saha.opportunity_' + decision, oid, {'decision': decision, 'has_reason': bool(fields.get('reason'))}, view_job(data))

    # ================================================================== الساحة · الإعداد
    @app.route('/api/v2/saha/settings', methods=['GET'], endpoint='v2saha_settings')
    @admin
    def v2saha_settings():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        data, fail = read('/api/bridge/opportunities/settings')
        if fail:
            return fail
        if not isinstance(data, dict):
            return err(BAD_REPLY_AR, 502)
        return ns(jsonify({'prep_course_url': _http_url(data.get('prep_course_url')), 'updated_at': data.get('updated_at') if isinstance(data.get('updated_at'), str) else ''}))

    @app.route('/api/v2/saha/settings', methods=['PUT'], endpoint='v2saha_settings_put')
    @admin
    def v2saha_settings_put():
        bad, b = guard()
        if bad:
            return bad
        if 'prep_course_url' not in b:
            raise Bad('رابط الدورة مطلوب (أو فارغ للمسح)')
        url = v_https(b.get('prep_course_url'), 'رابط الدورة')
        data, fail = send('PUT', '/api/bridge/opportunities/settings', {'prep_course_url': url}, 'saha.opportunity_settings', 'opportunities', 'saha')
        if fail:
            return fail
        return done('saha.opportunity_settings', 'opportunities', {'cleared': not url},
                    {'prep_course_url': _http_url(data.get('prep_course_url')), 'updated_at': data.get('updated_at') if isinstance(data.get('updated_at'), str) else ''})

    # ================================================================== الساحة · استيراد الفرص (تجربة ثم تأكيد)
    def seed_of(b):
        seed = b.get('seed')
        return check_seed(seed) if seed is not None else None          # بلا ملف ⇒ ملف المنصة نفسه

    @app.route('/api/v2/saha/opportunities/seed/preview', methods=['POST'], endpoint='v2saha_seed_preview')
    @admin
    def v2saha_seed_preview():
        bad, b = guard(mode='body')
        if bad:
            return bad
        seed = seed_of(b)
        data, fail = send('POST', '/api/bridge/opportunities/import-seed', seed, 'saha.seed_preview', 'seed', 'saha',
                          params={'dry_run': 'true'}, timeout=60, by=False)
        return fail or ns(jsonify(view_seed(data, True)))              # تجربة: بلا كتابة ولا تدقيق

    @app.route('/api/v2/saha/opportunities/seed/import', methods=['POST'], endpoint='v2saha_seed_import')
    @admin
    def v2saha_seed_import():
        bad, b = guard()
        if bad:
            return bad
        seed = seed_of(b)
        data, fail = send('POST', '/api/bridge/opportunities/import-seed', seed, 'saha.seed_import', 'seed', 'saha', timeout=60, by=False)
        if fail:
            return fail
        view = view_seed(data, False)
        return done('saha.seed_import', 'seed', {'created': view['created'], 'filled': view['filled'], 'skipped_unverified': view['skipped_unverified'],
                                                 'unchanged': view['unchanged'], 'warnings': len(view['warnings']), 'own_file': seed is not None}, view)

    # ================================================================== الساحة · تذكير مواعيد الفرص
    def last_run():
        try:
            row = g['db'].session.get(g['Setting'], LAST_KEY)
            d = json.loads(row.value) if row and row.value else None
        except Exception:   # noqa: BLE001
            return None
        if not isinstance(d, dict):
            return None
        out = {'at': d.get('at') if isinstance(d.get('at'), str) else None, 'ok': d.get('ok') is True, 'trigger': d.get('trigger') if d.get('trigger') in ('cron', 'manual') else None}
        if out['ok']:
            out.update(view_reminders(d))
        else:
            out['no_reply'] = d.get('no_reply') is True        # ضاع الرد (يختلف نصّه عن رفض المنصة)
        return out

    def save_last(snap):
        try:
            db = g['db']
            val = json.dumps(snap, ensure_ascii=False)
            row = db.session.get(g['Setting'], LAST_KEY)
            if row:
                row.value = val
                row.updated_at = datetime.datetime.utcnow()
            else:
                db.session.add(g['Setting'](key=LAST_KEY, value=val))
            db.session.commit()
        except Exception:   # noqa: BLE001 — حفظ آخر تشغيل لا يُسقط التشغيل
            try:
                g['db'].session.rollback()
            except Exception:   # noqa: BLE001
                pass

    def run_reminders(trigger, action):
        """نداء واحد لجسر التذكير ثم حفظ آخر تشغيل. ⇒ (رد جاهز عند الفشل | None، العرض | None)."""
        data, fail = send('POST', '/api/bridge/opportunities/run-reminders', {}, action, 'reminders', 'saha', timeout=60,
                          by='cron' if trigger == 'cron' else True)
        now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
        if fail:
            fresp = fail[0] if isinstance(fail, tuple) else fail
            fbody = fresp.get_json(silent=True) if hasattr(fresp, 'get_json') else None
            save_last({'at': now, 'ok': False, 'trigger': trigger, 'no_reply': isinstance(fbody, dict) and fbody.get('no_reply') is True})
            return fail, None
        view = view_reminders(data)
        save_last(dict(view, at=now, ok=True, trigger=trigger))
        return None, dict(view, ok=True, locked=not view['enabled'], at=now)

    @app.route('/api/v2/saha/reminders', methods=['GET'], endpoint='v2saha_reminders')
    @admin
    def v2saha_reminders():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        last = last_run()         # بلا نداء للمنصة: النداء نفسه يرسل. المقفول يظهر من آخر تشغيل.
        enabled = last.get('enabled') if last and last['ok'] else None
        return ns(jsonify({'last': last, 'enabled': enabled, 'locked': enabled is False}))

    @app.route('/api/v2/saha/reminders/run', methods=['POST'], endpoint='v2saha_reminders_run')
    @admin
    def v2saha_reminders_run():
        bad, _b = guard()
        if bad:
            return bad
        fail, view = run_reminders('manual', 'saha.reminders_run_now')
        if fail:
            return fail
        return done('saha.reminders_run_now', 'reminders', {k: view[k] for k in REMINDER_COUNTS + ('enabled',)}, view)

    @app.route('/api/v2/saha/reminders/cron', methods=['POST'], endpoint='v2saha_reminders_cron')
    def v2saha_reminders_cron():
        # n8n كل ساعة — بسرّ الجسر المشترك (مثل content/sync-cron). السرّ أولًا، ثم المفتاح (مقفول ⇒ ٤٠٤ بلا نداء).
        sec = request.headers.get('X-ELP-Metrics-Secret', '')
        secret = g['PLATFORM_METRICS_SECRET']
        if not (secret and sec and secrets.compare_digest(sec.encode('utf-8'), secret.encode('utf-8'))):
            return ns((jsonify({'error': 'unauthorized'}), 401))
        closed = g['_v2_closed']()
        if closed:
            return closed
        fail, view = run_reminders('cron', 'saha.reminders_cron')
        if fail:
            return fail
        if view['sent'] or view['errors']:
            g['_audit']('saha.reminders_cron', target='reminders', meta={k: view[k] for k in REMINDER_COUNTS}, actor='cron')
        return ns(jsonify(view))

    # ================================================================== الديوان · الأعمال
    @app.route('/api/v2/diwan/works', methods=['GET'], endpoint='v2diwan_works')
    @admin
    def v2diwan_works():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        status = pick_enum('status', WORK_STATUSES, 'pending_review')
        params = {'status': status}
        cid = (request.args.get('challenge_id') or '').strip()
        if cid:
            if not ID_OK.match(cid):
                return err(BAD_ID_AR)
            params['challenge_id'] = cid
        data, fail = read('/api/bridge/creative', params)
        return fail or list_reply(data, 'items', view_work, {'status': status})

    @app.route('/api/v2/diwan/works', methods=['POST'], endpoint='v2diwan_work_upload')
    @admin
    def v2diwan_work_upload():
        bad, b = guard()
        if bad:
            return bad
        fields = clean_work_upload(b)
        data, fail = send('POST', '/api/bridge/creative', fields, 'diwan.work_upload', '', 'diwan')
        if fail:
            return fail
        row = view_work(data)
        return done('diwan.work_upload', str(row.get('id') or ''), {'kind': fields['kind'], 'featured': bool(fields.get('featured'))}, row)

    @app.route('/api/v2/diwan/works/<wid>/decide', methods=['POST'], endpoint='v2diwan_work_decide')
    @admin
    def v2diwan_work_decide(wid):
        bad, b = guard([wid])
        if bad:
            return bad
        decision = v_enum(b.get('decision'), 'القرار', ('approve', 'reject'))
        fields = {'decision': decision}
        if decision == 'reject':
            fields['reason'] = v_text(b.get('reason'), 'سبب الرفض', 140)
            fields['note'] = v_text(b.get('note'), 'ملاحظة', 1000)
        data, fail = send('POST', '/api/bridge/creative/%s/decide' % q(wid), fields, 'diwan.work_' + decision, wid, 'diwan')
        if fail:
            return fail
        return done('diwan.work_' + decision, wid, {'decision': decision, 'has_reason': bool(fields.get('reason'))}, view_work(data))

    @app.route('/api/v2/diwan/works/<wid>', methods=['PUT'], endpoint='v2diwan_work_edit')
    @admin
    def v2diwan_work_edit(wid):
        bad, b = guard([wid])
        if bad:
            return bad
        fields = clean_work_patch(b)
        if 'status' in fields:
            action = 'diwan.work_hide' if fields['status'] == 'hidden' else 'diwan.work_show'
        elif 'comments_locked' in fields:
            action = 'diwan.work_comments_lock' if fields['comments_locked'] else 'diwan.work_comments_unlock'
        else:
            action = 'diwan.work_feature' if fields.get('featured') or fields.get('featured_until') else 'diwan.work_unfeature'
        data, fail = send('PUT', '/api/bridge/creative/%s' % q(wid), fields, action, wid, 'diwan')
        if fail:
            return fail
        return done(action, wid, {'fields': sorted(fields)}, view_work(data))

    # ================================================================== الديوان · التعليقات
    @app.route('/api/v2/diwan/comments', methods=['GET'], endpoint='v2diwan_comments')
    @admin
    def v2diwan_comments():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        status = pick_enum('status', COMMENT_STATUSES, 'visible')
        params = {'status': status}
        wid = (request.args.get('work_id') or '').strip()
        if wid:
            if not ID_OK.match(wid):
                return err(BAD_ID_AR)
            params['work_id'] = wid
        data, fail = read('/api/bridge/diwan/comments', params)
        return fail or list_reply(data, 'items', view_comment, {'status': status})

    @app.route('/api/v2/diwan/comments/<cid>/hide', methods=['POST'], endpoint='v2diwan_comment_hide')
    @admin
    def v2diwan_comment_hide(cid):
        bad, _b = guard([cid])
        if bad:
            return bad
        data, fail = send('POST', '/api/bridge/diwan/comments/%s/hide' % q(cid), {}, 'diwan.comment_hide', cid, 'diwan')
        if fail:
            return fail
        c = data.get('comment')
        return done('diwan.comment_hide', cid, {}, {'ok': True, 'comment': view_comment(c) if isinstance(c, dict) else None})

    # ================================================================== الديوان · التحديات
    @app.route('/api/v2/diwan/challenges', methods=['GET'], endpoint='v2diwan_challenges')
    @admin
    def v2diwan_challenges():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        status = pick_enum('status', CHALLENGE_STATUSES + ('all',), 'all')
        data, fail = read('/api/bridge/diwan/challenges', {'status': status} if status != 'all' else None)
        return fail or list_reply(data, 'items', view_challenge, {'status': status})

    @app.route('/api/v2/diwan/challenges', methods=['POST'], endpoint='v2diwan_challenge_create')
    @admin
    def v2diwan_challenge_create():
        bad, b = guard()
        if bad:
            return bad
        fields = clean_challenge(b, create=True)
        data, fail = send('POST', '/api/bridge/diwan/challenges', fields, 'diwan.challenge_create', '', 'diwan')
        if fail:
            return fail
        row = view_challenge(data)
        return done('diwan.challenge_create', str(row.get('id') or ''), {'status': fields.get('status', 'draft')}, row)

    @app.route('/api/v2/diwan/challenges/<cid>', methods=['PUT'], endpoint='v2diwan_challenge_edit')
    @admin
    def v2diwan_challenge_edit(cid):
        bad, b = guard([cid])
        if bad:
            return bad
        fields = clean_challenge(b, create=False)
        data, fail = send('PUT', '/api/bridge/diwan/challenges/%s' % q(cid), fields, 'diwan.challenge_edit', cid, 'diwan')
        if fail:
            return fail
        return done('diwan.challenge_edit', cid, {'fields': sorted(fields), 'status': fields.get('status', '')}, view_challenge(data))

    @app.route('/api/v2/diwan/challenges/<cid>/winners', methods=['POST'], endpoint='v2diwan_challenge_winners')
    @admin
    def v2diwan_challenge_winners(cid):
        bad, b = guard([cid])
        if bad:
            return bad
        winners = clean_winners(b)
        data, fail = send('POST', '/api/bridge/diwan/challenges/%s/winners' % q(cid), {'winners': winners}, 'diwan.challenge_winners', cid, 'diwan', timeout=60)
        if fail:
            return fail
        certs = [_pick(c, ('place', 'work_id', 'code')) for c in (data.get('certificates') or []) if isinstance(c, dict)]
        ch = data.get('challenge')
        emails = _int(data.get('emails_sent')) or 0
        already = data.get('already') is True
        return done('diwan.challenge_winners', cid, {'winners': len(winners), 'certificates': len(certs), 'emails_sent': emails, 'already': already},
                    {'ok': True, 'already': already, 'challenge': view_challenge(ch) if isinstance(ch, dict) else None, 'certificates': certs, 'emails_sent': emails})

    # ================================================================== الديوان · التقرير
    @app.route('/api/v2/diwan/report', methods=['GET'], endpoint='v2diwan_report')
    @admin
    def v2diwan_report():
        bad, _ = guard(mode='read')
        if bad:
            return bad
        raw = (request.args.get('days') or '30').strip()
        days = int(raw) if raw.isdigit() and 1 <= int(raw) <= 365 else 30
        data, fail = read('/api/bridge/diwan/report', {'days': days})
        if fail:
            return fail
        if not isinstance(data, dict):
            return err(BAD_REPLY_AR, 502)
        return ns(jsonify(view_report(data)))
