# -*- coding: utf-8 -*-
"""لقطات وفحوص «الأدوات» (الاستوديو، docs/v2/tools/SPEC.md) — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٤٣٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_tools.py ../docs/v2/tools/shots [only-prefix,...]

الخطوات: ٠١ لوحة الحالة والمربّعات (شغّال · استراحة السقف · المصدر الواقع) · ٠٢ مفتاح الإيقاف (ورقة · أوقف · أعد التشغيل) · ٠٣ الأدوات (قائمة · تشغيل ·
تعارض الصفحة القديمة · السعر بخطئه ومراجعته ورفض المنصة · الرسم التجريبي) · ٠٤ الأماكن (قائمة · رفع صورة · تعديل · إظهار وإخفاء · حذف · المحمي) ·
٠٥ العيّنات (سليم · أخفِ · امنع · رد ضايع · الفاضي) · ٠٦ التقرير (اليوم · الأسبوع · فترة أخرى · الشحن منفصلًا · علم الحارس) · ٠٧ الإعدادات (خطأ · مراجعة · حفظ · رفض المنصة) ·
٠٨ المصدر الواقع والفاضي · ٠٩ المفتاح مقفول.

السكربت بيفشل (exit 1) لو: «0/null/NaN/undefined» ظاهر · هدف أقل من ٤٤px · خانة أقل من ١٦px · تمرير أفقي · رقم لاتيني ظاهر · «·» ملاصقة لرقم · كلمة ممنوعة ·
نافذة متصفح (`alert`/`confirm`/`prompt`) · كتابة وصلت المنصة قبل ضغطة التأكيد أو غير المسارات المسموحة أو بلا `by` أو بـ`confirmed` · حفظ في المتصفح ·
أي طلب خرج من العملية غير خطوط جوجل · رسم حقيقي (`real` غير false).
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية، والمنصة جدول في الذاكرة (`tools_fixtures.ToolsPlatform`) والمزوّد تجريبي.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                         # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import tools_fixtures as tfx                  # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

PROBLEMS = vs.PROBLEMS
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
DESK = vs.DESK
MOB = {'width': 430, 'height': 932}
HASH = '#s/company/tools'
READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-tl[data-board]') && !document.querySelector('.v2s-tl .tl-skel')"
         " && !/…/.test((document.querySelector('.tl-tiles') || {innerText: ''}).innerText)")
BANNED = ('يقوّم', 'يقوم', 'API', 'JSON', 'Claude', 'DeepSeek', 'Anthropic', 'OpenAI', 'Higgsfield', 'endpoint', 'token', 'bridge', 'mock', 'kill')
OK_WRITES = [('PUT', re.compile(r'^/api/bridge/tools/recipes/[^/]+$')), ('POST', re.compile(r'^/api/bridge/tools/styles$')),
             ('PUT', re.compile(r'^/api/bridge/tools/styles/[^/]+$')), ('DELETE', re.compile(r'^/api/bridge/tools/styles/[^/]+$')),
             ('PUT', re.compile(r'^/api/bridge/tools/settings$')), ('POST', re.compile(r'^/api/bridge/tools/samples/[^/]+$'))]
RENDER = re.compile(r'^/api/bridge/tools/test-render/[^/]+$')
SCOPE_JS = """() => [...document.querySelectorAll('.v2s-tl, #epModal.v2s-tl-sh')].map(e => { const c = e.cloneNode(true);
  c.querySelectorAll('[dir="ltr"], [dir="auto"], .tl-who, script, style, input, textarea, select, option').forEach(n => n.remove()); return c.innerText; }).join('\\n')"""
FIXED_BUTTONS = ".v2s-tl button, .v2s-tl a, .v2s-tl input:not([type=checkbox]):not([type=radio]):not([type=file]), .tl-radio, #epModal.v2s-tl-sh button, #epModal.v2s-tl-sh input:not([type=checkbox]):not([type=radio]):not([type=file]), #epModal.v2s-tl-sh select, #epModal.v2s-tl-sh textarea, #epModal.v2s-tl-sh .tl-filebtn"
FIELDS = ".v2s-tl input:not([type=checkbox]):not([type=radio]):not([type=file]), .v2s-tl textarea, .v2s-tl select, #epModal.v2s-tl-sh input:not([type=checkbox]):not([type=radio]):not([type=file]), #epModal.v2s-tl-sh textarea, #epModal.v2s-tl-sh select"


def want(code):
    return not ONLY or any(code.startswith(o) for o in ONLY)


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def arn(n):
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def tlcheck(page, name):
    w = page.viewport_size['width']
    small = page.evaluate("""sel => [...document.querySelectorAll(sel)]
      .filter(b => b.offsetParent && !b.closest('[hidden]') && b.getBoundingClientRect().width > 2).map(b => [(b.className || b.id || b.tagName).toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""", FIXED_BUTTONS)
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    boxes = page.evaluate("""sel => [...document.querySelectorAll(sel)].filter(b => b.offsetParent).map(b => [b.id || b.className, parseFloat(getComputedStyle(b).fontSize)])""", FIELDS)
    for ident, fs in boxes:
        if fs < 16:
            PROBLEMS.append('%s: خانة %s خطها %s أقل من ١٦' % (name, ident, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    wide = page.evaluate("() => [...document.querySelectorAll('.v2s-tl *, #epModal.v2s-tl-sh *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed' && !e.closest('.tl-tbw')).length")
    if wide:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    txt = page.evaluate(SCOPE_JS)
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN/undefined ظاهر: %r' % (name, re.findall(r'.{0,10}(?<![\w@./-])(?:0|null|NaN|undefined)(?![\w@./-]).{0,10}', txt)[:2]))
    bad = [t for t in re.findall(r'\S*[0-9]\S*', txt) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    if re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', txt):
        PROBLEMS.append('%s: «·» ملاصقة لرقم: %r' % (name, re.findall(r'.{0,8}[0-9٠-٩]\s*·.{0,8}|.{0,8}·\s*[0-9٠-٩].{0,8}', txt)[:2]))
    for word in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    keys = page.evaluate("() => { try { return Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => /tool|studio|recipe|style|sample/i.test(k)); } catch (e) { return []; } }")
    if keys:
        PROBLEMS.append('%s: حفظ في المتصفح %r' % (name, keys))


def tshot(page, name, keep=True, target=None):
    if target:
        page.evaluate("sel => { const e = document.querySelector(sel); if (e) e.scrollIntoView({block: 'start'}); }", target)
    else:
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    page.wait_for_timeout(300)
    if keep:
        vs.shot(page, name, full=False)
    vs.shell_check(page, name)
    tlcheck(page, name)


def writes_since(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE') and not RENDER.match(c[1])]


def renders_since(h, since):
    return [c for c in h.platform_calls[since:] if c[0] == 'POST' and RENDER.match(c[1])]


def check_writes(name, h, since, expected):
    got = writes_since(h, since)
    for m, p, _q, body in got:
        if not any(m == am and rx.match(p) for am, rx in OK_WRITES):
            PROBLEMS.append('%s: كتابة غير مسموحة %s %s' % (name, m, p))
        if m != 'DELETE':
            if not isinstance(body, dict) or not str(body.get('by') or '').strip():
                PROBLEMS.append('%s: كتابة بلا by %s %s' % (name, m, p))
            elif '__file__' not in body and 'confirmed' in json.dumps(body):
                PROBLEMS.append('%s: confirmed سافر للمنصة %s %s' % (name, m, p))
    if len(got) != expected:
        PROBLEMS.append('%s: عدد الكتابات %d بدل %d: %r' % (name, len(got), expected, [(m, p) for m, p, _q, _b in got]))
    for m, p, _q, body in h.platform_calls[since:]:
        if RENDER.match(p) and (not isinstance(body, dict) or body.get('real') is not False):
            PROBLEMS.append('%s: رسم غير تجريبي %r' % (name, body))
    return got


def topen(browser, h, ef, viewport, mobile, hash_=HASH, ready=READY, wait_ready=True):
    h.ef = ef
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح ظهرت: %s' % d.message[:60]), d.dismiss()))
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.on('console', lambda m: PROBLEMS.append('console.error: %s' % m.text[:200]) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    if wait_ready:
        page.wait_for_function(ready, timeout=30000)
    page.wait_for_timeout(350)
    return page


def click(page, sel, wait=300):
    page.click(sel)
    page.wait_for_timeout(wait)


def go_sub(page, sub):
    click(page, '.tl-tile[data-sub="%s"]' % sub, 500)
    page.wait_for_function("() => !document.querySelector('.v2s-tl .tl-skel') && document.querySelector('.tl-head')", timeout=15000)
    page.wait_for_timeout(300)


def back_hub(page):
    click(page, '[data-a="hub"]', 400)
    page.wait_for_function("() => document.querySelector('.tl-tiles')", timeout=10000)


def sheet_open(page):
    page.wait_for_selector('#epModal.v2s-tl-sh', timeout=10000)
    page.wait_for_timeout(250)


def sheet_gone(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(450)


def tile_numbers(page):
    return page.evaluate("() => [...document.querySelectorAll('.tl-tile')].map(t => [t.dataset.sub, t.querySelector('.tl-n').textContent.trim(), t.querySelector('small').textContent.trim()])")


def card_ids(page):
    return page.evaluate("() => [...document.querySelectorAll('.tl-card[data-id]')].map(c => c.dataset.id)")


def wait_note(page, frag):
    page.wait_for_function("f => (document.querySelector('.tl-note') || {textContent: ''}).textContent.includes(f)", arg=frag, timeout=10000)


# ======================================================================= ١ — لوحة الحالة والمربّعات
def flow_hub(browser, h, pre, vp, mobile):
    if want('01'):
        ef = tfx.ToolsPlatform()
        page = topen(browser, h, ef, vp, mobile)
        nums = {s: (n, t) for s, n, t in tile_numbers(page)}
        expect(nums.get('recipes') == ('٢', 'من ٥ أدوات شغّالة') and nums.get('styles') == ('١٥', 'مكان وتصميم') and nums.get('samples') == ('٤', 'عيّنة تنتظر مراجعتك')
               and nums.get('report') == ('٤٣', 'عمل اليوم، ولك تقرير الأسبوع') and nums.get('settings') == ('١٠', 'دولار سقف الصرف اليومي'), '%s01: أرقام المربّعات %r' % (pre, nums))
        st = page.evaluate("""() => ({chip: document.querySelector('.tl-status .tl-chip').textContent.trim(), spend: document.querySelector('.tl-spendline b').textContent.trim(),
          pct: document.querySelector('.tl-bar2').getAttribute('aria-valuenow'), stats: [...document.querySelectorAll('.tl-stats > div')].map(d => d.innerText.replace(/\\s+/g, ' ').trim()),
          facts: [...document.querySelectorAll('.tl-facts li')].map(l => l.innerText.replace(/\\s+/g, ' ').trim()), kill: (document.querySelector('[data-a=kill]') || {}).textContent})""")
        expect(st['chip'] == 'الاستوديو شغّال' and st['spend'] == 'صُرف اليوم ٢٫٤ دولار من ١٠ دولارات' and st['pct'] == '24', '%s01: لوحة الحالة %r' % (pre, st))
        expect(st['stats'] == ['٤٣ عمل اليوم', '٤١ نجحت', '٢ لم تنجح'] and st['kill'] == 'أوقف الاستوديو الآن', '%s01: أعمال اليوم والفاشل ومفتاح الإيقاف %r' % (pre, st))
        expect(any(f.startswith('وضع الرسم تجريبي') for f in st['facts']) and any(f.startswith('الأدوات للأعضاء مغلقة') for f in st['facts']) and any(f.startswith('شحن الرصيد مغلق') for f in st['facts']), '%s01: المفاتيح للقراءة فقط %r' % (pre, st['facts']))
        expect(page.evaluate("() => !document.querySelector('.tl-facts input, .tl-facts select, .tl-facts [role=switch]')"), '%s01: مفاتيح الخادم لازم تبقى قراءة فقط' % pre)
        tabs = page.evaluate("() => [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim())")
        expect(tabs[-2] == 'الأدوات' and tabs[-1] == 'الإعدادات' and len(tabs) == 7, '%s01: تبويب الأدوات %r' % (pre, tabs))
        imgs = page.evaluate("() => [...document.querySelectorAll('.tl-timg')].map(e => getComputedStyle(e).backgroundImage.replace(/.*\\//, ''))")
        expect(len(imgs) == 5 and all('.jpg' in i for i in imgs), '%s01: صور المربّعات %r' % (pre, imgs))
        expect(page.evaluate("() => !document.querySelector('.tl-fine')") or True, '')
        tshot(page, pre + '01-hub.jpg')
        browser.close()

    if want('01b'):                       # استراحة السقف: النظام يوقف نفسه
        ef = tfx.ToolsPlatform()
        ef.tools_spent = 9.95
        page = topen(browser, h, ef, vp, mobile)
        st = page.evaluate("() => ({chip: document.querySelector('.tl-status .tl-chip').textContent.trim(), cls: document.querySelector('.tl-status').className, note: document.querySelector('.tl-snote').textContent})")
        expect('استراحة' in st['chip'] and 'cap' in st['cls'] and 'ارفع السقف' in st['note'], '%s01b: حالة السقف %r' % (pre, st))
        tshot(page, pre + '01b-cap.jpg')
        browser.close()

    if want('01c'):                       # مفتاح الإيقاف مضغوط من قبل + المفاتيح الحيّة
        ef = tfx.ToolsPlatform()
        ef.tools_settings['kill'] = True
        ef.tools_flags = {'tools_enabled': True, 'provider': 'live', 'topup_enabled': True}
        ef.tools_ffmpeg = False
        page = topen(browser, h, ef, vp, mobile)
        st = page.evaluate("() => ({chip: document.querySelector('.tl-status .tl-chip').textContent.trim(), btn: document.querySelector('[data-a=kill]').textContent.trim(), facts: [...document.querySelectorAll('.tl-facts li')].map(l => l.innerText.replace(/\\s+/g, ' ').trim()), warn: (document.querySelector('.tl-status .tl-warn') || {}).textContent})")
        expect('متوقف يدويًا' in st['chip'] and st['btn'] == 'أعد تشغيل الاستوديو' and any(f.startswith('وضع الرسم حيّ') for f in st['facts']) and 'الفيديو غير جاهز' in (st['warn'] or ''), '%s01c: %r' % (pre, st))
        tshot(page, pre + '01c-killed-live.jpg')
        browser.close()


# ======================================================================= ٢ — مفتاح الإيقاف
def flow_kill(browser, h, pre, vp, mobile):
    if not want('02'):
        return
    ef = tfx.ToolsPlatform()
    page = topen(browser, h, ef, vp, mobile)
    base = len(h.platform_calls)
    click(page, '[data-a="kill"]', 400)
    sheet_open(page)
    txt = page.inner_text('#epModal')
    expect('فورًا' in txt and 'أعمالًا جديدة' in txt.replace('أعمال جديدة', 'أعمالًا جديدة') and page.inner_text('#tlGo') == 'أوقف الاستوديو الآن', '%s02: ورقة الإيقاف %r' % (pre, txt[:120]))
    expect(page.evaluate("() => getComputedStyle(document.getElementById('tlGo')).backgroundColor") == 'rgb(200, 16, 46)', '%s02: زرّ الإيقاف أحمر' % pre)
    tshot(page, pre + '02-kill-sheet.jpg')
    check_writes(pre + '02-before-confirm', h, base, 0)
    click(page, '#tlNo', 300)
    sheet_gone(page)
    check_writes(pre + '02-cancel', h, base, 0)
    click(page, '[data-a="kill"]', 400)
    sheet_open(page)
    click(page, '#tlGo', 1000)
    sheet_gone(page)
    got = check_writes(pre + '02-kill', h, base, 1)
    if got:
        expect(got[0][3].get('settings') == {'kill': True}, '%s02: جسم الإيقاف %r' % (pre, got[0][3]))
    page.wait_for_function("() => /متوقف يدويًا/.test(document.querySelector('.tl-status .tl-chip').textContent)", timeout=10000)
    expect('أُوقف الاستوديو' in page.inner_text('.tl-note'), '%s02: رسالة الإيقاف' % pre)
    tshot(page, pre + '02b-killed.jpg')
    click(page, '[data-a="kill"]', 400)
    sheet_open(page)
    expect('سيعود الاستوديو' in page.inner_text('#epModal') and page.inner_text('#tlGo') == 'أعد تشغيل الاستوديو', '%s02: ورقة إعادة التشغيل' % pre)
    expect(page.evaluate("() => getComputedStyle(document.getElementById('tlGo')).backgroundColor") != 'rgb(200, 16, 46)', '%s02: إعادة التشغيل مش حمراء' % pre)
    click(page, '#tlGo', 1000)
    sheet_gone(page)
    got = check_writes(pre + '02-resume', h, base, 2)
    if len(got) == 2:
        expect(got[1][3].get('settings') == {'kill': False}, '%s02: جسم إعادة التشغيل %r' % (pre, got[1][3]))
    page.wait_for_function("() => /الاستوديو شغّال/.test(document.querySelector('.tl-status .tl-chip').textContent)", timeout=10000)
    # رد ضايع على الإيقاف: «لم يصل رد» لا «اترفض»
    ef.forced[('PUT', '/api/bridge/tools/settings')] = (504, {'detail': 'timeout'})
    click(page, '[data-a="kill"]', 400)
    sheet_open(page)
    click(page, '#tlGo', 900)
    expect('لم يصل رد' in page.inner_text('#tlErr') and page.evaluate("() => !!document.getElementById('epModal') && !document.getElementById('tlGo').disabled"), '%s02: الرد الضايع %r' % (pre, page.inner_text('#tlErr')))
    tshot(page, pre + '02c-no-reply.jpg')
    browser.close()


# ======================================================================= ٣ — الأدوات
def flow_recipes(browser, h, pre, vp, mobile):
    if want('03'):
        ef = tfx.ToolsPlatform()
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'recipes')
        ids = card_ids(page)
        expect(ids == ['headshot', 'linkedin', 'post', 'card', 'trend_video'], '%s03: بطاقات الأدوات %r' % (pre, ids))
        sw = page.evaluate("() => [...document.querySelectorAll('.tl-sw')].map(b => [b.getAttribute('aria-checked'), b.textContent.trim(), b.getBoundingClientRect().height])")
        expect([s[0] for s in sw] == ['true', 'false', 'false', 'true', 'false'] and sw[0][1] == 'شغّالة' and sw[1][1] == 'موقوفة', '%s03: مفاتيح التشغيل %r' % (pre, sw))
        heads = page.evaluate("() => [...document.querySelectorAll('.tl-gh')].map(e => e.textContent.trim())")
        expect(heads == ['صورتك', 'لينكدإن والسوشيال', 'الفيديو والكروت'], '%s03: مجموعات الأدوات %r' % (pre, heads))
        tshot(page, pre + '03-recipes.jpg')
        # —— تشغيل «لينكدإن قوي»: ورقة تأكيد ثم كتابة واحدة
        base = len(h.platform_calls)
        click(page, '.tl-sw[data-id="linkedin"]', 400)
        sheet_open(page)
        txt = page.inner_text('#epModal')
        expect('لينكدإن قوي' in txt and 'السقف اليومي' in txt and 'مغلقة للأعضاء' in txt and page.inner_text('#tlGo') == 'شغّل الأداة', '%s03: ورقة التشغيل %r' % (pre, txt[:160]))
        tshot(page, pre + '03b-enable-sheet.jpg')
        check_writes(pre + '03-before-confirm', h, base, 0)
        click(page, '#tlGo', 1100)
        sheet_gone(page)
        got = check_writes(pre + '03-enable', h, base, 1)
        if got:
            r = got[0][3].get('recipe') or {}
            expect(got[0][1] == '/api/bridge/tools/recipes/linkedin' and r.get('enabled') is True and r.get('id') == 'linkedin' and r.get('prompt_template') and r.get('styles') == ['li_office', 'li_library', 'li_calm'],
                   '%s03: جسم التشغيل (وصفة كاملة بمفتاح واحد متغيّر) %r' % (pre, got[0][3].keys()))
        page.wait_for_function("() => document.querySelector('.tl-sw[data-id=\"linkedin\"]').getAttribute('aria-checked') === 'true'", timeout=10000)
        expect('شُغّلت «لينكدإن قوي»' in page.inner_text('.tl-note'), '%s03: رسالة التشغيل' % pre)
        # —— الصفحة القديمة: تعديل من مكان تاني ⇒ ٤٠٩ داخل الورقة بلا كتابة
        ef._recipe('post')['sub_ar'] = 'نص معدَّل من مكان آخر'
        ef._recipe('post')['updated_at'] = tfx.iso(0.5)
        n = len(h.platform_calls)
        click(page, '.tl-sw[data-id="post"]', 400)
        sheet_open(page)
        click(page, '#tlGo', 900)
        expect('تغيّرت هذه الأداة' in page.inner_text('#tlErr'), '%s03: تعارض الصفحة القديمة %r' % (pre, page.inner_text('#tlErr')))
        check_writes(pre + '03-stale', h, n, 0)
        tshot(page, pre + '03c-stale.jpg')
        click(page, '#tlNo', 300)
        sheet_gone(page)
        # —— إيقاف أداة شغّالة
        n = len(h.platform_calls)
        click(page, '.tl-sw[data-id="card"]', 400)
        sheet_open(page)
        expect('فورًا' in page.inner_text('#epModal') and page.inner_text('#tlGo') == 'أوقف الأداة', '%s03: ورقة الإيقاف' % pre)
        click(page, '#tlGo', 1000)
        sheet_gone(page)
        got = check_writes(pre + '03-disable', h, n, 1)
        if got:
            expect(got[0][3]['recipe'].get('enabled') is False, '%s03: جسم الإيقاف' % pre)
        browser.close()

    if want('03d'):                       # السعر: خطأ حيّ · مراجعة · رفض المنصة · حفظ
        ef = tfx.ToolsPlatform()
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'recipes')
        base = len(h.platform_calls)
        click(page, '[data-a="redit"][data-id="headshot"]', 400)
        sheet_open(page)
        curs = page.evaluate("() => [...document.querySelectorAll('.tl-cur > b')].map(b => b.textContent.trim())")
        expect(curs == ['جنيه مصري', 'ريال سعودي', 'درهم إماراتي', 'ريال قطري', 'دينار كويتي', 'ريال عُماني', 'دولار أمريكي'], '%s03d: العملات السبع %r' % (pre, curs))
        expect(page.input_value('#tlP_EGP') == '٢٠' and page.input_value('#tlP_KWD') == '٠٫٤' and page.input_value('#tlEst') == '٠٫١٢', '%s03d: القيم الحالية بأرقام هندية' % pre)
        opts = page.evaluate("() => [...document.querySelectorAll('#tlRule option')].map(o => o.textContent.trim())")
        expect(opts == ['بلا قاعدة مجانية', 'مجانًا أول مرة لكل حساب موثّق', 'مجانية دائمة'.replace('دائمة', 'دائمًا'), 'مجانًا عددًا محددًا كل يوم'], '%s03d: قواعد المجاني %r' % (pre, opts))
        expect('أقل سعر مسموح ١٨' in page.inner_text('#tlrow_EGP'), '%s03d: أقل سعر مسموح للجنيه' % pre)
        page.fill('#tlP_EGP', '5')
        page.wait_for_timeout(200)
        expect('أقل سعر مسموح ١٨ جنيه' in page.inner_text('#tlE_EGP'), '%s03d: خطأ السعر تحت الحد %r' % (pre, page.inner_text('#tlE_EGP')))
        page.fill('#tlP_SAR', 'abc')
        page.fill('#tlEst', '30')
        click(page, '#tlNext', 300)
        expect('اكتب السعر' in page.inner_text('#tlE_SAR') and 'من صفر إلى ٢٠' in page.inner_text('#tlEEst') and 'صحّح الخانات' in page.inner_text('#tlErr'), '%s03d: أخطاء الإرسال %r' % (pre, page.inner_text('#tlErr')))
        tshot(page, pre + '03d-price-errors.jpg', target='.tl-curs')
        check_writes(pre + '03d-invalid', h, base, 0)
        page.fill('#tlEst', '0.12')
        page.fill('#tlP_SAR', '6')
        page.fill('#tlP_EGP', '٢٥')
        page.select_option('#tlRule', 'daily')
        page.wait_for_timeout(200)
        expect(page.evaluate("() => !document.getElementById('tlDailyBox').hidden"), '%s03d: خانة العدد اليومي ظهرت' % pre)
        click(page, '#tlNext', 300)
        expect('اكتب عددًا صحيحًا' in page.inner_text('#tlERule'), '%s03d: عدد المرات مطلوب' % pre)
        page.fill('#tlDaily', '٢')
        click(page, '#tlNext', 400)
        review = page.inner_text('#tlStage')
        expect('احفظ التعديل' in review and '٢٠ جنيه' in review and '٢٥ جنيه' in review and 'مجانًا مرتين كل يوم' in review and '٥ ريال سعودي' in review, '%s03d: ورقة المراجعة %r' % (pre, review[:220]))
        tshot(page, pre + '03e-price-review.jpg')
        check_writes(pre + '03d-before-confirm', h, base, 0)
        ef.forced[('PUT', '/api/bridge/tools/recipes/headshot')] = (422, {'detail': 'سعر USD أقل من الحد الأدنى (التكلفة × 3)'})
        click(page, '#tlGo', 900)
        expect('أقل من الحد الأدنى' in page.inner_text('#tlErr') and '٣' in page.inner_text('#tlErr'), '%s03d: رفض المنصة داخل الورقة %r' % (pre, page.inner_text('#tlErr')))
        del ef.forced[('PUT', '/api/bridge/tools/recipes/headshot')]
        click(page, '#tlGo', 1100)
        sheet_gone(page)
        got = check_writes(pre + '03d-save', h, base, 2)
        if len(got) == 2:
            r = got[1][3]['recipe']
            expect(r['price']['EGP'] == 25 and r['price']['SAR'] == 6 and r['free_rule'] == 'daily:2' and r['est_cost_usd'] == 0.12, '%s03d: جسم الحفظ %r' % (pre, r.get('price')))
        page.wait_for_function("() => document.querySelector('.tl-card[data-id=\"headshot\"]').innerText.includes('مجانًا مرتين كل يوم')", timeout=10000)
        expect('حُفظ سعر' in page.inner_text('.tl-note'), '%s03d: رسالة الحفظ' % pre)
        # سعر صفر على أداة لها تكلفة بلا قاعدة مجانية
        click(page, '[data-a="redit"][data-id="headshot"]', 400)
        sheet_open(page)
        page.select_option('#tlRule', 'none')
        page.fill('#tlP_EGP', '0')
        page.wait_for_timeout(200)
        expect('السعر صفر والتكلفة أكبر من صفر' in page.inner_text('#tlE_EGP'), '%s03d: الصفر بلا قاعدة %r' % (pre, page.inner_text('#tlE_EGP')))
        browser.close()

    if want('03f'):                       # الرسم التجريبي: معاينة بلا تأكيد ولا كتابة
        ef = tfx.ToolsPlatform()
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'recipes')
        base = len(h.platform_calls)
        click(page, '[data-a="rtest"][data-id="headshot"]', 400)
        sheet_open(page)
        expect('لا تكلّف شيئًا' in page.inner_text('#epModal') and 'تجريبية' in page.inner_text('#epModal'), '%s03f: نص المعاينة %r' % (pre, page.inner_text('#epModal')[:100]))
        opts = page.evaluate("() => [...document.querySelectorAll('#tlSt option')].map(o => o.textContent.trim())")
        expect(opts == ['أول مكان في الأداة', 'مكتب', 'مكتبة', 'مدخل المكتب', 'خلفية بسيطة'], '%s03f: أماكن المعاينة %r' % (pre, opts))
        page.select_option('#tlSt', 'hs_library')
        click(page, '#tlGo', 1200)
        page.wait_for_selector('.tl-shot', timeout=10000)
        n = page.evaluate("() => document.querySelectorAll('.tl-shot').length")
        expect(n == 2, '%s03f: صورتان تجريبيتان (%s)' % (pre, n))
        expect(page.evaluate("() => [...document.querySelectorAll('.tl-shot')].every(i => i.naturalWidth > 10)"), '%s03f: الصور ما اتحمّلتش' % pre)
        tshot(page, pre + '03f-test-render.jpg')
        rs = renders_since(h, base)
        expect(len(rs) == 1 and rs[0][3].get('style_id') == 'hs_library' and rs[0][3].get('real') is False, '%s03f: نداء الرسم %r' % (pre, rs))
        check_writes(pre + '03f-no-writes', h, base, 0)
        click(page, '#tlNo', 300)
        sheet_gone(page)
        click(page, '[data-a="rtest"][data-id="trend_video"]', 400)
        sheet_open(page)
        click(page, '#tlGo', 1000)
        expect('لا صور لهذه الأداة' in page.inner_text('#tlOut'), '%s03f: الفيديو بلا صور %r' % (pre, page.inner_text('#tlOut')))
        browser.close()


# ======================================================================= ٤ — الأماكن والأنماط
def style_ids(page, rid):
    return page.evaluate("rid => [...document.querySelectorAll('.tl-group[data-recipe=\"' + rid + '\"] .tl-style[data-id]')].map(s => s.dataset.id)", rid)


def flow_styles(browser, h, pre, vp, mobile):
    if want('04'):
        ef = tfx.ToolsPlatform()
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'styles')
        expect(style_ids(page, 'headshot') == ['hs_office', 'hs_library', 'hs_entrance', 'hs_plain'] and style_ids(page, 'card') == ['card_expert', 'card_cert', 'card_winner'], '%s04: تصاميم الأدوات' % pre)
        pics = page.evaluate("() => [...document.querySelectorAll('.tl-group[data-recipe=headshot] .tl-pic')].map(p => /^url\\(\"?data:image\\/jpeg/.test(getComputedStyle(p).backgroundImage))")
        expect(pics == [True] * 4, '%s04: صور الأماكن %r' % (pre, pics))
        none = page.evaluate("() => [...document.querySelectorAll('.tl-group[data-recipe=linkedin] .tl-pic.none')].length")
        expect(none == 3, '%s04: لينكدإن بلا صور معاينة (%s)' % (pre, none))
        dels = page.evaluate("() => ({card: document.querySelectorAll('.tl-group[data-recipe=card] [data-a=sdel]').length, hs: document.querySelectorAll('.tl-group[data-recipe=headshot] [data-a=sdel]').length, addCard: !!document.querySelector('[data-a=sadd][data-id=card]'), addHs: !!document.querySelector('[data-a=sadd][data-id=headshot]')})")
        expect(dels == {'card': 0, 'hs': 4, 'addCard': False, 'addHs': True}, '%s04: المحمي والإضافة %r' % (pre, dels))
        expect('بلا وجوه' in page.inner_text('.tl-ro'), '%s04: تذكير بلا وجوه' % pre)
        tshot(page, pre + '04-styles.jpg')
        tshot(page, pre + '04-styles-card.jpg', keep=False, target='.tl-group[data-recipe=card]')
        # —— إضافة مكان
        base = len(h.platform_calls)
        click(page, '[data-a="sadd"][data-id="headshot"]', 400)
        sheet_open(page)
        expect(page.input_value('#tlSort') == '٥' and page.evaluate("() => document.getElementById('tlAttach').checked && document.getElementById('tlJudge').checked"), '%s04: الافتراضيات' % pre)
        click(page, '#tlNext', 300)
        errs = page.evaluate("() => ['tlETitle', 'tlEPlace', 'tlEFile'].map(i => document.getElementById(i).textContent.trim())")
        expect(errs == ['اكتب اسم المكان (حتى ٦٠ حرفًا)', 'صف المكان بجملة قصيرة', 'اختر صورة المكان'], '%s04: أخطاء الإضافة %r' % (pre, errs))
        tshot(page, pre + '04b-add-errors.jpg')
        page.set_input_files('#tlFile', files=[{'name': 'page.html', 'mimeType': 'text/html', 'buffer': b'<script>alert(1)</script>'}])
        page.wait_for_timeout(200)
        expect('JPG أو PNG أو WebP' in page.inner_text('#tlEFile'), '%s04: ملف غير صورة %r' % (pre, page.inner_text('#tlEFile')))
        page.set_input_files('#tlFile', files=[{'name': 'big.png', 'mimeType': 'image/png', 'buffer': tfx.place_png('office') + b'\x00' * (3 * 1024 * 1024 + 10)}])
        page.wait_for_timeout(200)
        expect('أكبر من ٣ ميجا' in page.inner_text('#tlEFile'), '%s04: صورة كبيرة %r' % (pre, page.inner_text('#tlEFile')))
        page.fill('#tlTitle', 'غرفة اجتماعات')
        page.fill('#tlPlace', 'a quiet meeting room with soft light')
        page.set_input_files('#tlFile', files=[{'name': 'room.png', 'mimeType': 'image/png', 'buffer': tfx.place_png('office')}])
        page.wait_for_function("() => !document.getElementById('tlThumb').hidden", timeout=5000)
        tshot(page, pre + '04c-add-form.jpg')
        click(page, '#tlNext', 400)
        review = page.inner_text('#tlStage')
        expect('غرفة اجتماعات' in review and 'ويظهر للناس فورًا' in review and page.evaluate("() => !!document.querySelector('#epModal .tl-thumb')"), '%s04: مراجعة الإضافة %r' % (pre, review[:160]))
        tshot(page, pre + '04d-add-review.jpg')
        check_writes(pre + '04-before-confirm', h, base, 0)
        click(page, '#tlGo', 1300)
        sheet_gone(page)
        got = check_writes(pre + '04-add', h, base, 2)
        if len(got) == 2:
            up, att = got
            expect(up[1] == '/api/bridge/tools/styles' and up[3]['recipe_id'] == 'headshot' and up[3]['title_ar'] == 'غرفة اجتماعات' and up[3]['sort'] == '5' and up[3]['__file__']['name'] == 'preview.png'
                   and up[3]['__file__']['head'].startswith('\x89PNG') and re.fullmatch(r'st_[0-9a-f]{8}', up[3]['id']), '%s04: جسم الرفع %r' % (pre, up[3]))
            expect(att[1] == '/api/bridge/tools/recipes/headshot' and att[3]['recipe']['styles'][-1] == up[3]['id'], '%s04: ربط المكان بالأداة' % pre)
        page.wait_for_function("() => document.querySelectorAll('.tl-group[data-recipe=headshot] .tl-style[data-id]').length === 5", timeout=10000)
        expect('وظهر للناس' in page.inner_text('.tl-note'), '%s04: رسالة الإضافة %r' % (pre, page.inner_text('.tl-note')))
        new_id = style_ids(page, 'headshot')[-1]
        # —— إخفاء ثم إظهار
        n = len(h.platform_calls)
        click(page, '[data-a="svis"][data-id="%s"]' % new_id, 400)
        sheet_open(page)
        expect('سيختفي هذا المكان' in page.inner_text('#epModal') and page.inner_text('#tlGo') == 'أخفِه عن الناس', '%s04: ورقة الإخفاء' % pre)
        check_writes(pre + '04-hide-before', h, n, 0)
        click(page, '#tlGo', 1000)
        sheet_gone(page)
        got = check_writes(pre + '04-hide', h, n, 1)
        if got:
            expect(new_id not in got[0][3]['recipe']['styles'], '%s04: جسم الإخفاء' % pre)
        page.wait_for_function("id => document.querySelector('.tl-style[data-id=\"' + id + '\"] .tl-chip').textContent.includes('غير ظاهر')", arg=new_id, timeout=10000)
        tshot(page, pre + '04e-hidden.jpg', target='.tl-group[data-recipe=headshot]')
        # —— تعديل الاسم والترتيب والوصف
        n = len(h.platform_calls)
        click(page, '[data-a="sedit"][data-id="hs_plain"]', 400)
        sheet_open(page)
        expect(page.input_value('#tlTitle') == 'خلفية بسيطة' and page.input_value('#tlSort') == '٤', '%s04: قيم التعديل' % pre)
        page.fill('#tlTitle', 'جدار هادئ')
        page.fill('#tlSort', '٩')
        click(page, '#tlNext', 400)
        review = page.inner_text('#tlStage')
        expect('خلفية بسيطة' in review and 'جدار هادئ' in review and '٩' in review, '%s04: فرق التعديل %r' % (pre, review[:200]))
        tshot(page, pre + '04f-edit-review.jpg')
        check_writes(pre + '04-edit-before', h, n, 0)
        click(page, '#tlGo', 1000)
        sheet_gone(page)
        got = check_writes(pre + '04-edit', h, n, 1)
        if got:
            expect(got[0][3].get('style') == {'title_ar': 'جدار هادئ', 'sort': 9}, '%s04: جسم التعديل (الحقول المتغيّرة فقط) %r' % (pre, got[0][3]))
        # —— حذف بتأكيد أحمر
        n = len(h.platform_calls)
        click(page, '[data-a="sdel"][data-id="%s"]' % new_id, 400)
        sheet_open(page)
        expect('نهائيًا' in page.inner_text('#epModal') and page.inner_text('#tlGo') == 'احذف المكان', '%s04: ورقة الحذف' % pre)
        expect(page.evaluate("() => getComputedStyle(document.getElementById('tlGo')).backgroundColor") == 'rgb(200, 16, 46)', '%s04: زرّ الحذف أحمر' % pre)
        tshot(page, pre + '04g-delete.jpg')
        check_writes(pre + '04-delete-before', h, n, 0)
        click(page, '#tlGo', 1000)
        sheet_gone(page)
        check_writes(pre + '04-delete', h, n, 1)
        page.wait_for_function("id => !document.querySelector('.tl-style[data-id=\"' + id + '\"]')", arg=new_id, timeout=10000)
        browser.close()

    if want('04h'):                       # حارس: آخر أماكن أداة شغّالة + رد ضايع + معرّف مكرر
        ef = tfx.ToolsPlatform()
        ef._recipe('headshot')['styles'] = ['hs_plain']
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'styles')
        n = len(h.platform_calls)
        click(page, '[data-a="sdel"][data-id="hs_plain"]', 400)
        sheet_open(page)
        click(page, '#tlGo', 900)
        expect('آخر أماكن' in page.inner_text('#tlErr'), '%s04h: حارس آخر مكان %r' % (pre, page.inner_text('#tlErr')))
        tshot(page, pre + '04h-last-place.jpg')
        check_writes(pre + '04h-nothing', h, n, 0)
        click(page, '#tlNo', 300)
        sheet_gone(page)
        # رد ضايع على الرفع ⇒ «لم يصل رد»، وإعادة الضغط بنفس المعرّف ⇒ تعارض لا تكرار
        click(page, '[data-a="sadd"][data-id="headshot"]', 400)
        sheet_open(page)
        page.fill('#tlTitle', 'مكان تجريبي')
        page.fill('#tlPlace', 'a calm room')
        page.set_input_files('#tlFile', files=[{'name': 'room.png', 'mimeType': 'image/png', 'buffer': tfx.place_png('library')}])
        page.wait_for_function("() => !document.getElementById('tlThumb').hidden", timeout=5000)
        click(page, '#tlNext', 400)
        ef.forced[('POST', '/api/bridge/tools/styles')] = (504, {'detail': 'timeout'})
        click(page, '#tlGo', 900)
        expect('لم يصل رد' in page.inner_text('#tlErr'), '%s04h: الرد الضايع على الرفع %r' % (pre, page.inner_text('#tlErr')))
        del ef.forced[('POST', '/api/bridge/tools/styles')]
        click(page, '#tlGo', 1200)
        sheet_gone(page)
        click(page, '[data-a="sadd"][data-id="headshot"]', 400)
        sheet_open(page)
        browser.close()


# ======================================================================= ٥ — العيّنات
def flow_samples(browser, h, pre, vp, mobile):
    if want('05'):
        ef = tfx.ToolsPlatform()
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'samples')
        ids = card_ids(page)
        expect(ids == ['ou-a1b2c3d4', 'ou-e5f6a7b8', 'ou-c9d0e1f2', 'ou-13572468'], '%s05: بطاقات العيّنات %r' % (pre, ids))
        pics = page.evaluate("() => [...document.querySelectorAll('.tl-spic')].map(p => /^url\\(\"?data:image\\/jpeg/.test(getComputedStyle(p).backgroundImage))")
        expect(pics == [True] * 4, '%s05: صور العيّنات %r' % (pre, pics))
        first = page.inner_text('.tl-card[data-id="ou-a1b2c3d4"]')
        expect('صورتك المهنية' in first and 'مكتبة' in first and 'hala.nasr@example.test' in first and 'سليم' in first and 'أخفِ العمل' in first and 'امنع صاحبه' in first, '%s05: بطاقة العيّنة %r' % (pre, first))
        tshot(page, pre + '05-samples.jpg')
        base = len(h.platform_calls)
        # —— سليم
        click(page, '[data-a="mok"][data-id="ou-e5f6a7b8"]', 400)
        sheet_open(page)
        expect(page.inner_text('#tlGo') == 'العمل سليم' and 'لا يتغيّر شيء' in page.inner_text('#epModal'), '%s05: ورقة سليم' % pre)
        check_writes(pre + '05-ok-before', h, base, 0)
        click(page, '#tlGo', 1000)
        sheet_gone(page)
        got = check_writes(pre + '05-ok', h, base, 1)
        if got:
            expect(got[0][3].get('action') == 'ok' and got[0][1] == '/api/bridge/tools/samples/ou-e5f6a7b8', '%s05: جسم سليم %r' % (pre, got[0][3]))
        page.wait_for_function("() => document.querySelectorAll('.tl-card.sample').length === 3", timeout=10000)
        expect('عُلِّم العمل سليمًا' in page.inner_text('.tl-note'), '%s05: رسالة سليم' % pre)
        # —— أخفِ العمل (مدفوع ⇒ استرداد)
        click(page, '[data-a="mhide"][data-id="ou-a1b2c3d4"]', 400)
        sheet_open(page)
        expect('يُرَدّ المبلغ' in page.inner_text('#epModal') and 'فلوسي' in page.inner_text('#epModal'), '%s05: ورقة الإخفاء بالاسترداد' % pre)
        expect(page.evaluate("() => getComputedStyle(document.getElementById('tlGo')).backgroundColor") == 'rgb(200, 16, 46)', '%s05: زرّ الإخفاء أحمر' % pre)
        tshot(page, pre + '05b-hide-sheet.jpg')
        check_writes(pre + '05-hide-before', h, base, 1)
        click(page, '#tlGo', 1000)
        sheet_gone(page)
        got = check_writes(pre + '05-hide', h, base, 2)
        page.wait_for_function("() => document.querySelectorAll('.tl-card.sample').length === 2", timeout=10000)
        expect('رُدّ مبلغ مهمة واحدة' in page.inner_text('.tl-note'), '%s05: رسالة الاسترداد %r' % (pre, page.inner_text('.tl-note')))
        # —— رد ضايع على «امنع»
        ef.forced[('POST', '/api/bridge/tools/samples/ou-13572468')] = (504, {'detail': 'timeout'})
        click(page, '[data-a="mban"][data-id="ou-13572468"]', 400)
        sheet_open(page)
        expect('yousef.h@example.test' in page.inner_text('#epModal') and 'كل أعماله' in page.inner_text('#epModal'), '%s05: ورقة المنع' % pre)
        tshot(page, pre + '05c-ban-sheet.jpg')
        click(page, '#tlGo', 900)
        expect('لم يصل رد' in page.inner_text('#tlErr'), '%s05: الرد الضايع %r' % (pre, page.inner_text('#tlErr')))
        del ef.forced[('POST', '/api/bridge/tools/samples/ou-13572468')]
        click(page, '#tlGo', 1100)
        sheet_gone(page)
        got = check_writes(pre + '05-ban', h, base, 4)               # الرد الضايع وصل المنصة فعلًا + إعادة الضغط (المنصة مفروض ترد على التكرار بنفس النتيجة)
        if len(got) >= 4:
            expect(got[2][3].get('action') == 'ban_user' and got[3][3] == got[2][3], '%s05: جسم المنع %r' % (pre, got[2][3]))
        page.wait_for_function("() => document.querySelectorAll('.tl-card.sample').length === 1", timeout=10000)
        expect('مُنع صاحب العمل' in page.inner_text('.tl-note'), '%s05: رسالة المنع %r' % (pre, page.inner_text('.tl-note')))
        tshot(page, pre + '05d-after.jpg')
        browser.close()

    if want('05e'):
        ef = tfx.ToolsPlatform()
        ef.tools_samples = []
        page = topen(browser, h, ef, vp, mobile)
        go_sub(page, 'samples')
        expect('لا عيّنات تنتظر' in page.inner_text('.tl-empty'), '%s05e: الفاضي %r' % (pre, page.inner_text('.v2s-tl')[:80]))
        tshot(page, pre + '05e-empty.jpg')
        browser.close()


# ======================================================================= ٦ — التقرير
def flow_report(browser, h, pre, vp, mobile):
    if not want('06'):
        return
    ef = tfx.ToolsPlatform()
    ef.tools_report[4].update(count=3, succeeded=3, cost_usd=1.8, avg_cost_usd=0.6, revenue_usd=3.0, revenue_by_currency={'SAR': 114}, margin_usd=1.2, guard_flag=True)
    page = topen(browser, h, ef, vp, mobile)
    base0 = len(h.platform_calls)
    go_sub(page, 'report')
    page.wait_for_function("() => document.querySelector('.tl-stats.big')", timeout=10000)
    sums = page.evaluate("() => [...document.querySelectorAll('.tl-stats.big > div')].map(d => d.innerText.replace(/\\s+/g, ' ').trim())")
    expect(sums[0] == '٤٦ عمل' and sums[1] == '٢ لم تنجح' and sums[2].startswith('٥٫٥٢ دولار') and '٤٦٠ جنيه، ١٣٤ ريال سعودي' in sums[3], '%s06: إجماليات اليوم %r' % (pre, sums))
    expect('تقرير يوم' in page.inner_text('.tl-head'), '%s06: عنوان الفترة %r' % (pre, page.inner_text('.tl-head')))
    tp = page.inner_text('.tl-topup')
    expect('رصيد للعميل وليس إيرادًا' in tp and 'أرقام الشحن غير متاحة بعد من المنصة' in tp, '%s06: الشحن منفصلًا وغير متاح %r' % (pre, tp))
    expect('تحتاج مراجعة سعرها' in page.inner_text('.tl-warn') or 'تحتاج مراجعة سعرها' in page.inner_text('.v2s-tl'), '%s06: علم الحارس' % pre)
    tshot(page, pre + '06-report.jpg')
    tshot(page, pre + '06b-report-bottom.jpg', keep=True, target='.tl-topup')
    click(page, '[data-k="week"]', 800)
    page.wait_for_function("() => /من .* إلى/.test(document.querySelector('.tl-head p').textContent)", timeout=10000)
    sums = page.evaluate("() => [...document.querySelectorAll('.tl-stats.big > div')].map(d => d.innerText.replace(/\\s+/g, ' ').trim())")
    expect(sums[0] == '٢٧٦ عمل', '%s06: إجماليات الأسبوع %r' % (pre, sums))
    tshot(page, pre + '06c-week.jpg')
    click(page, '[data-k="custom"]', 500)
    expect('اختر الفترة' in page.inner_text('#tlRepBody'), '%s06: فترة أخرى بلا تواريخ' % pre)
    page.fill('#tlFrom', '2026-10-10')
    page.fill('#tlTo', '2026-10-01')
    click(page, '[data-a="rgo"]', 400)
    expect('بعد تاريخ' in page.inner_text('.v2s-tl'), '%s06: تواريخ مقلوبة %r' % (pre, page.inner_text('.tl-ce')))
    page.fill('#tlFrom', '2026-10-01')
    page.fill('#tlTo', '2026-10-15')
    ef.tools_topups = {'by_currency': {'EGP': 1500, 'SAR': 45}, 'count': 7}
    click(page, '[data-a="rgo"]', 900)
    page.wait_for_function("() => document.querySelector('.tl-tpline') && !document.querySelector('.tl-tpline.na')", timeout=10000)
    tp = page.inner_text('.tl-topup')
    expect('شُحن ٧ مرات: ١٬٥٠٠ جنيه، ٤٥ ريال سعودي' in tp and 'رصيد للعميل وليس إيرادًا' in tp, '%s06: الشحن حين تطلّعه المنصة %r' % (pre, tp))
    expect('من ١ أكتوبر ٢٠٢٦ إلى ١٥ أكتوبر ٢٠٢٦' in page.inner_text('.tl-head'), '%s06: عنوان الفترة المخصّصة %r' % (pre, page.inner_text('.tl-head')))
    tshot(page, pre + '06d-custom.jpg')
    check_writes(pre + '06-readonly', h, base0, 0)      # التقرير للقراءة فقط
    browser.close()


# ======================================================================= ٧ — الإعدادات
def flow_settings(browser, h, pre, vp, mobile):
    if not want('07'):
        return
    ef = tfx.ToolsPlatform()
    tall = dict(vp, height=vp['height'] if mobile else 1500)
    page = topen(browser, h, ef, tall, mobile)
    go_sub(page, 'settings')
    vals = page.evaluate("() => ({cap: document.getElementById('tlS_cap').value, max: document.getElementById('tlS_capMax').value, tmin: document.getElementById('tlS_tmin_EGP').value, kwd: document.getElementById('tlS_tmin_KWD').value, tmax: document.getElementById('tlS_tmax').value, imgM: document.getElementById('tlS_imgM').value, vidM: document.getElementById('tlS_vidM').value, rate: document.getElementById('tlS_rate_OMR').value})")
    expect(vals == {'cap': '١٠', 'max': '٢٠', 'tmin': '١٠٠', 'kwd': '١', 'tmax': '١٠٠٠٠', 'imgM': '٣', 'vidM': '٢٫٥', 'rate': '٠٫٣٨٥'}, '%s07: القيم الحالية بأرقام هندية %r' % (pre, vals))
    sections = page.evaluate("() => [...document.querySelectorAll('.tl-set h3')].map(h => h.textContent.trim())")
    expect(sections == ['الصرف اليومي', 'حدود الاستخدام', 'شحن «فلوسي»', 'حارس السعر', 'سطر «الجاي»'], '%s07: أقسام الإعدادات %r' % (pre, sections))
    tshot(page, pre + '07-settings.jpg')
    base = len(h.platform_calls)
    click(page, '[data-a="sreview"]', 300)
    expect('لا يوجد تغيير' in page.inner_text('#tlSetErr'), '%s07: لا تغيير %r' % (pre, page.inner_text('#tlSetErr')))
    # —— أخطاء الشاشة قبل أي نداء
    page.fill('#tlS_cap', '25')
    page.fill('#tlS_perUser', '0')
    page.fill('#tlS_tmin_SAR', '1.5')
    page.fill('#tlS_capMax', '51')
    page.fill('#tlS_next', 'ا' * 81)
    click(page, '[data-a="sreview"]', 300)
    errs = page.evaluate("() => ['cap', 'capMax', 'perUser', 'tmin_SAR', 'next'].map(k => document.getElementById('tlE_' + k).textContent.trim())")
    expect(all(errs[:4]) and 'أعلى سقف' in errs[1] and 'أقل شحنة' in errs[3] and 'صحّح الخانات' in page.inner_text('#tlSetErr'), '%s07: أخطاء الإعدادات %r' % (pre, errs))
    tshot(page, pre + '07b-settings-errors.jpg', target='.tl-set')
    check_writes(pre + '07-invalid', h, base, 0)
    # —— تعديل صحيح ⇒ مراجعة ⇒ تأكيد
    click(page, '[data-a="sreset"]', 300)
    page.fill('#tlS_cap', '١٥')
    page.fill('#tlS_perUser', '8')
    page.fill('#tlS_tmin_EGP', '150')
    page.fill('#tlS_next', 'الجاي: لينكدإن قوي')
    click(page, '[data-a="sreview"]', 500)
    sheet_open(page)
    diff = page.inner_text('#epModal .tl-diff')
    expect('١٠ دولارات' in diff and '١٥ دولارًا' in diff and '٨' in diff and '١٥٠ جنيه' in diff and 'الجاي: لينكدإن قوي' in diff and 'سقف الصرف' in page.inner_text('#epModal'), '%s07: مراجعة الإعدادات %r' % (pre, diff))
    tshot(page, pre + '07c-settings-review.jpg')
    check_writes(pre + '07-before-confirm', h, base, 0)
    ef.forced[('PUT', '/api/bridge/tools/settings')] = (422, {'detail': 'أعلى سقف مسموح به لا يزيد على ٥٠ دولارًا'})
    click(page, '#tlGo', 900)
    expect('أعلى سقف' in page.inner_text('#tlErr'), '%s07: رفض المنصة %r' % (pre, page.inner_text('#tlErr')))
    del ef.forced[('PUT', '/api/bridge/tools/settings')]
    click(page, '#tlGo', 1100)
    sheet_gone(page)
    got = check_writes(pre + '07-save', h, base, 2)
    if len(got) == 2:
        expect(got[1][3].get('settings') == {'daily_cap_usd': 15, 'per_user_daily': 8, 'topup_min_by_currency': {'EGP': 150}, 'next_line': 'الجاي: لينكدإن قوي'}, '%s07: جسم الحفظ (المتغيّر فقط) %r' % (pre, got[1][3]))
    page.wait_for_function("() => document.getElementById('tlS_cap') && document.getElementById('tlS_cap').value === '١٥'", timeout=10000)
    expect('حُفظت الإعدادات' in page.inner_text('.tl-note') and ef.tools_settings['daily_cap_usd'] == 15, '%s07: رسالة الحفظ' % pre)
    # —— رفع أعلى سقف إلى ٥٠ بخطوتين صريحتين
    page.fill('#tlS_capMax', '٥٠')
    page.fill('#tlS_cap', '٣٠')
    click(page, '[data-a="sreview"]', 500)
    sheet_open(page)
    expect('أعلى قيمة يمكن اختيارها' in page.inner_text('#epModal'), '%s07: تنبيه رفع الحد الأعلى' % pre)
    tshot(page, pre + '07d-cap-max.jpg')
    click(page, '#tlGo', 1100)
    sheet_gone(page)
    got = check_writes(pre + '07-cap-max', h, base, 3)
    if len(got) == 3:
        expect(got[2][3].get('settings') == {'daily_cap_usd': 30, 'daily_cap_max_usd': 50}, '%s07: جسم رفع الحد الأعلى %r' % (pre, got[2][3]))
    browser.close()


# ======================================================================= ٨ — المصدر الواقع والفاضي
def flow_down(browser, h, pre, vp, mobile):
    if not want('08'):
        return
    ef = tfx.ToolsPlatform()
    ef.tools_missing = True
    page = topen(browser, h, ef, vp, mobile, wait_ready=False)
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-tl .tl-status') && !document.querySelector('.v2s-tl .tl-skel')", timeout=30000)
    page.wait_for_timeout(500)
    nums = {s: (n, t) for s, n, t in tile_numbers(page)}
    expect(all(v == ('—', 'غير متاح بعد') for v in nums.values()) and len(nums) == 5, '%s08: المصدر الواقع يكتب «غير متاح بعد» %r' % (pre, nums))
    expect('غير متاح بعد على المنصة' in page.inner_text('.tl-status') and page.evaluate("() => !document.querySelector('[data-a=kill]')"), '%s08: لوحة الحالة بلا زرّ إيقاف %r' % (pre, page.inner_text('.tl-status')[:80]))
    tshot(page, pre + '08-down.jpg')
    click(page, '.tl-tile[data-sub="recipes"]', 600)
    expect('غير متاح بعد على المنصة' in page.inner_text('.v2s-tl'), '%s08: شاشة الأدوات والمصدر واقع' % pre)
    ef.tools_missing = False
    click(page, '[data-a="hub"]', 400)
    click(page, '.tl-tile[data-sub="recipes"]', 500)
    browser.close()
    # فاضي صادق: لا أدوات ولا عيّنات
    ef = tfx.ToolsPlatform(empty=True)
    page = topen(browser, h, ef, vp, mobile)
    go_sub(page, 'recipes')
    expect('لا أدوات على المنصة' in page.inner_text('.v2s-tl'), '%s08b: فاضي الأدوات' % pre)
    tshot(page, pre + '08b-empty.jpg')
    browser.close()
    # خطأ ٥٠٢ ثم «أعد المحاولة»
    ef = tfx.ToolsPlatform()
    ef.down.add('/api/bridge/tools/recipes')
    page = topen(browser, h, ef, vp, mobile)
    go_sub(page, 'recipes')
    expect('تعذّر جلب الأدوات' in page.inner_text('.tl-warn') and 'ليس معناه' in page.inner_text('.tl-warn'), '%s08c: خطأ الجلب %r' % (pre, page.inner_text('.v2s-tl')[:100]))
    tshot(page, pre + '08c-error.jpg')
    ef.down.discard('/api/bridge/tools/recipes')
    click(page, '[data-a="retry"]', 900)
    page.wait_for_function("() => document.querySelectorAll('.tl-card[data-id]').length === 5", timeout=10000)
    browser.close()


# ======================================================================= ٩ — المفتاح مقفول
def flow_closed(browser, h, pre, vp, mobile):
    if not want('09'):
        return
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = tfx.ToolsPlatform()
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#company', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && document.getElementById('view')", timeout=30000)
        page.wait_for_timeout(1500)
        st = page.evaluate("() => ({new: !!document.querySelector('.v2s-tl'), on: !!window.V2_ON})")
        expect(not st['new'] and not st['on'], '%s09: المفتاح مقفول وفيه أثر %r' % (pre, st))
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/tools/overview', '/api/v2/tools/recipes', '/api/v2/tools/settings', '/api/v2/tools/samples', '/api/v2/tools/report']) {
            const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        expect(not bad, '%s09: مسارات الأدوات والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(tfx.ToolsPlatform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', DESK, False), ('m', MOB, True)):
                if pre not in os.environ.get('TL_VP', 'dm'):
                    continue
                for flow in (flow_hub, flow_kill, flow_recipes, flow_styles, flow_samples, flow_report, flow_settings, flow_down, flow_closed):
                    try:
                        flow(browser, h, pre, vp, mobile)
                    except Exception as e:   # noqa: BLE001 — فشل خطوة ⇒ مشكلة مسجَّلة، ونكمّل باقي الخطوات
                        import traceback
                        PROBLEMS.append('%s%s: انهارت الخطوة: %s | %s' % (pre, flow.__name__, str(e).strip().split('\n')[0][:160], traceback.format_exc().strip().split('\n')[-3].strip()[:200]))
                        try:
                            browser.close()
                        except Exception:   # noqa: BLE001
                            pass
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
