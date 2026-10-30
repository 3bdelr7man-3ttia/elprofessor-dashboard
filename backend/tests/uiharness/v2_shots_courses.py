# -*- coding: utf-8 -*-
"""صور قسم «الدورات والمدرّبون» (الجولة الأخيرة) — كمبيوتر ١٤٤٠ (`d*`) وتابلت ٨٢٠ (`t*`) وموبايل ٣٩٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_courses.py ../docs/v2/final/shots-courses

الارتفاع طويل عمدًا (١٥٠٠ للكمبيوتر والتابلت و١٧٠٠ للموبايل) لأن الصفحة تمرّر من جوّا `.content` فلا تظهر الصفحة كلها في إطار قصير؛ العرض هو
اللي بيحكم الشكل. الوضع الرئيسي `with_abc=False` (المنصة لسه ما نشرتش الإضافات أ/ب/ج: لا صور ولا `submitted_at` ولا فحص نشر ولا مبيعات)،
ولقطات `-abc` بتبيّن اللي هيشوفه المؤسس بعد النشر. ⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة في الذاكرة (`courses_fixtures`)، وأي أصل
تاني بيتقفل ويتسجّل. السكربت بيفشل لو: «0/null/NaN/undefined» ظاهرة بدل «غير متاح بعد» · هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · تمرير
أفقي في أي عرض أو جوه أي بطاقة · رقم لاتيني ظاهر · طلب خارج التطبيق وخطوط جوجل · كتابة على `/api/v2/courses/*` بلا `confirmed:true` أو أي
كتابة على المسارات القديمة من الشاشات الجديدة · أثر للقائمة القديمة · شكل قديم ظاهر برّه إطار «كل السجلات» · داخل الإطار: تبويب قديم غير
«سجل الإدارة/الكتالوج» أو زرّ قرار قديم أو لون الأزرق/الذهبي القديم · عدّاد بلون على دورة بلا `submitted_at`.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'shots-courses'))
os.makedirs(OUT, exist_ok=True)
sys.argv = [sys.argv[0], OUT] + sys.argv[2:]

import v2_shots as vs                       # noqa: E402
import courses_fixtures as cf               # noqa: E402
from ef_route_harness import Harness, DASH  # noqa: E402

vs.OUT = OUT
PROBLEMS = vs.PROBLEMS
SHOTS = vs.SHOTS
DESK = {'width': 1440, 'height': 1500}
TAB = {'width': 820, 'height': 1500}
MOB = {'width': 390, 'height': 1700}
READY_CO = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2co') && !/…جارٍ جلب/.test(document.querySelector('.v2co').innerText)")
OLD_NAVY = None
OLD_GOLD = None


def rgb(css):
    m = re.findall(r'\d+', css or '')
    return tuple(int(x) for x in m[:3]) if len(m) >= 3 else None


def co_check(page, name, legacy=False):
    w = page.viewport_size['width']
    mobile = w <= 400
    # أهداف اللمس
    small = page.evaluate("""() => [...document.querySelectorAll('.v2co button, .v2co a[href], .v2co summary, .v2co input:not([type=checkbox]):not([type=radio]), #epModal .v2co-m button, #epModal .v2co-m input:not([type=checkbox]):not([type=radio]), #epModal .v2co-m textarea, #epModal .v2co-m select')]
      .filter(b => b.offsetParent && !b.classList.contains('v2co-person') && !b.closest('.v2co-lvhead,.v2co-lhead'))
      .map(b => [b.className || b.tagName, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    if mobile:
        big = page.evaluate("""() => [...document.querySelectorAll('.v2co-btn1, .v2co-btn2, .v2co-main, .v2co-link, .v2co-segb, .v2co-fchip, .v2co-mi, #epModal .v2co-m .v2co-btn1, #epModal .v2co-m .v2co-btn2')]
          .filter(b => b.offsetParent).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, big[:4]))
    # التمرير الأفقي: الصفحة وكل بطاقة
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    inner = page.evaluate("""() => [...document.querySelectorAll('[class*="v2co-"]')].filter(e => e.offsetParent && !['INPUT','TEXTAREA','SELECT','IMG'].includes(e.tagName)
      && e.scrollWidth > e.clientWidth + 1 && !['hidden','clip'].includes(getComputedStyle(e).overflowX) && getComputedStyle(e).display !== 'inline'
      && !e.closest('.v2co-legacy')).map(e => e.className.toString().slice(0, 40)).slice(0, 5)""")
    if inner:
        PROBLEMS.append('%s: تمرير أفقي جوه عناصر: %r' % (name, inner))
    out = page.evaluate("() => [...document.querySelectorAll('.v2co *, #epModal .v2co-m *')].filter(e => e.offsetParent && getComputedStyle(e).position !== 'absolute' && e.getBoundingClientRect().right > window.innerWidth + 1 && !e.closest('.v2c-tabs')).length")
    if out:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, out))
    # نصوص: الأرقام اللاتينية (إلا المعرّفات: بريد · رقم هاتف) و0/null/NaN
    txt = page.evaluate("""() => [...document.querySelectorAll('.v2co, .v2co-legacy, #epModal')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('.v2co-ph, [dir="ltr"], script, style').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر في الشاشة' % name)
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t and not re.search(r'[A-Za-z]-?\d', t)]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    for word in ('Zoom', 'Titch', 'API', 'slug', 'يقوّم'):
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % word, txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    # لا أثر لشكل قديم برّه إطار «كل السجلات»
    old = page.evaluate("""() => [...document.querySelectorAll('.kpis, .tabbar, .inboxwrap, .rail')].filter(e => e.offsetParent && !e.closest('.v2co-legacy')).map(e => e.className)""")
    if old:
        PROBLEMS.append('%s: شكل قديم ظاهر برّه الإطار: %r' % (name, old))


def co_shot(page, name, legacy=False):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    vs.shot(page, name, full=False)
    vs.shell_check(page, name)
    co_check(page, name)


def legacy_check(page, name):
    r = page.evaluate("""([navy, gold]) => {
      const vis = e => !!e.offsetParent;
      const tabs = [...document.querySelectorAll('.v2co-legacy #cTabs .tab[data-t]')].filter(vis).map(t => t.getAttribute('data-t'));
      const sel = '[data-a="pcapprove"],[data-a="pcreject"],[data-a="pctoggle"],[data-a="pcbidtoggle"],.pcDel,[data-a="editc"],[data-a="delc"],[data-a="pub"],[data-a="pubplatform"],#cCreate,#vp_pub';
      const btns = [...document.querySelectorAll(sel)].filter(vis).map(b => b.getAttribute('data-a') || b.id || b.className);
      const bad = [];
      document.querySelectorAll('.v2co-legacy *, #epModal *').forEach(e => { if (!vis(e)) return; const cs = getComputedStyle(e);
        [cs.color, cs.backgroundColor, cs.borderTopColor].forEach(c => { if (c === navy || c === gold) bad.push(e.className.toString().slice(0, 30) + ':' + c); }); });
      return {tabs, btns, bad: bad.slice(0, 6)};
    }""", [OLD_NAVY, OLD_GOLD])
    if sorted(r['tabs']) not in (['courses', 'platform'], ['courses'], ['platform']):
        PROBLEMS.append('%s: تبويبات قديمة ظاهرة جوه «كل السجلات»: %r' % (name, r['tabs']))
    if r['btns']:
        PROBLEMS.append('%s: أزرار قرار قديمة ظاهرة: %r' % (name, r['btns']))
    if r['bad']:
        PROBLEMS.append('%s: ألوان قديمة (الأزرق/الذهبي) ظاهرة: %r' % (name, r['bad']))


def wait_co(page, ms=700):
    page.wait_for_function(READY_CO, timeout=30000)
    page.wait_for_timeout(ms)


def nav(page, hash_, ms=700):
    page.evaluate("h => { location.hash = h; }", hash_)
    wait_co(page, ms)


def open_co(ctx, hash_, reqs=None, ms=900):
    page = ctx.new_page()
    if reqs is not None:
        page.on('request', lambda r: reqs.append((r.method, r.url, r.post_data)) if r.method != 'GET' and '/api/' in r.url else None)
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    wait_co(page, ms)
    return page


def sheet(page):
    page.wait_for_selector('#epModal .v2co-m', timeout=10000)
    page.wait_for_timeout(250)


def close_sheet(page):
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
    page.wait_for_timeout(150)


def writes_ok(reqs, name):
    """كل كتابة على المسارات الجديدة بـ`confirmed:true`، ولا كتابة من الشاشات الجديدة على المسارات القديمة للدورات."""
    for method, url, body in reqs:
        path = re.sub(r'^https?://[^/]+', '', url)
        if path.startswith('/api/v2/courses/') and method == 'POST':
            try:
                b = json.loads(body or '{}')
            except Exception:
                b = {}
            if b.get('confirmed') is not True:
                PROBLEMS.append('%s: كتابة بلا confirmed:true على %s' % (name, path))
        if re.match(r'^/api/(platform-courses|platform-course-offers)', path) and method != 'GET':
            PROBLEMS.append('%s: كتابة على مسار قديم %s' % (name, path))


def rows_state(page):
    return page.evaluate("""() => ({review: document.querySelectorAll('.v2co-col[data-col="review"] .v2co-t').length,
      building: document.querySelectorAll('.v2co-col[data-col="building"] .v2co-bc').length, published: document.querySelectorAll('.v2co-col[data-col="published"] .v2co-pr').length})""")


def click_col(page, col, mobile):
    if mobile:
        page.click('[data-a="col"][data-col="%s"]' % col)
        page.wait_for_timeout(250)


# ======================================================================= الرئيسي (بلا الإضافات أ/ب/ج)
def flow_main(browser, h, pre, vp, mobile):
    w = vp['width']
    h.ef = cf.CoursesPlatform(with_abc=False)
    ctx = browser.context(h, 'admin', vp, mobile)
    reqs = []
    page = open_co(ctx, '#s/courses/courses', reqs)
    # —— ٠١) اللوحة (الأعمدة) · الموبايل على كل زرّ
    info = page.evaluate("""() => ({tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), h1: document.querySelector('.v2c-h h1').textContent,
      sum: document.querySelector('.v2co-sum').textContent.trim(), covers: document.querySelectorAll('.v2co-cover').length, imgs: document.querySelectorAll('.v2co-img').length,
      main: [...document.querySelectorAll('.v2co-col[data-col="review"] .v2co-t .v2co-btn1')].map(b => b.textContent.trim()),
      timers: [...document.querySelectorAll('.v2co-col[data-col="review"] .v2co-time')].map(t => [t.textContent.trim(), t.className])})""")
    if info['tabs'] != ['الدورات', 'المدرّبون', 'الدورات الحيّة', 'ما يطلبه الناس', 'عروض الأسعار', 'كل السجلات']:
        PROBLEMS.append('%s01: تبويبات القسم %r' % (pre, info['tabs']))
    if info['sum'] != '١١ دورة منشورة · ٣ تحت البناء · دورتان تنتظرانك':
        PROBLEMS.append('%s01: سطر الملخّص %r' % (pre, info['sum']))
    if info['imgs'] != 0 or info['covers'] < 8:
        PROBLEMS.append('%s01: الأغلفة الورقية بلا صور: covers=%s imgs=%s' % (pre, info['covers'], info['imgs']))
    if sorted(info['main']) != sorted(['افتح وراجع', 'أعِدها بملاحظات']):
        PROBLEMS.append('%s01: أزرار التذاكر %r' % (pre, info['main']))
    if any('tone-none' not in t[1] or not t[0].startswith('أُنشئت') for t in info['timers']):
        PROBLEMS.append('%s01: عدّاد بلا submitted_at لازم رمادي وبصيغة «أُنشئت»: %r' % (pre, info['timers']))
    strips = page.evaluate("() => [...document.querySelectorAll('.v2co-col[data-col=\"review\"] .v2co-strip')].map(s => getComputedStyle(s).backgroundColor)")
    for c in strips:
        if rgb(c) in ((200, 16, 46), (143, 95, 0)):
            PROBLEMS.append('%s01: شريط تذكرة بلون تحذير على دورة بلا submitted_at: %s' % (pre, c))
    co_shot(page, pre + '01-board.jpg')
    if mobile:
        for col in ('review', 'building', 'published'):
            click_col(page, col, True)
            co_shot(page, pre + '01m-%s.jpg' % col)
        click_col(page, 'review', True)
    # —— ٠٥ هـ ٠٦) صفحة دورة في المراجعة بلا فحص نشر (القرار لك) · ورقة الإعادة بملاحظة جاهزة
    nav(page, '#s/courses/course/pc-15')
    st = page.evaluate("() => ({hash: location.hash, block: !!document.querySelector('.v2co-decide'), eq: [...document.querySelectorAll('.v2co-eq .v2co-btn1')].map(b => b.textContent.trim()), cls: [...document.querySelectorAll('.v2co-eq .v2co-btn1')].map(b => b.className)})")
    if st['hash'] != '#s/courses/course/pc-15' or not st['block'] or st['eq'] != ['انشرها', 'أعِدها بملاحظات'] or any('outline' not in c for c in st['cls']):
        PROBLEMS.append('%s05e: كتلة «القرار لك» %r' % (pre, st))
    co_shot(page, pre + '05e-course-review-unknown.jpg')
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    wait_co(page)
    if page.evaluate("() => location.hash") != '#s/courses/course/pc-15' or not page.query_selector('.v2co-decide'):
        PROBLEMS.append('%s05f: بعد إعادة التحميل ما رجعتش نفس الصفحة' % pre)
    co_shot(page, pre + '05f-course-after-reload.jpg')
    nav(page, '#s/courses/course/zzz-none')
    if 'غير متاح بعد' not in page.inner_text('.v2co'):
        PROBLEMS.append(pre + '05g: معرّف مجهول لازم «غير متاح بعد»')
    co_shot(page, pre + '05g-course-unknown-id.jpg')
    # —— ٠٥ ب جـ د) النشر من كتلة «القرار لك»: ورقة ١ ثم ٢ ثم النجاح
    nav(page, '#s/courses/course/pc-15')
    page.click('.v2co-eq [data-a="approve"]')
    sheet(page)
    co_shot(page, pre + '05b-approve-sheet-1.jpg')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    txt = page.inner_text('#epModal .v2co-m')
    if 'لم يكتمل فحص النشر' not in txt:
        PROBLEMS.append(pre + '05c: ورقة النشر ٢ ما فيهاش «لم يكتمل فحص النشر»')
    co_shot(page, pre + '05c-approve-sheet-2.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(900)
    sent = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/approve')]
    if len(sent) != 1 or sent[0][3] not in ({}, None) and set((sent[0][3] or {}).keys()) - {'payout_model'}:
        PROBLEMS.append('%s05d: نداء النشر %r' % (pre, sent))
    if not page.query_selector('.v2co-ok'):
        PROBLEMS.append(pre + '05d: ما فيش شريط نجاح بعد النشر')
    co_shot(page, pre + '05d-after-approve.jpg')
    # —— ٠٦) أعِدها بملاحظات: ملاحظة جاهزة من العقل (دورة بلا سعر) + رفض المنصة + النجاح
    nav(page, '#s/courses/course/pc-16')
    page.click('[data-a="return"][data-id="pc-16"]')
    sheet(page)
    note = page.input_value('#co_note')
    if note != 'ينقص الدورة قبل النشر: بلا سعر.':
        PROBLEMS.append('%s06: الملاحظة الجاهزة %r' % (pre, note))
    co_shot(page, pre + '06-return-sheet.jpg')
    h.ef.forced[('POST', '/api/bridge/courses/pc-16/reject')] = (422, {'detail': 'رفضت المنصة الإعادة لأن الدورة تغيّرت للتو'})
    page.click('#co_go')
    page.wait_for_selector('#epModal .v2co-errbox')
    if 'رفضت المنصة' not in page.inner_text('#epModal .v2co-errbox'):
        PROBLEMS.append(pre + '06b: رسالة المنصة ما ظهرتش في الورقة')
    co_shot(page, pre + '06b-return-refused.jpg')
    del h.ef.forced[('POST', '/api/bridge/courses/pc-16/reject')]
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(700)
    rj = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/reject')]
    if len(rj) != 1 or rj[0][3] != {'note': 'ينقص الدورة قبل النشر: بلا سعر.'}:
        PROBLEMS.append('%s06c: نداء الرفض %r' % (pre, rj))
    # —— ٠٧) صفحة دورة منشورة + ورقة الإخفاء + ورقة عروض الأسعار
    nav(page, '#s/courses/course/pc-01')
    t = page.inner_text('.v2co')
    if 'غير متاح بعد' not in t or not page.query_selector('#co_bid'):
        PROBLEMS.append(pre + '07: صفحة المنشورة ناقصة (مبيعات «غير متاح بعد» · مفتاح العروض)')
    co_shot(page, pre + '07-course-published.jpg')
    page.click('[data-a="hide"]')
    sheet(page)
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    co_shot(page, pre + '07b-hide-sheet.jpg')
    close_sheet(page)
    page.click('#co_bid')
    sheet(page)
    co_shot(page, pre + '07c-bid-sheet.jpg')
    close_sheet(page)
    # —— ٠٨) الأرشفة والحذف
    page.click('[data-a="archive"]')
    sheet(page)
    co_shot(page, pre + '08-archive-sheet.jpg')
    close_sheet(page)
    nav(page, '#s/courses/course/pc-14')
    page.click('[data-a="delete"]')
    sheet(page)
    if not page.is_disabled('#co_go'):
        PROBLEMS.append(pre + '08b: زرّ الحذف شغّال قبل كتابة العنوان')
    page.fill('#co_t', 'حقوق المستهلك')
    page.wait_for_timeout(150)
    co_shot(page, pre + '08b-delete-sheet.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(900)
    dl = [c for c in h.platform_calls[n0:] if c[0] == 'DELETE']
    if len(dl) != 1 or (dl[0][2] or {}).get('hard') != 'true':
        PROBLEMS.append('%s08c: نداء الحذف %r' % (pre, dl))
    if not any(c['id'] != 'pc-14' for c in h.ef.courses) or any(c['id'] == 'pc-14' for c in h.ef.courses):
        PROBLEMS.append(pre + '08c: الدورة ما اتحذفتش من المنصة')
    co_shot(page, pre + '08c-after-delete.jpg')
    # —— ٠٤) «كل الدورات» وفلتر
    nav(page, '#s/courses/courses')
    if page.query_selector('.v2co[data-screen="list"]'):
        page.click('[data-a="board"]')       # بعد الحذف المؤسس واقف على «كل الدورات»
        page.wait_for_selector('.v2co[data-screen="board"]')
    if mobile:
        click_col(page, 'published', True)
    page.click('[data-a="all"]')
    page.wait_for_selector('.v2co[data-screen="list"]')
    co_shot(page, pre + '04-list.jpg')
    page.click('[data-a="filter"][data-f="building"]')
    page.wait_for_timeout(300)
    n = page.evaluate("() => document.querySelectorAll('.v2co-lrow').length")
    if n != 3:
        PROBLEMS.append('%s04b: فلتر «تحت البناء» عدّ %s بدل ٣ (مقاولات · أُعيدت · دليل المحامي بعد إعادتها)' % (pre, n))
    page.fill('#co_q', 'المقاولات')
    page.wait_for_timeout(300)
    if page.evaluate("() => document.querySelectorAll('.v2co-lrow').length") != 1:
        PROBLEMS.append(pre + '04b: البحث ما رشّحش')
    co_shot(page, pre + '04b-list-filter.jpg')
    # —— ٠٩) المدرّبون
    nav(page, '#s/courses/trainers')
    co_shot(page, pre + '09-trainers.jpg')
    if mobile:
        page.click('[data-a="trseg"][data-seg="list"]')
        page.wait_for_timeout(250)
        co_shot(page, pre + '09m-trainers-list.jpg')
        page.click('[data-a="trseg"][data-seg="apps"]')
        page.wait_for_timeout(250)
    page.click('[data-a="appopen"][data-id="ta-2"] >> nth=-1')
    sheet(page)
    co_shot(page, pre + '09d-application-detail.jpg')
    close_sheet(page)
    page.click('[data-a="appreject"][data-id="ta-2"]')
    sheet(page)
    if not page.is_disabled('#co_go'):
        PROBLEMS.append(pre + '09c: زرّ الرفض شغّال بلا سبب')
    page.fill('#co_why', 'الخبرة المذكورة لا تكفي لتدريب دورة كاملة')
    page.wait_for_timeout(150)
    co_shot(page, pre + '09c-reject-sheet.jpg')
    close_sheet(page)
    page.click('[data-a="appaccept"][data-id="ta-1"]')
    sheet(page)
    co_shot(page, pre + '09b-accept-sheet.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(900)
    ac = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/trainer-applications/ta-1/approve')]
    if len(ac) != 1:
        PROBLEMS.append('%s09b: نداء قبول المدرّب %r' % (pre, ac))
    co_shot(page, pre + '09f-after-accept.jpg')
    if mobile:
        page.click('[data-a="trseg"][data-seg="list"]')
        page.wait_for_timeout(250)
    page.click('.v2co-kebab summary >> nth=0')
    page.wait_for_timeout(200)
    co_shot(page, pre + '09g-trainer-menu.jpg')
    page.click('[data-a="tstop"] >> nth=0')
    sheet(page)
    if not page.is_disabled('#co_go'):
        PROBLEMS.append(pre + '09e: زرّ الإيقاف شغّال قبل كتابة البريد')
    co_shot(page, pre + '09e-stop-sheet.jpg')
    close_sheet(page)
    # —— ١٠) الدورات الحيّة
    nav(page, '#s/courses/live')
    lv = page.evaluate("() => ({tix: document.querySelectorAll('.v2co-t').length, rows: document.querySelectorAll('.v2co-lv').length, main: [...document.querySelectorAll('.v2co-t .v2co-btn1')].map(b => b.textContent.trim())})")
    if lv['tix'] != 1 or lv['rows'] != 2 or lv['main'] != ['مدّد ٤٨ ساعة']:
        PROBLEMS.append('%s10: الدورات الحيّة %r' % (pre, lv))
    co_shot(page, pre + '10-live.jpg')
    page.click('[data-a="live-edit"][data-slug="commercial-contracts-live"] >> nth=0')
    sheet(page)
    page.fill('#co_zl', 'https://meet.test/commercial')
    page.check('#co_pin')
    co_shot(page, pre + '10c-schedule-sheet-1.jpg')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-diff')
    co_shot(page, pre + '10c-schedule-sheet-2.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(900)
    sc = [c for c in h.platform_calls[n0:] if c[0] == 'PUT' and c[1].endswith('/schedule')]
    if len(sc) != 1 or sc[0][3].get('confirmed') is not True or sc[0][3].get('zoom_link') != 'https://meet.test/commercial' or 'pin_schedule' in sc[0][3]:
        PROBLEMS.append('%s10c: نداء الموعد %r' % (pre, sc))
    co_shot(page, pre + '10d-after-schedule.jpg')
    page.click('[data-a="live-who"][data-slug="commercial-contracts-live"] >> nth=0')
    sheet(page)
    co_shot(page, pre + '10e-who-reserved.jpg')
    close_sheet(page)
    page.click('[data-a="live-cancel"]')
    sheet(page)
    page.click('#co_next')
    page.wait_for_selector('#co_t')
    if not page.is_disabled('#co_go'):
        PROBLEMS.append(pre + '10b: زرّ الإلغاء شغّال قبل كتابة العنوان')
    page.fill('#co_t', 'ورشة العقود التجارية')
    page.wait_for_timeout(150)
    co_shot(page, pre + '10b-cancel-sheet.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_selector('#co_done', timeout=15000)
    cn = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/live/commercial-contracts-live/decide')]
    if len(cn) != 1 or cn[0][3].get('action') != 'cancel':
        PROBLEMS.append('%s10b: نداء الإلغاء %r' % (pre, cn))
    if 'شخصان يحتاجان استردادًا يدويًا' not in page.inner_text('#epModal .v2co-m') or 'لم نجد دفعة' not in page.inner_text('#epModal .v2co-m'):
        PROBLEMS.append(pre + '10b2: قائمة الاسترداد ناقصة')
    co_shot(page, pre + '10b2-cancel-result.jpg')
    page.click('#co_done')
    page.wait_for_timeout(900)
    # —— ١١) ما يطلبه الناس
    nav(page, '#s/courses/demand')
    dm = page.evaluate("() => ({tix: document.querySelectorAll('.v2co-t').length, bars: document.querySelectorAll('.v2co-bars li').length, qs: document.querySelectorAll('.v2co-qs li').length,\n      top: (document.querySelector('.v2co-sum')||{}).textContent})")
    if dm['tix'] != 5 or dm['bars'] != 3 or dm['qs'] != 3:
        PROBLEMS.append('%s11: ما يطلبه الناس %r' % (pre, dm))
    co_shot(page, pre + '11-demand.jpg')
    page.click('[data-a="mk"] >> nth=0')
    sheet(page)
    if page.input_value('#co_ti') != 'دورة في عقود':
        PROBLEMS.append(pre + '11c: العنوان الجاهز من أسئلة الشات %r' % page.input_value('#co_ti'))
    co_shot(page, pre + '11c-create-prefilled.jpg')
    close_sheet(page)
    page.click('[data-a="prog-accept"] >> nth=0')
    sheet(page)
    co_shot(page, pre + '11b-program-accept.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(800)
    if len([c for c in h.platform_calls[n0:] if c[0] == 'POST' and '/program-requests/' in c[1]]) != 1:
        PROBLEMS.append(pre + '11b: نداء قبول الطلب')
    # —— ١٢) عروض الأسعار
    nav(page, '#s/courses/offers')
    co_shot(page, pre + '12-offers.jpg')
    page.click('[data-a="offer-counter"][data-id="co-2"]')
    sheet(page)
    page.fill('#co_am', '100')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-errbox')
    if 'لا يقل المبلغ' not in page.inner_text('#epModal .v2co-errbox'):
        PROBLEMS.append(pre + '12b: رسالة ما تحت الحد الأدنى')
    co_shot(page, pre + '12b-counter-below-floor.jpg')
    page.fill('#co_am', '320')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    co_shot(page, pre + '12c-counter-review.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(800)
    of = [c for c in h.platform_calls[n0:] if c[1].endswith('/course-offers/co-2/decide')]
    if len(of) != 1 or of[0][3] != {'decision': 'counter', 'amount': 320.0}:
        PROBLEMS.append('%s12c: نداء العرض المقابل %r' % (pre, of))
    page.click('[data-a="offer-accept"][data-id="co-1"]')
    sheet(page)
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    co_shot(page, pre + '12d-accept-offer-2.jpg')
    close_sheet(page)
    # —— ١٣) أنشئ دورة
    nav(page, '#s/courses/courses')
    page.click('[data-a="create"]')
    sheet(page)
    page.fill('#co_ti', 'دورة العقود الذكية للمبتدئين')
    co_shot(page, pre + '13-create-sheet-1.jpg')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    co_shot(page, pre + '13b-create-sheet-2.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => location.hash.indexOf('#s/courses/course/') === 0", timeout=10000)
    page.wait_for_timeout(900)
    cr = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1] == '/api/bridge/courses']
    if len(cr) != 1 or cr[0][3].get('is_active') is not False or any(k.startswith('price') for k in cr[0][3]) or cr[0][3].get('platform_owned') is not True:
        PROBLEMS.append('%s13: نداء الإنشاء %r' % (pre, cr))
    if 'مسودة' not in page.inner_text('.v2co-ok') or 'الفلوس' not in page.inner_text('.v2co-ok'):
        PROBLEMS.append(pre + '13c: شريط النجاح لازم يذكر المسودة وسعرها في «الفلوس»')
    co_shot(page, pre + '13c-after-create.jpg')
    nav(page, '#s/courses/courses')
    if mobile:
        click_col(page, 'building', True)
    if not page.query_selector('.v2co-bc >> text=دورة العقود الذكية للمبتدئين'):
        PROBLEMS.append(pre + '13c: الدورة الجديدة ما ظهرتش في «تحت البناء»')
    co_shot(page, pre + '13d-board-after-create.jpg')
    writes_ok(reqs, pre + 'main')
    # —— ١٤) «كل السجلات»
    h.ef = cf.CoursesPlatform(with_abc=False)      # منصة نظيفة: فيها دورة في المراجعة للكتالوج القديم
    page2 = open_legacy(ctx)
    legacy_check(page2, pre + '14')
    co_shot(page2, pre + '14-all-records.jpg')
    legacy_flow(page2, pre)
    # —— ١٥) الدخول من اللوحة والروابط القديمة
    entry_flow(ctx, pre)
    browser.close()


def open_legacy(ctx):
    page = ctx.new_page()
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.goto(DASH + '/#s/courses/all', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function("() => document.querySelector('.v2co-legacy #cTabs')", timeout=30000)
    page.wait_for_timeout(900)
    return page


def legacy_flow(page, pre):
    page.click('.v2co-legacy #cTabs .tab[data-t="platform"]')
    page.wait_for_selector('.v2co-legacy .row[data-pc]')
    page.click('.v2co-legacy .row[data-pc] >> nth=0')
    page.wait_for_timeout(500)
    legacy_check(page, pre + '14a')
    co_shot(page, pre + '14a-catalog-drawer.jpg')
    # أي صف في المراجعة ما فيهوش زرّ نشر/رفض
    idx = page.evaluate("() => [...document.querySelectorAll('.v2co-legacy .row[data-pc]')].findIndex(r => /بانتظار الاعتماد/.test(r.innerText))")
    if idx < 0:
        PROBLEMS.append(pre + '14a: ما لقيناش صف دورة في المراجعة في الكتالوج')
    else:
        page.click('.v2co-legacy .row[data-pc] >> nth=%d' % idx)
        page.wait_for_timeout(400)
        legacy_check(page, pre + '14a-review-row')
    # مودال قديم (المنهج والمحاضرات)
    page.click('.v2co-legacy .row[data-pc] >> nth=0')
    page.wait_for_timeout(300)
    btn = page.query_selector('.v2co-legacy [data-a="pcvideo"]')
    if btn is None:
        PROBLEMS.append(pre + '14b: زرّ «المنهج والمحاضرات» مش ظاهر')
        return
    btn.click()
    page.wait_for_selector('#epModal', timeout=10000)
    page.wait_for_timeout(700)
    legacy_check(page, pre + '14b')
    page.screenshot(path=os.path.join(OUT, pre + '14b-old-modal.jpg'), type='jpeg', quality=82)
    SHOTS.append(pre + '14b-old-modal.jpg')
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")


def entry_flow(ctx, pre):
    """١٥) مربّع اللوحة · بطاقة القرار · الرابط القديم #courses · حالة المدرّبين القديمة."""
    page = ctx.new_page()
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2_ON === true && window.EP && ['opsQueue','inbox'].every(k => EP.state[k] === 'ready') && document.querySelector('.v2-tile')", timeout=30000)
    page.wait_for_timeout(600)
    tile = page.query_selector('.v2-tile[data-tile="courses"]')
    if tile is None:
        PROBLEMS.append(pre + '15: مربّع الدورات مش موجود في اللوحة')
    else:
        tile.click()
        wait_co(page)
        if '#s/courses/' not in page.url or page.query_selector('.v2co') is None:
            PROBLEMS.append('%s15: مربّع الدورات ما هبطش على شاشة جديدة في القسم: %s' % (pre, page.url))
        co_shot(page, pre + '15-home-tile.jpg')
    nav(page, '#courses')
    if page.evaluate("() => location.hash") != '#s/courses/courses' or page.query_selector('.v2co[data-screen="board"]') is None:
        PROBLEMS.append(pre + '15: #courses ما هبطش على اللوحة')
    page.evaluate("() => { goOps('team', OPSQ_LANDINGS.trainer_applications_pending); }")
    page.wait_for_function("() => document.querySelector('.v2co[data-screen=\"trainers\"]')", timeout=10000)
    page.wait_for_timeout(500)
    if page.evaluate("() => location.hash") != '#s/courses/trainers':
        PROBLEMS.append('%s15: حالة المدرّبين القديمة ما هبطتش على تبويب المدرّبون: %s' % (pre, page.evaluate("() => location.hash")))
    page.evaluate("() => { goOps('courses', OPSQ_LANDINGS.live_needs_decision); }")
    page.wait_for_function("() => document.querySelector('.v2co[data-screen=\"live\"]')", timeout=10000)
    page.evaluate("() => { goOps('courses', OPSQ_LANDINGS.courses_pending); }")
    page.wait_for_function("() => document.querySelector('.v2co[data-screen=\"board\"]')", timeout=10000)
    page.evaluate("() => { goOps('courses', OPSQ_LANDINGS.course_interests_24h); }")
    page.wait_for_function("() => document.querySelector('.v2co[data-screen=\"demand\"]')", timeout=10000)
    if page.evaluate("() => location.hash") != '#s/courses/demand':
        PROBLEMS.append('%s15: رابط «الطلب على الدورات» القديم هبط على %s' % (pre, page.evaluate("() => location.hash")))


# ======================================================================= بعد الإضافات أ/ب/ج
def flow_abc(browser, h, pre, vp, mobile):
    h.ef = cf.CoursesPlatform(with_abc=True)
    ctx = browser.context(h, 'admin', vp, mobile)
    reqs = []
    page = open_co(ctx, '#s/courses/courses', reqs, ms=1500)
    info = page.evaluate("""() => ({imgs: document.querySelectorAll('.v2co-img').length, timers: [...document.querySelectorAll('.v2co-col[data-col="review"] .v2co-time')].map(t => [t.textContent.trim(), t.className]),
      main: [...document.querySelectorAll('.v2co-col[data-col="review"] .v2co-t')].map(t => [t.querySelector('.v2co-btn1').textContent.trim(), t.classList.contains('first')])})""")
    if info['imgs'] < 3:
        PROBLEMS.append('%s01-abc: الصور ما ظهرتش (%s)' % (pre, info['imgs']))
    if sorted(m[0] for m in info['main']) != sorted(['انشرها', 'أعِدها بملاحظات']):
        PROBLEMS.append('%s01-abc: أزرار التذاكر %r' % (pre, info['main']))
    if not any(m[1] for m in info['main']):
        PROBLEMS.append(pre + '01-abc: أقدم تذكرة لازم تاخد الإطار العنّابي')
    if any('tone-ok' not in t[1] and 'tone-warn' not in t[1] and 'tone-late' not in t[1] for t in info['timers']):
        PROBLEMS.append('%s01-abc: عدّاد submitted_at لازم يتلوّن %r' % (pre, info['timers']))
    co_shot(page, pre + '01-board-abc.jpg')
    if mobile:
        click_col(page, 'published', True)
        co_shot(page, pre + '01m-published-abc.jpg')
        click_col(page, 'review', True)
    nav(page, '#s/courses/course/pc-15', 1200)
    ck = page.inner_text('.v2co-chk')
    if 'فيديو تعريفي مرفوع' not in ck:
        PROBLEMS.append(pre + '05-abc: بنود فحص المنصة ما ظهرتش')
    co_shot(page, pre + '05-course-review-abc.jpg')
    page.click('.v2co-pgside [data-a="approve"]')
    sheet(page)
    if not page.query_selector('input[name="co_pm"]'):
        PROBLEMS.append(pre + '05b-abc: اختيار طريقة الدفع لازم يظهر لدورة مدرّب')
    co_shot(page, pre + '05b-approve-sheet-1-abc.jpg')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    co_shot(page, pre + '05c-approve-sheet-2-abc.jpg')
    n0 = len(h.platform_calls)
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(900)
    sent = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/approve')]
    if len(sent) != 1 or sent[0][3] != {'payout_model': 'share'}:
        PROBLEMS.append('%s05d-abc: نداء النشر %r' % (pre, sent))
    co_shot(page, pre + '05d-after-approve-abc.jpg')
    nav(page, '#s/courses/course/pc-16', 1200)
    co_shot(page, pre + '06-course-review-return-abc.jpg')
    nav(page, '#s/courses/course/pc-02', 1200)
    if 'غير متاح بعد' in page.inner_text('.v2co-tiles'):
        PROBLEMS.append(pre + '07-abc: المبيعات ما ظهرتش مع وجود المصدر')
    co_shot(page, pre + '07-course-published-abc.jpg')
    nav(page, '#s/courses/course/pc-09', 1200)
    co_shot(page, pre + '07-course-live-abc.jpg')
    writes_ok(reqs, pre + 'abc')
    browser.close()


# ======================================================================= الدورات والمصدر واقع · المفتاح مقفول
def flow_down(browser, h, pre, vp, mobile):
    h.ef = cf.CoursesPlatform(with_abc=False)
    h.ef.down.add('/api/bridge/courses')
    ctx = browser.context(h, 'admin', vp, mobile)
    page = ctx.new_page()
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.goto(DASH + '/#s/courses/courses', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function("() => /غير متاح بعد/.test((document.querySelector('.v2co')||{innerText:''}).innerText) && document.querySelector('.v2co-trcol')", timeout=30000)
    page.wait_for_timeout(700)
    t = page.inner_text('.v2co')
    if 'الدورات: غير متاح بعد' not in t or 'أعد المحاولة' not in t or not page.query_selector('.v2co-tm'):
        PROBLEMS.append('%s02: لقطة المصدر الواقع ناقصة (غير متاح · أعد المحاولة · بطاقة المدرّبين حيّة)' % pre)
    co_shot(page, pre + '02-board-source-down.jpg')
    browser.close()


def flow_off(browser, h, pre, vp, mobile):
    h.ef = cf.CoursesPlatform(with_abc=False)
    os.environ['DASH_V2_ENABLED'] = 'false'
    try:
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#courses', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.authed", timeout=30000)
        page.wait_for_timeout(2500)
        page.wait_for_function("() => document.querySelector('#cTabs')", timeout=20000)
        r = page.evaluate("() => ({v2: !!window.V2_ON, co: !!document.querySelector('[class*=\"v2co-\"]'), shell: document.querySelector('.app').classList.contains('v2-shell'), rail: !!document.querySelector('.rail .nav .item'), sec: window.V2SEC ? V2SEC.take('courses', document.getElementById('view')) : 'none'})")
        if r['v2'] or r['co'] or r['shell'] or not r['rail'] or r['sec'] not in (False, 'none'):
            PROBLEMS.append('%s16: المفتاح مقفول لازم الشاشة القديمة بالحرف: %r' % (pre, r))
        vs.shot(page, pre + '16-flag-off.jpg')
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const [m, p] of [['GET', '/api/v2/courses/stats'], ['GET', '/api/v2/courses/pc-1/checklist'], ['POST', '/api/v2/courses/create'], ['POST', '/api/v2/courses/pc-1/approve'],
                                ['POST', '/api/v2/courses/live/x/decide'], ['POST', '/api/v2/courses/offers/o/decide']]) {
            const x = await fetch(p, {method: m, headers: {Authorization: 'Bearer ' + t, 'Content-Type': 'application/json'}, body: m === 'POST' ? '{"confirmed":true}' : undefined});
            if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        if bad:
            PROBLEMS.append('%s16: مسارات الدورات الجديدة والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    global OLD_NAVY, OLD_GOLD
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(cf.CoursesPlatform(with_abc=False))
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        # ألوان الأزرق والذهبي القديمين من `:root` قبل ما الإطار يتحمّل
        ctx = browser.context(h, 'admin', DESK, False)
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_timeout(500)
        cols = page.evaluate("""() => { const d = document.createElement('i'); d.style.color = 'var(--navy)'; document.body.appendChild(d); const a = getComputedStyle(d).color;
          d.style.color = 'var(--gold)'; const b = getComputedStyle(d).color; d.remove(); return [a, b]; }""")
        OLD_NAVY, OLD_GOLD = cols
        browser.close()
        try:
            for pre, vp, mobile in (('d', DESK, False), ('t', TAB, False), ('m', MOB, True)):
                flow_main(browser, h, pre, vp, mobile)
                flow_abc(browser, h, pre, vp, mobile)
                flow_down(browser, h, pre, vp, mobile)
                flow_off(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': len(SHOTS), 'names': SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
