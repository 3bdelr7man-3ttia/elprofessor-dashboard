# -*- coding: utf-8 -*-
"""R24 م١ — «بعدين» و«تجاهل» على خادم الداشبورد (docs/R24-DASHBOARD-SPEC.md قاعدة ٤).

    import v2_decisions_routes as _v2dec; _v2dec.register(app, globals())

قبل كده «لاحقًا» كانت بتلفّ البطاقة في ذاكرة المتصفح بس، وأول «ابدأ القرارات» تاني كانت كل حاجة ترجع. دلوقتي:

  * جدول `decision_snooze(item_key, until, kind, reason, by, created_at, fingerprint)` — `item_key` = `<نوع>:<معرّف المنصة>`.
    `kind` = `snooze` (لحد تاريخ) أو `dismiss` (`until` فاضي + سبب إجباري). `fingerprint` بصمة حالة البند وقت التأجيل (من الواجهة):
    لو حالة البند اتغيّرت على المنصة بعدها يرجع البند ومعاه «رجع لأن…» — المقارنة في الواجهة لأن الحالة الحالية عندها.
  * ٤ مسارات للأدمن بس (نفس حارس مسارات v2: المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤، و`no-store`):
      GET  /api/v2/decisions/snoozed
      POST /api/v2/decisions/<key>/snooze   {until, fingerprint?}   `until` إجباري ولازم في المستقبل
      POST /api/v2/decisions/<key>/dismiss  {reason, fingerprint?}  السبب إجباري؛ مرفوض لأنواع الفلوس وأنواع صاحبها مستني رد
      POST /api/v2/decisions/<key>/restore
  * كل فعل بيتسجّل في سجل التدقيق (`decision.snooze|dismiss|restore`) بعد ما الكتابة تنجح بس.
⛔ مفيش نداء للمنصة هنا خالص: الجدول محلي، والفعل ما بيغيّرش حاجة على المنصة (البند بيستخبّى من الشاشة بس).
"""
import datetime
import re

from sqlalchemy import text

KEY_RE = re.compile(r'^([a-z][a-z_]{1,29}):([^\s$/\\?#%]{1,160})$')
SNOOZE_MAX_DAYS = 365
REASON_MIN, REASON_MAX = 3, 200
FP_MAX = 300
PURGE_AFTER_DAYS = 45          # مؤجَّل انتهى ميعاده من أكتر من كده بيتمسح من الجدول (الواجهة بتعامله زي المنتهي أصلًا)

# أنواع البنود (بادئة المفتاح) — اللي مش هنا ٤٠٠ (ما نخزّنش مفاتيح عشوائية).
KNOWN_TYPES = frozenset([
    'file', 'review', 'dispute', 'unactivated', 'legacy', 'payout', 'manual_payment', 'stuck_payment', 'payfail',
    'book_offer', 'trainer', 'join', 'identity_doc', 'pending_user', 'signup', 'founding', 'book', 'program', 'topic',
    'creative', 'verify', 'lead', 'message', 'site_message', 'course', 'live', 'brain_item', 'alert', 'other',
    'mk_tip',      # اقتراحات العقل في التسويق («لاحقًا» بتاعتها) — مفتاحها `mk_tip:<نوع>_<معرّف>`
])
# «تجاهل» بس للأنواع اللي مالهاش قرار على المنصة (قاعدة ٤). قايمة بيضا: أي نوع جديد مرفوض لحد ما يتحط هنا بقصد.
DISMISS_ALLOWED = frozenset(['signup', 'payfail', 'site_message', 'message', 'lead', 'stuck_payment', 'alert', 'other', 'mk_tip'])
# الأنواع اللي فيها فلوس أو صاحبها مستني رد: ليها «ارفض بسبب» مش «تجاهل» (رسالة الرفض بتقول كده).
DISMISS_REFUSED_MONEY_OR_WAITING = frozenset([
    'payout', 'manual_payment', 'dispute', 'legacy', 'unactivated', 'file', 'book_offer',
    'trainer', 'join', 'pending_user', 'identity_doc', 'founding',
])

CONFIRM_BAD_KEY_AR = 'مفتاح البند غير صالح'
UNKNOWN_TYPE_AR = 'نوع البند غير معروف'
UNTIL_REQUIRED_AR = 'اختار ميعاد رجوع البند'
UNTIL_BAD_AR = 'الميعاد غير صالح'
UNTIL_PAST_AR = 'الميعاد لازم يكون في المستقبل'
UNTIL_FAR_AR = 'أقصى تأجيل سنة'
REASON_REQUIRED_AR = 'اكتب سبب قصير (من ٣ أحرف)'
REASON_LONG_AR = 'السبب أطول من اللازم (حتى ٢٠٠ حرف)'
DISMISS_REFUSED_AR = 'ده مالوش «تجاهل» — ارفضه بسبب أو أجّله بميعاد'
DISMISS_UNSUPPORTED_AR = 'النوع ده مش بيتجاهل — أجّله بميعاد'
FAIL_AR = 'تعذّر الحفظ — حاول تاني'


def split_key(key):
    """('نوع', 'معرّف') أو None لو المفتاح مش على الشكل `<نوع>:<معرّف>`."""
    m = KEY_RE.match(key or '')
    return (m.group(1), m.group(2)) if m else None


def parse_until(value, now=None):
    """يحوّل `until` (ISO بـZ أو إزاحة أو تاريخ بس) إلى datetime بلا منطقة (UTC)، أو None لو مش مفهوم."""
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    try:
        if len(s) == 10:
            return datetime.datetime.strptime(s, '%Y-%m-%d')
        if s.endswith('Z') or s.endswith('z'):
            s = s[:-1] + '+00:00'
        dt = datetime.datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return dt


def iso(dt):
    return dt.replace(microsecond=0).isoformat() + 'Z'


def register(app, env):
    token_required = env['token_required']
    roles_required = env['roles_required']
    closed = env['_v2_closed']
    ns = env['_v2_ns']
    v2_body = env['_v2_body']
    audit = env['_audit']
    actor = env['_actor_email']
    db = env['db']
    jsonify = env['jsonify']
    request = env['request']

    def err(msg, status=400, **extra):
        body = {'error': msg}
        body.update(extra)
        return ns((jsonify(body), status))

    def now_utc():
        return datetime.datetime.utcnow().replace(microsecond=0)

    def ensure():
        """ينشئ الجدول لو ناقص (آمن يتكرّر، SQLite وPostgres)."""
        db.session.execute(text(
            'CREATE TABLE IF NOT EXISTS decision_snooze ('
            'item_key TEXT PRIMARY KEY, until TEXT NULL, kind TEXT NOT NULL DEFAULT \'snooze\', '
            'reason TEXT NOT NULL DEFAULT \'\', by TEXT NOT NULL DEFAULT \'\', created_at TEXT NOT NULL, '
            'fingerprint TEXT NOT NULL DEFAULT \'\')'))
        db.session.commit()

    def guard():
        gate = closed()
        if gate:
            return gate
        try:
            ensure()
        except Exception:                       # noqa: BLE001
            db.session.rollback()
            return err(FAIL_AR, 500)
        return None

    def row_json(r):
        parts = split_key(r[0]) or ('', '')
        return {'key': r[0], 'type': parts[0], 'id': parts[1], 'until': r[1], 'kind': r[2], 'reason': r[3],
                'by': r[4], 'created_at': r[5], 'fingerprint': r[6]}

    def purge_old():
        """مؤجَّل ميعاده فات من فترة بيتمسح. best-effort: فشله ما بيكسرش القراية."""
        try:
            cut = iso(now_utc() - datetime.timedelta(days=PURGE_AFTER_DAYS))
            db.session.execute(text("DELETE FROM decision_snooze WHERE kind = 'snooze' AND until IS NOT NULL AND until < :c"), {'c': cut})
            db.session.commit()
        except Exception:                       # noqa: BLE001
            db.session.rollback()

    def upsert(key, until, kind, reason, fingerprint):
        by = actor()
        now = iso(now_utc())
        db.session.execute(text('DELETE FROM decision_snooze WHERE item_key = :k'), {'k': key})
        db.session.execute(text(
            'INSERT INTO decision_snooze (item_key, until, kind, reason, by, created_at, fingerprint) '
            'VALUES (:k, :u, :kind, :r, :b, :c, :f)'),
            {'k': key, 'u': until, 'kind': kind, 'r': reason, 'b': by, 'c': now, 'f': fingerprint})
        db.session.commit()
        return by, now

    def common(key):
        """يتحقق من المفتاح ونوعه. يرجع (parts, None) أو (None, ردّ الخطأ)."""
        parts = split_key(key)
        if not parts:
            return None, err(CONFIRM_BAD_KEY_AR, 400)
        if parts[0] not in KNOWN_TYPES:
            return None, err(UNKNOWN_TYPE_AR, 400)
        return parts, None

    def fp_of(body):
        v = body.get('fingerprint')
        return v.strip()[:FP_MAX] if isinstance(v, str) else ''

    # ---------------------------------------------------------------- القراية
    @app.route('/api/v2/decisions/snoozed', methods=['GET'], endpoint='v2dec_snoozed')
    @token_required
    @roles_required('admin')
    def v2dec_snoozed():
        gate = guard()
        if gate:
            return gate
        purge_old()
        try:
            rows = db.session.execute(text(
                'SELECT item_key, until, kind, reason, by, created_at, fingerprint FROM decision_snooze ORDER BY created_at DESC')).fetchall()
        except Exception:                       # noqa: BLE001
            db.session.rollback()
            return err(FAIL_AR, 500)
        return ns(jsonify({'rows': [row_json(r) for r in rows], 'now': iso(now_utc())}))

    # ---------------------------------------------------------------- بعدين
    @app.route('/api/v2/decisions/<key>/snooze', methods=['POST'], endpoint='v2dec_snooze')
    @token_required
    @roles_required('admin')
    def v2dec_snooze(key):
        gate = guard()
        if gate:
            return gate
        parts, bad = common(key)
        if bad:
            return bad
        body = v2_body()
        raw = body.get('until')
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            return err(UNTIL_REQUIRED_AR, 400)
        dt = parse_until(raw)
        if dt is None:
            return err(UNTIL_BAD_AR, 400)
        now = now_utc()
        if dt <= now:
            return err(UNTIL_PAST_AR, 400)
        if dt > now + datetime.timedelta(days=SNOOZE_MAX_DAYS):
            return err(UNTIL_FAR_AR, 400)
        try:
            by, _ = upsert(key, iso(dt), 'snooze', '', fp_of(body))
        except Exception:                       # noqa: BLE001
            db.session.rollback()
            return err(FAIL_AR, 500)
        audit('decision.snooze', target=key, meta={'until': iso(dt), 'type': parts[0]})
        return ns(jsonify({'ok': True, 'key': key, 'until': iso(dt), 'kind': 'snooze', 'by': by}))

    # ---------------------------------------------------------------- تجاهل
    @app.route('/api/v2/decisions/<key>/dismiss', methods=['POST'], endpoint='v2dec_dismiss')
    @token_required
    @roles_required('admin')
    def v2dec_dismiss(key):
        gate = guard()
        if gate:
            return gate
        parts, bad = common(key)
        if bad:
            return bad
        if parts[0] in DISMISS_REFUSED_MONEY_OR_WAITING:
            return err(DISMISS_REFUSED_AR, 409, refused=True)
        if parts[0] not in DISMISS_ALLOWED:
            return err(DISMISS_UNSUPPORTED_AR, 409, refused=True)
        body = v2_body()
        reason = body.get('reason')
        reason = reason.strip() if isinstance(reason, str) else ''
        if len(reason) < REASON_MIN:
            return err(REASON_REQUIRED_AR, 400)
        if len(reason) > REASON_MAX:
            return err(REASON_LONG_AR, 400)
        try:
            by, _ = upsert(key, None, 'dismiss', reason, fp_of(body))
        except Exception:                       # noqa: BLE001
            db.session.rollback()
            return err(FAIL_AR, 500)
        audit('decision.dismiss', target=key, meta={'reason': reason, 'type': parts[0]})
        return ns(jsonify({'ok': True, 'key': key, 'until': None, 'kind': 'dismiss', 'by': by}))

    # ---------------------------------------------------------------- رجّعها
    @app.route('/api/v2/decisions/<key>/restore', methods=['POST'], endpoint='v2dec_restore')
    @token_required
    @roles_required('admin')
    def v2dec_restore(key):
        gate = guard()
        if gate:
            return gate
        parts, bad = common(key)
        if bad:
            return bad
        try:
            res = db.session.execute(text('DELETE FROM decision_snooze WHERE item_key = :k'), {'k': key})
            removed = (res.rowcount or 0) > 0
            db.session.commit()
        except Exception:                       # noqa: BLE001
            db.session.rollback()
            return err(FAIL_AR, 500)
        if removed:
            audit('decision.restore', target=key, meta={'type': parts[0]})
        return ns(jsonify({'ok': True, 'key': key, 'removed': removed}))
