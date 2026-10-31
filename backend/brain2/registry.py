# -*- coding: utf-8 -*-
"""سجل المنتجين: الكل = producers_ops + producers_biz + producers_files + producers_site. أي ملف يفشل استيراده يُسجَّل ولا يُسقط اللوحة."""
import logging

from brain2.contract import Producer

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
    from brain2 import producers_links as _links
    PRODUCERS.extend(_links.PRODUCERS)
except ImportError:
    logger.exception('brain2: producers_links failed to import')

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


# اقتراحات الأنظمة المتصلة (SPEC-B B5a): المعرّف `mcp:<اسم الرمز>`؛ بلا `apply` فاعتمادها «احتفظ بها» فقط، ولا تظهر في شاشة القواعد.
_EXTERNAL = Producer(
    id='mcp', section='home', kind='note', label='اقتراح من نظام متصل', sentence='', lock_reason='يسألك دائمًا لأن مصدره خارج العقل.',
    may_run_alone=False, default_mode='ask', per_run_cap=0, gather=lambda ctx: [], prompt=lambda t: ('', ''),
    validate=lambda d, t: None, tag='من نظام متصل', approve_label='احتفظ بها', listed=False)


def by_id(pid):
    hit = next((p for p in PRODUCERS if p.id == pid), None)
    if hit is None and isinstance(pid, str) and pid.startswith('mcp:'):
        return _EXTERNAL
    return hit
