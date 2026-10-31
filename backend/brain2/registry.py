# -*- coding: utf-8 -*-
"""سجل المنتجين: الكل = producers_ops + producers_biz. أي ملف يفشل استيراده يُسجَّل ولا يُسقط اللوحة."""
import logging

logger = logging.getLogger(__name__)
PRODUCERS = []
try:
    from brain2 import producers_ops as _ops
    PRODUCERS.extend(_ops.PRODUCERS)
except ImportError:
    logger.exception('brain2: producers_ops failed to import')
try:
    from brain2 import producers_biz as _biz
    PRODUCERS.extend(_biz.PRODUCERS)
except ImportError:
    logger.exception('brain2: producers_biz failed to import')


def by_id(pid):
    return next((p for p in PRODUCERS if p.id == pid), None)
