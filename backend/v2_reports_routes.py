# -*- coding: utf-8 -*-
"""قسم «التقارير» (الجولة النهائية) — مسار واحد للأرقام تقرأه الشاشة ورسالة الأحد معًا.

    GET  /api/v2/reports/summary?period=week|month|quarter&scope=all|files|courses|books|market|content|marketing[&fresh=1]
    GET  /api/v2/reports/weekly[?week=YYYY-MM-DD]
    PUT  /api/v2/reports/weekly/settings        {enabled, confirmed:true}
    POST /api/v2/reports/weekly/send            {week?, confirmed:true}         («أرسل الآن»)
    POST /api/v2/reports/weekly/deliver         سرّ المنصة فقط (الجدولة كل أحد)

⛔ المفتاح مقفول ⇒ ٤٠٤ بلا أي نداء للمنصة. ⛔ لا بيانات شخصية في الرد: أعداد ومجاميع فقط.
⛔ المصدر الذي فشل ⇒ حقوله None («غير متاح بعد»)، ولا يتحوّل إلى صفر أبدًا.
⛔ جمل «العقل» مبنية بقواعد ثابتة من أرقام الرد نفسه. لا نموذج ذكاء ولا نداء مدفوع هنا.
⛔ التقسيم بالأيام الكاملة بتوقيت القاهرة (اليوم الجاري خارج المقارنة، وله سطره «اليوم حتى الآن»).
"""
import concurrent.futures
import datetime
import math
import re
import secrets
import threading
import time

try:
    from zoneinfo import ZoneInfo
except Exception:                                    # pragma: no cover
    ZoneInfo = None

from flask import jsonify, request

TZ_NAME = 'Africa/Cairo'
PERIOD_DAYS = {'week': 7, 'month': 30, 'quarter': 91}
SCOPES = ('all', 'files', 'courses', 'books', 'market', 'content', 'marketing')
MONEY = ('files', 'courses', 'books')
SVC_OF_SECTION = {'files': 'experts', 'courses': 'courses', 'books': 'books'}
SOURCE_TIMEOUT = 12
USERS_LIMIT = 1000
MARKET_LIMIT = 500
CHAT_LIMIT = 3000
SUMMARY_TTL = 60
WEEKLY_TTL = 600
WEEKS_BACK = 12
SETTING_KEY = 'v2r_weekly_delivery'
NA = 'غير متاح بعد'
MARKETING_NA = 'تكتمل مع ربط الحملات في قسم التسويق'
NO_RULES_NA = 'هذا النطاق لا يقيس الدخل ولا الحسابات ولا الطلبات'
OPP_NA = 'هذا النطاق لا يقيس الأسئلة ولا طلبات السوق'
DELIVERY_PATH = '/api/bridge/reports/weekly/deliver'
DELIVERY_STATE_PATH = '/api/bridge/reports/weekly/delivery'
FUNNEL_PATH = '/api/bridge/reports/funnel'

MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
SECTION_NAME = {'files': 'ملفات الخبراء', 'courses': 'الدورات', 'books': 'الكتب', 'market': 'سوق الخدمات', 'content': 'المحتوى',
                'satisfaction': 'رضا العملاء', 'marketing': 'التسويق'}
INCOME_NAME = {'files': 'دخل ملفات الخبراء', 'courses': 'دخل الدورات', 'books': 'دخل الكتب'}
OPEN_LABEL = {'files': 'افتح ملفات الخبراء', 'courses': 'افتح الدورات', 'books': 'افتح الكتب', 'market': 'افتح السوق', 'people': 'افتح الناس'}
SOURCE_LABEL = {'ledger': 'دفتر الإيرادات', 'users': 'الحسابات الجديدة', 'market': 'طلبات السوق', 'content': 'مقالات الموقع',
                'disputes': 'النزاعات', 'chat': 'أسئلة المحادثة', 'funnel': 'رحلة الزائر', 'delivery': 'إرسال تقرير الأحد'}
CUR_NAME = {'EGP': 'جنيه', 'USD': 'دولار', 'SAR': 'ريال', 'EUR': 'يورو', 'AED': 'درهم', 'GBP': 'جنيه إسترليني', 'KWD': 'دينار', 'QAR': 'ريال'}
CHANNEL_LABEL = {'google': 'بحث جوجل', 'meta': 'فيسبوك وإنستجرام', 'whatsapp': 'واتساب', 'direct': 'دخلوا مباشرة',
                 'invite': 'دعوات الخبراء', 'other': 'مواقع أخرى'}
CHANNEL_ORDER = ('google', 'meta', 'whatsapp', 'direct', 'invite', 'other')
COUNTRY_LABEL = {'EG': 'مصر', 'SA': 'السعودية', 'AE': 'الإمارات', 'KW': 'الكويت', 'QA': 'قطر', 'BH': 'البحرين', 'OM': 'عُمان',
                 'JO': 'الأردن', 'LB': 'لبنان', 'IQ': 'العراق', 'SY': 'سوريا', 'PS': 'فلسطين', 'YE': 'اليمن', 'SD': 'السودان',
                 'LY': 'ليبيا', 'TN': 'تونس', 'DZ': 'الجزائر', 'MA': 'المغرب', 'TR': 'تركيا', 'US': 'أمريكا', 'GB': 'بريطانيا',
                 'DE': 'ألمانيا', 'FR': 'فرنسا', 'CA': 'كندا'}

# مرجعان للاختبار: الساعة والذاكرة المؤقتة.
_clock = lambda: datetime.datetime.now(datetime.timezone.utc)      # noqa: E731
_CACHE = {}
_CACHE_LOCK = threading.Lock()


# ------------------------------------------------------------------ أدوات الأرقام العربية
_DIG = '٠١٢٣٤٥٦٧٨٩'


def _digits(s):
    return re.sub(r'\d', lambda m: _DIG[int(m.group(0))], str(s))


def _ar(n):
    """رقم بأرقام هندية. العدد الصحيح بفاصل آلاف «٬»، والكسر بفاصل «٫» (منزلتان بالكثير)."""
    try:
        v = float(n)
    except (TypeError, ValueError):
        return ''
    if not math.isfinite(v):
        return ''
    neg = '-' if v < 0 else ''
    v = abs(v)
    whole = int(v)
    frac = int(round((v - whole) * 100))
    if frac == 100:
        whole, frac = whole + 1, 0
    s = '{:,}'.format(whole).replace(',', '٬')
    if frac:
        fs = '%02d' % frac
        if fs.endswith('0'):
            fs = fs[0]
        s += '٫' + fs
    return neg + _digits(s)


def _u(n, forms):
    """صيغة العدد العربية: [المفرد الكامل، المثنّى الكامل، «عدد + جمع»، «عدد + تمييز مفرد»]."""
    n = int(round(float(n or 0)))
    if n == 1:
        return forms[0]
    if n == 2:
        return forms[1]
    if 3 <= n <= 10:
        return _ar(n) + ' ' + forms[2]
    return _ar(n) + ' ' + forms[3]


def _round(x):
    """مثل Math.round في المتصفح (نصف إلى الأعلى)."""
    return int(math.floor(x + 0.5))


def _money_text(amount, cur):
    return _ar(amount) + ' ' + CUR_NAME.get(str(cur or 'EGP').upper(), str(cur or 'EGP').upper())


def _cents(x):
    return int(round(float(x) * 100))


def _totals_list(acc):
    """{عملة: سنت} ⇒ [{currency, amount}] والجنيه أولًا ثم الأبجدي. الصفر يُحذف."""
    keys = sorted([c for c, v in acc.items() if v], key=lambda c: (0 if c == 'EGP' else 1, c))
    return [{'currency': c, 'amount': acc[c] / 100.0} for c in keys]


def _egp_of(totals):
    for t in totals or []:
        if t['currency'] == 'EGP':
            return t['amount']
    return 0.0


def _others_of(totals):
    return [t for t in (totals or []) if t['currency'] != 'EGP']


def _service_of(source):
    """يطابق `serviceOf` في v2-logic.js بالحرف (يحرسه اختبار التطابق)."""
    s = str(source or '').strip().lower()
    if s in ('consultation', 'consulting', 'expert_file', 'expert_case'):
        return 'experts'
    if s in ('course', 'course_offer', 'program'):
        return 'courses'
    if s in ('book', 'knowledge'):
        return 'books'
    return 'other'


def _date_text(d, year=False):
    t = '%s %s' % (_ar(d.day), MONTHS[d.month - 1])
    return t + (' ' + _ar(d.year).replace('٬', '') if year else '')


# ------------------------------------------------------------------ النافذة (أيام كاملة بتوقيت القاهرة)
def _tz():
    try:
        return ZoneInfo(TZ_NAME)
    except Exception:
        return None


PREV_LABEL = {'week': 'الأيام السبعة التي قبلها', 'month': 'الثلاثين يومًا التي قبلها', 'quarter': 'الثلاثة عشر أسبوعًا التي قبلها'}


def make_window(period, from_d, days, tz_ok, now_local, bucket_days=None):
    until_d = from_d + datetime.timedelta(days=days)
    prev_from = from_d - datetime.timedelta(days=days)
    last = until_d - datetime.timedelta(days=1)
    if bucket_days is None:
        bucket_days = 7 if period == 'quarter' else 1
    if period == 'quarter':
        label = 'آخر ١٣ أسبوعًا (من %s إلى %s)' % (_date_text(from_d), _date_text(last))
    elif period == 'week':
        label = 'آخر ٧ أيام كاملة (من %s إلى %s)' % (_date_text(from_d), _date_text(last))
    else:
        label = 'آخر ٣٠ يومًا كاملة (من %s إلى %s)' % (_date_text(from_d), _date_text(last))
    return {'period': period, 'days': days, 'from': from_d, 'until': until_d, 'prev_from': prev_from, 'prev_until': from_d,
            'today': now_local.date(), 'now': now_local, 'tz_ok': tz_ok, 'bucket_days': bucket_days,
            'label': label, 'prev_label': PREV_LABEL[period]}


def rolling_window(period, now_utc, tz):
    ok = tz is not None
    local = now_utc.astimezone(tz if ok else datetime.timezone.utc)
    days = PERIOD_DAYS[period]
    until_d = local.date()
    return make_window(period, until_d - datetime.timedelta(days=days), days, ok, local)


def week_window(week_start, now_utc, tz):
    ok = tz is not None
    local = now_utc.astimezone(tz if ok else datetime.timezone.utc)
    w = make_window('week', week_start, 7, ok, local, bucket_days=1)
    w['label'] = 'من الأحد %s إلى السبت %s' % (_date_text(week_start), _date_text(week_start + datetime.timedelta(days=6), True))
    w['prev_label'] = 'الأسبوع الذي قبله'
    w['kind'] = 'weekly'
    return w


def latest_week_start(now_local_date):
    """أحدث أحد اكتمل أسبوعه: بداية الأسبوع الجاري (الأحد) ناقص ٧ أيام."""
    back = (now_local_date.weekday() + 1) % 7            # الاثنين=٠ ... الأحد=٦ ⇒ الأحد يرجع ٠
    cur_week = now_local_date - datetime.timedelta(days=back)
    return cur_week - datetime.timedelta(days=7)


def buckets_of(win):
    out, d, step = [], win['from'], datetime.timedelta(days=win['bucket_days'])
    while d < win['until']:
        out.append((d, d + step))
        d += step
    return out


def _bucket_index(win, d):
    if not (win['from'] <= d < win['until']):
        return None
    return (d - win['from']).days // win['bucket_days']


def _in_cur(win, d):
    return win['from'] <= d < win['until']


def _in_prev(win, d):
    return win['prev_from'] <= d < win['prev_until']


# ------------------------------------------------------------------ قراءة المصادر
def _parse_dt(v):
    if not isinstance(v, str) or not v.strip():
        return None
    s = v.strip().replace('Z', '+00:00')
    for fn in (lambda x: datetime.datetime.fromisoformat(x),
               lambda x: datetime.datetime.fromisoformat(re.sub(r'\.\d+', '', x)),
               lambda x: datetime.datetime.strptime(x[:19], '%Y-%m-%dT%H:%M:%S'),
               lambda x: datetime.datetime.strptime(x[:10], '%Y-%m-%d')):
        try:
            d = fn(s)
            return d
        except Exception:
            continue
    return None


def _local_date(v, tz):
    d = _parse_dt(v)
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d.astimezone(tz if tz is not None else datetime.timezone.utc).date()


def _unpack(resp):
    """(حالة، جسم) من رد `_platform_proxy`."""
    try:
        r, status = (resp[0], int(resp[1])) if isinstance(resp, tuple) else (resp, int(getattr(resp, 'status_code', 200)))
        body = r.get_json(silent=True)
        return status, body
    except Exception:
        return 0, None


def _pull(G, path, params=None):
    """نداء واحد للمنصة بلا إعادة محاولة. يعيد ('ok', جسم) أو ('absent', None) عند ٤٠٤ أو ('failed', None)."""
    try:
        with G['app'].app_context():
            resp = G['_platform_proxy']('GET', path, params=params, timeout=SOURCE_TIMEOUT)
        status, body = _unpack(resp)
    except Exception:
        return 'failed', None
    if status == 404:
        return 'absent', None
    if status != 200 or body is None:
        return 'failed', None
    return 'ok', body


def read_ledger(G, win):
    Revenue = G['Revenue']
    hi = win['today'] + datetime.timedelta(days=1)
    rows = Revenue.query.filter(Revenue.date >= win['prev_from'], Revenue.date < hi).all()
    out = []
    for r in rows:
        parts = []
        if r.amount_egp and float(r.amount_egp):
            parts.append(('EGP', float(r.amount_egp)))
        if r.amount_usd and float(r.amount_usd):
            parts.append(('USD', float(r.amount_usd)))
        oc = str(r.currency or '').strip().upper()
        if r.needs_fx and oc and oc not in ('EGP', 'USD') and r.amount_original and float(r.amount_original):
            parts.append((oc, float(r.amount_original)))
        if not parts:
            continue
        d = r.date.date() if isinstance(r.date, datetime.datetime) else r.date
        out.append({'date': d, 'svc': _service_of(r.source), 'parts': parts})
    return out


def aggregate_ledger(rows, d_from, d_until):
    """{svc: {count, totals{currency: سنت}}} للفترة [من، إلى)."""
    out = {s: {'count': 0, 'acc': {}} for s in ('experts', 'courses', 'books', 'other')}
    for r in rows:
        if not (d_from <= r['date'] < d_until):
            continue
        o = out[r['svc']]
        o['count'] += 1
        for cur, amt in r['parts']:
            o['acc'][cur] = o['acc'].get(cur, 0) + _cents(amt)
    return {s: {'count': v['count'], 'totals': _totals_list(v['acc'])} for s, v in out.items()}


def _oldest(dates):
    ds = [d for d in dates if d is not None]
    return min(ds) if ds else None


def read_users(G, win, tz):
    state, body = _pull(G, '/api/bridge/users', {'limit': USERS_LIMIT})
    if state != 'ok':
        return 'failed', None
    rows = body.get('users') if isinstance(body, dict) else body
    if not isinstance(rows, list):
        return 'failed', None
    dates = []
    for r in rows:
        if not isinstance(r, dict) or r.get('is_test') is True:
            continue
        dates.append(_local_date(r.get('created_at'), tz))
    return 'ok', {'dates': [d for d in dates if d is not None], 'n': len(rows), 'oldest': _oldest(dates)}


def _complete(n, cap, oldest, start):
    return n < cap or (oldest is not None and oldest < start)


def read_market(G, win, tz):
    state, body = _pull(G, '/api/bridge/market/requests', {'author_kind': 'member', 'include_test': 'false', 'limit': MARKET_LIMIT})
    if state != 'ok' or not isinstance(body, dict) or not isinstance(body.get('items'), list):
        return 'failed', None
    items = []
    dates = []
    for r in body['items']:
        if not isinstance(r, dict) or r.get('is_test') is True:
            continue
        d = _local_date(r.get('created_at'), tz)
        dates.append(d)
        if d is None:
            continue
        try:
            oc = int(r.get('offer_count') or 0)
        except (TypeError, ValueError):
            oc = 0
        items.append({'date': d, 'status': str(r.get('status') or ''), 'offers': oc,
                      'need': str(r.get('need_kind') or r.get('need') or '').strip().lower()})
    total = body.get('total')
    n = len(body['items'])
    complete_all = isinstance(total, int) and total <= n
    return 'ok', {'items': items, 'oldest': _oldest(dates), 'complete_all': complete_all, 'n': n}


def read_content(G, win, tz):
    Article = G['Article']
    try:
        rows = Article.query.filter(Article.status == 'published').all()
    except Exception:
        return 'failed', None
    dates = []
    for a in rows:
        p = a.published_at
        if p is None:
            continue
        dates.append(_local_date(p.isoformat(), tz))
    return 'ok', {'dates': [d for d in dates if d is not None]}


def read_disputes(G):
    state, body = _pull(G, '/api/bridge/ops/queue')
    if state != 'ok' or not isinstance(body, dict):
        return 'failed', None
    total = 0
    for k in ('expert_files_disputed', 'expert_files_case_disputed', 'consultation_disputes'):
        if k not in body:
            return 'failed', None
        v = body[k]
        if isinstance(v, dict):
            v = v.get('count')
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return 'failed', None
        total += int(v)
    return 'ok', total


def read_chat(G):
    state, body = _pull(G, '/api/bridge/chat-insights', {'limit': CHAT_LIMIT})
    if state != 'ok' or not isinstance(body, dict):
        return 'failed', None
    unmet = body.get('unmet')
    top = None
    if isinstance(unmet, list) and unmet and isinstance(unmet[0], dict):
        try:
            c = int(unmet[0].get('count') or 0)
        except (TypeError, ValueError):
            c = 0
        label = str(unmet[0].get('label') or '').strip()
        if label and c > 0:
            top = {'label': label, 'count': c}
    return 'ok', {'unmet': top, 'classified': body.get('classified'), 'unclassified': body.get('unclassified')}


def read_funnel(G, win, scope):
    """نداءان (الفترة والتي قبلها). ٤٠٤ ⇒ 'absent' ويُستعمل المصدر المؤقت. غير ذلك ⇒ 'failed'."""
    if scope == 'marketing':
        return 'absent', None
    out = {}
    states = {}
    for key, a, b in (('cur', win['from'], win['until']), ('prev', win['prev_from'], win['prev_until'])):
        st, body = _pull(G, FUNNEL_PATH, {'from': a.isoformat(), 'until': b.isoformat(), 'scope': scope, 'tz': TZ_NAME})
        states[key] = st
        out[key] = body if (st == 'ok' and isinstance(body, dict)) else None
    if states['cur'] == 'absent':
        return 'absent', None
    if states['cur'] != 'ok':
        return 'failed', None
    return 'ok', out


def db_get(G, key):
    return G['db'].session.get(G['Setting'], key)


def read_delivery(G, with_setting=True):
    setting = False
    try:
        row = db_get(G, SETTING_KEY)
        setting = bool(row and (row.value or '') == '1')
    except Exception:
        setting = False
    st, body = _pull(G, DELIVERY_STATE_PATH)
    out = {'setting': setting, 'bridge': st, 'platform_enabled': None, 'last_sent_week': None}
    if st == 'ok' and isinstance(body, dict):
        pe = body.get('enabled')
        out['platform_enabled'] = pe if isinstance(pe, bool) else None
        lw = body.get('last_sent_week')
        out['last_sent_week'] = lw if isinstance(lw, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', lw) else None
    elif st == 'ok':
        out['bridge'] = 'failed'
    out['text'] = delivery_text(out)
    return out


def delivery_text(d):
    br = d.get('bridge')
    if br == 'absent':
        return 'الإرسال كل أحد: %s — ينتظر تجهيز الإرسال على المنصة' % NA
    if br == 'failed':
        return 'الإرسال كل أحد: تعذّر التحقق الآن'
    if not d.get('setting'):
        return 'الإرسال كل أحد: متوقف'
    if d.get('platform_enabled'):
        t = 'يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام'
        lw = d.get('last_sent_week')
        if lw:
            try:
                y, m, dd = [int(x) for x in lw.split('-')]
                t += ' · آخر إرسال: أسبوع %s' % _date_text(datetime.date(y, m, dd))
            except Exception:
                pass
        return t
    return 'الإرسال مفعّل هنا، والمنصة لم تفعّله بعد'


# ------------------------------------------------------------------ جمع الحقائق
def collect(G, win, scope, with_delivery=True):
    """يجمع كل المصادر (واحد لكل نداء، بالتوازي، وكلٌّ يفشل لوحده). ⇒ facts."""
    tz = _tz() if win['tz_ok'] else None
    facts = {'win': win, 'scope': scope, 'src': {}, 'ledger': None, 'users': None, 'market': None, 'content': None, 'disputes': None,
             'chat': None, 'funnel': None, 'delivery': None}
    if scope == 'marketing':
        facts['src'] = {k: 'absent' for k in SOURCE_LABEL}
        facts['src']['window'] = 'ok' if win['tz_ok'] else 'failed'
        return facts
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=6)
    jobs = {
        'users': pool.submit(read_users, G, win, tz),
        'market': pool.submit(read_market, G, win, tz),
        'disputes': pool.submit(read_disputes, G),
        'chat': pool.submit(read_chat, G),
        'funnel': pool.submit(read_funnel, G, win, scope),
    }
    if with_delivery:
        jobs['delivery'] = pool.submit(read_delivery, G)
    try:
        facts['ledger'] = read_ledger(G, win)
        facts['src']['ledger'] = 'ok'
    except Exception:
        facts['src']['ledger'] = 'failed'
    try:
        st, val = read_content(G, win, tz)
        facts['content'], facts['src']['content'] = val, ('ok' if st == 'ok' else 'failed')
    except Exception:
        facts['src']['content'] = 'failed'
    for key, fut in jobs.items():
        try:
            res = fut.result(timeout=SOURCE_TIMEOUT + 3)
        except Exception:
            res = ('failed', None) if key != 'delivery' else {'setting': False, 'bridge': 'failed', 'platform_enabled': None, 'last_sent_week': None}
        if key == 'delivery':
            facts['delivery'] = res
            facts['src']['delivery'] = res['bridge']
        else:
            st, val = res
            facts[key] = val
            facts['src'][key] = st
    pool.shutdown(wait=False)
    facts['src']['window'] = 'ok' if win['tz_ok'] else 'failed'
    return facts


# ------------------------------------------------------------------ تحليل الحقائق إلى أرقام
def _count_in(dates, a, b):
    return sum(1 for d in dates if a <= d < b)


def users_figures(facts):
    """{cur, prev, buckets, today, ok_cur, ok_prev} أو None عند الفشل. نافذة ناقصة ⇒ None لأرقامها."""
    u = facts['users']
    if not u:
        return None
    win = facts['win']
    ok_cur = _complete(u['n'], USERS_LIMIT, u['oldest'], win['from'])
    ok_prev = _complete(u['n'], USERS_LIMIT, u['oldest'], win['prev_from'])
    bks = None
    if ok_cur:
        bks = [0] * len(buckets_of(win))
        for d in u['dates']:
            i = _bucket_index(win, d)
            if i is not None:
                bks[i] += 1
    return {'cur': _count_in(u['dates'], win['from'], win['until']) if ok_cur else None,
            'prev': _count_in(u['dates'], win['prev_from'], win['prev_until']) if ok_prev else None,
            'buckets': bks, 'today': (sum(1 for d in u['dates'] if d == win['today']) if ok_cur else None),
            'ok_cur': ok_cur, 'ok_prev': ok_prev}


def market_figures(facts):
    m = facts['market']
    if not m:
        return None
    win = facts['win']
    ok_cur = m['complete_all'] or (m['oldest'] is not None and m['oldest'] < win['from'])
    ok_prev = m['complete_all'] or (m['oldest'] is not None and m['oldest'] < win['prev_from'])

    def stats(a, b):
        its = [i for i in m['items'] if a <= i['date'] < b]
        course = [i for i in its if i['need'] == 'course']
        return {'new': len(its), 'with_offers': sum(1 for i in its if i['offers'] > 0), 'matched': sum(1 for i in its if i['status'] == 'matched'),
                'unanswered': sum(1 for i in its if i['status'] == 'open' and i['offers'] == 0),
                'course_need': len(course), 'course_unanswered': sum(1 for i in course if i['status'] == 'open' and i['offers'] == 0)}
    return {'cur': stats(win['from'], win['until']) if ok_cur else None, 'prev': stats(win['prev_from'], win['prev_until']) if ok_prev else None}


def content_figures(facts):
    c = facts['content']
    if c is None:
        return None
    win = facts['win']
    return {'cur': _count_in(c['dates'], win['from'], win['until']), 'prev': _count_in(c['dates'], win['prev_from'], win['prev_until'])}


def _sum_income(lst):
    """قائمة [{currency, amount}] من المنصة ⇒ مجاميع السنت لكل عملة."""
    acc = {}
    for it in lst or []:
        if not isinstance(it, dict):
            continue
        try:
            acc[str(it.get('currency') or 'EGP').upper()] = acc.get(str(it.get('currency') or 'EGP').upper(), 0) + _cents(it.get('amount') or 0)
        except (TypeError, ValueError):
            continue
    return acc


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def money_figures(facts):
    """لكل خدمة (experts/courses/books) والإجمالي: {cur:{count,totals}, prev:{...}} أو None لو الدفتر فشل.
    وحين تردّ المنصة بأرقام قسم (N3) تحل محل قراءة الدفتر لذلك القسم وحده."""
    if facts['src'].get('ledger') != 'ok' or facts['ledger'] is None:
        return None
    win = facts['win']
    cur = aggregate_ledger(facts['ledger'], win['from'], win['until'])
    prev = aggregate_ledger(facts['ledger'], win['prev_from'], win['prev_until'])
    out = {s: {'cur': cur[s], 'prev': prev[s], 'from_platform': False} for s in ('experts', 'courses', 'books', 'other')}
    fn = facts.get('funnel')
    if facts['src'].get('funnel') == 'ok' and fn:
        for sec, svc in SVC_OF_SECTION.items():
            c = ((fn.get('cur') or {}).get('sections') or {}).get(sec) or {}
            p = ((fn.get('prev') or {}).get('sections') or {}).get(sec) or {}
            if isinstance(c.get('income'), list) and _num(c.get('paid_orders')) is not None:
                out[svc]['cur'] = {'count': int(c['paid_orders']), 'totals': _totals_list(_sum_income(c['income']))}
                out[svc]['from_platform'] = True
                if isinstance(p.get('income'), list) and _num(p.get('paid_orders')) is not None:
                    out[svc]['prev'] = {'count': int(p['paid_orders']), 'totals': _totals_list(_sum_income(p['income']))}
                else:
                    out[svc]['prev'] = None
    return out


def _pct(cur, prev):
    return _round((cur - prev) * 100.0 / prev)


def trend_of(cur_egp, prev_egp, cur_count, prev_count):
    if cur_egp == 0 and prev_egp == 0:
        return {'key': 'none' if (cur_count or 0) == 0 and (prev_count or 0) == 0 else 'flat', 'pct': None}
    if prev_egp == 0:
        return {'key': 'new', 'pct': None}
    p = _pct(cur_egp, prev_egp)
    key = 'up' if p >= 5 else 'down' if p <= -5 else 'flat'
    return {'key': key, 'pct': p}


def trend_chip(t):
    k = t.get('key')
    p = t.get('pct')
    if k == 'up':
        return {'text': 'ينمو %s٪' % _ar(abs(p)), 'tone': 'up'}
    if k == 'down':
        return {'text': 'يتراجع %s٪' % _ar(abs(p)), 'tone': 'down'}
    if k == 'flat':
        return {'text': 'ثابت', 'tone': 'flat'}
    if k == 'new':
        return {'text': 'جديد', 'tone': 'up'}
    if k == 'none':
        return {'text': 'لا بيع', 'tone': 'mute'}
    return {'text': NA, 'tone': 'na'}


# ------------------------------------------------------------------ الأقسام (كل قسم في سطر)
def build_sections(facts, mf, mk, ct):
    secs = []
    funnel_ok = facts['src'].get('funnel') == 'ok'
    for key in MONEY:
        svc = SVC_OF_SECTION[key]
        row = {'key': key, 'label': SECTION_NAME[key], 'open': key, 'note': None, 'value': None, 'prev': None}
        if mf is None:
            row.update({'trend': {'key': 'na', 'pct': None}, 'chip': trend_chip({'key': 'na'})})
        else:
            c, p = mf[svc]['cur'], mf[svc]['prev']
            ce = _egp_of(c['totals'])
            row['value'] = {'kind': 'money', 'egp': ce, 'others': _others_of(c['totals']), 'count': c['count'], 'text': _money_text(ce, 'EGP')}
            if p is None:
                row['trend'] = {'key': 'na', 'pct': None}
            else:
                pe = _egp_of(p['totals'])
                row['prev'] = {'egp': pe, 'count': p['count']}
                row['trend'] = trend_of(ce, pe, c['count'], p['count'])
            row['chip'] = trend_chip(row['trend'])
            if row['value']['others']:
                row['chip_hint'] = 'النسبة بالجنيه فقط'
            if key == 'files' and not mf[svc]['from_platform']:
                row['note'] = 'تشمل الاستشارات العادية'
        secs.append(row)
    # السوق
    row = {'key': 'market', 'label': SECTION_NAME['market'], 'open': 'market', 'note': None, 'value': None, 'prev': None}
    if mk is None or mk['cur'] is None:
        row['chip'] = {'text': NA, 'tone': 'na'}
    else:
        n, u = mk['cur']['new'], mk['cur']['unanswered']
        row['value'] = {'kind': 'count', 'n': n, 'text': _u(n, ['طلب جديد واحد', 'طلبان جديدان', 'طلبات جديدة', 'طلبًا جديدًا'])}
        if u > 0:
            row['chip'] = {'text': _u(u, ['طلب واحد بلا عرض', 'طلبان بلا عرض', 'طلبات بلا عرض', 'طلبًا بلا عرض']), 'tone': 'bad'}
        else:
            row['chip'] = {'text': 'كلها جاءها عرض' if n else 'لا طلبات جديدة', 'tone': 'mute'}
    secs.append(row)
    # المحتوى
    row = {'key': 'content', 'label': SECTION_NAME['content'], 'open': 'content', 'note': None, 'value': None, 'prev': None}
    if ct is None:
        row['chip'] = {'text': NA, 'tone': 'na'}
    else:
        n = ct['cur']
        row['value'] = {'kind': 'count', 'n': n, 'text': _u(n, ['مقال واحد نُشر', 'مقالان نُشرا', 'مقالات نُشرت', 'مقالًا نُشر'])}
        cv = None
        if funnel_ok:
            cv = _num((((facts['funnel'].get('cur') or {}).get('sections') or {}).get('content') or {}).get('visits'))
        row['chip'] = {'text': 'الزيارات: %s' % (_ar(cv) if cv is not None else NA), 'tone': 'mute' if cv is not None else 'na'}
    secs.append(row)
    # رضا العملاء: التقييمات غير مسجّلة بعد، والنزاعات من مصدر الشارة
    row = {'key': 'satisfaction', 'label': SECTION_NAME['satisfaction'], 'open': 'disputes', 'note': None, 'value': None, 'prev': None}
    d = facts.get('disputes')
    if facts['src'].get('disputes') != 'ok' or d is None:
        row['chip'] = {'text': NA, 'tone': 'na'}
    elif d > 0:
        row['chip'] = {'text': _u(d, ['نزاع مفتوح', 'نزاعان مفتوحان', 'نزاعات مفتوحة', 'نزاعًا مفتوحًا']), 'tone': 'bad'}
    else:
        row['chip'] = {'text': 'لا نزاع مفتوح', 'tone': 'mute'}
    secs.append(row)
    return secs


# ------------------------------------------------------------------ رحلة الزائر
STAGE_CONV = {'asked': 'من الزوار', 'signed_up': 'ممن سألوا', 'opened': 'من المسجّلين', 'paid': 'ممن فتحوا'}
STAGE_ORDER = ['visits', 'asked', 'signed_up', 'opened', 'paid']
STAGE_LABEL = {'visits': 'زاروا المنصة', 'asked': 'سألوا سؤالًا', 'signed_up': 'سجّلوا حسابًا', 'opened': 'فتحوا ملفًا أو دورة', 'paid': 'دفعوا'}
PAID_SUB = 'عمليات دفع في الملفات والدورات والكتب، وقد يدفع الشخص أكثر من مرة'
SCOPE_STAGES = {
    'files': [('asked', 'سألوا سؤالًا'), ('opened', 'فتحوا ملفًا'), ('paid', 'دفعوا')],
    'courses': [('page_visits', 'زاروا صفحة دورة'), ('enrolled', 'سجّلوا في دورة'), ('paid', 'دفعوا')],
    'books': [('page_visits', 'زاروا صفحة كتاب'), ('buy_clicks', 'ضغطوا «اشترِ»'), ('paid', 'دفعوا')],
    'market': [('new', 'طلبات جديدة'), ('with_offers', 'جاءها عرض'), ('matched', 'تمّ الاتفاق')],
    'content': [('published', 'مقالات نُشرت'), ('visits', 'زيارات المقالات'), ('signups_from_articles', 'حسابات جاءت من مقال')],
}


def change_of(cur, prev):
    """سطر التغيير: (نص، نغمة، نسبة). cur مجهول ⇒ لا سطر. prev مجهول ⇒ لا سطر."""
    if cur is None or prev is None:
        return None, None, None
    if prev == 0:
        if cur > 0:
            return 'جديد', 'up', None
        return 'كما هو', 'flat', 0
    raw = (cur - prev) * 100.0 / prev
    if abs(raw) < 1:
        return 'كما هو', 'flat', 0
    p = _round(raw)
    return ('▲ %s٪' % _ar(abs(p)), 'up', p) if p > 0 else ('▼ %s٪' % _ar(abs(p)), 'down', p)


def missing_text(n):
    verb = 'تكتملان' if int(n) == 2 else 'تكتمل'
    return '%s %s حين تسجّل المنصة الزيارات' % (_u(n, ['خطوة واحدة', 'خطوتان', 'خطوات', 'خطوة']), verb)


def _stage(key, label, cur, prev, prev_stage_cur=None, sub=None, failed=False):
    text, tone, pct = change_of(cur, prev)
    conv_pct = conv_text = None
    if key in STAGE_CONV and cur is not None and prev_stage_cur not in (None, 0):
        conv_pct = _round(cur * 100.0 / prev_stage_cur)
        conv_text = '%s٪ %s' % (_ar(conv_pct), STAGE_CONV[key])
    return {'key': key, 'label': label, 'cur': cur, 'prev': prev, 'change_pct': pct, 'change_text': text, 'trend': tone or 'na',
            'conv_pct': conv_pct, 'conv_text': conv_text, 'sub': sub,
            'failed': bool(failed and cur is None)}


def build_funnel(facts, scope, mf, uf, mk, ct):
    funnel_ok = facts['src'].get('funnel') == 'ok'
    fc = ((facts['funnel'] or {}).get('cur') or {}) if funnel_ok else {}
    fp = ((facts['funnel'] or {}).get('prev') or {}) if funnel_ok else {}
    stages = []
    if scope == 'all':
        def pick(key, interim_cur, interim_prev):
            c = _num((fc.get('stages') or {}).get(key))
            p = _num((fp.get('stages') or {}).get(key))
            if c is not None:
                return c, p
            return interim_cur, interim_prev
        cur_vals = {}
        cur_vals['visits'] = pick('visits', None, None)
        cur_vals['asked'] = pick('asked', None, None)
        cur_vals['signed_up'] = pick('signed_up', uf['cur'] if uf else None, uf['prev'] if uf else None)
        cur_vals['opened'] = pick('opened', None, None)
        paid_c = _num((fc.get('stages') or {}).get('paid_people'))
        paid_p = _num((fp.get('stages') or {}).get('paid_people'))
        if paid_c is None and mf is not None:
            paid_c = sum(mf[s]['cur']['count'] for s in ('experts', 'courses', 'books'))
            paid_p = sum(mf[s]['prev']['count'] for s in ('experts', 'courses', 'books')) if all(mf[s]['prev'] is not None for s in ('experts', 'courses', 'books')) else None
        cur_vals['paid'] = (paid_c, paid_p)
        prev_cur = None
        for k in STAGE_ORDER:
            c, p = cur_vals[k]
            failed = (k == 'signed_up' and uf is None) or (k == 'paid' and mf is None)
            stages.append(_stage(k, STAGE_LABEL[k], c, p, prev_cur, PAID_SUB if (k == 'paid' and not funnel_ok) else None, failed))
            prev_cur = c
        title = 'من الزيارة إلى الدفع'
    elif scope in SCOPE_STAGES:
        sec = (fc.get('sections') or {}).get(scope) or {}
        psec = (fp.get('sections') or {}).get(scope) or {}
        vals = {}
        if scope == 'files':
            ex = mf['experts'] if mf else None
            vals['asked'] = (None, None)
            vals['opened'] = (_num(sec.get('opened')), _num(psec.get('opened')))
            vals['paid'] = (_num(sec.get('paid_orders')) if _num(sec.get('paid_orders')) is not None else (ex['cur']['count'] if ex else None),
                            _num(psec.get('paid_orders')) if _num(sec.get('paid_orders')) is not None else (ex['prev']['count'] if ex and ex['prev'] else None))
        elif scope in ('courses', 'books'):
            svc = SVC_OF_SECTION[scope]
            ex = mf[svc] if mf else None
            second = 'enrolled' if scope == 'courses' else 'buy_clicks'
            vals['page_visits'] = (_num(sec.get('page_visits')), _num(psec.get('page_visits')))
            vals[second] = (_num(sec.get(second)), _num(psec.get(second)))
            vals['paid'] = (_num(sec.get('paid_orders')) if _num(sec.get('paid_orders')) is not None else (ex['cur']['count'] if ex else None),
                            _num(psec.get('paid_orders')) if _num(sec.get('paid_orders')) is not None else (ex['prev']['count'] if ex and ex['prev'] else None))
        elif scope == 'market':
            c = mk['cur'] if mk else None
            p = mk['prev'] if mk else None
            for k in ('new', 'with_offers', 'matched'):
                vals[k] = (c[k] if c else None, p[k] if p else None)
        elif scope == 'content':
            vals['published'] = (ct['cur'] if ct else None, ct['prev'] if ct else None)
            vals['visits'] = (_num(sec.get('visits')), _num(psec.get('visits')))
            vals['signups_from_articles'] = (_num(sec.get('signups_from_articles')), _num(psec.get('signups_from_articles')))
        for k, label in SCOPE_STAGES[scope]:
            c, p = vals.get(k, (None, None))
            if scope == 'market':
                failed = True
            elif scope == 'content':
                failed = k == 'published' and ct is None
            else:
                failed = k == 'paid' and mf is None
            stages.append(_stage(k, label, c, p, None, None, failed))
        title = 'رحلة %s' % SECTION_NAME[scope]
    else:
        return None
    # «تكتمل حين تسجّل المنصة…» للخطوات التي لم يُسجَّل مصدرها بعد فقط؛ ما تعذّر جلبه يبقى صفًّا «غير متاح بعد»
    missing = sum(1 for s in stages if s['cur'] is None and not s['failed'])
    return {'title': title, 'mode': 'full' if funnel_ok else 'compact', 'missing': missing,
            'missing_text': missing_text(missing) if missing else None, 'stages': stages}


# ------------------------------------------------------------------ اليوم بيوم
def build_daily(facts, scope, mf, uf):
    win = facts['win']
    bks = buckets_of(win)
    if scope in ('market', 'content', 'marketing'):
        return {'na': True, 'reason': 'لا يوجد دخل يومي لهذا القسم', 'bucket': 'week' if win['bucket_days'] == 7 else 'day', 'rows': [],
                'income_other': [], 'signups_available': False, 'visits_available': False}
    svcs = ('experts', 'courses', 'books') if scope == 'all' else (SVC_OF_SECTION[scope],)
    ledger_ok = facts['src'].get('ledger') == 'ok' and facts['ledger'] is not None
    fn = (facts['funnel'] or {}).get('cur') if facts['src'].get('funnel') == 'ok' else None
    by_day = {}
    if fn and isinstance(fn.get('by_day'), list):
        for r in fn['by_day']:
            if isinstance(r, dict) and isinstance(r.get('date'), str):
                by_day[r['date']] = r
    nb = len(bks)
    inc = [0] * nb
    cnt = [0] * nb
    other_acc = {}
    if ledger_ok:
        for r in facts['ledger']:
            if r['svc'] not in svcs:
                continue
            i = _bucket_index(win, r['date'])
            if i is None:
                continue
            for cur, amt in r['parts']:
                if cur == 'EGP':
                    inc[i] += _cents(amt)
                else:
                    other_acc[cur] = other_acc.get(cur, 0) + _cents(amt)
            cnt[i] += 1
    # أرقام المنصة (الجسر) تحل محل المؤقت لنفس اليوم، والدخل اليومي من المنصة للمنصة كلها فقط
    vis, fsign, finc = [None] * nb, [None] * nb, [None] * nb
    fother = {}
    if by_day:
        for i, (a, b) in enumerate(bks):
            days = [by_day.get((a + datetime.timedelta(days=k)).isoformat()) for k in range((b - a).days)]
            if not days or any(d is None for d in days):
                continue
            vs = [_num(d.get('visits')) for d in days]
            if all(v is not None for v in vs):
                vis[i] = sum(vs)
            ss = [_num(d.get('signups')) for d in days]
            if all(v is not None for v in ss):
                fsign[i] = sum(ss)
            if scope == 'all' and all(isinstance(d.get('income'), list) for d in days):
                acc = {}
                for d in days:
                    for cur, c in _sum_income(d['income']).items():
                        acc[cur] = acc.get(cur, 0) + c
                finc[i] = acc
    use_finc = nb > 0 and all(x is not None for x in finc)
    if use_finc:
        inc = [x.get('EGP', 0) for x in finc]
        other_acc = {}
        for x in finc:
            for cur, c in x.items():
                if cur != 'EGP':
                    other_acc[cur] = other_acc.get(cur, 0) + c
    income_ok = ledger_ok or use_finc
    users_bks = uf['buckets'] if (scope == 'all' and uf is not None) else None
    rows = []
    for i, (a, b) in enumerate(bks):
        sg = fsign[i] if (scope == 'all' and fsign[i] is not None) else (users_bks[i] if users_bks is not None else None)
        rows.append({'from': a.isoformat(), 'to': (b - datetime.timedelta(days=1)).isoformat(), 'label': _date_text(a),
                     'income_egp': (inc[i] / 100.0) if income_ok else None, 'count': cnt[i] if ledger_ok and not use_finc else None,
                     'signups': sg if scope == 'all' else None, 'visits': vis[i]})
    return {'na': False, 'bucket': 'week' if win['bucket_days'] == 7 else 'day', 'rows': rows,
            'income_other': _totals_list(other_acc) if income_ok else [], 'ledger': income_ok,
            'signups_available': bool(scope == 'all' and rows and all(r['signups'] is not None for r in rows)),
            'visits_available': bool(rows and all(r['visits'] is not None for r in rows))}


def build_today(facts, scope, uf):
    win = facts['win']
    if scope in ('market', 'content', 'marketing') or win.get('kind') == 'weekly':
        return None
    svcs = ('experts', 'courses', 'books') if scope == 'all' else (SVC_OF_SECTION[scope],)
    inc, other = None, []
    if facts['src'].get('ledger') == 'ok' and facts['ledger'] is not None:
        acc, oth = 0, {}
        for r in facts['ledger']:
            if r['svc'] in svcs and r['date'] == win['today']:
                for cur, amt in r['parts']:
                    if cur == 'EGP':
                        acc += _cents(amt)
                    else:
                        oth[cur] = oth.get(cur, 0) + _cents(amt)
        inc, other = acc / 100.0, _totals_list(oth)
    return {'income_egp': inc, 'income_other': other, 'signups': (uf['today'] if (uf is not None and scope == 'all') else None),
            'show_signups': scope == 'all'}


def build_origins(facts, scope):
    base = {'channels': None, 'countries': None, 'top_pages': None, 'note': 'تكتمل حين تسجّل المنصة مصدر كل زائر وكل دفعة.'}
    if facts['src'].get('funnel') != 'ok' or scope != 'all':
        return base
    o = (facts['funnel'].get('cur') or {}).get('origins')
    if not isinstance(o, dict):
        return base
    out = dict(base)
    ch = o.get('channels')
    if isinstance(ch, list) and ch:
        tot = sum(_num(c.get('signups')) or 0 for c in ch if isinstance(c, dict))
        rows = []
        by = {str(c.get('key')): c for c in ch if isinstance(c, dict)}
        for k in CHANNEL_ORDER:
            c = by.get(k)
            if not c:
                continue
            s = _num(c.get('signups'))
            rows.append({'key': k, 'label': CHANNEL_LABEL[k], 'signups': s, 'visits': _num(c.get('visits')),
                         'pct': _round(s * 100.0 / tot) if (s is not None and tot) else None})
        out['channels'] = rows or None
    co = o.get('countries')
    if isinstance(co, list) and co:
        tot = sum(_num(c.get('signups')) or 0 for c in co if isinstance(c, dict))
        named = sorted([c for c in co if isinstance(c, dict) and str(c.get('code') or '').upper() in COUNTRY_LABEL and _num(c.get('signups'))],
                       key=lambda c: -c['signups'])
        top = named[:6]
        shown = sum(c['signups'] for c in top)
        rows = [{'code': str(c['code']).upper(), 'label': COUNTRY_LABEL[str(c['code']).upper()], 'signups': c['signups'],
                 'pct': _round(c['signups'] * 100.0 / tot) if tot else None} for c in top]
        if tot and tot - shown > 0:
            rows.append({'code': 'other', 'label': 'بلاد أخرى', 'signups': tot - shown, 'pct': _round((tot - shown) * 100.0 / tot)})
        out['countries'] = rows or None
    tp = o.get('top_pages')
    if isinstance(tp, list) and tp:
        rows = [{'path': str(p.get('path') or ''), 'title': str(p.get('title') or '').strip(), 'visits': _num(p.get('visits'))}
                for p in tp[:3] if isinstance(p, dict) and _num(p.get('visits')) is not None]
        out['top_pages'] = rows or None
    return out


# ------------------------------------------------------------------ العقل: جمل ثابتة من الأرقام
def figures(facts, mf, uf, mk):
    """الأرقام التي تحتاجها قواعد العقل، لكل مصدر: القيمة أو None عند الفشل."""
    fig = {'money': {}, 'signups': None, 'market': None, 'unmet': None, 'failed': {}, 'foreign': False, 'files_caveat': False}
    fig['failed']['ledger'] = mf is None
    fig['failed']['users'] = uf is None
    fig['failed']['market'] = mk is None
    fig['failed']['chat'] = facts['src'].get('chat') != 'ok'
    if mf is not None:
        for sec in MONEY:
            c, p = mf[SVC_OF_SECTION[sec]]['cur'], mf[SVC_OF_SECTION[sec]]['prev']
            fig['money'][sec] = {'cur_egp': _egp_of(c['totals']), 'cur_count': c['count'],
                                 'prev_egp': _egp_of(p['totals']) if p else None, 'prev_count': p['count'] if p else None}
            if _others_of(c['totals']) or (p and _others_of(p['totals'])):
                fig['foreign'] = True
        fig['files_caveat'] = not mf['experts']['from_platform']
    if uf is not None and uf['cur'] is not None and uf['prev'] is not None:
        fig['signups'] = {'cur': uf['cur'], 'prev': uf['prev']}
    elif uf is not None:
        fig['failed']['users'] = True
    if mk is not None and mk['cur'] is not None:
        fig['market'] = {'cur': mk['cur'], 'prev': mk['prev']}
    elif mk is not None:
        fig['failed']['market'] = True
    if facts['src'].get('chat') == 'ok' and facts['chat'] is not None:
        fig['unmet'] = facts['chat']['unmet']
    return fig


def _basis(label, value, source):
    return {'label': label, 'value': value, 'source': SOURCE_LABEL.get(source, source)}


def _files_caveat(sec, fig, basis):
    if sec == 'files' and fig['files_caveat']:
        basis.append(_basis('ما يشمله الرقم', 'ملفات الخبراء والاستشارات العادية', 'ledger'))


def _line(key, label):
    return {'key': key, 'label': label, 'text': None, 'empty_text': None, 'na_reason': None, 'basis': [], 'action': None}


def _action(section):
    return {'label': OPEN_LABEL[section], 'section': section, 'tab': None}


def build_brain(fig, scope):
    """ثلاثة أسطر: شغّال · واقف · فرصة. الترتيب والقواعد في SPEC-reports §7. ⇒ (lines, primary)."""
    working, stalled, opp = _line('working', 'شغّال'), _line('stalled', 'واقف'), _line('opportunity', 'فرصة')
    lines = [working, stalled, opp]
    if scope == 'marketing':
        for ln in lines:
            ln['na_reason'] = MARKETING_NA
        return lines, None
    secs = list(MONEY) if scope == 'all' else ([scope] if scope in MONEY else [])
    use_signups = scope == 'all'
    use_market = scope in ('all', 'market')
    money = fig['money']
    secs = [x for x in secs if fig['failed'].get('ledger') or x in money]

    def failed_labels(*keys):
        return [SOURCE_LABEL[k] for k in keys if fig['failed'].get(k)]

    def finish(ln, matched, empty, labels):
        if matched:
            return
        if labels:
            ln['na_reason'] = 'تعذّر جلب ' + ' و'.join(labels)
        else:
            ln['empty_text'] = empty

    # —— شغّال
    skipped = []
    hit = None
    if secs:
        if fig['failed']['ledger']:
            skipped.append('ledger')
        else:
            best = None
            for s in secs:
                m = money[s]
                if m['prev_egp'] and m['prev_egp'] > 0 and m['cur_count'] >= 2:
                    pct = _pct(m['cur_egp'], m['prev_egp'])
                    if pct >= 10 and (best is None or m['cur_egp'] - m['prev_egp'] > best[1]['cur_egp'] - best[1]['prev_egp']):
                        best = (s, m, pct)
            if best:
                s, m, pct = best
                basis = [_basis('%s الآن' % INCOME_NAME[s], _money_text(m['cur_egp'], 'EGP'), 'ledger'),
                         _basis('%s قبلها' % INCOME_NAME[s], _money_text(m['prev_egp'], 'EGP'), 'ledger')]
                if m['prev_count'] >= 3:
                    working['text'] = '%s زاد %s٪: من %s إلى %s جنيه.' % (INCOME_NAME[s], _ar(pct), _ar(m['prev_egp']), _ar(m['cur_egp']))
                else:
                    working['text'] = '%s: %s مقابل %s في الفترة التي قبلها.' % (
                        SECTION_NAME[s], _u(m['cur_count'], ['عملية بيع واحدة', 'عمليتا بيع', 'عمليات بيع', 'عملية بيع']),
                        _u(m['prev_count'], ['عملية واحدة', 'عمليتين', 'عمليات', 'عملية']))
                basis.append(_basis('عدد العمليات الآن وقبلها', '%s و%s' % (_ar(m['cur_count']), _ar(m['prev_count'])), 'ledger'))
                _files_caveat(s, fig, basis)
                if fig['foreign']:
                    basis.append(_basis('ملاحظة', 'النسبة بالجنيه فقط', 'ledger'))
                working['basis'] = basis
                working['action'] = _action(s)
                hit = True
    if not hit and use_signups:
        if fig['failed']['users'] or fig['signups'] is None:
            skipped.append('users')
        else:
            sg = fig['signups']
            if sg['prev'] >= 5 and _pct(sg['cur'], sg['prev']) >= 10:
                pct = _pct(sg['cur'], sg['prev'])
                working['text'] = 'الحسابات الجديدة زادت %s٪: %s مقابل %s.' % (_ar(pct), _ar(sg['cur']), _ar(sg['prev']))
                working['basis'] = [_basis('الحسابات الجديدة الآن', _ar(sg['cur']), 'users'), _basis('الحسابات الجديدة قبلها', _ar(sg['prev']), 'users')]
                working['action'] = _action('people')
                hit = True
    if not hit and use_market:
        if fig['failed']['market'] or fig['market'] is None or fig['market']['prev'] is None:
            skipped.append('market')
        else:
            c, p = fig['market']['cur']['new'], fig['market']['prev']['new']
            if p >= 3 and _pct(c, p) >= 10:
                pct = _pct(c, p)
                working['text'] = 'طلبات السوق زادت %s٪: %s مقابل %s.' % (_ar(pct), _ar(c), _ar(p))
                working['basis'] = [_basis('طلبات السوق الجديدة الآن', _ar(c), 'market'), _basis('طلبات السوق الجديدة قبلها', _ar(p), 'market')]
                working['action'] = _action('market')
                hit = True
    if not (secs or use_signups or use_market):
        working['na_reason'] = NO_RULES_NA
    else:
        finish(working, hit, 'لا نموّ واضح في هذه الفترة.', failed_labels(*skipped))

    # —— واقف
    skipped = []
    hit = None
    if secs:
        if fig['failed']['ledger']:
            skipped.append('ledger')
        else:
            cand = [(s, money[s]) for s in secs if money[s]['prev_count'] and money[s]['prev_count'] >= 1 and money[s]['cur_count'] == 0]
            if cand:
                s, m = sorted(cand, key=lambda x: -x[1]['prev_count'])[0]
                pc = m['prev_count']
                verb = 'وكان' if pc >= 3 else 'وكانت'
                stalled['text'] = '%s: لا بيع في هذه الفترة، %s %s في الفترة التي قبلها.' % (
                    SECTION_NAME[s], verb, _u(pc, ['عملية واحدة', 'عمليتان', 'عمليات', 'عملية']))
                basis = [_basis('عدد العمليات الآن', _ar(0), 'ledger'), _basis('عدد العمليات قبلها', _ar(pc), 'ledger')]
                _files_caveat(s, fig, basis)
                stalled['basis'] = basis
                stalled['action'] = _action(s)
                hit = True
            else:
                drops = []
                for s in secs:
                    m = money[s]
                    if m['prev_egp'] and m['prev_egp'] > 0 and m['prev_count'] >= 3 and _pct(m['cur_egp'], m['prev_egp']) <= -10:
                        drops.append((m['prev_egp'] - m['cur_egp'], s, m))
                if drops:
                    _, s, m = sorted(drops, key=lambda x: -x[0])[0]
                    pct = _pct(m['cur_egp'], m['prev_egp'])
                    stalled['text'] = '%s نزل %s٪: من %s إلى %s جنيه.' % (INCOME_NAME[s], _ar(abs(pct)), _ar(m['prev_egp']), _ar(m['cur_egp']))
                    basis = [_basis('%s الآن' % INCOME_NAME[s], _money_text(m['cur_egp'], 'EGP'), 'ledger'),
                             _basis('%s قبلها' % INCOME_NAME[s], _money_text(m['prev_egp'], 'EGP'), 'ledger')]
                    _files_caveat(s, fig, basis)
                    if fig['foreign']:
                        basis.append(_basis('ملاحظة', 'النسبة بالجنيه فقط', 'ledger'))
                    stalled['basis'] = basis
                    stalled['action'] = _action(s)
                    hit = True
    if not hit and use_market:
        if fig['failed']['market'] or fig['market'] is None:
            skipped.append('market')
        else:
            u = fig['market']['cur']['unanswered']
            if u > 0:
                stalled['text'] = _u(u, ['طلب واحد في السوق بلا عرض من خبير.', 'طلبان في السوق بلا عرض من خبير.',
                                         'طلبات في السوق بلا عرض من خبير.', 'طلبًا في السوق بلا عرض من خبير.'])
                stalled['basis'] = [_basis('طلبات بلا عرض', _ar(u), 'market'), _basis('طلبات السوق الجديدة', _ar(fig['market']['cur']['new']), 'market')]
                stalled['action'] = _action('market')
                hit = True
    if not hit and use_signups:
        if fig['failed']['users'] or fig['signups'] is None:
            skipped.append('users')
        else:
            sg = fig['signups']
            if sg['prev'] >= 5 and _pct(sg['cur'], sg['prev']) <= -10:
                pct = _pct(sg['cur'], sg['prev'])
                stalled['text'] = 'الحسابات الجديدة نزلت %s٪: %s مقابل %s.' % (_ar(abs(pct)), _ar(sg['cur']), _ar(sg['prev']))
                stalled['basis'] = [_basis('الحسابات الجديدة الآن', _ar(sg['cur']), 'users'), _basis('الحسابات الجديدة قبلها', _ar(sg['prev']), 'users')]
                stalled['action'] = _action('people')
                hit = True
    if not (secs or use_signups or use_market):
        stalled['na_reason'] = NO_RULES_NA
    else:
        finish(stalled, hit, 'لا تراجع واضح في هذه الفترة.', failed_labels(*skipped))

    # —— فرصة
    if scope in ('all', 'market', 'courses', 'files'):
        skipped = []
        hit = None
        if fig['failed']['chat']:
            skipped.append('chat')
        elif fig['unmet']:
            un = fig['unmet']
            opp['text'] = '%s عن «%s» ولا نقدّم له خدمة بعد.' % (_u(un['count'], ['سؤال واحد', 'سؤالان', 'أسئلة', 'سؤالًا']), un['label'])
            opp['basis'] = [_basis('عدد الأسئلة', _ar(un['count']), 'chat'), _basis('المدة', 'كل الأسئلة منذ البداية', 'chat')]
            opp['action'] = {'label': 'افتح الدورات', 'section': 'courses', 'tab': None}
            hit = True
        if not hit:
            if fig['failed']['market'] or fig['market'] is None:
                skipped.append('market')
            else:
                mk = fig['market']['cur']
                if mk['course_need'] >= 3 and mk['course_unanswered'] * 2 > mk['course_need']:
                    opp['text'] = '%s في السوق تطلب دورة، ولا يوجد عرض لأغلبها.' % _u(mk['course_need'], ['طلب واحد', 'طلبان', 'طلبات', 'طلبًا'])
                    opp['basis'] = [_basis('طلبات تطلب دورة', _ar(mk['course_need']), 'market'), _basis('منها بلا عرض', _ar(mk['course_unanswered']), 'market')]
                    opp['action'] = _action('market')
                    hit = True
        finish(opp, hit, 'لا فرصة واضحة في الأسئلة والطلبات حتى الآن.', failed_labels(*skipped))
    else:
        opp['na_reason'] = OPP_NA
    primary = None
    for k, ln in (('stalled', stalled), ('opportunity', opp), ('working', working)):
        if ln['text'] and ln['action']:
            primary = k
            break
    return lines, primary


# ------------------------------------------------------------------ الرد الكامل
def build_payload(facts, scope, period):
    win = facts['win']
    mf = money_figures(facts)
    uf = users_figures(facts)
    mk = market_figures(facts)
    ct = content_figures(facts)
    fig = figures(facts, mf, uf, mk)
    sections = build_sections(facts, mf, mk, ct)
    funnel = build_funnel(facts, scope, mf, uf, mk, ct)
    daily = build_daily(facts, scope, mf, uf)
    today = build_today(facts, scope, uf)
    brain, primary = build_brain(fig, scope)
    src = dict(facts['src'])
    users_state = src.get('users')
    if users_state == 'ok' and uf is not None and not (uf['ok_cur'] and uf['ok_prev']):
        src['users'] = 'partial'
    if src.get('market') == 'ok' and mk is not None and (mk['cur'] is None or mk['prev'] is None):
        src['market'] = 'partial'
    gen = win['now'].isoformat(timespec='seconds')
    out = {'ok': True, 'scope': scope, 'period': period,
           'window': {'from': win['from'].isoformat(), 'until': win['until'].isoformat(), 'days': win['days'], 'tz': TZ_NAME if win['tz_ok'] else 'UTC',
                      'label': win['label']},
           'prev': {'from': win['prev_from'].isoformat(), 'until': win['prev_until'].isoformat(), 'label': win['prev_label']},
           'generated_at': gen, 'sources': src, 'layout': 'full' if src.get('funnel') == 'ok' else 'compact',
           'funnel': funnel, 'daily': daily, 'today': today, 'origins': build_origins(facts, scope), 'sections': sections,
           'brain': brain, 'brain_primary': primary}
    if facts.get('delivery') is not None:
        out['delivery'] = facts['delivery']
    return out


def weekly_text(p):
    """نص التقرير كله بالعربية البسيطة، سطرًا سطرًا، والبنود غير المتاحة تُذكر «غير متاح بعد»."""
    L = ['تقرير الأسبوع', '%s، مقارنة بالأسبوع الذي قبله' % p['week']['label'], '', 'ملخص العقل']
    for b in p['brain']:
        t = b['text'] or b['empty_text'] or ('%s: %s' % (NA, b['na_reason']) if b['na_reason'] else NA)
        L.append('%s: %s' % (b['label'], t))
    L += ['', 'الأرقام']
    fn = p.get('funnel') or {}
    for s in fn.get('stages', []):
        if s['cur'] is None:
            L.append('%s: %s' % (s['label'], NA))
        else:
            extra = [x for x in (s.get('change_text'), s.get('conv_text')) if x]
            L.append('%s: %s%s' % (s['label'], _ar(s['cur']), (' (%s)' % ' · '.join(extra)) if extra else ''))
    L += ['', 'كل قسم في سطر']
    for r in p['sections']:
        val = r['value']['text'] if r.get('value') else NA
        chip = r.get('chip', {}).get('text')
        L.append('%s: %s%s' % (r['label'], val, (' · ' + chip) if chip else ''))
    return '\n'.join(L)


# ------------------------------------------------------------------ الذاكرة المؤقتة
def _cache_get(key, ttl):
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    return None


def _cache_put(key, val):
    with _CACHE_LOCK:
        _CACHE[key] = (time.time(), val)
        if len(_CACHE) > 200:
            for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:100]:
                _CACHE.pop(k, None)


def clear_cache():
    with _CACHE_LOCK:
        _CACHE.clear()


# ------------------------------------------------------------------ التسجيل
def summary_for(G, period, scope, fresh=False):
    tz = _tz()
    win = rolling_window(period, _clock(), tz)
    key = ('summary', scope, period, win['from'].isoformat(), win['until'].isoformat())
    facts = None if fresh else _cache_get(key, SUMMARY_TTL)
    if facts is None:
        facts = collect(G, win, scope)
        _cache_put(key, facts)
    return build_payload(facts, scope, period)


def weekly_for(G, week_str=None):
    """⇒ (payload, خطأ). الأسبوع الافتراضي = آخر أسبوع مكتمل (أحد إلى سبت) بتوقيت القاهرة."""
    tz = _tz()
    now = _clock()
    local = now.astimezone(tz if tz is not None else datetime.timezone.utc)
    latest = latest_week_start(local.date())
    oldest = latest - datetime.timedelta(days=7 * (WEEKS_BACK - 1))
    if week_str:
        try:
            ws = datetime.date.fromisoformat(week_str)
        except Exception:
            return None, 'اختر أسبوعًا اكتمل'
        if ws.weekday() != 6 or ws > latest:
            return None, 'اختر أسبوعًا اكتمل'
        if ws < oldest:
            return None, 'أقدم أسبوع متاح: %s' % _date_text(oldest, True)
    else:
        ws = latest
    win = week_window(ws, now, tz)
    key = ('weekly', ws.isoformat())
    facts = _cache_get(key, WEEKLY_TTL)
    if facts is None:
        facts = collect(G, win, 'all', with_delivery=False)
        _cache_put(key, facts)
    facts = dict(facts)
    facts['delivery'] = read_delivery(G)
    p = build_payload(facts, 'all', 'week')
    p['week'] = {'start': ws.isoformat(), 'end': (ws + datetime.timedelta(days=6)).isoformat(), 'label': win['label']}
    p['nav'] = {'prev': (ws - datetime.timedelta(days=7)).isoformat() if ws - datetime.timedelta(days=7) >= oldest else None,
                'next': (ws + datetime.timedelta(days=7)).isoformat() if ws + datetime.timedelta(days=7) <= latest else None}
    p['text'] = weekly_text(p)
    return p, None


def register(app, G):
    # ⛔ G هو قاموس app.py الحيّ (ليس نسخة): الأسماء المعرّفة بعد استدعاء register، وما يعدّله الاختبار (السرّ مثلًا)، تُقرأ وقت الطلب.
    token_required = G['token_required']
    roles_required = G['roles_required']
    closed = G['_v2_closed']
    ns = G['_v2_ns']

    def err(msg, code):
        return ns((jsonify({'error': msg}), code))

    @app.route('/api/v2/reports/summary', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2r_summary():
        c = closed()
        if c:
            return c
        period = (request.args.get('period') or 'month').strip()
        scope = (request.args.get('scope') or 'all').strip()
        if period not in PERIOD_DAYS:
            return err('فترة غير معروفة', 400)
        if scope not in SCOPES:
            return err('قسم غير معروف', 400)
        fresh = (request.args.get('fresh') or '').strip() in ('1', 'true')
        return ns(jsonify(summary_for(G, period, scope, fresh)))

    @app.route('/api/v2/reports/weekly', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2r_weekly():
        c = closed()
        if c:
            return c
        p, e = weekly_for(G, (request.args.get('week') or '').strip() or None)
        if e:
            return err(e, 400)
        return ns(jsonify(p))

    @app.route('/api/v2/reports/weekly/settings', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2r_weekly_settings():
        c = closed()
        if c:
            return c
        body = G['_v2_body']()
        bad = G['_v2_confirmed'](body)
        if bad:
            return bad
        en = body.get('enabled')
        if not isinstance(en, bool):
            return err('اختر تشغيل الإرسال أو إيقافه', 400)
        Setting, db = G['Setting'], G['db']
        row = db_get(G, SETTING_KEY)
        if en:
            if row is None:
                db.session.add(Setting(key=SETTING_KEY, value='1'))
            else:
                row.value = '1'
        elif row is not None:
            db.session.delete(row)
        db.session.commit()
        G['_audit']('reports.weekly_delivery', target='weekly', meta={'enabled': en})
        return ns(jsonify({'ok': True, 'delivery': {'setting': en, 'bridge': None, 'platform_enabled': None, 'last_sent_week': None}}))   # بلا نداء للمنصة: ما لم يُقرأ null

    @app.route('/api/v2/reports/weekly/send', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2r_weekly_send():
        c = closed()
        if c:
            return c
        body = G['_v2_body']()
        bad = G['_v2_confirmed'](body)
        if bad:
            return bad
        wk = body.get('week')
        p, e = weekly_for(G, wk.strip() if isinstance(wk, str) and wk.strip() else None)
        if e:
            return err(e, 400)
        resp = G['_v2_write']('POST', DELIVERY_PATH, {'week_start': p['week']['start'], 'text': p['text'], 'confirmed': True},
                              'reports.weekly_send', p['week']['start'], {'by': 'manual'})
        if isinstance(resp, tuple) and int(resp[1]) == 404:
            return ns((jsonify({'error': NA, 'na': True}), 404))
        return resp

    @app.route('/api/v2/reports/weekly/deliver', methods=['POST'])
    def v2r_weekly_deliver():
        sec = request.headers.get('X-ELP-Metrics-Secret', '')
        secret = G['PLATFORM_METRICS_SECRET']
        if not (secret and sec and secrets.compare_digest(sec, secret)):
            return ns((jsonify({'error': 'unauthorized'}), 401))
        c = closed()
        if c:
            return c
        row = db_get(G, SETTING_KEY)
        if not (row and (row.value or '') == '1'):
            return ns(jsonify({'sent': False, 'reason': 'off'}))
        p, e = weekly_for(G, None)
        if e:
            return err(e, 400)
        resp = G['_platform_proxy']('POST', DELIVERY_PATH, json_body={'week_start': p['week']['start'], 'text': p['text'], 'by': 'cron',
                                                                       'confirmed': True}, timeout=25)
        status, rb = _unpack(resp)
        if status == 404:
            return ns(jsonify({'sent': False, 'na': NA}))
        if status != 200:
            return ns((jsonify({'error': 'تعذّر إرسال التقرير'}), 502))
        rb = rb if isinstance(rb, dict) else {}
        G['_audit']('reports.weekly_cron', target=p['week']['start'], meta={'sent': bool(rb.get('sent')), 'already': bool(rb.get('already'))})
        return ns(jsonify({'sent': bool(rb.get('sent')), 'already': bool(rb.get('already'))}))
