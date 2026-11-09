# -*- coding: utf-8 -*-
"""حراسة التكرار وإعادة إبلاغ الرفض للمنتجات الخارجية (library_contribution / training_item / ask).

  * `already_decided`: بند اتعتمد/اتنفّذ/اترفض قبل كده لنفس المرجع ⇒ ما يتقترحش تاني.
  * رفض اتسجّل عندنا بس المنصة ما وصلهاش (`last_error='notify_failed'`) ⇒ `retry_reject` يعيد `on_reject`
    بدل ما البند يفضل معلّق عند المنصة.
"""
import json
import logging

NOTIFY_FAILED = 'notify_failed'
DECIDED = ('approved', 'edited', 'applying', 'unknown', 'rejected')
logger = logging.getLogger(__name__)


def _item(ctx):
    from brain2.engine import _models
    return _models(ctx.ns['db'])[0]


def already_decided(ctx, producer_id, ref):
    """True لو فيه صف محلي حاسم للمرجع. لو الصف مرفوض والإبلاغ فاشل نحاول نعيد الإبلاغ قبل ما نتخطاه."""
    try:
        Item = _item(ctx)
        return Item.query.filter(Item.producer == producer_id, Item.target_ref == ref,
                                 Item.status.in_(DECIDED)).first() is not None
    except Exception:   # noqa: BLE001
        return False


def save_reject_reason(row, reason):
    try:
        row.applied_json = json.dumps({'reject_reason': (reason or '')[:300]}, ensure_ascii=False)
    except Exception:   # noqa: BLE001
        pass


def retry_reject(ctx, producer_id, ref, hook):
    """لو فيه صف مرفوض إبلاغه فشل ⇒ نعيد `hook(ctx, target, reason)`. بيرجّع True لو اتبلّغ الآن."""
    try:
        from brain2.contract import Target
        from brain2.engine import _loads
        Item = _item(ctx)
        row = Item.query.filter(Item.producer == producer_id, Item.target_ref == ref, Item.status == 'rejected',
                                Item.last_error == NOTIFY_FAILED).first()
        if row is None:
            return False
        saved = _loads(row.applied_json, {})
        reason = saved.get('reject_reason') if isinstance(saved, dict) else ''
        target = Target(ref=row.target_ref, label=row.target_label or '', facts=_loads(row.facts_json, {}),
                        meta=_loads(row.meta_json, {}))
        res = hook(ctx, target, reason or '')
        if getattr(res, 'ok', False):
            row.last_error = None
            ctx.ns['db'].session.commit()
            return True
    except Exception:   # noqa: BLE001
        logger.exception('brain2: reject retry failed for %s', producer_id)
        try:
            ctx.ns['db'].session.rollback()
        except Exception:   # noqa: BLE001
            pass
    return False
