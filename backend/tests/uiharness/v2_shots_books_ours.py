# -*- coding: utf-8 -*-
"""لقطات وفحوص تبويب «كتبنا» (قسم «الكتب»، docs/v2/books-ours/SPEC.md §ج) — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٣٩٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_books_ours.py ../docs/v2/books-ours/shots [only-prefix,...]

الخطوات: القائمة · «كتاب جديد» (النوع فيه «أخرى») · صفحة الكتاب بالخطوات الثلاث · رفع PDF (غير PDF مرفوض، ولا كتابة قبل «ارفع الملف») ·
ورقة الأسعار الموجودة تُفتح من الصفحة · «اعرضه في المتجر» و«اسحبه» بتأكيد جوه الصفحة · كتابة العقل (المسودة تظهر بفصولها وتتعدّل ثم «اعمل ملف PDF وارفعه») ·
الكتابة بالتسليم للخيط الخلفي (حالة «يكتب الآن» ثم المسودة) · أكواد الأدلّة (إضافة · حذف · كود غلط · حفظ بتأكيد).

السكربت بيفشل (exit 1) لو: «0/null/NaN/undefined» ظاهر · هدف أقل من ٤٤px · تمرير أفقي · رقم لاتيني ظاهر · كلمة ممنوعة (يقوّم · API · …) ·
نافذة متصفح (`alert`/`confirm`/`prompt`) · كتابة وصلت المنصة قبل ضغطة التأكيد أو غير المسارات المسموحة أو بلا `confirmed:true` ·
سعر في أي كتابة من مسارات كتبنا · حفظ في المتصفح · أي طلب خرج من العملية غير خطوط جوجل.
⛔ صفر طلبات حقيقية وصفر نداء ذكاء: الداشبورد جوه العملية، والمنصة جدول في الذاكرة (`books_ours_fixtures.OursPlatform`)، و`ai_call` بديل، و`render_pdf` بديل لو weasyprint غير موجودة.
"""
import json
import os
import re
import sys
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                         # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import books_ours_fixtures as bof             # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

PROBLEMS = vs.PROBLEMS
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
READY = "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-ours[data-board]') && !/…جارٍ جلب/.test(document.querySelector('.v2s-ours').innerText)"
PDF = b'%PDF-1.4\n%shots\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
OK_WRITES = [('POST', re.compile(r'^/api/bridge/books/ours$')), ('PUT', re.compile(r'^/api/bridge/books/ours/[^/]+$')),
             ('POST', re.compile(r'^/api/bridge/books/ours/[^/]+/file$')), ('PUT', re.compile(r'^/api/bridge/books/ours/[^/]+/status$')),
             ('PUT', re.compile(r'^/api/bridge/guides/codes$')), ('PUT', re.compile(r'^/api/bridge/prices/book/[^/]+$'))]
BANNED = ('يقوّم', 'يقوم', 'API', 'JSON', 'weasyprint', 'Claude', 'DeepSeek', 'Anthropic', 'endpoint', 'token')
GOOD = {'title': 'دليل البداية في عقود الإيجار',
        'about': 'دليل مبسّط يشرح خطوات كتابة عقد الإيجار وما يجب الانتباه إليه.',
        'chapters': [{'title': 'لماذا نكتب العقد', 'body': 'العقد المكتوب يحفظ حق الطرفين ويمنع الخلاف قبل أن يبدأ.\n\nيبدأ الاتفاق بفهم ما يريده كل طرف، ثم يُكتب بلغة واضحة. وتنص المادة ٥٦٣ من القانون المدني على ذلك.'},
                     {'title': 'بنود لا تُنسى', 'body': 'مدة الإيجار وقيمته وموعد الدفع وطريقة التسليم عند انتهاء المدة.'},
                     {'title': 'حقوق الطرفين', 'body': 'لكل طرف حقوق وواجبات تُكتب في العقد بوضوح، حتى لا يختلف الفهم لاحقًا. وقد صدر القانون سنة ٢٠٠٣ ويُعرف باسم Labor Law.'}]}


def want(code):
    return not ONLY or any(code.startswith(o) for o in ONLY)


def oc_check(page, name):
    """أهداف ≥ ٤٤px · لا تمرير أفقي · لا «٠/null/NaN» ولا أرقام لاتينية · كلمات ممنوعة · لا حفظ في المتصفح · لا نافذة متصفح."""
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v2s-ours button, .v2s-ours input:not([type=checkbox]):not([type=file]), .v2s-ours textarea, .v2s-ours select, .v2s-ours label.ou-lab, #epModal .v2s-bm button, #epModal .v2s-bm input:not([type=checkbox]), #epModal .v2s-bm textarea, #epModal .v2s-bm select')]
      .filter(b => b.offsetParent && !b.closest('[hidden]')).map(b => [(b.className || b.id || b.tagName).toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    boxes = page.evaluate("""() => [...document.querySelectorAll('.v2s-ours input[type=text], .v2s-ours textarea, #epModal .v2s-bm input[type=text], #epModal .v2s-bm textarea')]
      .filter(b => b.offsetParent).map(b => [b.id || b.className, parseFloat(getComputedStyle(b).fontSize)])""")
    for ident, fs in boxes:
        if fs < 16:
            PROBLEMS.append('%s: خانة %s خطها %s أقل من ١٦' % (name, ident, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    wide = page.evaluate("() => [...document.querySelectorAll('.v2s-ours *, #epModal .v2s-bm *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed').length")
    if wide:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    inner = page.evaluate("""() => [...document.querySelectorAll('.v2s-ours *')].filter(e => e.offsetParent && !['INPUT','TEXTAREA','SELECT'].includes(e.tagName)
      && e.scrollWidth > e.clientWidth + 1 && !['hidden','clip','auto','scroll'].includes(getComputedStyle(e).overflowX) && getComputedStyle(e).display !== 'inline').map(e => e.className.toString().slice(0, 40)).slice(0, 5)""")
    if inner:
        PROBLEMS.append('%s: تمرير أفقي جوه عناصر: %r' % (name, inner))
    txt = page.evaluate("""() => [...document.querySelectorAll('.v2s-ours, #epModal .v2s-bm')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('[dir="ltr"], [dir="auto"], script, style').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر' % name)
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    for word in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    keys = page.evaluate("() => { try { return Object.keys(localStorage).filter(k => /books|ours/i.test(k)); } catch (e) { return []; } }")
    if keys:
        PROBLEMS.append('%s: حفظ في المتصفح %r' % (name, keys))


def oshot(page, name, keep=True, target=None):
    if target:
        page.evaluate("sel => { const e = document.querySelector(sel); if (e) e.scrollIntoView({block: 'start'}); }", target)
    else:
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    page.wait_for_timeout(300)
    if keep:
        vs.shot(page, name, full=False)
    vs.shell_check(page, name)
    oc_check(page, name)


def writes(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE')]


def check_writes(name, h, since, expected, price_ok=False):
    got = writes(h, since)
    for m, p, _q, body in got:
        if not any(m == am and rx.match(p) for am, rx in OK_WRITES):
            PROBLEMS.append('%s: كتابة غير مسموحة %s %s' % (name, m, p))
        if not isinstance(body, dict) or body.get('confirmed') is not True:
            PROBLEMS.append('%s: كتابة بلا confirmed:true %s %s' % (name, m, p))
        if '/prices/' in p and not price_ok:
            PROBLEMS.append('%s: سعر خرج من كتبنا %s' % (name, p))
        if '/prices/' not in p and isinstance(body, dict) and any(k.startswith('price') or k in ('versions', 'visible', 'pricing') for k in body):
            PROBLEMS.append('%s: سعر داخل كتابة كتبنا %s' % (name, p))
    if len(got) != expected:
        PROBLEMS.append('%s: عدد الكتابات %d بدل %d: %r' % (name, len(got), expected, [(m, p) for m, p, _q, _b in got]))
    return got


def wait_ours(page, extra=''):
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(350)


def oopen(browser, h, ef, viewport, mobile, hash_='#s/books/ours'):
    h.ef = ef
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح ظهرت: %s' % d.message[:60]), d.dismiss()))
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.on('console', lambda m: PROBLEMS.append('console.error: %s' % m.text[:200]) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    wait_ours(page)
    return page


def click(page, sel, wait=300):
    page.click(sel)
    page.wait_for_timeout(wait)


def open_book(page, slug):
    click(page, '[data-a="open"][data-slug="%s"]' % slug, 500)
    page.wait_for_function("() => document.querySelector('[data-board=\"ours-book\"] .ou-steps')", timeout=15000)
    page.wait_for_timeout(500)


def primary_count(page):
    return page.evaluate("() => document.querySelectorAll('.v2s-ours .ep-b1').length")


def install_stubs(h):
    """⛔ لا ذكاء حقيقي ولا weasyprint: الكاتب بديل في الذاكرة، والـPDF بديل لو المكتبة غير موجودة."""
    app = h.app
    stub = {'calls': []}

    def ai_call(system, user, purpose='ai'):
        stub['calls'].append({'purpose': purpose, 'user': user})
        return json.dumps(GOOD, ensure_ascii=False)
    app.ai_call = ai_call
    app.ai_writer_state = lambda: {'writer': 'main', 'label': None, 'source': 'db'}
    app.ai_daily_usage_state = lambda: {'remaining': 100}
    app.app.config['BRAIN_INLINE'] = True
    import v2_books_ours_routes as m
    try:
        import weasyprint   # noqa: F401
    except Exception:       # noqa: BLE001
        m.render_pdf = lambda draft, fonts_dir=None: PDF
    return stub


def reset_drafts(h):
    """مسودات الجولة السابقة (الكمبيوتر) ما تبقاش في جولة الموبايل."""
    from sqlalchemy import text
    with h.app.app.app_context():
        try:
            h.app.db.session.execute(text('DELETE FROM v2_books_ours_drafts'))
            h.app.db.session.commit()
        except Exception:   # noqa: BLE001  (الجدول لسه ما اتعملش)
            h.app.db.session.rollback()


def flow_ours(browser, h, pre, viewport, mobile):
    stub = install_stubs(h)
    reset_drafts(h)

    # —— ١) القائمة
    if want('01'):
        page = oopen(browser, h, bof.OursPlatform(), viewport, mobile)
        n = page.evaluate("""() => ({cards: document.querySelectorAll('.ou-card[data-slug]').length, guides: document.querySelectorAll('.ou-guides').length,
          newb: document.querySelectorAll('[data-a="new"]').length, prim: document.querySelectorAll('.ep-b1').length, tab: (document.querySelector('.v2c-tab.on') || {}).textContent,
          live: [...document.querySelectorAll('.ou-card .bk-st')].map(e => e.textContent.trim())})""")
        if n['cards'] != 4 or n['guides'] != 1 or n['newb'] != 1 or n['prim'] != 1 or n['tab'].strip() != 'كتبنا' or n['live'].count('في المتجر') != 1 or n['live'].count('مسودة') != 3:
            PROBLEMS.append('%s01: القائمة %r' % (pre, n))
        oshot(page, pre + '01-list.jpg')
        browser.close()

    # —— ٢) كتاب جديد
    if want('02'):
        page = oopen(browser, h, bof.OursPlatform(), viewport, mobile)
        base = len(h.platform_calls)
        click(page, '[data-a="new"]', 500)
        opts = page.evaluate("() => [...document.querySelectorAll('#ou_ty option')].map(o => o.textContent.trim())")
        if opts != ['كتاب', 'دليل', 'بحث', 'أخرى']:
            PROBLEMS.append('%s02: أنواع الكتاب %r' % (pre, opts))
        page.fill('#ou_t', 'دليل الشركات العائلية')
        page.fill('#ou_a', 'خطوات عملية لتنظيم الملكية والقرار داخل شركة عائلية.')
        page.select_option('#ou_ty', 'guide')
        oshot(page, pre + '02-new-book.jpg')
        page.fill('#ou_t', '')
        click(page, '#bk_go', 200)
        if 'اكتب عنوان' not in page.inner_text('#bkerr'):
            PROBLEMS.append('%s02: العنوان الفاضي ما اتمنعش' % pre)
        check_writes(pre + '02-empty', h, base, 0)
        page.fill('#ou_t', 'دليل الشركات العائلية')
        click(page, '#bk_go', 900)
        got = check_writes(pre + '02', h, base, 1)
        if got and (got[0][3].get('type') != 'guide' or not got[0][3].get('by') or not got[0][3].get('idem_key') or got[0][3].get('title') != 'دليل الشركات العائلية'):
            PROBLEMS.append('%s02: جسم الإنشاء %r' % (pre, got[0][3]))
        page.wait_for_function("() => document.querySelector('[data-board=\"ours-book\"]')", timeout=15000)
        if 'دليل الشركات العائلية' not in page.inner_text('#view'):
            PROBLEMS.append('%s02: الكتاب الجديد ما فتحش' % pre)
        oshot(page, pre + '02b-new-opened.jpg', keep=False)
        browser.close()

    # —— ٣) صفحة الكتاب بالخطوات + رفع PDF
    if want('03'):
        page = oopen(browser, h, bof.OursPlatform(), viewport, mobile)
        open_book(page, 'ours-startup-law')
        steps = page.evaluate("() => [...document.querySelectorAll('.ou-step')].map(s => [s.dataset.step, s.classList.contains('done'), (s.querySelector('.ou-flag') || {}).textContent])")
        if steps != [['content', True, 'تم'], ['price', False, 'لم يتم بعد'], ['store', False, 'غير معروض']]:
            PROBLEMS.append('%s03: الخطوات %r' % (pre, steps))
        if primary_count(page) != 1 or not page.evaluate("() => document.querySelector('.ou-step[data-step=price] .ep-b1')"):
            PROBLEMS.append('%s03: الزر الأساسي لازم يكون «حدّد السعر» وحده' % pre)
        oshot(page, pre + '03-book-steps.jpg')
        base = len(h.platform_calls)
        # ملف غير PDF ⇒ رفض في الصفحة بلا نداء
        page.set_input_files('#ou_file', {'name': 'notes.txt', 'mimeType': 'text/plain', 'buffer': b'hello'})
        page.wait_for_timeout(400)
        if 'اختر ملف PDF فقط' not in page.inner_text('.ou-step[data-step=content]'):
            PROBLEMS.append('%s03: غير PDF ما اترفضش' % pre)
        check_writes(pre + '03-nonpdf', h, base, 0)
        # PDF ⇒ لوحة التأكيد، وولا كتابة قبل الضغطة
        page.set_input_files('#ou_file', {'name': 'startup-law-v2.pdf', 'mimeType': 'application/pdf', 'buffer': PDF})
        page.wait_for_timeout(400)
        box = page.inner_text('.ou-confirm')
        if 'يحلّ محلّ الملف الحالي' not in box or 'startup-law-v2.pdf' not in page.inner_text('.ou-step[data-step=content]'):
            PROBLEMS.append('%s03: لوحة تأكيد الرفع %r' % (pre, box))
        check_writes(pre + '03-before-confirm', h, base, 0)
        oshot(page, pre + '03b-upload-confirm.jpg', keep=False, target='.ou-step[data-step=content]')
        click(page, '[data-a="cno"]', 300)
        check_writes(pre + '03-cancel', h, base, 0)
        page.set_input_files('#ou_file', {'name': 'startup-law-v2.pdf', 'mimeType': 'application/pdf', 'buffer': PDF})
        page.wait_for_timeout(300)
        click(page, '[data-a="cgo"]', 900)
        got = check_writes(pre + '03-upload', h, base, 1)
        if got and (not got[0][1].endswith('/ours-startup-law/file') or got[0][3].get('__file__', {}).get('name') != 'startup-law-v2.pdf' or not got[0][3].get('by')):
            PROBLEMS.append('%s03: جسم الرفع %r' % (pre, got[0][3]))
        if 'startup-law-v2.pdf' not in page.inner_text('.ou-step[data-step=content]'):
            PROBLEMS.append('%s03: الملف الجديد ما ظهرش بعد الرفع' % pre)
        # ورقة الأسعار الموجودة تُفتح من الصفحة
        click(page, '[data-a="price"]', 900)
        sheet = page.evaluate("() => (document.querySelector('#epModal .mh span') || {}).textContent")
        if not sheet or 'أسعار' not in sheet:
            PROBLEMS.append('%s03: ورقة الأسعار ما فتحتش (%r)' % (pre, sheet))
        else:
            oshot(page, pre + '03c-price-sheet.jpg', keep=False)
            page.click('#epModal [data-x]')
            page.wait_for_timeout(300)
        check_writes(pre + '03-price-open', h, base, 1)
        browser.close()

    # —— ٤) المتجر: اعرض واسحب بتأكيد · بلا ملف ⇒ لا زرّ · ٤٠٩ كما رجع
    if want('04'):
        ef = bof.OursPlatform()
        page = oopen(browser, h, ef, viewport, mobile)
        open_book(page, 'ours-arbitration')
        if page.evaluate("() => !!document.querySelector('[data-a=\"golive\"]')") or 'ارفع ملف PDF أولًا' not in page.inner_text('.ou-step[data-step=store]'):
            PROBLEMS.append('%s04: كتاب بلا ملف ظهر له زرّ العرض' % pre)
        click(page, '[data-a="back"]', 400)
        open_book(page, 'ours-startup-law')
        base = len(h.platform_calls)
        click(page, '[data-a="golive"]', 300)
        txt = page.inner_text('.ou-step[data-step=store] .ou-confirm')
        if 'سيظهر' not in txt or page.evaluate("() => !!document.querySelector('[data-a=\"golive\"]')"):
            PROBLEMS.append('%s04: لوحة تأكيد العرض %r' % (pre, txt))
        check_writes(pre + '04-before', h, base, 0)
        oshot(page, pre + '04-store-confirm.jpg', keep=False, target='.ou-step[data-step=store]')
        # المنصة ترفض (٤٠٩) ⇒ النص يظهر كما هو
        ef.forced[('PUT', '/api/bridge/books/ours/ours-startup-law/status')] = (409, {'detail': 'ارفع ملف الـPDF الأول'})
        click(page, '[data-a="cgo"]', 800)
        if 'ارفع ملف الـPDF الأول' not in page.inner_text('.ou-step[data-step=store]'):
            PROBLEMS.append('%s04: رد المنصة ٤٠٩ ما ظهرش' % pre)
        del ef.forced[('PUT', '/api/bridge/books/ours/ours-startup-law/status')]
        click(page, '[data-a="golive"]', 300)
        click(page, '[data-a="cgo"]', 900)
        got = check_writes(pre + '04-live', h, base, 2)
        if not page.evaluate("() => document.querySelector('.ou-step[data-step=store]').classList.contains('done')") or 'في المتجر' not in page.inner_text('.ou-bhead'):
            PROBLEMS.append('%s04: الكتاب ما بقاش في المتجر' % pre)
        click(page, '[data-a="pause"]', 300)
        if 'سيختفي' not in page.inner_text('.ou-confirm'):
            PROBLEMS.append('%s04: لوحة تأكيد السحب' % pre)
        click(page, '[data-a="cgo"]', 900)
        check_writes(pre + '04-pause', h, base, 3)
        if page.evaluate("() => document.querySelector('.ou-step[data-step=store]').classList.contains('done')"):
            PROBLEMS.append('%s04: السحب ما اتنفّذش' % pre)
        # الرد الضايع ⇒ «لم يصل رد»
        ef.forced[('PUT', '/api/bridge/books/ours/ours-startup-law/status')] = (504, {'detail': 'x'})
        click(page, '[data-a="golive"]', 300)
        click(page, '[data-a="cgo"]', 900)
        if 'لم يصل رد' not in page.inner_text('.ou-step[data-step=store]'):
            PROBLEMS.append('%s04: رد ضايع ما ظهرش «لم يصل رد»' % pre)
        oshot(page, pre + '04b-no-reply.jpg', keep=False, target='.ou-step[data-step=store]')
        browser.close()

    # —— ٥) العقل يكتب: مسودة ⇒ تعديل ⇒ PDF ⇒ رفع
    if want('05'):
        page = oopen(browser, h, bof.OursPlatform(), viewport, mobile)
        open_book(page, 'ours-arbitration')
        base = len(h.platform_calls)
        click(page, '[data-a="write"]', 400)
        click(page, '[data-a="draft"]', 300)
        if 'اكتب ما تريده' not in page.inner_text('#ou-writer'):
            PROBLEMS.append('%s05: تعليمات فاضية ما اتمنعتش' % pre)
        page.fill('#ou_ins', 'اكتب دليلًا مبسّطًا لعقود الإيجار للمستأجرين الجدد')
        page.fill('#ou_out', 'لماذا نكتب العقد\nبنود لا تُنسى')
        oshot(page, pre + '05a-writer.jpg', keep=False, target='#ou-writer')
        n0 = len(stub['calls'])
        click(page, '[data-a="draft"]', 1200)
        if len(stub['calls']) != n0 + 1:
            PROBLEMS.append('%s05: نداءات الكاتب %d' % (pre, len(stub['calls']) - n0))
        check_writes(pre + '05-draft', h, base, 0)             # ⛔ مفيش كتابة على المنصة من المسودة
        chs = page.evaluate("() => document.querySelectorAll('.ou-ch').length")
        if chs != 3 or page.input_value('#ou_dt') != GOOD['title']:
            PROBLEMS.append('%s05: المسودة ما ظهرتش بفصولها (%s)' % (pre, chs))
        mk = page.evaluate("""() => ({marks: [...document.querySelectorAll('.ou-hl-back mark')].map(m => m.textContent), note: (document.getElementById('ou-review') || {}).hidden === false ? document.getElementById('ou-review').textContent : null,
          color: getComputedStyle(document.querySelector('.ou-hl-back mark')).borderBottomColor})""")
        if sorted(set(mk['marks'])) != sorted(['٥٦٣', '٢٠٠٣', 'Labor', 'Law']) or mk['note'] != 'راجع هذه الأرقام والأسماء قبل العرض' or 'rgba(158, 43, 78' not in mk['color']:
            PROBLEMS.append('%s05: علامات المراجعة %r' % (pre, mk))
        oshot(page, pre + '05-brain-draft.jpg', target='.ou-review')
        # تعديل ثم حفظ (محلي) ثم PDF بتأكيد
        page.fill('#ou_ct1', 'بنود يجب ألا تُنسى')
        click(page, '[data-a="savedraft"]', 700)
        check_writes(pre + '05-save', h, base, 0)
        saved = page.evaluate("async () => { const t = localStorage.getItem('token'); const r = await fetch('/api/v2/books/ours/ours-arbitration/brain/draft', {headers: {Authorization: 'Bearer ' + t}}); return (await r.json()).draft.chapters[1].title; }")
        if saved != 'بنود يجب ألا تُنسى':
            PROBLEMS.append('%s05: التعديل ما اتحفظش (%r)' % (pre, saved))
        click(page, '[data-a="chadd"]', 300)
        page.fill('#ou_ct3', 'خاتمة')
        click(page, '[data-a="mkpdf"]', 300)
        if 'ناقص' not in page.inner_text('.ou-draft'):
            PROBLEMS.append('%s05: فصل ناقص ما اتمنعش' % pre)
        click(page, '[data-a="chdel"][data-i="3"]', 300)
        click(page, '[data-a="mkpdf"]', 600)
        if 'سيُنشأ ملف PDF' not in page.inner_text('.ou-draft .ou-confirm') or '٤ مواضع تحتاج مراجعة' not in page.inner_text('.ou-draft .ou-confirm'):
            PROBLEMS.append('%s05: لوحة تأكيد الـPDF' % pre)
        check_writes(pre + '05-before-pdf', h, base, 0)
        oshot(page, pre + '05b-pdf-confirm.jpg', keep=False, target='.ou-draft .ou-confirm')
        click(page, '.ou-draft [data-a="cgo"]', 1500)
        got = check_writes(pre + '05-pdf', h, base, 1)
        if got and (not got[0][1].endswith('/ours-arbitration/file') or not str(got[0][3].get('__file__', {}).get('head', '')).startswith('%PDF-')):
            PROBLEMS.append('%s05: رفع الـPDF %r' % (pre, got[0][3]))
        if not page.evaluate("() => document.querySelector('.ou-step[data-step=content]').classList.contains('done')"):
            PROBLEMS.append('%s05: الخطوة الأولى ما بقتش «تم» بعد الـPDF' % pre)
        browser.close()

    # —— ٦) الكتابة بالتسليم للخيط الخلفي: «يكتب الآن» ثم المسودة بالاستعلام
    if want('06'):
        from brain2 import engine
        page = oopen(browser, h, bof.OursPlatform(), viewport, mobile)
        open_book(page, 'ours-rent-notes')
        click(page, '[data-a="write"]', 300)
        page.fill('#ou_ins', 'اكتب دليلًا قصيرًا')
        real = engine.submit
        h.app.app.config['BRAIN_INLINE'] = False

        def slow_submit(ns, key, fn):
            def run():
                time.sleep(2.2)
                with h.app.app.app_context():
                    fn()
            threading.Thread(target=run, daemon=True).start()
            return {'queued': True}
        engine.submit = slow_submit
        try:
            click(page, '[data-a="draft"]', 900)
            if 'العقل يكتب' not in page.inner_text('#ou-writer') or not page.evaluate("() => document.querySelector('[data-a=\"draft\"]').disabled"):
                PROBLEMS.append('%s06: حالة «يكتب الآن» ما ظهرتش' % pre)
            oshot(page, pre + '06-writing.jpg', keep=False, target='#ou-writer')
            page.wait_for_function("() => document.querySelectorAll('.ou-ch').length === 3", timeout=20000)
        finally:
            engine.submit = real
            h.app.app.config['BRAIN_INLINE'] = True
        browser.close()

    # —— ٧) أكواد الأدلّة
    if want('07'):
        ef = bof.OursPlatform()
        page = oopen(browser, h, ef, viewport, mobile)
        click(page, '[data-a="codes"]', 700)
        rows = page.evaluate("() => document.querySelectorAll('.ou-code').length")
        if rows != 3 or 'استُعمل' not in page.inner_text('.ou-codes'):
            PROBLEMS.append('%s07: جدول الأكواد (%s)' % (pre, rows))
        oshot(page, pre + '07-codes.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="codeadd"]', 300)
        page.fill('[data-f="code"][data-i="3"]', 'Bad Code!')
        click(page, '[data-a="codesave"]', 300)
        if 'الكود من' not in page.inner_text('.v2s-ours'):
            PROBLEMS.append('%s07: كود غلط ما اترفضش' % pre)
        page.fill('[data-f="code"][data-i="3"]', 'summer-27')
        page.fill('[data-f="note"][data-i="3"]', 'حملة الصيف')
        page.fill('[data-f="max"][data-i="3"]', '٢٥')
        click(page, '[data-a="coderm"][data-i="2"]', 300)
        click(page, '[data-a="codesave"]', 300)
        if 'ستُحفظ' not in page.inner_text('.ou-confirm'):
            PROBLEMS.append('%s07: لوحة تأكيد حفظ الأكواد' % pre)
        check_writes(pre + '07-before', h, base, 0)
        oshot(page, pre + '07b-codes-confirm.jpg', keep=False, target='.ou-confirm')
        click(page, '[data-a="cgo"]', 1000)
        got = check_writes(pre + '07-save', h, base, 1)
        if got:
            codes = got[0][3].get('codes')
            if [c['code'] for c in codes] != ['spring-26', 'partner-gift', 'summer-27'] or codes[2]['max_uses'] != 25 or got[0][3].get('by', '') == '':
                PROBLEMS.append('%s07: جسم حفظ الأكواد %r' % (pre, got[0][3]))
        if 'حُفظت الأكواد' not in page.inner_text('.v2s-ours'):
            PROBLEMS.append('%s07: رسالة الحفظ' % pre)
        browser.close()

    # —— ٨) فاضي ومصدر واقع
    if want('08'):
        page = oopen(browser, h, bof.OursPlatform(empty=True), viewport, mobile)
        if 'لا كتب بعد' not in page.inner_text('#view') or page.evaluate("() => document.querySelectorAll('.ou-guides').length") != 1:
            PROBLEMS.append('%s08: الفاضي' % pre)
        oshot(page, pre + '08-empty.jpg', keep=False)
        browser.close()
        ef = bof.OursPlatform()
        ef.down.add('/api/bridge/books/ours')
        page = oopen(browser, h, ef, viewport, mobile)
        t = page.inner_text('#view')
        if 'غير متاح بعد' not in t or 'لا كتب بعد' in t:
            PROBLEMS.append('%s08: المصدر الواقع لازم «غير متاح بعد» لا «لا كتب»: %r' % (pre, t[:80]))
        oshot(page, pre + '08b-down.jpg', keep=False)
        browser.close()

    # —— ٩) المفتاح مقفول ⇒ لا أثر
    if want('09'):
        os.environ.pop('DASH_V2_ENABLED', None)
        try:
            h.ef = bof.OursPlatform()
            ctx = browser.context(h, 'admin', viewport, mobile)
            page = ctx.new_page()
            page.goto(DASH + '/#knowledge', wait_until='domcontentloaded')
            page.wait_for_function("() => window.EP && EP.state.knowledge === 'ready' && document.getElementById('knRows')", timeout=30000)
            st = page.evaluate("() => ({new: !!document.querySelector('.v2s-ours'), on: !!window.V2_ON})")
            if st['new'] or st['on']:
                PROBLEMS.append('%s09: المفتاح مقفول وفيه أثر %r' % (pre, st))
            bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
              for (const p of ['/api/v2/books/ours', '/api/v2/books/guide-codes']) { const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
            if bad:
                PROBLEMS.append('%s09: مسارات كتبنا والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
        finally:
            os.environ['DASH_V2_ENABLED'] = 'true'
        browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(bof.OursPlatform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', vs.DESK, False), ('m', vs.MOB, True)):
                if pre not in os.environ.get('BO_VP', 'dm'):
                    continue
                flow_ours(browser, h, pre, vp, mobile)
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
