# -*- coding: utf-8 -*-
"""نسبة المدرّب — مسارات `/api/v2/trainer-share*` (SPEC-C-courses C2b).

بروكسيات رفيعة فوق جسر المنصة `/api/bridge/trainer-share[/<email>]` و`/api/bridge/trainer-share-rules` (PARALLEL «نسبة المدرّب جاهزة»).
نفس قواعد D3 بالحرف:
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ قبل أي نداء للمنصة. `Cache-Control: no-store` على كل رد.
  * كل كتابة تطلب `confirmed: true` بالظبط. الفاعل (`by`) من التوكن لا من الجسم.
  * الجسم المبعوت للمنصة من قايمة بيضا، ونفحص الحدود هنا قبل أي نداء (النسبة ٣٥–٦٥ صحيحة · الزيادة ٠–٢٥ · السبب ٣ حروف فأكثر).
  * رفض المنصة بنصه العربي (`detail` ⇒ `error`) يمرّ كما هو. ٤٠١/٤٠٣ منها ⇒ ٥٠٢. رد ضايع ⇒ ٥٠٢ `{no_reply:true}` (نداء واحد ولا إعادة).
  * ⛔ السقف (٦٥) ما بيتبعتش ولا بيتعدّل من هنا: قراءة فقط.

`register(app, g)` بتتنادى من app.py بسطر واحد، و`g` = globals() بتاعته.
"""
import datetime
import re
from urllib.parse import quote

BASE_MIN, BASE_MAX = 35, 65
BONUS_MIN, BONUS_MAX = 0, 25
CAP_PCT = 65
REASON_MIN, REASON_MAX = 3, 300
EMAIL_RE = re.compile(r'^[^@\s/\\?#%]{1,64}@[^@\s/\\?#%]{1,190}\.[^@\s/\\?#%]{2,40}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}([T ][0-9:.]{4,15}([+-]\d{2}:?\d{2}|[Zz])?)?$')

ERR_EMAIL = 'بريد المدرّب غير صالح'
ERR_BASE = 'النسبة الأساسية رقم صحيح بين ٣٥ و٦٥'
ERR_BONUS = 'زيادة الإعلانات رقم صحيح بين ٠ و٢٥'
ERR_REASON = 'اكتب السبب (ثلاثة أحرف على الأقل)'
ERR_DATE = 'التاريخ غير صالح'
ERR_RANGE = 'تاريخ النهاية قبل تاريخ البداية'
ERR_CODE_MIN = 'الحد الأدنى مع كود المدرّب رقم صحيح بين ٣٥ و٦٥'
ERR_CAP = 'السقف ثابت عند ٦٥ ولا يُعدَّل من هنا'


def plain_int(v):
    """رقم صحيح من الجسم (لا منطقي ولا كسر ولا نص)، وإلا None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    return None


def clean_reason(v):
    s = re.sub(r'\s+', ' ', v).strip() if isinstance(v, str) else ''
    return s[:REASON_MAX] if len(s) >= REASON_MIN else ''


def clean_date(v):
    """(قيمة نظيفة أو None، ok). فاضي ⇒ (None, True). صيغة غير مفهومة ⇒ (None, False)."""
    if v is None:
        return None, True
    if not isinstance(v, str):
        return None, False
    s = v.strip()
    if not s:
        return None, True
    if not DATE_RE.match(s):
        return None, False
    try:
        datetime.date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return None, False
    return s, True


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def email_of(raw):
        e = (raw or '').strip().lower()
        return e if EMAIL_RE.match(e) else ''

    def guard(raw_email=None, write=False):
        """(رد جاهز أو None، البريد، الجسم). المفتاح ⇒ البريد ⇒ التأكيد (بالترتيب ده)."""
        closed = g['_v2_closed']()
        if closed:
            return closed, '', None
        email = ''
        if raw_email is not None:
            email = email_of(raw_email)
            if not email:
                return err(ERR_EMAIL), '', None
        body = g['_v2_body']() if write else {}
        if write:
            bad = g['_v2_confirmed'](body)
            if bad:
                return bad, email, None
        return None, email, body

    def path_of(email):
        return '/api/bridge/trainer-share/%s' % quote(email, safe='')

    # ------------------------------------------------------------------ القراءات
    @app.route('/api/v2/trainer-share', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2ts_list():
        bad, _, _ = guard()
        return bad or g['_v2_get']('/api/bridge/trainer-share')

    @app.route('/api/v2/trainer-share/<email>', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2ts_one(email):
        bad, em, _ = guard(email)
        return bad or g['_v2_get'](path_of(em))

    @app.route('/api/v2/trainer-share-rules', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2ts_rules_get():
        bad, _, _ = guard()
        return bad or g['_v2_get']('/api/bridge/trainer-share-rules')

    # ------------------------------------------------------------------ الكتابات
    @app.route('/api/v2/trainer-share/<email>', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2ts_put(email):
        bad, em, b = guard(email, write=True)
        if bad:
            return bad
        base = plain_int(b.get('base_pct'))
        if base is None or not BASE_MIN <= base <= BASE_MAX:
            return err(ERR_BASE)
        bonus = plain_int(b.get('ads_bonus_pts')) if b.get('ads_bonus_pts') is not None else 0
        if bonus is None or not BONUS_MIN <= bonus <= BONUS_MAX:
            return err(ERR_BONUS)
        reason = clean_reason(b.get('reason'))
        if not reason:
            return err(ERR_REASON)
        d_from, ok1 = clean_date(b.get('from'))
        d_until, ok2 = clean_date(b.get('until'))
        if not (ok1 and ok2):
            return err(ERR_DATE)
        if d_from and d_until and d_from[:10] > d_until[:10]:
            return err(ERR_RANGE)
        out = {'base_pct': base, 'ads_bonus_pts': bonus, 'reason': reason, 'confirmed': True}
        if d_from:
            out['from'] = d_from
        if d_until:
            out['until'] = d_until
        # ⛔ `by` يضيفه `_v2_write` من التوكن؛ أي `by` أو حقل زائد في جسم المتصفح لا يصل المنصة.
        return g['_v2_write']('PUT', path_of(em), out, 'trainer_share.update', em,
                              {'base_pct': base, 'ads_bonus_pts': bonus, 'reason_len': len(reason), 'from': d_from, 'until': d_until})

    @app.route('/api/v2/trainer-share-rules', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2ts_rules_put():
        bad, _, b = guard(write=True)
        if bad:
            return bad
        code_min = plain_int(b.get('code_min_pct'))
        if code_min is None or not BASE_MIN <= code_min <= BASE_MAX:
            return err(ERR_CODE_MIN)
        if b.get('cap_pct') is not None and plain_int(b.get('cap_pct')) != CAP_PCT:
            return err(ERR_CAP)
        reason = clean_reason(b.get('reason'))
        if not reason:
            return err(ERR_REASON)
        out = {'code_min_pct': code_min, 'reason': reason, 'confirmed': True}
        return g['_v2_write']('PUT', '/api/bridge/trainer-share-rules', out, 'trainer_share.rules', 'rules',
                              {'code_min_pct': code_min, 'reason_len': len(reason)})

    return app
