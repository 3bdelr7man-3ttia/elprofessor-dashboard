# -*- coding: utf-8 -*-
"""لقطات وفحوص مربّعات «الساحة» و«الديوان» (docs/v2/saha-tiles/SPEC.md) — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٤٣٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_saha.py ../docs/v2/saha-tiles/shots [only-prefix,...]

الخطوات (R18: ٠٨م محرّك الفرص): ٠١ مربّعات الساحة · ٠٢ الأخبار (مراجعة ثم نشر · سحب · جلب جديد) · ٠٣ طابور الفرص بالنوع (اعتماد · رفض بسبب · رد المنصة) · ٠٤ قائمة الفرص والنموذج الكامل
(إضافة · تعديل · حذف) · ٠٥ استيراد الفرص (تجربة ثم تأكيد · ملف مرفوع) · ٠٦ رابط دورة التحضير · ٠٧ الآراء · ٠٨ التذكير (مقفول ثم مفتوح) ·
٠٩ مربّعات الديوان · ١٠ الأعمال · ١١ التعليقات · ١٢ التحديات (نموذج · لجنة · الفائزون) · ١٣ التقرير (لا رقم بعد) · ١٤ المصدر الواقع والجسر الغايب · ١٥ الحالات الفاضية · ١٦ المفتاح مقفول.

السكربت بيفشل (exit 1) لو: «0/null/NaN/undefined» ظاهر · هدف أقل من ٤٤px · خانة أقل من ١٦px · تمرير أفقي · رقم لاتيني ظاهر · «·» ملاصقة لرقم · كلمة ممنوعة ·
نافذة متصفح (`alert`/`confirm`/`prompt`) · كتابة وصلت المنصة قبل ضغطة التأكيد أو غير المسارات المسموحة أو بلا `by` أو فيها `confirmed` ·
حفظ في المتصفح · أي طلب خرج من العملية غير خطوط جوجل.
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية، والمنصة جدول في الذاكرة (`saha_tiles_fixtures.SahaTilesPlatform`).
"""
import json
import os
os.environ.setdefault('DASH_SCHEDULER', '0')   # R16: مراقبة التشغيل/الملخص اليومي ما يشتغلوش جوّه الأداة (كانوا بيبعتوا تليجرام عبر الجسر المزيّف)
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                         # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import saha_tiles_fixtures as sfx             # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

PROBLEMS = vs.PROBLEMS
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
DESK = vs.DESK
MOB = {'width': 430, 'height': 932}
READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-sh[data-board]') && !document.querySelector('.v2s-sh .sh-skel')"
         " && !/…/.test((document.querySelector('.sh-tiles') || {innerText: ''}).innerText)")
BANNED = ('يقوّم', 'يقوم', 'API', 'JSON', 'Claude', 'DeepSeek', 'Anthropic', 'endpoint', 'token', 'bridge', 'dry_run', 'undefined')
B = r'^/api/bridge/'
OK_WRITES = [('PUT', re.compile(B + r'news/[^/]+$')), ('POST', re.compile(B + r'news/run$')), ('POST', re.compile(B + r'opinions/[^/]+/(reject|approve)$')),
             ('POST', re.compile(B + r'jobs$')), ('PUT', re.compile(B + r'jobs/[^/]+$')), ('DELETE', re.compile(B + r'jobs/[^/]+$')), ('POST', re.compile(B + r'jobs/[^/]+/decide$')),
             ('PUT', re.compile(B + r'opportunities/settings$')), ('POST', re.compile(B + r'opportunities/import-seed$')), ('POST', re.compile(B + r'opportunities/run-reminders$')),
             ('POST', re.compile(B + r'creative/[^/]+/decide$')), ('PUT', re.compile(B + r'creative/[^/]+$')), ('POST', re.compile(B + r'diwan/comments/[^/]+/hide$')),
             ('POST', re.compile(B + r'topics/[^/]+/(hide|restore)$')), ('POST', re.compile(B + r'legal-gate/backfill$')),
             ('POST', re.compile(B + r'diwan/challenges$')), ('PUT', re.compile(B + r'diwan/challenges/[^/]+$')), ('POST', re.compile(B + r'diwan/challenges/[^/]+/winners$')),
             ('PUT', re.compile(B + r'opportunities/autorun$')), ('PUT', re.compile(B + r'opportunities/sources/[a-z0-9_-]+$')),
             ('POST', re.compile(B + r'opportunities/sources/import-seed$')), ('POST', re.compile(B + r'opportunities/run$')),
             ('PUT', re.compile(B + r'opportunities/digest$')), ('POST', re.compile(B + r'opportunities/digest/send-test$'))]
# R18: كتابات «محرّك الفرص» جسمها بالعقد بالظبط ⇒ بلا `by` (عكس باقي الجسور).
ENGINE_RX = re.compile(B + r'opportunities/(autorun|sources/[a-z0-9_-]+|run|digest|digest/send-test)$')
SCOPE_JS = """() => [...document.querySelectorAll('.v2s-sh, #epModal.v2s-sh-sh')].map(e => { const c = e.cloneNode(true);
  c.querySelectorAll('[dir="ltr"], [dir="auto"], .sh-who, script, style, input, textarea, select, option').forEach(n => n.remove()); return c.innerText; }).join('\\n')"""


def want(code):
    return not ONLY or any(code.startswith(o) for o in ONLY)


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def arn(n):
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def shcheck(page, name):
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v2s-sh button, .v2s-sh a.sh-lnk, .v2s-sh select, .v2s-sh input:not([type=checkbox]):not([type=radio]), #epModal.v2s-sh-sh button, #epModal.v2s-sh-sh a.sh-lnk, #epModal.v2s-sh-sh input:not([type=checkbox]):not([type=radio]), #epModal.v2s-sh-sh select, #epModal.v2s-sh-sh textarea, #epModal.v2s-sh-sh .sh-chk, #epModal.v2s-sh-sh summary')].filter(b => b.offsetParent && !b.closest('[hidden]') && !(b.closest('details') && !b.closest('details').open && b.tagName !== 'SUMMARY'))
      .map(b => [(b.className || b.id || b.tagName).toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    boxes = page.evaluate("""() => [...document.querySelectorAll('.v2s-sh input:not([type=checkbox]):not([type=radio]), .v2s-sh select, #epModal.v2s-sh-sh input:not([type=checkbox]):not([type=radio]), #epModal.v2s-sh-sh textarea, #epModal.v2s-sh-sh select')].filter(b => b.offsetParent).map(b => [b.id || b.className, parseFloat(getComputedStyle(b).fontSize)])""")
    for ident, fs in boxes:
        if fs < 16:
            PROBLEMS.append('%s: خانة %s خطها %s أقل من ١٦' % (name, ident, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    wide = page.evaluate("() => [...document.querySelectorAll('.v2s-sh *, #epModal.v2s-sh-sh *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed').length")
    if wide:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    txt = page.evaluate(SCOPE_JS)
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر: %r' % (name, re.findall(r'.{0,10}(?<![\w@./-])(?:0|null|NaN|undefined)(?![\w@./-]).{0,10}', txt)[:2]))
    bad = [t for t in re.findall(r'\S*[0-9]\S*', txt) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    if re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', txt):
        PROBLEMS.append('%s: «·» ملاصقة لرقم: %r' % (name, re.findall(r'.{0,8}[0-9٠-٩]\s*·.{0,8}|.{0,8}·\s*[0-9٠-٩].{0,8}', txt)[:2]))
    for word in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    if re.search(r'#[0-9A-Fa-f]{6}\b|\bnull\b', txt):
        PROBLEMS.append('%s: نص تقني ظاهر' % name)
    keys = page.evaluate("() => { try { return Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => /saha|diwan|opp|challenge|seed/i.test(k)); } catch (e) { return []; } }")
    if keys:
        PROBLEMS.append('%s: حفظ في المتصفح %r' % (name, keys))


def mshot(page, name, keep=True, target=None):
    if target:
        page.evaluate("sel => { const e = document.querySelector(sel); if (e) e.scrollIntoView({block: 'start'}); }", target)
    else:
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    page.wait_for_timeout(300)
    if keep:
        vs.shot(page, name, full=False)
    vs.shell_check(page, name)
    shcheck(page, name)


def writes_since(h, since):
    """كتابات المنصة منذ `since` (التجربة `dry_run=true` ليست كتابة، ولا فحص الصلة بالقانون بلا `apply:true`)."""
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE') and not (c[2] or {}).get('dry_run')
            and not (c[1].endswith('/legal-gate/backfill') and (c[3] or {}).get('apply') is not True)]


def check_writes(name, h, since, expected):
    got = writes_since(h, since)
    for m, p, _q, body in got:
        if not any(m == am and rx.match(p) for am, rx in OK_WRITES):
            PROBLEMS.append('%s: كتابة غير مسموحة %s %s' % (name, m, p))
        if (body is not None and not isinstance(body, dict)) or (body and 'confirmed' in body):
            PROBLEMS.append('%s: confirmed سافر للمنصة %s %s' % (name, m, p))
        if ENGINE_RX.match(p):
            if isinstance(body, dict) and 'by' in body:
                PROBLEMS.append('%s: جسم المحرّك فيه by (العقد بالظبط) %s %s' % (name, m, p))
        elif 'import-seed' not in p and (not isinstance(body, dict) or not str(body.get('by') or '').strip()):
            PROBLEMS.append('%s: كتابة بلا by %s %s' % (name, m, p))
        if 'import-seed' in p and body and 'by' in body:
            PROBLEMS.append('%s: الاستيراد لا يحمل by (جسم غير فاضي = الملف نفسه) %s' % (name, p))
    if len(got) != expected:
        PROBLEMS.append('%s: عدد الكتابات %d بدل %d: %r' % (name, len(got), expected, [(m, p) for m, p, _q, _b in got]))
    return got


def reset_reminders(h):
    """قاعدة الداشبورد مشتركة بين الأحجام: آخر تشغيل للتذكير يتمسح قبل كل سيناريو (كل سيناريو يبدأ «لم يُشغَّل بعد»)."""
    m = h.app
    with m.app.app_context():
        row = m.db.session.get(m.Setting, 'v2saha_reminders_last')
        if row is not None:
            m.db.session.delete(row)
            m.db.session.commit()


def sopen(browser, h, ef, viewport, mobile, hash_='#s/content/saha', ready=READY, role='admin'):
    h.ef = ef
    reset_reminders(h)
    ctx = browser.context(h, role, viewport, mobile)
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح ظهرت: %s' % d.message[:60]), d.dismiss()))
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.on('console', lambda m: PROBLEMS.append('console.error: %s' % m.text[:200]) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(ready, timeout=30000)
    page.wait_for_timeout(350)
    return page


def vis(sel):
    return sel + ' >> visible=true'


def click(page, sel, wait=300):
    page.locator(vis(sel)).first.click()
    page.wait_for_timeout(wait)


def go_sub(page, sub):
    click(page, '.sh-tile[data-sub="%s"]' % sub, 500)
    page.wait_for_function("() => !document.querySelector('.v2s-sh .sh-skel') && document.querySelector('.sh-head')", timeout=15000)
    page.wait_for_timeout(300)


def back_hub(page):
    click(page, '[data-a="hub"]', 400)
    page.wait_for_function("() => document.querySelector('.sh-tiles') && !/…/.test(document.querySelector('.sh-tiles').innerText)", timeout=15000)


def sheet_open(page):
    page.wait_for_selector('#epModal.v2s-sh-sh', timeout=10000)
    page.wait_for_timeout(250)


def sheet_gone(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(450)


def tile_numbers(page):
    return {t[0]: (t[1], t[2]) for t in page.evaluate("() => [...document.querySelectorAll('.sh-tile')].map(t => [t.dataset.sub, t.querySelector('.sh-n').textContent.trim(), t.querySelector('small').textContent.trim()])")}


def count_rows(page, sel='[data-id]'):
    """عدد الصفوف الظاهرة (الجدول أو البطاقات حسب الشاشة)."""
    return page.evaluate("sel => new Set([...document.querySelectorAll('.v2s-sh ' + sel)].filter(e => e.offsetParent).map(e => e.dataset.id)).size", sel)


def wait_rows(page, n, sel='[data-id]'):
    page.wait_for_function("a => new Set([...document.querySelectorAll('.v2s-sh ' + a[1])].filter(e => e.offsetParent).map(e => e.dataset.id)).size === a[0]", arg=[n, sel], timeout=12000)
    page.wait_for_timeout(200)


def note_text(page):
    return page.evaluate("() => (document.querySelector('.sh-note') || {textContent: ''}).textContent.trim()")


def err_text(page, sel='#shErr'):
    return page.evaluate("s => (document.querySelector(s) || {textContent: ''}).textContent.trim()", sel)


def stage(page, text_in_sheet):
    page.wait_for_function("t => (document.getElementById('epModal') || {innerText: ''}).innerText.includes(t)", arg=text_in_sheet, timeout=10000)
    page.wait_for_timeout(200)


def confirm(page, wait=900):
    click(page, '#shGo', wait)


# ======================================================================= الساحة
def flow_saha(browser, h, pre, vp, mobile):
    # —— ٠١) المربّعات
    if want('01'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        nums = tile_numbers(page)
        expect(nums.get('news') == ('٣', 'خبر ينتظر مراجعتك') and nums.get('review') == ('٦', 'إعلان ينتظر قرارك') and nums.get('opps', ('',))[0] == '١١'
               and nums.get('opinions') == ('٢', 'رأي ينتظر قرارك') and nums.get('prep', ('',))[0] == 'مضبوط' and nums.get('import', ('',))[0] == 'جرّب'
               and nums.get('reminders') == ('—', 'لم يُشغَّل بعد') and nums.get('engine') == ('٢', 'مسودة تنتظر مراجعتك، والتشغيل اليومي متوقّف'),
               '%s01: أرقام مربّعات الساحة %r' % (pre, nums))
        tabs = page.evaluate("() => [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim())")
        expect('الساحة' in tabs and 'الديوان' in tabs and 'القاموس' in tabs and len(tabs) == 10, '%s01: تبويبات المحتوى %r' % (pre, tabs))
        imgs = page.evaluate("() => [...document.querySelectorAll('.sh-timg')].map(e => getComputedStyle(e).backgroundImage.replace(/.*\\//, ''))")
        expect(len(imgs) == 9 and all('.jpg' in i for i in imgs), '%s01: صور المربّعات %r' % (pre, imgs))
        mshot(page, pre + '01-hub.jpg')
        browser.close()

    # —— ٠٢) الأخبار
    if want('02'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'news')
        wait_rows(page, 3)
        mshot(page, pre + '02-news-list.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="newsapprove"][data-id="n-1"]', 400)
        sheet_open(page)
        expect('نص الخبر الكامل' in page.inner_text('#epModal') and page.input_value('#f_title') == 'قانون جديد للعمل المرن', '%s02: ورقة المراجعة ما عرضتش الخبر' % pre)
        cats = page.evaluate("() => [...document.querySelectorAll('#f_category option')].map(o => o.textContent.trim())")
        expect(cats[-1] == 'أخرى' and len(cats) == 4, '%s02: «أخرى» في التصنيف %r' % (pre, cats))
        page.fill('#f_title', '')
        click(page, '#shNext', 250)
        expect(page.inner_text('[data-e="title"]') != '', '%s02: عنوان فاضي ما اتمنعش' % pre)
        page.fill('#f_title', 'قانون جديد للعمل المرن يبدأ العام القادم')
        page.fill('#f_cover_url', 'http://insecure.example.test/x.jpg')
        click(page, '#shNext', 250)
        expect('https' in page.inner_text('[data-e="cover_url"]'), '%s02: رابط غير آمن مرّ' % pre)
        page.fill('#f_cover_url', '')
        click(page, '#shNext', 300)
        review = page.inner_text('#epModal')
        expect('مسودة' in review and 'منشور' in review and 'يبدأ العام القادم' in review and 'اعتمد ونشر' in review, '%s02: مراجعة النشر %r' % (pre, review[:160]))
        mshot(page, pre + '02b-news-review.jpg', keep=True)
        check_writes(pre + '02-before-confirm', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '02-approve', h, base, 1)
        if got:
            expect(got[0][0] == 'PUT' and got[0][3].get('status') == 'published' and got[0][3].get('title') == 'قانون جديد للعمل المرن يبدأ العام القادم' and set(got[0][3]) == {'status', 'title', 'by'},
                   '%s02: جسم الاعتماد %r' % (pre, got[0][3]))
        wait_rows(page, 2)
        expect('نُشر الخبر' in note_text(page), '%s02: رسالة النجاح %r' % (pre, note_text(page)))
        # سحب خبر منشور
        click(page, '[data-a="chip"][data-v="published"]', 700)
        wait_rows(page, 2)
        click(page, '[data-a="newsun"][data-id="n-9"]', 400)
        sheet_open(page)
        mshot(page, pre + '02c-news-unpublish.jpg', keep=True)
        check_writes(pre + '02-un-before', h, base, 1)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '02-unpublish', h, base, 2)
        if len(got) == 2:
            expect(got[1][3].get('status') == 'draft', '%s02: جسم سحب النشر %r' % (pre, got[1][3]))
        # جلب أخبار جديدة
        click(page, '[data-a="chip"][data-v="draft"]', 700)
        click(page, '[data-a="newsrun"]', 400)
        sheet_open(page)
        opts = page.evaluate("() => [...document.querySelectorAll('#f_limit option')].map(o => o.textContent.trim())")
        expect(opts[0] == 'كما تحدده المنصة' and len(opts) == 9, '%s02: خيارات العدد %r' % (pre, opts))
        page.select_option('#f_limit', '3')
        click(page, '#shNext', 300)
        mshot(page, pre + '02d-news-run.jpg', keep=True)
        check_writes(pre + '02-run-before', h, base, 2)
        confirm(page, 1200)
        sheet_gone(page)
        got = check_writes(pre + '02-run', h, base, 3)
        if len(got) == 3:
            expect(got[2][1].endswith('/news/run') and got[2][3].get('per_country_limit') == 3, '%s02: جسم الجلب %r' % (pre, got[2][3]))
        expect('مسودتان' in note_text(page), '%s02: رسالة الجلب %r' % (pre, note_text(page)))
        browser.close()

    # —— ٠٣) طابور الفرص
    if want('03'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'review')
        wait_rows(page, 6, '.sh-card')
        chips = page.evaluate("() => [...document.querySelectorAll('.sh-chip')].map(b => b.textContent.trim())")
        expect(chips == ['الكل', 'منح', 'وظائف', 'تدريب', 'مسابقات', 'أخرى'], '%s03: أنواع الفلتر %r' % (pre, chips))
        mshot(page, pre + '03-review-queue.jpg')
        for chip, n in (('grants', 2), ('job', 1), ('training', 1), ('competition', 1), ('other', 1), ('all', 6)):
            click(page, '[data-a="chip"][data-v="%s"]' % chip, 350)
            wait_rows(page, n, '.sh-card')
        base = len(h.platform_calls)
        click(page, '[data-a="oppapprove"][data-id="job-1"]', 400)
        sheet_open(page)
        expect('الساحة' in page.inner_text('#epModal') and 'اعتمد ونشر' in page.inner_text('#shGo'), '%s03: ورقة الاعتماد' % pre)
        mshot(page, pre + '03b-approve.jpg', keep=True)
        check_writes(pre + '03-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '03-approve', h, base, 1)
        if got:
            expect(got[0][3] == {'decision': 'approve', 'by': got[0][3].get('by')}, '%s03: جسم الاعتماد %r' % (pre, got[0][3]))
        wait_rows(page, 5, '.sh-card')
        # الرفض بسبب
        click(page, '[data-a="oppreject"][data-id="job-2"]', 400)
        sheet_open(page)
        click(page, '#shNext', 250)
        expect('٣ أحرف' in err_text(page) or 'سبب' in err_text(page), '%s03: رفض بلا سبب ما اتمنعش' % pre)
        page.fill('#f_reason', 'الرابط لا يعمل')
        click(page, '#shNext', 300)
        mshot(page, pre + '03c-reject.jpg', keep=True)
        check_writes(pre + '03-reject-before', h, base, 1)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '03-reject', h, base, 2)
        if len(got) == 2:
            expect(got[1][3].get('decision') == 'reject' and got[1][3].get('reason') == 'الرابط لا يعمل', '%s03: جسم الرفض %r' % (pre, got[1][3]))
        wait_rows(page, 4, '.sh-card')
        # المنصة ترفض (إعلان بلا رابط رسمي) ⇒ النص العربي كما هو في الورقة
        click(page, '[data-a="oppapprove"][data-id="job-6"]', 400)
        sheet_open(page)
        confirm(page, 900)
        expect('أكمل عنوان الإعلان' in err_text(page), '%s03: رد المنصة ما ظهرش %r' % (pre, err_text(page)))
        mshot(page, pre + '03d-platform-error.jpg', keep=True)
        check_writes(pre + '03-rejected-by-platform', h, base, 3)       # المحاولة وصلت المنصة ورفضتها بنصّها
        click(page, '#shBack', 400)
        sheet_gone(page)
        browser.close()

    # —— ٠٤) قائمة الفرص والنموذج الكامل
    if want('04'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'opps')
        wait_rows(page, 11)
        mshot(page, pre + '04-opps-list.jpg')
        click(page, '[data-a="chip"][data-k="oppSt"][data-v="published"]', 350)
        wait_rows(page, 3)
        click(page, '[data-a="chip"][data-k="oppKind"][data-v="grants"]', 350)
        wait_rows(page, 1)
        click(page, '[data-a="chip"][data-k="oppSt"][data-v="all"]', 350)
        click(page, '[data-a="chip"][data-k="oppKind"][data-v="all"]', 350)
        wait_rows(page, 11)
        base = len(h.platform_calls)
        click(page, '[data-a="oppnew"]', 400)
        sheet_open(page)
        pickers = page.evaluate("""() => ['kind', 'country', 'language', 'funding'].map(n => [...document.querySelectorAll('#f_' + n + ' option')].map(o => o.textContent.trim()).filter(t => t.startsWith('أخرى')).length)""")
        expect(pickers == [1, 1, 1, 1], '%s04: «أخرى» في كل قائمة اختيار %r' % (pre, pickers))
        click(page, '#shNext', 300)
        errs = page.evaluate("() => [...document.querySelectorAll('#epModal [data-e]')].filter(e => e.textContent.trim()).map(e => e.dataset.e)")
        expect(set(errs) >= {'kind', 'publish', 'title', 'official_url'}, '%s04: أخطاء النموذج الفاضي %r' % (pre, errs))
        mshot(page, pre + '04b-opp-form-errors.jpg', keep=True)
        page.select_option('#f_kind', 'other')
        page.select_option('#f_publish', 'draft')
        page.fill('#f_title', 'ورشة الكتابة القانونية')
        page.fill('#f_official_url', 'http://bad.example.test/x')
        click(page, '#shNext', 250)
        expect('https' in page.inner_text('[data-e="official_url"]'), '%s04: رابط غير آمن مرّ' % pre)
        page.fill('#f_official_url', 'https://workshop.example.test/apply')
        page.select_option('#f_country', 'other')
        page.wait_for_timeout(150)
        click(page, '#shNext', 250)
        expect('رمز البلد' in page.inner_text('[data-e="country"]'), '%s04: «أخرى» للبلد بلا رمز مرّت %r' % (pre, page.inner_text('[data-e="country"]')))
        page.fill('#f_country_other', 'jp')
        page.select_option('#f_funding', 'varies')
        page.fill('#f_eligibility', 'خريج قانون\nإجادة الإنجليزية')
        page.check('[data-f="featured"]')
        click(page, '#shNext', 350)
        review = page.inner_text('#epModal')
        expect('أخرى (JP)' in review and 'مسودة' in review and 'ورشة الكتابة القانونية' in review and 'نعم' in review, '%s04: مراجعة الإضافة %r' % (pre, review[:200]))
        mshot(page, pre + '04c-opp-review.jpg', keep=True)
        check_writes(pre + '04-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '04-create', h, base, 1)
        if got:
            b = got[0][3]
            expect(b.get('kind') == 'other' and b.get('publish') is False and b.get('country') == 'JP' and b.get('funding') == 'varies' and b.get('featured') is True
                   and b.get('eligibility_ar') == ['خريج قانون', 'إجادة الإنجليزية'] and b.get('official_url') == 'https://workshop.example.test/apply', '%s04: جسم الإضافة %r' % (pre, b))
        wait_rows(page, 12)
        # تعديل: الفرصة المميّزة (صورة + تمييز) ⇒ الفرق فقط
        click(page, '[data-a="oppedit"][data-id="job-7"]', 400)
        sheet_open(page)
        expect(page.input_value('#f_title') == 'منحة الدكتوراه المميّزة' and page.is_checked('[data-f="featured"]'), '%s04: نموذج التعديل ما اتعبّاش' % pre)
        click(page, '#shNext', 250)
        expect('لا يوجد تغيير' in err_text(page), '%s04: تعديل بلا تغيير مرّ %r' % (pre, err_text(page)))
        page.uncheck('[data-f="featured"]')
        page.fill('#f_image', '')
        page.select_option('#f_publish', 'draft')
        click(page, '#shNext', 350)
        review = page.inner_text('#epModal')
        expect('التمييز' in review and 'رابط الصورة' in review and 'النشر' in review and 'العنوان' not in review.replace('العنوان بالإنجليزية', ''), '%s04: فرق التعديل %r' % (pre, review[:200]))
        mshot(page, pre + '04d-opp-edit-review.jpg', keep=True)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '04-edit', h, base, 2)
        if len(got) == 2:
            expect(got[1][3].get('featured') is False and got[1][3].get('image') == '' and got[1][3].get('publish') is False and set(got[1][3]) == {'featured', 'image', 'publish', 'by'},
                   '%s04: جسم التعديل %r' % (pre, got[1][3]))
        # حذف: الوظيفة بلا زر حذف (المنصة ترفضه دائمًا)، والتدريب يُحذف
        click(page, '[data-a="oppedit"][data-id="job-8"]', 400)
        sheet_open(page)
        expect(page.locator('#shDel').count() == 0, '%s04: زر الحذف ظهر على وظيفة' % pre)
        page.evaluate("() => window.closeModal()")
        sheet_gone(page)
        click(page, '[data-a="oppedit"][data-id="job-9"]', 400)
        sheet_open(page)
        click(page, '#shDel', 400)
        sheet_open(page)
        mshot(page, pre + '04e-opp-delete.jpg', keep=True)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '04-delete', h, base, 3)
        if len(got) == 3:
            expect(got[2][0] == 'DELETE' and got[2][1].endswith('/jobs/job-9'), '%s04: حذف التدريب %r' % (pre, got[2][:2]))
        browser.close()

    # —— ٠٥) الاستيراد
    if want('05'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'import')
        base = len(h.platform_calls)
        mshot(page, pre + '05-import.jpg')
        click(page, '[data-a="seedprev"]', 900)
        page.wait_for_selector('[data-r="seed"]')
        nums = page.evaluate("() => [...document.querySelectorAll('[data-r=seed] .sh-nums li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim())")
        expect(nums[0].startswith('٣٤') and nums[1].startswith('١') and nums[2].startswith('٤') and nums[3].startswith('٢'), '%s05: أرقام التجربة %r' % (pre, nums))
        expect('لم يُحفظ شيء' in page.inner_text('[data-r=seed]') and 'تنبيهات' in page.inner_text('[data-r=seed]'), '%s05: نص التجربة' % pre)
        calls = [c for c in h.platform_calls[base:] if 'import-seed' in c[1]]
        expect(len(calls) == 1 and calls[0][2].get('dry_run') == 'true', '%s05: التجربة لازم dry_run %r' % (pre, calls))
        check_writes(pre + '05-after-preview', h, base, 0)
        mshot(page, pre + '05b-import-preview.jpg', target='[data-r=seed]')
        click(page, '[data-a="seedgo"]', 400)
        sheet_open(page)
        mshot(page, pre + '05c-import-confirm.jpg', keep=True)
        check_writes(pre + '05-before-confirm', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '05-import', h, base, 1)
        if got:
            expect(not got[0][3] and not got[0][2].get('dry_run'), '%s05: جسم الاستيراد الحقيقي %r' % (pre, got[0][3:]))
        expect('تم الاستيراد' in note_text(page) and '٣٤' in note_text(page), '%s05: رسالة الاستيراد %r' % (pre, note_text(page)))
        # ملف مرفوع: صالح ثم غير صالح
        page.set_input_files('#shSeedFile', files=[{'name': 'seed.json', 'mimeType': 'application/json', 'buffer': json.dumps({'items': [{'id': 'a'}, {'id': 'b'}]}).encode('utf-8')}])
        page.wait_for_function("() => document.querySelector('.sh-cur') && document.querySelector('.sh-cur').innerText.includes('seed.json')", timeout=8000)
        click(page, '[data-a="seedprev"]', 900)
        page.wait_for_selector('[data-r="seed"]')
        calls = [c for c in h.platform_calls[base:] if 'import-seed' in c[1] and (c[2] or {}).get('dry_run')]
        expect(len(calls) == 2 and (calls[-1][3] or {}).get('items') == [{'id': 'a'}, {'id': 'b'}], '%s05: الملف المرفوع ما وصلش للتجربة %r' % (pre, calls[-1:]))
        page.set_input_files('#shSeedFile', files=[{'name': 'bad.json', 'mimeType': 'application/json', 'buffer': b'{"x": 1}'}])
        page.wait_for_function("() => /غير صالح/.test(document.body.innerText)", timeout=8000)
        mshot(page, pre + '05d-import-bad-file.jpg', keep=False)
        browser.close()

    # —— ٠٦) رابط دورة التحضير
    if want('06'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'prep')
        base = len(h.platform_calls)
        mshot(page, pre + '06-prep.jpg')
        page.fill('#shPrep', 'http://insecure.example.test/p')
        click(page, '[data-a="prepsave"]', 300)
        expect('https' in page.inner_text('#shPrepErr'), '%s06: رابط غير آمن مرّ' % pre)
        page.fill('#shPrep', 'https://courses.example.test/prep')
        click(page, '[data-a="prepsave"]', 300)
        expect('هذا هو الرابط' in page.inner_text('#shPrepErr'), '%s06: نفس الرابط مرّ' % pre)
        page.fill('#shPrep', 'https://learn.example.test/english')
        click(page, '[data-a="prepsave"]', 400)
        sheet_open(page)
        expect('learn.example.test' in page.inner_text('#epModal') and 'courses.example.test' in page.inner_text('#epModal'), '%s06: فرق الرابط' % pre)
        mshot(page, pre + '06b-prep-review.jpg', keep=True)
        check_writes(pre + '06-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '06-save', h, base, 1)
        if got:
            expect(got[0][3].get('prep_course_url') == 'https://learn.example.test/english', '%s06: جسم الحفظ %r' % (pre, got[0][3]))
        page.wait_for_function("() => { const a = document.querySelector('.sh-cur a'); return a && a.innerText.trim() === 'افتح الرابط' && a.getAttribute('href').includes('learn.example.test') && a.getAttribute('title').includes('learn.example.test') && !document.querySelector('.sh-cur').innerText.includes('learn.example.test'); }", timeout=8000)
        click(page, '[data-a="prepclear"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '06-clear', h, base, 2)
        if len(got) == 2:
            expect(got[1][3].get('prep_course_url') == '', '%s06: جسم المسح %r' % (pre, got[1][3]))
        page.wait_for_function("() => document.querySelector('.sh-cur') && document.querySelector('.sh-cur').innerText.includes('لا يوجد رابط')", timeout=8000)
        browser.close()

    # —— ٠٧) الآراء
    if want('07'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'opinions')
        wait_rows(page, 2)
        mshot(page, pre + '07-opinions.jpg')
        topics = page.evaluate("() => [...document.querySelectorAll('#shTopic option')].map(o => o.textContent.trim())")
        expect(topics[0] == 'كل النقاشات' and len(topics) == 3, '%s07: قائمة النقاشات %r' % (pre, topics))
        page.select_option('#shTopic', 'tp-1')
        wait_rows(page, 1)
        page.select_option('#shTopic', '')
        wait_rows(page, 2)
        click(page, '[data-a="chip"][data-v="approved"]', 600)
        wait_rows(page, 2)
        base = len(h.platform_calls)
        click(page, '[data-a="ophide"][data-id="op-3"]', 400)
        sheet_open(page)
        mshot(page, pre + '07b-opinion-hide.jpg', keep=True)
        check_writes(pre + '07-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '07-hide', h, base, 1)
        if got:
            expect(got[0][1].endswith('/opinions/op-3/reject'), '%s07: مسار الإخفاء %r' % (pre, got[0][1]))
        wait_rows(page, 1)
        click(page, '[data-a="chip"][data-v="rejected"]', 600)
        wait_rows(page, 2)
        click(page, '[data-a="opshow"][data-id="op-5"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '07-restore', h, base, 2)
        if len(got) == 2:
            expect(got[1][1].endswith('/opinions/op-5/approve'), '%s07: مسار الإظهار %r' % (pre, got[1][1]))
        browser.close()

    # —— ٠٧ت) النقاشات: إخفاء/إرجاع + فحص الصلة بالقانون ثم إخفاء المختار (R17)
    if want('07t'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'topics')
        wait_rows(page, 2, '[data-a="topichide"]')
        mshot(page, pre + '07t-topics.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="topichide"][data-id="tp-1"]', 400)
        sheet_open(page)
        mshot(page, pre + '07t2-topic-hide.jpg', keep=True)
        check_writes(pre + '07t-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '07t-hide', h, base, 1)
        if got:
            expect(got[0][1].endswith('/topics/tp-1/hide'), '%s07t: مسار الإخفاء %r' % (pre, got[0][1]))
        click(page, '[data-a="chip"][data-v="hidden"]', 700)
        wait_rows(page, 1, '[data-a="topicshow"]')
        mshot(page, pre + '07t3-topics-hidden.jpg')
        click(page, '[data-a="topicshow"][data-id="tp-1"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '07t-restore', h, base, 2)
        if len(got) == 2:
            expect(got[1][1].endswith('/topics/tp-1/restore'), '%s07t: مسار الإرجاع %r' % (pre, got[1][1]))
        click(page, '[data-a="chip"][data-v="open"]', 700)
        click(page, '[data-a="gatecheck"]', 1200)
        page.wait_for_selector('.sh-panel[data-r="gate"]', timeout=10000)
        mshot(page, pre + '07t4-gate-check.jpg', target='.sh-panel[data-r="gate"]')
        panel = page.inner_text('.sh-panel[data-r="gate"]')
        expect('لم يتغير شيء بعد' in panel and 'نتيجة مباراة الأمس' in panel, '%s07t: نتيجة الفحص %r' % (pre, panel[:120]))
        click(page, '[data-a="gatetoggle"][data-id="nw-off"]', 400)       # الخبر ده يفضل كما هو
        expect('أخفِ المحدد (١)' in page.inner_text('.sh-panel[data-r="gate"]'), '%s07t: عدد المختار' % pre)
        click(page, '[data-a="gateapply"]', 400)
        sheet_open(page)
        mshot(page, pre + '07t5-gate-apply.jpg', keep=True)
        confirm(page, 1200)
        sheet_gone(page)
        got = check_writes(pre + '07t-apply', h, base, 3)                    # الفحص تجربة مش كتابة
        if len(got) == 3:
            expect(got[2][3].get('apply') is True and got[2][3].get('ids') == ['tp-2'], '%s07t: جسم الإخفاء %r' % (pre, got[2][3]))
        expect('تم الإخفاء' in page.inner_text('.sh-panel[data-r="gate"]'), '%s07t: حالة ما بعد الإخفاء' % pre)
        browser.close()

    # —— ٠٨) التذكير
    if want('08'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile)
        go_sub(page, 'reminders')
        expect('لم يُشغَّل بعد' in page.inner_text('.sh-panel'), '%s08: حالة البداية %r' % (pre, page.inner_text('.sh-panel')[:80]))
        base = len(h.platform_calls)
        mshot(page, pre + '08-reminders-never.jpg')
        click(page, '[data-a="remrun"]', 400)
        sheet_open(page)
        mshot(page, pre + '08b-reminders-confirm.jpg', keep=True)
        check_writes(pre + '08-before', h, base, 0)
        confirm(page, 1200)
        sheet_gone(page)
        got = check_writes(pre + '08-run-locked', h, base, 1)
        if got:
            expect(got[0][1].endswith('/run-reminders') and got[0][3].get('by') and got[0][3].get('by') != 'cron', '%s08: جسم التشغيل %r' % (pre, got[0][3]))
        page.wait_for_function("() => /التذكير مقفول/.test(document.querySelector('.sh-panel') ? document.querySelector('.sh-panel').innerText : '')", timeout=10000)
        expect('التذكير مقفول' in note_text(page), '%s08: رسالة المقفول %r' % (pre, note_text(page)))
        mshot(page, pre + '08c-reminders-locked.jpg')
        back_hub(page)
        nums = tile_numbers(page)
        expect(nums.get('reminders') == ('مقفول', 'التذكير مقفول'), '%s08: مربّع التذكير المقفول %r' % (pre, nums.get('reminders')))
        mshot(page, pre + '08d-hub-locked.jpg', keep=False)
        # المنصة فتحت التذكير
        ef.reminders_enabled = True
        go_sub(page, 'reminders')
        click(page, '[data-a="remrun"]', 400)
        sheet_open(page)
        confirm(page, 1200)
        sheet_gone(page)
        check_writes(pre + '08-run-open', h, base, 2)
        page.wait_for_function("() => /التذكير مفتوح/.test(document.querySelector('.sh-panel') ? document.querySelector('.sh-panel').innerText : '')", timeout=10000)
        expect('أُرسل ٥ تذكيرات' in note_text(page), '%s08: رسالة الإرسال %r' % (pre, note_text(page)))
        nums = page.evaluate("() => [...document.querySelectorAll('.sh-nums li')].map(li => li.innerText.replace(/\\s+/g, ' ').trim())")
        expect(nums[1].startswith('٥') and len(nums) == 5, '%s08: أرقام آخر تشغيل %r' % (pre, nums))
        mshot(page, pre + '08e-reminders-open.jpg')
        browser.close()


    # —— ٠٨م) محرّك الفرص (R18): المفتاح · المواعيد · تشغيل الآن · للمراجعة · المصادر · إيميل الأسبوع
    if want('08m'):
        flow_engine(browser, h, pre, vp, mobile)


def sheet_text(page):
    return page.evaluate("() => (document.getElementById('epModal') || {innerText: ''}).innerText")


def flow_engine(browser, h, pre, vp, mobile):
    ef = sfx.SahaTilesPlatform()
    page = sopen(browser, h, ef, vp, mobile)
    go_sub(page, 'engine')
    page.wait_for_selector('.sh-panel[data-r="auto"]', timeout=10000)
    sw = page.evaluate("() => { const b = document.querySelector('.sh-switch'); return b ? [b.getAttribute('aria-checked'), b.innerText.replace(/\\s+/g, ' ')] : null; }")
    expect(sw and sw[0] == 'false' and 'متوقّف' in sw[1], '%s08m: المفتاح في البداية %r' % (pre, sw))
    last = page.inner_text('.sh-panel[data-r="last"]')
    expect('اكتمل آخر تشغيل وفيه أعطال' in last and '٢٤' in last, '%s08m: آخر تشغيل %r' % (pre, last[:160]))
    mshot(page, pre + '08m-engine-run.jpg')
    base = len(h.platform_calls)
    # المفتاح ⇒ ورقة مراجعة ثم تأكيد
    click(page, '[data-a="engauto"]', 400)
    sheet_open(page)
    expect('يعمل' in sheet_text(page) and 'متوقّف' in sheet_text(page), '%s08m: ورقة المفتاح بلا قبل ⇐ بعد' % pre)
    mshot(page, pre + '08m2-engine-switch-sheet.jpg', keep=True)
    check_writes(pre + '08m-before', h, base, 0)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-switch', h, base, 1)
    if got:
        expect(got[0][3] == {'enabled': True}, '%s08m: جسم المفتاح %r' % (pre, got[0][3]))
    page.wait_for_function("() => (document.querySelector('.sh-switch') || {}).getAttribute && document.querySelector('.sh-switch').getAttribute('aria-checked') === 'true'", timeout=10000)
    expect('التشغيل اليومي يعمل الآن' in note_text(page), '%s08m: رسالة المفتاح %r' % (pre, note_text(page)))
    # المواعيد
    click(page, '[data-a="enghours"]', 400)
    sheet_open(page)
    page.fill('#f_hours', '٧، ١٩')
    click(page, '#shNext', 400)
    stage(page, '٧ صباحًا و٧ مساءً')
    mshot(page, pre + '08m3-engine-hours.jpg', keep=True)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-hours', h, base, 2)
    if len(got) == 2:
        expect(got[1][3] == {'enabled': True, 'hours': '7,19'}, '%s08m: جسم المواعيد %r' % (pre, got[1][3]))
    # شغّل الآن
    click(page, '[data-a="engrun"]', 400)
    sheet_open(page)
    confirm(page, 1200)
    sheet_gone(page)
    got = check_writes(pre + '08m-run', h, base, 3)
    if len(got) == 3:
        expect(got[2][1].endswith('/opportunities/run') and got[2][3] == {}, '%s08m: جسم التشغيل %r' % (pre, got[2][3]))
    expect(note_text(page) == 'اكتمل التشغيل: نُشرت فرصة واحدة، ٣ مسودات للمراجعة', '%s08m: رسالة التشغيل %r' % (pre, note_text(page)))
    mshot(page, pre + '08m4-engine-after-run.jpg')
    # للمراجعة: الشارة ثم نشر ورفض بسبب (مسار القرار الموجود)
    click(page, '[data-a="chip"][data-v="review"]', 700)
    wait_rows(page, 2, '.sh-card[data-id]')
    badge = page.evaluate("() => [...document.querySelectorAll('.sh-card[data-id]')].map(c => [c.dataset.id, c.innerText.includes('غالبًا مكررة')])")
    expect(badge == [['job-30', False], ['job-31', True]], '%s08m: شارة «غالبًا مكررة» %r' % (pre, badge))
    expect('صلته بالقانون ضعيفة' in page.inner_text('.sh-card[data-id="job-31"]') and 'منح الاتحاد الأوروبي' in page.inner_text('.sh-card[data-id="job-30"]'),
           '%s08m: سبب الفحص واسم المصدر' % pre)
    mshot(page, pre + '08m5-engine-review.jpg')
    click(page, '[data-a="engpub"][data-id="job-30"]', 400)
    sheet_open(page)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-publish', h, base, 4)
    if len(got) == 4:
        expect(got[3][1] == '/api/bridge/jobs/job-30/decide' and got[3][3].get('decision') == 'approve', '%s08m: نشر المسودة %r' % (pre, got[3]))
    wait_rows(page, 1, '.sh-card[data-id]')
    click(page, '[data-a="engrej"][data-id="job-31"]', 400)
    sheet_open(page)
    page.fill('#f_reason', 'مكررة مع فرصة منشورة')
    click(page, '#shNext', 400)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-reject', h, base, 5)
    if len(got) == 5:
        expect(got[4][3].get('decision') == 'reject' and got[4][3].get('reason') == 'مكررة مع فرصة منشورة', '%s08m: رفض المسودة %r' % (pre, got[4][3]))
    page.wait_for_selector('.v2s-sh .sh-empty', timeout=10000)
    # المصادر: توثيق مصدر (الصف كاملًا بالحقل المتغيّر)
    click(page, '[data-a="chip"][data-v="sources"]', 700)
    wait_rows(page, 3, '[data-a="engsrctr"]')
    mshot(page, pre + '08m6-engine-sources.jpg')
    click(page, '[data-a="engsrctr"][data-id="eu-grants"]', 400)
    sheet_open(page)
    expect('مباشرة' in sheet_text(page), '%s08m: ورقة التوثيق لا تشرح النشر المباشر' % pre)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-trust', h, base, 6)
    if len(got) == 6:
        expect(got[5][1].endswith('/sources/eu-grants') and got[5][3].get('trusted') is True and got[5][3].get('url') == 'https://grants.example.test/eu'
               and got[5][3].get('enabled') is True, '%s08m: جسم التوثيق %r' % (pre, got[5][3]))
    # إيميل الأسبوع: المفتاح · المعاينة بلا كتابة · رسالة التجربة بتأكيد
    click(page, '[data-a="chip"][data-v="digest"]', 700)
    page.wait_for_selector('.sh-panel[data-r="digest"]', timeout=10000)
    mshot(page, pre + '08m7-engine-digest.jpg')
    click(page, '[data-a="engdig"]', 400)
    sheet_open(page)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-digest', h, base, 7)
    if len(got) == 7:
        expect(got[6][3] == {'enabled': True}, '%s08m: جسم إيميل الأسبوع %r' % (pre, got[6][3]))
    page.fill('#shEngMail', 'member@example.test')
    click(page, '[data-a="engprev"]', 900)
    page.wait_for_selector('iframe.sh-pv', timeout=10000)
    fr = page.evaluate("() => { const f = document.querySelector('iframe.sh-pv'); return [f.getAttribute('sandbox'), (f.getAttribute('srcdoc') || '').includes('لايدن')]; }")
    expect(fr == ['', True], '%s08m: إطار المعاينة معزول وفيه الرسالة %r' % (pre, fr))
    check_writes(pre + '08m-preview', h, base, 7)
    pvt = page.inner_text('.sh-panel[data-r="pv"]')
    expect('المسار: القانون الدولي' in pvt and 'intl-law' not in pvt and not page.query_selector('[data-r="pvwarn"]'),
           '%s08m: المعاينة باسم المسار العربي بلا تنبيه %r' % (pre, pvt[:200]))
    mshot(page, pre + '08m8-engine-preview.jpg', target='.sh-panel[data-r="pv"]')
    # صاحب البريد أوقف الرسائل: المعاينة تظهر ومعها إن الرسالة مش هتوصله
    page.fill('#shEngMail', 'unsub@example.test')
    click(page, '[data-a="engprev"]', 900)
    page.wait_for_selector('[data-r="pvwarn"]', timeout=10000)
    wt = page.inner_text('[data-r="pvwarn"]')
    expect('أوقف رسائل المنصة' in wt and page.query_selector('iframe.sh-pv') is not None, '%s08m: تنبيه إيقاف الرسائل %r' % (pre, wt))
    mshot(page, pre + '08m8b-engine-preview-unsub.jpg', target='.sh-panel[data-r="pv"]')
    # بريد مش لعضو: السبب مكان «لا فرص»
    page.fill('#shEngMail', 'nobody@example.test')
    click(page, '[data-a="engprev"]', 900)
    page.wait_for_function("() => { const w = document.querySelector('[data-r=\"pvwarn\"]'); return w && w.innerText.includes('ليس لعضو'); }", timeout=10000)
    pvt = page.inner_text('.sh-panel[data-r="pv"]')
    expect('لا فرص' not in pvt and 'لا نص للرسالة' not in pvt and page.query_selector('iframe.sh-pv') is None, '%s08m: بريد ليس لعضو %r' % (pre, pvt[:200]))
    check_writes(pre + '08m-preview2', h, base, 7)
    page.fill('#shEngMail', 'member@example.test')
    click(page, '[data-a="engtest"]', 400)
    sheet_open(page)
    expect('member@example.test' in sheet_text(page), '%s08m: ورقة التجربة لا تعرض البريد' % pre)
    confirm(page, 1000)
    sheet_gone(page)
    got = check_writes(pre + '08m-test', h, base, 8)
    if len(got) == 8:
        expect(got[7][3] == {'email': 'member@example.test'}, '%s08m: جسم رسالة التجربة %r' % (pre, got[7][3]))
    expect(note_text(page).startswith('أُرسلت رسالة التجربة') and 'مسار آخر' in note_text(page), '%s08m: نتيجة التجربة %r' % (pre, note_text(page)))
    back_hub(page)
    nums = tile_numbers(page)
    expect(nums.get('engine') == ('٠', 'لا مسودات تنتظر'), '%s08m: مربّع المحرّك بعد المراجعة %r' % (pre, nums.get('engine')))
    browser.close()
    # منصة فاضية: «لا مصادر بعد» ⇒ «إضافة المصادر الأولى»
    ef2 = sfx.SahaTilesPlatform(empty=True)
    page = sopen(browser, h, ef2, vp, mobile)
    go_sub(page, 'engine')
    expect('لم يحدث أي تشغيل بعد' in page.inner_text('.sh-panel[data-r="last"]'), '%s08m: آخر تشغيل في البداية' % pre)
    click(page, '[data-a="chip"][data-v="sources"]', 700)
    page.wait_for_selector('.v2s-sh .sh-empty', timeout=10000)
    mshot(page, pre + '08m9-engine-sources-empty.jpg')
    base = len(h.platform_calls)
    click(page, '[data-a="engseed"]', 400)
    sheet_open(page)
    confirm(page, 1000)
    sheet_gone(page)
    check_writes(pre + '08m-seed', h, base, 1)
    wait_rows(page, 3, '[data-a="engsrctr"]')
    expect('أُضيف ٣ مصادر' in note_text(page), '%s08m: رسالة إضافة المصادر %r' % (pre, note_text(page)))
    browser.close()


# ======================================================================= الديوان
def flow_diwan(browser, h, pre, vp, mobile):
    D = '#s/content/diwan'
    if want('09'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile, D)
        nums = tile_numbers(page)
        expect(nums.get('works') == ('٣', 'عمل ينتظر قرارك') and nums.get('comments') == ('٣', 'تعليق ظاهر للقرّاء') and nums.get('challenges') == ('١', 'تحدٍّ مفتوح الآن')
               and nums.get('report') == ('—', 'لا رقم بعد'), '%s09: أرقام مربّعات الديوان %r' % (pre, nums))
        mshot(page, pre + '09-diwan-hub.jpg')
        browser.close()

    if want('10'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile, D)
        go_sub(page, 'works')
        wait_rows(page, 3, '.sh-card')
        mshot(page, pre + '10-works.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="work"][data-w="approve"][data-id="CR_1"]', 400)
        sheet_open(page)
        check_writes(pre + '10-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '10-approve', h, base, 1)
        if got:
            expect(got[0][1].endswith('/creative/CR_1/decide') and got[0][3] == {'decision': 'approve', 'by': got[0][3].get('by')}, '%s10: جسم الاعتماد %r' % (pre, got[0][3]))
        wait_rows(page, 2, '.sh-card')
        click(page, '[data-a="work"][data-w="reject"][data-id="CR_2"]', 400)
        sheet_open(page)
        click(page, '#shNext', 250)
        expect('٣ أحرف' in err_text(page), '%s10: رفض بلا سبب ما اتمنعش' % pre)
        page.fill('#f_reason', 'لا يناسب شروط الديوان')
        page.fill('#f_note', 'نرحب بمشاركتك في تحدٍّ قادم')
        click(page, '#shNext', 300)
        mshot(page, pre + '10b-work-reject.jpg', keep=True)
        check_writes(pre + '10-reject-before', h, base, 1)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '10-reject', h, base, 2)
        if len(got) == 2:
            expect(got[1][3].get('decision') == 'reject' and got[1][3].get('reason') == 'لا يناسب شروط الديوان' and got[1][3].get('note') == 'نرحب بمشاركتك في تحدٍّ قادم', '%s10: جسم الرفض %r' % (pre, got[1][3]))
        click(page, '[data-a="chip"][data-v="published"]', 600)
        wait_rows(page, 4, '.sh-card')          # الثلاثة المنشورة + العمل اللي اعتُمد الآن
        # تمييز بتاريخ نهاية
        click(page, '[data-a="work"][data-w="feature"][data-id="CR_4"]', 400)
        sheet_open(page)
        page.fill('#f_until', '2026-12-01')
        click(page, '#shNext', 300)
        expect('٢٠٢٦' in page.inner_text('#epModal') or 'ديسمبر' in page.inner_text('#epModal'), '%s10: تاريخ التمييز %r' % (pre, page.inner_text('#epModal')[:120]))
        mshot(page, pre + '10c-work-feature.jpg', keep=True)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '10-feature', h, base, 3)
        if len(got) == 3:
            expect(got[2][0] == 'PUT' and got[2][3].get('featured') is False and got[2][3].get('featured_until') == '2026-12-01T23:59:59+02:00', '%s10: جسم التمييز %r' % (pre, got[2][3]))
        # إلغاء التمييز وفتح التعليقات على CR_6 (مميّز ومقفول)
        click(page, '[data-a="work"][data-w="unfeature"][data-id="CR_6"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        click(page, '[data-a="work"][data-w="unlock"][data-id="CR_6"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '10-unfeature-unlock', h, base, 5)
        if len(got) == 5:
            expect(got[3][3].get('featured') is False and got[4][3].get('comments_locked') is False, '%s10: جسما إلغاء التمييز والفتح %r %r' % (pre, got[3][3], got[4][3]))
        # قفل وإخفاء ثم إظهار
        click(page, '[data-a="work"][data-w="lock"][data-id="CR_5"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        click(page, '[data-a="work"][data-w="hide"][data-id="CR_5"]', 400)
        sheet_open(page)
        mshot(page, pre + '10d-work-hide.jpg', keep=True)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '10-lock-hide', h, base, 7)
        if len(got) == 7:
            expect(got[5][3].get('comments_locked') is True and got[6][3].get('status') == 'hidden', '%s10: جسما القفل والإخفاء %r %r' % (pre, got[5][3], got[6][3]))
        click(page, '[data-a="chip"][data-v="hidden"]', 600)
        wait_rows(page, 2, '.sh-card')
        click(page, '[data-a="work"][data-w="show"][data-id="CR_7"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '10-show', h, base, 8)
        if len(got) == 8:
            expect(got[7][3].get('status') == 'published', '%s10: جسم الإظهار %r' % (pre, got[7][3]))
        browser.close()

    if want('11'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile, D)
        go_sub(page, 'comments')
        wait_rows(page, 3)
        mshot(page, pre + '11-comments.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="chide"][data-id="cm-2"]', 400)
        sheet_open(page)
        mshot(page, pre + '11b-comment-hide.jpg', keep=True)
        check_writes(pre + '11-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '11-hide', h, base, 1)
        if got:
            expect(got[0][1].endswith('/diwan/comments/cm-2/hide'), '%s11: مسار الإخفاء %r' % (pre, got[0][1]))
        wait_rows(page, 2)
        click(page, '[data-a="chip"][data-v="hidden"]', 600)
        wait_rows(page, 2)
        expect(page.evaluate("() => !document.querySelector('[data-a=chide]')"), '%s11: زرّ الإخفاء ظهر على تعليق مخفي' % pre)
        browser.close()

    if want('12'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile, D)
        go_sub(page, 'challenges')
        wait_rows(page, 4)
        mshot(page, pre + '12-challenges.jpg')
        expect(page.evaluate("() => !!document.querySelector('[data-a=chwin][data-id=CH_2]') && !document.querySelector('[data-a=chwin][data-id=CH_3]') && !document.querySelector('[data-a=chwin][data-id=CH_4]')"),
               '%s12: زرّ الفائزين لازم على المغلق وحده' % pre)
        base = len(h.platform_calls)
        click(page, '[data-a="chnew"]', 400)
        sheet_open(page)
        kinds = page.evaluate("() => [...document.querySelectorAll('[data-fm=kinds]')].map(i => i.parentNode.innerText.trim())")
        ptypes = page.evaluate("() => [...document.querySelectorAll('#f_prize_type_0 option')].map(o => o.textContent.trim())")
        expect(kinds[-1] == 'أخرى' and ptypes[-1] == 'أخرى', '%s12: «أخرى» في أنواع الأعمال والجوائز %r %r' % (pre, kinds, ptypes))
        click(page, '#shNext', 300)
        errs = page.evaluate("() => [...document.querySelectorAll('#epModal [data-e]')].filter(e => e.textContent.trim()).map(e => e.dataset.e)")
        expect({'title', 'opens_at', 'closes_at'} <= set(errs), '%s12: أخطاء النموذج الفاضي %r' % (pre, errs))
        mshot(page, pre + '12b-challenge-errors.jpg', keep=True)
        page.fill('#f_title', 'تحدّي الرسالة القانونية')
        page.fill('#f_brief', 'اكتب رسالة قصيرة إلى قاضٍ تخيّلي')
        page.fill('#f_word_cap', '٥٠٠')
        page.fill('#f_opens_at', '2026-12-01')
        page.fill('#f_closes_at', '2026-12-01')
        click(page, '#shNext', 250)
        expect('بعد البدء' in page.inner_text('[data-e="closes_at"]'), '%s12: إغلاق قبل البدء مرّ' % pre)
        page.fill('#f_closes_at', '2026-12-20')
        page.select_option('#f_status', 'open')
        page.fill('#f_prize_label_0', 'شهادة المركز الأول')
        page.fill('#f_jury_name_0', 'د. منى')
        page.fill('#f_jury_name_1', 'أ. كريم')
        click(page, '#shNext', 250)
        expect('ثلاثة أعضاء' in page.inner_text('[data-e="jury"]'), '%s12: فتح بلجنة غير مكتملة مرّ %r' % (pre, page.inner_text('[data-e="jury"]')))
        click(page, '[data-add="jury"]', 300)
        n_jury = page.evaluate("() => document.querySelectorAll('[data-row=jury]').length")
        expect(n_jury == 4 and page.input_value('#f_jury_name_0') == 'د. منى' and page.input_value('#f_title') == 'تحدّي الرسالة القانونية', '%s12: إضافة محكّم أضاعت ما كُتب (%s)' % (pre, n_jury))
        click(page, '[data-rm="jury"][data-i="3"]', 300)
        page.fill('#f_jury_name_2', 'أ. ريم')
        page.select_option('#f_prize_type_0', 'other')
        page.select_option('#f_prize_place_0', '1')
        click(page, '#shNext', 350)
        review = page.inner_text('#epModal')
        expect('مفتوح' in review and 'د. منى' in review and 'شهادة المركز الأول' in review and 'الأول' in review, '%s12: مراجعة التحدّي %r' % (pre, review[:200]))
        mshot(page, pre + '12c-challenge-review.jpg', keep=True)
        check_writes(pre + '12-before', h, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '12-create', h, base, 1)
        if got:
            b = got[0][3]
            expect(b.get('status') == 'open' and len(b.get('jury', [])) == 3 and b.get('word_cap') == 500 and b.get('kind_allowed') == ['story']
                   and b.get('opens_at') == '2026-12-01' and str(b.get('closes_at')).endswith('T23:59:59+02:00') and b.get('prizes') == [{'type': 'certificate', 'label': 'شهادة المركز الأول', 'ref': '', 'place': 1}], '%s12: جسم الإنشاء %r' % (pre, b))
        wait_rows(page, 5)
        # تعديل مسودة: الوصف فقط
        click(page, '[data-a="chedit"][data-id="CH_1"]', 400)
        sheet_open(page)
        page.fill('#f_brief', 'وصف جديد للتحدّي')
        click(page, '#shNext', 350)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '12-edit', h, base, 2)
        if len(got) == 2:
            expect(set(got[1][3]) == {'brief', 'by'}, '%s12: جسم التعديل لازم الوصف وحده %r' % (pre, got[1][3]))
        # تعديل تحدٍّ أُعلنت نتيجته ⇒ رد المنصة بنصه
        click(page, '[data-a="chedit"][data-id="CH_4"]', 400)
        sheet_open(page)
        page.fill('#f_title', 'عنوان مغيَّر')
        click(page, '#shNext', 300)
        confirm(page, 900)
        expect('أُعلنت النتائج' in err_text(page), '%s12: رد المنصة على تعديل نتيجة معلنة %r' % (pre, err_text(page)))
        click(page, '#shBack', 300)
        click(page, '#shNo', 400)
        sheet_gone(page)
        # الفائزون
        click(page, '[data-a="chwin"][data-id="CH_2"]', 800)
        sheet_open(page)
        picks = page.evaluate("() => [...document.querySelectorAll('#f_w_work_1 option')].map(o => o.textContent.trim())")
        expect(len(picks) == 4 and picks[0] == 'اختر العمل', '%s12: أعمال التحدّي المنشورة %r' % (pre, picks))
        click(page, '#shNext', 250)
        expect('فائزًا واحدًا' in err_text(page), '%s12: بلا فائز مرّ %r' % (pre, err_text(page)))
        page.select_option('#f_w_work_1', 'CR_4')
        click(page, '#shNext', 250)
        expect('سطر اللجنة' in err_text(page), '%s12: بلا سطر لجنة مرّ %r' % (pre, err_text(page)))
        page.fill('#f_w_line_1', 'أجمل بداية قرأناها')
        page.select_option('#f_w_work_2', 'CR_4')
        page.fill('#f_w_line_2', 'نفس العمل')
        click(page, '#shNext', 250)
        expect('لا يتكرر' in err_text(page), '%s12: عمل مكرر مرّ %r' % (pre, err_text(page)))
        page.select_option('#f_w_work_2', 'CR_5')
        page.fill('#f_w_line_2', 'لغة نقية ومؤثرة')
        click(page, '#shNext', 350)
        review = page.inner_text('#epModal')
        expect('المركز الأول' in review and 'المركز الثاني' in review and 'أجمل بداية قرأناها' in review and 'راجع الأسماء جيدًا' in review, '%s12: ورقة تأكيد الفائزين %r' % (pre, review[:200]))
        mshot(page, pre + '12d-winners-confirm.jpg', keep=True)
        check_writes(pre + '12-win-before', h, base, 3)        # + محاولة تعديل التحدّي المعلَن اللي المنصة رفضتها
        confirm(page, 1200)
        sheet_gone(page)
        got = check_writes(pre + '12-winners', h, base, 4)
        if len(got) == 4:
            expect(got[3][3].get('winners') == [{'place': 1, 'work_id': 'CR_4', 'jury_line': 'أجمل بداية قرأناها'}, {'place': 2, 'work_id': 'CR_5', 'jury_line': 'لغة نقية ومؤثرة'}], '%s12: جسم الفائزين %r' % (pre, got[3][3]))
        expect('أُعلنت النتيجة' in note_text(page) and 'شهادتان' in note_text(page), '%s12: رسالة الفائزين %r' % (pre, note_text(page)))
        expect(page.evaluate("() => !document.querySelector('[data-a=chwin]')"), '%s12: زرّ الفائزين ظهر بعد الإعلان' % pre)
        browser.close()

    if want('13'):
        ef = sfx.SahaTilesPlatform()
        page = sopen(browser, h, ef, vp, mobile, D)
        go_sub(page, 'report')
        cards = page.evaluate("() => [...document.querySelectorAll('.sh-stat-card')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())")
        expect(len(cards) == 6, '%s13: بطاقات التقرير %r' % (pre, cards))
        na = [c for c in cards if 'لا رقم بعد' in c]
        expect(len(na) == 4 and any(c.startswith('٠ ') for c in cards), '%s13: الغايب «لا رقم بعد» والصفر الحقيقي ٠ %r' % (pre, cards))
        expect(any('٣ من ٤' in c and '٧٥٪' in c for c in cards) or any('٣ من ٤' in c for c in cards), '%s13: نسبة القبول %r' % (pre, cards))
        mshot(page, pre + '13-report-empty.jpg')
        ef.sd_report = dict(sfx.REPORT_FULL)
        click(page, '[data-a="chip"][data-v="90"]', 800)
        page.wait_for_function("() => document.querySelector('.sh-stat-card') && !document.querySelector('.sh-skel')", timeout=8000)
        cards = page.evaluate("() => [...document.querySelectorAll('.sh-stat-card')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())")
        expect(any('١٬٢٤٠' in c for c in cards) and any('٣٥٪' in c for c in cards) and not any('لا رقم بعد' in c for c in cards), '%s13: التقرير الكامل %r' % (pre, cards))
        mshot(page, pre + '13b-report-full.jpg')
        browser.close()


# ======================================================================= مصدر واقع · جسر غايب · مفتاح مقفول
def flow_down(browser, h, pre, vp, mobile):
    if want('14'):
        ef = sfx.SahaTilesPlatform()
        ef.down = {'/api/bridge/news'}
        ef.missing = {'/api/bridge/diwan/comments'}
        page = sopen(browser, h, ef, vp, mobile)
        nums = tile_numbers(page)
        expect(nums.get('news') == ('—', 'غير متاح بعد') and nums.get('review') == ('٦', 'إعلان ينتظر قرارك'), '%s14: مربّع المصدر الواقع %r' % (pre, nums.get('news')))
        expect(page.evaluate("() => !!document.querySelector('.sh-warn')"), '%s14: تنبيه الأرقام غير المتاحة ما ظهرش' % pre)
        mshot(page, pre + '14-hub-down.jpg')
        go_sub(page, 'news')
        expect('غير متاح بعد' in page.inner_text('.sh-warn') and page.evaluate("() => !!document.querySelector('.sh-warn [data-a=retry]')"), '%s14: شاشة الأخبار الواقعة' % pre)
        expect(page.evaluate("() => !document.querySelector('.sh-empty')"), '%s14: «لا أخبار» ظهرت بدل «غير متاح»' % pre)
        mshot(page, pre + '14b-news-down.jpg')
        ef.down = set()
        click(page, '[data-a="retry"]', 900)
        wait_rows(page, 3)
        browser.close()
        # الجسر غايب في الديوان (التعليقات ٤٠٤) ⇒ «غير متاح بعد» لا «لا شيء»
        ef2 = sfx.SahaTilesPlatform()
        ef2.missing = {'/api/bridge/diwan/comments'}
        page = sopen(browser, h, ef2, vp, mobile, '#s/content/diwan')
        nums = tile_numbers(page)
        expect(nums.get('comments') == ('—', 'غير متاح بعد'), '%s14: جسر التعليقات الغايب %r' % (pre, nums.get('comments')))
        go_sub(page, 'comments')
        expect('غير متاح بعد' in page.inner_text('.sh-warn'), '%s14: شاشة التعليقات والجسر غايب' % pre)
        mshot(page, pre + '14c-comments-missing.jpg', keep=False)
        browser.close()


def flow_empty(browser, h, pre, vp, mobile):
    """١٥) الحالات الفاضية الحقيقية: منصة سليمة بلا بيانات ⇒ «لا … بعد» (تختلف عن «غير متاح بعد» في ١٤)."""
    if not want('15'):
        return
    steps = (('saha', '#s/content/saha', (('news', 'b-news', '15b-news-empty.jpg'), ('review', 'b-review', '15c-review-empty.jpg'), ('opps', 'b-opps', '15d-opps-empty.jpg'),
                                           ('opinions', 'b-opinions', '15e-opinions-empty.jpg'))),
             ('diwan', '#s/content/diwan', (('works', 'b-works', '15f-works-empty.jpg'), ('comments', 'b-comments', '15g-comments-empty.jpg'),
                                            ('challenges', 'b-challenges', '15h-challenges-empty.jpg'))))
    for board, hash_, subs in steps:
        ef = sfx.SahaTilesPlatform(empty=True)
        page = sopen(browser, h, ef, vp, mobile, hash_)
        if board == 'saha':
            mshot(page, pre + '15-hub-empty.jpg')
        else:
            mshot(page, pre + '15a-diwan-hub-empty.jpg')
        for sub, _, shot_name in subs:
            go_sub(page, sub)
            page.wait_for_timeout(300)
            expect(page.evaluate("() => !!document.querySelector('.v2s-sh .sh-empty')"), '%s15: %s فاضية بلا رسالة «لا … بعد»' % (pre, sub))
            expect(page.evaluate("() => !document.querySelector('.v2s-sh .sh-warn')"), '%s15: %s فاضية لكن ظهر «غير متاح بعد» (المصدر سليم)' % (pre, sub))
            mshot(page, pre + shot_name)
            back_hub(page)
        browser.close()


def flow_closed(browser, h, pre, vp, mobile):
    if not want('16'):
        return
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = sfx.SahaTilesPlatform()
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#market', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.market === 'ready' && document.getElementById('view')", timeout=30000)
        st = page.evaluate("() => ({new: !!document.querySelector('.v2s-sh'), on: !!window.V2_ON})")
        expect(not st['new'] and not st['on'], '%s16: المفتاح مقفول وفيه أثر %r' % (pre, st))
        before = len(h.platform_calls)
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/saha/news', '/api/v2/saha/opportunities', '/api/v2/saha/settings', '/api/v2/saha/reminders', '/api/v2/diwan/works', '/api/v2/diwan/challenges', '/api/v2/diwan/report']) {
            const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        expect(not bad, '%s16: مسارات الساحة والديوان والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
        expect(len([c for c in h.platform_calls[before:] if '/news' in c[1] or '/jobs' in c[1] or '/creative' in c[1] or '/diwan' in c[1]]) == 0, '%s16: نداء للمنصة والمفتاح مقفول' % pre)
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(sfx.SahaTilesPlatform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', DESK, False), ('m', MOB, True)):
                if pre not in os.environ.get('SAHA_VP', 'dm'):
                    continue
                flow_saha(browser, h, pre, vp, mobile)
                flow_diwan(browser, h, pre, vp, mobile)
                flow_down(browser, h, pre, vp, mobile)
                flow_empty(browser, h, pre, vp, mobile)
                flow_closed(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
