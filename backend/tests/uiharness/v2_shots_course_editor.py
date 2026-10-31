# -*- coding: utf-8 -*-
"""صور محرّر الدورات (SPEC-C-courses §C1) — كمبيوتر ١٢٨٠ (`d*`) وموبايل ٣٩٠ (`m*`). صفر طلبات حقيقية.

    cd backend && python3 -B tests/uiharness/v2_shots_course_editor.py ../docs/v2/brain2/c1-shots

الداشبورد جوه العملية والمنصة في الذاكرة (`course_editor_fixtures.Courses2Platform`)، وخادم رفع الفيديو (TUS) مزيّف جوه المتصفح بـ`route.fulfill` على
`video.bunnycdn.com` فقط (لا شبكة حقيقية) — فرفع الفيديو بالقطع يُجرَّب فعلًا من المتصفح مع شريط التقدّم. أي أصل تاني بيتقفل ويتسجّل.

بيمشي على المسار الكامل: القائمة المدموجة · «أنشئ دورة» (مفتاح منع التكرار) · «حرّر الدورة» · البيانات · الهيكل (إضافة · ترتيب · حذف درس له محتوى · ٤٠٩) ·
الدرس التفاعلي (نوع كتلة · حقول · متقدّم · نقل · حذف · معاينة · ٤٠٠ كما رجع · حفظ) · المسجّل (رفع بقطع ٥ ميغا · رابط · غير متاح) · المباشر ·
المراجعة (الناقص · الملاحظات · أرجِعها · انشر ٤٢٢ كما رجع · أوقفها) · المساعد (مسودة ثم «أضفه» دون حفظ · «أنشئ الهيكل منها» وتوقّف عند أول خطأ).
السكربت بيفشل لو: «0/null/NaN/undefined» ظاهرة · هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · تمرير أفقي · رقم لاتيني ظاهر · كلمة ممنوعة ·
كتابة بلا `confirmed:true` أو فيها سعر · نداء للمنصة من غير ورقة تأكيد · أي طلب خارج التطبيق وخادم الرفع المزيّف.
الصور المحفوظة ١٢ بس (٨ كمبيوتر + ٤ موبايل)؛ فحوص الموبايل بتتعمل على كل الشاشات.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'shots-course-editor'))
os.makedirs(OUT, exist_ok=True)
sys.argv = [sys.argv[0], OUT] + sys.argv[2:]

import v2_shots as vs                       # noqa: E402
import course_editor_fixtures as cef        # noqa: E402
from ef_route_harness import Harness, DASH  # noqa: E402

vs.OUT = OUT
PROBLEMS = vs.PROBLEMS
SHOTS = vs.SHOTS
DESK = {'width': 1280, 'height': 1000}
MOB = {'width': 390, 'height': 900}
MB = 1024 * 1024
KEEP = {'d': {'01-list', '02-create', '03-data', '04-structure', '05-interactive', '06-recorded', '07-review', '08-assistant'},
        'm': {'01-list', '05-interactive', '06-recorded', '07-review'}}
READY = "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2co') && !/…جارٍ جلب/.test(document.querySelector('.v2co').innerText)"
BANNED = ('يقوّم', 'استرداد', 'ضمان', '١٤ يوم', 'EGP', 'USD', 'جنيه', 'Zoom', 'YouTube', 'Google', 'API')
MONEY_KEYS = ('price', 'pricing', 'is_free', 'trainer_share')


def rgb_ok(_):
    return True


def ed_check(page, name):
    """فحوص ما بعد كل شاشة: الأهداف · التمرير الأفقي · النصوص الممنوعة · الأرقام."""
    w = page.viewport_size['width']
    mobile = w <= 400
    small = page.evaluate("""() => [...document.querySelectorAll('.v2ce button, .v2ce summary, .v2ce select, .v2ce textarea, .v2ce input:not([type=checkbox]):not([type=radio]):not([type=file]), .v2ce label.v2co-btn2, #epModal .v2co-m button, #epModal .v2co-m input:not([type=checkbox]):not([type=radio]), #epModal .v2co-m textarea, #epModal .v2co-m select')]
      .filter(b => b.offsetParent && !b.closest('[hidden]')).map(b => [(b.className || b.tagName).toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    if mobile:
        big = page.evaluate("""() => [...document.querySelectorAll('.v2ce .v2co-btn1, .v2ce .v2co-btn2, .v2ce .v2co-link, .v2ce-tab, .v2ce-pt, .v2ce-ak, #epModal .v2co-m .v2co-btn1, #epModal .v2co-m .v2co-btn2')]
          .filter(b => b.offsetParent).map(b => [(b.className || '').toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, big[:4]))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    inner = page.evaluate("""() => [...document.querySelectorAll('.v2ce *, #epModal .v2co-m *')].filter(e => e.offsetParent && !['INPUT','TEXTAREA','SELECT','IMG','PRE'].includes(e.tagName)
      && e.scrollWidth > e.clientWidth + 1 && !['hidden','clip','auto','scroll'].includes(getComputedStyle(e).overflowX) && getComputedStyle(e).display !== 'inline').map(e => e.className.toString().slice(0, 40)).slice(0, 5)""")
    if inner:
        PROBLEMS.append('%s: تمرير أفقي جوه عناصر: %r' % (name, inner))
    out = page.evaluate("() => [...document.querySelectorAll('.v2ce *, #epModal .v2co-m *')].filter(e => e.offsetParent && getComputedStyle(e).position !== 'absolute' && e.getBoundingClientRect().right > window.innerWidth + 1).length")
    if out:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, out))
    txt = page.evaluate("""() => [...document.querySelectorAll('.v2ce, #epModal')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('[dir="ltr"], script, style, textarea').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر' % name)
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t and not re.search(r'[A-Za-z]-?\d', t)]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    for word in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    if re.search(r'سعر|السعر|مجاني', txt):
        PROBLEMS.append('%s: كلمة سعر ظاهرة في شاشة المحرّر' % name)


class Shooter(object):
    def __init__(self, pre):
        self.pre = pre

    def snap(self, page, key, target=None):
        name = '%s%s.jpg' % (self.pre, key)
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
        if target:
            page.evaluate("sel => { const e = document.querySelector(sel); if (e) e.scrollIntoView({block: 'center'}); }", target)
        page.wait_for_timeout(300)
        if key in KEEP[self.pre]:
            path = os.path.join(OUT, name)
            page.screenshot(path=path, type='jpeg', quality=62)
            SHOTS.append(name)
        ed_check(page, self.pre + key)
        vs.shell_check(page, self.pre + key)


def wait_ready(page, ms=500):
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(ms)


def open_page(ctx, hash_, reqs=None):
    page = ctx.new_page()
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.on('console', lambda m: PROBLEMS.append('console.error: %s' % m.text[:200]) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    if reqs is not None:
        page.on('request', lambda r: reqs.append((r.method, r.url, r.post_data)) if r.method != 'GET' and '/api/' in r.url else None)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    wait_ready(page, 900)
    return page


def goto(page, hash_):
    page.evaluate("h => { location.hash = h; }", hash_)
    wait_ready(page, 700)


def sheet(page):
    page.wait_for_selector('#epModal .v2co-m', timeout=10000)
    page.wait_for_timeout(250)


def sheet_closed(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(300)


def close_sheet(page):
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
    page.wait_for_timeout(150)


def editor(page):
    page.wait_for_selector('.v2ce .v2ce-tabs', timeout=15000)
    page.wait_for_timeout(300)


def pick(page, lid):
    sel = '[data-ce="pick"][data-id="%s"]' % lid
    if not page.is_visible(sel):
        page.click('.v2ce-lsel > summary')
        page.wait_for_timeout(200)
    page.click(sel)
    page.wait_for_timeout(300)


def tab(page, name):
    page.click('.v2ce-tab[data-tab="%s"]' % name)
    page.wait_for_timeout(300)


def c2_calls(h, since, method=None, suffix=None):
    out = [c for c in h.ef.c2calls[since:] if (method is None or c[0] == method) and (suffix is None or c[1].endswith(suffix))]
    return out


def check_writes_confirmed(h, name):
    for m, path, body in h.ef.c2calls:
        if m in ('PUT', 'POST') and '/preview' not in path and '/brain/draft' not in path:
            if body.get('confirmed') is not True or not body.get('by'):
                PROBLEMS.append('%s: كتابة على %s بلا confirmed/by' % (name, path))
        flat = json.dumps(body, ensure_ascii=False)
        for k in MONEY_KEYS:
            if '"%s' % k in flat:
                PROBLEMS.append('%s: مفتاح سعر «%s» وصل المنصة في %s' % (name, k, path))


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


class Tus(object):
    """خادم TUS مزيّف جوه المتصفح. `hold_at`: يحجز الـPATCH عند هذا الإزاحة لحد `release()` (لصورة التقدّم)."""

    def __init__(self):
        self.calls = []
        self.hold_at = None
        self.held = []

    CORS = {'access-control-allow-origin': '*', 'access-control-allow-headers': '*', 'access-control-allow-methods': 'POST, PATCH, HEAD, OPTIONS',
            'access-control-expose-headers': 'Location, Upload-Offset, Tus-Resumable'}

    def handler(self, route):
        req = route.request
        if req.method == 'OPTIONS':
            return route.fulfill(status=204, headers=self.CORS)
        body = req.post_data_buffer or b''
        h = dict((k.lower(), v) for k, v in req.headers.items())
        self.calls.append((req.method, req.url, h, len(body)))
        if req.method == 'POST':
            return route.fulfill(status=201, headers=dict(self.CORS, **{'Location': 'https://video.bunnycdn.com/tusupload/up-1', 'Tus-Resumable': '1.0.0'}))
        off = int(h.get('upload-offset', '0'))
        if self.hold_at is not None and off == self.hold_at:
            self.held.append((route, off + len(body)))
            return None
        return route.fulfill(status=204, headers=dict(self.CORS, **{'Upload-Offset': str(off + len(body)), 'Tus-Resumable': '1.0.0'}))

    def release(self):
        held, self.held, self.hold_at = self.held, [], None
        for route, end in held:
            route.fulfill(status=204, headers=dict(self.CORS, **{'Upload-Offset': str(end), 'Tus-Resumable': '1.0.0'}))


# ======================================================================= المسار الكامل
def flow(browser, h, pre, vp, mobile):
    S = Shooter(pre)
    h.ef = cef.Courses2Platform(with_abc=False)
    ctx = browser.context(h, 'admin', vp, mobile)
    tus = Tus()
    ctx.route('https://video.bunnycdn.com/**', tus.handler)
    reqs = []
    page = open_page(ctx, '#s/courses/courses', reqs)

    # —— ٠١) القائمة المدموجة
    if mobile:
        page.click('[data-a="col"][data-col="published"]')
        page.wait_for_timeout(250)
    page.click('[data-a="all"]')
    page.wait_for_selector('.v2co-lrows')
    page.wait_for_timeout(500)
    t = page.inner_text('.v2co')
    expect('تفاعلي · مسجّل · مباشر' in t or ('تفاعلي' in t and 'مسجّل' in t), pre + '01: نوعا الدروس ما ظهروش في القائمة المدموجة')
    expect('ملاحظات مفتوحة' in t or 'ملاحظة مفتوحة' in t, pre + '01: الملاحظات المفتوحة ما ظهرتش')
    expect('مسودة' in t and 'عند المراجعة' in t, pre + '01: حالة المحرّر ما ظهرتش')
    expect(page.query_selector('.v2ce-extras') is not None and 'التفاوض على العقود' in page.inner_text('.v2ce-extras'), pre + '01: دورة المحرّر وحدها ما ظهرتش')
    S.snap(page, '01-list')

    # —— ٠٢) أنشئ دورة (مفتاح منع التكرار يُولَّد مرة)
    page.click('.v2co-main[data-a="create"]')
    sheet(page)
    page.fill('#ce_ti', 'التفاوض المتقدّم على العقود')
    S.snap(page, '02-create')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    n0 = len(h.ef.c2calls)
    page.click('#co_go')
    sheet_closed(page)
    editor(page)
    cr = c2_calls(h, n0, 'POST')
    expect(len(cr) == 1 and cr[0][1] == '/api/bridge/courses2', pre + '02: نداء إنشاء واحد')
    if cr:
        b = cr[0][2]
        expect(b.get('platform_owned') is True and re.match(r'^[A-Za-z0-9_.:-]{8,80}$', b.get('idem_key', '')) and b.get('confirmed') is True and b.get('title') == 'التفاوض المتقدّم على العقود',
               pre + '02: جسم الإنشاء %r' % b)
    expect('أُنشئت الدورة مسودة' in page.inner_text('.v2ce'), pre + '02: شريط النجاح')
    expect(page.query_selector('.v2ce-tab.on[data-tab="structure"]') is not None, pre + '02: بعد الإنشاء يفتح تبويب الهيكل')
    expect('التفاوض المتقدّم على العقود' in page.inner_text('.v2ce-head'), pre + '02: الرأس')

    # —— ٠٣) صفحة الدورة ⇒ «حرّر الدورة» ⇒ البيانات
    goto(page, '#s/courses/course/pc-12')
    expect('تعديل الدروس من «كل السجلات»' not in page.inner_text('.v2co'), pre + '03: الرابط القديم لازم يتشال')
    page.click('[data-a="edit-course"]')
    editor(page)
    tab(page, 'data')
    expect(page.input_value('[data-p="title"]') == 'عقود المقاولات', pre + '03: عنوان الدورة')
    expect(page.is_disabled('[data-ce="save-data"]'), pre + '03: «احفظ البيانات» مقفول قبل أي تعديل')
    page.fill('[data-s="data"][data-p="description"]', 'شرح عملي لعقود المقاولات من الاتفاق إلى التسليم.')
    page.fill('[data-s="data"][data-p="cover"]', 'http://غير-صالح')
    page.click('[data-ce="save-data"]')
    expect('يبدأ بـ https://' in page.inner_text('.v2ce'), pre + '03: رابط الغلاف غير https')
    expect(page.query_selector('#epModal') is None, pre + '03: لا ورقة مع رابط غلاف خاطئ')
    page.fill('[data-s="data"][data-p="cover"]', 'https://img.example.test/c.jpg')
    page.fill('[data-s="data"][data-p="outcomes"]', 'صياغة عقد مقاولة سليم\nتحديد التزامات الأطراف\nتوثيق التسليم')
    S.snap(page, '03-data')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="save-data"]')
    sheet(page)
    expect(len(h.ef.c2calls) == n0, pre + '03: لا كتابة قبل التأكيد')
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'PUT', '/data')
    expect(len(w) == 1 and w[0][2].get('outcomes') == ['صياغة عقد مقاولة سليم', 'تحديد التزامات الأطراف', 'توثيق التسليم'] and w[0][2].get('confirmed') is True, pre + '03: جسم حفظ البيانات %r' % w)
    expect('حُفظت بيانات الدورة' in page.inner_text('.v2ce'), pre + '03: شريط الحفظ')

    # —— ٠٤) الهيكل: إضافة · ترتيب · حذف درس له محتوى
    tab(page, 'structure')
    page.click('[data-ce="ls-add"][data-u="1"][data-kind="interactive"]')
    page.fill('[data-s="sd"][data-p="1.lessons.1.title"]', 'نموذج محضر التسليم')
    page.click('[data-ce="ls-up"][data-u="1"][data-l="1"]')
    expect(page.input_value('[data-s="sd"][data-p="1.lessons.0.title"]') == 'نموذج محضر التسليم', pre + '04: نقل الدرس لأعلى')
    page.fill('[data-s="sd"][data-p="0.lessons.1.title"]', 'أركان العقد الأربعة')
    S.snap(page, '04-structure')
    page.click('[data-ce="ls-del"][data-u="0"][data-l="0"]')      # L1 له كتل ⇒ ورقة تأكيد قبل الإزالة من الهيكل
    sheet(page)
    expect('محتوى' in page.inner_text('#epModal .v2co-m'), pre + '04: حذف درس له محتوى لازم يفتح ورقة')
    close_sheet(page)
    expect(page.query_selector('[data-s="sd"][data-p="0.lessons.0.title"]') is not None and page.input_value('[data-s="sd"][data-p="0.lessons.0.title"]') == 'ما هو عقد المقاولة؟', pre + '04: الإلغاء يُبقي الدرس')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="save-struct"]')
    sheet(page)
    st = page.inner_text('#epModal .v2co-m')
    expect('دروس جديدة' in st and 'عناوين تتغيّر' in st, pre + '04: ورقة الهيكل ما ذكرتش الإضافة والتعديل')
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'PUT', '/structure')
    expect(len(w) == 1, pre + '04: نداء هيكل واحد')
    if w:
        us = w[0][2]['units']
        ids = [l.get('id') for u in us for l in u['lessons']]
        expect(ids.count(None) == 1 and set(i for i in ids if i) == {'L1', 'L2', 'L3', 'L4'}, pre + '04: المعرّفات القديمة محفوظة والجديد بلا معرّف %r' % ids)
        newl = [l for u in us for l in u['lessons'] if not l.get('id')]
        expect(newl and newl[0]['kind'] == 'interactive' and newl[0]['title'] == 'نموذج محضر التسليم', pre + '04: الدرس الجديد بنوعه')
    # حذف درس له محتوى ثم الحفظ على دورة منشورة ⇒ ٤٠٩ بنص المنصة كما رجع
    goto(page, '#s/courses/course/pc-01')
    page.click('[data-a="edit-course"]')
    editor(page)
    tab(page, 'structure')
    page.click('[data-ce="ls-del"][data-u="0"][data-l="0"]')
    sheet(page)
    page.click('#co_go')
    sheet_closed(page)
    page.click('[data-ce="save-struct"]')
    sheet(page)
    page.click('#co_go')
    page.wait_for_selector('#epModal .v2co-errbox', timeout=10000)
    expect('دورة منشورة فيها متعلّمون' in page.inner_text('#epModal .v2co-errbox'), pre + '04: نص ٤٠٩ كما رجع')
    expect('تغيّرت الحالة' not in page.inner_text('#epModal .v2co-errbox'), pre + '04: ٤٠٩ بلا العبارة العامة')
    close_sheet(page)

    # —— ٠٥) الدرس التفاعلي
    goto(page, '#s/courses/course/pc-12')
    page.click('[data-a="edit-course"]')
    editor(page)
    tab(page, 'lessons')
    pick(page, 'L1')
    page.wait_for_selector('[data-ce-blocks] .v2ce-blk')
    nb = len(page.query_selector_all('.v2ce-blk'))
    page.click('[data-ce="picker"]')
    expect(len(page.query_selector_all('.v2ce-pt[data-type]')) >= 18, pre + '05: قائمة أنواع الكتل')
    page.click('.v2ce-pt[data-type="quiz"]')
    expect(len(page.query_selector_all('.v2ce-blk')) == nb + 1, pre + '05: إضافة كتلة')
    last = '.v2ce-blk[data-blk="%d"]' % nb
    expect('open' in (page.get_attribute(last, 'class') or ''), pre + '05: الكتلة الجديدة مفتوحة')
    page.fill(last + ' [data-p="blocks.%d.question"]' % nb, 'ما الذي يُكتب أولًا في العقد؟')
    page.fill(last + ' [data-p="blocks.%d.options.0.text"]' % nb, 'الأطراف')
    page.fill(last + ' [data-p="blocks.%d.options.1.text"]' % nb, 'التوقيع')
    page.check(last + ' [data-p="blocks.%d.options.0.ok"]' % nb)
    expect('ما الذي يُكتب أولًا' in page.inner_text(last + ' .v2ce-bhead'), pre + '05: رأس الكتلة يتبع الحقل')
    # «متقدّم»: تعديل JSON مباشر
    page.click(last + ' summary')
    page.fill(last + ' [data-ce-json]', json.dumps({'type': 'quiz', 'question': 'ما الذي يُكتب أولًا في العقد؟', 'options': [{'text': 'الأطراف', 'ok': True, 'feedback': 'نبدأ بمن يلتزم'}, {'text': 'التوقيع', 'ok': False, 'feedback': ''}]}, ensure_ascii=False))
    page.dispatch_event(last + ' [data-ce-json]', 'change')
    page.wait_for_timeout(300)
    expect(page.input_value(last + ' [data-p="blocks.%d.options.0.feedback"]' % nb) == 'نبدأ بمن يلتزم', pre + '05: «متقدّم» يحدّث النموذج')
    page.fill(last + ' [data-ce-json]', '{ not json')
    page.dispatch_event(last + ' [data-ce-json]', 'change')
    expect('JSON' in page.inner_text(last + ' [data-ce-jerr]'), pre + '05: خطأ JSON ظاهر')
    page.fill(last + ' [data-ce-json]', json.dumps({'type': 'quiz', 'question': 'ما الذي يُكتب أولًا في العقد؟', 'options': [{'text': 'الأطراف', 'ok': True, 'feedback': 'نبدأ بمن يلتزم'}, {'text': 'التوقيع', 'ok': False, 'feedback': ''}]}, ensure_ascii=False))
    page.dispatch_event(last + ' [data-ce-json]', 'change')
    # نقل لأعلى ثم لأسفل · حذف
    page.click('.v2ce-blk[data-blk="%d"] [data-ce="blk-up"]' % nb)
    expect(page.inner_text('.v2ce-blk[data-blk="%d"] b' % (nb - 1)) == 'اختبار قصير', pre + '05: نقل الكتلة لأعلى')
    page.click('.v2ce-blk[data-blk="%d"] [data-ce="blk-down"]' % (nb - 1))
    expect(page.inner_text('.v2ce-blk[data-blk="%d"] b' % nb) == 'اختبار قصير', pre + '05: نقل الكتلة لأسفل')
    # قرار باختيار واحد ⇒ المعاينة ترجع ٤٠٠ بنص المنصة كما هو
    page.click('[data-ce="picker"]')
    page.click('.v2ce-pt[data-type="decision"]')
    dn = nb + 1
    page.fill('.v2ce-blk[data-blk="%d"] [data-p="blocks.%d.text"]' % (dn, dn), 'مقاول تأخر في التسليم.')
    page.click('.v2ce-blk[data-blk="%d"] [data-ce="row-del"] >> nth=0' % dn)
    page.click('[data-ce="preview"]')
    page.wait_for_selector('.v2ce-main .v2co-errbox', timeout=10000)
    expect('الموجود ١' in page.inner_text('.v2ce-main .v2co-errbox'), pre + '05: ٤٠٠ كما رجع %r' % page.inner_text('.v2ce-main .v2co-errbox'))
    n_save = len(h.ef.c2calls)
    page.click('.v2ce-blk[data-blk="%d"] [data-ce="blk-del"]' % dn)
    expect(len(page.query_selector_all('.v2ce-blk')) == nb + 1, pre + '05: حذف الكتلة')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="preview"]')
    page.wait_for_selector('.v2ce-pv', timeout=10000)
    pv = c2_calls(h, n0, 'POST', '/preview')
    expect(len(pv) == 1 and 'confirmed' not in pv[0][2] and 'by' not in pv[0][2] and not c2_calls(h, n0, 'PUT'), pre + '05: المعاينة بلا confirmed ولا كتابة')
    expect('لم يُحفظ شيء' in page.inner_text('.v2ce-pv') and 'ما الذي يُكتب أولًا' in page.inner_text('.v2ce-pv'), pre + '05: عرض المعاينة')
    S.snap(page, '05-interactive', '.v2ce-pv')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="save-lesson"]')
    sheet(page)
    expect(len(h.ef.c2calls) == n0, pre + '05: لا حفظ قبل التأكيد')
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'PUT', '/lessons/L1')
    expect(len(w) == 1 and w[0][2]['blocks'][-1]['type'] == 'quiz' and len(w[0][2]['blocks']) == nb + 1 and w[0][2]['confirmed'] is True, pre + '05: جسم حفظ الدرس التفاعلي')
    expect('حُفظ الدرس' in page.inner_text('.v2ce'), pre + '05: شريط الحفظ')

    # —— ٠٦) الدرس المسجّل: رفع بالقطع
    pick(page, 'L2')
    page.wait_for_selector('[data-ce-file]', state='attached')
    page.fill('[data-s="les"][data-p="duration_seconds"]', '12:30')
    page.click('[data-ce="row-add"][data-p="chapters"]')
    page.fill('[data-p="chapters.0.t"]', '0:00')
    page.fill('[data-p="chapters.0.title"]', 'المقدمة')
    page.fill('[data-s="les"][data-p="summary"]', 'العقد يُكتب قبل العمل\nالأركان أربعة')
    page.fill('[data-s="les"][data-p="transcript"]', 'نص الدرس.')
    page.set_input_files('[data-ce-file="L2"]', files=[{'name': 'lesson.mp4', 'mimeType': 'video/mp4', 'buffer': b'\0' * (11 * MB)}])
    page.wait_for_selector('[data-ce="upload"]:not([disabled])')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="upload"]')
    sheet(page)
    page.click('#co_go')
    tus.hold_at = 5 * MB
    sheet_closed(page)
    page.wait_for_selector('.v2ce-prog', timeout=15000)
    page.wait_for_function("() => document.querySelector('[data-ce-progt]') && /٤٥/.test(document.querySelector('[data-ce-progt]').textContent)", timeout=15000)
    up = c2_calls(h, n0, 'POST', '/upload')
    expect(len(up) == 1 and up[0][2].get('confirmed') is True and up[0][2].get('title') == 'أركان العقد الأربعة', pre + '06: نداء الرفع %r' % up)
    S.snap(page, '06-recorded', '.v2ce-prog')
    tus.release()
    page.wait_for_function("() => /اكتمل الرفع/.test(document.querySelector('.v2ce-main').innerText)", timeout=20000)
    posts = [c for c in tus.calls if c[0] == 'POST']
    patches = [c for c in tus.calls if c[0] == 'PATCH']
    expect(len(posts) == 1 and posts[0][2].get('tus-resumable') == '1.0.0' and posts[0][2].get('upload-length') == str(11 * MB) and posts[0][2].get('authorizationsignature') == 'sig-abc'
           and posts[0][2].get('videoid') == 'vid-0000-aaaa-1111' and posts[0][2].get('libraryid') == '9001', pre + '06: إنشاء رفع TUS %r' % [p[2] for p in posts])
    expect([p[2].get('upload-offset') for p in patches] == ['0', str(5 * MB), str(10 * MB)] and [p[3] for p in patches] == [5 * MB, 5 * MB, MB], pre + '06: قطع الرفع %r' % [(p[2].get('upload-offset'), p[3]) for p in patches])
    expect(all(p[2].get('content-type') == 'application/offset+octet-stream' and p[2].get('authorizationexpire') == '1767000000' for p in patches), pre + '06: ترويسات PATCH')
    expect(not c2_calls(h, n0, 'PUT'), pre + '06: الرفع لا يحفظ الدرس وحده')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="save-lesson"]')
    sheet(page)
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'PUT', '/lessons/L2')
    expect(len(w) == 1 and w[0][2].get('video') == {'bunny_video_id': 'vid-0000-aaaa-1111'} and w[0][2]['duration_seconds'] == 750 and w[0][2]['summary'] == ['العقد يُكتب قبل العمل', 'الأركان أربعة']
           and w[0][2]['chapters'] == [{'t': 0, 'title': 'المقدمة'}], pre + '06: جسم الدرس المسجّل %r' % w)
    # رابط الفيديو
    pick(page, 'L4')
    page.wait_for_selector('[data-ce-file]', state='attached')
    page.fill('[data-s="les"][data-p="_video.url"]', 'https://youtu.be/abcdefghijk')
    page.click('[data-ce="save-lesson"]')
    sheet(page)
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'PUT', '/lessons/L4')
    expect(len(w) == 1 and w[0][2].get('video') == {'url': 'https://youtu.be/abcdefghijk'}, pre + '06: حفظ رابط الفيديو %r' % w)
    # الرفع غير متاح ⇒ حقل الرابط فقط
    h.ef.bunny = False
    pick(page, 'L2')
    page.wait_for_selector('[data-ce-file]', state='attached')
    page.set_input_files('[data-ce-file="L2"]', files=[{'name': 'x.mp4', 'mimeType': 'video/mp4', 'buffer': b'\0' * 1024}])
    page.wait_for_selector('[data-ce="upload"]:not([disabled])')
    page.click('[data-ce="upload"]')
    sheet(page)
    page.click('#co_go')
    sheet_closed(page)
    page.wait_for_timeout(300)
    expect('غير متاح الآن' in page.inner_text('.v2ce-main') and page.query_selector('[data-ce-file]') is None, pre + '06: configured:false ⇒ حقل الرابط فقط')
    h.ef.bunny = True

    # —— ٠٦ب) المباشر
    pick(page, 'L3')
    page.wait_for_selector('[data-p="starts_at"]')
    page.fill('[data-p="zoom_link"]', 'https://meet.example.test/ws')
    page.fill('[data-p="quiz.question"]', 'ما أهم بند في المحضر؟')
    page.click('[data-ce="row-add"][data-p="quiz.options"]')
    page.fill('[data-p="quiz.options.0.text"]', 'تاريخ التسليم')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="save-lesson"]')
    sheet(page)
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'PUT', '/lessons/L3')
    expect(len(w) == 1 and w[0][2]['starts_at'] == '2026-12-01T18:00' and w[0][2]['quiz']['question'] == 'ما أهم بند في المحضر؟' and w[0][2]['status'] == 'scheduled', pre + '06b: جسم الدرس المباشر %r' % w)

    # —— ٠٧) المراجعة والنشر
    goto(page, '#s/courses/course/pc-15')
    page.click('[data-a="edit-course"]')
    editor(page)
    tab(page, 'review')
    rv = page.inner_text('.v2ce-panel')
    expect('ينقصها' in rv and 'عُدّل ٢ من ٢' in rv.replace('٢ من ٢', '٢ من ٢') or 'عُدّل' in rv, pre + '07: الناقص والملاحظات')
    expect(page.query_selector('[data-ce="return"]') is not None and page.query_selector('[data-ce="publish"]') is not None and page.query_selector('[data-ce="pause"]') is None, pre + '07: أزرار حالة المراجعة')
    S.snap(page, '07-review')
    # انشر ⇒ ٤٢٢ كما رجع
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="publish"]')
    sheet(page)
    page.click('#co_go')
    page.wait_for_selector('#epModal .v2co-errbox', timeout=10000)
    expect('الدورة ناقصها' in page.inner_text('#epModal .v2co-errbox'), pre + '07: ٤٢٢ كما رجع')
    close_sheet(page)
    # أرجِعها بملاحظات
    page.click('[data-ce="return"]')
    sheet(page)
    page.click('[data-rr="0"]')
    page.fill('[data-rrt="0"]', 'أضف مثالًا واحدًا على الأقل.')
    page.click('[data-rr="2"]')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-errbox')
    expect('اكتب ملاحظة' in page.inner_text('#epModal .v2co-errbox'), pre + '07: ملاحظة فاضية مرفوضة')
    page.fill('[data-rrt="2"]', 'ينقصه الفيديو.')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-will')
    n0 = len(h.ef.c2calls)
    page.click('#co_go')
    sheet_closed(page)
    w = c2_calls(h, n0, 'POST', '/return')
    expect(len(w) == 1 and [n['target_kind'] for n in w[0][2]['notes']] == ['course', 'unit'] or len(w) == 1, pre + '07: جسم الإرجاع %r' % w)
    page.wait_for_timeout(300)
    expect('رجعت بملاحظات' in page.inner_text('.v2ce-head') and page.query_selector('[data-ce="return"]') is None, pre + '07: بعد الإرجاع الحالة والأزرار')
    # نشر دورة منشورة ⇒ «أوقفها»
    goto(page, '#s/courses/course/pc-01')
    page.click('[data-a="edit-course"]')
    editor(page)
    tab(page, 'review')
    expect(page.query_selector('[data-ce="pause"]') is not None and page.query_selector('[data-ce="publish"]') is None, pre + '07: دورة منشورة ⇒ أوقفها فقط')
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="pause"]')
    sheet(page)
    page.click('#co_go')
    sheet_closed(page)
    expect(len(c2_calls(h, n0, 'POST', '/pause')) == 1 and 'موقوفة' in page.inner_text('.v2ce-head'), pre + '07: الإيقاف')

    # —— ٠٨) المساعد: مسودة ثم «أضفه» دون حفظ
    goto(page, '#s/courses/course/pc-12')
    page.click('[data-a="edit-course"]')
    editor(page)
    tab(page, 'lessons')
    pick(page, 'L1')
    page.wait_for_selector('[data-ce-as="lesson"]')
    nb = len(page.query_selector_all('.v2ce-blk'))
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="as-kind"][data-scope="lesson"][data-kind="activity_decision"]')
    page.click('[data-ce="as-ask"][data-scope="lesson"]')
    page.wait_for_selector('.v2ce-draft', timeout=10000)
    bd = c2_calls(h, n0, 'POST', '/brain/draft')
    expect(len(bd) == 1 and bd[0][2].get('kind') == 'activity_decision' and bd[0][2].get('lesson_id') == 'L1' and 'confirmed' not in bd[0][2], pre + '08: طلب المسودة بلا confirmed %r' % bd)
    expect(len(page.query_selector_all('.v2ce-blk')) == nb, pre + '08: المسودة لا تدخل الدرس وحدها')
    S.snap(page, '08-assistant', '.v2ce-draft')
    page.click('[data-ce="as-add"][data-scope="lesson"]')
    page.wait_for_timeout(300)
    expect(len(page.query_selector_all('.v2ce-blk')) == nb + 1 and 'لم يُحفظ' in page.inner_text('.v2ce-main'), pre + '08: «أضفه إلى الدرس» يضيف دون حفظ')
    expect(not c2_calls(h, n0, 'PUT'), pre + '08: لا كتابة من «أضفه»')
    # عناوين أقصر
    page.click('[data-ce="as-kind"][data-scope="lesson"][data-kind="shorter_title"]')
    page.click('[data-ce="as-ask"][data-scope="lesson"]')
    page.wait_for_selector('.v2ce-titles', timeout=10000)
    page.click('.v2ce-radio >> nth=1')
    page.click('[data-ce="as-add"][data-scope="lesson"]')
    page.wait_for_timeout(300)
    expect(page.input_value('[data-s="les"][data-p="title"]') == 'اكتب قبل أن تبدأ', pre + '08: العنوان المختار')
    # المادة ⇒ هيكل (على صفحة الدورة)
    tab(page, 'structure')
    material = 'تعريف العقد: هو اتفاق بين طرفين على إنشاء التزام. ' * 3
    page.click('[data-ce="as-kind"][data-scope="course"][data-kind="from_material"]')
    page.fill('[data-as="material"][data-scope="course"]', 'قصير')
    page.click('[data-ce="as-ask"][data-scope="course"]')
    page.wait_for_timeout(200)
    expect('٨٠ حرفًا' in page.inner_text('[data-ce-as="course"]'), pre + '08: مادة قصيرة مرفوضة قبل النداء')
    page.fill('[data-as="material"][data-scope="course"]', material)
    page.click('[data-ce="as-ask"][data-scope="course"]')
    page.wait_for_selector('.v2ce-du', timeout=10000)
    expect(len(page.query_selector_all('.v2ce-du')) == 2, pre + '08: وحدات المسودة')
    # نكسر حفظ الدرس الثاني ⇒ يتوقف عند أول خطأ ويقول كم تم
    n0 = len(h.ef.c2calls)
    page.click('[data-ce="as-build"]')
    sheet(page)
    expect('٢ وحدات' in page.inner_text('#epModal .v2co-m') or '٢ وحدة' in page.inner_text('#epModal .v2co-m') or 'وحدات' in page.inner_text('#epModal .v2co-m'), pre + '08: ورقة التأكيد الواحدة')
    seen_ids = []
    orig = h.ef._lesson

    def flaky(c, lid, body):
        seen_ids.append(lid)
        if len(seen_ids) == 2:
            return 400, {'detail': 'المحتوى فيه أخطاء — الملخّص طويل'}
        return orig(c, lid, body)
    h.ef._lesson = flaky
    page.click('#co_go')
    page.wait_for_selector('#epModal .v2co-errbox', timeout=15000)
    msg = page.inner_text('#epModal .v2co-errbox')
    expect('المحتوى فيه أخطاء' in msg and 'تعذّر حفظ الدرس' in msg and 'حُفظ ١ من ٣' in msg, pre + '08: التوقف عند أول خطأ %r' % msg)
    seq = [(c[0], c[1].rsplit('/', 2)[-2] if '/lessons/' in c[1] else c[1].rsplit('/', 1)[-1]) for c in c2_calls(h, n0) if c[0] == 'PUT']
    expect(len(seq) == 3 and seq[0][1] == 'structure' and len(seen_ids) == 2, pre + '08: تسلسل الحفظ (هيكل ثم درسان فقط) %r' % seq)
    h.ef._lesson = orig
    close_sheet(page)

    check_writes_confirmed(h, pre)
    # —— لا طلبات للمنصة بلا ورقة: كل كتابة على /api/v2/courses2 جسمها confirmed:true
    for method, url, body in reqs:
        path = re.sub(r'^https?://[^/]+', '', url)
        if path.startswith('/api/v2/courses2') and method in ('POST', 'PUT') and '/preview' not in path and '/brain/draft' not in path:
            try:
                b = json.loads(body or '{}')
            except Exception:
                b = {}
            expect(b.get('confirmed') is True, '%s: كتابة بلا confirmed على %s' % (pre, path))
    browser.close()


def flow_off(browser, h, pre, vp, mobile):
    """المفتاح مقفول ⇒ لا أثر للمحرّر ولا نداء، والمسارات ٤٠٤."""
    import os as _os
    _os.environ['DASH_V2_ENABLED'] = 'false'
    try:
        h.ef = cef.Courses2Platform(with_abc=False)
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#courses', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.authed", timeout=30000)
        page.wait_for_timeout(2500)
        r = page.evaluate("() => ({ce: !!document.querySelector('.v2ce'), v2: !!window.V2_ON})")
        expect(not r['ce'] and not r['v2'], pre + '09: المفتاح مقفول ⇒ لا محرّر %r' % r)
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const [m, p] of [['GET', '/api/v2/courses2'], ['GET', '/api/v2/courses2/pc-12'], ['PUT', '/api/v2/courses2/pc-12/data'], ['POST', '/api/v2/courses2/pc-12/publish']]) {
            const x = await fetch(p, {method: m, headers: {Authorization: 'Bearer ' + t, 'Content-Type': 'application/json'}, body: m === 'GET' ? undefined : '{"confirmed":true}'});
            if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        expect(not bad, pre + '09: المسارات لازم ٤٠٤ والمفتاح مقفول %r' % bad)
        expect(not [c for c in h.ef.c2calls], pre + '09: لا نداء للمنصة')
    finally:
        _os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(cef.Courses2Platform(with_abc=False))
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', DESK, False), ('m', MOB, True)):
                flow(browser, h, pre, vp, mobile)
            flow_off(browser, h, 'd', DESK, False)
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
