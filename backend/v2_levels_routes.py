# -*- coding: utf-8 -*-
"""R24 م٣ — مستويات العقل و«عمل لوحده» والتعلّم (docs/R24-DASHBOARD-SPEC.md «العقل (المرحلة ٣)»).

    import v2_levels_routes as _v2lv; _v2lv.register(app, globals())

المنطق كله في `brain2/levels.py` و`brain2/alone.py`؛ هنا المسارات بس (أدمن بس · المفتاح `DASH_V2_ENABLED` مقفول ⇒ ٤٠٤ · `no-store`):

  GET  /api/v2/brain/levels                          الأنواع بمستوياتها + إحصاء ٣٠ يوم + حالة سؤال التعلّم
  PUT  /api/v2/brain/levels/<type>      {level}      بيغيّر المستوى. ⛔ الفلوس والنشر ⇒ ٤٠٩ «دايمًا بموافقتك» · نوع فعله ما بيتعكسش ⇒ ٤٠٩ · تدقيق
  POST /api/v2/brain/learn              {work_type, outcome, ref?}   قرار على نوع مش منتج (وافقت زي ما هي · عدّلت · رفضت)
  GET  /api/v2/brain/learn                           أنواع لازم يظهر لها سؤال «تخليني أعملها لوحدي؟»
  POST /api/v2/brain/learn/<type>/answer {answer: yes|no}   «آه» ⇒ لوحده (بنفس الحارس) · «لا» ⇒ يسكّت السؤال ٣٠ يوم
  GET  /api/v2/brain/alone-log?day=today|all         سجل «عمل لوحده»
  POST /api/v2/brain/alone-log/<id>/undo             «رجّعها» — لو مستحيلة دلوقتي بنقول كده بوضوح
  GET  /api/v2/brain/reviews                         مراجعات «راجعت…» الجاهزة لبطاقات طلبات الانضمام (قايمة بيضا، من غير facts ولا meta)
"""
import datetime
import json
import logging
import re

from brain2 import alone, engine, levels

logger = logging.getLogger(__name__)

WT_RE = re.compile(r'^[a-z][a-z_]{1,39}$')
ID_RE = re.compile(r'^[0-9a-f]{32}$')
REVIEW_PRODUCERS = ('application_review',)
REVIEW_DAYS = 21


def register(app, env):
    token_required = env['token_required']
    roles_required = env['roles_required']
    closed = env['_v2_closed']
    ns_out = env['_v2_ns']
    v2_body = env['_v2_body']
    actor = env['_actor_email']
    db = env['db']
    jsonify = env['jsonify']

    def out(payload, status=200):
        return ns_out((jsonify(payload), status) if status != 200 else jsonify(payload))

    def guard():
        gate = closed()
        if gate:
            return gate
        try:
            levels.ensure(db)
        except Exception:   # noqa: BLE001
            db.session.rollback()
            logger.exception('brain2 levels: ensure failed')
            return out({'error': levels.FAIL_AR}, 500)
        return None

    def bad_type(wt):
        return None if isinstance(wt, str) and WT_RE.match(wt) else out({'error': levels.ERR_UNKNOWN}, 404)

    @app.route('/api/v2/brain/levels', methods=['GET'], endpoint='v2lv_get')
    @token_required
    @roles_required('admin')
    def v2lv_get():
        gate = guard()
        if gate:
            return gate
        try:
            return out(levels.view(env))
        except Exception:   # noqa: BLE001
            db.session.rollback()
            logger.exception('brain2 levels: view failed')
            return out({'error': levels.FAIL_AR}, 500)

    @app.route('/api/v2/brain/levels/<work_type>', methods=['PUT'], endpoint='v2lv_put')
    @token_required
    @roles_required('admin')
    def v2lv_put(work_type):
        gate = guard()
        if gate:
            return gate
        bad = bad_type(work_type)
        if bad:
            return bad
        level = v2_body().get('level')
        status, payload = levels.set_level(env, work_type, level if isinstance(level, str) else '', actor())
        return out(payload, status)

    @app.route('/api/v2/brain/learn', methods=['POST'], endpoint='v2lv_learn_post')
    @token_required
    @roles_required('admin')
    def v2lv_learn_post():
        gate = guard()
        if gate:
            return gate
        body = v2_body()
        wt, outcome = body.get('work_type'), body.get('outcome')
        bad = bad_type(wt)
        if bad:
            return bad
        status, payload = levels.record(env, wt, outcome if isinstance(outcome, str) else '', body.get('ref'), actor())
        return out(payload, status)

    @app.route('/api/v2/brain/learn', methods=['GET'], endpoint='v2lv_learn_get')
    @token_required
    @roles_required('admin')
    def v2lv_learn_get():
        gate = guard()
        if gate:
            return gate
        try:
            return out({'prompts': levels.prompts(env), 'streak_needed': levels.LEARN_STREAK})
        except Exception:   # noqa: BLE001
            db.session.rollback()
            logger.exception('brain2 levels: prompts failed')
            return out({'error': levels.FAIL_AR}, 500)

    @app.route('/api/v2/brain/learn/<work_type>/answer', methods=['POST'], endpoint='v2lv_learn_answer')
    @token_required
    @roles_required('admin')
    def v2lv_learn_answer(work_type):
        gate = guard()
        if gate:
            return gate
        bad = bad_type(work_type)
        if bad:
            return bad
        ans = v2_body().get('answer')
        status, payload = levels.answer_learn(env, work_type, ans if isinstance(ans, str) else '', actor())
        return out(payload, status)

    @app.route('/api/v2/brain/alone-log', methods=['GET'], endpoint='v2lv_alone_log')
    @token_required
    @roles_required('admin')
    def v2lv_alone_log():
        gate = guard()
        if gate:
            return gate
        request = env['request']
        day = 'today' if (request.args.get('day') or 'today') == 'today' else None
        try:
            return out({'rows': levels.alone_rows(env, day)})
        except Exception:   # noqa: BLE001
            db.session.rollback()
            logger.exception('brain2 levels: alone log failed')
            return out({'error': levels.FAIL_AR}, 500)

    @app.route('/api/v2/brain/alone-log/<log_id>/undo', methods=['POST'], endpoint='v2lv_alone_undo')
    @token_required
    @roles_required('admin')
    def v2lv_alone_undo(log_id):
        gate = guard()
        if gate:
            return gate
        if not ID_RE.match(log_id or ''):
            return out({'error': 'معرّف غير صالح'}, 400)
        status, payload = levels.undo(env, log_id, actor())
        return out(payload, status)

    @app.route('/api/v2/brain/reviews', methods=['GET'], endpoint='v2lv_reviews')
    @token_required
    @roles_required('admin')
    def v2lv_reviews():
        """أحدث مراجعة جاهزة لكل بطاقة (المرجع `trainer:<معرّف الطلب>`). قايمة بيضا: النقط والاقتراح والسبب وقت الكتابة بس."""
        gate = guard()
        if gate:
            return gate
        Item = engine._models(db)[0]
        since = datetime.datetime.utcnow() - datetime.timedelta(days=REVIEW_DAYS)
        rows = Item.query.filter(Item.producer.in_(REVIEW_PRODUCERS), Item.status.in_(('done_alone', 'proposed', 'approved', 'edited')),
                                 Item.created_at >= since).order_by(Item.created_at.asc()).all()
        res = {}
        for r in rows:          # الأحدث يكتب فوق الأقدم لنفس المرجع
            try:
                b = json.loads(r.body_json) if r.body_json else {}
            except (TypeError, ValueError):
                b = {}
            if not isinstance(b, dict) or not b.get('points'):
                continue
            res[r.target_ref] = {'producer': r.producer, 'text': b.get('text') or '', 'why': b.get('why') or '', 'recommend': b.get('recommend') or '',
                                 'points': b.get('points'), 'source': r.source or '', 'created_at': r.created_at.replace(microsecond=0).isoformat() + 'Z' if r.created_at else ''}
        return out({'reviews': res})
