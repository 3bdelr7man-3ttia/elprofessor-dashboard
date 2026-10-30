# -*- coding: utf-8 -*-
"""لقطات تبويب «الكتب والأعمال» الجديد (قسم «الكتب») — كمبيوتر ١٤٤٠ (`d*`) وتابلت ٨٢٠ (`t*`) وموبايل ٣٩٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_books.py ../docs/v2/final/shots-books [only-prefix,...]

اللقطات: القائمة بالممرّات · زر العقل · البحث · لا نتيجة · المرفوض مفتوحًا · قليل الصفوف بلا بحث · المصادر واقعة · المتجر مقفول · كله واقع ·
عروض فقط · صفحة عمل (ظاهر · مخفي وبيع منه · بلا اتفاقية · كتاب متجر) · الرجوع · بند المراجعة · ورقة الاعتماد من القائمة · رفض بلا ملف · بعد الاعتماد ·
«ضع سعرًا» · التعديل (نموذج · قبل ⇒ بعد · رفض المنصة) · تحذير الإخفاء · «أضف كتابًا» · مكتبة المراجع · فاضي · الغلاف مقفول.

السكربت بيفشل (exit 1) لو: «٠/0/null/NaN/undefined» ظاهر بدل «غير متاح بعد» · هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · تمرير أفقي · رقم لاتيني
ظاهر خارج رقم العمل · أي كتابة وصلت المنصة غير المسارات الأربعة الموجودة، أو سُجّلت قبل ضغطة التأكيد · أي طلب خرج من العملية غير خطوط جوجل ·
أي أثر للشكل القديم تحت الغلاف · صورة غير books.jpg والصورة الرمزية · بحث أو خانة نص أقل من ١٦px أو أقل من ٤٨px (٥٢px في الموبايل) ·
في الموبايل آخر سطر في صفحة العمل مغطّى بشريط الزرّ · الشريط ظاهر وفي ورقة مفتوحة · الرجوع من صفحة العمل لا يعيد القائمة · حفظ في المتصفح.
⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة (`v2s_books_fixtures.BooksPlatform`).
"""
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                            # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import v2_fixtures as v2fx                       # noqa: E402
import v2s_books_fixtures as bfx                 # noqa: E402
from ef_route_harness import Harness, DASH       # noqa: E402

PROBLEMS = vs.PROBLEMS
TAB = {'width': 820, 'height': 1180}
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
READY = "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-books[data-board]') && !/…جارٍ جلب/.test(document.querySelector('.v2s-books').innerText)"
ALLOWED_WRITES = [('PUT', re.compile(r'^/api/bridge/knowledge/[^/]+$')), ('POST', re.compile(r'^/api/bridge/knowledge/[^/]+/decide$')),
                  ('POST', re.compile(r'^/api/bridge/books$')), ('POST', re.compile(r'^/api/bridge/library/ingest-drive-folder$'))]
OLD_MARKERS = '#view .kpis, #view .policy, #view #knRows, #view details, #view .esc-row, #view .bk-cover, #view [role=tablist]'


def want(code):
    return not ONLY or any(code.startswith(o) for o in ONLY)


def bk_check(page, name):
    """أهداف ≥ ٤٤px (والأزرار ≥ ٥٢px في الموبايل) · لا تمرير أفقي · لا «٠/null/NaN» ولا أرقام لاتينية · لا أثر للقديم · صور مسموحة بس · خانات ≥ ١٦px."""
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v2s-books button, .v2s-books a[href], .v2s-books input, #epModal .v2s-bm button, #epModal .v2s-bm input, #epModal .v2s-bm textarea, #epModal .v2s-bm select')]
      .filter(b => b.offsetParent)
      .map(b => [b.className || b.tagName, Math.round((b.type === 'checkbox' && b.closest('label') ? b.closest('label') : b).getBoundingClientRect().height)])
      .filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    boxes = page.evaluate("""() => [...document.querySelectorAll('.v2s-books input[type=search], #epModal .v2s-bm input[type=text], #epModal .v2s-bm textarea, #epModal .v2s-bm select')]
      .filter(b => b.offsetParent).map(b => [b.id || b.className, Math.round(b.getBoundingClientRect().height), parseFloat(getComputedStyle(b).fontSize)])""")
    for ident, h, fs in boxes:
        if fs < 16 or h < (52 if w <= 400 else 48):
            PROBLEMS.append('%s: خانة %s ارتفاعها %s وخطها %s' % (name, ident, h, fs))
    if w <= 400:
        big = page.evaluate("""() => [...document.querySelectorAll('.v2s-books .v3-btn1, .v2s-books .v3-btn2, .v2s-books .v3-link, .v2s-books .bk-fold, #epModal .v2s-bm .btn')]
          .filter(b => b.offsetParent).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, big[:4]))
        narrow = page.evaluate("""() => { const W = window.innerWidth;
          return [...document.querySelectorAll('.v2s-books .v3-btn1, .v2s-books .v3-btn2, #epModal .v2s-bm .btn')]
            .filter(b => b.offsetParent && !b.closest('.bk-pills') && b.getBoundingClientRect().width < (b.closest('#epModal') ? 120 : W * 0.6))
            .map(b => [b.className, Math.round(b.getBoundingClientRect().width)]); }""")
        if narrow:
            PROBLEMS.append('%s: أزرار ليست بعرض الشاشة في الموبايل: %r' % (name, narrow[:4]))
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, sw, w))
        wide = page.evaluate("() => [...document.querySelectorAll('.v2s-books *, #epModal .v2s-bm *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
        if wide:
            PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    txt = page.evaluate("""() => [...document.querySelectorAll('.v2s-books, #epModal .v2s-bm')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('.bk-ref').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر في الشاشة' % name)
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    old = page.evaluate("(sel) => document.querySelectorAll(sel).length", OLD_MARKERS)
    if old:
        PROBLEMS.append('%s: أثر للشكل القديم (%d)' % (name, old))
    imgs = page.evaluate("() => [...document.querySelectorAll('#view img')].map(i => i.getAttribute('src'))")
    for src in imgs:
        if src not in ('v2/img/books.jpg', 'v2/img/brain-avatar.jpg'):
            PROBLEMS.append('%s: صورة غير مسموحة %s' % (name, src))
    keys = page.evaluate("() => { try { return Object.keys(localStorage).filter(k => k.indexOf('v2s_books') === 0); } catch (e) { return []; } }")
    if keys:
        PROBLEMS.append('%s: حفظ في المتصفح %r' % (name, keys))
    dock = page.evaluate("() => { const d = document.getElementById('bkDock'); return !!(d && d.getBoundingClientRect().height > 0 && getComputedStyle(d).display !== 'none' && document.getElementById('epModal')); }")
    if dock:
        PROBLEMS.append('%s: الشريط ظاهر وفي ورقة مفتوحة' % name)


def bshot(page, name):
    vs.shot(page, name, full=False)
    vs.shell_check(page, name)
    bk_check(page, name)


def scroll_to(page, sel, block='start'):
    page.evaluate("([s, b]) => { const e = document.querySelector(s); if (e) e.scrollIntoView({block: b}); }", [sel, block])
    page.wait_for_timeout(150)


def top(page):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")


def bopen(browser, h, ef, viewport, mobile, hash_='#s/books/books', wait=True):
    h.ef = ef
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    if wait:
        page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(500)
    return page


def writes(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE')]


def check_writes(name, h, since, expected):
    got = writes(h, since)
    for m, p, _q, _b in got:
        if not any(m == am and rx.match(p) for am, rx in ALLOWED_WRITES):
            PROBLEMS.append('%s: كتابة غير مسموحة %s %s' % (name, m, p))
    if len(got) != expected:
        PROBLEMS.append('%s: عدد الكتابات %d بدل %d: %r' % (name, len(got), expected, [(m, p) for m, p, _q, _b in got]))
    return got


def click_confirm(page, h, sel, since_idx):
    """يضغط زرّ التأكيد، ويفحص إن ولا كتابة سُجّلت قبل الضغطة (الوقت من سجل المنصة الوهمية)."""
    t0 = time.time()
    early = [e for e in h.ef.write_log[since_idx:] if e[0] < t0]
    if early:
        PROBLEMS.append('كتابة قبل ضغطة التأكيد: %r' % [(e[1], e[2]) for e in early])
    page.click(sel)
    return t0


def wait_closed(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)


def row(page, key):
    return '.v2s-books [data-key="%s"]' % key


def flow_books(browser, h, pre, viewport, mobile):
    w = viewport['width']
    tall = dict(viewport, height=viewport['height'] if (mobile or w == 820) else 1500)

    # —— ١) القائمة الكاملة
    if want('01'):
        page = bopen(browser, h, bfx.BooksPlatform(), tall, mobile)
        info = page.evaluate("""() => ({lanes: [...document.querySelectorAll('.bk-lane')].map(l => [l.getAttribute('data-lane'), ((l.querySelector('.v3-cnt') || {}).textContent || '').trim()]),
          search: !!document.getElementById('bkSearch'), brain: document.querySelector('.bk-bsum').textContent.trim(), btn: (document.querySelector('.bk-brain .v3-btn1') || {}).textContent,
          offlink: (document.querySelector('.bk-offlink') || {}).textContent, rejHidden: document.getElementById('bk-lane-rejected-body').hidden,
          tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), desc: document.querySelector('.v2c-h p').textContent})""")
        lanes = dict((k, v) for k, v in info['lanes'])
        if [k for k, _ in info['lanes']] != ['review', 'noprice', 'hiddenSold', 'live', 'hidden', 'rejected']:
            PROBLEMS.append('%s01: ترتيب الممرّات %r' % (pre, info['lanes']))
        if not info['search'] or not info['rejHidden'] or info['btn'] != 'ابدأ المراجعة' or 'وعرضان' not in (info['offlink'] or ''):
            PROBLEMS.append('%s01: القائمة ناقصة %r' % (pre, {k: info[k] for k in ('search', 'rejHidden', 'btn', 'offlink')}))
        if info['tabs'] != ['مراجعة العروض', 'طلبات القرّاء', 'الكتب والأعمال']:
            PROBLEMS.append('%s01: تبويبات الكتب %r' % (pre, info))
        if lanes.get('review') != '٣' or lanes.get('noprice') != '١' or lanes.get('hiddenSold') != '١':
            PROBLEMS.append('%s01: عدّادات القرار %r' % (pre, lanes))
        top(page)
        bshot(page, pre + '01-list.jpg')
        # 01b: زرّ العقل يقفز لأول ممرّ فيه شغل ويركّز عنوانه
        page.click('.bk-brain [data-a="brain"]')
        page.wait_for_timeout(300)
        focused = page.evaluate("() => (document.activeElement.closest('.bk-lane') || {}).id")
        if focused != 'bk-lane-review':
            PROBLEMS.append('%s01b: زرّ العقل ما ركّزش ممرّ المراجعة (%s)' % (pre, focused))
        bshot(page, pre + '01b-brain-scroll.jpg')
        # 01c: بحث بالتطبيع العربي
        top(page)
        page.fill('#bkSearch', 'دليل')
        page.wait_for_timeout(250)
        got = page.evaluate("() => [...document.querySelectorAll('.bk-lane')].map(l => l.getAttribute('data-lane'))")
        if 'rejected' in got or 'review' not in got or 'hidden' in got:
            PROBLEMS.append('%s01c: ممرّات البحث %r' % (pre, got))
        bshot(page, pre + '01c-search.jpg')
        page.fill('#bkSearch', 'اداره')
        page.fill('#bkSearch', 'zzzz')
        page.wait_for_timeout(200)
        if 'لا أعمال بهذا الوصف' not in page.inner_text('#bkLanes') or not page.query_selector('#bkLanes [data-a="clearq"]'):
            PROBLEMS.append(pre + '01d: لا نتيجة ناقصة')
        bshot(page, pre + '01d-nomatch.jpg')
        page.click('#bkLanes [data-a="clearq"]')
        page.wait_for_timeout(200)
        if page.input_value('#bkSearch') != '':
            PROBLEMS.append(pre + '01d: «امسح البحث» ما مسحش الخانة')
        # 01e: المرفوض مفتوحًا
        page.click('.bk-fold')
        page.wait_for_timeout(200)
        scroll_to(page, '#bk-lane-rejected')
        rej = page.evaluate("() => document.querySelectorAll('#bk-lane-rejected-body .bk-row').length")
        if rej != 2 or page.get_attribute('.bk-fold', 'aria-expanded') != 'true':
            PROBLEMS.append('%s01e: المرفوض مفتوحًا %d' % (pre, rej))
        bshot(page, pre + '01e-rejected-open.jpg')
        browser.close()

    if want('01f'):
        ef = bfx.BooksPlatform()
        ef.items = ef.items[3:7]
        ef.prices = {k: v for k, v in ef.prices.items() if k in ('bk-labor', 'bk-new')}
        ef.offers = []
        ef.store = [s for s in ef.store if s['slug'] == 'bk-labor']
        page = bopen(browser, h, ef, tall, mobile)
        if page.query_selector('#bkSearch'):
            PROBLEMS.append(pre + '01f: خانة البحث ظاهرة والصفوف قليلة')
        top(page)
        bshot(page, pre + '01f-few.jpg')
        browser.close()

    # —— ٢) المصادر واقعة
    if want('02'):
        ef = bfx.BooksPlatform(p1=False)
        ef.down = {'/api/bridge/books/works'}
        ef.down_status = {'pending_review'}
        page = bopen(browser, h, ef, tall, mobile)
        info = page.evaluate("""() => ({warn: (document.querySelector('.v3-warn') || {}).textContent, cnt: [...document.querySelectorAll('.bk-lane')].map(l => [l.getAttribute('data-lane'), ((l.querySelector('.v3-cnt') || {}).textContent || '').trim()]),
          na: document.body.innerText.indexOf('المبيعات: غير متاح بعد') > -1, lanes: [...document.querySelectorAll('.bk-lane')].map(l => l.getAttribute('data-lane'))})""")
        if 'حالة المراجعة' not in (info['warn'] or '') or 'بيانات المتجر' not in (info['warn'] or '') or not info['na'] or 'unknown' not in info['lanes']:
            PROBLEMS.append('%s02: المصادر الواقعة ما اتبيّنتش %r' % (pre, info))
        if not any('+' in c for _k, c in info['cnt']):
            PROBLEMS.append('%s02: عدّاد ناقص من غير «+» %r' % (pre, info['cnt']))
        top(page)
        bshot(page, pre + '02-sources-down.jpg')
        browser.close()

        page = bopen(browser, h, bfx.BooksPlatform(store_open=False), tall, mobile)
        if 'متجر الكتب لم يُفتح بعد' not in page.inner_text('.v2s-books') or page.query_selector('.v3-warn'):
            PROBLEMS.append(pre + '02b: المتجر المقفول ما اتبيّنش بلا تحذير')
        if page.evaluate("() => document.querySelectorAll('[data-key^=\"st:\"]').length"):
            PROBLEMS.append(pre + '02b: كتب متجر والمتجر مقفول')
        top(page)
        bshot(page, pre + '02b-store-closed.jpg')
        browser.close()

        ef = bfx.BooksPlatform()
        ef.down = {'/api/bridge/knowledge', '/api/bridge/prices/book', '/api/bridge/book-offers'}
        page = bopen(browser, h, ef, tall, mobile, wait=False)
        page.wait_for_function("() => /غير متاح بعد/.test(document.body.innerText) && document.querySelector('[data-a=\"retry\"]')", timeout=30000)
        if page.query_selector('.bk-lane'):
            PROBLEMS.append(pre + '02c: ممرّات ظاهرة والمصادر كلها واقعة')
        bshot(page, pre + '02c-all-down.jpg')
        ef.down = set()
        page.click('[data-a="retry"]')
        page.wait_for_function("() => document.querySelector('.bk-lane')", timeout=15000)
        browser.close()

        ef = bfx.BooksPlatform()
        ef.items = [d for d in ef.items if d['status'] != 'pending_review']
        page = bopen(browser, h, ef, tall, mobile)
        txt = page.inner_text('#bk-lane-review')
        if 'لا أعمال من السوق تنتظر مراجعتك' not in txt or 'وعرضان في «مراجعة العروض»' not in txt or page.query_selector('#bk-lane-review .v3-cnt'):
            PROBLEMS.append('%s02d: ممرّ المراجعة بعروض فقط %r' % (pre, txt))
        scroll_to(page, '#bk-lane-review')
        bshot(page, pre + '02d-offers-only.jpg')
        page.click('#bk-lane-review [data-a="offers"]')
        page.wait_for_function("() => location.hash === '#s/books/offers'", timeout=10000)
        browser.close()

    # —— ٣) صفحة العمل
    if want('03'):
        page = bopen(browser, h, bfx.BooksPlatform(), tall, mobile)
        scroll_to(page, row(page, 'kn:kn-4'), 'center')
        y0 = page.evaluate("() => (document.querySelector('.content') || {}).scrollTop || window.scrollY")
        page.click(row(page, 'kn:kn-4') + ' [data-a="open"]')
        page.wait_for_selector('.v2s-books[data-board="work"]')
        facts = page.evaluate("() => [...document.querySelectorAll('.bk-facts dt')].map(d => d.textContent)")
        if facts != ['الحالة', 'المبيعات', 'السعر', 'اتفاقية البيع', 'الملف', 'أُضيف', 'رقم العمل']:
            PROBLEMS.append('%s03: حقائق العمل %r' % (pre, facts))
        txt = page.inner_text('.v2s-books')
        if 'لا شيء ينتظرك في هذا العمل' not in txt or 'النسبة القديمة' not in txt or 'يُباع بالنسبة القديمة' not in txt:
            PROBLEMS.append(pre + '03: صفحة عمل ظاهر ناقصة (الاتفاقية القديمة وسطر العقل)')
        if page.query_selector('.bk-dock') and not mobile:
            pass
        top(page)
        bshot(page, pre + '03-work-market-live.jpg')
        # 03c: الرجوع بزرّ المتصفح يرجع للقائمة والتمرير محفوظ
        page.go_back()
        page.wait_for_selector('.v2s-books[data-board="works"]')
        page.wait_for_timeout(300)
        y1 = page.evaluate("() => (document.querySelector('.content') || {}).scrollTop || window.scrollY")
        if page.evaluate('() => location.hash') != '#s/books/books' or abs((y1 or 0) - (y0 or 0)) > 40:
            PROBLEMS.append('%s03c: الرجوع ما رجّعش القائمة (hash=%s y=%s/%s)' % (pre, page.evaluate('() => location.hash'), y1, y0))
        bshot(page, pre + '03c-back.jpg')
        # الرجوع من الزرّ داخل الصفحة
        page.click(row(page, 'kn:kn-4') + ' [data-a="open"]')
        page.wait_for_selector('.v2s-books[data-board="work"]')
        page.click('.bk-back')
        page.wait_for_selector('.v2s-books[data-board="works"]')
        # 03b: مخفي وبيع منه
        scroll_to(page, '#bk-lane-hiddenSold')
        page.click(row(page, 'kn:kn-7') + ' [data-a="open"]')
        page.wait_for_selector('.v2s-books[data-board="work"]')
        txt = page.inner_text('.v2s-books')
        if 'لا يستطيع أصحابها تحميلها' not in txt or not page.query_selector('.bk-panel .bk-mainbtn'):
            PROBLEMS.append(pre + '03b: صفحة المخفي المبيع ناقصة')
        if mobile:
            if not page.evaluate("() => { const d = document.getElementById('bkDock'); return !!d && d.getBoundingClientRect().height > 0 && getComputedStyle(d).display !== 'none'; }"):
                PROBLEMS.append(pre + '03b: شريط الزرّ مش ظاهر في الموبايل')
            if page.evaluate("() => getComputedStyle(document.querySelector('.bk-panel .bk-mainbtn')).display") != 'none':
                PROBLEMS.append(pre + '03b: الزرّ متكرر في اللوحة والشريط')
            page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = c.scrollHeight; window.scrollTo(0, document.body.scrollHeight); }")
            page.wait_for_timeout(200)
            cover = page.evaluate("""() => { const dds = document.querySelectorAll('.bk-facts dd'), last = dds[dds.length - 1].getBoundingClientRect(), d = document.getElementById('bkDock').getBoundingClientRect();
              return last.bottom - d.top; }""")
            if cover > 0.5:
                PROBLEMS.append('%s03b: الشريط يغطّي آخر سطر (%s)' % (pre, cover))
        else:
            if page.evaluate("() => { const d = document.getElementById('bkDock'); return !!(d && d.getBoundingClientRect().height > 0 && getComputedStyle(d).display !== 'none'); }"):
                PROBLEMS.append(pre + '03b: شريط الموبايل ظاهر على الشاشة الكبيرة')
        top(page)
        bshot(page, pre + '03b-work-hidden-sold.jpg')
        browser.close()

        page = bopen(browser, h, bfx.BooksPlatform(p1=False), tall, mobile)
        page.click(row(page, 'kn:kn-4') + ' [data-a="open"]')
        page.wait_for_selector('.v2s-books[data-board="work"]')
        txt = page.inner_text('.v2s-books')
        agr = page.evaluate("() => [...document.querySelectorAll('.bk-facts > div')].filter(d => d.querySelector('dt').textContent === 'اتفاقية البيع').map(d => d.querySelector('dd').textContent)")
        if agr != ['غير متاح بعد'] or 'يُباع بالنسبة القديمة' in txt:
            PROBLEMS.append('%s03d: بلا الحقول الجديدة %r' % (pre, agr))
        top(page)
        bshot(page, pre + '03d-no-p1.jpg')
        browser.close()

    # —— ٤) قرارات المراجعة من بند القائمة
    if want('04'):
        ef = bfx.BooksPlatform()
        page = bopen(browser, h, ef, tall, mobile)
        scroll_to(page, '#bk-lane-review')
        item = page.inner_text(row(page, 'kn:kn-1'))
        if 'ينتظر المراجعة منذ' not in item or 'اعتمد وانشر' not in item or 'ارفض' not in item:
            PROBLEMS.append('%s04: بند المراجعة ناقص %r' % (pre, item))
        bshot(page, pre + '04-review-item.jpg')
        n0, wl = len(h.platform_calls), len(ef.write_log)
        page.click(row(page, 'kn:kn-1') + ' [data-a="approve"]')
        page.wait_for_selector('#epModal #bk_go')
        bshot(page, pre + '04b-approve.jpg')
        check_writes(pre + '04b', h, n0, 0)
        page.click('#bk_x')
        wait_closed(page)
        # 04c: بلا ملف ⇒ «ارفض» هو الرئيسي والسبب جاهز
        page.click(row(page, 'kn:kn-2') + ' [data-a="reject"]')
        page.wait_for_selector('#epModal #bk_reason')
        if 'أرفق ملف العمل' not in page.input_value('#bk_reason'):
            PROBLEMS.append(pre + '04c: سبب الرفض مش جاهز')
        main_label = page.evaluate("() => document.querySelector('[data-key=\"kn:kn-2\"] .v3-btn1').textContent")
        if main_label != 'ارفض':
            PROBLEMS.append('%s04c: زرّ بند بلا ملف الرئيسي %r' % (pre, main_label))
        bshot(page, pre + '04c-reject-nofile.jpg')
        page.click('#bk_x')
        wait_closed(page)
        # اعتماد فعلي بعد ضغطة التأكيد
        page.click(row(page, 'kn:kn-1') + ' [data-a="approve"]')
        page.wait_for_selector('#epModal #bk_go')
        n1 = len(ef.write_log)
        click_confirm(page, h, '#bk_go', n1)
        wait_closed(page)
        page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
        page.wait_for_function("() => document.querySelector('#bk-lane-live [data-key=\"kn:kn-1\"]')", timeout=10000)
        got = check_writes(pre + '04d', h, n0, 1)
        if got and (got[0][0] != 'POST' or got[0][1] != '/api/bridge/knowledge/kn-1/decide' or got[0][3].get('decision') != 'approve' or got[0][3].get('note') != ''):
            PROBLEMS.append('%s04d: نداء الاعتماد %r' % (pre, got[0]))
        if page.query_selector(row(page, 'kn:kn-1') + '.bk-dec'):
            PROBLEMS.append(pre + '04d: العمل لسه في ممرّ المراجعة بعد الاعتماد')
        top(page)
        bshot(page, pre + '04d-after-approve.jpg')
        # الرفض بسبب
        page.click(row(page, 'kn:kn-3') + ' [data-a="reject"]')
        page.wait_for_selector('#epModal #bk_reason')
        page.click('#bk_go')
        if 'اكتب سبب الرفض' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '04c: رفض بلا سبب اتقبل')
        page.fill('#bk_reason', 'الموضوع مكرر مع كتاب آخر')
        n2 = len(ef.write_log)
        click_confirm(page, h, '#bk_go', n2)
        wait_closed(page)
        page.wait_for_function("() => document.querySelector('#bk-lane-rejected [data-key=\"kn:kn-3\"]')", timeout=10000)
        got = check_writes(pre + '04e', h, n0, 2)
        if got and got[-1][3] != {'decision': 'reject', 'note': 'الموضوع مكرر مع كتاب آخر'}:
            PROBLEMS.append('%s04e: جسم الرفض %r' % (pre, got[-1][3]))
        # اعتماد بلا ملف تردّه المنصة ⇒ رسالتها في الورقة (٤٢٢)
        page.click(row(page, 'kn:kn-2') + ' [data-a="approve"]')
        page.wait_for_selector('#epModal #bk_go')
        page.click('#bk_go')
        page.wait_for_selector('#epModal .v3-err')
        if 'بلا ملف' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '04f: رسالة المنصة ما ظهرتش')
        bshot(page, pre + '04f-refused.jpg')
        page.click('#bk_x')
        browser.close()

    # —— ٥) كتب المتجر
    if want('05'):
        page = bopen(browser, h, bfx.BooksPlatform(), tall, mobile)
        scroll_to(page, row(page, 'st:bk-tenant-guide'), 'center')
        page.click(row(page, 'st:bk-tenant-guide') + ' [data-a="open"]')
        page.wait_for_selector('.v2s-books[data-board="work"]')
        page.wait_for_function("() => document.querySelector('.bk-facts').innerText.indexOf('آخر حركة') > -1", timeout=15000)
        txt = page.inner_text('.v2s-books')
        for need in ('للقراءة على المنصة', 'للتحميل', 'النشر مع إعلانات', 'مصر:', 'السعودية:', 'إعلانات الأعمال', 'الفلوس › الأسعار', 'عدّل الأسعار والظهور'):
            if need not in txt:
                PROBLEMS.append('%s05: صفحة كتاب المتجر ناقصة «%s»' % (pre, need))
        if page.query_selector('.bk-panel .v3-btn1'):
            PROBLEMS.append(pre + '05: كتاب ظاهر فيه زرّ رئيسي')
        top(page)
        bshot(page, pre + '05-work-store.jpg')
        page.click('.bk-back')
        page.wait_for_selector('.v2s-books[data-board="works"]')
        scroll_to(page, '#bk-lane-noprice')
        page.click(row(page, 'st:bk-new') + ' [data-a="price"]')
        page.wait_for_function("() => location.hash === '#s/money/prices'", timeout=10000)
        page.wait_for_function("() => document.querySelector('.v3[data-board=\"prices\"]')", timeout=10000)
        bshot_money = page.evaluate("() => document.querySelector('.v2c-h h1').textContent")
        if bshot_money != 'الفلوس':
            PROBLEMS.append('%s05b: «ضع سعرًا» ما وصّلش لـ«الفلوس» (%s)' % (pre, bshot_money))
        vs.shot(page, pre + '05b-store-noprice.jpg')
        browser.close()

    # —— ٦) التعديل والإخفاء والإظهار
    if want('06'):
        ef = bfx.BooksPlatform()
        page = bopen(browser, h, ef, tall, mobile)
        n0 = len(h.platform_calls)
        page.click(row(page, 'kn:kn-4') + ' [data-a="open"]')
        page.wait_for_selector('.v2s-books[data-board="work"]')
        page.click('.bk-panel [data-a="edit"]')
        page.wait_for_selector('#epModal #bk_t')
        bshot(page, pre + '06-edit.jpg')
        page.click('#bk_rev')
        if 'لم تغيّر أي شيء' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '06: تعديل بلا تغيير اتقبل')
        page.fill('#bk_p', 'abc')
        page.click('#bk_rev')
        if 'اكتب السعر رقمًا' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '06: سعر غير صالح اتقبل')
        page.fill('#bk_t', 'الوجيز في أحكام الشركات (طبعة جديدة)')
        page.fill('#bk_p', '٢٩٩٫٥٠')
        page.click('#bk_rev')
        page.wait_for_selector('#bk_go')
        diff = page.inner_text('#bk_s2')
        for need in ('الآن', 'بعد التعديل', 'السعر', '٢٥٠ جنيه', '٢٩٩٫٥ جنيه', 'يسري على المشترين القادمين فقط', 'المنصة ٢٠٪'):
            if need not in diff:
                PROBLEMS.append('%s06b: المراجعة ناقصة «%s» %r' % (pre, need, diff))
        bshot(page, pre + '06b-edit-diff.jpg')
        check_writes(pre + '06b', h, n0, 0)
        # 06c: رفض المنصة
        ef.forced[('PUT', '/api/bridge/knowledge/kn-4')] = (422, {'detail': 'السعر أقل من الحد المسموح 50 جنيه'})
        click_confirm(page, h, '#bk_go', len(ef.write_log))
        page.wait_for_selector('#bkerr2 .v3-err')
        if 'رفضت المنصة هذا التعديل' not in page.inner_text('#bkerr2') or '٥٠' not in page.inner_text('#bkerr2'):
            PROBLEMS.append(pre + '06c: رسالة المنصة %r' % page.inner_text('#bkerr2'))
        bshot(page, pre + '06c-edit-refused.jpg')
        del ef.forced[('PUT', '/api/bridge/knowledge/kn-4')]
        n1 = len(ef.write_log)
        click_confirm(page, h, '#bk_go', n1)
        wait_closed(page)
        page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
        got = [c for c in writes(h, n0) if c[1] == '/api/bridge/knowledge/kn-4' and c[3].get('price_egp') == 299.5]
        if not got or set(got[-1][3].keys()) != {'title', 'price_egp'}:
            PROBLEMS.append('%s06d: جسم التعديل %r' % (pre, writes(h, n0)))
        check_writes(pre + '06d', h, n0, 2)
        # 07: الإخفاء بتحذير المشترين
        page.click('.bk-panel [data-a="hide"]')
        page.wait_for_selector('#epModal .v3-warn')
        if 'لا يستطيع تحميله' not in page.inner_text('#epModal'):
            PROBLEMS.append(pre + '07: تحذير الإخفاء ناقص')
        bshot(page, pre + '07-hide-warning.jpg')
        n2 = len(writes(h, n0))
        page.click('#bk_x')
        wait_closed(page)
        if len(writes(h, n0)) != n2:
            PROBLEMS.append(pre + '07: إلغاء الإخفاء كتب شيئًا')
        click_hide = True
        page.click('.bk-panel [data-a="hide"]')
        page.wait_for_selector('#epModal #bk_go')
        click_confirm(page, h, '#bk_go', len(ef.write_log))
        wait_closed(page)
        page.wait_for_function("() => document.querySelector('.bk-panel [data-a=\"show\"]')", timeout=10000)
        last = writes(h, n0)[-1]
        if last[3] != {'is_active': False}:
            PROBLEMS.append('%s07: جسم الإخفاء %r' % (pre, last))
        del click_hide
        browser.close()

    # —— ٨) أضف كتابًا
    if want('08'):
        ef = bfx.BooksPlatform()
        page = bopen(browser, h, ef, tall, mobile)
        n0 = len(h.platform_calls)
        scroll_to(page, '.bk-addrow')
        page.click('.bk-addrow [data-a="add"]')
        page.wait_for_selector('#epModal #bk_at')
        page.click('#bk_go')
        if 'اكتب عنوان الكتاب' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '08: كتاب بلا عنوان اتقبل')
        page.fill('#bk_at', 'دليل المحامي الجديد')
        page.fill('#bk_af', 'http://x.test/a.pdf')
        page.click('#bk_go')
        if 'الصق رابطًا يبدأ بـ' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '08: رابط غير آمن اتقبل')
        bshot(page, pre + '08-add.jpg')
        check_writes(pre + '08', h, n0, 0)
        page.fill('#bk_af', 'https://files.example.test/new.pdf')
        page.fill('#bk_ap', '١٢٠')
        click_confirm(page, h, '#bk_go', len(ef.write_log))
        wait_closed(page)
        page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
        got = check_writes(pre + '08b', h, n0, 1)
        if got and set(got[0][3].keys()) != {'title', 'author', 'description', 'price', 'currency', 'file_url', 'cover_url', 'is_active'}:
            PROBLEMS.append('%s08b: حقول الإضافة %r' % (pre, got[0][3]))
        if got and (got[0][3]['price'] != 120 or got[0][3]['is_active'] is not True):
            PROBLEMS.append('%s08b: قيم الإضافة %r' % (pre, got[0][3]))
        # 09: مكتبة المراجع
        scroll_to(page, '.bk-libline', 'center')
        bshot(page, pre + '09-library-line.jpg')
        page.click('.bk-libline [data-a="library"]')
        page.wait_for_selector('#epModal #bk_lf')
        page.click('#bk_go')
        if 'الصق رابط مجلد' not in page.inner_text('#bkerr'):
            PROBLEMS.append(pre + '09: مجلد فاضي اتقبل')
        bshot(page, pre + '09-library.jpg')
        n1 = len(h.platform_calls)
        page.fill('#bk_lf', 'https://drive.google.com/drive/u/0/folders/1AbCdEfGhIjKlMnOp?usp=sharing')
        click_confirm(page, h, '#bk_go', len(ef.write_log))
        page.wait_for_selector('#bk_done')
        if 'استُورد ٥ من ٧ ملفًا' not in page.inner_text('#epModal'):
            PROBLEMS.append(pre + '09b: نتيجة الاستيراد %r' % page.inner_text('#epModal'))
        sent = [c for c in writes(h, n1)]
        if len(sent) != 1 or {k: sent[0][3].get(k) for k in ('folder_id', 'category', 'max_files')} != {'folder_id': '1AbCdEfGhIjKlMnOp', 'category': 'memo_template', 'max_files': 40}:
            PROBLEMS.append('%s09b: نداء الاستيراد %r' % (pre, sent))
        check_writes(pre + '09b', h, n1, 1)
        bshot(page, pre + '09b-library-done.jpg')
        page.click('#bk_done')
        wait_closed(page)
        browser.close()

    # —— ١٠) لا أعمال بعد
    if want('10'):
        page = bopen(browser, h, bfx.BooksPlatform(empty=True), tall, mobile)
        n = page.evaluate("() => ({adds: document.querySelectorAll('[data-a=\"add\"]').length, lanes: document.querySelectorAll('.bk-lane').length, search: !!document.getElementById('bkSearch'), empty: document.querySelectorAll('.v3-empty').length, lib: !!document.querySelector('.bk-libline')})")
        if n != {'adds': 1, 'lanes': 0, 'search': False, 'empty': 1, 'lib': True}:
            PROBLEMS.append('%s10: الفاضي %r' % (pre, n))
        top(page)
        bshot(page, pre + '10-empty.jpg')
        browser.close()

    # —— ١٢) الغلاف مقفول = الشاشة القديمة بحالها
    if want('12'):
        os.environ.pop('DASH_V2_ENABLED', None)
        try:
            h.ef = bfx.BooksPlatform()
            ctx = browser.context(h, 'admin', viewport, mobile)
            page = ctx.new_page()
            page.goto(DASH + '/#knowledge', wait_until='domcontentloaded')
            page.wait_for_function("() => window.EP && EP.state.knowledge === 'ready' && document.getElementById('knRows')", timeout=30000)
            page.wait_for_timeout(400)
            st = page.evaluate("() => ({new: !!document.querySelector('.v2s-books, .v3'), on: !!window.V2_ON, shell: !!(window.V2SHELL && V2SHELL.on), old: !!document.querySelector('#knRows .row')})")
            if st['new'] or st['on'] or st['shell'] or not st['old']:
                PROBLEMS.append('%s12: المفتاح مقفول والشاشة مش القديمة %r' % (pre, st))
            bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
              for (const p of ['/api/v2/books/review?status=rejected', '/api/v2/books/store']) {
                const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
            if bad:
                PROBLEMS.append('%s12: مسارات الكتب والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
            vs.shot(page, pre + '12-flag-off.jpg')
        finally:
            os.environ['DASH_V2_ENABLED'] = 'true'
        browser.close()


def main():
    import json
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', vs.DESK, False), ('t', TAB, False), ('m', vs.MOB, True)):
                if pre not in os.environ.get('BK_VP', 'dtm'):
                    continue
                flow_books(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
