# -*- coding: utf-8 -*-
"""R24 م٣ — «عمل لوحده»: العقل ينفّذ بنفسه الأنواع اللي مستواها «لوحده»، وبنفس دوال الفعل اللي بتستعملها الداشبورد.

  * ⛔ ما بيتنفّذ حاجة إلا لو `levels.level_of(...) == 'alone'` **والنوع مؤهَّل** (مش مقفول وفعله بيتعكس) — فحص تاني هنا غير فحص التخزين.
  * ⛔ ولا نداء ذكاء: القواعد هنا بسيطة (زائر عادي من غير علامة · تعليق حكم عليه فحص التعليقات إنه مسيء). الذكاء بتاع «المراجعة» في الجولة.
  * كل فعل بيتسجّل في `alone_log` (إيه · على مين · إمتى · بيانات الرجوع) **بعد** ما ينجح على المنصة بس.
  * الرجوع (`run_undo`): بنفس الدوال المعاكسة. لو الرجوع مستحيل دلوقتي (المنصة رفضت، أو اتلغى، أو الاقتراح اتحسم) بنقول كده بوضوح.
  * سقف لكل نوع في كل فحص (`PER_TICK`) — لا طوفان ولا نداء زيادة.
  * الملاحظات اللي بيكتبها العقل لوحده (`done_alone`) بتتسجّل من `engine._store` عبر `log_note` تحت، ورجوعها «احذفها».
"""
import logging

from brain2 import levels

logger = logging.getLogger(__name__)

PER_TICK = 5
GATHER_LIMIT = 200

MSG_VISITOR_UNDO = 'رجّعنا الزائر لقايمة الانتظار. الرسالة اللي وصلته من المنصة ما بتتسحبش.'
MSG_COMMENT_UNDO = 'رجّعنا التعليق وبقى ظاهر تاني.'
MSG_NOTE_UNDO = 'اتشالت الملاحظة.'
ERR_PLATFORM = 'مقدرناش نرجّعها دلوقتي — تعذّر الاتصال بالمنصة'
ERR_NOTE_GONE = 'مينفعش ترجّعها دلوقتي — الملاحظة اتحسمت قبل كده'


def _call(ns, name, *a, **k):
    fn = ns.get(name)
    if not callable(fn):
        return None
    return fn(*a, **k)


def _rows_of(resp, keys):
    body = levels._json_of(resp)
    if isinstance(body, dict):
        for k in keys:
            if isinstance(body.get(k), list):
                body = body[k]
                break
    return [r for r in body if isinstance(r, dict)] if isinstance(body, list) else None


def _err_text(resp, default):
    js = levels._json_of(resp)
    msg = js.get('error') if isinstance(js, dict) else ''
    return msg if isinstance(msg, str) and msg.strip() else default


# ------------------------------------------------------------------ زائر عادي
def _gather_visitors(ns):
    """زوّار طلبوا فتح المنصة، بإيميل عادي ومن غير أي علامة اشتباه. غير كده يفضل قرارك."""
    resp = _call(ns, '_platform_proxy', 'GET', '/api/bridge/pending-users', params={'limit': GATHER_LIMIT})
    if resp is None or not levels._ok(ns, resp):
        return None
    users = _rows_of(resp, ('users', 'items', 'rows'))
    if users is None:
        return None
    out = []
    for u in users:
        ir = u.get('invite_request') if isinstance(u.get('invite_request'), dict) else {}
        flags = u.get('flag_labels')
        uid = str(u.get('id') or '').strip()
        if (ir.get('status') or 'none') != 'requested' or not uid or not str(u.get('email') or '').strip():
            continue
        if isinstance(flags, list) and any(str(f).strip() for f in flags):
            continue
        name = str(u.get('full_name') or u.get('name') or '').strip() or 'زائر'
        out.append({'ref': 'pu:' + uid, 'user_id': uid, 'name': name[:80]})
    return out


def _do_visitor_open(ns, t, actor):
    resp = _call(ns, '_pending_user_access_write', t['user_id'], 'member', '', actor)
    if resp is None or not levels._ok(ns, resp):
        return False, _err_text(resp, 'تعذّر الفتح')
    return True, {'work_type': 'visitor_open', 'what': 'فتح المنصة لـ' + t['name'], 'label': t['name'],
                  'undo': {'kind': 'visitor_open', 'user_id': t['user_id']}}


def _undo_visitor_open(ns, payload, actor):
    uid = str(payload.get('user_id') or '')
    if not uid:
        return False, 'مينفعش ترجّعها دلوقتي'
    resp = _call(ns, '_pending_user_access_write', uid, 'pending', 'رجوع من العقل بطلب المؤسس', actor)
    if resp is None or not levels._ok(ns, resp):
        return False, 'مقدرناش نرجّعها دلوقتي — ' + _err_text(resp, 'المنصة ما قبلتش')
    return True, MSG_VISITOR_UNDO


# ------------------------------------------------------------------ تعليق مسيء بوضوح
def _gather_comments(ns):
    """تعليقات مستنية حكم عليها فحص التعليقات إنها مسيئة صراحة (فحص اتعمل + مسيء). الباقي قرارك."""
    resp = _call(ns, '_platform_proxy', 'GET', '/api/bridge/opinions', params={'status': 'pending'})
    if resp is None or not levels._ok(ns, resp):
        return None
    rows = _rows_of(resp, ('opinions', 'items', 'rows'))
    if rows is None:
        return None
    out = []
    for o in rows:
        mod = o.get('ai_moderation') if isinstance(o.get('ai_moderation'), dict) else {}
        oid = str(o.get('id') or '').strip()
        if not oid or (o.get('status') or 'pending') != 'pending' or mod.get('ai_checked') is not True or mod.get('abusive') is not True:
            continue
        out.append({'ref': 'op:' + oid, 'opinion_id': oid, 'name': str(o.get('topic_title') or 'تعليق')[:80]})
    return out


def _do_comment_reject(ns, t, actor):
    resp = _call(ns, '_opinion_moderate', t['opinion_id'], 'reject', actor)
    if resp is None or not levels._ok(ns, resp):
        return False, _err_text(resp, 'تعذّر الإخفاء')
    return True, {'work_type': 'comment_reject_abusive', 'what': 'إخفاء تعليق مسيء على «%s»' % t['name'], 'label': t['name'],
                  'undo': {'kind': 'comment_reject', 'opinion_id': t['opinion_id']}}


def _undo_comment_reject(ns, payload, actor):
    oid = str(payload.get('opinion_id') or '')
    if not oid:
        return False, 'مينفعش ترجّعها دلوقتي'
    resp = _call(ns, '_opinion_moderate', oid, 'approve', actor)
    if resp is None or not levels._ok(ns, resp):
        return False, 'مقدرناش نرجّعها دلوقتي — ' + _err_text(resp, 'المنصة ما قبلتش')
    return True, MSG_COMMENT_UNDO


# ------------------------------------------------------------------ ملاحظة كتبها العقل لوحده
def _undo_note(ns, payload, actor):
    """«احذفها» نفسها: ملاحظة `done_alone` ⇒ `discarded`. أي حالة تانية ⇒ اتحسمت قبل كده."""
    from brain2 import engine
    db = ns['db']
    Item = engine._models(db)[0]
    iid = str(payload.get('item_id') or '')
    changed = Item.query.filter(Item.id == iid, Item.status == 'done_alone').update(
        {'status': 'discarded', 'decided_at': engine.utcnow(), 'decided_by': str(actor)[:255]}, synchronize_session=False)
    db.session.commit()
    if changed != 1:
        return False, ERR_NOTE_GONE
    return True, MSG_NOTE_UNDO


# ------------------------------------------------------------------ الجدول
# work_type -> (gather, do, undo kind). do بترجّع (True, {work_type, what, label, undo}) أو (False, رسالة).
ACTIONS = {
    'visitor_open': (_gather_visitors, _do_visitor_open),
    'comment_reject_abusive': (_gather_comments, _do_comment_reject),
}
UNDOERS = {
    'visitor_open': _undo_visitor_open,
    'comment_reject': _undo_comment_reject,
    'discard_item': _undo_note,
}


def run_undo(ns, payload, actor):
    fn = UNDOERS.get(str((payload or {}).get('kind') or ''))
    if fn is None:
        return False, 'مينفعش ترجّعها دلوقتي'
    try:
        return fn(ns, payload, actor)
    except Exception:   # noqa: BLE001
        logger.exception('brain2 alone: undo raised')
        try:
            ns['db'].session.rollback()
        except Exception:   # noqa: BLE001
            pass
        return False, ERR_PLATFORM


def log_note(ns, row, producer):
    """يسجّل ملاحظة/مراجعة كتبها العقل لوحده (`done_alone`) في `alone_log` برجوع «احذفها». بيتنادى من `engine._store`.
    الآراء (kind=opinion) ما بتتسجّلش واحدة واحدة: كتير، وبتتعدّ في الإحصاء من صفوفها."""
    wt = levels.get_type(producer.id)
    if wt is None or producer.kind == 'opinion' or not levels.eligible(wt):
        return ''
    what = 'كتب %s على «%s»' % ((producer.tag or producer.label or 'ملاحظة'), (row.target_label or 'عنصر')[:80])
    return levels.log_alone(ns, wt.id, what, target_ref=row.id, target_label=row.target_label or '',
                            undo={'kind': 'discard_item', 'item_id': row.id})


def run_pending(ns, actor='العقل'):
    """فحص واحد: كل نوع مستواه «لوحده» وله فعل ⇒ يجمع ويفّذ (سقف `PER_TICK`). يرجع {نوع: عدد اللي اتنفّذ}. ⛔ ولا نداء ذكاء."""
    from brain2 import engine
    done = {}
    if not engine.writes_enabled():
        return done
    for wt_id, (gather, do) in ACTIONS.items():
        wt = levels.get_type(wt_id)
        if wt is None or not levels.eligible(wt) or levels.level_of(ns, wt) != 'alone':
            continue
        try:
            targets = gather(ns)
        except Exception:   # noqa: BLE001
            logger.exception('brain2 alone: gather failed for %s', wt_id)
            continue
        if targets is None:
            continue            # المصدر ما وصلش: مفيش تنفيذ على الأعمى
        n = 0
        for t in targets[:PER_TICK]:
            try:
                ok, res = do(ns, t, actor)
            except Exception:   # noqa: BLE001
                logger.exception('brain2 alone: action raised for %s', wt_id)
                try:
                    ns['db'].session.rollback()
                except Exception:   # noqa: BLE001
                    pass
                break
            if not ok:
                logger.warning('brain2 alone: %s not done (%s)', wt_id, str(res)[:120])
                continue
            levels.log_alone(ns, res['work_type'], res['what'], target_ref=t['ref'], target_label=res.get('label', ''), undo=res['undo'])
            n += 1
        if n:
            done[wt_id] = n
    return done
