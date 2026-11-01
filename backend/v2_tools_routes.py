# -*- coding: utf-8 -*-
"""«الأدوات / الاستوديو» في الداشبورد (docs/v2/tools/SPEC.md): بروكسيات رفيعة فوق جسور المنصة `/api/bridge/tools/*` (docs/TOOLS-API.md هناك).

    GET  /api/v2/tools/overview                    ⇒ /api/bridge/tools/overview (فيه jobs_today؛ تقرير اليوم احتياطي لمنصة أقدم)  نظرة اليوم
    POST /api/v2/tools/kill                        ⇒ PUT /api/bridge/tools/settings {kill}                            «أوقف الاستوديو الآن» / إعادة التشغيل
    GET  /api/v2/tools/recipes                     ⇒ /api/bridge/tools/recipes                                        الأدوات والأماكن
    POST /api/v2/tools/recipes/<id>/enable         ⇒ PUT /api/bridge/tools/recipes/<id>                               مفتاح التشغيل لكل أداة
    PUT  /api/v2/tools/recipes/<id>                ⇒ PUT /api/bridge/tools/recipes/<id>                               السعر والتكلفة والقاعدة المجانية
    POST /api/v2/tools/recipes/<id>/test-render    ⇒ POST /api/bridge/tools/test-render/<id>                          رسم تجريبي (مزوّد تجريبي فقط)
    POST /api/v2/tools/styles   (multipart)        ⇒ POST /api/bridge/tools/styles بـ attach_to (نداء واحد)            مكان جديد بصورته
    PUT  /api/v2/tools/styles/<id>                 ⇒ PUT /api/bridge/tools/styles/<id>                                الاسم والترتيب والوصف وبدل الصورة
    POST /api/v2/tools/styles/<id>/visible         ⇒ PUT /api/bridge/tools/recipes/<أداته>                            ظاهر للناس / غير ظاهر
    DELETE /api/v2/tools/styles/<id>               ⇒ DELETE /api/bridge/tools/styles/<id>
    GET|PUT /api/v2/tools/settings                 ⇒ GET|PUT /api/bridge/tools/settings                               السقف · حدود الاستخدام · الشحن · حارس السعر
    GET  /api/v2/tools/samples                     ⇒ /api/bridge/tools/samples                                        العيّنات للمراجعة
    POST /api/v2/tools/samples/<id>                ⇒ POST /api/bridge/tools/samples/<id>                              سليم / أخفِ / امنع صاحبه
    GET  /api/v2/tools/report?range=&from=&to=     ⇒ /api/bridge/tools/report                                         التقرير
    POST /api/v2/tools/sweep-cron                  ⇒ POST /api/bridge/tools/sweep                                     كنس الاحتفاظ كل ساعة (سرّ المنصة فقط، من n8n)

نفس قواعد `v2_market4_routes.py`:
  * المفتاح (`DASH_V2_ENABLED`) مقفول ⇒ ٤٠٤ بلا أي نداء للمنصة · `Cache-Control: no-store` على كل رد. (استثناء مقصود: `sweep-cron` ما بيتوقفش على المفتاح،
    لأن «نحذف السيلفي خلال ٢٤ ساعة» وعد للناس، وهو محمي بالسرّ وحده.)
  * كل المسارات للأدمن بس (فيها إيميلات الناس وصور أعمالهم).
  * كل كتابة تطلب `confirmed: true` بالظبط قبل أي نداء، و`by` من التوكن وحده.
  * الجسم المبعوت للمنصة من قايمة بيضا بالحقول، والردود مفلترة بقايمة بيضا كمان.
  * ⛔ نداء واحد بلا إعادة محاولة. رد ضايع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) على كتابة ⇒ ٥٠٢ و`no_reply:true`. نص `detail` العربي من المنصة (٤٠٤ · ٤٠٩ · ٤٢٢) بيعدّي كما هو.
  * قراءة غابت من المنصة (٤٠٤) ⇒ `bridge_missing:true` والشاشة تكتب «غير متاح بعد» لا «لا شيء».
  * تدقيق عند النجاح بس، بالإجراء وبما حدث (مفاتيح وأعداد، لا نص حر).
  * ⛔ صفر نداء حقيقي: المعاينة `real:false` دايمًا (مزوّد تجريبي)، و`real:true` من الداشبورد مرفوضة.
  * تعديل الأداة: قراءة ثم دمج ثم كتابة، مع فحص `base_updated_at` (لو اتغيّرت الأداة من ساعة فتح الشاشة ⇒ ٤٠٩ «حدّث الصفحة»).

`register(app, g)` بتتنادى من app.py بسطر واحد (محروس)، و`g` = globals() بتاعته.
"""
import base64
import binascii
import datetime
import math
import re
from urllib.parse import quote

NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
MISSING_AR = 'الأدوات غير متاحة بعد على المنصة'
BAD_ID_AR = 'معرّف غير صالح'
CHANGED_AR = 'تغيّرت هذه الأداة منذ فتحت الصفحة. حدّث الصفحة ثم أعد المحاولة.'
NO_CHANGE_AR = 'لا فرق عن القيم الحالية'
REAL_AR = 'الرسم الحقيقي غير متاح من الداشبورد. المعاينة تجريبية فقط.'
FILE_NONE_AR = 'اختر صورة المكان'
FILE_BAD_AR = 'الملف ليس صورة صالحة (JPG أو PNG أو WebP)'
ATTACH_FAILED_AR = 'أُضيف المكان لكنه لم يُربط بالأداة. حدّث الصفحة ثم اضغط «أظهره للناس» عليه'

CURRENCIES = ('EGP', 'SAR', 'AED', 'QAR', 'KWD', 'OMR', 'USD')
CUR_AR = {'EGP': 'الجنيه', 'SAR': 'الريال السعودي', 'AED': 'الدرهم', 'QAR': 'الريال القطري', 'KWD': 'الدينار الكويتي', 'OMR': 'الريال العماني', 'USD': 'الدولار'}
DEFAULT_RATES = {'EGP': 50.0, 'SAR': 3.75, 'AED': 3.67, 'QAR': 3.64, 'KWD': 0.31, 'OMR': 0.385, 'USD': 1.0}
GROUPS = ('photo', 'social', 'video_cards')
FREE_RULES_FIXED = ('none', 'once_per_verified_account', 'always')
ROLES = ('all', 'verified_expert', 'judge_prosecutor_masked')
RANGES = ('today', 'week', 'custom')
ACTIONS = ('ok', 'hide', 'ban_user')
PROTECTED_KINDS = ('expert_card', 'certificate_card', 'winner_card')     # أنماط مربوطة بشاشات في المنصة (نقاط الدخول من السياق)

ID_RE = re.compile(r'^[a-z][a-z0-9_]{1,31}$')
OID_RE = re.compile(r'^[A-Za-z0-9_-]{6,64}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
DATA_IMG_RE = re.compile(r'^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$')
DAILY_RE = re.compile(r'^daily:(\d{1,3})$')

PREVIEW_MAX = 3 * 1024 * 1024
TITLE_MAX = 60
PLACE_MAX = 400
NEXT_LINE_MAX = 80
SORT_MAX = 999
COST_MAX = 20.0
PRICE_MAX = 100000
RANGE_MAX_DAYS = 366
SHOT_MAX = 6 * 1024 * 1024
SHOTS_MAX = 4
SAMPLE_PREVIEW_MAX = 700 * 1024
STYLE_PREVIEW_MAX = 700 * 1024
SAMPLES_LIMIT = 50

RECIPE_FIELDS = ('id', 'title_ar', 'sub_ar', 'group', 'output_kind', 'provider', 'enabled', 'draft', 'free_rule', 'variants', 'sort', 'watermark_free',
                 'updated_at', 'updated_by')
STYLE_FIELDS = ('id', 'recipe_id', 'title_ar', 'place_prompt', 'judge_ok', 'uses_provider', 'hidden', 'kind', 'sort', 'enabled', 'preview_asset_id', 'updated_at', 'updated_by')
SETTING_NUMS = ('daily_cap_usd', 'daily_cap_max_usd', 'image_min_multiple', 'video_min_multiple')
SETTING_INTS = ('per_user_daily', 'per_ip_daily', 'free_posts_daily', 'sample_pct', 'retry_limit', 'topup_max_egp')
REPORT_FIELDS = ('recipe_id', 'title', 'count', 'succeeded', 'failures', 'cost_usd', 'revenue_usd', 'margin_usd', 'avg_cost_usd')
SWEEP_KEYS = ('inputs', 'outputs_expired', 'outputs_removed', 'jobs_stale')

_SNIFF = ((b'\x89PNG\r\n\x1a\n', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'))


def sniff_image(raw):
    """نوع الصورة من البايتات وحدها (png · jpeg · webp). غير كده ⇒ None."""
    for magic, kind in _SNIFF:
        if raw.startswith(magic):
            return kind
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'image/webp'
    return None


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def _int(v):
    return int(v) if isinstance(v, int) and not isinstance(v, bool) else None


def _str(v, limit=400):
    return v.strip()[:limit] if isinstance(v, str) else ''


def _pick(d, keys):
    return {k: d[k] for k in keys if k in d} if isinstance(d, dict) else {}


def _cur_map(m):
    out = {}
    if isinstance(m, dict):
        for c in CURRENCIES:
            n = _num(m.get(c))
            if n is not None:
                out[c] = n
    return out


# ---------------------------------------------------------------------------------------------------- العروض (قايمة بيضا)
def view_overview(ov, rep):
    if not isinstance(ov, dict) or not isinstance(ov.get('today'), dict):
        return None
    t = ov['today']
    fl = ov.get('flags') if isinstance(ov.get('flags'), dict) else {}
    jobs = None
    jt = ov.get('jobs_today')
    if isinstance(jt, dict) and _int(jt.get('count')) is not None:        # المنصة الجديدة: `jobs_today` في نفس الرد (يوم UTC)
        jobs = {'count': _int(jt.get('count')) or 0, 'succeeded': _int(jt.get('succeeded')) or 0, 'failures': _int(jt.get('failures')) or 0}
    elif isinstance(rep, dict) and isinstance(rep.get('recipes'), list):   # منصة أقدم: من تقرير اليوم
        rows = [r for r in rep['recipes'] if isinstance(r, dict)]
        jobs = {'count': sum(_int(r.get('count')) or 0 for r in rows), 'succeeded': sum(_int(r.get('succeeded')) or 0 for r in rows),
                'failures': sum(_int(r.get('failures')) or 0 for r in rows)}
    reason = t.get('reason') if t.get('reason') in ('kill', 'cap') else None
    return {'flags': {'tools_enabled': bool(fl.get('tools_enabled')), 'provider': fl.get('provider') if fl.get('provider') in ('mock', 'live') else None,
                      'topup_enabled': bool(fl.get('topup_enabled'))},
            'today': {'cap_usd': _num(t.get('cap_usd')), 'spent_usd': _num(t.get('spent_usd')), 'remaining_usd': _num(t.get('remaining_usd')),
                      'kill': bool(t.get('kill')), 'paused': bool(t.get('paused')), 'reason': reason},
            'ffmpeg': bool(ov.get('ffmpeg')), 'raqm': bool(ov.get('raqm')), 'jobs': jobs}


def view_recipe(r):
    if not isinstance(r, dict):
        return None
    out = _pick(r, RECIPE_FIELDS)
    out['est_cost_usd'] = _num(r.get('est_cost_usd'))
    out['price'] = _cur_map(r.get('price'))
    out['allowed_roles'] = [x for x in (r.get('allowed_roles') or []) if x in ROLES] if isinstance(r.get('allowed_roles'), list) else []
    out['blocked_roles'] = [x for x in (r.get('blocked_roles') or []) if x in ROLES] if isinstance(r.get('blocked_roles'), list) else []
    out['styles'] = [x for x in (r.get('styles') or []) if isinstance(x, str) and ID_RE.match(x)] if isinstance(r.get('styles'), list) else []
    out['sizes'] = [str(s.get('key'))[:30] for s in (r.get('sizes') or []) if isinstance(s, dict) and s.get('key')] if isinstance(r.get('sizes'), list) else []
    return out


def view_style(s):
    if not isinstance(s, dict):
        return None
    out = _pick(s, STYLE_FIELDS)
    pd = s.get('preview_data')
    out['preview_data'] = pd if isinstance(pd, str) and len(pd) <= STYLE_PREVIEW_MAX and DATA_IMG_RE.match(pd) else ''
    return out


def view_recipes(d):
    if not isinstance(d, dict) or not isinstance(d.get('recipes'), list):
        return None
    recs = [view_recipe(r) for r in d['recipes'] if isinstance(r, dict) and ID_RE.match(str(r.get('id') or ''))]
    styles = [view_style(s) for s in (d.get('styles') or []) if isinstance(s, dict) and ID_RE.match(str(s.get('id') or ''))]
    return {'recipes': [r for r in recs if r], 'styles': [s for s in styles if s], 'groups': list(GROUPS)}


def view_settings(d):
    if not isinstance(d, dict) or not isinstance(d.get('settings'), dict):
        return None
    s = d['settings']
    out = {}
    for k in SETTING_NUMS:
        out[k] = _num(s.get(k))
    for k in SETTING_INTS:
        v = s.get(k)
        out[k] = int(v) if _num(v) is not None else None
    out['kill'] = bool(s.get('kill'))
    out['next_line'] = _str(s.get('next_line'), NEXT_LINE_MAX)
    out['rates'] = _cur_map(s.get('rates'))
    out['topup_min_by_currency'] = {k: int(v) for k, v in _cur_map(s.get('topup_min_by_currency')).items()}
    bt = s.get('blocked_terms')
    out['blocked_terms_count'] = len(bt) if isinstance(bt, list) else None
    lim = d.get('limits') if isinstance(d.get('limits'), dict) else {}
    out['absolute_max_usd'] = _num(lim.get('daily_cap_absolute_max_usd')) or 50.0
    return out


def view_samples(d):
    if not isinstance(d, dict) or not isinstance(d.get('samples'), list):
        return None
    rows = []
    for r in d['samples']:
        if not isinstance(r, dict) or not OID_RE.match(str(r.get('id') or '')):
            continue
        pv = r.get('preview')
        rows.append({'id': r['id'], 'email': _str(r.get('email'), 200), 'recipe_id': _str(r.get('recipe_id'), 40), 'style_id': _str(r.get('style_id'), 40),
                     'created_at': _str(r.get('created_at'), 40), 'sizes': [_str(x, 30) for x in (r.get('sizes') or [])][:6] if isinstance(r.get('sizes'), list) else [],
                     'preview': pv if isinstance(pv, str) and len(pv) <= SAMPLE_PREVIEW_MAX and DATA_IMG_RE.match(pv) else ''})
    return {'samples': rows, 'limit': SAMPLES_LIMIT}


def view_report(d, frm, to):
    if not isinstance(d, dict) or not isinstance(d.get('recipes'), list):
        return None
    rows = []
    for r in d['recipes']:
        if not isinstance(r, dict):
            continue
        row = {k: r.get(k) for k in REPORT_FIELDS if k in r}
        for k in ('count', 'succeeded', 'failures'):
            row[k] = _int(row.get(k)) or 0
        for k in ('cost_usd', 'revenue_usd', 'margin_usd', 'avg_cost_usd'):
            row[k] = _num(row.get(k)) or 0.0
        row['recipe_id'] = _str(row.get('recipe_id'), 40)
        row['title'] = _str(row.get('title'), 120) or row['recipe_id']
        row['revenue_by_currency'] = _cur_map(r.get('revenue_by_currency'))
        row['guard_flag'] = bool(r.get('guard_flag'))
        rows.append(row)
    ov = view_overview({'today': d.get('today') or {}, 'flags': {}}, None)
    tp = d.get('topups')
    topups = None
    if isinstance(tp, dict) and isinstance(tp.get('by_currency'), dict) and tp.get('is_revenue') is not True:     # لو المنصة قالت «إيراد» ما نعرضوش (رصيد عميل بس)
        topups = {'by_currency': _cur_map(tp['by_currency']), 'count': _int(tp.get('count'))}
    return {'recipes': rows, 'from': frm, 'to': to, 'today': ov['today'] if ov else None, 'topups': topups}


def view_images(d):
    if not isinstance(d, dict) or not isinstance(d.get('images'), list):
        return None
    imgs = [x for x in d['images'] if isinstance(x, str) and len(x) <= SHOT_MAX and DATA_IMG_RE.match(x)][:SHOTS_MAX]
    return {'images': imgs, 'uses_provider': bool(d.get('uses_provider')), 'provider': 'mock'}


# ---------------------------------------------------------------------------------------------------- التحقق
def free_rule_ok(rule):
    if rule in FREE_RULES_FIXED:
        return True
    m = DAILY_RE.match(rule) if isinstance(rule, str) else None
    return bool(m) and 1 <= int(m.group(1)) <= 999


def _decimals_ok(v, places):
    return abs(v * 10 ** places - round(v * 10 ** places)) < 1e-6


def clean_recipe_edit(b):
    """(حقول التعديل {price, est_cost_usd, free_rule} النظيفة، رسالة عربية | None). التحقق قبل أي نداء؛ المنصة تعيد التحقق وحارس السعر عندها."""
    out = {}
    if 'price' in b:
        p = b['price']
        if not isinstance(p, dict) or set(p.keys()) != set(CURRENCIES):
            return None, 'اكتب سعرًا لكل عملة من العملات السبع'
        clean = {}
        for c in CURRENCIES:
            n = _num(p[c])
            if n is None or n < 0 or n > PRICE_MAX or not _decimals_ok(n, 3):
                return None, 'سعر %s رقم من صفر إلى %d بثلاث منازل عشرية على الأكثر' % (CUR_AR[c], PRICE_MAX)
            clean[c] = round(n, 3)
        out['price'] = clean
    if 'est_cost_usd' in b:
        n = _num(b['est_cost_usd'])
        if n is None or n < 0 or n > COST_MAX or not _decimals_ok(n, 4):
            return None, 'التكلفة التقديرية رقم من صفر إلى %d دولارًا' % COST_MAX
        out['est_cost_usd'] = round(n, 4)
    if 'free_rule' in b:
        if not free_rule_ok(b['free_rule']):
            return None, 'القاعدة المجانية غير معروفة'
        out['free_rule'] = b['free_rule']
    if not out:
        return None, 'لا يوجد تغيير'
    return out, None


def guard_error(recipe, settings):
    """نفس حارس السعر عند المنصة (`guard_price`): السعر بالدولار ≥ التكلفة × المضاعِف. نص عربي أو None. المنصة تعيد الفحص."""
    est = _num(recipe.get('est_cost_usd')) or 0.0
    if est <= 0 or recipe.get('provider') in (None, '', 'none'):
        return None
    video = recipe.get('output_kind') == 'video' or str(recipe.get('provider') or '').endswith('video')
    mult = _num(settings.get('video_min_multiple' if video else 'image_min_multiple')) or (2.5 if video else 3.0)
    rates = dict(DEFAULT_RATES)
    rates.update(_cur_map(settings.get('rates')))
    rule = recipe.get('free_rule') or 'none'
    for cur in CURRENCIES:
        v = _num((recipe.get('price') or {}).get(cur)) or 0.0
        if v <= 0:
            if rule == 'none' or not free_rule_ok(rule):
                return 'سعر %s صفر والتكلفة أكبر من صفر. حدّد سعرًا أو قاعدة مجانية' % CUR_AR[cur]
            continue
        if v / (rates.get(cur) or 1.0) + 1e-9 < est * mult:
            return 'سعر %s أقل من الحد الأدنى (التكلفة × %g)' % (CUR_AR[cur], mult)
    return None


def clean_settings(ch, current, absolute_max):
    """(حقول الإعدادات النظيفة، رسالة عربية | None). نفس تحقق المنصة (`validate_settings_patch`) بنص أوضح. ⛔ `kill` له مسار مستقل و`blocked_terms` خارج هذه الشاشة."""
    if not isinstance(ch, dict) or not ch:
        return None, 'لا يوجد تغيير'
    allowed = set(SETTING_NUMS) | set(SETTING_INTS) | {'next_line', 'rates', 'topup_min_by_currency'}
    for k in ch:
        if k not in allowed:
            return None, 'حقل غير مسموح به: %s' % k
    out = {}
    if 'daily_cap_max_usd' in ch:
        n = _num(ch['daily_cap_max_usd'])
        if n is None or not (0 < n <= absolute_max) or not _decimals_ok(n, 2):
            return None, 'أعلى سقف مسموح به لا يزيد على %g دولارًا' % absolute_max
        out['daily_cap_max_usd'] = n
    cap_max = out.get('daily_cap_max_usd', _num(current.get('daily_cap_max_usd')) or 20.0)
    if 'daily_cap_usd' in ch:
        n = _num(ch['daily_cap_usd'])
        if n is None or not (0 < n <= cap_max) or not _decimals_ok(n, 2):
            return None, 'السقف اليومي رقم أكبر من صفر ولا يزيد على %g دولارًا' % cap_max
        out['daily_cap_usd'] = n
    for k in ('image_min_multiple', 'video_min_multiple'):
        if k in ch:
            n = _num(ch[k])
            if n is None or not (1.0 <= n <= 20.0) or not _decimals_ok(n, 2):
                return None, 'المضاعِف رقم بين ١ و٢٠'
            out[k] = n
    ranges = {'per_user_daily': (1, 200), 'per_ip_daily': (1, 1000), 'free_posts_daily': (0, 50), 'sample_pct': (0, 100), 'retry_limit': (0, 10)}
    labels = {'per_user_daily': 'حد المستخدم اليومي', 'per_ip_daily': 'حد الشبكة اليومي', 'free_posts_daily': 'عدد البوستات المجانية اليومية', 'sample_pct': 'نسبة العيّنات', 'retry_limit': 'إعادات المحاولة المجانية'}
    for k, (lo, hi) in ranges.items():
        if k in ch:
            n = _int(ch[k])
            if n is None or not (lo <= n <= hi):
                return None, '%s رقم صحيح بين %d و%d' % (labels[k], lo, hi)
            out[k] = n
    if 'topup_max_egp' in ch:
        n = _int(ch['topup_max_egp'])
        if n is None or not (100 <= n <= 10 ** 7):
            return None, 'سقف الشحن رقم صحيح لا يقل عن ١٠٠ جنيه'
        out['topup_max_egp'] = n
    if 'next_line' in ch:
        s = ch['next_line']
        if not isinstance(s, str) or len(s.strip()) > NEXT_LINE_MAX:
            return None, 'سطر «الجاي» أقصر من ٨٠ حرفًا'
        out['next_line'] = s.strip()
    for key, label in (('rates', 'سعر الصرف'), ('topup_min_by_currency', 'أقل شحنة')):
        if key in ch:
            m = ch[key]
            if not isinstance(m, dict) or not m:
                return None, '%s غير صالح' % label
            clean = {}
            for c, v in m.items():
                if c not in CURRENCIES:
                    return None, 'عملة غير معروفة'
                if key == 'rates':
                    n = _num(v)
                    if n is None or not (0 < n <= 1000000) or not _decimals_ok(n, 4):
                        return None, 'سعر الصرف لـ%s رقم أكبر من صفر' % CUR_AR[c]
                    clean[c] = n
                else:
                    n = _int(v)
                    if n is None or not (0 < n <= 1000000):
                        return None, 'أقل شحنة بـ%s رقم صحيح أكبر من صفر' % CUR_AR[c]
                    clean[c] = n
            out[key] = clean
    return out, None


def clean_style_fields(b, creating=False):
    """(حقول النمط {title_ar, place_prompt, sort, judge_ok}، رسالة | None) من جسم JSON أو نموذج. الغائب ما يتبعتش."""
    out = {}
    if 'title_ar' in b:
        t = b['title_ar'].strip() if isinstance(b['title_ar'], str) else ''
        if not t or len(t) > TITLE_MAX:
            return None, 'اكتب اسم المكان (حتى ٦٠ حرفًا)'
        out['title_ar'] = t
    if 'place_prompt' in b:
        p = b['place_prompt'].strip() if isinstance(b['place_prompt'], str) else None
        if p is None or len(p) > PLACE_MAX:
            return None, 'وصف المكان حتى ٤٠٠ حرف'
        out['place_prompt'] = p
    if 'sort' in b:
        n = _int(b['sort'])
        if n is None or not (0 <= n <= SORT_MAX):
            return None, 'الترتيب رقم صحيح من ٠ إلى ٩٩٩'
        out['sort'] = n
    if 'judge_ok' in b:
        if not isinstance(b['judge_ok'], bool):
            return None, 'حدّد: المكان يناسب القضاة وأعضاء النيابة أم لا'
        out['judge_ok'] = b['judge_ok']
    return out, None


def decode_data_image(s):
    """data URL لصورة ⇒ (بايتات، نوع) | (None، رسالة). النوع من البايتات لا من الترويسة."""
    m = DATA_IMG_RE.match(s) if isinstance(s, str) else None
    if not m:
        return None, FILE_BAD_AR
    try:
        raw = base64.b64decode(m.group(2), validate=True)
    except (binascii.Error, ValueError):
        return None, FILE_BAD_AR
    if not raw or len(raw) > PREVIEW_MAX:
        return None, 'صورة المكان أكبر من ٣ ميجا' if raw else FILE_BAD_AR
    kind = sniff_image(raw)
    if kind is None:
        return None, FILE_BAD_AR
    return (raw, kind), None


def resolve_range(key, frm, to, today):
    """(من، إلى، رسالة | None) بتاريخ UTC (نفس يوم المنصة). `custom` ⇒ تاريخان صالحان، من ≤ إلى، ولا يزيد عن ٣٦٦ يومًا."""
    if key == 'week':
        return (today - datetime.timedelta(days=6)).isoformat(), today.isoformat(), None
    if key != 'custom':
        return today.isoformat(), today.isoformat(), None
    try:
        a = datetime.date.fromisoformat(frm) if DATE_RE.match(frm or '') else None
        b = datetime.date.fromisoformat(to) if DATE_RE.match(to or '') else None
    except ValueError:
        a = b = None
    if a is None or b is None:
        return None, None, 'اختر تاريخ البداية والنهاية'
    if a > b:
        return None, None, 'تاريخ البداية بعد تاريخ النهاية'
    if (b - a).days >= RANGE_MAX_DAYS:
        return None, None, 'اختر مدة لا تزيد على سنة'
    return a.isoformat(), b.isoformat(), None


def utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date()


# ---------------------------------------------------------------------------------------------------- التسجيل
def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']
    request = g['request']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400, **extra):
        body = {'error': msg}
        body.update(extra)
        return ns((jsonify(body), code))

    def closed_or_confirmed(confirm_from_form=False):
        """(رد الإغلاق/التأكيد | None، الجسم). المفتاح مقفول ⇒ ٤٠٤ · غير مؤكَّد ⇒ ٤٠٠ — كله قبل أي نداء."""
        c = g['_v2_closed']()
        if c:
            return c, None
        if confirm_from_form:
            if (request.form.get('confirmed') or '').strip() != 'true':
                return g['_v2_confirmed']({}), None
            return None, {}
        body = g['_v2_body']()
        bad = g['_v2_confirmed'](body)
        return (bad, None) if bad else (None, body)

    def read(path, params=None, timeout=15):
        resp = g['_platform_proxy']('GET', path, params=params, timeout=timeout)
        if g['_resp_ok'](resp):
            j = resp.get_json(silent=True)
            return (j if isinstance(j, dict) else {}), None
        if isinstance(resp, tuple) and int(resp[1]) == 404:
            return None, ns((jsonify({'error': MISSING_AR, 'bridge_missing': True}), 404))
        return None, ns(g['_v2_mask_auth'](resp))

    def platform_write(method, path, body=None, data=None, files=None, timeout=25, attempt='write', target=''):
        """نداء واحد. (JSON الرد | None، ردّ الخطأ | None). رد ضايع ⇒ ٥٠٢ و`no_reply` وسطر تدقيق."""
        payload = None
        if body is not None:
            payload = dict(body)
            payload['by'] = g['_actor_email']()[:80]
        if data is not None:
            data = dict(data)
            data['by'] = g['_actor_email']()[:80]
        resp = g['_platform_proxy'](method, path, json_body=payload, data=data, files=files, timeout=timeout)
        if g['_resp_ok'](resp):
            j = resp.get_json(silent=True)
            return (j if isinstance(j, dict) else {}), None
        if g['_ef_no_reply'](resp):
            g['_audit']('tools.no_reply', target=target, meta={'attempt': attempt})
            return None, ns((jsonify({'error': NO_REPLY_AR, 'no_reply': True}), 502))
        return None, ns(g['_v2_mask_auth'](resp))

    def q(x):
        return quote(x, safe='')

    def load_recipes():
        d, fail = read('/api/bridge/tools/recipes')
        if fail:
            return None, fail
        v = view_recipes(d)
        if v is None:
            return None, err('تعذر قراءة رد المنصة', 502)
        raw = {r.get('id'): r for r in d.get('recipes') or [] if isinstance(r, dict)}
        return {'view': v, 'raw': raw, 'styles_raw': {s.get('id'): s for s in d.get('styles') or [] if isinstance(s, dict)}}, None

    # ------------------------------------------------------------------ ١ · نظرة اليوم ومفتاح الإيقاف
    @app.route('/api/v2/tools/overview', methods=['GET'], endpoint='v2tl_overview')
    @token_required
    @roles_required('admin')
    def v2tl_overview():
        c = g['_v2_closed']()
        if c:
            return c
        ov, fail = read('/api/bridge/tools/overview')
        if fail:
            return fail
        today = utc_today().isoformat()
        jt = ov.get('jobs_today') if isinstance(ov, dict) else None
        rep = None
        if not (isinstance(jt, dict) and _int(jt.get('count')) is not None):          # مفيش `jobs_today` (منصة أقدم) ⇒ نقرا تقرير اليوم
            rep, _f = read('/api/bridge/tools/report', {'from': today, 'to': today})   # فشل التقرير لا يُسقط النظرة: «أعمال اليوم» تكتب «غير متاح بعد»
        view = view_overview(ov, rep)
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        view['day'] = jt.get('day') if isinstance(jt, dict) and DATE_RE.match(str(jt.get('day') or '')) else today
        return ns(jsonify(view))

    @app.route('/api/v2/tools/kill', methods=['POST'], endpoint='v2tl_kill')
    @token_required
    @roles_required('admin')
    def v2tl_kill():
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        if not isinstance(b.get('kill'), bool):
            return err('حدّد: إيقاف الاستوديو أم إعادة تشغيله')
        out, fail = platform_write('PUT', '/api/bridge/tools/settings', {'settings': {'kill': b['kill']}}, attempt='kill', target='kill')
        if fail:
            return fail
        v = view_settings(out)
        g['_audit']('tools.kill' if b['kill'] else 'tools.resume', target='kill', meta={'kill': b['kill']})
        return ns(jsonify({'kill': bool(v['kill']) if v else b['kill']}))

    # ------------------------------------------------------------------ ٢ · الأدوات (الوصفات)
    @app.route('/api/v2/tools/recipes', methods=['GET'], endpoint='v2tl_recipes')
    @token_required
    @roles_required('admin')
    def v2tl_recipes():
        c = g['_v2_closed']()
        if c:
            return c
        data, fail = load_recipes()
        if fail:
            return fail
        return ns(jsonify(data['view']))

    def recipe_put(rid, mutate, action, meta, extra_check=None):
        """قراءة ⇒ فحص `base_updated_at` ⇒ دمج ⇒ فحص حارس السعر ⇒ PUT واحد. ⇒ (ردّ نهائي)."""
        if not ID_RE.match(rid or ''):
            return err(BAD_ID_AR)
        data, fail = load_recipes()
        if fail:
            return fail
        cur = data['raw'].get(rid)
        if cur is None:
            return err('هذه الأداة لم تعد موجودة على المنصة', 404)
        merged = dict(cur)
        bad = mutate(merged, cur, data)
        if bad:
            return err(bad[0], bad[1])
        sets, fail = read('/api/bridge/tools/settings')
        if fail:
            return fail
        turning_off = merged.get('enabled') is False and _cur_map(merged.get('price')) == _cur_map(cur.get('price'))
        gmsg = None if turning_off else guard_error(merged, sets.get('settings') if isinstance(sets.get('settings'), dict) else {})   # الإيقاف بلا تغيير سعر ما يتحرسش (زي المنصة)
        if gmsg:
            return err(gmsg, 422)
        out, fail = platform_write('PUT', '/api/bridge/tools/recipes/%s' % q(rid), {'recipe': merged}, attempt=action, target=rid)
        if fail:
            return fail
        g['_audit'](action, target=rid, meta=meta)
        saved = view_recipe(out.get('recipe')) or view_recipe(merged)
        return ns(jsonify({'recipe': saved}))

    def base_check(cur, b):
        """لو اتغيّرت الأداة (أو الصفحة قديمة) من ساعة فتح الشاشة ⇒ ٤٠٩ بدل ما نكتب فوق تعديل غيرنا."""
        base = b.get('base_updated_at')
        base = base if isinstance(base, str) else ''
        return None if base == str(cur.get('updated_at') or '') else (CHANGED_AR, 409)

    @app.route('/api/v2/tools/recipes/<rid>/enable', methods=['POST'], endpoint='v2tl_recipe_enable')
    @token_required
    @roles_required('admin')
    def v2tl_recipe_enable(rid):
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        if not isinstance(b.get('enabled'), bool):
            return err('حدّد: تشغيل الأداة أم إيقافها')
        on = b['enabled']

        def mutate(merged, cur, data):
            bad = base_check(cur, b)
            if bad:
                return bad
            if bool(cur.get('enabled')) == on:
                return 'الأداة %s بالفعل' % ('شغّالة' if on else 'موقوفة'), 409
            if on and not (cur.get('styles') or []):
                return 'أضف مكانًا واحدًا على الأقل قبل تشغيل الأداة', 422
            merged['enabled'] = on
            if on and merged.get('draft'):
                merged['draft'] = False
            return None
        return recipe_put(rid, mutate, 'tools.recipe_enable' if on else 'tools.recipe_disable', {'enabled': on})

    @app.route('/api/v2/tools/recipes/<rid>', methods=['PUT'], endpoint='v2tl_recipe_edit')
    @token_required
    @roles_required('admin')
    def v2tl_recipe_edit(rid):
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        edit, msg = clean_recipe_edit(b)
        if msg:
            return err(msg)

        def mutate(merged, cur, data):
            bad = base_check(cur, b)
            if bad:
                return bad
            if not [k for k, v in edit.items() if cur.get(k) != v]:
                return NO_CHANGE_AR, 400
            merged.update(edit)
            return None
        return recipe_put(rid, mutate, 'tools.recipe_edit', {'keys': sorted(edit.keys())})

    @app.route('/api/v2/tools/recipes/<rid>/test-render', methods=['POST'], endpoint='v2tl_test_render')
    @token_required
    @roles_required('admin')
    def v2tl_test_render(rid):
        c = g['_v2_closed']()
        if c:
            return c
        b = g['_v2_body']()
        if not ID_RE.match(rid or ''):
            return err(BAD_ID_AR)
        if b.get('real'):
            return err(REAL_AR, 400)
        sid = b.get('style_id', '')
        sid = sid if isinstance(sid, str) else ''
        if sid and not ID_RE.match(sid):
            return err(BAD_ID_AR)
        # لا كتابة ولا تكلفة: `real:false` دايمًا ⇒ المزوّد التجريبي، ما بيتخزّنش ولا بيتحسب على حد. بلا ورقة تأكيد.
        resp = g['_platform_proxy']('POST', '/api/bridge/tools/test-render/%s' % q(rid), json_body={'style_id': sid, 'real': False}, timeout=60)
        if not g['_resp_ok'](resp):
            return ns(g['_v2_mask_auth'](resp))
        view = view_images(resp.get_json(silent=True))
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(view))

    # ------------------------------------------------------------------ ٣ · الأماكن والأنماط
    @app.route('/api/v2/tools/styles', methods=['POST'], endpoint='v2tl_style_create')
    @token_required
    @roles_required('admin')
    def v2tl_style_create():
        bad, _b = closed_or_confirmed(confirm_from_form=True)
        if bad:
            return bad
        f = request.form
        sid = (f.get('id') or '').strip()
        rid = (f.get('recipe_id') or '').strip()
        if not ID_RE.match(sid) or not ID_RE.match(rid):
            return err(BAD_ID_AR)
        sort_raw = (f.get('sort') or '0').strip()
        fields, msg = clean_style_fields({'title_ar': f.get('title_ar') or '', 'place_prompt': f.get('place_prompt') or '',
                                          'sort': int(sort_raw) if re.fullmatch(r'\d{1,4}', sort_raw) else -1,
                                          'judge_ok': (f.get('judge_ok') or 'true') == 'true'}, creating=True)
        if msg:
            return err(msg)
        attach = (f.get('attach') or 'true') != 'false'
        if not fields.get('place_prompt'):
            return err('صف المكان بجملة قصيرة')
        if (request.content_length or 0) > PREVIEW_MAX + 1024 * 1024:
            return err('صورة المكان أكبر من ٣ ميجا', 413)
        up = request.files.get('preview')
        if up is None or not (up.filename or '').strip():
            return err(FILE_NONE_AR)
        raw = up.read(PREVIEW_MAX + 1)
        if len(raw) > PREVIEW_MAX:
            return err('صورة المكان أكبر من ٣ ميجا', 413)
        kind = sniff_image(raw)
        if not raw or kind is None:
            return err(FILE_BAD_AR)
        data, fail = load_recipes()
        if fail:
            return fail
        recipe = data['raw'].get(rid)
        if recipe is None:
            return err('هذه الأداة لم تعد موجودة على المنصة', 404)
        if recipe.get('provider') in (None, '', 'none'):
            return err('هذه الأداة تصميمها بالكود، ولا تحتاج أماكن')
        if sid in data['styles_raw']:
            return err('أُضيف هذا المكان من قبل. حدّث الصفحة.', 409)
        ext = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}[kind]
        form_data = {'id': sid, 'recipe_id': rid, 'title_ar': fields['title_ar'], 'place_prompt': fields['place_prompt'],
                     'judge_ok': 'true' if fields.get('judge_ok', True) else 'false', 'uses_provider': 'true', 'kind': 'scene', 'sort': str(fields.get('sort', 0))}
        if attach:
            form_data['attach_to'] = rid                         # نداء واحد: المنصة تربطه بالأداة ذرّيًا (`$addToSet`)
        resp = g['_platform_proxy']('POST', '/api/bridge/tools/styles', data=dict(form_data, by=g['_actor_email']()[:80]),
                                    files={'preview': ('preview.' + ext, raw, kind)}, timeout=40)
        if not g['_resp_ok'](resp):
            if isinstance(resp, tuple) and int(resp[1]) == 503 and 'لم يُحفظ' in str((resp[0].get_json(silent=True) or {}).get('error') or ''):
                # ٥٠٣ برسالة المنصة «تعذّر ربط المكان…، لم يُحفظ شيء»: رد أكيد (النمط اتشال عندها) لا رد ضايع
                return err(str(resp[0].get_json(silent=True).get('error')), 502, not_saved=True)
            if g['_ef_no_reply'](resp):
                g['_audit']('tools.no_reply', target=sid, meta={'attempt': 'style_create'})
                return ns((jsonify({'error': NO_REPLY_AR, 'no_reply': True}), 502))
            return ns(g['_v2_mask_auth'](resp))
        out = resp.get_json(silent=True)
        out = out if isinstance(out, dict) else {}
        style = view_style(out.get('style')) or {'id': sid, 'recipe_id': rid, 'title_ar': fields['title_ar']}
        attached = bool(attach and out.get('attached') is True)
        g['_audit']('tools.style_create', target=sid, meta={'recipe': rid, 'attached': attached, 'size': len(raw)})
        if attach and not attached:                              # الرد 200 لكن بلا `attached:true`: المكان اتحفظ ولم يُربط ⇒ خطأ واضح مش نجاح
            return err(ATTACH_FAILED_AR, 502, attach_failed=True)
        return ns(jsonify({'style': style, 'attached': attached, 'attach_failed': False}))

    @app.route('/api/v2/tools/styles/<sid>', methods=['PUT'], endpoint='v2tl_style_edit')
    @token_required
    @roles_required('admin')
    def v2tl_style_edit(sid):
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        if not ID_RE.match(sid or ''):
            return err(BAD_ID_AR)
        fields, msg = clean_style_fields(b)
        if msg:
            return err(msg)
        if 'preview_data' in b:
            img, msg = decode_data_image(b['preview_data'])
            if msg:
                return err(msg)
            fields['preview_data'] = b['preview_data']
        if not fields:
            return err('لا يوجد تغيير')
        out, fail = platform_write('PUT', '/api/bridge/tools/styles/%s' % q(sid), {'style': fields}, attempt='style_edit', target=sid)
        if fail:
            return fail
        g['_audit']('tools.style_edit', target=sid, meta={'keys': sorted(fields.keys())})
        return ns(jsonify({'style': view_style(out.get('style')) or {'id': sid}}))

    @app.route('/api/v2/tools/styles/<sid>/visible', methods=['POST'], endpoint='v2tl_style_visible')
    @token_required
    @roles_required('admin')
    def v2tl_style_visible(sid):
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        if not ID_RE.match(sid or ''):
            return err(BAD_ID_AR)
        if not isinstance(b.get('visible'), bool):
            return err('حدّد: إظهار المكان للناس أم إخفاؤه')
        vis = b['visible']
        data, fail = load_recipes()
        if fail:
            return fail
        style = data['styles_raw'].get(sid)
        if style is None:
            return err('هذا المكان لم يعد موجودًا على المنصة', 404)
        rid = str(style.get('recipe_id') or '')

        def mutate(merged, cur, dat):
            bad = base_check(cur, b)
            if bad:
                return bad
            lst = list(cur.get('styles') or [])
            if vis == (sid in lst):
                return 'المكان %s بالفعل' % ('ظاهر' if vis else 'مخفي'), 409
            if vis:
                lst.append(sid)
            else:
                lst = [x for x in lst if x != sid]
                if cur.get('enabled') and not lst:
                    return 'هذه آخر أماكن أداة شغّالة. أوقف الأداة أولًا أو أظهر مكانًا آخر', 422
            merged['styles'] = lst
            return None
        return recipe_put(rid, mutate, 'tools.style_show' if vis else 'tools.style_hide', {'recipe': rid})

    @app.route('/api/v2/tools/styles/<sid>', methods=['DELETE'], endpoint='v2tl_style_delete')
    @token_required
    @roles_required('admin')
    def v2tl_style_delete(sid):
        bad, _b = closed_or_confirmed()
        if bad:
            return bad
        if not ID_RE.match(sid or ''):
            return err(BAD_ID_AR)
        data, fail = load_recipes()
        if fail:
            return fail
        style = data['styles_raw'].get(sid)
        if style is None:
            return err('هذا المكان لم يعد موجودًا على المنصة', 404)
        if style.get('kind') in PROTECTED_KINDS:
            return err('هذا التصميم مرتبط بشاشات في المنصة، فلا يُحذف. يمكنك إخفاؤه أو تعديل اسمه', 422)
        rid = str(style.get('recipe_id') or '')
        rec = data['raw'].get(rid) or {}
        if rec.get('enabled') and sid in (rec.get('styles') or []) and len(rec.get('styles') or []) <= 1:
            return err('هذه آخر أماكن أداة شغّالة. أوقف الأداة أولًا أو أضف مكانًا آخر', 422)
        _o, fail = platform_write('DELETE', '/api/bridge/tools/styles/%s' % q(sid), None, attempt='style_delete', target=sid)
        if fail:
            return fail
        g['_audit']('tools.style_delete', target=sid, meta={'recipe': rid})
        return ns(jsonify({'ok': True}))

    # ------------------------------------------------------------------ ٤ · الإعدادات
    @app.route('/api/v2/tools/settings', methods=['GET'], endpoint='v2tl_settings')
    @token_required
    @roles_required('admin')
    def v2tl_settings():
        c = g['_v2_closed']()
        if c:
            return c
        d, fail = read('/api/bridge/tools/settings')
        if fail:
            return fail
        view = view_settings(d)
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(view))

    @app.route('/api/v2/tools/settings', methods=['PUT'], endpoint='v2tl_settings_put')
    @token_required
    @roles_required('admin')
    def v2tl_settings_put():
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        changes = b.get('changes')
        d, fail = read('/api/bridge/tools/settings')          # السقف يتقارن بالحدّ الحالي عند المنصة
        if fail:
            return fail
        cur = view_settings(d) or {}
        clean, msg = clean_settings(changes, cur, cur.get('absolute_max_usd') or 50.0)
        if msg:
            return err(msg, 422)
        out, fail = platform_write('PUT', '/api/bridge/tools/settings', {'settings': clean}, attempt='settings', target='settings')
        if fail:
            return fail
        g['_audit']('tools.settings', target='settings', meta={'keys': sorted(clean.keys())})
        return ns(jsonify(view_settings(out) or {}))

    # ------------------------------------------------------------------ ٥ · العيّنات
    @app.route('/api/v2/tools/samples', methods=['GET'], endpoint='v2tl_samples')
    @token_required
    @roles_required('admin')
    def v2tl_samples():
        c = g['_v2_closed']()
        if c:
            return c
        d, fail = read('/api/bridge/tools/samples', {'limit': SAMPLES_LIMIT}, timeout=25)
        if fail:
            return fail
        view = view_samples(d)
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(view))

    @app.route('/api/v2/tools/samples/<oid>', methods=['POST'], endpoint='v2tl_sample_act')
    @token_required
    @roles_required('admin')
    def v2tl_sample_act(oid):
        bad, b = closed_or_confirmed()
        if bad:
            return bad
        if not OID_RE.match(oid or ''):
            return err(BAD_ID_AR)
        action = b.get('action')
        if action not in ACTIONS:
            return err('اختر: سليم أو أخفِ العمل أو امنع صاحبه')
        out, fail = platform_write('POST', '/api/bridge/tools/samples/%s' % q(oid), {'action': action}, attempt='sample_' + action, target=oid)
        if fail:
            return fail
        refunded = _int(out.get('refunded')) or 0
        g['_audit']('tools.sample_' + action, target=oid, meta={'refunded': refunded})
        return ns(jsonify({'id': oid, 'status': 'ok' if action == 'ok' else 'hidden', 'banned': action == 'ban_user', 'refunded': refunded}))

    # ------------------------------------------------------------------ ٦ · التقرير
    @app.route('/api/v2/tools/report', methods=['GET'], endpoint='v2tl_report')
    @token_required
    @roles_required('admin')
    def v2tl_report():
        c = g['_v2_closed']()
        if c:
            return c
        key = (request.args.get('range') or 'today').strip()
        if key not in RANGES:
            key = 'today'
        frm, to, msg = resolve_range(key, (request.args.get('from') or '').strip(), (request.args.get('to') or '').strip(), utc_today())
        if msg:
            return err(msg, 422)
        d, fail = read('/api/bridge/tools/report', {'from': frm, 'to': to}, timeout=30)
        if fail:
            return fail
        view = view_report(d, frm, to)
        if view is None:
            return err('تعذر قراءة رد المنصة', 502)
        view['range'] = key
        return ns(jsonify(view))

    # ------------------------------------------------------------------ ٧ · كنس الاحتفاظ (كرون كل ساعة)
    @app.route('/api/v2/tools/sweep-cron', methods=['POST'], endpoint='v2tl_sweep_cron')
    def v2tl_sweep_cron():
        if not g['_metrics_secret_ok']():
            return ns((jsonify({'error': 'unauthorized'}), 401))
        resp = g['_platform_proxy']('POST', '/api/bridge/tools/sweep', json_body={}, timeout=60)
        if not g['_resp_ok'](resp):
            return ns((jsonify({'error': 'تعذّر تشغيل الكنس'}), 502))
        j = resp.get_json(silent=True)
        j = j if isinstance(j, dict) else {}
        counts = {k: (_int(j.get(k)) or 0) for k in SWEEP_KEYS}
        if any(counts.values()):          # سطر تدقيق لما يتمسح شيء بس: ٢٤ سطر يوميًا فاضيين ما يفيدوش
            g['_audit']('tools.sweep_cron', target='sweep', meta=counts, actor='cron')
        out = {'ok': True}
        out.update(counts)
        return ns(jsonify(out))
