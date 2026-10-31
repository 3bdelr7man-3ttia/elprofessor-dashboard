# -*- coding: utf-8 -*-
"""«العقل» الجولة ٢ — مسارات الخادم (SPEC docs/v2/brain2/SPEC.md §2.5).

قواعد ثابتة في كل المسارات:
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ بلا أي نداء. `Cache-Control: no-store` على كل رد.
  * الفاعل من التوكن (`_actor_email`) لا من الجسم؛ حقل `by` في الجسم يُتجاهل.
  * ⛔ لا مسار هنا يستدعي الذكاء في خيط الطلب: الكتابة كلها في خيط «العقل» الخلفي (`engine.submit`).
  * ⛔ `/items` لا يرجّع `meta` ولا `facts` أبدًا (قايمة بيضا). `/opinions/lookup` لا يكتب ولا يستدعي الذكاء.
  * ⛔ الاعتماد يطلب `confirmed: true`، والتنفيذ الفعلي `producer.apply` لا يُستدعى إلا منه.
المساعدات تُقرأ من `ns` (= globals() في app.py) وقت الطلب.
"""
import datetime
import json
import logging
import re

from flask import jsonify, request

from brain2 import engine, registry, telegram

logger = logging.getLogger(__name__)

ID_RE = re.compile(r'^[0-9a-f]{32}$')
ITEMS_LIMIT = 100
LOOKUP_MAX = 40
CARD_ID_MAX = 190
ERR_BAD_ID = 'معرّف غير صالح'
ERR_NOT_FOUND = 'هذا الاقتراح غير موجود'
ERR_BAD_MODE = 'اختيار غير صالح'
ERR_BAD_TEXT = 'اكتب نصًا من حرف إلى ٩٠٠ حرف'
ERR_BANNED = 'في النص عبارة غير مقبولة. عدّلها ثم أعد المحاولة'
ERR_BAD_CARD = 'بيانات البطاقة غير صالحة'
ERR_BIG_FACTS = 'بيانات البطاقة أكبر من المسموح'
ERR_TOO_MANY = 'عدد البطاقات أكبر من المسموح'
ERR_BAD_SINCE = 'تاريخ غير صالح'
ERR_UNKNOWN_PRODUCER = 'قاعدة غير معروفة'
ERR_DISCARD = 'لا تُحذف هذه الكتابة من هنا'
ERR_BAD_TELEGRAM = 'اختيار تليجرام غير صالح'
ERR_TG_NOT_FOR_OPINION = 'الآراء لا تُرسل إلى تليجرام'
ERR_NO_TEXT_EDIT = 'لا يُعدّل نص هذا الاقتراح هنا؛ افتح الموقع وعدّل الكتلة نفسها'
TG_ID_RE = re.compile(r'^\d{1,20}$')


def _iso(dt):
    from v2_brain_routes import _utc_iso
    return _utc_iso(dt)


def kick(ns, trigger='cron'):
    """يبدأ جولة كتابة في الخيط الخلفي بلا انتظار. أي فشل يُسجَّل ولا يكسر المنادي (نداء الكرون الأصلي)."""
    try:
        if not ns['_v2_enabled']() or not engine.writes_enabled():
            return None
        status, payload = engine.start_run(ns, 'cron' if trigger == 'cron' else 'admin', 'cron')
        return payload.get('run_id') if status == 202 else None
    except Exception:   # noqa: BLE001
        logger.exception('brain2: kick failed')
        return None


def register(app, ns):
    db = ns['db']
    Item, Switch, Run = engine._models(db)
    token_required = ns['token_required']
    roles_required = ns['roles_required']

    def L(name):
        return ns[name]

    def out(payload, status=200):
        return L('_v2_ns')((jsonify(payload), status) if status != 200 else jsonify(payload))

    def item_out(r):
        """قايمة بيضا. ⛔ لا meta ولا facts."""
        p = registry.by_id(r.producer)
        try:
            body = json.loads(r.body_json) if r.body_json else {}
        except (TypeError, ValueError):
            body = {}
        return {'id': r.id, 'producer': r.producer, 'section': r.section, 'kind': r.kind,
                'target_label': r.target_label or '', 'body': body if isinstance(body, dict) else {},
                'status': r.status, 'source': r.source, 'created_at': _iso(r.created_at),
                'decided_at': _iso(r.decided_at), 'decided_by': r.decided_by or '',
                'tag': (p.tag if p else '') or '',
                'approve_label': (body.get('approve_label') if isinstance(body, dict) else '') or (p.approve_label if p else '') or '',
                'last_error': r.last_error or ''}

    def run_out(r):
        try:
            skipped = json.loads(r.skipped_json) if r.skipped_json else {}
        except (TypeError, ValueError):
            skipped = {}
        active = r.finished_at is None and r.started_at is not None and \
            r.started_at > engine.utcnow() - datetime.timedelta(minutes=engine.RUN_LOCK_MINUTES)
        return {'id': r.id, 'trigger': r.trigger, 'started_at': _iso(r.started_at),
                'finished_at': _iso(r.finished_at), 'ai_calls': r.ai_calls or 0, 'items': r.items or 0,
                'skipped': skipped if isinstance(skipped, dict) else {}, 'by': r.by or '', 'active': bool(active)}

    def gate():
        return L('_v2_closed')()

    def confirmed_body():
        body = L('_v2_body')()
        return body, L('_v2_confirmed')(body)

    def listed(pid):
        p = registry.by_id(pid) if isinstance(pid, str) else None
        return p if p is not None and p.listed else None

    def bad_id(item_id):
        return None if ID_RE.match(item_id or '') else out({'error': ERR_BAD_ID}, 400)

    # ------------------------------------------------------------------ المفاتيح
    @app.route('/api/v2/brain/switches', methods=['GET'], endpoint='v2_brain2_switches_get')
    @token_required
    @roles_required('admin')
    def v2_brain2_switches_get():
        closed = gate()
        if closed:
            return closed
        engine.ensure_schema(db)
        rows = {r.producer: r for r in Switch.query.all()}
        items = []
        for p in registry.PRODUCERS:
            if not p.listed:
                continue
            r = rows.get(p.id)
            items.append({'id': p.id, 'section': p.section, 'kind': p.kind, 'label': p.label,
                          'sentence': p.sentence, 'lock_reason': p.lock_reason,
                          'may_run_alone': bool(p.may_run_alone), 'mode': engine.effective_mode(ns, p),
                          'telegram': telegram.enabled(ns, p), 'telegram_ok': telegram.decide_allowed_producer(p),
                          'telegram_can_toggle': telegram.toggle_allowed(p),
                          'updated_at': _iso(r.updated_at) if r else None,
                          'updated_by': (r.updated_by or None) if r else None})
        ws = engine.writer_state(ns)
        payload = {'switches': items, 'writer': ws['writer'],
                   'brain_today': {'used': engine.brain_today(db), 'cap': engine.day_cap()}}
        if ws['label']:
            payload['writer_label'] = ws['label']      # اسم مفتاح القاعدة الشغّال (SPEC-B B1) — يغيب مع مزوّد البيئة
        return out(payload)

    @app.route('/api/v2/brain/switches/<producer_id>', methods=['PUT'], endpoint='v2_brain2_switches_put')
    @token_required
    @roles_required('admin')
    def v2_brain2_switches_put(producer_id):
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        p = listed(producer_id)
        if p is None:
            return out({'error': ERR_UNKNOWN_PRODUCER}, 404)
        mode = body.get('mode') if 'mode' in body else None
        tg = body.get('telegram') if 'telegram' in body else None
        if mode is None and tg is None:
            return out({'error': ERR_BAD_MODE}, 400)
        if mode is not None:
            if mode not in engine.MODES:
                return out({'error': ERR_BAD_MODE}, 400)
            if mode == 'alone' and not p.may_run_alone:
                return out({'error': 'هذا لا يعمل وحده: ' + (p.lock_reason or '')}, 400)
        if 'telegram' in body:
            if not isinstance(tg, bool):
                return out({'error': ERR_BAD_TELEGRAM}, 400)
            if not telegram.toggle_allowed(p):
                return out({'error': ERR_TG_NOT_FOR_OPINION}, 400)
        actor = L('_actor_email')()
        engine.ensure_schema(db)
        row = Switch.query.get(p.id)
        if row is None:
            row = Switch(producer=p.id, mode=mode or engine.effective_mode(ns, p))
            db.session.add(row)
        meta = {}
        if mode is not None:
            row.mode = mode
            meta['mode'] = mode
        if tg is not None:
            row.telegram = tg
            meta['telegram'] = tg
        row.updated_at, row.updated_by = engine.utcnow(), actor
        db.session.commit()
        L('_audit')('v2_brain.switch', target=p.id, meta=meta)
        return out({'id': p.id, 'mode': engine.effective_mode(ns, p), 'telegram': telegram.enabled(ns, p),
                    'updated_at': _iso(row.updated_at), 'updated_by': actor})

    # ------------------------------------------------------------------ العناصر
    @app.route('/api/v2/brain/items', methods=['GET'], endpoint='v2_brain2_items')
    @token_required
    @roles_required('admin')
    def v2_brain2_items():
        closed = gate()
        if closed:
            return closed
        from v2_brain_routes import parse_iso
        q = Item.query
        section = (request.args.get('section') or '').strip()
        if section:
            q = q.filter(Item.section == section[:20])
        status = (request.args.get('status') or 'proposed').strip()
        if status != 'all':
            if status not in engine.STATUSES:
                return out({'error': ERR_BAD_MODE}, 400)
            q = q.filter(Item.status == status)
        kind = (request.args.get('kind') or '').strip()
        if kind:
            q = q.filter(Item.kind == kind[:10])
        if request.args.get('since'):
            since = parse_iso(request.args.get('since'))
            if since is None:
                return out({'error': ERR_BAD_SINCE}, 400)
            q = q.filter(Item.created_at >= since.replace(tzinfo=None))
        engine.sweep_applying(db)
        rows = q.order_by(Item.created_at.desc(), Item.id.desc()).limit(ITEMS_LIMIT).all()
        return out({'items': [item_out(r) for r in rows]})

    @app.route('/api/v2/brain/items/<item_id>/approve', methods=['POST'], endpoint='v2_brain2_approve')
    @token_required
    @roles_required('admin')
    def v2_brain2_approve(item_id):
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        bad = bad_id(item_id)
        if bad:
            return bad
        engine.sweep_applying(db)
        text = None
        if body.get('text') is not None:
            cur = Item.query.get(item_id)
            cur_body = engine._loads(cur.body_json, {}) if cur is not None else {}
            if isinstance(cur_body.get('edits'), list) and cur_body.get('edits'):
                return out({'error': ERR_NO_TEXT_EDIT}, 400)       # مراجعة/تعديل الموقع: التعديلات هي الاقتراح، لا نصّه
            text = engine.clean_text(body.get('text')) if isinstance(body.get('text'), str) else ''
            if not (engine.EDIT_MIN <= len(text) <= engine.EDIT_MAX):
                return out({'error': ERR_BAD_TEXT}, 400)
            if engine.has_banned(text):
                return out({'error': ERR_BANNED}, 400)
        status, payload = engine.apply_item(ns, item_id, L('_actor_email')(), text)
        return out(payload, status)

    def _decide(item_id, new_status, allowed_status, audit, extra_filter=None):
        bad = bad_id(item_id)
        if bad:
            return bad
        engine.sweep_applying(db)
        r = Item.query.get(item_id)
        if r is None:
            return out({'error': ERR_NOT_FOUND}, 404)
        if extra_filter is not None and not extra_filter(r):
            return out({'error': ERR_DISCARD}, 409)
        actor = L('_actor_email')()
        changed = Item.query.filter(Item.id == item_id, Item.status == allowed_status).update(
            {'status': new_status, 'decided_at': engine.utcnow(), 'decided_by': actor}, synchronize_session=False)
        db.session.commit()
        if changed != 1:
            return out({'error': engine.ERR_DECIDED}, 409)
        L('_audit')(audit, target=item_id, meta={'producer': r.producer})
        return out({'ok': True, 'id': item_id, 'status': new_status})

    @app.route('/api/v2/brain/items/<item_id>/reject', methods=['POST'], endpoint='v2_brain2_reject')
    @token_required
    @roles_required('admin')
    def v2_brain2_reject(item_id):
        closed = gate()
        if closed:
            return closed
        _, bad = confirmed_body()
        if bad:
            return bad
        return _decide(item_id, 'rejected', 'proposed', 'brain.reject')

    @app.route('/api/v2/brain/items/<item_id>/discard', methods=['POST'], endpoint='v2_brain2_discard')
    @token_required
    @roles_required('admin')
    def v2_brain2_discard(item_id):
        closed = gate()
        if closed:
            return closed
        _, bad = confirmed_body()
        if bad:
            return bad
        return _decide(item_id, 'discarded', 'done_alone', 'brain.discard', extra_filter=lambda r: r.kind == 'note')

    # ------------------------------------------------------------------ الآراء
    def card_parts(raw):
        """(kind, card_id, cleaned_facts) أو None لو الشكل غير صالح."""
        if not isinstance(raw, dict):
            return None
        kind, cid, facts = raw.get('kind'), raw.get('card_id'), raw.get('facts')
        if isinstance(cid, (int, float)) and not isinstance(cid, bool):
            cid = str(cid)
        if not (isinstance(kind, str) and isinstance(cid, str) and cid.strip() and len(cid) <= CARD_ID_MAX
                and isinstance(facts, dict)):
            return None
        return kind, cid.strip(), engine.clean_opinion_facts(kind, facts)

    def facts_bytes(f):
        return len(json.dumps(f, ensure_ascii=False, default=str).encode('utf-8'))

    @app.route('/api/v2/brain/opinion', methods=['POST'], endpoint='v2_brain2_opinion')
    @token_required
    @roles_required('admin')
    def v2_brain2_opinion():
        closed = gate()
        if closed:
            return closed
        raw = L('_v2_body')()
        if isinstance(raw.get('facts'), dict) and facts_bytes(raw['facts']) > engine.opinion_max_bytes():
            return out({'error': ERR_BIG_FACTS}, 400)
        parts = card_parts(raw)
        if parts is None:
            return out({'error': ERR_BAD_CARD}, 400)
        kind, cid, facts = parts
        if facts_bytes(facts) > engine.opinion_max_bytes():
            return out({'error': ERR_BIG_FACTS}, 400)
        item, reason, queued = engine.submit_opinion(ns, kind, cid, facts)
        if item is not None:
            return out({'item': item_out(item)})
        if queued:
            return out({'queued': True})
        return out({'item': None, 'reason': reason})

    @app.route('/api/v2/brain/opinions/lookup', methods=['POST'], endpoint='v2_brain2_lookup')
    @token_required
    @roles_required('admin')
    def v2_brain2_lookup():
        closed = gate()
        if closed:
            return closed
        cards = L('_v2_body')().get('cards')
        if not isinstance(cards, list):
            return out({'error': ERR_BAD_CARD}, 400)
        if len(cards) > LOOKUP_MAX:
            return out({'error': ERR_TOO_MANY}, 400)
        res = {}
        for raw in cards:
            parts = card_parts(raw)
            if parts is None:
                continue
            kind, cid, facts = parts
            if facts_bytes(facts) > engine.opinion_max_bytes():
                res[cid] = None
                continue
            row = engine.opinion_lookup(ns, kind, cid, facts)
            res[cid] = item_out(row) if row is not None and row.status == 'done_alone' else None
        return out({'items': res})

    # ------------------------------------------------------------------ الجولة
    def parse_only(body):
        only = body.get('only')
        if only is None:
            return None, None
        ids = [only] if isinstance(only, str) else only
        if not (isinstance(ids, list) and ids and all(listed(i) for i in ids)):
            return None, out({'error': ERR_UNKNOWN_PRODUCER}, 400)
        return ids, None

    @app.route('/api/v2/brain/run', methods=['POST'], endpoint='v2_brain2_run')
    @token_required
    @roles_required('admin')
    def v2_brain2_run():
        closed = gate()
        if closed:
            return closed
        body, bad = confirmed_body()
        if bad:
            return bad
        only, bad = parse_only(body)
        if bad:
            return bad
        status, payload = engine.start_run(ns, 'admin', L('_actor_email')(), only)
        return out(payload, status)

    @app.route('/api/v2/brain/runs/latest', methods=['GET'], endpoint='v2_brain2_runs_latest')
    @token_required
    @roles_required('admin')
    def v2_brain2_runs_latest():
        closed = gate()
        if closed:
            return closed
        r = Run.query.order_by(Run.started_at.desc(), Run.id.desc()).first()
        return out({'run': run_out(r) if r is not None else None})

    @app.route('/api/v2/brain/run-cron', methods=['POST'], endpoint='v2_brain2_run_cron')
    def v2_brain2_run_cron():
        closed = gate()
        if closed:
            return closed
        if not L('_metrics_secret_ok')():
            return out({'error': 'unauthorized'}, 401)
        status, payload = engine.start_run(ns, 'cron', 'cron')
        return out(payload, status)

    # ------------------------------------------------------------------ قرار من تليجرام
    def tg_reply(payload, status=200):
        return out(payload, status)

    @app.route('/api/v2/brain/telegram-decide', methods=['POST'], endpoint='v2_brain2_telegram_decide')
    def v2_brain2_telegram_decide():
        """تستدعيه المنصة عند ضغطة زر في تليجرام. ⛔ بالسرّ المشترك فقط (لا JWT)، والفاعل `telegram:<id>` لا من الجسم.
        approve = نفس تنفيذ مسار الاعتماد بلا تعديل · reject = رفض · open = لا شيء. غير `proposed` ⇒ {ok:false, reason:'decided'}."""
        closed = gate()
        if closed:
            return closed
        if not L('_metrics_secret_ok')():
            return tg_reply({'error': 'unauthorized'}, 401)
        raw = request.get_json(silent=True)
        raw = raw if isinstance(raw, dict) else {}
        item_id, action, tg_id = raw.get('item_id'), raw.get('action'), raw.get('tg_user_id')
        if isinstance(tg_id, int) and not isinstance(tg_id, bool):
            tg_id = str(tg_id)
        if not (isinstance(item_id, str) and ID_RE.match(item_id) and action in ('approve', 'reject', 'open')
                and isinstance(tg_id, str) and TG_ID_RE.match(tg_id)):
            return tg_reply({'ok': False, 'reason': 'bad_request'}, 400)
        if action == 'open':
            return tg_reply({'ok': True, 'line': ''})
        admins = telegram.admin_ids()
        if admins is not None and tg_id not in admins:
            return tg_reply({'ok': False, 'reason': 'not_allowed'})
        r = Item.query.get(item_id)
        if r is None:
            return tg_reply({'ok': False, 'reason': 'not_found'})
        if r.status != 'proposed':
            return tg_reply({'ok': False, 'reason': 'decided'})
        p = registry.by_id(r.producer)
        # لا قرار من تليجرام إلا لاقتراح أُرسل إليه فعلًا، ومنتجه مسموح، والمفتاح لم يُطفأ بعد الإرسال.
        if not (telegram.decide_allowed_producer(p) and telegram.enabled(ns, p) and telegram.was_sent(ns, item_id)):
            return tg_reply({'ok': False, 'reason': 'not_allowed'})
        body_d = engine._loads(r.body_json, {})
        if not telegram.can_decide(p, body_d, engine._loads(r.meta_json, {}), engine._loads(r.facts_json, {}), r.target_ref):
            return tg_reply({'ok': False, 'reason': 'not_allowed'})
        actor = 'telegram:' + tg_id
        # الفاعل لمسارات المنصة وسجل التدقيق (`_actor_email` و`_audit` يقرآنه من g.user): طلب تليجرام بلا مستخدم لوحة.
        from types import SimpleNamespace
        from flask import g
        g.user = SimpleNamespace(email=actor)
        if action == 'reject':
            changed = Item.query.filter(Item.id == item_id, Item.status == 'proposed').update(
                {'status': 'rejected', 'decided_at': engine.utcnow(), 'decided_by': actor}, synchronize_session=False)
            db.session.commit()
            if changed != 1:
                return tg_reply({'ok': False, 'reason': 'decided'})
            L('_audit')('brain.reject', target=item_id, meta={'producer': r.producer, 'via': 'telegram'}, actor=actor)
            return tg_reply({'ok': True, 'line': 'رُفض الاقتراح'})
        status, payload = engine.apply_item(ns, item_id, actor, None)
        if status == 200:
            return tg_reply({'ok': True, 'line': telegram.result_line(p, payload.get('info'))})
        if status == 409:
            return tg_reply({'ok': False, 'reason': 'decided'})
        if status == 404:
            return tg_reply({'ok': False, 'reason': 'not_found'})
        reason = 'unknown' if payload.get('no_reply') else 'failed'
        return tg_reply({'ok': False, 'reason': reason, 'line': str(payload.get('error') or '')[:200]})

    # ------------------------------------------------------------------ مرسل رسالة الموقع (للمنصة فقط)
    @app.route('/api/v2/brain/site-message/<msg_id>/sender', methods=['GET'], endpoint='v2_brain2_site_message_sender')
    def v2_brain2_site_message_sender(msg_id):
        """تتحقق منه المنصة من مستلم بريد العقل لسياق `site_message`. ⛔ بالسرّ المشترك فقط (لا JWT)،
        والمفتاح مقفول ⇒ ٤٠٤ قبل أي فحص سرّ. لا يرجّع غير البريد (بلا اسم ولا نص)."""
        closed = gate()
        if closed:
            return closed
        if not L('_metrics_secret_ok')():
            return out({'error': 'unauthorized'}, 401)
        if not (isinstance(msg_id, str) and re.fullmatch(r'[0-9]{1,12}', msg_id)):
            return out({'error': 'not_found'}, 404)
        M = ns.get('Message')
        row = M.query.get(int(msg_id)) if M is not None else None
        email = (getattr(row, 'email', '') or '').strip().lower() if row is not None else ''
        if not email:
            return out({'error': 'not_found'}, 404)
        return out({'email': email})
