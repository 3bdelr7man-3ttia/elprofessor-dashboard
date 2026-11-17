# -*- coding: utf-8 -*-
"""R30 — «اعكس الملف وارجع الفلوس» لملف خبير بعد تحويل أجره + «محجوز حتى يُسلَّم العمل» من الضمان الحقيقي على المنصة.

    import v2_expert_money_routes as _v2xm; _v2xm.register(app, globals())

  GET  /api/v2/expert-files/<file_id>/reverse-preview   اللي هيحصل قبل التأكيد (من جسر المنصة كما هو)
  POST /api/v2/expert-files/<file_id>/reverse           {reason, confirmed:true}  ⇐ POST /api/bridge/expert-files/<id>/reverse
  GET  /api/v2/money/held                               المحجوز في الضمان لكل عملة ⇐ GET /api/bridge/escrow/held

ليه: الاختبار الحيّ للرحلة الكاملة (2026-11-16/17) — بعد ما العميل ضغط «تمام» واتحوّل أجر الخبير، مفيش طريق يرجّع الفلوس؛
و«محجوز حتى يُسلَّم العمل» كان صفر طول ما الـ٥٠٠ في الضمان لأنه كان بيقرا جدول ضمان الداشبورد القديم (مرآة ما بتتغذّاش).

⛔ قواعد الفلوس (CLAUDE.md):
  * أدمن بس + المفتاح `DASH_V2_ENABLED` (مقفول ⇒ ٤٠٤) + `no-store`.
  * نوع الشغل `expert_file_reverse` مقفول على «يسألك» في `brain2/levels.py` (lock=money، ومفيش مستوى غير `ask`). الحارس هنا في الخادم:
    لو المستوى المحسوب طلع أي حاجة غير «يسألك» ⇒ ٤٠٩ قبل أي نداء للمنصة. والتنفيذ نفسه بضغطة أدمن بتأكيد صريح بس.
  * التأكيد `confirmed: true` بالظبط، والسبب إلزامي. الجسم المبعوت للمنصة قايمة بيضا، و`by` من التوكن مش من المتصفح.
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) ⇒ «ما وصلناش رد» + سطر سجل (الضغطة التانية آمنة: المنصة متماثلة لكل ملف).
  * النجاح بيتحقّق من **رد المنصة** (`status == 'refunded'` و`reversed`)، والتدقيق بعد النجاح بس وبأرقام المنصة.
"""
import re
from urllib.parse import quote

from brain2 import levels

WORK_TYPE = 'expert_file_reverse'
REASON_MAX = 500
FID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
REASON_AR = 'سبب العكس مطلوب'
LOCK_AR = 'عكس الملف بموافقتك دائمًا، ولا يُنفَّذ إلا بتأكيدك'
BAD_ID_AR = 'هذا الملف غير موجود'
SLOW_AR = 'المنصة تستغرق وقتًا؛ يُرجى الانتظار قليلًا ثم فتح الملف من جديد قبل أي محاولة أخرى، تجنبًا للتكرار'
REVERSE_TIMEOUT = 40
PREVIEW_TIMEOUT = 20
HELD_TIMEOUT = 20


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def locked_ok():
        """⛔ الحارس الصلب: العكس ما يبقاش «لوحده» ولا «يقترح» أبدًا — بس «يسألك»."""
        wt = levels.get_type(WORK_TYPE)
        if wt is None or levels.lock_of(wt) != 'money':
            return False
        try:
            return levels.level_of({'db': g['db']}, wt) == 'ask'
        except Exception:   # noqa: BLE001 — قراية المستوى فشلت ⇒ نفترض الأسوأ: نوقف
            try:
                g['db'].session.rollback()
            except Exception:   # noqa: BLE001
                pass
            return False

    def slow(file_id):
        g['_audit']('expert_file.no_reply', target=file_id, meta={'attempt': 'reverse'})
        return ns((jsonify({'error': SLOW_AR, 'no_reply': True}), 502))

    @app.route('/api/v2/expert-files/<file_id>/reverse-preview', methods=['GET'], endpoint='v2xm_preview')
    @token_required
    @roles_required('admin')
    def v2xm_preview(file_id):
        closed = g['_v2_closed']()
        if closed:
            return closed
        if not FID_RE.match(file_id or ''):
            return err(BAD_ID_AR, 404)
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', '/api/bridge/expert-files/%s/reverse-preview' % quote(file_id, safe=''),
                                                          timeout=PREVIEW_TIMEOUT)))

    @app.route('/api/v2/expert-files/<file_id>/reverse', methods=['POST'], endpoint='v2xm_reverse')
    @token_required
    @roles_required('admin')
    def v2xm_reverse(file_id):
        closed = g['_v2_closed']()
        if closed:
            return closed
        if not FID_RE.match(file_id or ''):
            return err(BAD_ID_AR, 404)
        body = g['_v2_body']()
        bad = g['_v2_confirmed'](body)
        if bad:
            return bad
        reason = body.get('reason')
        reason = reason.strip()[:REASON_MAX] if isinstance(reason, str) else ''
        if not reason:
            return err(REASON_AR)
        if not locked_ok():
            return err(LOCK_AR, 409)
        resp = g['_platform_proxy']('POST', '/api/bridge/expert-files/%s/reverse' % quote(file_id, safe=''),
                                    json_body={'reason': reason, 'confirmed': True, 'by': g['_actor_email']()},
                                    timeout=REVERSE_TIMEOUT)
        if not g['_resp_ok'](resp):
            if g['_ef_no_reply'](resp):
                return slow(file_id)
            return ns(g['_v2_mask_auth'](resp))
        doc = g['_proxy_json'](resp)
        if doc.get('status') != 'refunded' or doc.get('reversed') is not True:
            return slow(file_id)          # ٢٠٠ من غير الحالة المتوقعة: ما نقدرش نقول «اتعكس»
        ex = doc.get('expert') if isinstance(doc.get('expert'), dict) else {}
        meta = {k: doc.get(k) for k in ('amount', 'currency', 'file_no', 'consultation_id', 'payment_id', 'clawback', 'uncovered', 'already')
                if doc.get(k) not in (None, '')}
        if ex:
            meta.update({'expert_email': ex.get('email'), 'expert_amount': ex.get('amount'), 'expert_currency': ex.get('currency')})
        meta['reason'] = reason
        if not doc.get('already'):
            g['_audit']('expert_file.reverse', target=file_id, meta=meta)
        return ns(resp)

    @app.route('/api/v2/money/held', methods=['GET'], endpoint='v2xm_held')
    @token_required
    @roles_required('admin')
    def v2xm_held():
        closed = g['_v2_closed']()
        if closed:
            return closed
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', '/api/bridge/escrow/held', timeout=HELD_TIMEOUT)))
