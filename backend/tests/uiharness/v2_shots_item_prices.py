# -*- coding: utf-8 -*-
"""لقطات «سعر خاص لكل دليل» في «الفلوس ‹ الأسعار» — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٤٣٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_item_prices.py ../docs/v2/item-prices/shots [only-prefix,...]

اللقطات: ٠١ القائمة (الكل) · ٠٢ شريحة الأدلّة · ٠٣ بحث · ٠٣ب لا نتيجة · ٠٤ دليل يأخذ السعر العام (النموذج) · ٠٥ سعر خاص لدليل (نموذج ⇒ قبل ⇒ بعد ⇒ النتيجة) ·
٠٦ «ارجع للسعر العام» (المراجعة ⇒ النتيجة) · ٠٧ صف السعر العام (نموذج ⇒ قبل ⇒ بعد ⇒ النتيجة) · ٠٨ تعديل كتاب كما كان (نموذج ⇒ قبل ⇒ بعد) ·
٠٩ فاضي · ١٠ المصدر واقع · ١١ المتجر مقفول.

السكربت بيفشل (exit 1) لو: هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · خانة أقل من ٤٨px أو خطها أقل من ١٦px · تمرير أفقي (كمبيوتر وموبايل) ·
رقم لاتيني ظاهر في النص العربي · «·» جنب رقم · كلمة ممنوعة · «٠/null/NaN/undefined» ظاهرة · أي كتابة وصلت المنصة قبل ضغطة التأكيد أو غير
الكتابة المتوقعة · أي طلب خرج من العملية غير خطوط جوجل.
⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة (`item_prices_fixtures.ItemPricesPlatform`).
"""
import json
import os
os.environ.setdefault('DASH_SCHEDULER', '0')   # R16: مراقبة التشغيل/الملخص اليومي ما يشتغلوش جوّه الأداة (كانوا بيبعتوا تليجرام عبر الجسر المزيّف)
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                            # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import v2_fixtures as v2fx                       # noqa: E402
import d3_fixtures as d3fx                       # noqa: E402
import item_prices_fixtures as ipfx              # noqa: E402
from ef_route_harness import Harness, DASH       # noqa: E402

PROBLEMS = vs.PROBLEMS
DESK = {'width': 1440, 'height': 900}
MOB = {'width': 430, 'height': 932}
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
BANNED = ('يقوّم', 'API', 'JSON', 'HTTP', 'DELETE', 'bridge', 'confirmed', 'endpoint', 'rev ', 'سيرفر', 'استعلام', 'قاعدة بيانات')
READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v3[data-board=\"prices\"]')"
         " && !/…جارٍ جلب/.test(document.querySelector('.v3').innerText)")


def want(code):
    return not ONLY or any(code.startswith(o) or o.startswith(code) for o in ONLY)


def writes(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE')]


def ip_check(page, name):
    """فحوص هذه الشاشة فوق فحوص D3: خانات ≥٤٨px وخط ≥١٦px · تمرير أفقي في الحجمين · «·» جنب رقم · كلمات ممنوعة."""
    w = page.viewport_size['width']
    boxes = page.evaluate("""() => [...document.querySelectorAll('.v3 input:not([type=checkbox]), .v3 textarea, #epModal input:not([type=checkbox]), #epModal textarea, #epModal select')]
      .filter(b => b.offsetParent).map(b => [b.id || b.className || b.tagName, Math.round(b.getBoundingClientRect().height), parseFloat(getComputedStyle(b).fontSize), b.tagName])""")
    for ident, h, fs, tag in boxes:
        if fs < 16 or (tag != 'TEXTAREA' and h < (52 if w <= 400 else 48)) or (tag == 'TEXTAREA' and h < 48):
            if w <= 460 and fs >= 16 and h >= 48 and tag != 'TEXTAREA':
                continue
            PROBLEMS.append('%s: خانة %s ارتفاعها %s وخطها %s' % (name, ident, h, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, sw, w))
    wide = page.evaluate("() => [...document.querySelectorAll('.v3 *, #epModal .v3m *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
    if wide:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    if w <= 460:
        small = page.evaluate("""() => [...document.querySelectorAll('.v3-btn1, .v3-btn2, .v3-chip, #epModal .v3m .btn')]
          .filter(b => b.offsetParent).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
        if small:
            PROBLEMS.append('%s: أزرار أقل من ٤٤px في الموبايل: %r' % (name, small[:4]))
    txt = page.evaluate("() => [...document.querySelectorAll('.v3, #epModal .v3m')].map(e => e.innerText).join('\\n')")
    if re.search(r'[٠-٩]\s*[·•]|[·•]\s*[٠-٩]', txt):
        PROBLEMS.append('%s: «·» جنب رقم: %r' % (name, re.findall(r'.{0,12}(?:[٠-٩]\s*[·•]|[·•]\s*[٠-٩]).{0,12}', txt)[:2]))
    for bad in BANNED:
        if bad in txt:
            PROBLEMS.append('%s: كلمة ممنوعة «%s»' % (name, bad))
    ar = re.sub(r'[A-Za-z]+', '', re.sub(r'[٠-٩]', '', txt))
    if re.search(r'\d', ar):
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, re.findall(r'\S*\d\S*', ar)[:3]))


def ishot(page, name):
    vs.d3_shot(page, name)
    ip_check(page, name)


def iopen(browser, h, ef, viewport, mobile):
    h.ef = ef
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/money/prices', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(500)
    return page


def rows(page):
    return page.evaluate("""() => [...document.querySelectorAll('.v3[data-board="prices"] .v3-psec')].map(s => ({key: s.getAttribute('data-sec'),
      title: (s.querySelector('h3') || {}).textContent, rows: [...s.querySelectorAll('.v3-pr')].map(r => ({id: r.getAttribute('data-id'),
      title: r.querySelector('b').textContent, badge: (r.querySelector('.v3-own') || {}).textContent || '',
      btns: [...r.querySelectorAll('button')].map(b => b.textContent.trim()), mins: r.querySelector('.v3-mins').textContent}))}))""")


def row_btn(page, rid, action):
    return page.locator('.v3[data-board="prices"] .v3-pr[data-id="%s"] [data-a="%s"]' % (rid, action))


def fail(msg):
    PROBLEMS.append(msg)


def check_one_write(name, h, since, method, path_re, check=None):
    got = writes(h, since)
    if len(got) != 1 or got[0][0] != method or not re.match(path_re, got[0][1]):
        fail('%s: الكتابة المتوقعة %s %s فجاءت %r' % (name, method, path_re, [(m, p) for m, p, _q, _b in got]))
        return None
    body = got[0][3] or {}
    if body.get('confirmed') is not True:
        fail('%s: الكتابة بلا confirmed:true' % name)
    if check:
        msg = check(body)
        if msg:
            fail('%s: %s' % (name, msg))
    return body


def flow(browser, h, pre, viewport, mobile):
    tall = dict(viewport, height=viewport['height'] if mobile else 1500)

    # —— ٠١ القائمة ثم الأدلّة ثم البحث
    if want(pre + '0'):
        n_start = len(h.platform_calls)
        page = iopen(browser, h, ipfx.ItemPricesPlatform(d2=True), tall, mobile)
        secs = rows(page)
        if [s['key'] for s in secs] != ['book', 'general', 'guide'] or [len(s['rows']) for s in secs] != [4, 1, 5]:
            fail('%s01: المجموعات %r' % (pre, [(s['key'], len(s['rows'])) for s in secs]))
        g = {r['id']: r for s in secs for r in s['rows']}
        if g['guide-rent']['badge'] != 'سعر خاص' or g['guide-sole']['badge'] != 'يأخذ السعر العام':
            fail('%s01: الشارتان %r' % (pre, [g['guide-rent']['badge'], g['guide-sole']['badge']]))
        if 'عدّل' not in g['guide-sole']['btns'] or 'ارجع للسعر العام' in g['guide-sole']['btns']:
            fail('%s01: أزرار دليل يأخذ العام %r' % (pre, g['guide-sole']['btns']))
        if 'ارجع للسعر العام' not in g['guide-rent']['btns']:
            fail('%s01: دليل بسعر خاص بلا «ارجع للسعر العام»: %r' % (pre, g['guide-rent']['btns']))
        if g['guide-sole']['mins'] != g['_guides']['mins']:
            fail('%s01: أقل سعر فعلي لدليل يأخذ العام %r' % (pre, g['guide-sole']['mins']))
        if g['_guides']['title'] != 'السعر العام للأدلّة' or [r for r in g if r.startswith('bk-')] == []:
            fail('%s01: صف العام أو الكتب ناقص' % pre)
        chips = page.evaluate("() => [...document.querySelectorAll('.v3-chip')].map(c => [c.textContent.replace(/\\s+/g, ' ').trim(), c.getAttribute('aria-pressed')])")
        if [c[0].split(' ')[0] for c in chips] != ['الكل', 'الكتب', 'الأدلّة'] or chips[0][1] != 'true':
            fail('%s01: الشرائح %r' % (pre, chips))
        ishot(page, pre + '01-list.jpg')
        page.click('.v3-chip[data-g="guide"]')
        page.wait_for_timeout(250)
        secs = rows(page)
        if [s['key'] for s in secs] != ['general', 'guide']:
            fail('%s02: شريحة الأدلّة %r' % (pre, [s['key'] for s in secs]))
        ishot(page, pre + '02-guides-chip.jpg')
        page.click('.v3-chip[data-g="book"]')
        page.wait_for_timeout(250)
        if [s['key'] for s in rows(page)] != ['book']:
            fail('%s02: شريحة الكتب' % pre)
        page.click('.v3-chip[data-g="all"]')
        page.fill('#v3_psearch', 'مواريث')
        page.wait_for_timeout(300)
        found = [r['id'] for s in rows(page) for r in s['rows']]
        if found != ['guide-heirs']:
            fail('%s03: نتيجة البحث %r' % (pre, found))
        ishot(page, pre + '03-search.jpg')
        page.fill('#v3_psearch', 'لا شيء بهذا الاسم')
        page.wait_for_timeout(300)
        if rows(page) or 'لا نتيجة' not in page.inner_text('.v3[data-board="prices"]'):
            fail('%s03b: لا نتيجة' % pre)
        ishot(page, pre + '03b-search-empty.jpg')
        if writes(h, n_start):
            fail('%s0x: كتابة أثناء التصفّح' % pre)
        browser.close()

    # —— ٠٤ دليل يأخذ السعر العام: النموذج
    if want(pre + '04'):
        page = iopen(browser, h, ipfx.ItemPricesPlatform(d2=True), tall, mobile)
        row_btn(page, 'guide-sole', 'price').click()
        page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
        txt = page.inner_text('#epModal')
        if 'يأخذ السعر العام' not in txt or page.locator('#v3_fromgen').count() != 1:
            fail('%s04: نص الدليل الذي يأخذ العام أو زر «ابدأ من السعر العام»: %r' % (pre, txt[:200]))
        if not page.is_checked('#v3_vis'):
            fail('%s04: «ظاهر للناس» لازم يبدأ من ظهور الدليل اليوم' % pre)
        if page.input_value('#epModal input[data-v="read"][data-c="eg"]') != '':
            fail('%s04: خانة مصر لازم تبدأ فاضية' % pre)
        ishot(page, pre + '04-guide-uses-general.jpg')
        page.click('#v3_fromgen')
        page.wait_for_timeout(300)
        if page.input_value('#epModal input[data-v="read"][data-c="eg"]') != '99':
            fail('%s04: «ابدأ من السعر العام» ما ملأش الخانات: %r' % (pre, page.input_value('#epModal input[data-v="read"][data-c="eg"]')))
        ishot(page, pre + '04b-from-general.jpg')
        browser.close()

    # —— ٠٥ سعر خاص لدليل: نموذج ⇒ قبل ⇒ بعد ⇒ النتيجة
    if want(pre + '05'):
        ef = ipfx.ItemPricesPlatform(d2=True)
        page = iopen(browser, h, ef, tall, mobile)
        row_btn(page, 'guide-sole', 'price').click()
        page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
        page.fill('#epModal input[data-v="read"][data-c="eg"]', '٢٢٠')
        page.fill('#epModal input[data-v="read"][data-c="default"]', '12')
        if page.locator('#epModal input[data-v="pdf"]').count():
            PROBLEMS.append(pre + '05a: محرّر الدليل فيه صف PDF والمنصة ترفضه')
        ishot(page, pre + '05a-guide-own-form.jpg')
        n0 = len(h.platform_calls)
        page.click('#v3_review')
        page.wait_for_selector('#epModal #v3_go')
        diff = page.inner_text('#epModal .v3-diff')
        for w in ('٢٢٠ جنيه', 'لا سعر', '١٢ دولار'):
            if w not in diff:
                fail('%s05: «%s» مش في فرق قبل⇒بعد: %r' % (pre, w, diff))
        if writes(h, n0):
            fail('%s05: كتابة قبل التأكيد' % pre)
        ishot(page, pre + '05b-guide-own-diff.jpg')
        page.click('#v3_go')
        page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
        check_one_write(pre + '05', h, n0, 'PUT', r'^/api/bridge/prices/book/guide-sole$',
                        lambda b: None if b.get('rev') == 0 and b['versions']['read']['eg'] == {'amount': 220, 'currency': 'EGP'} and b.get('visible') is True and b.get('by')
                        else 'جسم الكتابة %r' % b)
        page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
        page.wait_for_function("() => [...document.querySelectorAll('.v3-pr[data-id=\"guide-sole\"] .v3-own')].some(e => e.textContent.trim() === 'سعر خاص')", timeout=10000)
        if not row_btn(page, 'guide-sole', 'preset').count():
            fail('%s05: «ارجع للسعر العام» لم يظهر بعد الحفظ' % pre)
        ishot(page, pre + '05c-guide-own-result.jpg')
        browser.close()

    # —— ٠٦ «ارجع للسعر العام»
    if want(pre + '06'):
        ef = ipfx.ItemPricesPlatform(d2=True)
        page = iopen(browser, h, ef, tall, mobile)
        n0 = len(h.platform_calls)
        row_btn(page, 'guide-rent', 'preset').click()
        page.wait_for_selector('#epModal #v3_rgo')
        diff = page.inner_text('#epModal .v3-diff')
        for w in ('سعر خاص', 'السعر العام', '١٢٠ جنيه', '٩٩ جنيه'):
            if w not in diff:
                fail('%s06: «%s» مش في مراجعة الرجوع: %r' % (pre, w, diff))
        if writes(h, n0):
            fail('%s06: كتابة قبل التأكيد' % pre)
        page.fill('#v3_rnote', 'الدليل يأخذ سعر الأدلّة')
        ishot(page, pre + '06a-reset-review.jpg')
        page.click('#v3_rgo')
        page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
        check_one_write(pre + '06', h, n0, 'DELETE', r'^/api/bridge/prices/book/guide-rent$',
                        lambda b: None if b.get('note') == 'الدليل يأخذ سعر الأدلّة' and b.get('rev') == 1 and b.get('by') else 'جسم الحذف %r' % b)
        page.wait_for_function("() => [...document.querySelectorAll('.v3-pr[data-id=\"guide-rent\"] .v3-own')].some(e => e.textContent.trim() === 'يأخذ السعر العام')", timeout=10000)
        if row_btn(page, 'guide-rent', 'preset').count():
            fail('%s06: «ارجع للسعر العام» ما زال ظاهرًا' % pre)
        if 'guide-rent' in ef.guide_docs:
            fail('%s06: الوثيقة لم تُحذف' % pre)
        ishot(page, pre + '06b-reset-result.jpg')
        # الإلغاء ما يكتب
        page2 = iopen(browser, h, ipfx.ItemPricesPlatform(d2=True), tall, mobile)
        n1 = len(h.platform_calls)
        row_btn(page2, 'guide-heirs', 'preset').click()
        page2.wait_for_selector('#epModal #v3_rno')
        page2.click('#v3_rno')
        page2.wait_for_function("() => !document.getElementById('epModal')", timeout=5000)
        if writes(h, n1):
            fail('%s06: الإلغاء كتب' % pre)
        # رفض المنصة (نسخة قديمة) ⇒ الرسالة تظهر والورقة تبقى
        ef3 = ipfx.ItemPricesPlatform(d2=True)
        page3 = iopen(browser, h, ef3, tall, mobile)
        row_btn(page3, 'guide-rent', 'preset').click()
        page3.wait_for_selector('#epModal #v3_rgo')
        ef3.guide_docs['guide-rent']['rev'] = 9
        page3.click('#v3_rgo')
        page3.wait_for_selector('#epModal .v3-err')
        if 'اتعدّلت من مكان تاني' not in page3.inner_text('#epModal .v3-err') or not page3.locator('#v3_rgo').count():
            fail('%s06: رسالة رفض المنصة' % pre)
        ishot(page3, pre + '06c-reset-refused.jpg')
        browser.close()

    # —— ٠٧ صف السعر العام
    if want(pre + '07'):
        ef = ipfx.ItemPricesPlatform(d2=True)
        page = iopen(browser, h, ef, tall, mobile)
        row_btn(page, '_guides', 'price').click()
        page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
        if 'يُباع به كل دليل' not in page.inner_text('#epModal') or page.locator('#v3_fromgen').count():
            fail('%s07: نص السعر العام' % pre)
        page.fill('#epModal input[data-v="read"][data-c="eg"]', '١١٠')
        ishot(page, pre + '07a-general-form.jpg')
        n0 = len(h.platform_calls)
        page.click('#v3_review')
        page.wait_for_selector('#epModal #v3_go')
        diff = page.inner_text('#epModal .v3-diff')
        if '٩٩ جنيه' not in diff or '١١٠ جنيه' not in diff:
            fail('%s07: فرق السعر العام %r' % (pre, diff))
        ishot(page, pre + '07b-general-diff.jpg')
        page.click('#v3_go')
        page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
        check_one_write(pre + '07', h, n0, 'PUT', r'^/api/bridge/prices/book/_guides$',
                        lambda b: None if b['versions']['read']['eg'] == {'amount': 110, 'currency': 'EGP'} else 'جسم الكتابة %r' % b)
        page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
        ishot(page, pre + '07c-general-result.jpg')
        browser.close()

    # —— ٠٨ كتاب كما كان
    if want(pre + '08'):
        ef = ipfx.ItemPricesPlatform(d2=True)
        page = iopen(browser, h, ef, tall, mobile)
        if row_btn(page, 'bk-tenant-guide', 'preset').count():
            fail('%s08: الكتاب عليه «ارجع للسعر العام»' % pre)
        row_btn(page, 'bk-tenant-guide', 'price').click()
        page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
        if page.locator('#v3_fromgen').count() or 'يأخذ السعر العام' in page.inner_text('#epModal'):
            fail('%s08: نص الأدلّة ظهر في ورقة كتاب' % pre)
        ishot(page, pre + '08a-book-form.jpg')
        page.fill('#epModal input[data-v="read"][data-c="eg"]', '٢٥٠')
        page.uncheck('#v3_vis')
        page.click('#v3_review')
        page.wait_for_selector('#epModal #v3_go')
        diff = page.inner_text('#epModal .v3-diff')
        for w in ('١٥٠ جنيه', '٢٥٠ جنيه', 'ظاهر للناس'):
            if w not in diff:
                fail('%s08: «%s» مش في فرق قبل⇒بعد: %r' % (pre, w, diff))
        ishot(page, pre + '08b-book-diff.jpg')
        n0 = len(h.platform_calls)
        page.click('#v3_go')
        page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
        check_one_write(pre + '08', h, n0, 'PUT', r'^/api/bridge/prices/book/bk-tenant-guide$',
                        lambda b: None if b.get('visible') is False and b['versions']['read']['eg'] == {'amount': 250, 'currency': 'EGP'} else 'جسم الكتابة %r' % b)
        browser.close()

    # —— ٠٩ فاضي · ١٠ المصدر واقع · ١١ المتجر مقفول
    if want(pre + '09'):
        page = iopen(browser, h, ipfx.ItemPricesPlatform(empty=True, d2=True), tall, mobile)
        if 'لا أعمال بعد' not in page.inner_text('.v3[data-board="prices"]') or page.locator('#v3_psearch').count():
            fail('%s09: الفاضي' % pre)
        ishot(page, pre + '09-empty.jpg')
        browser.close()
    if want(pre + '10'):
        ef = ipfx.ItemPricesPlatform(d2=True)
        ef.down.add('/api/bridge/prices/book')
        h.ef = ef
        ctx = browser.context(h, 'admin', tall, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#s/money/prices', wait_until='domcontentloaded')
        page.wait_for_function(vs.SHELL_READY, timeout=30000)
        page.wait_for_function("() => document.querySelector('.v3[data-board=\"prices\"]') && /غير متاح بعد/.test(document.querySelector('.v3').innerText)", timeout=30000)
        page.wait_for_timeout(400)
        ishot(page, pre + '10-down.jpg')
        browser.close()
    if want(pre + '11'):
        ef = ipfx.ItemPricesPlatform(d2=True)
        ef.forced[('GET', '/api/bridge/prices/book')] = (404, {'detail': 'Not Found'})
        h.ef = ef
        ctx = browser.context(h, 'admin', tall, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#s/money/prices', wait_until='domcontentloaded')
        page.wait_for_function(vs.SHELL_READY, timeout=30000)
        page.wait_for_function("() => document.querySelector('.v3[data-board=\"prices\"]') && /لم يُفتح بعد/.test(document.querySelector('.v3').innerText)", timeout=30000)
        page.wait_for_timeout(400)
        ishot(page, pre + '11-closed.jpg')
        browser.close()

    # —— ١٢ حد البيع: «دليل قصير» بلا سعر + سطر «فوق الحد / تحت الحد» + نموذج الدليل القصير
    if want(pre + '12'):
        ef = ipfx.ItemPricesPlatform(d2=True, short_guides=('guide-labor', 'guide-trademark'), min_words=4000)
        page = iopen(browser, h, ef, tall, mobile)
        page.click('.v3-chip[data-g="guide"]')
        page.wait_for_timeout(250)
        g = {r['id']: r for s_ in rows(page) for r in s_['rows']}
        if g['guide-labor']['badge'] != 'دليل قصير' or 'يُقرأ كاملًا بلا سعر' not in g['guide-labor']['mins']:
            fail('%s12: الدليل القصير %r' % (pre, g['guide-labor']))
        if g['guide-sole']['badge'] != 'يأخذ السعر العام':
            fail('%s12: دليل فوق الحد %r' % (pre, g['guide-sole']['badge']))
        size = page.inner_text('.v3-size') if page.locator('.v3-size').count() else ''
        if 'حد البيع ٤٠٠٠ كلمة (نحو ١٥ صفحة)' not in size or 'فوق الحد ويُباع: ٣' not in size or 'بلا سعر: ٢' not in size:
            fail('%s12: سطر الحد %r' % (pre, size))
        ishot(page, pre + '12a-short-list.jpg')
        n0 = len(h.platform_calls)
        row_btn(page, 'guide-labor', 'price').click()
        page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
        txt = page.inner_text('#epModal')
        if 'أقصر من حد البيع' not in txt or page.locator('#v3_fromgen').count() != 0 or not page.is_checked('#v3_vis'):
            fail('%s12: نموذج الدليل القصير %r' % (pre, txt[:200]))
        if writes(h, n0):
            fail('%s12: كتابة قبل التأكيد' % pre)
        ishot(page, pre + '12b-short-form.jpg')
        browser.close()

    # —— ١٣ «الأسعار المبدئية»: البطاقة ⇒ ورقة المراجعة (لا كتابة) ⇒ أكّد ⇒ ٣ كتابات بالظبط ⇒ «مطبّقة»
    if want(pre + '13'):
        sellers = {'bk-tenant-guide': 'seed', 'bk-startup-law': 'ours', 'bk-labor': 'expert', 'bk-new': 'free'}
        page = iopen(browser, h, ipfx.ItemPricesPlatform(d2=True, sellers=sellers), tall, mobile)
        if page.locator('[data-a="starter"]').count() != 1:
            fail('%s13: زر الأسعار المبدئية مش ظاهر' % pre)
        ishot(page, pre + '13a-starter-card.jpg')
        n0 = len(h.platform_calls)
        page.click('[data-a="starter"]')
        page.wait_for_selector('#v3_sgo')
        txt = page.inner_text('#epModal')
        for must in ('السعر العام للأدلّة', 'دليل المستأجر في عقود الإيجار', 'قانون الشركات الناشئة', 'كتب الخبراء: ١', 'الكتب المجانية: ١'):
            if must not in txt:
                fail('%s13: ورقة المراجعة ناقصة «%s»' % (pre, must))
        if 'الوجيز في قانون العمل' in txt.split('العمل')[-1] and 'الوجيز في قانون العمل' in page.inner_text('#epModal table'):
            fail('%s13: كتاب الخبير في القايمة' % pre)
        if writes(h, n0):
            fail('%s13: كتابة قبل «أكّد التطبيق»' % pre)
        ishot(page, pre + '13b-starter-review.jpg')
        page.click('#v3_sgo')
        page.wait_for_function("() => !document.querySelector('#v3_sgo')", timeout=15000)
        page.wait_for_function("() => /الأسعار المبدئية مطبّقة/.test(document.querySelector('.v3').innerText)", timeout=15000)
        got = writes(h, n0)
        paths = sorted(p_ for m, p_, _q, _b in got)
        if [m for m, *_ in got] != ['PUT'] * 3 or paths != sorted(['/api/bridge/prices/book/_guides', '/api/bridge/prices/book/bk-tenant-guide', '/api/bridge/prices/book/bk-startup-law']):
            fail('%s13: الكتابات %r' % (pre, [(m, p_) for m, p_, _q, _b in got]))
        for m, p_, _q, b in got:
            b = b or {}
            if b.get('confirmed') is not True or b.get('visible') is not True:
                fail('%s13: %s بلا confirmed/visible' % (pre, p_))
            if p_.endswith('_guides') and set((b.get('versions') or {}).keys()) - {'read', 'pdf'} != set() or (p_.endswith('_guides') and (b.get('versions') or {}).get('pdf')):
                fail('%s13: السعر العام للأدلّة فيه PDF' % pre)
        if page.locator('[data-a="starter"]').count():
            fail('%s13: الزر لسه ظاهر بعد التطبيق' % pre)
        ishot(page, pre + '13c-starter-applied.jpg')
        browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            d3fx.seed_dash(h.app)
            flow(browser, h, 'd', DESK, False)
            flow(browser, h, 'm', MOB, True)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls), 'problems': PROBLEMS},
                     ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
