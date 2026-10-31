# -*- coding: utf-8 -*-
"""سجل المنتجين: الكل = producers_ops + producers_biz + producers_files + producers_site. أي ملف يفشل استيراده يُسجَّل ولا يُسقط اللوحة."""
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
try:
    from brain2 import producers_files as _files
    PRODUCERS.extend(_files.PRODUCERS)
except ImportError:
    logger.exception('brain2: producers_files failed to import')

try:
    from brain2 import producers_site as _site
    PRODUCERS.extend(_site.PRODUCERS)
except ImportError:
    logger.exception('brain2: producers_site failed to import')

# «اسألني على تليجرام» (SPEC-B §B2). ⛔ لا يغيّر العقد: اشتراك على مستوى المنتج.
#  * TELEGRAM_OK: منتجات يجوز اعتماد اقتراحها أو رفضه بزر من تليجرام. أي منتج خارجها (فلوس، مقفول بقرار) يصله رابط
#    «افتح في اللوحة» فقط ولا يعتمده تليجرام أبدًا. الآراء (kind=opinion) لا تُرسل إلى تليجرام مطلقًا.
#  * TELEGRAM_DEFAULT_ON: المنتجات التي يكون «اسألني على تليجرام» فيها مفعّلًا قبل أن يلمسه المؤسس.
TELEGRAM_OK = frozenset({'reply_draft', 'file_review', 'course_review'})
TELEGRAM_DEFAULT_ON = frozenset({'reply_draft', 'file_review', 'course_review'})


def by_id(pid):
    return next((p for p in PRODUCERS if p.id == pid), None)
