# -*- coding: utf-8 -*-
"""لقطات وفحوص «إدارة السوق» (السوق v4، docs/v2/market4/SPEC.md) — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٤٣٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_market4.py ../docs/v2/market4/shots [only-prefix,...]

الخطوات: ٠١ المربّعات الأربعة بأرقامها · ٠٢ اقتراحات «أخرى» (قائمة · ورقة الاعتماد بالنوع والتخصص والنطاق وفي كلٍّ «أخرى» · الرفض) ·
٠٣ مدى الأسعار (قائمة «بلا مدى» · البحث · ورقة سبع عملات بالتحذير والخطأ · المراجعة · المسح) · ٠٤ المكاتب (قائمة · «وثّق السجل») ·
٠٥ الطلبات المفتوحة (قراءة فقط) · ٠٦ بلاد القيد وملف الترخيص عند قبول الانضمام · ٠٧ سلّم السوق في جدول النسب · ٠٨ المصدر الواقع والفاضي · ٠٩ المفتاح مقفول.

السكربت بيفشل (exit 1) لو: «0/null/NaN/undefined» ظاهر · هدف أقل من ٤٤px · خانة أقل من ١٦px · تمرير أفقي · رقم لاتيني ظاهر · «·» ملاصقة لرقم · كلمة ممنوعة ·
نافذة متصفح (`alert`/`confirm`/`prompt`) · كتابة وصلت المنصة قبل ضغطة التأكيد أو غير المسارات المسموحة أو بلا `confirmed:true` على جانب الداشبورد ·
حفظ في المتصفح · أي طلب خرج من العملية غير خطوط جوجل.
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية، والمنصة جدول في الذاكرة (`m4_fixtures.Market4Platform`).
"""
import json
import os
os.environ.setdefault('DASH_SCHEDULER', '0')   # R16: مراقبة التشغيل/الملخص اليومي ما يشتغلوش جوّه الأداة (كانوا بيبعتوا تليجرام عبر الجسر المزيّف)
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                         # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import m4_fixtures as m4fx                    # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

PROBLEMS = vs.PROBLEMS
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
DESK = vs.DESK
MOB = {'width': 430, 'height': 932}
READY = "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-m4[data-board]') && !document.querySelector('.v2s-m4 .m4-skel') && !/…/.test((document.querySelector('.m4-tiles') || {innerText: ''}).innerText)"
PEOPLE_READY = ("() => window.V2SHELL && V2SHELL.on === true && window.EP && ['inbox','invites','pendingUsers'].every(k => EP.state[k] === 'ready')"
                " && document.querySelector('.v2c-tab') && document.querySelector('.v2p[data-tab=\"requests\"]') && !document.querySelector('.v2p .v2p-sk')")
BANNED = ('يقوّم', 'يقوم', 'API', 'JSON', 'Claude', 'DeepSeek', 'Anthropic', 'endpoint', 'token', 'bridge')
OK_WRITES = [('POST', re.compile(r'^/api/bridge/market/suggestions/[^/]+/decide$')), ('PUT', re.compile(r'^/api/bridge/market/catalog/[^/]+/anchor$')),
             ('POST', re.compile(r'^/api/bridge/market/orgs/[^/]+/verify-reg$')), ('POST', re.compile(r'^/api/bridge/join-requests/[^/]+/decide$')),
             ('PUT', re.compile(r'^/api/bridge/shares$'))]
SCOPE_JS = """() => [...document.querySelectorAll('.v2s-m4, #epModal.v2s-m4-sh, #epModal .m4-lic, .m4-lic')].map(e => { const c = e.cloneNode(true);
  c.querySelectorAll('[dir="ltr"], [dir="auto"], .m4-who, script, style, input, textarea, select, option').forEach(n => n.remove()); return c.innerText; }).join('\\n')"""


def want(code):
    return not ONLY or any(code.startswith(o) for o in ONLY)


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def m4check(page, name):
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v2s-m4 button, .v2s-m4 input:not([type=checkbox]):not([type=radio]), .v2s-m4 a.m4-reg, #epModal.v2s-m4-sh button, #epModal.v2s-m4-sh input:not([type=checkbox]):not([type=radio]), #epModal.v2s-m4-sh select, #epModal.v2s-m4-sh textarea, .m4-lic button, .m4-lic a.m4-lic-dl, .m4-lic-opt')]
      .filter(b => b.offsetParent && !b.closest('[hidden]')).map(b => [(b.className || b.id || b.tagName).toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    boxes = page.evaluate("""() => [...document.querySelectorAll('.v2s-m4 input[type=text], .v2s-m4 input[type=search], .v2s-m4 textarea, #epModal.v2s-m4-sh input[type=text], #epModal.v2s-m4-sh input:not([type]), #epModal.v2s-m4-sh textarea, #epModal.v2s-m4-sh select')]
      .filter(b => b.offsetParent).map(b => [b.id || b.className, parseFloat(getComputedStyle(b).fontSize)])""")
    for ident, fs in boxes:
        if fs < 16:
            PROBLEMS.append('%s: خانة %s خطها %s أقل من ١٦' % (name, ident, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    wide = page.evaluate("() => [...document.querySelectorAll('.v2s-m4 *, #epModal.v2s-m4-sh *, .m4-lic *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed').length")
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
    keys = page.evaluate("() => { try { return Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => /market|m4|licence|anchor/i.test(k)); } catch (e) { return []; } }")
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
    m4check(page, name)


def calls_since(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE')]


def check_writes(name, h, since, expected, with_confirm=False):
    got = calls_since(h, since)
    for m, p, _q, body in got:
        if not any(m == am and rx.match(p) for am, rx in OK_WRITES):
            PROBLEMS.append('%s: كتابة غير مسموحة %s %s' % (name, m, p))
        if '/join-requests/' not in p and (not isinstance(body, dict) or not str(body.get('by') or '').strip()):
            PROBLEMS.append('%s: كتابة بلا by %s %s' % (name, m, p))        # قرار الانضمام: المنصة بتختم by=dashboard، والتدقيق عندنا باسم الفاعل
        if with_confirm and (not isinstance(body, dict) or body.get('confirmed') is not True):
            PROBLEMS.append('%s: كتابة بلا confirmed:true %s %s' % (name, m, p))
    if len(got) != expected:
        PROBLEMS.append('%s: عدد الكتابات %d بدل %d: %r' % (name, len(got), expected, [(m, p) for m, p, _q, _b in got]))
    return got


def mopen(browser, h, ef, viewport, mobile, hash_='#s/market/manage', ready=READY):
    h.ef = ef
    ctx = browser.context(h, 'admin', viewport, mobile)
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


def click(page, sel, wait=300):
    page.click(sel)
    page.wait_for_timeout(wait)


def go_sub(page, sub):
    click(page, '.m4-tile[data-sub="%s"]' % sub, 500)
    page.wait_for_function("() => !document.querySelector('.v2s-m4 .m4-skel') && document.querySelector('.m4-head')", timeout=15000)
    page.wait_for_timeout(300)


def sheet_open(page):
    page.wait_for_selector('#epModal.v2s-m4-sh', timeout=10000)
    page.wait_for_timeout(250)


def sheet_gone(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(450)


def tile_numbers(page):
    return page.evaluate("() => [...document.querySelectorAll('.m4-tile')].map(t => [t.dataset.sub, t.querySelector('.m4-n').textContent.trim(), t.querySelector('small').textContent.trim()])")


def arn(n):
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


# ======================================================================= ١ — الرئيسية
def flow_manage(browser, h, pre, vp, mobile):
    # —— ٠١) المربّعات
    if want('01'):
        ef = m4fx.Market4Platform()
        page = mopen(browser, h, ef, vp, mobile)
        nums = {s: (n, t) for s, n, t in tile_numbers(page)}
        open_n = len([r for r in ef.rows if r['status'] == 'open' and r['kind'] != 'training_offer' and not r['is_test']])
        expect(nums.get('sug') == ('٤', 'تنتظر قرارك') and nums.get('price') == ('٩', 'خدمة بلا مدى سعر') and nums.get('firms') == ('٣', 'مكتب ينتظر التوثيق')
               and nums.get('open') == (arn(open_n), 'طلب مفتوح الآن'), '%s01: أرقام المربّعات %r' % (pre, nums))
        tabs = page.evaluate("() => [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim())")
        expect(tabs[-1] == 'إدارة السوق' and len(tabs) == 4, '%s01: تبويب إدارة السوق %r' % (pre, tabs))
        imgs = page.evaluate("() => [...document.querySelectorAll('.m4-timg')].map(e => getComputedStyle(e).backgroundImage.replace(/.*\\//, ''))")
        expect(len(imgs) == 4 and all('.jpg' in i for i in imgs), '%s01: صور المربّعات %r' % (pre, imgs))
        mshot(page, pre + '01-hub.jpg')
        browser.close()

    # —— ٠٢) اقتراحات «أخرى»
    if want('02'):
        ef = m4fx.Market4Platform()
        page = mopen(browser, h, ef, vp, mobile)
        go_sub(page, 'sug')
        cards = page.evaluate("() => [...document.querySelectorAll('.m4-card')].map(c => [c.dataset.id, c.querySelector('h3').textContent.trim(), !!c.querySelector('[data-a=sapprove]'), !!c.querySelector('[data-a=sreject]')])")
        expect([c[0] for c in cards] == ['sg-1', 'sg-2', 'sg-3', 'sg-4'] and all(c[2] and c[3] for c in cards), '%s02: بطاقات الاقتراحات %r' % (pre, cards))
        who = page.inner_text('.m4-card[data-id="sg-1"] .m4-who')
        expect('lawyer.hala@example.test' in who, '%s02: صاحب الاقتراح %r' % (pre, who))
        mshot(page, pre + '02-sug-list.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="sapprove"][data-id="sg-1"]', 400)
        sheet_open(page)
        opts_t = page.evaluate("() => [...document.querySelectorAll('#m4Type option')].map(o => o.textContent.trim())")
        opts_s = page.evaluate("() => [...document.querySelectorAll('#m4Spec option')].map(o => o.textContent.trim())")
        expect(opts_t[-1] == 'أخرى' and len(opts_t) == 14 and opts_s[-1] == 'أخرى' and len(opts_s) == 16, '%s02: «أخرى» في قوائم الاختيار %r %r' % (pre, opts_t[-1], opts_s[-1]))
        radios = page.evaluate("() => [...document.querySelectorAll('input[name=m4sc]')].map(r => r.value)")
        expect(radios == ['note', 'other'], '%s02: خيارا النطاق %r' % (pre, radios))
        click(page, '#m4Go', 300)
        expect('اختر نوع الخدمة' in page.inner_text('#m4Err'), '%s02: الاعتماد بلا نوع ما اتمنعش' % pre)
        check_writes(pre + '02-empty', h, base, 0)
        page.select_option('#m4Type', 'other')
        page.select_option('#m4Spec', 'other')
        page.check('input[name=m4sc][value=other]')
        page.fill('#m4Scope', 'ترجمة العقود والأحكام مع مراجعة لغوية يعتمدها محامٍ')
        page.wait_for_timeout(200)
        hints = page.inner_text('#m4TypeH') + ' | ' + page.inner_text('#m4SpecH')
        expect('رأي قانوني مكتوب' in hints and 'عام' in hints, '%s02: تلميح «أخرى» %r' % (pre, hints))
        mshot(page, pre + '02b-sug-approve.jpg', target=None)
        check_writes(pre + '02-before-confirm', h, base, 0)
        click(page, '#m4Go', 1000)
        sheet_gone(page)
        got = check_writes(pre + '02-approve', h, base, 1)
        if got:
            expect(got[0][3].get('decision') == 'approve' and got[0][3].get('service_type') == '' and got[0][3].get('specialty') == '' and got[0][3].get('scope', '').startswith('ترجمة'),
                   '%s02: جسم الاعتماد %r' % (pre, got[0][3]))
            expect('confirmed' not in got[0][3], '%s02: confirmed لا يسافر للمنصة في هذا الجسر' % pre)
        page.wait_for_function("() => document.querySelectorAll('.m4-card').length === 3", timeout=10000)
        expect('سجّلنا طلب تقديمها' in page.inner_text('.m4-note'), '%s02: رسالة النجاح %r' % (pre, page.inner_text('.v2s-m4')[:120]))
        mshot(page, pre + '02d-sug-after.jpg', keep=False)
        # اعتماد باختيارات حقيقية
        click(page, '[data-a="sapprove"][data-id="sg-2"]', 400)
        sheet_open(page)
        page.select_option('#m4Type', 'compliance')
        page.select_option('#m4Spec', 'labor')
        click(page, '#m4Go', 1000)
        sheet_gone(page)
        got = check_writes(pre + '02-approve2', h, base, 2)
        if len(got) == 2:
            expect((got[1][3].get('service_type'), got[1][3].get('specialty'), got[1][3].get('scope')) == ('compliance', 'labor', ''), '%s02: جسم الاعتماد الثاني %r' % (pre, got[1][3]))
        # الرفض
        click(page, '[data-a="sreject"][data-id="sg-3"]', 400)
        sheet_open(page)
        expect('بلا ذكر سبب' in page.inner_text('#epModal'), '%s02: نص الرفض %r' % (pre, page.inner_text('#epModal')[:100]))
        mshot(page, pre + '02c-sug-reject.jpg', keep=True)
        check_writes(pre + '02-reject-before', h, base, 2)
        click(page, '#m4Go', 1000)
        sheet_gone(page)
        got = check_writes(pre + '02-reject', h, base, 3, with_confirm=False)
        if len(got) == 3:
            expect(got[2][3] == {'decision': 'reject', 'by': got[2][3].get('by')} and got[2][3].get('by'), '%s02: جسم الرفض %r' % (pre, got[2][3]))
        # قرار سبق (٤٠٩) يظهر نصه كما هو، والقائمة تتحدّث
        ef.suggestions[3]['status'] = 'approved'
        click(page, '[data-a="sreject"][data-id="sg-4"]', 400)
        sheet_open(page)
        click(page, '#m4Go', 900)
        expect('اتقرّر' in page.inner_text('#m4Err'), '%s02: رد المنصة ٤٠٩ ما ظهرش %r' % (pre, page.inner_text('#m4Err')))
        mshot(page, pre + '02e-sug-conflict.jpg')
        browser.close()

    # —— ٠٣) مدى الأسعار
    if want('03'):
        ef = m4fx.Market4Platform()
        page = mopen(browser, h, ef, vp, mobile)
        go_sub(page, 'price')
        rows = page.evaluate("() => [...document.querySelectorAll('.m4-card')].map(c => [c.dataset.slug, !!c.querySelector('[data-a=edit]'), c.querySelector('.m4-range').textContent.trim()])")
        expect(len(rows) == 9 and all(r[1] and r[2] == 'بلا مدى' for r in rows), '%s03: قائمة «بلا مدى» %r' % (pre, rows))
        expect(page.evaluate("() => document.querySelector('[data-a=norange]').getAttribute('aria-pressed')") == 'true', '%s03: فلتر بلا مدى ما اشتغلش' % pre)
        mshot(page, pre + '03-price-list.jpg')
        # البحث
        page.fill('#m4q', 'عقد')
        click(page, '[data-a="qgo"]', 900)
        slugs = page.evaluate("() => [...document.querySelectorAll('.m4-card')].map(c => c.dataset.slug)")
        expect(slugs == ['contract-draft'], '%s03: نتيجة البحث %r' % (pre, slugs))
        # الفلتر مطفأ: الكل، والثابت بلا زرّ
        click(page, '[data-a="norange"]', 900)
        slugs = page.evaluate("() => [...document.querySelectorAll('.m4-card')].map(c => [c.dataset.slug, !!c.querySelector('[data-a=edit]')])")
        expect([s[0] for s in slugs] == ['contract-review', 'contract-draft', 'rent-opinion'] and [s[1] for s in slugs] == [True, True, False], '%s03: بحث «عقد» بلا فلتر %r' % (pre, slugs))
        page.fill('#m4q', '')
        click(page, '[data-a="qgo"]', 900)
        allrows = page.evaluate("() => [...document.querySelectorAll('.m4-card')].map(c => [c.dataset.slug, !!c.querySelector('[data-a=edit]'), !!c.querySelector('.m4-st.fixed')])")
        expect(len(allrows) == 14 and [r[0] for r in allrows if not r[1]] == ['family-opinion', 'rent-opinion'] and all(r[2] for r in allrows if not r[1]), '%s03: الثابت بلا زرّ %r' % (pre, allrows))
        mshot(page, pre + '03e-price-all.jpg')
        click(page, '[data-a="norange"]', 900)
        # الورقة: تحذير وخطأ وتصحيح
        base = len(h.platform_calls)
        click(page, '[data-a="edit"][data-slug="contract-draft"]', 400)
        sheet_open(page)
        curs = page.evaluate("() => [...document.querySelectorAll('.m4-cur > b')].map(b => b.textContent.trim())")
        expect(curs == ['جنيه مصري', 'ريال سعودي', 'درهم إماراتي', 'ريال قطري', 'دينار كويتي', 'ريال عُماني', 'دولار أمريكي'], '%s03: العملات السبع %r' % (pre, curs))
        click(page, '#m4Next', 300)
        expect('امسح المدى' in page.inner_text('#m4Err'), '%s03: حفظ فاضٍ %r' % (pre, page.inner_text('#m4Err')))
        expect(page.evaluate("() => !document.getElementById('m4Clear')"), '%s03: «امسح المدى» ظهر على خدمة بلا مدى' % pre)
        page.fill('#m4min_EGP', '٢٥٠٠')
        page.fill('#m4max_EGP', '٦٠٠٠')
        page.fill('#m4min_SAR', '100')
        page.fill('#m4max_SAR', '900')
        page.fill('#m4min_USD', '50')
        page.fill('#m4max_KWD', '5')
        page.fill('#m4min_AED', '9')
        page.fill('#m4max_AED', '1.5')
        page.wait_for_timeout(250)
        warn = page.inner_text('#m4e_SAR')
        bad_aed = page.inner_text('#m4e_AED')
        expect('ثلاثة أضعاف' in warn and 'بلا كسور' in bad_aed, '%s03: تحذير ٣× وخطأ الكسور %r %r' % (pre, warn, bad_aed))
        click(page, '#m4Next', 300)
        expect(page.inner_text('#m4e_USD').startswith('اكتب الأدنى والأعلى معًا') and page.inner_text('#m4e_KWD').startswith('اكتب الأدنى والأعلى معًا'), '%s03: نصف الزوج %r' % (pre, page.inner_text('#m4e_USD')))
        mshot(page, pre + '03b-price-edit.jpg', target='.m4-curs')
        check_writes(pre + '03-invalid', h, base, 0)
        page.fill('#m4min_USD', '')
        page.fill('#m4max_KWD', '')
        page.fill('#m4min_AED', '')
        page.fill('#m4max_AED', '')
        click(page, '#m4Next', 400)
        review = page.inner_text('#m4Stage')
        expect('احفظ المدى' in review and 'بلا مدى' in review and '٢٬٥٠٠ إلى ٦٬٠٠٠ جنيه' in review and 'ثلاثة أضعاف' in review, '%s03: ورقة المراجعة %r' % (pre, review[:200]))
        mshot(page, pre + '03c-price-review.jpg', keep=True)
        check_writes(pre + '03-before-confirm', h, base, 0)
        # المنصة ترفض ⇒ النص كما هو داخل الورقة
        ef.forced[('PUT', '/api/bridge/market/catalog/contract-draft/anchor')] = (422, {'detail': {'message': 'SAR: الأدنى لازم يكون أقل من الأعلى'}})
        click(page, '#m4Go', 900)
        expect('SAR' in page.inner_text('#m4Err') or 'الأدنى' in page.inner_text('#m4Err'), '%s03: رفض المنصة ما ظهرش %r' % (pre, page.inner_text('#m4Err')))
        del ef.forced[('PUT', '/api/bridge/market/catalog/contract-draft/anchor')]
        click(page, '#m4Go', 1100)
        sheet_gone(page)
        got = check_writes(pre + '03-save', h, base, 2)
        if len(got) == 2:
            expect(got[1][3].get('anchor_range') == {'EGP': [2500, 6000], 'SAR': [100, 900]}, '%s03: جسم المدى %r' % (pre, got[1][3]))
        page.wait_for_function("() => !document.querySelector('[data-slug=\"contract-draft\"]')", timeout=10000)
        expect('حُفظ مدى السعر' in page.inner_text('.m4-note'), '%s03: رسالة الحفظ' % pre)
        n9 = page.evaluate("() => document.querySelectorAll('.m4-card').length")
        expect(n9 == 8, '%s03: القائمة ما اتحدّثتش (%s)' % (pre, n9))
        # مسح مدى موجود
        click(page, '[data-a="norange"]', 900)
        click(page, '[data-a="edit"][data-slug="contract-review"]', 400)
        sheet_open(page)
        expect(page.input_value('#m4min_EGP') == '٢٥٠٠' and page.input_value('#m4max_USD') == '٢٢٠', '%s03: القيم الحالية بأرقام هندية' % pre)
        click(page, '#m4Clear', 400)
        review = page.inner_text('#m4Stage')
        expect('سيُمسح مدى السعر كله' in review and review.count('بلا مدى') >= 3, '%s03: ورقة المسح %r' % (pre, review[:160]))
        mshot(page, pre + '03d-price-clear.jpg', keep=True)
        click(page, '#m4Go', 1100)
        sheet_gone(page)
        got = check_writes(pre + '03-clear', h, base, 3)
        if len(got) == 3:
            expect(got[2][3].get('anchor_range') is None and 'anchor_range' in got[2][3], '%s03: جسم المسح %r' % (pre, got[2][3]))
        browser.close()

    # —— ٠٤) المكاتب
    if want('04'):
        ef = m4fx.Market4Platform()
        page = mopen(browser, h, ef, vp, mobile)
        go_sub(page, 'firms')
        info = page.evaluate("""() => [...document.querySelectorAll('.m4-card')].map(c => ({id: c.dataset.id, reg: (c.querySelector('a.m4-reg') || {}).href || '', noreg: !!c.querySelector('.m4-reg.none'),
          btn: !!c.querySelector('[data-a=verify]'), meta: c.querySelector('.m4-meta').innerText.replace(/\\s+/g, ' ')}))""")
        expect([i['id'] for i in info] == ['org-1', 'org-2', 'org-3'], '%s04: المكاتب %r' % (pre, info))
        expect(info[0]['reg'].startswith('https://files.example.test/') and info[0]['btn'] and 'ثلاثة' not in info[0]['meta'] and '٣ أعضاء' in info[0]['meta'], '%s04: مكتب ١ %r' % (pre, info[0]))
        expect(info[2]['noreg'] and not info[2]['btn'], '%s04: مكتب بلا سجل %r' % (pre, info[2]))
        target = page.evaluate("() => [...document.querySelectorAll('a.m4-reg')].map(a => a.getAttribute('rel') + '|' + a.getAttribute('target'))")
        expect(all(t == 'noopener noreferrer|_blank' for t in target), '%s04: رابط السجل بلا rel %r' % (pre, target))
        mshot(page, pre + '04-firms-list.jpg')
        base = len(h.platform_calls)
        click(page, '[data-a="verify"][data-id="org-1"]', 400)
        sheet_open(page)
        expect('افتح السجل وراجعه' in page.inner_text('#epModal') and 'مكتب النور' in page.inner_text('#epModal'), '%s04: ورقة التوثيق' % pre)
        mshot(page, pre + '04b-firms-verify.jpg')
        check_writes(pre + '04-before', h, base, 0)
        click(page, '#m4Go', 1000)
        sheet_gone(page)
        got = check_writes(pre + '04-verify', h, base, 1)
        if got:
            expect(got[0][1].endswith('/org-1/verify-reg') and set(got[0][3]) == {'by'}, '%s04: جسم التوثيق %r' % (pre, got[0][3]))
        page.wait_for_function("() => document.querySelectorAll('.m4-card').length === 2", timeout=10000)
        expect('تم توثيق السجل' in page.inner_text('.m4-note'), '%s04: رسالة التوثيق' % pre)
        # رد ضايع
        ef.forced[('POST', '/api/bridge/market/orgs/org-2/verify-reg')] = (504, {'detail': 'x'})
        click(page, '[data-a="verify"][data-id="org-2"]', 400)
        sheet_open(page)
        click(page, '#m4Go', 900)
        expect('لم يصل رد' in page.inner_text('#m4Err'), '%s04: رد ضايع ما ظهرش «لم يصل رد»' % pre)
        mshot(page, pre + '04c-no-reply.jpg')
        browser.close()

    # —— ٠٥) الطلبات المفتوحة
    if want('05'):
        ef = m4fx.Market4Platform()
        page = mopen(browser, h, ef, vp, mobile)
        go_sub(page, 'open')
        info = page.evaluate("""() => ({tb: document.querySelectorAll('.m4-tb tbody tr').length, cards: document.querySelectorAll('.m4-cards.open .m4-card').length,
          tbVis: !!(document.querySelector('.m4-tbw') && document.querySelector('.m4-tbw').offsetParent), cardsVis: !!(document.querySelector('.m4-cards.open') && document.querySelector('.m4-cards.open').offsetParent),
          acts: document.querySelectorAll('.v2s-m4 [data-a=sapprove], .v2s-m4 [data-a=verify], .v2s-m4 [data-a=edit]').length, ro: (document.querySelector('.m4-ro') || {}).textContent})""")
        n = len([r for r in ef.rows if r['status'] == 'open' and r['kind'] != 'training_offer' and not r['is_test']])
        expect(info['tb'] == n and info['cards'] == n and info['acts'] == 0 and 'للعرض فقط' in (info['ro'] or ''), '%s05: الطلبات المفتوحة %r' % (pre, info))
        expect(info['tbVis'] != mobile and info['cardsVis'] == mobile, '%s05: جدول للكمبيوتر وبطاقات للموبايل %r' % (pre, info))
        text = page.inner_text('.v2s-m4')
        expect('مراجعة عقد تجاري' in text and 'مصر' in text and '٣ مرات' in text and 'مرفقان' in text and 'عروض' in text, '%s05: أعمدة الطلب %r' % (pre, text[:120]))
        mshot(page, pre + '05-open-list.jpg')
        base = len(h.platform_calls)
        check_writes(pre + '05-readonly', h, base, 0)
        browser.close()

    # —— ٠٨) مصدر واقع · فاضي
    if want('08'):
        ef = m4fx.Market4Platform()
        ef.down.add('/api/bridge/market/suggestions')
        ef.m4_missing.add('/api/bridge/market/orgs')
        page = mopen(browser, h, ef, vp, mobile, ready="() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.m4-tiles') && !/…/.test(document.querySelector('.m4-tiles').innerText)")
        nums = {s: (n, t) for s, n, t in tile_numbers(page)}
        expect(nums['sug'] == ('—', 'غير متاح بعد') and nums['firms'] == ('—', 'غير متاح بعد') and nums['price'][0] == '٩', '%s08: المصدر الواقع لازم «غير متاح بعد» لا صفر %r' % (pre, nums))
        expect('بعض الأرقام غير متاحة' in page.inner_text('.v2s-m4'), '%s08: شريط الأرقام الناقصة' % pre)
        mshot(page, pre + '08-down.jpg')
        go_sub_dir = page.click('.m4-tile[data-sub="firms"]')
        page.wait_for_timeout(600)
        expect('غير متاح بعد على المنصة' in page.inner_text('.v2s-m4'), '%s08: المكاتب والجسر ناقص %r' % (pre, page.inner_text('.v2s-m4')[:100]))
        browser.close()
        page = mopen(browser, h, m4fx.Market4Platform(empty=True), vp, mobile)
        nums = {s: (n, t) for s, n, t in tile_numbers(page)}
        expect(nums['sug'] == ('٠', 'لا شيء ينتظر') or nums['sug'][0] in ('٠', '—'), '%s08: الفاضي %r' % (pre, nums))
        page.click('.m4-tile[data-sub="sug"]')
        page.wait_for_function("() => document.querySelector('.m4-empty')", timeout=10000)
        expect('لا اقتراحات تنتظر' in page.inner_text('.v2s-m4'), '%s08: نص الفاضي' % pre)
        mshot(page, pre + '08b-empty.jpg')
        browser.close()


# ======================================================================= ٢ — بلاد القيد (طلب الانضمام)
def flow_licence(browser, h, pre, vp, mobile):
    if not want('06'):
        return
    ef = m4fx.Market4Platform()
    page = mopen(browser, h, ef, vp, mobile, hash_='#s/people/invites', ready=PEOPLE_READY)
    if mobile:
        click(page, '.v2d-segb[data-col="join"]', 300)
    # الطلب المرخَّص: «افتح وراجع» لا قبول بضغطة
    prim = page.evaluate("() => (document.querySelector('.v2p-t[data-id=\"join:jr-lic-1\"] [data-w=\"p\"]') || {}).textContent")
    expect((prim or '').strip() == 'افتح وراجع', '%s06: زرّ الطلب المرخَّص %r' % (pre, prim))
    plain = page.evaluate("() => (document.querySelector('.v2p-t[data-id=\"join:jr-plain\"] [data-w=\"p\"]') || {}).textContent")
    expect((plain or '').strip() == 'اقبل', '%s06: الطلب غير المرخَّص يبقى «اقبل» %r' % (pre, plain))
    base = len(h.platform_calls)
    click(page, '.v2p-t[data-id="join:jr-lic-1"] [data-w="p"]', 500)
    page.wait_for_selector('#epModal .m4-lic', timeout=10000)
    page.wait_for_timeout(300)
    st = page.evaluate("""() => ({checked: [...document.querySelectorAll('#epModal .m4-lic input:checked')].map(i => i.value), total: document.querySelectorAll('#epModal .m4-lic input[type=checkbox]').length,
      labels: [...document.querySelectorAll('#epModal .m4-lic-opt span')].map(s => s.textContent.trim()), info: document.querySelector('#epModal .m4-lic-info').textContent.trim(),
      view: !!document.getElementById('v2pmLView'), attach: document.querySelectorAll('#epModal .v2pm-files a').length})""")
    expect(st['checked'] == ['SA'] and st['total'] == 19 and st['labels'][-1] == 'أخرى' and st['labels'][:2] == ['مصر', 'السعودية'], '%s06: كتلة بلاد القيد %r' % (pre, st))
    expect(st['info'] == 'بلد القيد المكتوب في الطلب: السعودية، رقم القيد: ١٢٣٤٥' and st['view'] and st['attach'] == 0, '%s06: سطر الطلب وزرّ الملف %r' % (pre, st))
    mshot(page, pre + '06-licence-block.jpg', target='#epModal .m4-lic')
    # عرض ملف الترخيص
    n_calls = len(h.platform_calls)
    click(page, '#v2pmLView', 1000)
    page.wait_for_selector('#epModal .m4-lic-img', timeout=10000)
    src = page.evaluate("() => document.querySelector('#epModal .m4-lic-img').getAttribute('src')")
    nat = page.evaluate("() => document.querySelector('#epModal .m4-lic-img').naturalWidth")
    expect(src.startswith('data:image/png;base64,') and nat > 100, '%s06: الصورة data وبعرض %r' % (pre, (src[:30], nat)))
    files = [c for c in h.platform_calls[n_calls:] if '/licence-files/' in c[1]]
    expect(len(files) == 1 and files[0][0] == 'GET', '%s06: نداء الملف %r' % (pre, files))
    expect(page.evaluate("() => document.getElementById('v2pmLView').textContent.trim()") == 'أخفِ الملف', '%s06: نص الزرّ بعد العرض' % pre)
    mshot(page, pre + '06b-licence-viewer.jpg', target='#epModal .m4-lic')
    click(page, '#v2pmLView', 300)
    expect(page.evaluate("() => !document.querySelector('#epModal .m4-lic-img')"), '%s06: إخفاء الملف' % pre)
    check_writes(pre + '06-before-approve', h, base, 0)
    # اختيار بلدين ثم القبول
    page.check('#epModal .m4-lic-opt input[value="EG"]')
    page.wait_for_timeout(150)
    click(page, '#v2pmOk', 1200)
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    got = check_writes(pre + '06-approve', h, base, 1)
    if got:
        expect(got[0][1].endswith('/jr-lic-1/decide') and got[0][3].get('decision') == 'approve' and got[0][3].get('licensed_countries') == ['EG', 'SA'], '%s06: جسم القبول %r' % (pre, got[0][3]))
    browser.close()

    # قبول بلا بلد ⇒ منع، ثم «أخرى»، ثم رفض المنصة لبلد غلط
    ef = m4fx.Market4Platform()
    page = mopen(browser, h, ef, vp, mobile, hash_='#s/people/invites', ready=PEOPLE_READY)
    if mobile:
        click(page, '.v2d-segb[data-col="join"]', 300)
    base = len(h.platform_calls)
    click(page, '.v2p-t[data-id="join:jr-lic-2"] [data-w="p"]', 500)
    page.wait_for_selector('#epModal .m4-lic', timeout=10000)
    st = page.evaluate("() => ({checked: [...document.querySelectorAll('#epModal .m4-lic input:checked')].map(i => i.value), info: document.querySelector('#epModal .m4-lic-info').textContent.trim(), view: !!document.getElementById('v2pmLView')})")
    expect(st['checked'] == ['XX'] and 'قبرص' in st['info'] and not st['view'], '%s06: طلب «أخرى» بلا ملف %r' % (pre, st))
    page.uncheck('#epModal .m4-lic-opt input[value="XX"]')
    click(page, '#v2pmOk', 500)
    err = page.inner_text('#epModal .v2pm-err')
    expect('اختر بلد القيد' in err, '%s06: قبول بلا بلد ما اتمنعش %r' % (pre, err))
    check_writes(pre + '06-no-country', h, base, 0)
    mshot(page, pre + '06c-licence-required.jpg', target='#epModal .m4-lic')
    page.check('#epModal .m4-lic-opt input[value="XX"]')
    click(page, '#v2pmOk', 1200)
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    got = check_writes(pre + '06-approve-xx', h, base, 1)
    if got:
        expect(got[0][3].get('licensed_countries') == ['XX'], '%s06: جسم «أخرى» %r' % (pre, got[0][3]))
    browser.close()

    # الطلب غير المرخَّص: بلا كتلة، وقبول بلا licensed_countries
    ef = m4fx.Market4Platform()
    page = mopen(browser, h, ef, vp, mobile, hash_='#s/people/invites', ready=PEOPLE_READY)
    if mobile:
        click(page, '.v2d-segb[data-col="join"]', 300)
    base = len(h.platform_calls)
    click(page, '.v2p-t[data-id="join:jr-plain"] .v2p-strip', 500)
    page.wait_for_selector('#epModal .v2pm', timeout=10000)
    expect(page.evaluate("() => !document.querySelector('#epModal .m4-lic')"), '%s06: كتلة ترخيص على طلب غير مرخَّص' % pre)
    click(page, '#v2pmOk', 1200)
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    got = check_writes(pre + '06-plain', h, base, 1)
    if got:
        expect('licensed_countries' not in got[0][3], '%s06: بلاد قيد على طلب غير مرخَّص %r' % (pre, got[0][3]))
    browser.close()

    # بلد ترفضه المنصة ⇒ الطلب يفضل مفتوحًا وجملتها تظهر
    ef = m4fx.Market4Platform()
    ef.forced[('POST', '/api/bridge/join-requests/jr-lic-1/decide')] = (422, {'detail': 'بلد القيد غير مفهوم — اكتب رمز البلد (مثل EG أو SA)'})
    page = mopen(browser, h, ef, vp, mobile, hash_='#s/people/invites', ready=PEOPLE_READY)
    if mobile:
        click(page, '.v2d-segb[data-col="join"]', 300)
    click(page, '.v2p-t[data-id="join:jr-lic-1"] [data-w="p"]', 500)
    page.wait_for_selector('#epModal .m4-lic', timeout=10000)
    click(page, '#v2pmOk', 1000)
    expect('بلد القيد غير مفهوم' in page.inner_text('#epModal .v2pm-err'), '%s06: رفض المنصة ما ظهرش %r' % (pre, page.inner_text('#epModal .v2pm-err')))
    expect(page.evaluate("() => !!document.getElementById('epModal') && !document.getElementById('v2pmOk').disabled"), '%s06: الزرّ ما رجعش بعد الرفض' % pre)
    browser.close()


# ======================================================================= ٣ — سلّم السوق في جدول النسب
def flow_shares(browser, h, pre, vp, mobile):
    if not want('07'):
        return
    ef = m4fx.Market4Platform()
    tall = dict(vp, height=vp['height'] if mobile else 1500)
    h.ef = ef
    ctx = browser.context(h, 'admin', tall, mobile)
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح ظهرت: %s' % d.message[:60]), d.dismiss()))
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.goto(DASH + '/#s/money/shares', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function("() => document.querySelector('.v3[data-board=\"shares\"] .v3-mkt')", timeout=30000)
    page.wait_for_timeout(400)
    info = page.evaluate("""() => ({cur: [...document.querySelectorAll('.v3-mkc h4')].map(h => h.textContent.trim()), tiers: document.querySelector('.v3-mkc ul').innerText.replace(/\\s+/g, ' '),
      floor: document.querySelector('.v3-mkt small').textContent, btn: !!document.querySelector('[data-a=share][data-k=market]')})""")
    expect(info['cur'] == ['جنيه مصري', 'ريال سعودي', 'درهم إماراتي', 'ريال قطري', 'دينار كويتي', 'ريال عُماني', 'دولار أمريكي'] and info['btn'], '%s07: سلّم السوق %r' % (pre, info))
    expect('٢٥٪' in info['floor'] and 'أقل من ١٠٬٠٠٠' in info['tiers'] and 'المنصة ٣٥٪' in info['tiers'], '%s07: نص السلّم %r' % (pre, info))
    page.evaluate("() => document.querySelector('.v3-mkt').scrollIntoView({block: 'start'})")
    page.wait_for_timeout(250)
    vs.shot(page, pre + '07-shares-market.jpg', full=False)
    base = len(h.platform_calls)
    page.click('[data-a="share"][data-k="market"]')
    page.wait_for_selector('#epModal .v3-mkf', timeout=10000)
    expect(page.evaluate("() => document.querySelectorAll('#epModal .v3-mkf').length") == 7 and page.input_value('#v3_m_EGP_0_max') == '١٠٠٠٠' and page.input_value('#v3_m_EGP_1_pct') == '٣٠',
           '%s07: حقول الورقة بأرقام هندية' % pre)
    expect(page.evaluate("() => !document.getElementById('v3_m_EGP_2_max')"), '%s07: آخر درجة بلا سقف' % pre)
    # تحت الأرضية ⇒ رفض في الشاشة بلا نداء
    page.fill('#v3_m_EGP_2_pct', '٢٤')
    page.click('#v3_review')
    page.wait_for_timeout(300)
    expect('لا ينزل عن ٢٥٪' in page.inner_text('#v3err'), '%s07: الأرضية ما اتحرستش %r' % (pre, page.inner_text('#v3err')))
    check_writes(pre + '07-floor', h, base, 0)
    page.evaluate("() => document.querySelector('#epModal .v3-mkf').scrollIntoView({block: 'start'})")
    vs.shot(page, pre + '07b-shares-edit.jpg', full=False)
    page.fill('#v3_m_EGP_2_pct', '٢٥')
    page.fill('#v3_m_EGP_1_pct', '٢٨')
    page.fill('#v3_m_SAR_0_max', '800')
    page.click('#v3_review')
    page.wait_for_selector('#epModal #v3_go', timeout=10000)
    diff = page.inner_text('#epModal .v3-diff')
    expect('٣٠٪' in diff and '٢٨٪' in diff and '٨٠٠' in diff, '%s07: فرق السلّم %r' % (pre, diff))
    vs.shot(page, pre + '07c-shares-diff.jpg', full=False)
    check_writes(pre + '07-before-confirm', h, base, 0)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    got = check_writes(pre + '07-save', h, base, 1, with_confirm=True)
    if got:
        ch = got[0][3].get('changes') or {}
        lad = ((ch.get('market') or {}).get('ladder_by_currency')) or {}
        expect(sorted(lad) == ['EGP', 'SAR'] and lad['EGP'][1]['platform_pct'] == 28 and lad['SAR'][0]['max'] == 800 and set(ch) == {'market'} and got[0][3].get('version') == 3,
               '%s07: جسم النسب %r' % (pre, got[0][3]))
    page.wait_for_function("() => document.querySelector('.v3-log li')", timeout=10000)
    hist = page.evaluate("() => document.querySelector('.v3-log li').innerText.replace(/\\s+/g, ' ')")
    expect('السوق' in hist and '٢٨٪' in hist, '%s07: سجل التعديلات %r' % (pre, hist))
    browser.close()


# ======================================================================= ٤ — المفتاح مقفول
def flow_closed(browser, h, pre, vp, mobile):
    if not want('09'):
        return
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = m4fx.Market4Platform()
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#market', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.market === 'ready' && document.getElementById('view')", timeout=30000)
        st = page.evaluate("() => ({new: !!document.querySelector('.v2s-m4'), on: !!window.V2_ON})")
        expect(not st['new'] and not st['on'], '%s09: المفتاح مقفول وفيه أثر %r' % (pre, st))
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/market/suggestions', '/api/v2/market/catalog', '/api/v2/market/orgs', '/api/v2/market/licence-files/lf-3c9a41d2-7b05-4e88-a1f0']) {
            const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        expect(not bad, '%s09: مسارات السوق v4 والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(m4fx.Market4Platform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', DESK, False), ('m', MOB, True)):
                if pre not in os.environ.get('M4_VP', 'dm'):
                    continue
                flow_manage(browser, h, pre, vp, mobile)
                flow_licence(browser, h, pre, vp, mobile)
                flow_shares(browser, h, pre, vp, mobile)
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
