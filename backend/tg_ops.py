# -*- coding: utf-8 -*-
"""R16 — تليجرام اللوحة: مُرسِلٌ واحد، زرّ «جرّب التنبيهات»، سجلّ آخر ٢٠ محاولة، مراقبة التشغيل، والملخص اليومي.

المؤسس (2026-11-08): «فين التنبيهات والقرارات على التليجرام… مفيش خالص شغل النظام بتاع التلجرام».

قواعد ثابتة:
  * ⛔ **مُرسِلٌ واحد** في اللوحة: `send()`. أي جزء في اللوحة (العقل، المراقبة، الملخص) يرسل منه — لا نداء
    `api.telegram.org` ولا جسر إرسال في مكانٍ آخر. «العقل» يسأل من `ask_brain()` هنا (يُسجَّل في السجلّ نفسه).
  * الطريق: لو اللوحة نفسها معها توكن ورقم محادثة (`TELEGRAM_OPS_BOT_TOKEN`|`TELEGRAM_BOT_TOKEN` +
    `TELEGRAM_ADMIN_CHAT_ID`) ⇒ مباشرة. وإلا ⇒ عبر جسر المنصة (`POST /api/bridge/telegram/send`) بسرّ
    `METRICS_SECRET` — المنصة هي صاحبة البوت.
  * كل محاولة تُكتب في SQLite (`tg_send_log`) بسببٍ واحد من قائمة ثابتة — بلا نصّ رسالة ولا سرّ.
  * إعادة محاولة على الشبكة و٤٢٩ و٥xx فقط؛ أي ٤xx آخر خطأ إعداد لا تحلّه الإعادة.
  * المؤقِّت (خيطٌ واحد، gunicorn -w 1): مراقبة ثلاثة عناوين كل ٥ دقائق (تنبيه بعد فشلين متتاليين، ومرّة عند
    الرجوع)، وملخص يومي واحد. لا يعمل داخل pytest، و`DASH_SCHEDULER=0` يطفئه.
"""
import datetime
import json
import logging
import os
import sys
import threading
import time

import requests

logger = logging.getLogger(__name__)

REASONS = ('ok', 'no_token', 'no_chat', 'bad_token', 'wrong_chat', 'bot_not_allowed', 'telegram_error',
           'network', 'no_bridge_secret', 'bridge_secret_mismatch', 'bridge_error', 'empty')
RETRY_DELAYS = (0.5, 1.5)
LOG_KEEP = 200
STATUS_ROWS = 20
# المنصة نفسها بتحاول تليجرام ٣ مرّات بمهلة ٨ ثواني (+ getWebhookInfo في «جرّب التنبيهات») ⇒ أسوأ حالة ~٣٤ ثانية.
# مهلة نداء الإرسال من اللوحة لازم تبقى أطول من كده، وإلا اللوحة تعيد المحاولة والرسالة تتكرّر.
SEND_TIMEOUT = 45
SELFTEST_TEXT = ('🔔 رسالة تجربة من لوحة البروفيسور.\n'
                 'لو وصلت، يبقى تنبيهات التسجيل والدفع والطلبات شغّالة.')
DASHBOARD_URL = 'https://dashboard.elprofessor.net/'

DEFAULT_WATCH = (
    ('التطبيق', 'https://app.elprofessor.net/'),
    # خادم المنصة: صحّته خلف القفل الآن (٤٠٣) — أي ردّ من الخادم نفسه (أقل من ٥٠٠) = شغّال.
    ('خادم المنصة', 'https://api.elprofessor.net/api/health'),
    ('الموقع', 'https://elprofessor.net/'),
)
WATCH_EVERY_SECONDS = 300
FAILS_TO_ALERT = 2

_STATE = {'model': None, 'kv': None, 'app': None, 'ns': None, 'thread': None}


# ════════════════════════════════════════════════════════════════════ النماذج
def _models(db):
    if _STATE['model'] is not None:
        return _STATE['model'], _STATE['kv']

    class TgSendLog(db.Model):
        __tablename__ = 'tg_send_log'
        id = db.Column(db.Integer, primary_key=True)
        at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
        kind = db.Column(db.String(40))
        mode = db.Column(db.String(10))          # direct | bridge
        ok = db.Column(db.Boolean, default=False)
        reason = db.Column(db.String(40))
        detail = db.Column(db.String(300))
        tries = db.Column(db.Integer, default=0)

    class OpsKV(db.Model):
        __tablename__ = 'ops_kv'
        key = db.Column(db.String(120), primary_key=True)
        value = db.Column(db.Text)
        updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    _STATE['model'], _STATE['kv'] = TgSendLog, OpsKV
    return TgSendLog, OpsKV


# ════════════════════════════════════════════════════════════════════ الإعداد
def _token():
    return (os.environ.get('TELEGRAM_OPS_BOT_TOKEN') or '').strip() or (os.environ.get('TELEGRAM_BOT_TOKEN') or '').strip()


def _chat():
    return (os.environ.get('TELEGRAM_ADMIN_CHAT_ID') or '').strip()


def mode():
    """direct لو اللوحة معها توكن ورقم محادثة، وإلا bridge (المنصة صاحبة البوت)."""
    return 'direct' if (_token() and _chat()) else 'bridge'


def _secret(ns):
    return str((ns or {}).get('PLATFORM_METRICS_SECRET') or '').strip()


def _platform_url(ns):
    return str((ns or {}).get('PLATFORM_API_URL') or 'https://api.elprofessor.net').rstrip('/')


def config(ns):
    """أعلام منطقية بلا أي قيمة سرّية."""
    m = mode()
    warnings = []
    if m == 'bridge' and not _secret(ns):
        warnings.append('اللوحة مش مربوطة بالمنصة (METRICS_SECRET فاضي) — ولا رسالة هتخرج من اللوحة.')
    if m == 'bridge':
        # تنبيه «خادم المنصة واقع» بيعدّي من خادم المنصة نفسه ⇒ مش هيوصل وهو واقع (هيتعاد كل ٥ دقايق لحد ما يوصل).
        warnings.append('تنبيه «خادم المنصة واقع» بيعدّي من المنصة نفسها، فمش هيوصل وهي واقعة. عشان يوصل: '
                        'حطّ TELEGRAM_OPS_BOT_TOKEN وTELEGRAM_ADMIN_CHAT_ID على سيرفر اللوحة كمان.')
    if (os.environ.get('DASH_SCHEDULER') or '').strip() == '0':
        warnings.append('المراقبة والملخص اليومي متوقّفين (DASH_SCHEDULER=0).')
    return {'mode': m, 'dashboard_token_set': bool(_token()), 'dashboard_chat_set': bool(_chat()),
            'bridge_secret_set': bool(_secret(ns)), 'scheduler_running': bool(_STATE['thread'] and _STATE['thread'].is_alive()),
            'warnings': warnings}


# ════════════════════════════════════════════════════════════════════ السجلّ
def _log(ns, kind, m, result):
    """صفّ في `tg_send_log`. ⛔ لا يرمي، ولا نصّ رسالة ولا سرّ."""
    try:
        Model = _STATE['model']
        db = (ns or {}).get('db') or (_STATE['ns'] or {}).get('db')
        if Model is None or db is None:
            return
        db.session.add(Model(kind=str(kind or 'ops')[:40], mode=m, ok=bool(result.get('ok')),
                             reason=str(result.get('reason') or '')[:40],
                             detail=str(result.get('detail') or '')[:300], tries=int(result.get('tries') or 0)))
        db.session.commit()
        n = Model.query.count()
        if n > LOG_KEEP:
            old = Model.query.order_by(Model.id.asc()).limit(n - LOG_KEEP).all()
            for r in old:
                db.session.delete(r)
            db.session.commit()
    except Exception:   # noqa: BLE001
        logger.exception('tg_ops: log failed')
        try:
            ns['db'].session.rollback()
        except Exception:   # noqa: BLE001
            pass


def recent(ns, limit=STATUS_ROWS):
    Model = _STATE['model']
    if Model is None:
        return []
    out = []
    for r in Model.query.order_by(Model.id.desc()).limit(limit).all():
        out.append({'at': r.at.replace(microsecond=0).isoformat() + 'Z' if r.at else None, 'kind': r.kind,
                    'mode': r.mode, 'ok': bool(r.ok), 'reason': r.reason, 'detail': r.detail or '', 'tries': r.tries or 0})
    return out


# ════════════════════════════════════════════════════════════════════ الإرسال
def _classify(status, desc):
    d = (desc or '').lower()
    if status == 401:
        return 'bad_token'
    if status == 400 and 'chat not found' in d:
        return 'wrong_chat'
    if status == 403:
        return 'bot_not_allowed'
    return 'telegram_error'


def _desc(resp):
    try:
        js = resp.json()
        if isinstance(js, dict) and js.get('description'):
            return str(js['description'])[:300]
    except Exception:   # noqa: BLE001
        pass
    return str(getattr(resp, 'text', '') or '')[:300]


def _direct(text, links):
    token, chat = _token(), _chat()
    payload = {'chat_id': chat, 'text': text[:4096], 'disable_web_page_preview': True}
    rows = [[{'text': str(b.get('text') or 'افتح')[:40], 'url': b['url']}] for b in (links or [])
            if isinstance(b, dict) and str(b.get('url') or '').startswith('https://')]
    if rows:
        payload['reply_markup'] = {'inline_keyboard': rows}
    delays = list(RETRY_DELAYS)
    tries = 0
    last = {'ok': False, 'reason': 'network', 'detail': ''}
    while True:
        tries += 1
        try:
            r = requests.post('https://api.telegram.org/bot%s/sendMessage' % token, json=payload, timeout=10)
            if r.status_code < 400:
                return {'ok': True, 'reason': 'ok', 'detail': '', 'tries': tries}
            desc = _desc(r)
            last = {'ok': False, 'reason': _classify(r.status_code, desc), 'detail': ('%s %s' % (r.status_code, desc)).strip()}
            if r.status_code != 429 and r.status_code < 500:
                last['tries'] = tries
                return last
        except Exception as exc:   # noqa: BLE001
            last = {'ok': False, 'reason': 'network', 'detail': type(exc).__name__}
        if not delays:
            last['tries'] = tries
            return last
        wait = delays.pop(0)
        if wait:
            time.sleep(wait)


def _bridge(ns, path, body=None, method='POST', timeout=20, once=False):
    """نداء جسر المنصة. يرجع (dict|None, reason, detail).

    `once=True` للنداءات اللي بتبعت رسالة فعلًا (send · selftest): إعادة المحاولة بس لو الاتصال نفسه ما اتعملش
    (الطلب ما وصلش المنصة أصلًا). مهلة قراءة أو ٥xx ⇒ لا إعادة، لأن المنصة ممكن تكون بعتت والرسالة تتكرّر."""
    secret = _secret(ns)
    if not secret:
        return None, 'no_bridge_secret', ''
    delays = list(RETRY_DELAYS)
    while True:
        retry = True
        try:
            r = requests.request(method, _platform_url(ns) + path, json=body,
                                 headers={'X-ELP-Metrics-Secret': secret}, timeout=timeout)
            if r.status_code == 200:
                try:
                    js = r.json()
                except Exception:   # noqa: BLE001
                    js = None
                return (js if isinstance(js, dict) else {}), 'ok', ''
            if r.status_code == 401:
                return None, 'bridge_secret_mismatch', 'HTTP 401'
            if r.status_code < 500:
                return None, 'bridge_error', 'HTTP %s' % r.status_code
            err = ('bridge_error', 'HTTP %s' % r.status_code)
            retry = not once
        except Exception as exc:   # noqa: BLE001
            err = ('network', type(exc).__name__)
            # ConnectionError (ومنها ConnectTimeout) = الطلب ما اتبعتش. ReadTimeout = اتبعت ومستنيين الردّ.
            if once:
                retry = isinstance(exc, requests.exceptions.ConnectionError) and \
                    not isinstance(exc, requests.exceptions.ReadTimeout)
        if not delays or not retry:
            return None, err[0], err[1]
        wait = delays.pop(0)
        if wait:
            time.sleep(wait)


def send(ns, text, kind='ops', links=None):
    """المُرسِل الوحيد في اللوحة. يرجع {ok, reason, detail, tries, mode} ولا يرمي أبدًا."""
    text = str(text or '').strip()
    m = mode()
    if not text:
        return {'ok': False, 'reason': 'empty', 'detail': '', 'tries': 0, 'mode': m}
    try:
        if m == 'direct':
            res = _direct(text, links)
        else:
            js, why, detail = _bridge(ns, '/api/bridge/telegram/send',
                                      {'text': text[:3500], 'kind': kind, 'links': list(links or [])[:4]},
                                      timeout=SEND_TIMEOUT, once=True)
            if js is None:
                res = {'ok': False, 'reason': why, 'detail': detail, 'tries': 1}
            else:
                res = {'ok': js.get('ok') is True, 'reason': js.get('reason') or ('ok' if js.get('ok') else 'telegram_error'),
                       'detail': str(js.get('detail') or '')[:300], 'tries': js.get('tries') or 1}
    except Exception as exc:   # noqa: BLE001
        res = {'ok': False, 'reason': 'network', 'detail': type(exc).__name__, 'tries': 0}
    res['mode'] = m
    _log(ns, kind, m, res)
    if not res['ok']:
        logger.warning('tg_ops: send failed kind=%s mode=%s reason=%s detail=%s', kind, m, res['reason'], res['detail'])
    return res


def ask_brain(ns, proxy, payload):
    """سؤال «العقل» بأزرار اعتمد/ارفض (B2) — عبر جسر المنصة `POST /api/bridge/brain/ask` (الأزرار لازم تتبني
    في المنصة لأن مستقبِل الضغطات هناك). `proxy` = `_platform_proxy`. يرجع True لو وصل فعلًا، ويُسجَّل."""
    sent = False
    res = {'ok': False, 'reason': 'bridge_error', 'detail': '', 'tries': 1}
    try:
        resp = proxy('POST', '/api/bridge/brain/ask', json_body=payload, timeout=10)
        if ns['_resp_ok'](resp):
            js = ns['_proxy_json'](resp)
            sent = js.get('sent') is True
            res = {'ok': sent, 'reason': 'ok' if sent else 'telegram_error',
                   'detail': '' if sent else 'المنصة ردّت sent=false (افتح «جرّب التنبيهات» لمعرفة السبب)', 'tries': 1}
        else:
            res['detail'] = 'الجسر رفض الطلب'
    except Exception as exc:   # noqa: BLE001
        res = {'ok': False, 'reason': 'network', 'detail': type(exc).__name__, 'tries': 1}
        logger.exception('tg_ops: brain ask raised')
    _log(ns, 'brain_ask', 'bridge', res)
    return sent


def selftest(ns):
    """زرّ «جرّب التنبيهات»: رسالة تجربة واحدة وسبب واضح."""
    m = mode()
    if m == 'direct':
        res = send(ns, SELFTEST_TEXT, kind='selftest', links=[{'text': 'افتح اللوحة', 'url': DASHBOARD_URL}])
        return {'ok': res['ok'], 'reason': res['reason'], 'detail': res['detail'], 'mode': m, 'platform': None}
    js, why, detail = _bridge(ns, '/api/bridge/telegram/selftest', {}, timeout=SEND_TIMEOUT, once=True)
    if js is None:
        res = {'ok': False, 'reason': why, 'detail': detail, 'tries': 1}
        _log(ns, 'selftest', m, res)
        return {'ok': False, 'reason': why, 'detail': detail, 'mode': m, 'platform': None}
    res = {'ok': js.get('ok') is True, 'reason': js.get('reason') or 'telegram_error',
           'detail': str(js.get('detail') or '')[:300], 'tries': js.get('tries') or 1}
    _log(ns, 'selftest', m, res)
    return {'ok': res['ok'], 'reason': res['reason'], 'detail': res['detail'], 'mode': m,
            'platform': {'config': js.get('config') or {}, 'webhook': js.get('webhook') or {}}}


def arm_webhook(ns, force=False):
    """«شغّل أزرار القرار». الويب-هوك مربوط بمكان تاني ⇒ المنصة ترجّع `webhook_elsewhere` ومضيفه، واللوحة تسأل
    المؤسس قبل ما تبعت `force`."""
    js, why, detail = _bridge(ns, '/api/bridge/telegram/arm-webhook', {'force': bool(force)}, once=True)
    if js is None:
        return {'ok': False, 'reason': why, 'detail': detail}
    return {'ok': js.get('ok') is True, 'reason': js.get('reason') or '', 'detail': str(js.get('detail') or ''),
            'host': str(js.get('host') or '')[:120], 'webhook': js.get('webhook')}


def platform_status(ns):
    js, why, detail = _bridge(ns, '/api/bridge/telegram/status', None, method='GET', timeout=10)
    return js if js is not None else {'error': why, 'detail': detail}


# ════════════════════════════════════════════════════════════════════ مخزن صغير (حالة المراقبة/الملخص)
def kv_get(ns, key, default=None):
    KV = _STATE['kv']
    if KV is None:
        return default
    row = KV.query.get(key)
    if row is None:
        return default
    try:
        return json.loads(row.value)
    except (TypeError, ValueError):
        return default


def kv_set(ns, key, value):
    KV = _STATE['kv']
    db = ns['db']
    row = KV.query.get(key)
    if row is None:
        row = KV(key=key)
        db.session.add(row)
    row.value = json.dumps(value, ensure_ascii=False)
    row.updated_at = datetime.datetime.utcnow()
    db.session.commit()


# ════════════════════════════════════════════════════════════════════ مراقبة التشغيل
def watch_targets():
    raw = (os.environ.get('DASH_WATCH_URLS') or '').strip()
    if not raw:
        return list(DEFAULT_WATCH)
    out = []
    for part in raw.split(','):
        part = part.strip()
        if part.startswith('https://'):
            out.append((part, part))
    return out or list(DEFAULT_WATCH)


def _probe(url, get):
    """شغّال = الخادم ردّ بأقل من ٥٠٠ وليس ٤٠٤ (٤٠١/٤٠٣ = خادم حيّ خلف قفل)."""
    try:
        r = get(url, timeout=15, allow_redirects=True)
        code = int(getattr(r, 'status_code', 0) or 0)
        return (0 < code < 500 and code != 404), 'HTTP %s' % code
    except Exception as exc:   # noqa: BLE001
        return False, type(exc).__name__


def check_uptime(ns, get=None):
    """جولة واحدة. تنبيه بعد فشلين متتاليين، ومرّة واحدة عند الرجوع. يرجع قائمة بما أُرسل."""
    get = get or requests.get
    sent = []
    for label, url in watch_targets():
        up, why = _probe(url, get)
        key = 'uptime:' + url
        st = kv_get(ns, key, {}) or {}
        fails = int(st.get('fails') or 0)
        down = bool(st.get('down'))
        # ⛔ الحالة تتغيّر بس لما التنبيه يوصل فعلًا: تنبيه ما وصلش (مثلًا «خادم المنصة واقع» وهو بيعدّي من
        # المنصة نفسها) يتعاد في الجولة الجاية بعد ٥ دقايق، مش يضيع.
        if up:
            if down:
                res = send(ns, '🟢 %s رجع يشتغل\n%s' % (label, url), kind='uptime', links=[{'text': 'افتح', 'url': url}])
                if not res.get('ok'):
                    kv_set(ns, key, {'fails': 0, 'down': True, 'last': why, 'alert_failed': res.get('reason')})
                    continue
                sent.append(('up', url))
            kv_set(ns, key, {'fails': 0, 'down': False, 'last': why})
            continue
        fails += 1
        alert_failed = ''
        if fails >= FAILS_TO_ALERT and not down:
            res = send(ns, '🔴 %s مش شغّال (فشل %s مرّات متتالية)\n%s\nالسبب: %s' % (label, fails, url, why),
                       kind='uptime', links=[{'text': 'افتح', 'url': url}])
            if res.get('ok'):
                sent.append(('down', url))
                down = True
            else:
                alert_failed = res.get('reason') or 'network'
        st = {'fails': fails, 'down': down, 'last': why}
        if alert_failed:
            st['alert_failed'] = alert_failed
        kv_set(ns, key, st)
    return sent


def uptime_state(ns):
    out = []
    for label, url in watch_targets():
        st = kv_get(ns, 'uptime:' + url, {}) or {}
        # «واقع» للعرض = الخادم بيفشل فعلًا (حتى لو التنبيه نفسه لسه ما وصلش).
        failing = bool(st.get('down')) or int(st.get('fails') or 0) >= FAILS_TO_ALERT
        out.append({'label': label, 'url': url, 'down': failing, 'fails': int(st.get('fails') or 0),
                    'last': st.get('last') or '', 'alert_failed': st.get('alert_failed') or ''})
    return out


# ════════════════════════════════════════════════════════════════════ الملخص اليومي
DIGEST_LABELS = {
    'signups_new': 'تسجيلات جديدة لم تُراجع',
    'payments_failed_new': 'دفعات فشلت لم تُراجع',
    'trainer_applications': 'طلبات مدرّبين',
    'courses_pending': 'دورات تنتظر الاعتماد',
    'live_needs_decision': 'دورات حيّة تحتاج قرارًا',
    'manual_payments': 'إيصالات تحويل',
    'wallet_payouts': 'طلبات سحب',
    'stuck_card_payments': 'دفعات بطاقة عالقة',
    'split_pending': 'اقتسام إيراد معلّق',
    'manual_refunds': 'طلبات استرجاع يدوية',
    'consultation_disputes': 'ملاحظات على ملفات قديمة',
    'consultations_legacy': 'ملفات قديمة تنتظر قرارًا',
    'expert_files_disputed': 'ملفات عليها ملاحظة',
    'expert_files_case_disputed': 'مراحل قضايا عليها ملاحظة',
    'expert_files_unassigned': 'ملفات تنتظر التوزيع',
    'expert_files_no_candidate': 'ملفات بلا خبير مناسب',
    'expert_files_assign_overdue': 'ملفات لم تُستلم في موعدها',
    'expert_files_late': 'آراء متأخرة',
    'expert_files_in_review': 'آراء تنتظر مراجعتك',
    'expert_files_blocked': 'ملفات توقفت أموالها',
    'expert_files_unactivated': 'ملفات دُفعت ولم تصل إلى التوزيع',
    'founding_leads': 'طلبات خبير مؤسس',
    'testimonials_pending': 'شهادات تنتظر المراجعة',
    'lead_magnet_awaiting': 'ملفات وُعد بها ولم تُسلَّم',
    'topics_pending_review': 'موضوعات من أعضاء',
    'opinions_pending': 'تعليقات تنتظر المراجعة',
    'creative_pending': 'أعمال إبداعية تنتظر المراجعة',
}


def _ar_num(n):
    return str(int(n)).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def digest_text(ns, queue):
    """نصّ الملخص من طابور المنصة (`/api/bridge/ops/queue`) وحالة المراقبة وفشل الإرسال آخر ٢٤ ساعة."""
    lines = ['☀️ ملخص اليوم من لوحة البروفيسور']
    items = []
    if isinstance(queue, dict):
        for a in queue.get('alerts_v2') or []:
            if isinstance(a, dict) and a.get('count'):
                items.append('• %s: %s' % (DIGEST_LABELS.get(a.get('key'), 'بند ينتظر قرارًا'), _ar_num(a['count'])))
        e24 = queue.get('enrollments_24h')
        if isinstance(e24, int) and e24:
            items.append('• اشتراكات في الدورات آخر ٢٤ ساعة: %s' % _ar_num(e24))
    if queue is None:
        lines.append('⚠️ تعذّر قراءة طابور المنصة — الأرقام ناقصة.')
    elif items:
        lines.append('ينتظر قرارك:')
        lines.extend(items)
    else:
        lines.append('لا شيء ينتظر قرارك في الوارد.')
    down = [u['label'] for u in uptime_state(ns) if u['down']]
    if down:
        lines.append('🔴 متوقّف الآن: ' + '، '.join(down))
    Model = _STATE['model']
    if Model is not None:
        since = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
        bad = Model.query.filter(Model.at >= since, Model.ok.is_(False)).count()
        if bad:
            lines.append('⚠️ رسائل تليجرام فشلت آخر ٢٤ ساعة: %s (التفاصيل في «جرّب التنبيهات»)' % _ar_num(bad))
    return '\n'.join(lines)


def _cairo_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo('Africa/Cairo'))
    except Exception:   # noqa: BLE001
        return datetime.datetime.utcnow() + datetime.timedelta(hours=2)


def digest_hour():
    try:
        return min(23, max(0, int((os.environ.get('DASH_DIGEST_HOUR') or '9').strip())))
    except ValueError:
        return 9


def send_digest(ns, force=False):
    """مرّة واحدة في اليوم (بتوقيت القاهرة)، إلا لو `force`."""
    today = _cairo_now().date().isoformat()
    key = 'digest:last'
    if not force and kv_get(ns, key) == today:
        return {'ok': False, 'reason': 'already_sent', 'detail': today}
    if not force:
        # محاولة فاشلة ⇒ إعادة بعد ساعة، لا كل دقيقة (لا نُغرق السجلّ ولا الجسر).
        tried = float(kv_get(ns, 'digest:tried_at', 0) or 0)
        if time.time() - tried < 3600:
            return {'ok': False, 'reason': 'retry_later', 'detail': ''}
        kv_set(ns, 'digest:tried_at', time.time())
    js, why, _detail = _bridge(ns, '/api/bridge/ops/queue', None, method='GET', timeout=20)
    res = send(ns, digest_text(ns, js), kind='digest', links=[{'text': 'افتح الوارد', 'url': DASHBOARD_URL}])
    if res['ok']:
        kv_set(ns, key, today)
    return res


# ════════════════════════════════════════════════════════════════════ المؤقِّت
def tick(ns, now_ts=None):
    """خطوة واحدة من المؤقِّت (تُختبر بلا خيط)."""
    now_ts = now_ts if now_ts is not None else time.time()
    last = float(kv_get(ns, 'uptime:last_run', 0) or 0)
    if now_ts - last >= WATCH_EVERY_SECONDS - 5:
        kv_set(ns, 'uptime:last_run', now_ts)
        check_uptime(ns)
    if _cairo_now().hour >= digest_hour():
        send_digest(ns)


def _loop(app, ns):
    time.sleep(30)                       # الإقلاع يخلص الأول
    while True:
        try:
            with app.app_context():
                tick(ns)
        except Exception:   # noqa: BLE001
            logger.exception('tg_ops: scheduler tick failed')
            try:
                with app.app_context():
                    ns['db'].session.rollback()
            except Exception:   # noqa: BLE001
                pass
        time.sleep(60)


def scheduler_allowed():
    if (os.environ.get('DASH_SCHEDULER') or '').strip() == '0':
        return False
    return 'pytest' not in sys.modules


def start_scheduler(app, ns):
    if _STATE['thread'] is not None and _STATE['thread'].is_alive():
        return _STATE['thread']
    t = threading.Thread(target=_loop, args=(app, ns), name='tg-ops-scheduler', daemon=True)
    t.start()
    _STATE['thread'] = t
    return t


# ════════════════════════════════════════════════════════════════════ المسارات
def register(app, ns):
    from flask import jsonify, request

    db = ns['db']
    _models(db)
    _STATE['app'], _STATE['ns'] = app, ns
    token_required = ns['token_required']
    roles_required = ns['roles_required']

    def no_store(resp, status=200):
        r = jsonify(resp)
        r.status_code = status
        r.headers['Cache-Control'] = 'no-store'
        return r

    @app.route('/api/telegram/selftest', methods=['POST'], endpoint='tg_ops_selftest')
    @token_required
    @roles_required('admin')
    def tg_ops_selftest():
        out = selftest(ns)
        try:
            ns['_audit']('telegram.selftest', target=out.get('reason') or '', meta={'ok': bool(out.get('ok'))})
        except Exception:   # noqa: BLE001
            pass
        return no_store(out)

    @app.route('/api/telegram/status', methods=['GET'], endpoint='tg_ops_status')
    @token_required
    @roles_required('admin')
    def tg_ops_status():
        body = {'config': config(ns), 'attempts': recent(ns), 'uptime': uptime_state(ns),
                'digest_hour': digest_hour(), 'digest_last': kv_get(ns, 'digest:last')}
        if request.args.get('platform') == '1':
            body['platform'] = platform_status(ns)
        return no_store(body)

    @app.route('/api/telegram/arm-webhook', methods=['POST'], endpoint='tg_ops_arm')
    @token_required
    @roles_required('admin')
    def tg_ops_arm():
        body = request.get_json(silent=True) or {}
        out = arm_webhook(ns, force=body.get('force') is True)
        try:
            ns['_audit']('telegram.arm_webhook', target=out.get('reason') or '', meta={'ok': bool(out.get('ok'))})
        except Exception:   # noqa: BLE001
            pass
        return no_store(out)

    @app.route('/api/telegram/digest', methods=['POST'], endpoint='tg_ops_digest')
    @token_required
    @roles_required('admin')
    def tg_ops_digest():
        return no_store(send_digest(ns, force=True))

    # —— «تسجيل جديد» في الوارد (قاعدة: أي طابور يُنبّه تليجرام لازم له صفّ في الوارد بإجراء)
    @app.route('/api/platform-signups', methods=['GET'], endpoint='tg_ops_signups')
    @token_required
    @roles_required('admin')
    def tg_ops_signups():
        return ns['_platform_proxy']('GET', '/api/bridge/signups/recent', params={'limit': 200})

    @app.route('/api/platform-signups/<user_id>/ack', methods=['POST'], endpoint='tg_ops_signup_ack')
    @token_required
    @roles_required('admin')
    def tg_ops_signup_ack(user_id):
        import re as _re
        if not _re.match(r'^[A-Za-z0-9_-]{1,64}$', user_id or ''):
            return no_store({'error': 'معرّف غير صالح'}, 400)
        resp = ns['_platform_proxy']('POST', '/api/bridge/signups/%s/ack' % user_id,
                                     json_body={'by': ns['_actor_email']() or 'dashboard'})
        try:
            ns['_audit']('signup.ack', target=user_id)
        except Exception:   # noqa: BLE001
            pass
        return resp

    # —— «دفع فشل» في الوارد (نفس القاعدة): رفض البوابة · صفحة دفع ما فتحتش · بوابة كاملة مش جاهزة.
    @app.route('/api/platform-payment-failures', methods=['GET'], endpoint='tg_ops_payfails')
    @token_required
    @roles_required('admin')
    def tg_ops_payfails():
        return ns['_platform_proxy']('GET', '/api/bridge/payment-failures/recent', params={'limit': 200})

    @app.route('/api/platform-payment-failures/<row_id>/ack', methods=['POST'], endpoint='tg_ops_payfail_ack')
    @token_required
    @roles_required('admin')
    def tg_ops_payfail_ack(row_id):
        import re as _re
        if not _re.match(r'^[A-Za-z0-9_-]{1,64}$', row_id or ''):
            return no_store({'error': 'معرّف غير صالح'}, 400)
        resp = ns['_platform_proxy']('POST', '/api/bridge/payment-failures/%s/ack' % row_id,
                                     json_body={'by': ns['_actor_email']() or 'dashboard'})
        try:
            ns['_audit']('payment_failure.ack', target=row_id)
        except Exception:   # noqa: BLE001
            pass
        return resp

    if scheduler_allowed():
        start_scheduler(app, ns)
