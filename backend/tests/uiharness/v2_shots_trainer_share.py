# -*- coding: utf-8 -*-
"""صور شاشة «نسبة المدرّب» (SPEC-C-courses C2b) — داخل تبويب «المدرّبون» في قسم الدورات.

    cd backend && python3 -B tests/uiharness/v2_shots_trainer_share.py [out_dir]

كمبيوتر ١٤٤٠ (`d`) وموبايل ٣٩٠ (`m`). ثماني لقطات كحد أقصى: 01 القائمة وبطاقة القواعد · 02 ورقة التعديل (النصيب الحيّ والإعلانات والسجل) ·
03 ورقة التأكيد · 04 (كمبيوتر) الإعلانات «غير متاح بعد» داخل الورقة · 04 (موبايل) ورقة قواعد النسبة.

⛔ صفر شبكة وصفر منفذ: الداشبورد جوه العملية (`ef_route_harness`) والمنصة جدول في الذاكرة (`SharePlatform`) يرد على
`/api/bridge/trainer-share*` و`/api/bridge/ads-ledger`، فالمسارات الحقيقية `/api/v2/trainer-share*` هي اللي تُجرَّب.

السكربت بيفشل لو: تمرير أفقي · هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · رقم أو حرف لاتيني ظاهر خارج البريد · صفر/null/NaN/undefined ظاهر ·
لفظ ممنوع (يقوّم · استرداد · ضمان) · النصيب الحيّ لا يطابق المعادلة · كتابة بلا `confirmed:true` أو على مسار غير مسارات النسبة ·
حفظ بجسم غير المتوقع · فشل مصدر لا يظهر «غير متاح بعد».
"""
import copy
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'docs', 'v2', 'trainer-share-shots'))
os.makedirs(OUT, exist_ok=True)
sys.argv = [sys.argv[0], OUT]
sys.path.insert(0, _HERE)

import v2_shots as vs                       # noqa: E402
import courses_fixtures as cf               # noqa: E402
from ef_route_harness import Harness, DASH  # noqa: E402

vs.OUT = OUT
PROBLEMS = vs.PROBLEMS
DESK = {'width': 1440, 'height': 1300}
MOB = {'width': 390, 'height': 1700}
TODAY = datetime.date.today()
FROM = (TODAY - datetime.timedelta(days=5)).isoformat()
UNTIL = (TODAY + datetime.timedelta(days=20)).isoformat()
ADMIN_EMAIL = 'admin@example.test'


def _row(email, name, base, bonus, reason, frm='', until=''):
    return {'email': email, 'name': name, 'base_pct': base, 'ads_bonus_pts': bonus, 'reason': reason, 'from': frm, 'until': until,
            'updated_at': TODAY.isoformat() + 'T09:00:00', 'updated_by': 'founder@example.test'}


class SharePlatform(cf.CoursesPlatform):
    """جسور النسبة في الذاكرة بنفس قواعد المنصة (٣٥–٦٥ صحيحة · ٠–٢٥ · سبب ٣ حروف)، وكل كتابة تُسجَّل في `ts_writes`."""

    def __init__(self, **kw):
        super(SharePlatform, self).__init__(with_abc=False, **kw)
        self.ts = [_row('hala@example.test', 'هالة منصور', 50, 5, 'إعلان ممول على دورتها', FROM, UNTIL),
                   _row('nadia@example.test', 'نادية فؤاد', 35, 0, ''),
                   _row('karim@example.test', 'كريم عادل', 60, 0, 'اتفاق خاص'),
                   _row('rana@example.test', 'رنا سمير', 45, 10, 'حملة الخريف', FROM, UNTIL)]
        self.hist = {'hala@example.test': [
            {'base_pct': 40, 'ads_bonus_pts': 0, 'reason': 'بداية التعاقد', 'from': '', 'until': '', 'at': (TODAY - datetime.timedelta(days=60)).isoformat() + 'T09:00:00', 'by': 'founder@example.test'},
            {'base_pct': 50, 'ads_bonus_pts': 5, 'reason': 'إعلان ممول على دورتها', 'from': FROM, 'until': UNTIL, 'at': (TODAY - datetime.timedelta(days=5)).isoformat() + 'T09:00:00', 'by': 'founder@example.test'}]}
        self.rules = {'code_min_pct': 50, 'cap_pct': 65, 'rev': 2, 'updated_at': TODAY.isoformat() + 'T08:00:00', 'updated_by': 'founder@example.test'}
        self.ts_writes = []
        self.ts_closed = False          # الجسر لسه ما اتنشرش ⇒ ٤٠٤
        self.ts_forced = None           # (status, body) يُفرض على كتابة النسبة مرة واحدة
        self.ads = copy.deepcopy(self.ads) + [
            {'owner_kind': 'course', 'owner_id': 'seo-for-firms', 'balance': [{'currency': 'EGP', 'amount': 1200.0}], 'last_entry_at': TODAY.isoformat() + 'T08:00:00',
             'owner_email': 'hala@example.test', 'entries': 3, 'title': 'التسويق لمكاتب المحاماة'}]

    def _route(self, method, path, params, body):
        if path.startswith('/api/bridge/trainer-share'):
            if self.ts_closed:
                return 404, {'detail': 'Not Found'}
            if path in self.down:
                return 502, {'detail': 'تعذر الاتصال'}
            return self._share(method.upper(), path, body or {})
        return super(SharePlatform, self)._route(method, path, params, body)

    def _share(self, method, path, body):
        if path == '/api/bridge/trainer-share' and method == 'GET':
            return 200, {'items': copy.deepcopy(self.ts)}
        if path == '/api/bridge/trainer-share-rules':
            if method == 'GET':
                return 200, copy.deepcopy(self.rules)
            self.ts_writes.append((method, path, copy.deepcopy(body)))
            cm = body.get('code_min_pct')
            if body.get('confirmed') is not True or not isinstance(cm, int) or not 35 <= cm <= 65 or len(str(body.get('reason') or '').strip()) < 3:
                return 400, {'detail': 'بيانات القواعد غير صالحة'}
            self.rules.update(code_min_pct=cm, rev=self.rules['rev'] + 1)
            return 200, {'ok': True, **self.rules}
        m = re.match(r'^/api/bridge/trainer-share/(.+)$', path)
        if not m:
            return 404, {'detail': 'x'}
        email = m.group(1).replace('%40', '@')
        row = next((r for r in self.ts if r['email'] == email), None)
        if row is None:
            return 404, {'detail': 'هذا المدرّب غير معتمد'}
        if method == 'GET':
            return 200, dict(row, limits={'min': 35, 'max': 65, 'ads_bonus_max': 25}, history=copy.deepcopy(self.hist.get(email, [])))
        self.ts_writes.append((method, path, copy.deepcopy(body)))
        if self.ts_forced:
            out, self.ts_forced = self.ts_forced, None
            return out
        if body.get('confirmed') is not True or not body.get('by'):
            return 400, {'detail': 'لازم تأكيد صريح'}
        row.update(base_pct=body['base_pct'], ads_bonus_pts=body['ads_bonus_pts'], reason=body['reason'], updated_by=body['by'])
        row['from'], row['until'] = body.get('from', ''), body.get('until', '')
        self.hist.setdefault(email, []).append({'base_pct': row['base_pct'], 'ads_bonus_pts': row['ads_bonus_pts'], 'reason': row['reason'], 'from': row['from'],
                                                'until': row['until'], 'at': TODAY.isoformat() + 'T12:00:00', 'by': body['by']})
        return 200, {'ok': True, **row}


READY = "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2co[data-screen=\"trainers\"]') && !!document.querySelector('[data-ts-host]')"
LIST_READY = "() => document.querySelectorAll('[data-ts-host] .v2ts-row').length > 0 || /غير متاح بعد|لا مدرّبين/.test((document.querySelector('[data-ts-host] [data-ts-card=\"list\"]')||{}).innerText || '')"
BAD_WORDS = ('يقوّم', 'استرداد', 'ضمان', 'اعكس', 'مزايدة')


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def ts_check(page, name):
    w = page.viewport_size['width']
    mobile = w <= 400
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    inner = page.evaluate("""() => [...document.querySelectorAll('.v2ts *, #epModal .v2ts-m *')].filter(e => e.offsetParent && !['INPUT','TEXTAREA','IMG'].includes(e.tagName)
      && e.scrollWidth > e.clientWidth + 1 && !['hidden','clip'].includes(getComputedStyle(e).overflowX) && getComputedStyle(e).display !== 'inline')
      .map(e => e.className.toString().slice(0, 40)).slice(0, 5)""")
    if inner:
        PROBLEMS.append('%s: تمرير أفقي جوه عناصر: %r' % (name, inner))
    out = page.evaluate("() => [...document.querySelectorAll('.v2ts *, #epModal .v2ts-m *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
    if out:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, out))
    small = page.evaluate("""(min) => [...document.querySelectorAll('.v2ts button, #epModal .v2ts-m button, #epModal .v2ts-m input:not([type=hidden]), #epModal .v2ts-m textarea')]
      .filter(b => b.offsetParent && !b.disabled).map(b => [(b.className || b.id || b.tagName).toString().slice(0, 24), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < min)""", 44)
    if small:
        PROBLEMS.append('%s: أهداف أقل من %d px: %r' % (name, 44, small[:4]))
    txt = page.evaluate("""() => [...document.querySelectorAll('.v2ts, #epModal .v2ts-m')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('[dir="ltr"], script, style, input, textarea, time').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN/undefined ظاهر' % name)
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    if re.search(r'[A-Za-z]', txt):
        PROBLEMS.append('%s: حروف لاتينية ظاهرة: %r' % (name, re.findall(r'.{0,8}[A-Za-z]+.{0,8}', txt)[:2]))
    for word in BAD_WORDS:
        if word in txt:
            PROBLEMS.append('%s: لفظ ممنوع «%s»' % (name, word))
    return txt


def shot(page, name):
    page.wait_for_timeout(250)
    path = os.path.join(OUT, name)
    page.screenshot(path=path, type='jpeg', quality=70)
    vs.SHOTS.append(name)


def open_page(ctx):
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح %s' % d.type), d.dismiss()))
    reqs = []
    page.on('request', lambda r: reqs.append((r.method, re.sub(r'^https?://[^/]+', '', r.url), r.post_data)) if r.method != 'GET' and '/api/' in r.url else None)
    page.goto(DASH + '/#s/courses/trainers', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_function(LIST_READY, timeout=30000)
    page.wait_for_timeout(500)
    return page, reqs


def scroll_to_ts(page):
    page.evaluate("() => { const e = document.querySelector('[data-ts-host]'); if (e) e.scrollIntoView({block: 'start'}); }")
    page.wait_for_timeout(200)


def sheet_ready(page):
    page.wait_for_selector('#epModal .v2ts-m', timeout=10000)
    page.wait_for_function("() => !/جارٍ جلب/.test(document.querySelector('#epModal').innerText)", timeout=15000)
    page.wait_for_timeout(250)


def close_sheet(page):
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
    page.wait_for_timeout(120)


def writes_ok(reqs, name):
    for method, path, body in reqs:
        if not path.startswith('/api/v2/trainer-share'):
            PROBLEMS.append('%s: كتابة على مسار غير مسارات النسبة: %s %s' % (name, method, path))
            continue
        try:
            b = json.loads(body or '{}')
        except Exception:
            b = {}
        if method != 'PUT' or b.get('confirmed') is not True:
            PROBLEMS.append('%s: كتابة بلا confirmed:true أو بفعل غير PUT على %s' % (name, path))
        for banned in ('by', 'cap_pct', 'price_egp', 'trainer_share_pct'):
            if banned in b:
                PROBLEMS.append('%s: حقل ممنوع «%s» في جسم الكتابة' % (name, banned))


def flow(browser, h, pre, vp, mobile):
    ef = h.ef = SharePlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page, reqs = open_page(ctx)
    n = pre
    # —— ٠١) القائمة وبطاقة القواعد
    scroll_to_ts(page)
    info = page.evaluate("""() => ({rows: [...document.querySelectorAll('[data-ts-host] .v2ts-row')].map(r => r.innerText.replace(/\\s+/g, ' ').trim()),
      rules: (document.querySelector('[data-ts-card="rules"]')||{}).innerText || '', title: (document.querySelector('[data-ts-host] h2')||{}).innerText})""")
    expect(info['title'] == 'نسبة المدرّب' and len(info['rows']) == 4, '%s01: القائمة %r' % (n, info['rows']))
    expect('الأساسية ٥٠٪' in info['rows'][0] and 'زيادة الإعلانات +٥' in info['rows'][0] and 'إعلان ممول' in info['rows'][0], '%s01: صف هالة %r' % (n, info['rows'][:1]))
    expect('بلا زيادة' in info['rows'][1] and 'الأساسية ٣٥٪' in info['rows'][1], '%s01: صف نادية %r' % (n, info['rows'][1:2]))
    expect('٥٠٪' in info['rules'] and '٦٥٪' in info['rules'] and 'ثابت' in info['rules'] and 'الحد الأدنى مع كود المدرّب' in info['rules'], '%s01: بطاقة القواعد %r' % (n, info['rules']))
    ts_check(page, n + '01')
    shot(page, n + '01-list.jpg')
    # —— ٠٢) ورقة التعديل: النصيب الحيّ بالمعادلة، والإعلانات من دفتر الإعلانات الموجود، والسجل
    page.click('[data-ts="edit"][data-email="hala@example.test"]')
    sheet_ready(page)
    t = page.inner_text('#ts_total')
    expect('نصيب المدرّب الآن: ٥٥٪ · المنصة ٤٥٪' in t, '%s02: النصيب الحيّ %r' % (n, t))
    expect('مع بيع بكود المدرّب' in t and 'نصيبه ٥٥٪ · المنصة ٤٥٪' in t, '%s02: سطر الكود %r' % (n, t))
    ads = page.inner_text('#ts_ads')
    expect('رصيد إعلانات المدرّب الآن' in ads and 'مصر' in ads and 'السعودية' in ads and 'مبيعات' not in ads.replace('المبيعات', '') and 'غير متاح بعد' in ads,
           '%s02: الإعلانات %r' % (n, ads))
    hist = page.inner_text('#ts_hist')
    expect('بداية التعاقد' in hist and 'إعلان ممول على دورتها' in hist, '%s02: السجل %r' % (n, hist))
    page.fill('#ts_base', '٦٠')
    page.fill('#ts_bonus', '٢٠')
    t = page.inner_text('#ts_total')
    expect('نصيب المدرّب الآن: ٦٥٪ · المنصة ٣٥٪' in t, '%s02: السقف ٦٥ %r' % (n, t))
    page.fill('#ts_base', '٤٠')
    page.fill('#ts_bonus', '٣٠')
    page.click('#ts_next')                                         # زيادة ٣٠ مرفوضة
    expect(page.inner_text('[data-err="ts_bonus"]') != '' and not reqs, '%s02: زيادة فوق ٢٥ لازم تتمنع بلا نداء' % n)
    page.fill('#ts_base', '٥٥')
    page.fill('#ts_bonus', '١٠')
    page.fill('#ts_from', FROM)
    page.fill('#ts_until', UNTIL)
    t = page.inner_text('#ts_total')
    expect('نصيب المدرّب الآن: ٦٥٪ · المنصة ٣٥٪' in t, '%s02: ٥٥ + ١٠ %r' % (n, t))
    page.fill('#ts_base', '٥٥')
    page.fill('#ts_bonus', '٥')
    page.click('#ts_next')                                         # السبب فاضي
    expect('اكتب السبب' in page.inner_text('[data-err="ts_reason"]') and not reqs and not ef.ts_writes, '%s02: السبب لازم يمنع المتابعة بلا نداء' % n)
    page.fill('#ts_reason', 'رفع النسبة بسبب إعلان ممول')
    page.evaluate("() => { const s = document.querySelector('#epModal .mb'); if (s) s.scrollTop = 0; }")
    ts_check(page, n + '02')
    shot(page, n + '02-sheet.jpg')
    # —— ٠٣) التأكيد قبل الكتابة
    page.click('#ts_next')
    page.wait_for_selector('#ts_go')
    ctext = page.inner_text('#epModal .v2ts-stage')
    expect('الأساسية لـ«هالة منصور»: ٥٥٪' in ctext.replace('النسبة ', '') or '٥٥٪' in ctext, '%s03: ورقة التأكيد %r' % (n, ctext))
    expect('نصيب المدرّب الآن: ٦٠٪ · المنصة ٤٠٪' in ctext and 'يسري على المبيعات الجديدة فقط' in ctext and 'رفع النسبة بسبب إعلان ممول' in ctext, '%s03: ورقة التأكيد %r' % (n, ctext))
    expect(not ef.ts_writes and not reqs, '%s03: لا كتابة قبل الضغط على «أكّد الحفظ»' % n)
    ts_check(page, n + '03')
    shot(page, n + '03-confirm.jpg')
    # رجوع يحفظ ما كُتب، ثم فشل بنص المنصة العربي يبقي الورقة مفتوحة
    page.click('#ts_back')
    expect(page.input_value('#ts_reason') == 'رفع النسبة بسبب إعلان ممول', '%s03: الرجوع يضيّع السبب' % n)
    page.click('#ts_next')
    page.wait_for_selector('#ts_go')
    ef.ts_forced = (400, {'detail': 'الزيادة المسجّلة تتجاوز الحد المسموح'})
    page.click('#ts_go')
    page.wait_for_selector('.v2ts-errbox')
    expect('الزيادة المسجّلة تتجاوز الحد المسموح' in page.inner_text('.v2ts-errbox') and page.query_selector('#ts_go') is not None, '%s03: نص المنصة لازم يظهر والورقة تبقى' % n)
    # الحفظ الفعلي
    page.click('#ts_go')
    page.wait_for_function("() => !document.getElementById('epModal') && /تم حفظ نسبة/.test(document.querySelector('[data-ts-host]').innerText)", timeout=15000)
    page.wait_for_function("() => /الأساسية ٥٥٪/.test(document.querySelector('[data-ts-host]').innerText)", timeout=15000)
    last = ef.ts_writes[-1]
    expect(last[0] == 'PUT' and last[1] == '/api/bridge/trainer-share/hala%40example.test' and last[2].get('confirmed') is True and last[2].get('by') and
           {k: last[2].get(k) for k in ('base_pct', 'ads_bonus_pts', 'reason', 'from', 'until')} == {'base_pct': 55, 'ads_bonus_pts': 5, 'reason': 'رفع النسبة بسبب إعلان ممول', 'from': FROM, 'until': UNTIL},
           '%s03: جسم الحفظ على المنصة %r' % (n, last))
    expect(len([w for w in ef.ts_writes if w[0] == 'PUT']) == 2, '%s03: نداءان بالظبط (المرفوض والناجح)' % n)
    writes_ok(reqs, n + '03')
    ts_check(page, n + '03b')
    # —— ٠٤) قواعد النسبة (موبايل: لقطة) — الحد الأدنى مع الكود
    reqs.clear()
    page.click('[data-ts="rules"]')
    page.wait_for_selector('#tr_min')
    rtext = page.inner_text('#epModal .v2ts-stage')
    expect('السقف' in rtext and '٦٥٪' in rtext and 'ثابت ولا يُعدَّل من هنا' in rtext and not page.query_selector('#tr_cap'), '%s04: السقف لازم يكون قراءة فقط %r' % (n, rtext))
    page.fill('#tr_min', '٧٠')
    page.fill('#tr_reason', 'سبب')
    page.click('#tr_next')
    expect('بين ٣٥ و٦٥' in page.inner_text('[data-err="tr_min"]') and not reqs, '%s04: حد أدنى فوق ٦٥ لازم يتمنع' % n)
    page.fill('#tr_min', '٥٥')
    ts_check(page, n + '04')
    if mobile:
        shot(page, n + '04-rules.jpg')
    page.click('#tr_next')
    page.wait_for_selector('#tr_go')
    page.click('#tr_go')
    page.wait_for_function("() => !document.getElementById('epModal') && /٥٥٪/.test(document.querySelector('[data-ts-card=\"rules\"]').innerText)", timeout=15000)
    expect(ef.rules['code_min_pct'] == 55, '%s04: الحد الأدنى ما اتحفظش' % n)
    expect(ef.ts_writes[-1][2].get('confirmed') is True and 'cap_pct' not in ef.ts_writes[-1][2], '%s04: جسم القواعد %r' % (n, ef.ts_writes[-1]))
    writes_ok(reqs, n + '04')
    # —— ٠٥) مصدر الإعلانات يفشل لوحده: «غير متاح بعد» داخل الورقة، والباقي يعمل
    ef.down = {'/api/bridge/ads-ledger'}
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_function(LIST_READY, timeout=30000)
    page.click('[data-ts="edit"][data-email="karim@example.test"]')
    sheet_ready(page)
    ads = page.inner_text('#ts_ads')
    expect(ads.count('غير متاح بعد') == 2 and 'إيداعات الإعلانات: غير متاح بعد' in ads and 'المبيعات قبل الإيداع وبعده: غير متاح بعد' in ads, '%s05: الإعلانات لازم تكتب «غير متاح بعد» %r' % (n, ads))
    expect('نصيب المدرّب الآن: ٦٠٪ · المنصة ٤٠٪' in page.inner_text('#ts_total'), '%s05: النصيب لا يتأثر بفشل الإعلانات' % n)
    ts_check(page, n + '05')
    if not mobile:
        shot(page, n + '04-ads-unavailable.jpg')
    close_sheet(page)
    # —— ٠٦) الجسر لسه ما اتنشرش: القائمة والقواعد «غير متاح بعد» بلا أرقام مخترعة
    ef.down = set()
    ef.ts_closed = True
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_function(LIST_READY, timeout=30000)
    page.wait_for_timeout(400)
    closed = page.inner_text('[data-ts-host]')
    expect(closed.count('غير متاح بعد') >= 2 and '٥٥٪' not in closed and not page.query_selector('[data-ts-host] .v2ts-row'), '%s06: الجسر المقفول لازم يكتب «غير متاح بعد» %r' % (n, closed))
    ts_check(page, n + '06')
    expect(not [r for r in reqs if r[0] != 'PUT'], '%s06: كتابات غريبة %r' % (n, reqs))
    page.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(SharePlatform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', DESK, False), ('m', MOB, True)):
                try:
                    flow(browser, h, pre, vp, mobile)
                except Exception as e:
                    import traceback
                    traceback.print_exc(limit=5)
                    PROBLEMS.append('%s: استثناء %s' % (pre, str(e).split(chr(10))[0][:240]))
                    browser.close()
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
