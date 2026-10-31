# -*- coding: utf-8 -*-
"""صور «العقل» الجولة ٢ — بطاقات رأي العقل وبطاقات اقتراحاته وشريط «ما كتبه العقل هنا» (P4، docs/v2/brain2/SPEC.md §4 و§5).

    cd backend && python3 -B tests/uiharness/v2_shots_brain2.py [out_dir] [only]     # only = أرقام اللقطات (مثلًا 01,05)
    FLOWS=flow_deck,flow_bars VPS=dm python3 -B tests/uiharness/v2_shots_brain2.py

كمبيوتر ١٤٤٠×٩٠٠ (`d`) · تابلت ٨٢٠×١١٨٠ (`t`) · موبايل ٣٩٠×٨٤٤ (`m`). ⛔ صفر شبكة: الداشبورد جوه العملية (`ef_route_harness`)، والمنصة جدول في الذاكرة
(`v2_fixtures.V2Platform`)، ومسارات `/api/v2/brain/*` الجديدة تُرَدّ من `brain2_fixtures.BrainBackend` داخل المتصفح. لا منفذ يُفتح ولا نداء ذكاء اصطناعي.

اللقطات: 01 بطاقة التركيز برأي العقل (مدرّب، والزر الأساسي «افتح الطلب» بعد التبديل) · 02 نزاع (نص فقط بلا تبديل) · 03 مسودة رد · 04 ورقة التعديل ·
05 ورقة الإرسال · 06 قفل بعد ردّ ضائع · 07 علامة الجملة الثابتة · 08 «يكتب العقل رأيه…» ثم الرأي · 09 شريط الناس · 10 الشريط موسّعًا ·
11 شريط المحتوى (ملاحظات) · 12 تذاكر الوارد برأي العقل · 13 تذاكر الناس برأي العقل.

السكربت بيفشل لو: تمرير أفقي (≤١٠٢٤) · هدف أقل من ٤٤px · حرف لاتيني أو صفر/null/undefined في نصوص العقل الجديدة · بريد/هاتف/مفتاح خارج القائمة المسموحة
في حقائق الرأي المُرسَلة · اعتماد بلا `confirmed:true` · كتابة غير مسارات العقل الجديدة · استثناء في الصفحة · أي طلب برّه الداشبورد.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
OUT_DIR = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else os.path.join(ROOT, 'docs', 'v2', 'brain2', 'shots-p4')
ONLY = set((sys.argv[2] if len(sys.argv) > 2 else '').split(',')) - {''}
sys.argv = [sys.argv[0], OUT_DIR]          # v2_shots بيقرأ OUT وقت الاستيراد
sys.path.insert(0, _HERE)

import v2_shots as vs                      # noqa: E402
import v2_fixtures as v2fx                 # noqa: E402
import brain2_fixtures as bf               # noqa: E402

PROBLEMS = vs.PROBLEMS
DESK = vs.DESK
TAB = {'width': 820, 'height': 1180}
MOB = vs.MOB
DASH = vs.DASH
BACKENDS = []

ALLOWED_KEYS = set('tag age sub warn reason static_line facts money_text objection expert_reply hours_held headline specialty years attachments '
                   'method dispute_check fx_alert type suggested_price price_note service licensed licence_missing body topic'.split())
NO_REPLY_TEXT = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
ZONES = '.v2b-bar, .v2b-src, #epModal .v2b-m, .v2-card[data-kind="brain_item"] .v2-brain, .v2-card[data-kind="brain_item"] .v2-acts'
APPLE = "() => window.V2BRAIN && V2BRAIN._state.P.state === 'ready'"


def want(name):
    return not ONLY or name[1:3] in ONLY


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def bcheck(page, name):
    """فحوص الجولة: لا تمرير أفقي (≤١٠٢٤) · أهداف ≥٤٤ · لا لاتيني ولا صفر/null في نصوص العقل الجديدة."""
    w = page.viewport_size['width']
    if w <= 1024:
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, sw, w))
        wide = page.evaluate("() => [...document.querySelectorAll('.v2b-bar *, #epModal .v2b-m *, .v2b-src')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
        if wide:
            PROBLEMS.append('%s: %d عنصر من العقل يخرج من عرض الشاشة' % (name, wide))
    tiny = page.evaluate("""() => [...document.querySelectorAll('.v2b-bar button, #epModal .v2b-m button, #epModal .v2b-m textarea')]
      .filter(b => b.offsetParent && !b.disabled).map(b => [b.className.toString().slice(0, 18) + ':' + (b.textContent || '').trim().slice(0, 14), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if tiny:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, tiny[:4]))
    txt = page.evaluate("(z) => [...document.querySelectorAll(z)].filter(e => e.offsetParent).map(e => e.innerText).join('\\n')", ZONES)
    if re.search(r'[A-Za-z]', txt):
        PROBLEMS.append('%s: حرف لاتيني في نصوص العقل: %r' % (name, re.findall(r'.{0,10}[A-Za-z]+.{0,10}', txt)[:2]))
    if re.search(r'(?<![\w٠-٩])(0|٠|null|undefined|NaN)(?![\w٠-٩])', txt):
        PROBLEMS.append('%s: صفر/null/undefined ظاهر في نصوص العقل: %r' % (name, re.findall(r'.{0,10}(?:null|undefined|NaN).{0,10}', txt)[:2]))
    for bad in ('يقوّم', 'اعكس', '⇒', '✓'):
        if bad in txt:
            PROBLEMS.append('%s: لفظ ممنوع «%s» في نصوص العقل' % (name, bad))


def bshot(page, name, full=False, scroll_to=None):
    if scroll_to:           # لقطة تذكرة في وسط القائمة: نُظهر السطر المطلوب بدل أعلى الصفحة
        page.evaluate("(sel) => { const e = document.querySelector(sel); if (e) e.scrollIntoView({block: 'center'}); }", scroll_to)
    else:
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    if want(name):
        vs.shot(page, name, full=full)
        try:
            vs.shell_check(page, name)
        except Exception as e:
            PROBLEMS.append('%s: shell_check %s' % (name, e))
    bcheck(page, name)


def watch(page, label):
    page.on('pageerror', lambda e: PROBLEMS.append('%s: استثناء في الصفحة: %s' % (label, str(e)[:160])))
    page.on('dialog', lambda d: (PROBLEMS.append('%s: نافذة متصفح %s' % (label, d.type)), d.dismiss()))


def open_page(ctx, hash_, label, ready=None):
    page = ctx.new_page()
    page.set_default_timeout(20000)
    watch(page, label)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    if ready:
        page.wait_for_function(ready, timeout=30000)
    page.wait_for_timeout(500)
    return page


def new_ctx(browser, h, vp, mobile, bk):
    h.ef = v2fx.V2Platform()
    BACKENDS.append(bk)
    ctx = browser.context(h, 'admin', vp, mobile)
    try:
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=DASH)
    except Exception:
        pass
    bk.install(ctx)
    return ctx


def start_deck(page):
    page.wait_for_function(APPLE, timeout=20000)
    page.wait_for_timeout(700)
    page.click('[data-a="start"]')
    page.wait_for_selector('.v2-card')


def focus(page, kind, where=None):
    vs.focus_on(page, kind, 0, where)


def facts_ok(bk, pre):
    """حقائق كل رأي أُرسل: لا بريد ولا هاتف ولا مفتاح خارج القائمة ولا جسم أكبر من ٣ كيلوبايت."""
    for body in bk.opinion_posts + [c for p in bk.lookup_posts for c in p.get('cards', [])]:
        f = body.get('facts') or {}
        blob = json.dumps(f, ensure_ascii=False)
        expect('@' not in blob, pre + ': بريد في حقائق الرأي: ' + blob[:120])
        expect(not re.search(r'(?:\d[\s\-().]*){7,}', blob.replace('٠', '0').translate(str.maketrans('١٢٣٤٥٦٧٨٩', '123456789'))), pre + ': رقم هاتف في حقائق الرأي: ' + blob[:120])
        extra = set(f) - ALLOWED_KEYS
        expect(not extra, pre + ': مفاتيح خارج القائمة: %r' % extra)
        expect(len(blob.encode('utf-8')) <= 3072, pre + ': حقائق أكبر من ٣ كيلوبايت')
        expect(body.get('kind') and body.get('card_id'), pre + ': جسم بلا kind أو card_id')


# ======================================================================= ١) بطاقة التركيز
def flow_deck(browser, h, pre, vp, mobile):
    bk = bf.BrainBackend('ready')
    ctx = new_ctx(browser, h, vp, mobile, bk)
    page = open_page(ctx, '', pre + 'deck')
    start_deck(page)
    # مدرّب: الرأي «افتح» ⇒ الزر الأساسي هو الفتح (بدّل بين زرّين قائمين فقط)
    focus(page, 'trainer')
    page.wait_for_selector('.v2-card .v2b-src.ai', timeout=15000)
    lab = page.evaluate("() => [document.querySelector('[data-a=\"primary\"]').textContent.trim(), (document.querySelector('[data-a=\"secondary\"]') || {}).textContent]")
    expect(lab[0] == 'افتح الطلب' and (lab[1] or '').strip() == 'اقبل الطلب', pre + '01: الزر الأساسي بعد التبديل %r' % lab)
    src = page.inner_text('.v2-card .v2b-src.ai')
    expect(src.startswith('كتبه العقل'), pre + '01: سطر المصدر «%s»' % src)
    expect(page.inner_text('.v2-brain b') == 'رأي العقل', pre + '01: عنوان الصندوق')
    bshot(page, pre + '01-deck-opinion-trainer.jpg')
    # نزاع: نص فقط، لا تبديل للأزرار
    focus(page, 'dispute')
    page.wait_for_selector('.v2-card .v2b-src.ai', timeout=15000)
    lab = page.inner_text('[data-a="primary"]')
    expect(lab.strip() == 'افتح النزاع', pre + '02: زر النزاع تغيّر إلى «%s»' % lab)
    bshot(page, pre + '02-deck-opinion-dispute.jpg')
    # مسودة رد: اعتمد/عدّل/ارفض
    focus(page, 'brain_item', 'rd_member')
    page.wait_for_timeout(200)
    btn = page.evaluate("() => [...document.querySelectorAll('.v2-acts button')].map(b => b.textContent.trim())")
    expect(btn[:3] == ['أرسل الرد', 'ارفض', 'عدّل'], pre + '03: أزرار المسودة %r' % btn)
    expect(page.inner_text('.v2-brain b') == 'ما كتبه العقل', pre + '03: عنوان صندوق المسودة')
    bshot(page, pre + '03-deck-reply-draft.jpg')
    # ورقة الإرسال (عضو) ثم التأكيد: confirmed:true بلا نص
    page.click('[data-a="primary"]')
    page.wait_for_selector('#epModal .v2b-m')
    sheet = page.inner_text('#epModal')
    expect('إرسال الرد' in sheet and 'يصل هذا الرد إلى صاحب الرسالة إشعارًا داخل المنصة.' in sheet, pre + '05: نص ورقة الإرسال %r' % sheet[:200])
    expect('نعم، أرسله' in sheet and 'رجوع' in sheet, pre + '05: أزرار الورقة')
    bshot(page, pre + '05-send-sheet.jpg')
    n0 = len(bk.writes)
    page.click('#v2b_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(500)
    expect(len(bk.writes) == n0 + 1 and bk.writes[-1] == ('/api/v2/brain/items/rd_member/approve', {'confirmed': True}), pre + '05: جسم الاعتماد %r' % bk.writes[n0:])
    expect('rd_member' not in page.evaluate("() => JSON.stringify(V2._state.deck.map(c => c.id))"), pre + '05: البطاقة ما زالت في الطابور بعد الاعتماد')
    # تعديل مسودة موقع: النص المعدَّل يُرسل وينسخ
    focus(page, 'brain_item', 'rd_site')
    page.click('[data-a="edit"]')
    page.wait_for_selector('#epModal #v2b_t')
    sheet = page.inner_text('#epModal')
    expect('يُحفظ الرد هنا ويُنسخ لترسله بنفسك. لا يُرسل بريد من اللوحة بعد.' in sheet, pre + '04: نص ورقة الموقع')
    expect('بريد' in sheet and 'أُرسل' not in sheet, pre + '04: ادعاء إرسال بريد')
    page.wait_for_function("() => !document.querySelector('.toast')", timeout=8000)      # توست الاعتماد السابق لا يغطّي الورقة في اللقطة
    bshot(page, pre + '04-edit-sheet.jpg')
    new_text = 'نعتذر عن هذا الإزعاج، وسنراجع الأمر ونوافيكم بالنتيجة.'
    page.fill('#v2b_t', new_text)
    n0 = len(bk.writes)
    page.click('#v2b_go')
    page.wait_for_function("() => !document.getElementById('epModal') || document.querySelector('#epModal .v2b-ta[readonly]')", timeout=15000)
    page.wait_for_timeout(500)
    expect(bk.writes[n0:] == [('/api/v2/brain/items/rd_site/approve', {'confirmed': True, 'text': new_text})], pre + '04: جسم التعديل %r' % bk.writes[n0:])
    toast = page.evaluate("() => [...document.querySelectorAll('.toast')].map(t => t.textContent).join('|')")
    fallback = page.evaluate("() => !!document.querySelector('#epModal .v2b-ta[readonly]')")
    expect('نُسخ النص' in toast or fallback, pre + '04: لا توست «نُسخ النص» ولا بديل النسخ: %r' % toast)
    if 'نُسخ النص' in toast:
        try:
            got = page.evaluate("() => navigator.clipboard.readText()")
            expect(got == new_text, pre + '04: الحافظة %r' % got)
        except Exception:
            pass
    if fallback:
        page.click('#v2b_x')
    # ردّ ضائع: تُقفل البطاقة بالنص المطلوب
    bk.apply['rd_lead'] = ('no_reply',)
    focus(page, 'brain_item', 'rd_lead')
    page.click('[data-a="primary"]')
    page.wait_for_selector('#epModal .v2b-m')
    page.click('#v2b_go')
    page.wait_for_selector('#epModal .v2b-err', timeout=10000)
    expect(NO_REPLY_TEXT in page.inner_text('#epModal .v2b-err'), pre + '06: نص الردّ الضائع في الورقة')
    bshot(page, pre + '06-noreply-sheet.jpg')
    page.click('#v2b_x')
    page.wait_for_function("() => !document.getElementById('epModal')")
    page.wait_for_timeout(300)
    locked = page.evaluate("() => [(document.querySelector('.v2-err') || {}).textContent, (document.querySelector('[data-a=\"refresh\"]') || {}).textContent]")
    expect(NO_REPLY_TEXT in (locked[0] or '') and (locked[1] or '').strip() == 'حدّث الآن', pre + '06: قفل البطاقة بعد الردّ الضائع %r' % locked)
    facts_ok(bk, pre + 'deck')
    for path, body in bk.writes:
        expect(body.get('confirmed') is True, pre + ': كتابة بلا confirmed:true ' + path)


# ======================================================================= ٢) العلامات والتحميل
def flow_marks(browser, h, pre, vp, mobile):
    bk = bf.BrainBackend('fail')
    ctx = new_ctx(browser, h, vp, mobile, bk)
    page = open_page(ctx, '', pre + 'marks')
    start_deck(page)
    focus(page, 'trainer')
    page.wait_for_selector('.v2-card .v2b-src.static', timeout=15000)
    expect(page.inner_text('.v2-card .v2b-src') == 'جملة ثابتة: تعذّرت كتابة رأي العقل الآن', pre + '07: علامة العطل')
    expect(page.inner_text('.v2-brain b') == 'اقتراح العقل' or page.inner_text('.v2-brain b') == 'ما يراه العقل', pre + '07: عنوان الجملة الثابتة تغيّر')
    expect('اقبل' in page.inner_text('[data-a="primary"]'), pre + '07: الزر الأساسي تغيّر بدون رأي')
    bshot(page, pre + '07-deck-failed-mark.jpg')
    bk.mode = 'cap'
    focus(page, 'pending_user')
    page.wait_for_selector('.v2-card .v2b-src.static', timeout=15000)
    expect(page.inner_text('.v2-card .v2b-src') == 'جملة ثابتة: بلغ العقل حدّ كتابته اليوم', pre + '07: علامة الحد')
    bk.mode = 'off'
    focus(page, 'review')
    page.wait_for_selector('.v2-card .v2b-src.static', timeout=15000)
    expect(page.inner_text('.v2-card .v2b-src') == 'جملة ثابتة: رأي العقل متوقّف من القواعد', pre + '07: علامة التوقف')
    # الاستقصاء: queued ⇒ «يكتب العقل رأيه…» ثم الرأي بعد استعلامات lookup (بطاقة واحدة في كل استعلام)
    bk2 = bf.BrainBackend('queued', polls_before_ready=2)
    ctx2 = new_ctx(browser, h, vp, mobile, bk2)
    page2 = open_page(ctx2, '', pre + 'queued')
    start_deck(page2)
    focus(page2, 'trainer')
    page2.wait_for_selector('.v2-card .v2b-src.wait', timeout=15000)
    expect(page2.inner_text('.v2-card .v2b-src') == 'يكتب العقل رأيه…', pre + '08: نص التحميل')
    bshot(page2, pre + '08-deck-loading.jpg')
    page2.wait_for_selector('.v2-card .v2b-src.ai', timeout=30000)
    polls = [p for p in bk2.lookup_posts if len(p.get('cards', [])) == 1 and p['cards'][0]['kind'] == 'trainer']
    expect(2 <= len(polls) <= 20, pre + '08: عدد استعلامات الاستقصاء %d' % len(polls))
    expect(len(bk2.opinion_posts) == 1 or len([p for p in bk2.opinion_posts if p['kind'] == 'trainer']) == 1, pre + '08: طُلب الرأي أكثر من مرة')
    bshot(page2, pre + '08b-deck-after-poll.jpg')
    facts_ok(bk, pre + 'marks')
    facts_ok(bk2, pre + 'queued')


# ======================================================================= ٣) الشريط
def flow_bars(browser, h, pre, vp, mobile):
    bk = bf.BrainBackend('ready')
    ctx = new_ctx(browser, h, vp, mobile, bk)
    page = open_page(ctx, '#s/people/invites', pre + 'bars', "() => document.querySelector('.v2p[data-tab=\"requests\"]') && !document.querySelector('.v2p .v2p-sk')")
    page.wait_for_selector('#v2bbar .v2b-bar', timeout=20000)
    info = page.evaluate("""() => ({n: document.querySelectorAll('#v2bbar .v2b-c').length, all: (document.querySelector('#v2bbar .v2b-all') || {}).textContent,
      head: document.querySelector('#v2bbar .v2b-h b').textContent, hidden: document.getElementById('v2bbar').hidden,
      order: [...document.querySelectorAll('#v2bbar, #v2sbar, #view')].map(e => e.id)})""")
    expect(info['n'] == 3 and (info['all'] or '').strip() == 'اعرض الكل (٤)' and info['head'] == 'ما كتبه العقل هنا', pre + '09: الشريط %r' % info)
    expect(info['order'] == ['v2sbar', 'v2bbar', 'view'], pre + '09: ترتيب الحاويات %r' % info['order'])
    bshot(page, pre + '09-bar-people.jpg')
    page.click('#v2bbar .v2b-all')
    page.wait_for_function("() => document.querySelectorAll('#v2bbar .v2b-c').length === 4")
    bshot(page, pre + '10-bar-people-all.jpg')
    # رفض من الشريط: ورقة ثم confirmed:true، ثم يبقى ٣ ولا زر «اعرض الكل»
    page.click('#v2bbar .v2b-c[data-id="rd_lead"] [data-a="brain_reject"]')
    page.wait_for_selector('#epModal .v2b-m')
    expect('يُرفض هذا الاقتراح ولا يُنفَّذ شيء.' in page.inner_text('#epModal'), pre + '10: نص ورقة الرفض')
    n0 = len(bk.writes)
    page.click('#v2b_go')
    page.wait_for_function("() => !document.getElementById('epModal') && document.querySelectorAll('#v2bbar .v2b-c').length === 3", timeout=15000)
    expect(bk.writes[n0:] == [('/api/v2/brain/items/rd_lead/reject', {'confirmed': True})], pre + '10: جسم الرفض %r' % bk.writes[n0:])
    expect(page.evaluate("() => !document.querySelector('#v2bbar .v2b-all')"), pre + '10: زر الكل ظل بعد النزول إلى ٣')
    # المحتوى: ملاحظتان «احتفظ بها/احذفها»
    page.evaluate("() => { location.hash = '#s/content/pipeline'; }")
    page.wait_for_function("() => document.querySelectorAll('#v2bbar .v2b-c').length === 2 && !document.getElementById('v2bbar').hidden", timeout=20000)
    page.wait_for_timeout(500)
    btns = page.evaluate("() => [...document.querySelectorAll('#v2bbar .v2b-c:first-child button')].map(b => b.textContent.trim())")
    expect(btns == ['احتفظ بها', 'احذفها'], pre + '11: أزرار الملاحظة %r' % btns)
    bshot(page, pre + '11-bar-content.jpg')
    page.click('#v2bbar .v2b-c:first-child [data-a="brain_reject"]')
    page.wait_for_selector('#epModal .v2b-m')
    expect('تُحذف هذه الملاحظة. لم تغيّر شيئًا في المنصة.' in page.inner_text('#epModal'), pre + '11: نص حذف الملاحظة')
    page.click('#v2b_x')
    # مخفي في اللوحة والعقل
    for hash_, nm in (('#s/home/board', 'home'), ('#s/brain/log', 'brain')):
        page.evaluate("(h) => { location.hash = h; }", hash_)
        page.wait_for_timeout(900)
        expect(page.evaluate("() => document.getElementById('v2bbar').hidden"), pre + '12: الشريط ظاهر في ' + nm)
    for path, body in bk.writes:
        expect(body.get('confirmed') is True, pre + ': كتابة بلا confirmed:true ' + path)


# ======================================================================= ٤) التذاكر
def flow_tickets(browser, h, pre, vp, mobile):
    bk = bf.BrainBackend('ready', lookup_fill=True)
    ctx = new_ctx(browser, h, vp, mobile, bk)
    page = open_page(ctx, '#s/home/inbox', pre + 'tickets', "() => document.querySelector('.v2h-t')")
    page.wait_for_timeout(1500)
    if mobile:          # الموبايل يعرض مقطعًا واحدًا: نمرّ على المقاطع حتى نجد تذكرة برأي العقل
        for i in range(page.locator('.v2h-segb').count()):
            if page.query_selector('.v2h-brain .v2b-src.ai'):
                break
            page.locator('.v2h-segb').nth(i).click()
            page.wait_for_timeout(600)
    page.wait_for_selector('.v2h-brain .v2b-src.ai', timeout=20000)
    expect(page.inner_text('.v2h-brain .v2b-src.ai').startswith('كتبه العقل'), pre + '12: سطر المصدر في التذكرة')
    n = page.evaluate("() => [...document.querySelectorAll('.v2h-t')].map(t => t.querySelectorAll('.v2h-btn1').length).filter(x => x !== 1).length")
    expect(n == 0, pre + '12: تذكرة بلا زر رئيسي واحد')
    lk = [p for p in bk.lookup_posts if p.get('cards')]
    expect(len(lk) >= 1 and len(lk[0]['cards']) <= 40, pre + '12: نداء lookup واحد للتذاكر')
    expect(not bk.opinion_posts, pre + '12: التذاكر طلبت رأيًا جديدًا (يجب lookup فقط)')
    bshot(page, pre + '12-tickets-inbox.jpg', scroll_to='.v2h-brain .v2b-src.ai')
    page.evaluate("() => { location.hash = '#s/people/invites'; }")
    page.wait_for_function("() => document.querySelector('.v2p[data-tab=\"requests\"]') && !document.querySelector('.v2p .v2p-sk')", timeout=20000)
    page.wait_for_selector('.v2p-body > .v2b-src.ai', timeout=20000)
    bshot(page, pre + '13-tickets-people.jpg', scroll_to='.v2p-body > .v2b-src.ai')
    facts_ok(bk, pre + 'tickets')


# ======================================================================= ٥) المقفول والعطل: لا أثر
def flow_degrade(browser, h, pre, vp, mobile):
    bk = bf.BrainBackend('closed')
    ctx = new_ctx(browser, h, vp, mobile, bk)
    page = open_page(ctx, '', pre + 'closed')
    page.wait_for_timeout(1200)
    page.click('[data-a="start"]')
    page.wait_for_selector('.v2-card')
    focus(page, 'trainer')
    page.wait_for_timeout(1000)
    marks = page.evaluate("() => document.querySelectorAll('.v2b-src').length")
    expect(marks == 0, pre + '14: علامة ظهرت والخادم لا يعرف المسار (%d)' % marks)
    expect('اقبل' in page.inner_text('[data-a="primary"]'), pre + '14: الزر الأساسي تغيّر')
    page.evaluate("() => { location.hash = '#s/people/invites'; }")
    page.wait_for_timeout(1500)
    expect(page.evaluate("() => document.getElementById('v2bbar').hidden"), pre + '14: الشريط ظاهر والخادم لا يعرف المسار')


FLOWS = [flow_deck, flow_marks, flow_bars, flow_tickets, flow_degrade]


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = vs.Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            only_flows = set((os.environ.get('FLOWS') or '').split(',')) - {''}
            only_vps = os.environ.get('VPS') or 'dtm'
            for fl in FLOWS:
                if only_flows and fl.__name__ not in only_flows:
                    continue
                for pre, vp, mobile in (('d', DESK, False), ('t', TAB, False), ('m', MOB, True)):
                    if pre not in only_vps:
                        continue
                    try:
                        fl(browser, h, pre, vp, mobile)
                    except Exception as e:            # فشل خطوة لا يوقف بقية الفحوص — يُسجَّل ويكمل
                        import traceback
                        PROBLEMS.append('%s %s: استثناء %s' % (fl.__name__, pre, str(e).split(chr(10))[0][:200]))
                        traceback.print_exc(limit=4)
                        browser.close()
        finally:
            browser.close()
    # ولا كتابة وصلت للداشبورد نفسه من هذه اللقطات: كل كتابات العقل ردّتها الأداة الوهمية.
    writes = [c for c in h.dash_calls if c[0] in ('POST', 'PUT', 'PATCH', 'DELETE')]
    if writes:
        PROBLEMS.append('كتابات وصلت للداشبورد: %r' % writes[:5])
    rep = h.blocked_report()
    print(json.dumps({'out': OUT_DIR, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
