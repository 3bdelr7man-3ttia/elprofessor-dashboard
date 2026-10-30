# -*- coding: utf-8 -*-
"""«الدورات والمدرّبون» على الهيكل الجديد — مسارات `/api/v2/courses/*` (الجولة الأخيرة).

بروكسيات رفيعة فوق جسور المنصة (`routes/admin_bridge.py` · `routes/ops_bridge.py` · `routes/live_courses.py`). نفس قواعد D3 بالحرف:
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ قبل أي رحلة للمنصة. `Cache-Control: no-store` على كل رد.
  * كل كتابة تطلب `confirmed: true` بالظبط (غير كده ٤٠٠ قبل أي نداء). الجسم المبعوت للمنصة من قايمة بيضا، ولا حقل `by` (نماذج
    جسور الدورات ما بتعرّفوش): الفاعل بيروح لسجل التدقيق من التوكن.
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) = «ما وصلناش رد» + سطر سجل، مش «اترفض». ٤٠١/٤٠٣ من المنصة ⇒ ٥٠٢.
  * تدقيق عند النجاح بس، وبما **حدث** فعلًا (الأرشفة غير الحذف).
  * ⛔ السعر والنسبة ما بيتعدّلوش من هنا أبدًا: لا حقل سعر في الإنشاء، و`trainer_share_pct` في الجسم بيتجاهل (النسب من جدول النسب).

`register(app, g)` بتتنادى من app.py بسطر واحد، و`g` = globals() بتاعته (الديكوريترز والمساعدات والموديلات).
"""
import re
from urllib.parse import quote

TITLE_MAX = 160
NOTE_MAX = 600
SLUG_BAD_AR = 'معرّف غير صالح'
PAYOUT_MODELS = ('share', 'hourly')
COURSE_TYPES = ('recorded_paid', 'recorded_free')
LIVE_ACTIONS = ('confirm', 'extend', 'cancel')
OFFER_DECISIONS = ('approve', 'reject', 'counter')


def _plain_int(v):
    """رقم صحيح من الجسم (لا منطقي ولا كسر ولا نص)، وإلا None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v == int(v):
        return int(v)
    return None


def _plain_number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']
    ID_RE = g['V2_ID_RE']

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def guard(raw_id=None, write=True):
        """(رد جاهز أو None، الجسم). المفتاح ⇒ المعرّف ⇒ التأكيد (بالترتيب ده)."""
        closed = g['_v2_closed']()
        if closed:
            return closed, None
        if raw_id is not None and not ID_RE.match(raw_id or ''):
            return err(SLUG_BAD_AR), None
        body = g['_v2_body']() if write else {}
        if write:
            bad = g['_v2_confirmed'](body)
            if bad:
                return bad, None
        return None, body

    def write(method, path, platform_body, audit_action, target, meta, params=None):
        """كتابة واحدة على المنصة. `audit_action` اسم أو دالة(رد) تعيد الاسم بما حدث فعلًا."""
        resp = g['_platform_proxy'](method, path, params=params, json_body=platform_body, timeout=25)
        if g['_resp_ok'](resp):
            name = audit_action(resp) if callable(audit_action) else audit_action
            g['_audit'](name, target=target, meta=meta)
            return ns(resp)
        if g['_ef_no_reply'](resp):
            name = audit_action(resp) if callable(audit_action) else audit_action
            return ns(g['_ef_no_reply_resp'](name.split('.')[0], target, name))
        return ns(g['_v2_mask_auth'](resp))

    def read(path):
        return ns(g['_v2_mask_auth'](g['_platform_proxy']('GET', path, timeout=12)))

    # ------------------------------------------------------------------ قراءات جديدة (يرجعها ٤٠٤ كما هي لو الجسر لسه ما اتنشرش)
    @app.route('/api/v2/courses/stats', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2co_stats():
        closed = g['_v2_closed']()
        return closed or read('/api/bridge/courses/stats')

    @app.route('/api/v2/courses/<course_id>/checklist', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2co_checklist(course_id):
        bad, _ = guard(course_id, write=False)
        return bad or read('/api/bridge/courses/%s/checklist' % quote(course_id, safe=''))

    # ------------------------------------------------------------------ إنشاء مسودة مخفية بلا سعر
    @app.route('/api/v2/courses/create', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_create():
        bad, b = guard()
        if bad:
            return bad
        title = b.get('title')
        title = title.strip() if isinstance(title, str) else ''
        if not title or len(title) > TITLE_MAX:
            return err('اكتب عنوان الدورة')
        ctype = b.get('type')
        if ctype not in COURSE_TYPES:
            return err('نوع غير معروف')
        owner, owner_error = g['_course_owner_fields'](b)
        if owner_error:
            return err(owner_error)
        tn = b.get('trainer_name')
        trainer_name = tn.strip()[:255] if isinstance(tn, str) else ''
        db, Course = g['db'], g['Course']
        # الدفتر أولًا (ومعه `commit`): مفتاح عدم التكرار على المنصة هو `dashboard_course_id`.
        ledger = Course(title=title, trainer_name=trainer_name, status='active', price_egp=0, price_usd=0)
        db.session.add(ledger)
        db.session.commit()
        ledger_id = ledger.id
        payload = {'title': title, 'type': ctype, 'trainer_name': trainer_name, 'is_active': False, 'dashboard_course_id': ledger_id}
        payload.update(owner)
        resp = g['_platform_proxy']('POST', '/api/bridge/courses', json_body=payload, timeout=25)
        if g['_resp_ok'](resp):
            data = g['_proxy_json'](resp)
            pid, slug = data.get('id'), data.get('slug')
            row = Course.query.get(ledger_id)
            if row is not None:
                row.platform_course_id = pid
                row.platform_course_slug = slug
                db.session.commit()
            g['_audit']('course.create', target=ledger_id, meta={'title': title, 'platform_owned': bool(owner.get('platform_owned')), 'type': ctype})
            return ns(jsonify({'ok': True, 'platform_course_id': pid, 'platform_course_slug': slug}))
        if g['_ef_no_reply'](resp):
            # الرد ضاع: المنصة ممكن تكون أنشأتها ⇒ نسيب سطر الدفتر ونرجّع شكل «ما وصلناش رد».
            return ns(g['_ef_no_reply_resp']('course', str(ledger_id), 'course.create'))
        row = Course.query.get(ledger_id)
        if row is not None:
            db.session.delete(row)
            db.session.commit()
        return ns(g['_v2_mask_auth'](resp))

    # ------------------------------------------------------------------ اعتماد · رفض
    @app.route('/api/v2/courses/<course_id>/approve', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_approve(course_id):
        bad, b = guard(course_id)
        if bad:
            return bad
        out = {}
        pm = b.get('payout_model')
        if pm is not None:
            if pm not in PAYOUT_MODELS:
                return err('طريقة الدفع غير معروفة')
            out['payout_model'] = pm      # ⛔ `trainer_share_pct` من الجسم ما بيتبعتش أبدًا: النسب من جدول النسب.
        return write('POST', '/api/bridge/courses/%s/approve' % quote(course_id, safe=''), out, 'course.approve', course_id, {'payout_model': pm})

    @app.route('/api/v2/courses/<course_id>/reject', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_reject(course_id):
        bad, b = guard(course_id)
        if bad:
            return bad
        note = b.get('note')
        note = note.strip() if isinstance(note, str) else ''
        if not note:
            return err('اكتب ملاحظاتك أولًا، فهي تصل إلى صاحب الدورة')
        note = note[:NOTE_MAX]
        return write('POST', '/api/bridge/courses/%s/reject' % quote(course_id, safe=''), {'note': note}, 'course.reject', course_id, {'note_len': len(note)})

    # ------------------------------------------------------------------ ظهور · عروض أسعار · أرشفة/حذف
    @app.route('/api/v2/courses/<course_id>/visibility', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_visibility(course_id):
        bad, b = guard(course_id)
        if bad:
            return bad
        if not isinstance(b.get('is_active'), bool):
            return err('قيمة غير صالحة')
        on = b['is_active']
        return write('PUT', '/api/bridge/courses/%s' % quote(course_id, safe=''), {'is_active': on}, 'course.show' if on else 'course.hide', course_id, {'is_active': on})

    @app.route('/api/v2/courses/<course_id>/bid', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_bid(course_id):
        bad, b = guard(course_id)
        if bad:
            return bad
        if not isinstance(b.get('bid_enabled'), bool):
            return err('قيمة غير صالحة')
        on = b['bid_enabled']
        return write('PUT', '/api/bridge/courses/%s' % quote(course_id, safe=''), {'bid_enabled': on}, 'course.bid_on' if on else 'course.bid_off', course_id, {'bid_enabled': on})

    @app.route('/api/v2/courses/<course_id>/archive', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_archive(course_id):
        bad, b = guard(course_id)
        if bad:
            return bad
        hard = b.get('hard') is True
        # ⛔ الفعل المسجَّل هو ما **حدث**: منصة أقدم تتجاهل `hard` وتؤرشف، فالرد (`deleted`) هو الحَكَم.
        return write('DELETE', '/api/bridge/courses/%s' % quote(course_id, safe=''), None,
                     lambda resp: 'course.delete' if g['_proxy_json'](resp).get('deleted') is True else 'course.archive', course_id, {'hard': hard},
                     params={'hard': 'true'} if hard else None)

    # ------------------------------------------------------------------ موعد الدورة الحيّة
    @app.route('/api/v2/courses/<course_id>/schedule', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_schedule(course_id):
        bad, b = guard(course_id)
        if bad:
            return bad
        out = {}
        for key in ('start_date', 'zoom_link'):
            v = b.get(key)
            if v is None:
                continue
            if not isinstance(v, str):
                return err('قيمة غير صالحة')
            if v.strip():
                out[key] = v.strip()
        if b.get('max_seats') is not None:
            seats = _plain_int(b.get('max_seats'))
            if seats is None or seats < 0:
                return err('عدد المقاعد غير صالح')
            out['max_seats'] = seats
        # ⛔ `confirmed` عندنا = تأكيد الشاشة ولا يُمرَّر أبدًا. «ثبّت الموعد للمتعلّمين» اسمه عندنا `pin_schedule` وهو وحده اللي بيبقى `confirmed` على المنصة.
        if b.get('pin_schedule') is not None:
            out['confirmed'] = bool(b['pin_schedule'])
        if not out:
            return err('لا يوجد تغيير')
        return write('PUT', '/api/bridge/courses/%s/schedule' % quote(course_id, safe=''), out, 'live.schedule', course_id, {'keys': sorted(out.keys())})

    # ------------------------------------------------------------------ عروض الأسعار
    @app.route('/api/v2/courses/offers/<offer_id>/decide', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_offer_decide(offer_id):
        bad, b = guard(offer_id)
        if bad:
            return bad
        decision = b.get('decision')
        if decision not in OFFER_DECISIONS:
            return err('قرار غير معروف')
        out = {'decision': decision}
        amount = None
        if decision == 'counter':
            amount = _plain_number(b.get('amount'))
            if amount is None or amount <= 0:
                return err('اكتب المبلغ')
            out['amount'] = amount
        return write('POST', '/api/bridge/course-offers/%s/decide' % quote(offer_id, safe=''), out, 'course_offer.' + decision, offer_id, {'amount': amount})

    # ------------------------------------------------------------------ قرار الدورة الحيّة
    @app.route('/api/v2/courses/live/<slug>/decide', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2co_live_decide(slug):
        bad, b = guard(slug)
        if bad:
            return bad
        action = b.get('action')
        if action not in LIVE_ACTIONS:
            return err('إجراء غير معروف')
        hours = 48
        if b.get('extend_hours') is not None:
            hours = _plain_int(b.get('extend_hours'))
            if hours is None or hours < 1 or hours > 720:
                return err('مدة التمديد غير صالحة')
        return write('POST', '/api/bridge/live/%s/decide' % quote(slug, safe=''), {'action': action, 'extend_hours': hours}, 'live.' + action, slug, {'extend_hours': hours if action == 'extend' else None})

    return app
