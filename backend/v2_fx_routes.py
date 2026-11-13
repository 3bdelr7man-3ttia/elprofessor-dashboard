# -*- coding: utf-8 -*-
"""أسعار الصرف للتقارير بس — `GET /api/v2/money/rates` (r25).

قرار المؤسس: كل بلد بعملتها، ولا جمع بين عملتين أبدًا. الرقم الوحيد المسموح بالدولار هو سطر «تقريبًا بالدولار» في تقارير الفلوس،
وده محتاج جدول أسعار صرف. الجدول بيتخزّن في `settings` (مفتاح `fx_rates_usd`) وبيتحدّث **مرة في اليوم على الأكتر** من مصدر عام مجاني
بلا مفتاح (`open.er-api.com`)، ولو التحديث فشل بنفضل على آخر أسعار سليمة ونعرض تاريخها. مفيش أسعار خالص ⇒ `rates: null` والواجهة تخفي السطر.

⛔ الأسعار دي للعرض التقريبي فقط: مفيش دفع ولا تسوية ولا تحويل بيعتمد عليها.
⛔ الاختبارات بتستبدل `fetch_rates` — مفيش نداء شبكة وقت التطوير.
"""
import datetime
import json

RATES_URL = 'https://open.er-api.com/v6/latest/USD'
SETTING_KEY = 'fx_rates_usd'
REFRESH_HOURS = 24
FETCH_TIMEOUT = 6
# العملات اللي اللوحة بتتعامل معاها (مصر + الخليج + الدولار + احتياطي)
KEEP = ('USD', 'EGP', 'SAR', 'AED', 'KWD', 'QAR', 'OMR', 'BHD', 'EUR', 'GBP')


def fetch_rates():
    """نداء واحد للمصدر العام. بيرجّع `{'rates': {...}, 'date': 'YYYY-MM-DD'}` أو بيرفع استثناء (والمنادي بيكمل على آخر أسعار سليمة)."""
    import requests
    r = requests.get(RATES_URL, timeout=FETCH_TIMEOUT)
    r.raise_for_status()
    body = r.json()
    if body.get('result') != 'success' or not isinstance(body.get('rates'), dict):
        raise ValueError('رد أسعار الصرف غير صالح')
    stamp = body.get('time_last_update_unix')
    day = datetime.datetime.utcfromtimestamp(stamp).date().isoformat() if isinstance(stamp, (int, float)) else datetime.datetime.utcnow().date().isoformat()
    return {'rates': body['rates'], 'date': day}


def clean_rates(rates):
    """أسعار سليمة بس: عملة معروفة وقيمة موجبة محدودة. USD دايمًا ١."""
    out = {}
    if not isinstance(rates, dict):
        return out
    for cur in KEEP:
        try:
            v = float(rates.get(cur))
        except (TypeError, ValueError):
            continue
        if v > 0 and v < 1e9:
            out[cur] = round(v, 6)
    if out:
        out['USD'] = 1.0
    return out


def _load(Setting):
    row = Setting.query.get(SETTING_KEY)
    if not row or not row.value:
        return None
    try:
        data = json.loads(row.value)
    except (TypeError, ValueError):
        return None
    rates = clean_rates(data.get('rates'))
    if not rates.get('EGP'):
        return None
    return {'rates': rates, 'date': str(data.get('date') or ''), 'fetched_at': str(data.get('fetched_at') or '')}


def _age_hours(fetched_at, now):
    try:
        t = datetime.datetime.fromisoformat(fetched_at)
    except (TypeError, ValueError):
        return None
    return (now - t).total_seconds() / 3600.0


def current_rates(db, Setting, now=None, fetch=None):
    """الأسعار الحالية للعرض: `{'rates', 'date', 'stale'}` أو None لو مفيش أسعار أصلًا.
    بتحدّث لو آخر جلب أقدم من ٢٤ ساعة؛ فشل الجلب ⇒ آخر أسعار سليمة بعلامة `stale`، ولا بنكتب فوقها حاجة."""
    now = now or datetime.datetime.utcnow()
    fetch = fetch or fetch_rates
    cached = _load(Setting)
    age = _age_hours(cached['fetched_at'], now) if cached else None
    if cached and age is not None and age < REFRESH_HOURS:
        return {'rates': cached['rates'], 'date': cached['date'], 'stale': False}
    try:
        got = fetch()
        rates = clean_rates(got.get('rates'))
        if not rates.get('EGP'):
            raise ValueError('الأسعار ناقصة')
        payload = json.dumps({'rates': rates, 'date': str(got.get('date') or now.date().isoformat()), 'fetched_at': now.isoformat()}, ensure_ascii=False)
        row = Setting.query.get(SETTING_KEY)
        if row:
            row.value = payload
            row.updated_at = now
        else:
            db.session.add(Setting(key=SETTING_KEY, value=payload, updated_at=now))
        db.session.commit()
        return {'rates': rates, 'date': str(got.get('date') or now.date().isoformat()), 'stale': False}
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        if cached:
            return {'rates': cached['rates'], 'date': cached['date'], 'stale': True}
        return None


def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']

    @app.route('/api/v2/money/rates', methods=['GET'], endpoint='v2_money_rates')
    @token_required
    @roles_required('admin')
    def v2_money_rates():
        closed = g['_v2_closed']()
        if closed:
            return closed
        got = current_rates(g['db'], g['Setting'], fetch=g.get('_fx_fetch_override'))
        if not got:
            return g['_v2_ns'](jsonify({'rates': None, 'date': '', 'stale': False}))
        return g['_v2_ns'](jsonify(got))

    return app
