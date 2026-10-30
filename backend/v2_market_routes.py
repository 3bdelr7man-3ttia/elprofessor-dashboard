# -*- coding: utf-8 -*-
"""«سوق الخدمات» على الهيكل الجديد (الجولة النهائية) — ثلاثة بروكسيات رفيعة فوق جسر السوق على المنصة.

    GET  /api/v2/market/requests                      ⇒ /api/bridge/market/requests              (قائمة كل الطلبات بفلاتر وصفحات)
    POST /api/v2/market/requests/<id>/relane          ⇒ /api/bridge/market/requests/<id>/relane  (نقل الطلب لحارته الصحيحة)
    POST /api/v2/market/requests/<id>/link-course     ⇒ /api/bridge/market/requests/<id>/annotate (ربط دورة بطلب مفتوح)

كلها: المفتاح (`DASH_V2_ENABLED`) مقفول ⇒ ٤٠٤ بلا أي نداء · `Cache-Control: no-store` · نداء واحد ولا إعادة محاولة ·
القراءة للأدمن والموظف (زي لوحة السوق القديمة) والكتابة للأدمن بس بـ`confirmed:true` · `by` من التوكن مش من الجسم ·
الجسم المبعوت للمنصة من قايمة بيضا · تدقيق عند النجاح بس · رد كتابة ضاع ⇒ «ما وصلناش رد».

⛔ `app.py` بيعرّف `_platform_proxy` و`_market_proxy` بعد سطر التسجيل، فكل الدوال المساعدة بتتقرا من `ns` وقت النداء
(مش وقت التسجيل). `token_required` و`roles_required` وحدهم بيتاخدوا وقت التسجيل (معرّفين فوق).
"""

LANES = ('request', 'course_request', 'public_service', 'training_offer', 'all')
STATUSES = ('open', 'matched', 'closed', 'all')
NEED_KINDS = ('expert', 'service', 'course', 'book', 'training_offer', 'other')
AUTHOR_KINDS = ('member', 'platform', 'all')
RELANE_NEEDS = ('expert', 'service', 'course', 'book', 'other')    # ⛔ الطلب ما يتنقلش لحارة العروض (training_offer)
Q_MAX = 80
NOTE_MAX = 300
COURSE_MAX = 200
MISSING_AR = 'سوق الخدمات غير متاح بعد على المنصة'


def _int(v, default, lo, hi):
    try:
        n = int(str(v).strip())
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def register(app, ns):
    token_required = ns['token_required']
    roles_required = ns['roles_required']

    def g(name):
        return ns[name]

    def jsonify(*a, **kw):
        return ns['jsonify'](*a, **kw)

    @app.route('/api/v2/market/requests', methods=['GET'], endpoint='v2s_market_requests')
    @token_required
    @roles_required('admin', 'employee')
    def v2s_market_requests():
        closed = g('_v2_closed')()
        if closed:
            return closed
        args = ns['request'].args
        params = {}
        lane = (args.get('lane') or 'all').strip()
        params['lane'] = lane if lane in LANES else 'all'
        status = (args.get('status') or 'all').strip()
        params['status'] = status if status in STATUSES else 'all'
        need = (args.get('need_kind') or '').strip()
        if need in NEED_KINDS:
            params['need_kind'] = need
        author = (args.get('author_kind') or 'all').strip()
        params['author_kind'] = author if author in AUTHOR_KINDS else 'all'
        q = (args.get('q') or '').strip()[:Q_MAX]
        if q:
            params['q'] = q
        inc = (args.get('include_test') or '').strip().lower()
        params['include_test'] = 'false' if inc in ('0', 'false') else 'true'
        params['limit'] = _int(args.get('limit'), 50, 1, 100)
        params['skip'] = _int(args.get('skip'), 0, 0, 100000)
        resp = g('_v2_get')('/api/bridge/market/requests', params=params)
        if isinstance(resp, tuple) and int(resp[1]) == 404:
            return g('_v2_ns')((jsonify({'error': MISSING_AR, 'bridge_missing': True}), 404))
        return resp

    def _checked(request_id):
        """(ردّ الرفض أو None, الجسم): المفتاح ثم المعرّف ثم التأكيد الصريح."""
        closed = g('_v2_closed')()
        if closed:
            return closed, None
        if not g('V2_ID_RE').match(request_id or ''):
            return g('_v2_ns')((jsonify({'error': 'هذا الطلب غير موجود'}), 404)), None
        body = g('_v2_body')()
        bad = g('_v2_confirmed')(body)
        if bad:
            return bad, None
        return None, body

    @app.route('/api/v2/market/requests/<request_id>/relane', methods=['POST'], endpoint='v2s_market_relane')
    @token_required
    @roles_required('admin')
    def v2s_market_relane(request_id):
        err, body = _checked(request_id)
        if err:
            return err
        need = body.get('need_kind')
        if not isinstance(need, str) or need.strip() not in RELANE_NEEDS:
            return g('_v2_ns')((jsonify({'error': 'نوع الطلب غير معروف'}), 400))
        need = need.strip()
        reason = g('_ef_note')(body.get('reason'), NOTE_MAX)
        path = '/api/bridge/market/requests/%s/relane' % ns['quote'](request_id, safe='')
        return g('_v2_write')('POST', path, {'need_kind': need, 'reason': reason}, 'market.relane', request_id, {'need_kind': need})

    @app.route('/api/v2/market/requests/<request_id>/link-course', methods=['POST'], endpoint='v2s_market_link_course')
    @token_required
    @roles_required('admin')
    def v2s_market_link_course(request_id):
        err, body = _checked(request_id)
        if err:
            return err
        course = body.get('course')
        if not isinstance(course, str):
            return g('_v2_ns')((jsonify({'error': 'اختر دورة'}), 400))
        course = course.strip()[:COURSE_MAX]
        path = '/api/bridge/market/requests/%s/annotate' % ns['quote'](request_id, safe='')
        # ⛔ قايمة بيضا: `linked_course_id` وحده (لا evidence_note ولا join_goal ولا specialty من هنا).
        return g('_v2_write')('POST', path, {'linked_course_id': course}, 'market.link_course', request_id, {'course': course})
