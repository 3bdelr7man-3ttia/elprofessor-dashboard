# -*- coding: utf-8 -*-
"""«القاموس» — المصطلحات القانونية بثلاث لغات (docs/v2/glossary/SPEC.md). ملف مستقل كي لا يلمس غيره.

    import v2_glossary_routes as _v2s_glossary; _v2s_glossary.register(app, globals())

`ns` = `globals()` الخاصة بـ app.py: كل اسم يُبحث عنه وقت الطلب فلا يستورد هذا الملف `app` أبدًا. النموذج `GlossaryTerm` في app.py.

الإدارة (أدمن بس، `/api/v2/content/glossary`):
  GET    /                       قائمة + بحث (عربي · إنجليزي · فرنسي · التعريف) + مجال («أخرى» منها) + حالة (مسودة · تحت التأكيد · مؤكّد) + مراجعة + عدّادات
  POST   /                       مصطلح جديد (مسودة)             GET /<id>  مصطلح
  PUT    /<id>                   تعديل بالفرق فقط
  POST   /<id>/publish | unpublish      نشر وإلغاء نشر (النشر بلا ختم ⇒ «تحت التأكيد»)
  POST   /<id>/review | unreview        ختم «راجعه» (الاسم والصفة وموافقة ظهور الاسم) وإزالته
  DELETE /<id>                   مسودة لم تُنشر قط فقط
  POST   /seed/preview           معاينة الاستيراد (لا كتابة ولا تأكيد)     POST /seed/import   الاستيراد (يطلب التأكيد)
  GET    /topics                 نقاشات «الساحة» المنشورة (من جسر المنصة)
  POST   /<id>/attach-topic | detach-topic    ربط نقاش موجود بالمصطلح وفصله
  POST   /<id>/saha-topic/preview | /saha-topic/open       فتح نقاش جديد في «الساحة» للمصطلح المنشور (معاينة بلا كتابة · ثم فتح بتأكيد)
  POST   /saha-topics/bulk/preview | /bulk/open             نفسه لكل المنشور بلا نقاش (دفعات ≤٥٠ في نداء المنصة)
  GET|PUT /settings              إعدادان: `glossary.require_review` (الافتراضي مغلق) و`glossary.expert_reviews_enabled` (الافتراضي مغلق)
  GET    /reviews                قائمة مراجعات المتخصصين (status · kind) + عدّاد                    ┐ مغلقة (٤٠٤) ما دام
  POST   /reviews/<id>/approve | reject      «اعتمد» (تأكيد ⇒ يختم المصطلح) · «ارفض»                ┘ `expert_reviews_enabled` مغلقًا
الفيد العام (بلا توكن، منشور فقط، حقول عامة فقط، no-store): GET /api/content/glossary
الاستمارة العامة (بلا توكن): POST /api/public/expert-reviews — مراجعة متخصص (kind = glossary_term | course | track)؛ مغلقة (٤٠٤ قبل قراءة الجسم) ما دام الإعداد مغلقًا

القواعد (نفس `v2_saha_link_routes.py` و`v2_market4_routes.py`):
  * أدمن بس · المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤ بلا أي أثر · `no-store`.
  * كل كتابة تطلب `confirmed: true` بالضبط (لا يُخزَّن ولا يُمرَّر) · `by` من التوكن وحده (في سجل التدقيق) · قوائم بيضاء للحقول داخلًا وخارجًا.
  * تدقيق عند النجاح بس. نداء الجسر اللي ضاع رده ⇒ ٥٠٢ و`no_reply`.
  * قرار المؤسس ٢٠٢٦-١١-٠١ (بعد الجولة ٢): «حتى القاموس مش لازم نبني تحتيه إنه أكّد وما تأكّدش… نفتحه للنقاش ونلمّ الاعتراضات». فالمراجعات مطفأة لا محذوفة:
    `glossary.expert_reviews_enabled` (الافتراضي مغلق، لا يُكتب من `PUT /api/settings` العام) يحجب الاستمارة العامة وصندوق المراجعات وصف الجرس
    وحقول المراجعة من الفيد؛ والواجهة تعرض «مسودة / منشور» فقط، و«راجعه» ختم داخلي في المحرّر لا يصل الموقع. شرط المراجعة يتعطّل معه.
  * كل مصطلح منشور يُفتح له نقاش في «الساحة» عبر مسار البذر بلا نموذج ذكاء (`POST /api/bridge/topics/seed`) — `apply:false` معاينة، `apply:true` فتح.
  * الحالات: draft (للمؤسس وحده) ⇒ under_review (منشور وظاهر بلا ختم) ⇒ confirmed (منشور وعليه ختم). «منشور» = أيٌّ من الأخيرين.
    تعديل جوهري لمصطلح مؤكَّد يمسح الختم فيرجع «تحت التأكيد» ويبقى ظاهرًا. `glossary.require_review` (الافتراضي مغلق): مفعّل = لا نشر بلا ختم (٤٠٩)
    وتعديل جوهري لمؤكَّد يرجعه مسودة.
  * الاستمارة العامة لا تخزّن IP ولا متصفحًا؛ حدّ المعدّل في الذاكرة فقط.
  * أي تغيير يمسّ صفحة منشورة (أو يسقطها) يطلب توليد الصفحات في الخلفية — وفشل التوليد لا يُسقط الحفظ أبدًا.
⛔ لا يعدّل `prerender.py` ولا أي مسار من `/api/content/articles`.
"""
import datetime
import json
import os
import re

SLUG_RE = re.compile(r'^[a-z](?:[a-z0-9-]{0,62}[a-z0-9])?$')
RESERVED_SLUGS = ('index',)                                # glossary/index.html صفحة الفهرس نفسها (prerender.GLOSSARY_RESERVED)
TOPIC_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')       # نفس SAHA_TOPIC_ID_RE في prerender.py
SAHA_APP_URL = 'https://app.elprofessor.net/?page=saha&topic='
_LIVE = ('open', 'published')                              # النقاش علنيّ فعلًا
SETTING_KEY = 'glossary.require_review'
EXPERT_KEY = 'glossary.expert_reviews_enabled'            # الافتراضي مغلق: لا استمارة ولا صندوق ولا جرس ولا حقول مراجعة في الفيد
SEED_CAP = 50                                              # أكبر عدد عناصر في نداء بذر واحد عند المنصة
TOPIC_TAG = 'القاموس'
TOPIC_TITLE_TAIL = ': هل الترجمة والتعريف دقيقان؟'
TOPIC_QUESTION = 'هل الترجمة أو التعريف دقيق في نظامك القانوني؟ اكتب اعتراضك أو اقتراحك.'
SITE_PAGE = 'https://elprofessor.net/glossary/'
STATES = ('draft', 'under_review', 'confirmed')
PUBLISHED = ('under_review', 'confirmed')                  # «منشور» = ظاهر في الفيد والموقع

AREAS = (
    ('contracts', 'عقود'), ('litigation', 'تقاضٍ'), ('corporate', 'شركات'), ('general', 'عام'),
    ('arbitration', 'تحكيم'), ('criminal', 'جنائي'), ('ip', 'ملكية فكرية'), ('labor', 'عمل'),
    ('family', 'أسرة'), ('other', 'أخرى'),
)
AREA_CODES = tuple(a for a, _ in AREAS)
AREA_LABEL = dict(AREAS)

# حقول جوهرية: تعديلها على مصطلح مُراجَع يمسح الختم (والمنشور يرجع مسودة حين المراجعة مطلوبة).
SUBSTANTIVE = ('ar', 'en', 'fr', 'definition_ar', 'example_en', 'example_ar', 'false_friend_note_ar', 'countries_note_ar')
EDITABLE = ('slug', 'ar', 'en', 'fr', 'area', 'definition_ar', 'example_en', 'example_ar',
            'false_friend_note_ar', 'countries_note_ar', 'related')
MAX_LEN = {'ar': 300, 'en': 300, 'fr': 300, 'definition_ar': 3000, 'example_en': 1500, 'example_ar': 1500,
           'false_friend_note_ar': 2000, 'countries_note_ar': 2000}
REQUIRED = ('ar', 'en', 'definition_ar')
RELATED_MAX = 20
IMPORT_MAX = 500
SOURCES = ('seed', 'course1', 'upload')
_DATA_FILES = {'seed': 'glossary_seed.json', 'course1': 'glossary_course1.json'}
_URL_RE = re.compile(r'https?://|www\.', re.I)
_CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
# محارف الاتجاه (LRM/RLM · LRE…RLO · LRI…PDI): تقلب ما بعدها في الصفحة، فتُحذف من كل نص يأتي من الزائر أو يصير ختمًا عامًّا
_BIDI_RE = re.compile('[\u200e\u200f\u202a-\u202e\u2066-\u2069]')


def strip_ctrl(v):
    return _BIDI_RE.sub('', _CTRL_RE.sub('', v))

# استمارة المتخصصين العامة (POST /api/public/expert-reviews)
KINDS = ('glossary_term', 'course', 'track')
SPECIALTIES = (('law_practice', 'محاماة'), ('judiciary', 'قضاء'), ('legal_translation', 'ترجمة قانونية'),
               ('law_teaching', 'تدريس القانون'), ('corporate_counsel', 'مستشار شركات'), ('other', 'أخرى'))
SPECIALTY_CODES = tuple(c for c, _ in SPECIALTIES)
SPECIALTY_LABEL = dict(SPECIALTIES)
VERDICTS = ('confirm', 'suggest')
REVIEW_STATUSES = ('pending', 'approved', 'rejected')
REF_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$')  # عقد الجلسة الأساسية لـcourse/track: حروف صغيرة وأرقام وشرطة، حتى ٨٠
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PENDING_PER_REF = 3                                        # أكثر عدد صفوف معلّقة بأسماء مختلفة لنفس (البريد، النوع، العنصر)
LOOSE_LIMIT, STRICT_LIMIT, WINDOW = 60, 5, 3600            # نفس حدّي /api/messages: فضفاض لكل نداء وصارم للصحيح
RATE_AR = 'محاولات كثيرة، جرّب بعد قليل'

CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NOT_FOUND_AR = 'المصطلح غير موجود'
NOT_FOUND_ROUTE_AR = 'غير موجود'
NEEDS_REVIEW_AR = 'يُنشر بعد أن يراجعه خبير'
BAD_PUBLIC_NAME_AR = 'اختر: يظهر اسم المراجع أو لا يظهر'
ALREADY_PUBLISHED_AR = 'المصطلح منشور بالفعل'
NOT_PUBLISHED_AR = 'المصطلح غير منشور'
NOT_REVIEWED_AR = 'المصطلح لم يُراجَع بعد'
SLUG_FROZEN_AR = 'رابط المصطلح لا يتغيّر بعد أول نشر'
SLUG_TAKEN_AR = 'هذا الرابط مستخدم لمصطلح آخر'
RESERVED_SLUG_AR = 'هذا الرابط محجوز لصفحة الفهرس، اختر رابطًا آخر'
BAD_SLUG_AR = 'الرابط حروف إنجليزية صغيرة وأرقام وشرطات فقط (مثال: force-majeure)'
BAD_AREA_AR = 'اختر مجالًا من القائمة'
BAD_REVIEWER_AR = 'اكتب اسم المراجع (حرفان على الأقل) وصفته'
NO_URL_AR = 'لا تضع روابط في النص'
DELETE_ONLY_DRAFT_AR = 'يُحذف المصطلح قبل أول نشر فقط؛ بعده ألغِ نشره'
HAS_TOPIC_AR = 'لهذا المصطلح نقاش مرتبط بالفعل'
NO_TOPIC_AR = 'لا نقاش مرتبط بهذا المصطلح'
BAD_TOPIC_AR = 'معرّف النقاش غير صالح'
TOPIC_NOT_LIVE_AR = 'هذا النقاش غير موجود أو غير منشور في الساحة'
BAD_SOURCE_AR = 'اختر مصدر الاستيراد'
BAD_UPLOAD_AR = 'الملف يجب أن يحوي قائمة مصطلحات (items)'
TOO_MANY_AR = 'الملف يتجاوز ٥٠٠ مصطلح'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة ثم أعد المحاولة.'
SEED_NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة ثم أعد المحاولة؛ إن كان النقاش قد فُتح فسيُربط بالمصطلح ولن يتكرر.'
TOPIC_NOT_PUBLISHED_AR = 'انشر المصطلح أولًا ثم افتح نقاشه'
BAD_TOPIC_TITLE_AR = 'عنوان النقاش من ٣ إلى ٢٠٠ حرف'
BAD_TOPIC_QUESTION_AR = 'اكتب سؤال النقاش (حتى ٥٠٠٠ حرف)'
TOPIC_EXISTS_NOT_LIVE_AR = 'يوجد نقاش بنفس العنوان لكنه غير منشور في الساحة'
TOPIC_DUP_IN_BATCH_AR = 'تعذّر فتح النقاش لهذا المصطلح بسبب عنوان مكرر، غيّر عنوانه ثم أعد المحاولة'
TOPIC_TITLE_LONG_AR = 'عنوان النقاش أطول من ٢٠٠ حرف، افتح نقاشه من شاشة المصطلح بعنوان أقصر'
TOPIC_PLAN_NEW_AR = 'سيُفتح نقاش جديد في الساحة'
TOPIC_PLAN_LINK_AR = 'يوجد نقاش بنفس العنوان، سيُربط به'
NO_ELIGIBLE_AR = 'لا مصطلحات منشورة بلا نقاش'
PLATFORM_DOWN_AR = 'تعذّر الاتصال بالمنصة'
PLATFORM_REFUSED_AR = 'المنصة رفضت البيانات المرسلة'
BAD_REPLY_AR = 'تعذّر قراءة رد المنصة'
BAD_SETTING_AR = 'القيمة نعم أو لا'
NO_REVIEW_AR = 'المراجعة غير موجودة'
REVIEW_DECIDED_AR = 'سبق البتّ في هذه المراجعة'
REVIEW_TERM_GONE_AR = 'المصطلح لم يعد موجودًا'
BAD_NOTE_AR = 'الملاحظة نص حتى ٥٠٠ حرف'


# ——————————————————————————————————————————————— دوال نقية (تُختبر بلا تطبيق)

def valid_slug(x):
    return isinstance(x, str) and bool(SLUG_RE.match(x)) and x not in RESERVED_SLUGS


def slugify(text):
    """ASCII kebab من نص إنجليزي؛ '' لو لم يبقَ شيء صالح. الاسم المحجوز (index) يصير index-term."""
    s = re.sub(r'[^a-z0-9]+', '-', (text or '').lower()).strip('-')[:64].strip('-')
    if s in RESERVED_SLUGS:
        s += '-term'
    return s if SLUG_RE.match(s) else ''


def _clean_text(v, field):
    """(قيمة | None، مشكلة | None). نص حر: يُقصّ، بلا روابط ولا محارف تحكّم، وبحدّ طول."""
    if v is None:
        return None, None
    if not isinstance(v, str):
        return None, 'نص مطلوب (%s)' % field
    v = _CTRL_RE.sub('', v).strip()
    if not v:
        return None, None
    if _URL_RE.search(v):
        return None, NO_URL_AR
    if len(v) > MAX_LEN[field]:
        return None, 'النص أطول من %d حرفًا (%s)' % (MAX_LEN[field], field)
    return v, None


def clean_related(v):
    """(قائمة slugs مرتبة بلا تكرار | None، مشكلة | None)."""
    if v is None:
        return [], None
    if not isinstance(v, list) or len(v) > RELATED_MAX:
        return None, 'المصطلحات القريبة قائمة حتى %d' % RELATED_MAX
    out = []
    for x in v:
        if not isinstance(x, str) or not SLUG_RE.match(x.strip()):
            return None, 'رابط مصطلح قريب غير صالح'
        x = x.strip()
        if x not in out:
            out.append(x)
    return out, None


def clean_fields(raw, present_only=False, need_slug=False):
    """يفحص حقول المصطلح من جسم/صف خام. ⇒ (حقول نظيفة، [مشاكل]).
    present_only: للتعديل — لا يفحص إلا الحقول الموجودة في raw. غير ذلك (إنشاء/استيراد) يطلب الثلاثة المطلوبة والمجال.
    ⛔ لا يأخذ إلا الحقول المسموحة؛ أي مفتاح آخر (status · reviewed_* · saha_topic_id…) يُتجاهل."""
    out, problems = {}, []
    keys = [k for k in EDITABLE if (k in raw or not present_only)]
    for k in keys:
        v = raw.get(k)
        if k == 'slug':
            if v is None or (isinstance(v, str) and not v.strip()):
                if need_slug:
                    problems.append(BAD_SLUG_AR)
                continue
            if not isinstance(v, str) or not SLUG_RE.match(v.strip()):
                problems.append(BAD_SLUG_AR)
            elif v.strip() in RESERVED_SLUGS:
                problems.append(RESERVED_SLUG_AR)
            else:
                out['slug'] = v.strip()
        elif k == 'area':
            if not isinstance(v, str) or v.strip() not in AREA_CODES:
                problems.append(BAD_AREA_AR)
            else:
                out['area'] = v.strip()
        elif k == 'related':
            rel, p = clean_related(v)
            if p:
                problems.append(p)
            else:
                out['related'] = rel
        else:
            val, p = _clean_text(v, k)
            if p:
                problems.append('%s: %s' % (k, p))
            elif val is None and k in REQUIRED:
                problems.append('الحقل مطلوب: %s' % k)
            else:
                out[k] = val
    return out, problems


def clean_row(raw, index=0):
    """صف مستورد (seed/course1/upload). يقبل `id` أو `slug`، ويشتقّ الرابط من الإنجليزي لو غاب. ⇒ (حقول، [مشاكل])."""
    if not isinstance(raw, dict):
        return None, ['الصف ليس كائنًا']
    row = dict(raw)
    sid = row.get('id') if row.get('id') is not None else row.get('slug')
    if sid is None or (isinstance(sid, str) and not sid.strip()):
        row['slug'] = slugify(row.get('en') if isinstance(row.get('en'), str) else '')
    else:
        row['slug'] = sid
    fields, problems = clean_fields(row, need_slug=True)
    return fields, problems


def load_source(name, base=None):
    """الصفوف الخام لمصدر مدمج (seed | course1) من backend/data. None لو الملف غاب أو لم يُقرأ."""
    path = os.path.join(base or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'), _DATA_FILES[name])
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    items = data.get('items') if isinstance(data, dict) else data
    return items if isinstance(items, list) else None


def reviewed(t):
    return bool(t.reviewed_at and t.reviewed_by_name and t.reviewed_by_role)


def is_published(t):
    return (t.status or 'draft') in PUBLISHED


def settle(t):
    """حالة المنشور تتبع الختم: عليه ختم ⇒ confirmed، بلا ختم ⇒ under_review. المسودة تبقى مسودة."""
    if is_published(t):
        t.status = 'confirmed' if reviewed(t) else 'under_review'


def clear_stamp(t):
    t.reviewed_by_name = t.reviewed_by_role = t.reviewed_at = None
    t.reviewer_name_public = False


def related_of(t):
    try:
        v = json.loads(t.related or '[]')
    except ValueError:
        return []
    return [x for x in v if isinstance(x, str)] if isinstance(v, list) else []


def iso(d):
    return d.isoformat() if d else None


def serialize_admin(t, frozen=None):
    return {
        'id': t.id, 'slug': t.slug, 'ar': t.ar, 'en': t.en, 'fr': t.fr or '', 'area': t.area,
        'area_label': AREA_LABEL.get(t.area, AREA_LABEL['other']),
        'definition_ar': t.definition_ar, 'example_en': t.example_en or '', 'example_ar': t.example_ar or '',
        'false_friend_note_ar': t.false_friend_note_ar or '', 'countries_note_ar': t.countries_note_ar or '',
        'related': related_of(t), 'status': t.status if t.status in STATES else 'draft', 'published': is_published(t),
        'reviewed': reviewed(t), 'reviewed_by_name': t.reviewed_by_name or None, 'reviewed_by_role': t.reviewed_by_role or None,
        'reviewer_name_public': bool(t.reviewer_name_public),
        'reviewed_at': iso(t.reviewed_at), 'saha_topic_id': t.saha_topic_id or None,
        'source': t.source or 'manual', 'slug_frozen': t.published_at is not None,
        'created_at': iso(t.created_at), 'updated_at': iso(t.updated_at), 'published_at': iso(t.published_at),
    }


def serialize_public(t, published_by_slug, reviews=False):
    """حقول الفيد العام. ⛔ بلا إيميلات ولا حالة داخلية ولا مصدر.
    `reviews` = `glossary.expert_reviews_enabled`. مغلقًا (الافتراضي): لا مفاتيح `review_state` ولا `reviewed_by_name|role` ولا `reviewed_at` أصلًا،
    وملاحظة الدول تظهر متى وُجدت (المصطلح يُنشر ويُفتح للنقاش). مفعّلًا (شكل الجولة ٢): `review_state` = under_review | confirmed،
    وملاحظة الدول لا تُنشر إلا لمؤكَّد، واسم المراجع وصفته لا يُنشران إلا لمؤكَّد وافق على ظهور اسمه (الخادم يفرضها هنا لا الصفحة)."""
    rev = t.status == 'confirmed' and reviewed(t)
    named = rev and bool(t.reviewer_name_public)
    rel = []
    for s in related_of(t):
        r = published_by_slug.get(s)
        if r is not None and r.id != t.id:
            rel.append({'slug': r.slug, 'ar': r.ar, 'en': r.en})
    row = {
        'id': t.id, 'slug': t.slug, 'ar': t.ar, 'en': t.en, 'fr': t.fr or None, 'area': t.area,
        'area_label': AREA_LABEL.get(t.area, AREA_LABEL['other']),
        'definition_ar': t.definition_ar, 'example_en': t.example_en or None, 'example_ar': t.example_ar or None,
        'false_friend_note_ar': t.false_friend_note_ar or None,
        'countries_note_ar': (t.countries_note_ar or None) if (rev or not reviews) else None,
        'related': rel,
    }
    if reviews:
        row.update({
            'review_state': 'confirmed' if rev else 'under_review',
            'reviewed_by_name': t.reviewed_by_name if named else None,
            'reviewed_by_role': t.reviewed_by_role if named else None,
            'reviewed_at': iso(t.reviewed_at) if rev else None,
        })
    row.update({
        'saha_topic_id': t.saha_topic_id if (t.saha_topic_id and TOPIC_ID_RE.match(t.saha_topic_id)) else None,
        'published_at': iso(t.published_at), 'updated_at': iso(t.updated_at),
    })
    return row


def flag_on(Setting, key):
    """إعداد منطقي في جدول settings: غياب الصف أو قيمة غير مفهومة = مغلق، ولا يفتحه إلا `1/true/on/yes/نعم`."""
    s = Setting.query.get(key)
    if s is None or s.value is None:
        return False
    return str(s.value).strip().lower() in ('1', 'true', 'on', 'yes', 'نعم')


def reviews_enabled(Setting):
    """مراجعات المتخصصين مفعّلة؟ الافتراضي لا (قرار المؤسس ٢٠٢٦-١١-٠١). يقرؤه app.py لصف الجرس أيضًا."""
    return flag_on(Setting, EXPERT_KEY)


# ——————————————————————————————————————————————— نقاش «الساحة» لكل مصطلح (مسار البذر بلا نموذج ذكاء)

def default_topic_title(t):
    """«<العربي> (<الإنجليزي>): هل الترجمة والتعريف دقيقان؟». ليس فريدًا بالضرورة: الفريد في القاموس هو الـslug وحده، فمصطلحان
    بالزوج نفسه (عربي وإنجليزي، أو ما يطويه تطبيع المنصة إلى عنوان واحد) يخرجان بعنوان واحد. في الدفعة الواحدة يُعامَل الثاني
    كخطأ (`duplicate_in_batch`) فلا يُربط، وفي تشغيل لاحق يردّ البذر `duplicate_title` فيُربط بنقاش الأول، والتجربة تُظهر ذلك
    «سيُربط بموجود» قبل أي كتابة. لتمييزهما يُعدَّل العنوان في ورقة المصطلح قبل الفتح."""
    return '%s (%s)%s' % ((t.ar or '').strip(), (t.en or '').strip(), TOPIC_TITLE_TAIL)


def topic_body(t):
    """نص المنصة تحت السؤال: التعريف (+ المثال لو وُجد) ورابط صفحة المصطلح. ⛔ لا `source_article_slug`: المنصة تعرضه «من مقال» برابط /blog/."""
    parts = [(t.definition_ar or '').strip()]
    ex = [x.strip() for x in (t.example_en, t.example_ar) if x and x.strip()]
    if ex:
        parts.append('مثال:\n' + '\n'.join(ex))
    parts.append(SITE_PAGE + t.slug + '.html')
    return '\n\n'.join(p for p in parts if p)


def topic_item(t, title=None, question=None):
    """(عنصر البذر | None، رسالة عربية | None). العنوان والسؤال الافتراضيان من المصطلح، والمرسَل يُفحص بحدود المنصة."""
    title = default_topic_title(t) if title is None else title
    title = strip_ctrl(title).strip() if isinstance(title, str) else ''
    if not 3 <= len(title) <= 200:
        return None, BAD_TOPIC_TITLE_AR
    question = TOPIC_QUESTION if question is None else question
    question = strip_ctrl(question).strip() if isinstance(question, str) else ''
    if not 1 <= len(question) <= 5000:
        return None, BAD_TOPIC_QUESTION_AR
    return {'title': title, 'question': question, 'body': topic_body(t), 'tags': [TOPIC_TAG]}, None


def align_seed(titles, data):
    """يطابق ردّ البذر (created/skipped) بعناصر الطلب بالعنوان (المنصة تردّه مقصوصًا كما أُرسل). ⇒ قائمة بنفس الترتيب من
    ('created', صف) | ('skipped', صف) أو None لو الرد ناقص أو لا يطابق. العنوان المتكرر يستهلك صفوفه بالترتيب."""
    if not isinstance(data, dict):
        return None
    pools = {'created': {}, 'skipped': {}}
    for kind in pools:
        rows = data.get(kind)
        if not isinstance(rows, list):
            return None
        for r in rows:
            if not isinstance(r, dict) or not isinstance(r.get('title'), str):
                return None
            pools[kind].setdefault(r['title'], []).append(r)
    out = []
    for t in titles:
        if pools['created'].get(t):
            out.append(('created', pools['created'][t].pop(0)))
        elif pools['skipped'].get(t):
            out.append(('skipped', pools['skipped'][t].pop(0)))
        else:
            return None
    return out


def clean_submission(d):
    """(حقول نظيفة | None، رسالة عربية | None). يفحص جسم الاستمارة العامة. ⛔ لا يقرأ إلا الحقول المعلنة؛ ولا عنوان IP ولا متصفح."""
    def one_line(v, lo, hi):
        v = re.sub(r'\s+', ' ', strip_ctrl(v)).strip() if isinstance(v, str) else ''
        return v if lo <= len(v) <= hi and not _URL_RE.search(v) and '@' not in v else None
    kind = d.get('kind')
    if kind not in KINDS:
        return None, 'نوع العنصر غير صالح'
    ref = d.get('ref')
    ref = ref.strip() if isinstance(ref, str) else ''
    if not REF_RE.match(ref) or (kind == 'glossary_term' and not valid_slug(ref)):
        return None, 'العنصر المراد مراجعته غير صالح'
    name = one_line(d.get('name'), 2, 80)
    if not name:
        return None, 'اكتب اسمك (حرفان على الأقل، بلا روابط ولا بريد)'
    email = d.get('email')
    email = email.strip().lower() if isinstance(email, str) else ''
    if not email or len(email) > 254 or not EMAIL_RE.match(email):
        return None, 'اكتب بريدًا إلكترونيًّا صالحًا'
    spec = d.get('specialty')
    if spec not in SPECIALTY_CODES:
        return None, 'اختر تخصصك من القائمة، أو «أخرى»'
    other = None
    if spec == 'other':
        other = one_line(d.get('specialty_other'), 2, 80)
        if not other:
            return None, 'اكتب تخصصك (حرفان على الأقل)'
    verdict = d.get('verdict')
    if verdict not in VERDICTS:
        return None, 'اختر: أؤكد الترجمة والتعريف، أو أقترح تعديلًا'
    text = d.get('text')
    if text is not None and not isinstance(text, str):
        return None, 'النص غير صالح'
    text = strip_ctrl(text or '').strip()
    if verdict == 'suggest' and not text:
        return None, 'اكتب التعديل الذي تقترحه'
    if len(text) > (2000 if verdict == 'suggest' else 1000):
        return None, 'النص أطول من المسموح'
    show = d.get('show_name', False)
    if not isinstance(show, bool):
        return None, 'اختر: يظهر اسمك أو لا يظهر'
    title = d.get('ref_title')
    title = one_line(title, 1, 200) if (kind != 'glossary_term' and isinstance(title, str)) else None
    return {'kind': kind, 'ref': ref, 'name': name, 'email': email, 'specialty': spec, 'specialty_other': other,
            'verdict': verdict, 'text': text or None, 'show_name': show, 'ref_title': title}, None


def ar_count(n, forms):
    """نفس U في v2-logic.js: forms = [المفرد الكامل، المثنّى الكامل، «عدد + جمع»، «عدد + تمييز مفرد»]؛ الأرقام هندية."""
    n = int(n)
    if n == 1:
        return forms[0]
    if n == 2:
        return forms[1]
    num = str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))
    return '%s %s' % (num, forms[2] if 3 <= n <= 10 else forms[3])


def name_key(v):
    return re.sub(r'\s+', ' ', v or '').strip().casefold()


def specialty_text(r):
    return (r.specialty_other or '') if r.specialty == 'other' else SPECIALTY_LABEL.get(r.specialty, SPECIALTY_LABEL['other'])


def _like(q):
    return '%' + q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


# ——————————————————————————————————————————————— التسجيل

def register(app, ns):
    from flask import jsonify, request

    def N(name):
        return ns[name]

    def guard(f):
        return N('token_required')(N('roles_required')('admin')(f))

    def out(resp):
        return N('_v2_ns')(resp)

    def err(msg, code=400, **extra):
        body = {'error': msg}
        body.update(extra)
        return out((jsonify(body), code))

    def T():
        return N('GlossaryTerm')

    def db():
        return N('db')

    def now():
        return datetime.datetime.utcnow()

    def reviews_on():
        """مراجعات المتخصصين مفعّلة؟ الافتراضي لا."""
        return flag_on(N('Setting'), EXPERT_KEY)

    def require_review():
        """مفعّل = النشر بلا مراجعة ممنوع. الافتراضي مغلق؛ لا يفعّله إلا قيمة صريحة. ويتعطّل كله ما دامت المراجعات مغلقة (لا فرق بين مسودة ومنشور غير الظهور)."""
        return reviews_on() and flag_on(N('Setting'), SETTING_KEY)

    def push(tid):
        """طلب توليد الصفحات في الخلفية — فشله لا يُسقط الحفظ."""
        try:
            N('_prerender_push_async')('glossary:%s' % tid)
        except Exception:                                  # noqa: BLE001
            pass

    def audit(action, target, meta=None):
        N('_audit')(action, target=str(target), meta=meta)

    def head(write=True, tid=None, reviews=False):
        """(رد جاهز | None، المصطلح | None، الجسم). المفتاح ثم (المراجعات مفعّلة؟) ثم التأكيد ثم الوجود — قبل أي أثر."""
        closed = N('_v2_closed')()
        if closed:
            return closed, None, None
        if reviews and not reviews_on():
            return err(NOT_FOUND_ROUTE_AR, 404), None, None
        body = N('_v2_body')() if write else {}
        if write:
            bad = N('_v2_confirmed')(body)
            if bad:
                return bad, None, None
        term = None
        if tid is not None:
            term = db().session.get(T(), tid)
            if term is None:
                return err(NOT_FOUND_AR, 404), None, None
        return None, term, body

    def counts():
        rows = T().query.with_entities(T().status, T().area, T().reviewed_at, T().reviewed_by_name, T().reviewed_by_role).all()
        by_area = {a: 0 for a in AREA_CODES}
        c = {'all': len(rows), 'draft': 0, 'under_review': 0, 'confirmed': 0, 'published': 0, 'reviewed': 0, 'unreviewed': 0,
             'published_unreviewed': 0}
        for st, area, ra, rn, rr in rows:
            c[st if st in PUBLISHED else 'draft'] += 1
            rev = bool(ra and rn and rr)
            c['reviewed' if rev else 'unreviewed'] += 1
            if st in PUBLISHED:
                c['published'] += 1
                if not rev:
                    c['published_unreviewed'] += 1
            by_area[area if area in by_area else 'other'] += 1
        c['by_area'] = by_area
        c['reviews_pending'] = N('ExpertReviewSubmission').query.filter_by(status='pending').count() if reviews_on() else 0
        c['published_no_topic'] = T().query.filter(T().status.in_(PUBLISHED), db().or_(T().saha_topic_id.is_(None), T().saha_topic_id == '')).count()
        return c

    def areas_meta():
        return [{'code': a, 'label': l} for a, l in AREAS]

    # ——— قائمة وقراءة

    @app.route('/api/v2/content/glossary', methods=['GET'], endpoint='v2_glossary_list')
    @guard
    def v2_glossary_list():
        bad, _t, _b = head(write=False)
        if bad:
            return bad
        q = (request.args.get('q') or '').strip()[:120]
        area = (request.args.get('area') or '').strip()
        status = (request.args.get('status') or 'all').strip()
        review = (request.args.get('review') or 'all').strip()
        if area and area != 'all' and area not in AREA_CODES:
            return err(BAD_AREA_AR)
        if status not in ('all', 'draft', 'under_review', 'confirmed', 'published') or review not in ('all', 'reviewed', 'unreviewed'):
            return err('قيمة غير صالحة')
        try:
            limit = max(1, min(int(request.args.get('limit', 200)), 500))
            offset = max(0, int(request.args.get('offset', 0)))
        except ValueError:
            return err('قيمة غير صالحة')
        M = T()
        query = M.query
        if q:
            like = _like(q)
            query = query.filter(db().or_(*[getattr(M, f).like(like, escape='\\') for f in ('ar', 'en', 'fr', 'definition_ar', 'slug')]))
        if area and area != 'all':
            query = query.filter(M.area == area)
        if status == 'published':
            query = query.filter(M.status.in_(PUBLISHED))
        elif status != 'all':
            query = query.filter(M.status == status)
        if review == 'reviewed':
            query = query.filter(M.reviewed_at.isnot(None), M.reviewed_by_name.isnot(None), M.reviewed_by_role.isnot(None))
        elif review == 'unreviewed':
            query = query.filter(db().or_(M.reviewed_at.is_(None), M.reviewed_by_name.is_(None), M.reviewed_by_role.is_(None)))
        total = query.count()
        rows = query.order_by(M.en.asc(), M.id.asc()).offset(offset).limit(limit).all()
        return out(jsonify({'items': [serialize_admin(t) for t in rows], 'total': total, 'counts': counts(),
                            'areas': areas_meta(), 'require_review': require_review(), 'reviews_enabled': reviews_on(),
                            'substantive_fields': list(SUBSTANTIVE)}))

    @app.route('/api/v2/content/glossary/<int:tid>', methods=['GET'], endpoint='v2_glossary_get')
    @guard
    def v2_glossary_get(tid):
        bad, term, _b = head(write=False, tid=tid)
        if bad:
            return bad
        return out(jsonify({'item': serialize_admin(term), 'require_review': require_review(), 'reviews_enabled': reviews_on()}))

    # ——— إنشاء وتعديل وحذف

    @app.route('/api/v2/content/glossary', methods=['POST'], endpoint='v2_glossary_create')
    @guard
    def v2_glossary_create():
        bad, _t, body = head()
        if bad:
            return bad
        raw = dict(body)
        if not (isinstance(raw.get('slug'), str) and raw['slug'].strip()):
            raw['slug'] = slugify(raw.get('en') if isinstance(raw.get('en'), str) else '')
        fields, problems = clean_fields(raw, need_slug=True)
        if problems:
            return err(problems[0], problems=problems)
        if T().query.filter_by(slug=fields['slug']).first():
            return err(SLUG_TAKEN_AR, 409)
        t = T()(source='manual', status='draft', created_at=now(), updated_at=now(),
                **{k: (json.dumps(v, ensure_ascii=False) if k == 'related' else v) for k, v in fields.items()})
        db().session.add(t)
        db().session.commit()
        audit('glossary.create', t.id, {'slug': t.slug, 'area': t.area})
        return out(jsonify({'ok': True, 'item': serialize_admin(t)}))

    @app.route('/api/v2/content/glossary/<int:tid>', methods=['PUT'], endpoint='v2_glossary_update')
    @guard
    def v2_glossary_update(tid):
        bad, t, body = head(tid=tid)
        if bad:
            return bad
        fields, problems = clean_fields(body, present_only=True)
        if problems:
            return err(problems[0], problems=problems)
        if 'slug' in fields and fields['slug'] != t.slug:
            if t.published_at is not None:
                return err(SLUG_FROZEN_AR, 409)
            if T().query.filter(T().slug == fields['slug'], T().id != t.id).first():
                return err(SLUG_TAKEN_AR, 409)
        changed = []
        for k, v in fields.items():
            cur = related_of(t) if k == 'related' else (getattr(t, k) or None)
            if cur != (v if k == 'related' else (v or None)):
                changed.append(k)
        if not changed:
            return out(jsonify({'ok': True, 'changed': [], 'item': serialize_admin(t)}))
        was_pub = is_published(t)
        for k in changed:
            setattr(t, k, json.dumps(fields[k], ensure_ascii=False) if k == 'related' else fields[k])
        cleared = unpublished = False
        if reviewed(t) and any(k in SUBSTANTIVE for k in changed):
            clear_stamp(t)
            cleared = True
            if was_pub and require_review():
                t.status = 'draft'
                unpublished = True
        if was_pub and not unpublished:
            settle(t)                                      # مؤكَّد عُدّل نصّه ⇒ تحت التأكيد ويبقى ظاهرًا
        t.updated_at = now()
        db().session.commit()
        audit('glossary.update', tid, {'fields': changed, 'review_cleared': cleared, 'unpublished': unpublished})
        if was_pub:
            push(tid)
        return out(jsonify({'ok': True, 'changed': changed, 'review_cleared': cleared, 'unpublished': unpublished,
                            'item': serialize_admin(t)}))

    @app.route('/api/v2/content/glossary/<int:tid>', methods=['DELETE'], endpoint='v2_glossary_delete')
    @guard
    def v2_glossary_delete(tid):
        bad, t, _b = head(tid=tid)
        if bad:
            return bad
        if t.published_at is not None or is_published(t):
            return err(DELETE_ONLY_DRAFT_AR, 409)
        slug = t.slug
        db().session.delete(t)
        db().session.commit()
        audit('glossary.delete', tid, {'slug': slug})
        return out(jsonify({'ok': True}))

    # ——— نشر ومراجعة

    @app.route('/api/v2/content/glossary/<int:tid>/publish', methods=['POST'], endpoint='v2_glossary_publish')
    @guard
    def v2_glossary_publish(tid):
        bad, t, _b = head(tid=tid)
        if bad:
            return bad
        if is_published(t):
            return err(ALREADY_PUBLISHED_AR, 409)
        if t.slug in RESERVED_SLUGS:                       # صف قديم بالرابط المحجوز: لا يُنشر فيُسقط كل صفحات القاموس
            return err(RESERVED_SLUG_AR, 409)
        if require_review() and not reviewed(t):
            return err(NEEDS_REVIEW_AR, 409, needs_review=True)
        t.status = 'under_review'
        settle(t)                                          # عليه ختم ⇒ مؤكَّد، وإلا تحت التأكيد
        if t.published_at is None:
            t.published_at = now()
        t.updated_at = now()
        db().session.commit()
        audit('glossary.publish', tid, {'slug': t.slug, 'reviewed': reviewed(t), 'state': t.status})
        push(tid)
        return out(jsonify({'ok': True, 'item': serialize_admin(t)}))

    @app.route('/api/v2/content/glossary/<int:tid>/unpublish', methods=['POST'], endpoint='v2_glossary_unpublish')
    @guard
    def v2_glossary_unpublish(tid):
        bad, t, _b = head(tid=tid)
        if bad:
            return bad
        if not is_published(t):
            return err(NOT_PUBLISHED_AR, 409)
        t.status = 'draft'
        t.updated_at = now()
        db().session.commit()
        audit('glossary.unpublish', tid, {'slug': t.slug})
        push(tid)
        return out(jsonify({'ok': True, 'item': serialize_admin(t)}))

    def person(v, lo, hi):
        v = re.sub(r'\s+', ' ', strip_ctrl(v)).strip() if isinstance(v, str) else ''
        if not lo <= len(v) <= hi or _URL_RE.search(v) or '@' in v:
            return None
        return v

    @app.route('/api/v2/content/glossary/<int:tid>/review', methods=['POST'], endpoint='v2_glossary_review')
    @guard
    def v2_glossary_review(tid):
        bad, t, body = head(tid=tid)
        if bad:
            return bad
        name, role = person(body.get('reviewer_name'), 2, 120), person(body.get('reviewer_role'), 2, 80)
        if not name or not role:
            return err(BAD_REVIEWER_AR)
        public = body.get('reviewer_name_public', False)
        if not isinstance(public, bool):
            return err(BAD_PUBLIC_NAME_AR)
        restamp = reviewed(t)
        t.reviewed_by_name, t.reviewed_by_role, t.reviewed_at, t.reviewer_name_public = name, role, now(), public
        settle(t)                                          # منشور ⇒ مؤكَّد؛ المسودة تبقى مسودة (تُنشر لاحقًا مؤكَّدة)
        t.updated_at = now()
        db().session.commit()
        audit('glossary.review', tid, {'slug': t.slug, 'restamp': restamp, 'reviewer_name': name, 'reviewer_role': role,
                                       'name_public': public, 'state': t.status})
        if is_published(t):
            push(tid)
        return out(jsonify({'ok': True, 'item': serialize_admin(t)}))

    @app.route('/api/v2/content/glossary/<int:tid>/unreview', methods=['POST'], endpoint='v2_glossary_unreview')
    @guard
    def v2_glossary_unreview(tid):
        bad, t, _b = head(tid=tid)
        if bad:
            return bad
        if not reviewed(t):
            return err(NOT_REVIEWED_AR, 409)
        was_pub = is_published(t)
        clear_stamp(t)
        unpublished = False
        if was_pub and require_review():
            t.status = 'draft'
            unpublished = True
        else:
            settle(t)                                      # مؤكَّد بلا ختم ⇒ تحت التأكيد ويبقى ظاهرًا
        t.updated_at = now()
        db().session.commit()
        audit('glossary.unreview', tid, {'slug': t.slug, 'unpublished': unpublished})
        if was_pub:
            push(tid)
        return out(jsonify({'ok': True, 'unpublished': unpublished, 'item': serialize_admin(t)}))

    # ——— الإعداد

    @app.route('/api/v2/content/glossary/settings', methods=['GET'], endpoint='v2_glossary_settings_get')
    @guard
    def v2_glossary_settings_get():
        bad, _t, _b = head(write=False)
        if bad:
            return bad
        return out(jsonify({'require_review': require_review(), 'expert_reviews_enabled': reviews_on(), 'under_review': counts()['under_review'],
                            'published_unreviewed': counts()['published_unreviewed']}))

    def set_flag(key, v):
        S = N('Setting')
        s = S.query.get(key)
        if s is None:
            db().session.add(S(key=key, value='1' if v else '0'))
        else:
            s.value = '1' if v else '0'
            s.updated_at = now()

    @app.route('/api/v2/content/glossary/settings', methods=['PUT'], endpoint='v2_glossary_settings_put')
    @guard
    def v2_glossary_settings_put():
        """الإعدادان يُكتبان من هنا وحده (والعام `PUT /api/settings` يرفضهما). كل مفتاح مرسَل يجب أن يكون منطقيًّا، ومفتاح واحد على الأقل."""
        bad, _t, body = head()
        if bad:
            return bad
        keys = (('require_review', SETTING_KEY), ('expert_reviews_enabled', EXPERT_KEY))
        sent = [(k, sk) for k, sk in keys if k in body]
        if not sent or any(not isinstance(body[k], bool) for k, _ in sent):
            return err(BAD_SETTING_AR)
        before = {k: flag_on(N('Setting'), sk) for k, sk in keys}
        for k, sk in sent:
            set_flag(sk, body[k])
        db().session.commit()
        changed = {k: body[k] for k, _ in sent if before[k] != body[k]}
        if changed:
            audit('glossary.setting', ','.join(sorted(changed)), changed)
        # عند التفعيل لا نُسقط شيئًا تلقائيًّا: نُخبر الشاشة بعدد «تحت التأكيد» ليقرّر الأدمن.
        c = counts()
        return out(jsonify({'ok': True, 'require_review': require_review(), 'expert_reviews_enabled': reviews_on(),
                            'under_review': c['under_review'], 'published_unreviewed': c['published_unreviewed']}))

    # ——— الاستيراد (معاينة ثم تأكيد)

    def source_rows(body):
        """(الصفوف الخام، المصدر، رسالة خطأ | None)."""
        src = body.get('source')
        if src not in SOURCES:
            return None, None, BAD_SOURCE_AR
        if src == 'upload':
            payload = body.get('payload', body.get('items'))
            rows = payload.get('items') if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                return None, src, BAD_UPLOAD_AR
        else:
            rows = load_source(src)
            if rows is None:
                return None, src, 'ملف المصدر غير متاح على الخادم'
        if len(rows) > IMPORT_MAX:
            return None, src, TOO_MANY_AR
        return rows, src, None

    def plan(rows):
        """يصنّف كل صف: جديد · موجود (يُتخطّى) · مكرّر داخل الملف · غير صالح. لا كتابة."""
        existing = {s for (s,) in T().query.with_entities(T().slug).all()}
        seen, new, skip_existing, skip_dup, invalid = set(), [], 0, 0, []
        for i, raw in enumerate(rows):
            fields, problems = clean_row(raw, i)
            sid = fields.get('slug') if fields else None
            if problems:
                invalid.append({'row': i + 1, 'slug': (raw.get('id') or raw.get('slug')) if isinstance(raw, dict) and isinstance(raw.get('id') or raw.get('slug'), str) else None,
                                'problem': problems[0]})
            elif sid in existing:
                skip_existing += 1
            elif sid in seen:
                skip_dup += 1
            else:
                seen.add(sid)
                new.append(fields)
        return new, skip_existing, skip_dup, invalid

    def plan_view(src, total, new, skip_existing, skip_dup, invalid):
        return {'source': src, 'total': total, 'new_count': len(new), 'skip_existing': skip_existing,
                'skip_duplicate_in_file': skip_dup, 'invalid_count': len(invalid), 'problems': invalid[:20],
                'sample': [{'slug': f['slug'], 'ar': f['ar'], 'en': f['en'], 'area': f['area'], 'area_label': AREA_LABEL[f['area']]} for f in new[:8]]}

    @app.route('/api/v2/content/glossary/seed/preview', methods=['POST'], endpoint='v2_glossary_seed_preview')
    @guard
    def v2_glossary_seed_preview():
        bad, _t, body = head(write=False)
        if bad:
            return bad
        body = N('_v2_body')()
        rows, src, msg = source_rows(body)
        if msg:
            return err(msg)
        new, skip_existing, skip_dup, invalid = plan(rows)
        return out(jsonify(plan_view(src, len(rows), new, skip_existing, skip_dup, invalid)))

    @app.route('/api/v2/content/glossary/seed/import', methods=['POST'], endpoint='v2_glossary_seed_import')
    @guard
    def v2_glossary_seed_import():
        bad, _t, body = head()
        if bad:
            return bad
        rows, src, msg = source_rows(body)
        if msg:
            return err(msg)
        new, skip_existing, skip_dup, invalid = plan(rows)
        stamp = now()
        for f in new:
            db().session.add(T()(source=src, status='draft', created_at=stamp, updated_at=stamp,
                                 **{k: (json.dumps(v, ensure_ascii=False) if k == 'related' else v) for k, v in f.items()}))
        db().session.commit()
        view = plan_view(src, len(rows), new, skip_existing, skip_dup, invalid)
        audit('glossary.seed_import', src, {'source': src, 'imported': len(new), 'skipped_existing': skip_existing,
                                            'skipped_duplicate': skip_dup, 'invalid': len(invalid)})
        view['ok'] = True
        view['imported'] = len(new)
        return out(jsonify(view))

    # ——— نقاشات الساحة

    def bridge_topics():
        """(قائمة نقاشات علنية | None، رد خطأ جاهز | None). من جسر المنصة `GET /api/bridge/topics`."""
        resp = N('_platform_proxy')('GET', '/api/bridge/topics', timeout=25)
        if not N('_resp_ok')(resp):
            if N('_ef_no_reply')(resp):
                audit('glossary.no_reply', 'topics', {'attempt': 'list'})
                return None, err(NO_REPLY_AR, 502, no_reply=True)
            return None, out(N('_v2_mask_auth')(resp))
        try:
            data = (resp[0] if isinstance(resp, tuple) else resp).get_json(silent=True)
        except Exception:                                  # noqa: BLE001
            data = None
        if isinstance(data, dict):
            data = data.get('topics')
        if not isinstance(data, list):
            return None, err(BAD_REPLY_AR, 502)
        rows = []
        for r in data:
            if (isinstance(r, dict) and r.get('status') in _LIVE and isinstance(r.get('id'), str) and TOPIC_ID_RE.match(r['id'])):
                title = r.get('title') if isinstance(r.get('title'), str) else ''
                rows.append({'id': r['id'], 'title': title[:200], 'status': r['status']})
        return rows, None

    @app.route('/api/v2/content/glossary/topics', methods=['GET'], endpoint='v2_glossary_topics')
    @guard
    def v2_glossary_topics():
        bad, _t, _b = head(write=False)
        if bad:
            return bad
        rows, e = bridge_topics()
        if e:
            return e
        return out(jsonify({'topics': rows[:300], 'url_prefix': SAHA_APP_URL}))

    @app.route('/api/v2/content/glossary/<int:tid>/attach-topic', methods=['POST'], endpoint='v2_glossary_attach')
    @guard
    def v2_glossary_attach(tid):
        bad, t, body = head(tid=tid)
        if bad:
            return bad
        topic = body.get('saha_topic_id')
        if not (isinstance(topic, str) and TOPIC_ID_RE.match(topic)):
            return err(BAD_TOPIC_AR)
        if t.saha_topic_id:
            return err(HAS_TOPIC_AR, 409)
        rows, e = bridge_topics()
        if e:
            return e
        if topic not in {r['id'] for r in rows}:
            return err(TOPIC_NOT_LIVE_AR, 409)
        t.saha_topic_id = topic
        t.updated_at = now()
        db().session.commit()
        audit('glossary.topic_attach', tid, {'topic_id': topic})
        if is_published(t):
            push(tid)
        return out(jsonify({'ok': True, 'saha_topic_id': topic, 'url': SAHA_APP_URL + topic}))

    @app.route('/api/v2/content/glossary/<int:tid>/detach-topic', methods=['POST'], endpoint='v2_glossary_detach')
    @guard
    def v2_glossary_detach(tid):
        bad, t, _b = head(tid=tid)
        if bad:
            return bad
        if not t.saha_topic_id:
            return err(NO_TOPIC_AR, 409)
        topic = t.saha_topic_id
        t.saha_topic_id = None
        t.updated_at = now()
        db().session.commit()
        audit('glossary.topic_detach', tid, {'topic_id': topic})
        if is_published(t):
            push(tid)
        return out(jsonify({'ok': True, 'saha_topic_id': None}))

    # ——— نقاش جديد في «الساحة» لكل مصطلح منشور (مسار البذر بلا نموذج ذكاء، لا `bridge_create_topic`)

    def seed_call(items, apply):
        """(ردّ البذر المقروء | None، رد خطأ جاهز | None). نداء واحد حتى SEED_CAP عنصرًا. ⛔ لا `by` ولا `confirmed` ولا `source_article_slug` ولا `segment` في الجسم.
        ضياع الرد ⇒ ٥٠٢ و`no_reply` (وإعادة المحاولة آمنة: البذر لا يكرّر عنوانًا موجودًا فنربط به). ٤٢٢ يمرّ بنصّه العربي، وغيره ⇒ ٥٠٢."""
        resp = N('_platform_proxy')('POST', '/api/bridge/topics/seed', json_body={'items': items, 'apply': bool(apply)}, timeout=40)
        if not N('_resp_ok')(resp):
            if N('_ef_no_reply')(resp):
                audit('glossary.no_reply', 'saha-topic', {'attempt': 'apply' if apply else 'preview'})
                return None, err(SEED_NO_REPLY_AR if apply else NO_REPLY_AR, 502, no_reply=True)
            code = int(resp[1]) if isinstance(resp, tuple) else 502
            msg = N('_proxy_json')(resp).get('error')
            if code == 422 and isinstance(msg, str) and re.search('[\u0600-\u06ff]', msg):
                return None, err(msg, 422)
            if code == 422:
                return None, err(PLATFORM_REFUSED_AR, 422)
            return None, err(PLATFORM_DOWN_AR, 502)
        data = N('_proxy_json')(resp)
        if not isinstance(data, dict) or data.get('ok') is not True or data.get('applied') is not bool(apply):
            return None, err(BAD_REPLY_AR, 502)
        return data, None

    def settle_seed(kind, row, live):
        """نتيجة عنصر واحد ⇒ ('create', id | None) | ('link', id) | ('error', رسالة). id لا يكون None إلا في المعاينة. `live` = معرّفات النقاشات العلنية."""
        if kind == 'created':
            tid = row.get('id')
            if tid is None:
                return 'create', None
            return ('create', tid) if isinstance(tid, str) and TOPIC_ID_RE.match(tid) else ('error', BAD_REPLY_AR)
        reason, ex = row.get('reason'), row.get('existing_id')
        if reason == 'duplicate_in_batch':
            return 'error', TOPIC_DUP_IN_BATCH_AR
        if reason == 'duplicate_title' and isinstance(ex, str) and TOPIC_ID_RE.match(ex):
            return ('link', ex) if ex in (live or ()) else ('error', TOPIC_EXISTS_NOT_LIVE_AR)
        return 'error', BAD_REPLY_AR

    def needs_live(aligned):
        return any(k == 'skipped' and r.get('reason') == 'duplicate_title' for k, r in aligned)

    def live_ids():
        rows, e = bridge_topics()
        return ({r['id'] for r in rows} if rows is not None else None), e

    def with_extra(resp, **extra):
        body = dict(N('_proxy_json')(resp))
        body.update(extra)
        return out((jsonify(body), int(resp[1]) if isinstance(resp, tuple) else 502))

    def topic_head(tid, write):
        """المصطلح للنقاش: منشور فقط ولم يُربط بعد. المعاينة بلا تأكيد ولا كتابة."""
        bad, t, body = head(write=write, tid=tid)
        if bad:
            return bad, None, None
        if not write:
            body = N('_v2_body')()
        if not is_published(t):
            return err(TOPIC_NOT_PUBLISHED_AR, 409), None, None
        if t.saha_topic_id:
            return err(HAS_TOPIC_AR, 409), None, None
        return None, t, body

    def link(t, topic_id, adopted):
        t.saha_topic_id = topic_id
        t.updated_at = now()
        db().session.commit()
        audit('glossary.saha_open', t.id, {'topic_id': topic_id, 'adopted': adopted})

    def one_topic(tid, apply):
        bad, t, body = topic_head(tid, apply)
        if bad:
            return bad
        item, msg = topic_item(t, body.get('title'), body.get('question'))
        if msg:
            return err(msg)
        data, e = seed_call([item], apply)
        if e:
            return e
        al = align_seed([item['title']], data)
        if al is None or len(al) != 1:
            return err(BAD_REPLY_AR, 502)
        live = None
        if needs_live(al):
            live, e = live_ids()
            if e:
                return e
        res, topic = settle_seed(al[0][0], al[0][1], live)
        if res == 'error':
            return err(topic, 409 if topic == TOPIC_EXISTS_NOT_LIVE_AR else 502)
        if not apply:
            return out(jsonify({'ok': True, 'plan': 'create' if res == 'create' else 'link_existing', 'title': item['title'], 'question': item['question'],
                                'message': TOPIC_PLAN_NEW_AR if res == 'create' else TOPIC_PLAN_LINK_AR, 'existing_id': topic if res == 'link' else None}))
        link(t, topic, res == 'link')
        if is_published(t):
            push(tid)
        return out(jsonify({'ok': True, 'saha_topic_id': topic, 'url': SAHA_APP_URL + topic, 'adopted': res == 'link'}))

    @app.route('/api/v2/content/glossary/<int:tid>/saha-topic/preview', methods=['POST'], endpoint='v2_glossary_saha_preview')
    @guard
    def v2_glossary_saha_preview(tid):
        return one_topic(tid, False)

    @app.route('/api/v2/content/glossary/<int:tid>/saha-topic/open', methods=['POST'], endpoint='v2_glossary_saha_open')
    @guard
    def v2_glossary_saha_open(tid):
        return one_topic(tid, True)

    def bulk_run(apply):
        """كل مصطلح منشور بلا نقاش: دفعات ≤SEED_CAP بالتتابع، وتتوقف عند أول فشل (ما تم ربطه قبله يبقى ويُذكر في `results`)."""
        closed = N('_v2_closed')()
        if closed:
            return closed
        if apply:
            bad = N('_v2_confirmed')(N('_v2_body')())
            if bad:
                return bad
        M = T()
        terms = M.query.filter(M.status.in_(PUBLISHED), db().or_(M.saha_topic_id.is_(None), M.saha_topic_id == '')).order_by(M.en.asc(), M.id.asc()).all()
        if not terms:
            return err(NO_ELIGIBLE_AR, 409)
        results, work = [], []
        for t in terms:
            base = {'id': t.id, 'ar': t.ar, 'en': t.en, 'slug': t.slug, 'topic_id': None, 'message': ''}
            item, _m = topic_item(t)
            if item is None:
                results.append(dict(base, outcome='error', message=TOPIC_TITLE_LONG_AR))
            else:
                work.append((t, item, base))
        batches = [work[i:i + SEED_CAP] for i in range(0, len(work), SEED_CAP)]
        live, linked = None, []
        names = {'create': 'created', 'link': 'linked_existing', 'error': 'error'}

        def stop(resp):
            done = sum(1 for r in results if r['outcome'] != 'error')
            return with_extra(resp, stopped=True, results=results, done=done, remaining=len(terms) - len(results))

        for chunk in batches:
            data, e = seed_call([it for _t, it, _b in chunk], apply)
            if e:
                return stop(e)
            al = align_seed([it['title'] for _t, it, _b in chunk], data)
            if al is None or len(al) != len(chunk):
                return stop(err(BAD_REPLY_AR, 502))
            if live is None and needs_live(al):
                live, e = live_ids()
                if e:
                    return stop(e)
            for (t, _it, base), (kind, row) in zip(chunk, al):
                res, topic = settle_seed(kind, row, live)
                if res == 'error':
                    results.append(dict(base, outcome='error', message=topic))
                    continue
                if apply:
                    link(t, topic, res == 'link')
                    linked.append(t.id)
                results.append(dict(base, outcome=names[res], topic_id=topic if apply else None, existing_id=topic if res == 'link' else None,
                                    message=TOPIC_PLAN_LINK_AR if res == 'link' else TOPIC_PLAN_NEW_AR))
        counts_ = {n: sum(1 for r in results if r['outcome'] == n) for n in ('created', 'linked_existing', 'error')}
        view = {'ok': True, 'applied': bool(apply), 'dry_run': not apply, 'total': len(terms), 'batches': len(batches), 'counts': counts_, 'results': results}
        if apply:
            audit('glossary.saha_bulk', 'bulk', {'terms': len(terms), 'batches': len(batches), **counts_})
            for tid_ in linked:
                push(tid_)
        return out(jsonify(view))

    @app.route('/api/v2/content/glossary/saha-topics/bulk/preview', methods=['POST'], endpoint='v2_glossary_saha_bulk_preview')
    @guard
    def v2_glossary_saha_bulk_preview():
        return bulk_run(False)

    @app.route('/api/v2/content/glossary/saha-topics/bulk/open', methods=['POST'], endpoint='v2_glossary_saha_bulk_open')
    @guard
    def v2_glossary_saha_bulk_open():
        return bulk_run(True)

    # ——— مراجعات المتخصصين (الاستمارة العامة ⇒ صندوق «مراجعات القاموس»)

    def R():
        return N('ExpertReviewSubmission')

    def sub_view(r, term=None):
        """مراجعة واحدة للأدمن (فيها البريد: للتواصل بشأنها فقط). term = المصطلح الحالي لمراجعة glossary_term."""
        v = {'id': r.id, 'kind': r.kind, 'ref': r.ref, 'ref_title': r.ref_title or '', 'name': r.name, 'email': r.email,
             'specialty': r.specialty, 'specialty_label': SPECIALTY_LABEL.get(r.specialty, SPECIALTY_LABEL['other']),
             'specialty_other': r.specialty_other or None, 'specialty_text': specialty_text(r), 'verdict': r.verdict,
             'text': r.text or '', 'show_name': bool(r.show_name), 'status': r.status, 'created_at': iso(r.created_at),
             'decided_at': iso(r.decided_at), 'decided_by': r.decided_by or None, 'admin_note': r.admin_note or '',
             'term': serialize_admin(term) if term is not None else None, 'term_changed': False}
        if term is not None and r.term_updated_at is not None:
            v['term_changed'] = term.updated_at != r.term_updated_at
        return v

    def terms_for(rows):
        slugs = {r.ref for r in rows if r.kind == 'glossary_term'}
        if not slugs:
            return {}
        return {t.slug: t for t in T().query.filter(T().slug.in_(slugs)).all()}

    def review_counts():
        c = {k: R().query.filter_by(status=k).count() for k in REVIEW_STATUSES}
        c['all'] = sum(c.values())
        return c

    @app.route('/api/v2/content/glossary/reviews', methods=['GET'], endpoint='v2_glossary_reviews_list')
    @guard
    def v2_glossary_reviews_list():
        bad, _t, _b = head(write=False, reviews=True)
        if bad:
            return bad
        status = (request.args.get('status') or 'pending').strip()
        kind = (request.args.get('kind') or 'all').strip()
        if status not in REVIEW_STATUSES + ('all',) or kind not in KINDS + ('all',):
            return err('قيمة غير صالحة')
        try:
            limit = max(1, min(int(request.args.get('limit', 200)), 500))
        except ValueError:
            return err('قيمة غير صالحة')
        query = R().query
        if status != 'all':
            query = query.filter(R().status == status)
        if kind != 'all':
            query = query.filter(R().kind == kind)
        total = query.count()
        rows = query.order_by(R().created_at.desc(), R().id.desc()).limit(limit).all()
        by_slug = terms_for(rows)
        return out(jsonify({'items': [sub_view(r, by_slug.get(r.ref) if r.kind == 'glossary_term' else None) for r in rows],
                            'total': total, 'counts': review_counts(), 'specialties': [{'code': c, 'label': l} for c, l in SPECIALTIES]}))

    def pending_review(rid, body):
        """(الصف | None، رد خطأ | None). يجب أن يكون معلّقًا."""
        r = db().session.get(R(), rid)
        if r is None:
            return None, err(NO_REVIEW_AR, 404)
        if r.status != 'pending':
            return None, err(REVIEW_DECIDED_AR, 409)
        note = body.get('admin_note')
        if note is not None and (not isinstance(note, str) or len(note.strip()) > 500):
            return None, err(BAD_NOTE_AR)
        return r, None

    def decide(r, status, body):
        r.status = status
        r.decided_at = now()
        r.decided_by = N('_actor_email')()[:80]
        note = body.get('admin_note')
        r.admin_note = (strip_ctrl(note).strip() or None) if isinstance(note, str) else None

    @app.route('/api/v2/content/glossary/reviews/<int:rid>/approve', methods=['POST'], endpoint='v2_glossary_review_approve')
    @guard
    def v2_glossary_review_approve(rid):
        bad, _t, body = head(reviews=True)
        if bad:
            return bad
        r, e = pending_review(rid, body)
        if e:
            return e
        term, stamped, open_id, changed = None, False, None, False
        if r.kind == 'glossary_term':
            term = T().query.filter_by(slug=r.ref).first()
            if term is None:
                return err(REVIEW_TERM_GONE_AR, 409)
            changed = r.term_updated_at is not None and term.updated_at != r.term_updated_at      # تغيّر النص بعد التقديم (الشاشة حذّرت)
            if r.verdict == 'confirm':
                role = person(specialty_text(r), 2, 80)
                name = person(r.name, 2, 120)
                if not name or not role:
                    return err(BAD_REVIEWER_AR, 409)
                term.reviewed_by_name, term.reviewed_by_role, term.reviewed_at = name, role, now()
                term.reviewer_name_public = bool(r.show_name)
                settle(term)                               # منشور ⇒ مؤكَّد؛ المسودة تبقى مسودة
                term.updated_at = now()
                stamped = True
            else:
                open_id = term.id                          # اقتراح تعديل: الشاشة تفتح المحرّر والمصطلح يبقى كما هو
        decide(r, 'approved', body)
        db().session.commit()
        audit('glossary.review_approve', rid, {'kind': r.kind, 'ref': r.ref, 'verdict': r.verdict, 'stamped': stamped,
                                               'state': term.status if term is not None else None})
        if stamped and is_published(term):
            push(term.id)
        v = sub_view(r, term)
        v['term_changed'] = changed
        return out(jsonify({'ok': True, 'item': v, 'stamped': stamped, 'open_term_id': open_id,
                            'term': serialize_admin(term) if term is not None else None}))

    @app.route('/api/v2/content/glossary/reviews/<int:rid>/reject', methods=['POST'], endpoint='v2_glossary_review_reject')
    @guard
    def v2_glossary_review_reject(rid):
        bad, _t, body = head(reviews=True)
        if bad:
            return bad
        r, e = pending_review(rid, body)
        if e:
            return e
        decide(r, 'rejected', body)
        db().session.commit()
        audit('glossary.review_reject', rid, {'kind': r.kind, 'ref': r.ref, 'verdict': r.verdict})
        return out(jsonify({'ok': True, 'item': sub_view(r)}))

    # ——— الفيد العام

    def feed_payload():
        M = T()
        pub = M.query.filter(M.status.in_(PUBLISHED)).all()
        by_slug = {t.slug: t for t in pub}
        on = reviews_on()
        rows = [serialize_public(t, by_slug, on) for t in sorted(pub, key=lambda x: ((x.en or '').lower(), x.id))]
        return {'source': 'dashboard', 'areas': areas_meta(), 'terms': rows}

    ns['_glossary_feed_payload'] = feed_payload            # يقرؤه المولّد (prerender) بلا نداء HTTP — نفس نمط `_prerender_feed_json`

    @app.route('/api/content/glossary', methods=['GET'], endpoint='public_glossary_feed')
    def public_glossary_feed():
        """PUBLIC: المصطلحات المنشورة فقط، بحقول عامة فقط. بلا توكن، no-store (مثل فيد المقالات)، وCORS من الإعداد العام."""
        return N('_no_store')(jsonify(feed_payload()))

    # ——— الاستمارة العامة

    def pub(body, code):
        return N('_no_store')(jsonify(body)), code

    @app.route('/api/public/expert-reviews', methods=['POST'], endpoint='public_expert_review_create')
    def public_expert_review_create():
        """PUBLIC: مراجعة متخصص (تأكيد أو اقتراح تعديل). بلا توكن، وحراسته نسخة من `/api/messages`: حدّ فضفاض لكل نداء قبل أي شيء،
        ثم فخّ الحقل الخفي (يردّ نجاحًا وهميًّا ولا يخزّن)، ثم التحقق، ثم الحدّ الصارم. CORS من الإعداد العام للتطبيق.
        ⛔ لا يُخزَّن IP ولا متصفح: `_client_ip()` مفتاح دلو في الذاكرة فقط."""
        if not reviews_on():                               # قرار المؤسس ٢٠٢٦-١١-٠١: لا استمارة. ٤٠٤ قبل قراءة الجسم ولا شيء يُخزَّن ولا حصة تُستهلك
            return pub({'error': 'not_found'}, 404)
        d = request.get_json(silent=True)
        d = d if isinstance(d, dict) else {}
        ip = N('_client_ip')()
        if not N('_rate_ok')('expreview:any:' + ip, LOOSE_LIMIT, WINDOW):
            return pub({'error': 'rate_limited', 'detail': RATE_AR}, 429)
        if d.get('website') or d.get('hp'):
            N('_rate_ok')('expreview:' + ip, STRICT_LIMIT, WINDOW)       # يستهلك حصة: الفخّ لا يمنح ممرًّا مجانيًّا
            return pub({'ok': True}, 201)
        f, msg = clean_submission(d)
        if msg:
            return pub({'error': 'invalid', 'detail': msg}, 400)
        term = None
        if f['kind'] == 'glossary_term':
            term = T().query.filter_by(slug=f['ref']).first()
            if term is None or not is_published(term):
                return pub({'error': 'not_found', 'detail': 'هذا المصطلح غير موجود'}, 404)
            f['ref_title'] = term.ar
        if not N('_rate_ok')('expreview:' + ip, STRICT_LIMIT, WINDOW):
            return pub({'error': 'rate_limited', 'detail': RATE_AR}, 429)
        # التكرار يحدّث الصف المعلّق لنفس (البريد، النوع، العنصر) بشرط أن يكون الاسم نفسه: البريد غير موثّق، فمن يعيد الإرسال
        # ببريد غيره باسم مختلف لا يستبدل مراجعة صاحبه. الاسم المختلف يصير صفًّا معلّقًا مستقلًّا (حتى PENDING_PER_REF) يراه الأدمن بجانب الأول.
        same = R().query.filter_by(email=f['email'], kind=f['kind'], ref=f['ref'], status='pending').all()
        row = next((x for x in same if name_key(x.name) == name_key(f['name'])), None)
        if row is None:
            if len(same) >= PENDING_PER_REF:
                return pub({'ok': True}, 201)                                   # سقف الصفوف المعلّقة: لا شيء يُخزَّن ولا يُكشف
            row = R()(status='pending', created_at=now())
            db().session.add(row)
        for k in ('kind', 'ref', 'name', 'email', 'specialty', 'specialty_other', 'verdict', 'text', 'show_name'):
            setattr(row, k, f[k])
        row.ref_title = f['ref_title']
        row.term_updated_at = term.updated_at if term is not None else None
        db().session.commit()
        return pub({'ok': True}, 201)
