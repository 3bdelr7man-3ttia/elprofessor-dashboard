# -*- coding: utf-8 -*-
"""R28 — «استرداد» شراء دورة اندفع يدويًا + «مستحق للخبراء والمدرّبين» من محافظهم.

    import v2_purchase_refunds_routes as _v2pr; _v2pr.register(app, globals())

  GET  /api/v2/purchases/<payment_id>/refund-preview   اللي هيحصل قبل التأكيد (من جسر المنصة كما هو)
  POST /api/v2/purchases/<payment_id>/refund           {reason, confirmed:true}   ⇐ POST /api/bridge/purchases/<id>/refund
  GET  /api/v2/money/owed                              المستحق لأصحاب الأعمال لكل عملة ⇐ GET /api/bridge/wallets/owed

⛔ قواعد الفلوس (CLAUDE.md):
  * أدمن بس + المفتاح `DASH_V2_ENABLED` (مقفول ⇒ ٤٠٤) + `no-store`.
  * نوع الشغل `course_refund` مقفول على «يسألك» في `brain2/levels.py` (lock=money، ومفيش مستوى غير `ask`). الحارس هنا في الخادم:
    لو المستوى المحسوب طلع أي حاجة غير «يسألك» (جدول اتعدّل غلط) ⇒ ٤٠٩ قبل أي نداء للمنصة. والتنفيذ نفسه بضغطة أدمن بتأكيد صريح بس.
  * التأكيد `confirmed: true` بالظبط، والسبب إلزامي. الجسم المبعوت للمنصة قايمة بيضا، و`by` من التوكن مش من المتصفح.
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) ⇒ «ما وصلناش رد» + سطر سجل (الضغطة التانية آمنة: المنصة متماثلة لكل دفعة).
  * النجاح بيتحقّق من **رد المنصة** (`status == 'refunded'`)، والتدقيق بعد النجاح بس وبأرقام المنصة.
"""
import re
from urllib.parse import quote

from brain2 import levels

WORK_TYPE = 'course_refund'
REASON_MAX = 500
PID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')
REASON_AR = 'اكتب سبب الاسترداد'
LOCK_AR = 'الاسترداد بموافقتك دائمًا، ولا يُنفَّذ إلا بتأكيدك'
BAD_ID_AR = 'هذه الدفعة غير موجودة'
SLOW_AR = 'المنصة بتاخد وقت — استنى ثواني وافتح الصفحة تاني قبل ما تجرّب، عشان ما يتكررش'
# r29: نداء الاسترداد على المنصة ممكن ياخد ~١٠ ثواني (عكس نصيب المدرّب + غلق الدورة + إيصال)، والمهلة القديمة (٢٥ث) مع بوابة قدّامها قطعت أول ضغطة في اختبار حيّ.
REFUND_TIMEOUT = 40
# «المستحق»: المنصة بتعدّ محفظة كل صاحب عمل، فبياخد وقت أطول من القراية العادية (١٢ث).
OWED_TIMEOUT = 30
PREVIEW_TIMEOUT = 20


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def locked_ok():
        """⛔ الحارس الصلب: الاسترداد ما يبقاش «لوحده» ولا «يقترح» أبدًا — بس «يسألك»."""
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

    def slow(payment_id):
        """رد المنصة ضاع أو اتأخر: الاسترداد ممكن يكون اتنفّذ. سطر سجل + جملة صادقة (لا «تعذّر» عامة)، والواجهة بتعيد الفحص بنفسها."""
        g['_audit']('purchase.no_reply', target=payment_id, meta={'attempt': 'refund'})
        return ns((jsonify({'error': SLOW_AR, 'no_reply': True}), 502))

    @app.route('/api/v2/purchases/<payment_id>/refund-preview', methods=['GET'], endpoint='v2pr_preview')
    @token_required
    @roles_required('admin')
    def v2pr_preview(payment_id):
        closed = g['_v2_closed']()
        if closed:
            return closed
        if not PID_RE.match(payment_id or ''):
            return err(BAD_ID_AR, 404)
        # مهلة أطول (٢٠ث): الواجهة بتفحص بيها بعد ما الاسترداد يتأخر، والمنصة ممكن لسه مشغولة بإنهائه.
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', '/api/bridge/purchases/%s/refund-preview' % quote(payment_id, safe=''), timeout=PREVIEW_TIMEOUT)))

    @app.route('/api/v2/purchases/<payment_id>/refund', methods=['POST'], endpoint='v2pr_refund')
    @token_required
    @roles_required('admin')
    def v2pr_refund(payment_id):
        closed = g['_v2_closed']()
        if closed:
            return closed
        if not PID_RE.match(payment_id or ''):
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
        resp = g['_platform_proxy']('POST', '/api/bridge/purchases/%s/refund' % quote(payment_id, safe=''),
                                    json_body={'reason': reason, 'full': True, 'confirmed': True, 'by': g['_actor_email']()},
                                    timeout=REFUND_TIMEOUT)
        if not g['_resp_ok'](resp):
            if g['_ef_no_reply'](resp):
                return slow(payment_id)
            return ns(g['_v2_mask_auth'](resp))
        doc = g['_proxy_json'](resp)
        if doc.get('status') != 'refunded':
            # ٢٠٠ من غير الحالة المتوقعة: ما نقدرش نقول «اتردّت» — زي رد ضاع.
            return slow(payment_id)
        seller = doc.get('seller') if isinstance(doc.get('seller'), dict) else {}
        meta = {k: doc.get(k) for k in ('amount', 'currency', 'buyer_email', 'title', 'clawback', 'already') if doc.get(k) not in (None, '')}
        if seller:
            meta.update({'seller_email': seller.get('email'), 'seller_amount': seller.get('amount'), 'seller_currency': seller.get('currency')})
        meta['reason'] = reason
        if not doc.get('already'):
            g['_audit']('purchase.refund', target=payment_id, meta=meta)
        return ns(resp)

    @app.route('/api/v2/money/owed', methods=['GET'], endpoint='v2pr_owed')
    @token_required
    @roles_required('admin')
    def v2pr_owed():
        closed = g['_v2_closed']()
        if closed:
            return closed
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', '/api/bridge/wallets/owed', timeout=OWED_TIMEOUT)))
