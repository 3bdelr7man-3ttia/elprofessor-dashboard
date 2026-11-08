# -*- coding: utf-8 -*-
"""«العقل يشتغل لوحده» — مُشغِّل داخلي بمواعيد ثابتة بتوقيت القاهرة، بدل الاعتماد على n8n وحده.

لماذا: الجولة كانت تبدأ فقط من `POST /api/ai/agents/run-cron` (n8n، الساعة ٨ مساءً)، وعقدتا n8n لفريق المساعدين
عُطّلتا لتوفير التكلفة؛ فلم يبدأ العقل أي جولة وحده، ولم يظهر للمؤسس شيء.

القواعد:
  * المواعيد من `DASH_BRAIN_AUTORUN_HOURS` (ساعات القاهرة بفواصل، الافتراضي «9,20»). `DASH_BRAIN_AUTORUN=0` يوقفه.
  * كل موعد يبدأ جولة واحدة فقط (صف جولة بـ`trigger='cron'` بعد بداية الموعد يكفي)، ولو كان الخادم نائمًا وقتها
    تبدأ عند أول فحص بعده. الجولة نفسها بلا تكرار (البصمة)، فالتكرار لا يكلّف إلا الجديد.
  * الفحص كل ٥ دقائق في خيط خلفي واحد؛ لا يعمل داخل الاختبارات (`pytest` محمّل) ولا لو `DASH_V2_ENABLED` مقفول
    أو `DASH_BRAIN_WRITE=0`.
  * ⛔ لا نداء ذكاء هنا: يفتح الجولة عبر `engine.start_run` فقط، والجولة تمرّ بكل السقوف المعتادة.
"""
import datetime
import logging
import os
import sys
import threading

from brain2 import engine

logger = logging.getLogger(__name__)

TICK_SECONDS = 300
FIRST_DELAY_SECONDS = 90
DEFAULT_HOURS = (9, 20)
_STATE = {'thread': None}


def enabled():
    return (os.environ.get('DASH_BRAIN_AUTORUN') or '').strip() != '0'


def hours():
    raw = (os.environ.get('DASH_BRAIN_AUTORUN_HOURS') or '').strip()
    if not raw:
        return list(DEFAULT_HOURS)
    out = set()
    for part in raw.split(','):
        try:
            h = int(part.strip())
        except (TypeError, ValueError):
            continue
        if 0 <= h <= 23:
            out.add(h)
    return sorted(out) or list(DEFAULT_HOURS)


def _cairo():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo('Africa/Cairo')
    except Exception:   # noqa: BLE001 — بلا قاعدة مناطق: +٢ ثابتة أقرب تقريب
        return datetime.timezone(datetime.timedelta(hours=2))


def _aware_utc(dt):
    return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt.astimezone(datetime.timezone.utc)


def last_slot(now_utc):
    """بداية آخر موعد مضى (UTC بلا منطقة، مثل أعمدة القاعدة)."""
    tz = _cairo()
    local = _aware_utc(now_utc).astimezone(tz)
    hs = hours()
    for day_back in (0, 1):
        d = (local - datetime.timedelta(days=day_back)).date()
        for h in reversed(hs):
            cand = datetime.datetime(d.year, d.month, d.day, h, 0, tzinfo=tz)
            if cand <= local:
                return cand.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return None


def next_slot(now_utc):
    tz = _cairo()
    local = _aware_utc(now_utc).astimezone(tz)
    for day_fwd in (0, 1):
        d = (local + datetime.timedelta(days=day_fwd)).date()
        for h in hours():
            cand = datetime.datetime(d.year, d.month, d.day, h, 0, tzinfo=tz)
            if cand > local:
                return cand.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return None


def due(db, now_utc=None):
    """هل فات موعد بلا جولة تلقائية بعده؟"""
    now_utc = now_utc or engine.utcnow()
    slot = last_slot(now_utc)
    if slot is None:
        return False
    Run = engine._models(db)[2]
    hit = Run.query.filter(Run.trigger == 'cron', Run.started_at >= slot).first()
    return hit is None


def tick(ns, now_utc=None):
    """فحص واحد. يرجع run_id لو بدأ جولة، وإلا None. يُستدعى داخل app_context."""
    if not enabled():
        return None
    try:
        if not ns['_v2_enabled']() or not engine.writes_enabled():
            return None
    except Exception:   # noqa: BLE001
        return None
    db = ns['db']
    if not due(db, now_utc):
        return None
    if engine.active_run(db) is not None:
        return None
    status, payload = engine.start_run(ns, 'cron', 'auto')
    if status == 202:
        logger.info('brain2: autorun started %s', payload.get('run_id'))
        return payload.get('run_id')
    return None


def status(ns, now_utc=None):
    """للشاشة: {on, next_at} — `next_at` نص ISO بتوقيت UTC أو None."""
    now_utc = now_utc or engine.utcnow()
    on = enabled()
    try:
        on = on and bool(ns['_v2_enabled']()) and engine.writes_enabled()
    except Exception:   # noqa: BLE001
        on = False
    nxt = next_slot(now_utc) if on else None
    return {'on': bool(on), 'next_at': (nxt.replace(tzinfo=datetime.timezone.utc).isoformat().replace('+00:00', 'Z') if nxt else None),
            'hours': hours()}


def _loop(ns):
    import time
    time.sleep(FIRST_DELAY_SECONDS)
    app, db = ns['app'], ns['db']
    while True:
        try:
            with app.app_context():
                try:
                    tick(ns)
                finally:
                    try:
                        db.session.remove()
                    except Exception:   # noqa: BLE001
                        pass
        except Exception:   # noqa: BLE001
            logger.exception('brain2: autorun tick failed')
        time.sleep(TICK_SECONDS)


def start(ns):
    """يبدأ الخيط مرة واحدة لكل عملية. لا شيء داخل الاختبارات أو لو أُوقف من البيئة."""
    if 'pytest' in sys.modules or not enabled():
        return False
    if _STATE['thread'] is not None and _STATE['thread'].is_alive():
        return False
    th = threading.Thread(target=_loop, args=(ns,), name='brain2-autorun', daemon=True)
    _STATE['thread'] = th
    th.start()
    return True
