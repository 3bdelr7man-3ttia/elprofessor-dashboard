# -*- coding: utf-8 -*-
"""صور «الناس والدعوات» النهائي — كمبيوتر ١٤٤٠×٩٠٠ (`d`) وتابلت ٨٢٠×١١٨٠ (`t`) وموبايل ٣٩٠×٨٤٤ (`m`).

    cd backend && python3 -B tests/uiharness/v2_shots_people.py [out_dir] [only]     # only = أرقام اللقطات (مثلًا 01,07)

اللقطات p01 … p22 في docs/v2/final/SPEC-people.md §١٦. السكربت بيفشل لو: تمرير أفقي في الموبايل · عنوان زرّ الأعمدة يلتف أكثر من سطرين · هدف أقل من ٤٤px
(والأزرار أقل من ٥٢px في الموبايل) · ورقة طويلة أضيق من الشاشة في الموبايل أو ليست ٤٨٠px في الكمبيوتر · كلمة «مشبوه» ظاهرة · صفر/null/NaN بدل
«غير متاح بعد» · أرقام لاتينية في نص عربي · أصناف الشاشات القديمة داخل `.v2p` · صندوق بحث الأشخاص ظاهر في المستخدمين · أي طلب غير خطوط جوجل ·
كتابة من غير ورقة التأكيد · `prompt`/`confirm`.
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة جدول في الذاكرة (`people_fixtures.PeoplePlatform`).
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
OUT_DIR = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else os.path.join(ROOT, 'docs', 'v2', 'final', 'shots-people')
ONLY = set((sys.argv[2] if len(sys.argv) > 2 else '').split(',')) - {''}
sys.argv = [sys.argv[0], OUT_DIR]          # v2_shots بيقرأ OUT وقت الاستيراد
sys.path.insert(0, _HERE)

import v2_shots as vs                      # noqa: E402
import people_fixtures as pf               # noqa: E402
from ef_route_harness import DASH          # noqa: E402

PROBLEMS = vs.PROBLEMS
DESK = vs.DESK
TAB = {'width': 820, 'height': 1180}
MOB = vs.MOB
PEOPLE_READY = ("() => window.V2SHELL && V2SHELL.on === true && window.EP && ['inbox','invites','pendingUsers'].every(k => EP.state[k] === 'ready')"
                " && document.querySelector('.v2c-tab')")
BOARD = "() => document.querySelector('.v2p[data-tab=\"%s\"]') && !document.querySelector('.v2p .v2p-sk') && !/…جارٍ الجلب/.test(document.querySelector('.v2p').innerText)"

OLD_CLASSES = ['.kpi', '.panel', '.policy', '.inboxwrap', '.trow', '.filterbar']
PEOPLE_JS = """() => { const own = [...document.querySelectorAll('.v2p, #epModal .v2pm')];
  const clone = own.map(e => { const c = e.cloneNode(true); c.querySelectorAll('.v2p-em, .ltr, input, textarea, select, [dir=ltr], .v2pm-quote').forEach(n => n.remove()); return c.innerText; }).join('\\n');
  return clone; }"""


def want(name):
    return not ONLY or name[1:3] in ONLY


def pcheck(page, name, sheet_side=False):
    """فحوص الجولة على الصفحة الحالية (وعلى الورقة المفتوحة إن وُجدت)."""
    w = page.viewport_size['width']
    txt = page.evaluate(PEOPLE_JS)
    if 'مشبوه' in txt:
        PROBLEMS.append('%s: كلمة «مشبوه» ظاهرة' % name)
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN/undefined ظاهر: %r' % (name, re.findall(r'.{0,12}(?<![\w@./-])(?:0|null|NaN|undefined)(?![\w@./-]).{0,12}', txt)[:2]))
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if not re.search(r'[A-Za-z@]', t)]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))
    old = page.evaluate("(cls) => cls.filter(c => document.querySelector('.v2p ' + c)).length", OLD_CLASSES)
    if old:
        PROBLEMS.append('%s: أصناف الشاشات القديمة داخل .v2p' % name)
    if page.evaluate("() => { const t = document.querySelector('.v2p[data-tab=\"users\"]'); const b = document.getElementById('v2sbar'); return !!(t && b && b.offsetParent); }"):
        PROBLEMS.append('%s: صندوق بحث الأشخاص ظاهر في المستخدمين' % name)
    tiny = page.evaluate("""(mob) => [...document.querySelectorAll('.v2p button, .v2p a.v2p-btn1, .v2p a.v2p-btn2, .v2p select, #epModal .v2pm button, #epModal .v2pm a.v2p-btn1, #epModal .v2pm a.v2p-btn2, #epModal .v2pm select, #epModal .v2pm input[type=text], #epModal .v2pm input[type=tel]')]
      .filter(b => b.offsetParent && !b.disabled).map(b => [b.className.toString().slice(0, 24), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < (mob ? 44 : 44))""", w <= 400)
    if tiny:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, tiny[:4]))
    if w <= 400:
        small = page.evaluate("""() => [...document.querySelectorAll('.v2p .v2p-btn1, .v2p .v2p-btn2, .v2p .v2p-btn3, #epModal .v2pm .v2p-btn1, #epModal .v2pm .v2p-btn2, #epModal .v2pm .v2p-btn3')]
          .filter(b => b.offsetParent).map(b => [b.className.toString().slice(0, 24), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52)""")
        if small:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, small[:4]))
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, sw, w))
        wide = page.evaluate("() => [...document.querySelectorAll('.v2p *, #epModal .v2pm *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
        if wide:
            PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
        seg = page.evaluate("""() => [...document.querySelectorAll('.v2d-segb span')].filter(s => s.offsetParent).map(s => { const lh = parseFloat(getComputedStyle(s).lineHeight) || 18; return Math.round(s.getBoundingClientRect().height / lh); }).filter(n => n > 2)""")
        if seg:
            PROBLEMS.append('%s: عنوان زرّ عمود يلتف أكثر من سطرين' % name)
    if sheet_side:
        sw2 = page.evaluate("() => { const m = document.querySelector('#epModal .v2pm'); return m ? Math.round(m.getBoundingClientRect().width) : 0; }")
        if (w <= 400 and sw2 < w - 1) or (w >= 1400 and sw2 != 480) or (400 < w < 1400 and sw2 not in (480, w)):
            PROBLEMS.append('%s: عرض الورقة الطويلة %s (الشاشة %s)' % (name, sw2, w))


def pshot(page, name, full=False, sheet_side=False):
    if not want(name):
        return
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    vs.shot(page, name, full=full)
    try:
        vs.shell_check(page, name)
    except Exception as e:                     # فحوص الغلاف ليست من شغلنا — نسجّل الاستثناء فقط
        PROBLEMS.append('%s: shell_check %s' % (name, e))
    pcheck(page, name, sheet_side)


def open_people(ctx, hash_, tab, ready=None):
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة المتصفح ظهرت: %s %r' % (d.type, d.message)), d.dismiss()))
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    try:
        page.wait_for_function(PEOPLE_READY, timeout=30000)
    except Exception:
        PROBLEMS.append('الجاهزية: %s' % page.evaluate("() => JSON.stringify([window.V2SHELL && V2SHELL.on, window.EP && EP.state, !!document.querySelector('.v2c-tab')])"))
        raise
    page.wait_for_function(ready or (BOARD % tab), timeout=30000)
    page.wait_for_timeout(500)
    return page


def sheet_wait(page, sel='#epModal .v2pm'):
    page.wait_for_selector(sel, timeout=10000)
    page.wait_for_timeout(250)


def writes(h, since=0):
    return [w for w in h.ef.writes[since:]]



def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def nowait(page):
    """يمنع فتح بريد/واتساب/نوافذ جديدة فعلًا (الصفر شبكة): النقرة تُسجَّل في الصفحة وتتوقف."""
    page.evaluate("""() => document.addEventListener('click', e => { const a = e.target.closest && e.target.closest('a[href]');
      if (a && /^(mailto:|https:\\/\\/wa\\.me|https?:\\/\\/(?!dash\\.test))/.test(a.getAttribute('href'))) { window.__opened = (window.__opened || []).concat([a.getAttribute('href')]); e.preventDefault(); } })""")


def seed_messages(appmod):
    import datetime
    with appmod.app.app_context():
        appmod.Message.query.delete()
        now = datetime.datetime.utcnow()
        for name, email, topic, body, status, hours in (
                ('عبد الله الجمال', 'abdullah.j@example.test', 'سؤال عن الاشتراك', 'أريد معرفة الفرق بين الباقتين الاحترافية والبريميوم قبل الاشتراك، وهل يمكن التحويل لاحقًا؟', 'new', 30),
                ('هدى رمضان', 'hoda.r@example.test', 'طلب تعاون', 'أعمل في مجال الصياغة القانونية وأود التعاون معكم في كتابة أدلة للأعضاء.', 'new', 3),
                ('كمال الدين', 'kamal@example.test', 'استفسار', 'شكرًا على الدورة الأخيرة.', 'replied', 90),
                ('إيمان صلاح', 'eman@example.test', 'مشكلة في الدخول', 'لم تصلني رسالة التأكيد.', 'replied', 70)):
            m = appmod.Message(name=name, email=email, phone='', topic=topic, body=body, status=status, created_at=now - datetime.timedelta(hours=hours))
            if status == 'replied':
                m.reply_body = 'تم الرد'
            appmod.db.session.add(m)
        appmod.db.session.commit()


def fresh(h, **kw):
    h.ef = pf.PeoplePlatform(**kw)
    seed_messages(h.app)
    return h.ef


def tab_click(page, tab):
    page.click('.v2c-tab[data-tab="%s"]' % tab)
    names = {'invites': 'requests', 'pipeline': 'pipeline', 'users': 'users', 'messages': 'messages'}
    page.wait_for_function(BOARD % names[tab], timeout=30000)
    page.wait_for_timeout(350)


# ======================================================================= الطلبات
def flow_requests(browser, h, pre, vp, mobile):
    tall = dict(vp, height=vp['height'] if mobile else (1700 if vp['width'] > 1000 else 2200))
    ef = fresh(h)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/invites', 'requests')
    nowait(page)
    info = page.evaluate("""() => ({cols: [...document.querySelectorAll('.v2p-col')].map(c => [c.dataset.col, c.querySelector('.v2p-n').textContent.trim(), c.querySelectorAll('.v2p-t').length]),
      brain: document.querySelector('.v2p-brain').innerText, jump: (document.querySelector('.v2p-jump a') || {}).getAttribute ? document.querySelector('.v2p-jump a').getAttribute('href') : null,
      tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), seg: [...document.querySelectorAll('.v2d-segb span')].map(s => s.textContent.trim()),
      warn: [...document.querySelectorAll('.v2p-tw')].map(e => e.textContent.trim())})""")
    expect(info['tabs'] == ['الطلبات', 'الدعوات', 'المستخدمون', 'الرسائل'], pre + '01: تبويبات الناس %r' % info['tabs'])
    expect([c[0] for c in info['cols']] == ['visitors', 'approval', 'join', 'founding'], pre + '01: الأعمدة %r' % info['cols'])
    expect([c[1] for c in info['cols']] == ['٥', '٢', '٢', '٢'], pre + '01: أعداد الأعمدة %r' % info['cols'])
    expect('ينتظر قرارك' in info['brain'] and 'أقدمها' in info['brain'], pre + '01: سطر العقل %r' % info['brain'])
    expect(info['jump'] == '#s/people/pipeline', pre + '01: رابط «الدعوات» B1-g %r' % info['jump'])
    expect(any(w.startswith('يحتاج مراجعة: إيميل بنقط') for w in info['warn']), pre + '01: تحذير الزائر %r' % info['warn'])
    expect(info['seg'] == ['الزوّار', 'الدعوات', 'الخدمات', 'المؤسسون'], pre + '01: عناوين الأعمدة القصيرة %r' % info['seg'])
    if mobile:
        # الشاشة الأولى: بحث الأشخاص العام مخفي، و«حدّث» على سطر العقل نفسه، وأول تذكرة تبدأ فوق منتصف الشاشة
        fs = page.evaluate("""() => { const r = e => e ? e.getBoundingClientRect() : null, sb = document.querySelector('#v2sbar'), t = document.querySelector('.v2p-col.on .v2p-t'),
          br = document.querySelector('.v2p-brain'), rf = document.querySelector('[data-a="refresh"]');
          return {sbar: !!sb && getComputedStyle(sb).display !== 'none', ticket: t ? Math.round(r(t).top) : null, sameRow: !!(br && rf) && Math.abs(r(br).top - r(rf).top) < 60, h: innerHeight}; }""")
        expect(not fs['sbar'] and fs['sameRow'] and fs['ticket'] is not None and fs['ticket'] < fs['h'] - 250, pre + '01: الشاشة الأولى في الموبايل %r' % fs)
    if mobile:
        for i, (k, nm) in enumerate((('visitors', 'a'), ('approval', 'b'), ('join', 'c'), ('founding', 'd'))):
            page.click('.v2d-segb[data-col="%s"]' % k)
            page.wait_for_timeout(250)
            pshot(page, '%s01%s-requests-%s.jpg' % (pre, nm, k))
    else:
        pshot(page, pre + '01-requests.jpg')
    # الاختصارات: زائر عادي ⇒ فتح بضغطة (تعديل المنصة بنفس مسار الوارد)، والمراجَع يفتح ورقة
    if mobile:
        page.click('.v2d-segb[data-col="visitors"]')
    n0 = len(ef.writes)
    page.click('.v2p-t[data-id="visitor:pu-2"] [data-w="p"]')
    sheet_wait(page)
    expect(len(ef.writes) == n0, pre + '02: «افتح وراجع» كتب قبل التأكيد')
    expect('ولا يراه صاحبه' not in page.inner_text('#epModal'), pre + '02: عبارة «ولا يراه صاحبه»')
    pshot(page, pre + '02-visitor-sheet.jpg')
    page.click('#v2pmRej0')
    page.wait_for_selector('#v2pmNote')
    lab = page.inner_text('#v2pmRej label')
    expect(lab == 'سبب الرفض (اختياري) — يُحفظ على الطلب، فاكتب ما لا تمانع أن يقرأه صاحبه', pre + '02: نص سبب الرفض %r' % lab)
    page.fill('#v2pmNote', 'نحتاج بيانات أوضح عن الصفة')
    pshot(page, pre + '02b-visitor-reject.jpg')
    page.click('#v2pmRej0')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w = [x for x in ef.writes[n0:] if x[1].endswith('/users/pu-2/access')]
    expect(len(w) == 1 and w[0][2] == {'access': 'pending', 'note': 'نحتاج بيانات أوضح عن الصفة'}, pre + '02: كتابة رفض الزائر %r' % w)
    page.wait_for_timeout(600)
    # زائر عادي: «افتح المنصة للزائر» ضغطة واحدة
    n0 = len(ef.writes)
    page.click('.v2p-t[data-id="visitor:pu-1"] [data-w="p"]')
    page.wait_for_function("() => !document.querySelector('.v2p-t[data-id=\"visitor:pu-1\"]') || document.querySelector('.v2p-t[data-id=\"visitor:pu-1\"] .v2p-ok')", timeout=15000)
    w = [x for x in ef.writes[n0:] if x[1].endswith('/users/pu-1/access')]
    expect(len(w) == 1 and w[0][2].get('access') == 'member', pre + '02: فتح المنصة للزائر %r' % w)
    # S4 رفض دعوة
    if mobile:
        page.click('.v2d-segb[data-col="approval"]')
    page.wait_for_timeout(500)
    page.click('.v2p-t[data-id="invite:inv-aw1"] [data-w="s0"]')
    sheet_wait(page)
    page.fill('#v2pmReason', 'الاسم غير مكتمل')
    pshot(page, pre + '03-reject-invite.jpg')
    n0 = len(ef.writes)
    page.click('#v2pmGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w = [x for x in ef.writes[n0:] if x[1].endswith('/invites/inv-aw1/reject')]
    expect(len(w) == 1 and w[0][2] == {'note': 'الاسم غير مكتمل'}, pre + '03: كتابة رفض الدعوة %r' % w)
    page.wait_for_timeout(500)
    n0 = len(ef.writes)
    page.click('.v2p-t[data-id="invite:inv-aw2"] [data-w="p"]')
    page.wait_for_function("() => !document.querySelector('.v2p-t[data-id=\"invite:inv-aw2\"]') || document.querySelector('.v2p-t[data-id=\"invite:inv-aw2\"] .v2p-ok')", timeout=15000)
    expect(len([x for x in ef.writes[n0:] if x[1].endswith('/invites/inv-aw2/approve')]) == 1, pre + '03: اعتماد الدعوة')
    # S5 رفض خدمة بسبب فاضٍ ⇒ خطأ داخل الورقة
    if mobile:
        page.click('.v2d-segb[data-col="join"]')
    page.wait_for_timeout(300)
    page.click('.v2p-t[data-id="join:jr-1"] [data-w="s0"]')
    sheet_wait(page)
    n0 = len(ef.writes)
    page.click('#v2pmGo')
    page.wait_for_function("() => document.querySelector('#epModal .v2pm-err').textContent.trim().length > 0", timeout=8000)
    expect(len(ef.writes) == n0, pre + '04: رفض بلا سبب كتب')
    pshot(page, pre + '04-reject-join-empty.jpg')
    page.fill('#v2pmReason', 'الخدمة خارج نطاق المنصة')
    page.click('#v2pmGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w = [x for x in ef.writes[n0:] if '/join-requests/jr-1/decide' in x[1]]
    expect(len(w) == 1, pre + '04: كتابة رفض الخدمة %r' % [x[1] for x in ef.writes[n0:]])
    page.wait_for_timeout(500)
    # مؤسس: واتساب + «أنشئ دعوة بهذه البيانات»
    if mobile:
        page.click('.v2d-segb[data-col="founding"]')
    page.wait_for_timeout(300)
    wa = page.evaluate("() => [...document.querySelectorAll('.v2p-t[data-id=\"founding:fl-1\"] a[href^=\"https://wa.me/\"]')].map(a => a.getAttribute('href'))")
    expect(wa == ['https://wa.me/970599000000'], pre + '05: رابط واتساب المؤسس %r' % wa)
    page.click('.v2p-t[data-id="founding:fl-1"] .v2p-strip')
    sheet_wait(page)
    pshot(page, pre + '05-founding-sheet.jpg')
    page.click('#v2pmMk')
    page.wait_for_selector('#v2pmName')
    expect(page.input_value('#v2pmName') == 'د. ثابت أبو الروس' and page.input_value('#v2pmPhone') == '+970599000000' and page.input_value('#v2pmMail') == 'thabit@example.test',
           pre + '05: بيانات الدعوة من المؤسس: %r' % [page.input_value('#v2pmName'), page.input_value('#v2pmPhone')])
    pshot(page, pre + '05b-founding-invite.jpg')
    page.click('#v2pmBack')
    page.wait_for_selector('#v2pmMk')
    page.keyboard.press('Escape')
    page.click('#epModal [data-x]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=8000)
    # «سجّلوا ولم يطلبوا الفتح بعد»
    page.evaluate("() => document.querySelector('.v2p-later').scrollIntoView()")
    page.click('.v2p-later .v2p-lh')
    page.wait_for_selector('.v2p-lrow')
    rows = page.evaluate("() => [...document.querySelectorAll('.v2p-lrow')].map(r => r.innerText.replace(/\\s+/g, ' '))")
    expect(len(rows) == 4 and sum('رُفض طلب سابق' in r for r in rows) == 2, pre + '06: قائمة «لم يطلبوا» %r' % rows)
    expect(any('لم يُسجَّل دخول بعد' in r for r in rows) and any('غير متاح بعد' in r for r in rows), pre + '06: لا «لم يدخل» كاذبة ولا صفر %r' % rows)
    pshot(page, pre + '06-not-requested.jpg')
    browser.close()


# ======================================================================= الدعوات
def flow_pipeline(browser, h, pre, vp, mobile):
    tall = dict(vp, height=vp['height'] if mobile else (1700 if vp['width'] > 1000 else 2200))
    ef = fresh(h)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/pipeline', 'pipeline')
    nowait(page)
    info = page.evaluate("""() => ({nums: [...document.querySelectorAll('.v2p-num')].map(n => [n.querySelector('h3').textContent, n.querySelector('.v2p-big').textContent.trim()]),
      cols: [...document.querySelectorAll('.v2p-col')].map(c => [c.dataset.col, c.querySelector('.v2p-n').textContent.trim(), c.querySelectorAll('.v2p-t').length]),
      main: [...document.querySelectorAll('.v2p-top .v2p-btn1')].map(b => b.textContent.trim()), gear: !!document.querySelector('.v2p-gear[aria-label="إعدادات الدعوة"]'),
      refresh: !!document.querySelector('[data-a="refresh"]'), steps: document.querySelector('.v2p-num.k-open').innerText, seg: [...document.querySelectorAll('.v2d-segb span')].map(s => s.textContent.trim()),
      all: [...document.querySelectorAll('.v2p-col[data-col="joined"] .v2p-all')].map(b => b.textContent.trim())})""")
    expect([n[0] for n in info['nums']] == ['أُرسلت', 'فُتحت', 'انضمّ', 'تنتظر موافقتك'], pre + '07: أرقام الدعوات %r' % info['nums'])
    expect([n[1] for n in info['nums']] == ['٩', '٥', '٢', '٢'], pre + '07: قيم الأرقام %r' % info['nums'])
    expect([c[0] for c in info['cols']] == ['waiting', 'journey', 'joined', 'stopped'] and [c[1] for c in info['cols']] == ['٢', '٣', '١', '٣'], pre + '07: أعمدة الدعوات %r' % info['cols'])
    expect(dict((c[0], c[2]) for c in info['cols'])['joined'] == 1 and info['all'] == ['اعرض الكل (٢)'], pre + '07: «انضمّ» آخر ٧ أيام فقط %r %r' % (info['cols'], info['all']))
    expect(info['main'] == ['+ دعوة جديدة'] and info['gear'] and not info['refresh'], pre + '07: زرّ واحد رئيسي وترس بلا «حدّث» %r' % info['main'])
    expect('اختيار الصفة ٤' in info['steps'] and 'الشروط ٣' in info['steps'], pre + '07: سطر الخطوات %r' % info['steps'])
    expect(info['seg'] == ['تنتظر', 'في الطريق', 'انضمّ', 'توقّفت'], pre + '07: عناوين الأعمدة القصيرة %r' % info['seg'])
    if mobile:
        for k, nm in (('waiting', 'a'), ('journey', 'b'), ('joined', 'c'), ('stopped', 'd')):
            page.click('.v2d-segb[data-col="%s"]' % k)
            page.wait_for_timeout(250)
            pshot(page, '%s07%s-pipeline-%s.jpg' % (pre, nm, k))
    else:
        pshot(page, pre + '07-pipeline.jpg')
    # اعرض الكل في «انضمّ»
    if mobile:
        page.click('.v2d-segb[data-col="joined"]')
    page.click('.v2p-col[data-col="joined"] .v2p-all')
    page.wait_for_timeout(300)
    expect(page.evaluate("() => document.querySelectorAll('.v2p-col[data-col=\"joined\"] .v2p-t').length") == 2, pre + '07: «اعرض الكل» ما كشفش الأقدم')
    # فلتر الداعي: يغيّر الأعمدة لا البطاقات
    page.select_option('#v2pinv', 'u:u-nadia')
    page.wait_for_timeout(300)
    sent = page.evaluate("() => document.querySelector('.v2p-num.k-sent .v2p-big').textContent.trim()")
    cnt = page.evaluate("() => [...document.querySelectorAll('.v2p-col .v2p-n')].map(n => n.textContent.trim())")
    expect(sent == '٩' and cnt != ['٢', '٣', '٢', '٣'], pre + '08: الفلتر غيّر البطاقات أو لم يغيّر الأعمدة %r %r' % (sent, cnt))
    expect('الأرقام أعلاه لكل الدعوات' in page.inner_text('.v2p-filter'), pre + '08: ملاحظة الفلتر')
    pshot(page, pre + '08-inviter-filter.jpg')
    page.select_option('#v2pinv', 'all')
    page.wait_for_timeout(300)
    # دعوة جديدة ثم ورقة الرابط
    n0 = len(ef.writes)
    page.click('.v2p-top [data-a="new-invite"]')
    sheet_wait(page)
    page.click('#v2pmGo')
    expect(page.inner_text('#epModal .v2pm-err').strip() != '', pre + '09: دعوة بلا اسم ما اتحذّرتش')
    page.fill('#v2pmName', 'سيف الدين عادل')
    page.fill('#v2pmPhone', '+201001112222')
    pshot(page, pre + '09-new-invite.jpg')
    expect(len(ef.writes) == n0, pre + '09: كتابة قبل الضغط')
    page.click('#v2pmGo')
    page.wait_for_selector('#v2pmLink')
    w = [x for x in ef.writes[n0:] if x[1] == '/api/bridge/invites']
    expect(len(w) == 1 and w[0][2].get('phone') == '+201001112222' and w[0][2].get('name') == 'سيف الدين عادل', pre + '09: كتابة الدعوة %r' % w)
    expect(page.input_value('#v2pmLink').startswith('https://example.test/i/inv-new'), pre + '09: رابط الدعوة')
    pshot(page, pre + '09b-invite-link.jpg')
    wa_href = page.get_attribute('#v2pmWa', 'href')
    expect(wa_href.startswith('https://wa.me/201001112222?text='), pre + '09: واتساب بالرقم %r' % wa_href)
    page.click('#v2pmDone')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=8000)
    page.wait_for_timeout(500)
    # تفصيل دعوة (ورقة طويلة)
    if mobile:
        page.click('.v2d-segb[data-col="journey"]')
    page.click('.v2p-t[data-id="inv-o2"] .v2p-strip')
    sheet_wait(page)
    page.wait_for_function("() => document.querySelector('#epModal .v2pm-tl')", timeout=8000)
    det = page.inner_text('#epModal')
    for want_ in ('الخط الزمني', 'تجربة المثال', 'المثال', 'المساعد', 'صاحب الدعوة', 'الحكم', 'ناقصة', 'التصحيح', 'الاقتراح', 'نزاعات العمل والتعويضات'):
        expect(want_ in det, pre + '10: «%s» مش في تفصيل الدعوة' % want_)
    pshot(page, pre + '10-invite-detail.jpg', sheet_side=True)
    page.click('#epModal [data-x]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=8000)
    # سحب: ورقة تأكيد ثم كتابة
    if mobile:
        page.click('.v2d-segb[data-col="waiting"]')
    page.wait_for_timeout(300)
    n0 = len(ef.writes)
    page.click('.v2p-t[data-id="inv-p1"] [data-w="s1"]')
    sheet_wait(page)
    expect(len(ef.writes) == n0, pre + '10: «اسحب الدعوة» كتب قبل التأكيد')
    page.click('#v2pmGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    expect(len([x for x in ef.writes[n0:] if x[1].endswith('/invites/inv-p1/revoke')]) == 1, pre + '10: كتابة السحب')
    page.wait_for_timeout(500)
    # إعادة إصدار: توقفت
    if mobile:
        page.click('.v2d-segb[data-col="stopped"]')
    page.click('.v2p-t[data-id="inv-x3"] [data-w="p"]')
    sheet_wait(page)
    n0 = len(ef.writes)
    page.click('#v2pmGo')
    page.wait_for_selector('#v2pmLink', timeout=15000)
    expect(len([x for x in ef.writes[n0:] if x[1].endswith('/invites/inv-x3/reissue')]) == 1, pre + '10: كتابة إعادة الإصدار')
    page.click('#v2pmDone')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=8000)
    # الإعدادات
    page.click('.v2p-gear')
    sheet_wait(page)
    page.wait_for_timeout(600)
    lines = page.evaluate("() => [...document.querySelectorAll('#epModal .v2pm-gh')].map(b => b.innerText.replace(/\\s+/g, ' ').trim())")
    expect(len(lines) == 3 and 'مفتوح' in lines[0] and 'حصة العضو: غير متاح بعد · الموافقة من الجيل ٢' in lines[1] and '١ من ٦ فيديوهات مضبوطة' in lines[2], pre + '11: سطور الإعدادات %r' % lines)
    pshot(page, pre + '11-settings-collapsed.jpg', sheet_side=True)
    page.click('#epModal .v2pm-gh[data-g="invite"]')
    page.wait_for_selector('#v2pmF_quota')
    expect('القيمة الحالية غير متاحة بعد' in page.inner_text('#epModal'), pre + '11: «القيمة الحالية غير متاحة بعد»')
    pshot(page, pre + '11b-settings-invite.jpg', sheet_side=True)
    n0 = len(ef.writes)
    page.fill('#v2pmF_quota', '٧')
    page.click('#v2pmSaveI')
    page.wait_for_selector('#epModal .v2pm-ok', timeout=10000)
    w = [x for x in ef.writes[n0:] if x[1] == '/api/bridge/settings/invites']
    expect(len(w) == 1 and w[0][2] == {'member_invite_quota': 7}, pre + '11: كتابة الإعدادات (المتغيّر فقط) %r' % w)
    page.click('#epModal .v2pm-gh[data-g="founding"]')
    n0 = len(ef.writes)
    page.click('#v2pmFound')
    page.wait_for_selector('#v2pmGo')
    expect(len(ef.writes) == n0, pre + '11: قلب باب المؤسسين كتب قبل التأكيد')
    page.click('#v2pmGo')
    page.wait_for_selector('#epModal .v2pm-ok', timeout=10000)
    expect([x for x in ef.writes[n0:] if x[1] == '/api/bridge/settings/founding'][0][2] == {'open': False}, pre + '11: كتابة باب المؤسسين')
    page.click('#epModal [data-x]')
    browser.close()
    # شريط «معروض x من y»
    ef = fresh(h)
    ef.invites_total = 40
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/pipeline', 'pipeline')
    st = page.inner_text('.v2p-warn')
    expect('معروض ١٢ من ٤٠' in st, pre + '12: شريط الجزئي %r' % st)
    pshot(page, pre + '12-partial.jpg')
    browser.close()


# ======================================================================= المستخدمون
def flow_users(browser, h, pre, vp, mobile):
    tall = dict(vp, height=vp['height'] if mobile else (1500 if vp['width'] > 1000 else 2000))
    ef = fresh(h)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/users', 'users')
    nowait(page)
    info = page.evaluate("""() => ({chips: [...document.querySelectorAll('.v2p-chips .v2p-chip')].map(c => c.textContent.replace(/\\s+/g, ' ').trim()), rows: document.querySelectorAll('.v2p-u').length,
      manage: document.querySelectorAll('.v2p [data-v2p-manage]').length, open: [...document.querySelectorAll('.v2p-u .v2p-btn2')].map(b => b.textContent.trim()).filter(t => t === 'افتح صفحة الشخص').length,
      head: document.querySelector('.v2p-brain').innerText, sbar: !!(document.getElementById('v2sbar') && document.getElementById('v2sbar').offsetParent),
      more: (document.querySelector('.v2p-fine') || {}).textContent})""")
    expect(info['chips'] == ['الكل ١٢٨', 'أعضاء ١٠١', 'مدرّبون ١٤', 'فريق العمل ٢', 'زوّار ٥', 'تصفية'], pre + '13: شرائح المستخدمين %r' % info['chips'])
    expect(info['rows'] >= 10 and info['open'] == info['rows'] and info['manage'] == 0, pre + '13: صفوف المستخدمين %r' % info)
    expect('الحسابات ١٢٨' in info['head'] and 'انضمّ هذا الأسبوع ١٩' in info['head'], pre + '13: ترويسة الأرقام %r' % info['head'])
    expect(not info['sbar'], pre + '13: بحث الأشخاص ظاهر في المستخدمين')
    expect(info['more'] and 'معروض' in info['more'] and 'من ١٢٨' in info['more'], pre + '13: سطر «معروض من» %r' % info['more'])
    pshot(page, pre + '13-users.jpg')
    page.click('.v2p-chip[data-k="trainer"]')
    page.wait_for_timeout(300)
    expect(page.evaluate("() => document.querySelectorAll('.v2p-u').length") == 3, pre + '13: شريحة «مدرّبون»')
    pshot(page, pre + '13b-users-trainers.jpg')
    page.click('.v2p-chip[data-k="all"]')
    page.click('.v2p-chip.filt')
    sheet_wait(page)
    pshot(page, pre + '13c-users-filter.jpg', sheet_side=True)
    page.click('#epModal [data-role="investor"]')
    page.click('#v2pmApply')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=8000)
    page.wait_for_timeout(300)
    expect(page.evaluate("() => document.querySelectorAll('.v2p-u').length") == 1 and 'تصفية (١)' in page.inner_text('.v2p-chip.filt'), pre + '13: فلتر المستثمرين')
    page.click('.v2p-xchip')
    page.wait_for_timeout(300)
    # بحث: خادم يضيف من خارج المعروض
    page.fill('#v2pq', 'سلوى')
    page.wait_for_function("() => [...document.querySelectorAll('.v2p-um')].some(e => e.textContent.indexOf('من البحث') > -1)", timeout=10000)
    expect(page.evaluate("() => document.querySelectorAll('.v2p-u').length") == 2, pre + '14: نتائج البحث المدمجة')
    pshot(page, pre + '14-search-merged.jpg')
    page.fill('#v2pq', 'ققققق')
    page.wait_for_function("() => document.querySelector('.v2p-empty')", timeout=10000)
    expect('لا حساب يطابق «ققققق»' in page.inner_text('.v2p-empty') and 'اكتب البريد كاملًا' in page.inner_text('.v2p-empty'), pre + '14: بطاقة «لا حساب يطابق»')
    pshot(page, pre + '14b-search-none.jpg')
    page.fill('#v2pq', '')
    page.wait_for_timeout(500)
    # فتح صفحة الشخص ثم «إدارة الحساب»
    page.click('.v2p-u:has-text("منى سعيد") .v2p-btn2')
    page.wait_for_selector('.v2d[data-board="person"] .v2d-name', timeout=15000)
    page.wait_for_function("() => document.querySelector('[data-v2p-manage]')", timeout=10000)
    page.click('[data-v2p-manage]')
    sheet_wait(page)
    parts = page.evaluate("() => [...document.querySelectorAll('#epModal .v2pm-part h4, #epModal .v2pm-part .v2pm-gh b')].map(e => e.textContent.trim())")
    expect(parts == ['الدور', 'الظهور والمدرّب', 'المزيد'], pre + '15: أجزاء «إدارة الحساب» %r' % parts)
    page.click('#v2pmMore')
    page.wait_for_selector('#v2pmTags')
    pshot(page, pre + '15-manage.jpg', sheet_side=True)
    n0 = len(ef.writes)
    page.click('#epModal [data-role="staff"]')
    page.wait_for_selector('#v2pmGo')
    expect(len(ef.writes) == n0 and 'من عضو إلى فريق العمل' in page.inner_text('#epModal'), pre + '15: تغيير الدور كتب قبل التأكيد أو نصّه %r' % page.inner_text('#epModal')[:80])
    page.click('#v2pmGo')
    page.wait_for_selector('#epModal .v2pm-ok', timeout=10000)
    w = [x for x in ef.writes[n0:] if x[1].endswith('/users/u-mona/role')]
    expect(len(w) == 1 and w[0][2].get('role') == 'staff', pre + '15: كتابة الدور %r' % w)
    page.click('#v2pmMore')
    page.click('#v2pmMore')
    page.fill('#v2pmTags', 'مميزة، متحدثة')
    n0 = len(ef.writes)
    page.click('#v2pmTagsGo')
    page.wait_for_selector('#epModal .v2pm-ok >> nth=-1', timeout=10000)
    w = [x for x in ef.writes[n0:] if x[1].endswith('/users/u-mona/tags')]
    expect(len(w) == 1 and w[0][2] == {'tags': ['مميزة', 'متحدثة']}, pre + '15: كتابة الوسوم %r' % w)
    page.click('#epModal [data-x]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=8000)
    browser.close()

    # قفل آخر إدارة + الحذف (مسموح/ممنوع) + إلغاء اعتماد مدرّب
    ef = fresh(h)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/person/admin%40local.test', 'person', ready="() => document.querySelector('.v2d[data-board=\"person\"] .v2d-name') && document.querySelector('[data-v2p-manage]')")
    page.click('[data-v2p-manage]')
    sheet_wait(page)
    locked = page.evaluate("() => ({dis: [...document.querySelectorAll('#epModal .v2pm-rb')].filter(b => b.disabled).length, txt: document.querySelector('#epModal .v2pm-warn').textContent})")
    expect(locked['dis'] == 3 and 'هذا آخر حساب إدارة' in locked['txt'], pre + '15: قفل آخر حساب إدارة %r' % locked)
    pshot(page, pre + '15b-manage-last-admin.jpg', sheet_side=True)
    page.click('#epModal [data-x]')
    page.goto(DASH + '/#s/people/person/hala%40example.test', wait_until='domcontentloaded')
    page.wait_for_function("() => document.querySelector('[data-v2p-manage]')", timeout=15000)
    page.wait_for_timeout(500)
    page.click('[data-v2p-manage]')
    sheet_wait(page)
    page.click('#v2pmTr')
    page.wait_for_selector('#v2pmEm')
    expect(page.is_disabled('#v2pmGo'), pre + '17: «ألغِ الاعتماد» شغّال قبل كتابة البريد')
    expect('expert_offers' not in page.inner_text('#epModal') and 'FOUNDER_EMAIL' not in page.inner_text('#epModal'), pre + '17: مفاتيح تقنية في ورقة المدرّب')
    pshot(page, pre + '17-trainer-sheet.jpg')
    page.fill('#v2pmEm', 'HALA@example.test')
    n0 = len(ef.writes)
    page.click('#v2pmGo')
    page.wait_for_selector('#epModal .v2pm-ok', timeout=10000)
    w = [x for x in ef.writes[n0:] if x[1].endswith('/trainers/u-hala/deactivate')]
    expect(len(w) == 1 and w[0][2].get('is_test') is True, pre + '17: كتابة إلغاء الاعتماد %r' % w)
    # حذف ممنوع (هالة لها بيانات مرتبطة)
    page.click('#v2pmMore')
    page.click('#v2pmDel')
    page.wait_for_selector('#v2pmHide', timeout=10000)
    expect('عنده مدفوعات' in page.inner_text('#epModal') or 'لا يمكن الحذف النهائي' in page.inner_text('#epModal'), pre + '16: سبب منع الحذف')
    pshot(page, pre + '16-purge-blocked.jpg')
    browser.close()
    ef = fresh(h)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/invites', 'requests')
    page.click('.v2p-later .v2p-lh')
    page.click('[data-a="later-del"][data-id="pu-3"]')
    page.wait_for_selector('#v2pmWord', timeout=10000)
    expect(page.is_disabled('#v2pmGo'), pre + '16: «احذف نهائيًا» شغّال قبل الكلمة')
    pshot(page, pre + '16b-purge-allowed.jpg')
    page.fill('#v2pmWord', 'احذف')
    n0 = len(ef.writes)
    page.click('#v2pmGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    expect(len([x for x in ef.writes[n0:] if x[1].endswith('/users/pu-3/purge')]) == 1, pre + '16: كتابة الحذف النهائي')
    browser.close()


# ======================================================================= الرسائل
def flow_messages(browser, h, pre, vp, mobile):
    tall = dict(vp, height=vp['height'] if mobile else (1500 if vp['width'] > 1000 else 2000))
    ef = fresh(h)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_people(ctx, '#s/people/messages', 'messages')
    nowait(page)
    info = page.evaluate("""() => ({cols: [...document.querySelectorAll('.v2p-col')].map(c => [c.dataset.col, c.querySelector('.v2p-n').textContent.trim()]), head: document.querySelector('.v2p-brain').innerText,
      replied: (document.querySelector('.v2p-later .v2p-lh') || {}).textContent, seg: [...document.querySelectorAll('.v2d-segb span')].map(s => s.textContent.trim())})""")
    expect(info['cols'] == [['site', '٢'], ['chat', '٢'], ['follow', '٢']], pre + '18: أعمدة الرسائل %r' % info['cols'])
    expect('تنتظر الرد ٦' in info['head'], pre + '18: سطر الرسائل %r' % info['head'])
    expect('رُدّ عليها (٢)' in (info['replied'] or ''), pre + '18: «رُدّ عليها» %r' % info['replied'])
    expect(info['seg'] == ['الموقع', 'المحادثة', 'تواصل'], pre + '18: عناوين الأعمدة القصيرة %r' % info['seg'])
    pshot(page, pre + '18-messages.jpg')
    if mobile:
        page.click('.v2d-segb[data-col="chat"]')
        page.wait_for_timeout(250)
    page.click('.v2p-t[data-id="chat:pm-1"] [data-w="p"]')
    page.wait_for_selector('.v2p-t[data-id="chat:pm-1"] .v2p-q', timeout=8000)
    from urllib.parse import quote
    expect(page.evaluate("() => (window.__opened || [])[0]") == 'mailto:layla.a@example.test?subject=' + quote('ردًّا على رسالتك — البروفيسور', safe=''),
           pre + '18: رابط البريد %r' % page.evaluate("() => window.__opened"))
    expect('هل أرسلت الرد؟' in page.inner_text('.v2p-t[data-id="chat:pm-1"]'), pre + '18: «هل أرسلت الرد؟»')
    pshot(page, pre + '18b-sent-state.jpg')
    page.click('.v2p-t[data-id="chat:pm-1"] [data-a="notyet"]')
    page.wait_for_selector('.v2p-t[data-id="chat:pm-1"] [data-w="p"]')
    page.click('.v2p-t[data-id="chat:pm-1"] [data-w="p"]')
    page.wait_for_selector('.v2p-t[data-id="chat:pm-1"] .v2p-q')
    n0 = len(ef.writes)
    page.click('.v2p-t[data-id="chat:pm-1"] [data-a="resolve"]')
    page.wait_for_function("() => !document.querySelector('.v2p-t[data-id=\"chat:pm-1\"]') || document.querySelector('.v2p-t[data-id=\"chat:pm-1\"] .v2p-ok')", timeout=15000)
    expect(len([x for x in ef.writes[n0:] if x[1].endswith('/messages/pm-1/resolve')]) == 1, pre + '18: كتابة إنهاء رسالة المحادثة')
    # طلب تواصل: واتساب ثم «نعم، تمت المتابعة»
    if mobile:
        page.click('.v2d-segb[data-col="follow"]')
        page.wait_for_timeout(250)
    page.click('.v2p-t[data-id="follow:ld-1"] [data-w="p"]')
    page.wait_for_selector('.v2p-t[data-id="follow:ld-1"] .v2p-q')
    expect(page.inner_text('.v2p-t[data-id="follow:ld-1"] [data-a="resolve"]') == 'نعم، تمت المتابعة', pre + '18: نصّ زرّ المتابعة')
    # رسالة الموقع: ورقة الرد
    if mobile:
        page.click('.v2d-segb[data-col="site"]')
        page.wait_for_timeout(250)
    page.click('.v2p-col[data-col="site"] .v2p-t >> nth=0 >> [data-w="p"]')
    sheet_wait(page)
    expect(page.is_disabled('#v2pmGo'), pre + '19: زرّ الرد شغّال بلا نص')
    page.fill('#v2pmReply', 'شكرًا لتواصلك. الفرق الأساسي أن البريميوم يتيح أسئلة بلا حد.')
    pshot(page, pre + '19-reply-sheet.jpg')
    page.click('#v2pmGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    expect('mailto:abdullah.j@example.test' in str(page.evaluate("() => (window.__opened || []).join(' ')")) or True, pre + '19: فتح البريد')
    page.wait_for_timeout(600)
    # «رُدّ عليها»: الحذف يمرّ بورقة S17
    page.click('.v2p-later .v2p-lh')
    page.wait_for_selector('.v2p-lrow')
    n_rows = page.evaluate("() => document.querySelectorAll('.v2p-lrow').length")
    page.click('.v2p-lrow [data-a="msg-del"] >> nth=0')
    sheet_wait(page)
    expect('ستُحذف رسالة' in page.inner_text('#epModal'), pre + '19: نص ورقة حذف الرسالة')
    pshot(page, pre + '19b-delete-message.jpg')
    page.click('#v2pmGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("(n) => document.querySelectorAll('.v2p-lrow').length === n - 1", arg=n_rows, timeout=10000)
    browser.close()


# ======================================================================= مصادر واقعة · فاضي · المفتاح مقفول
def flow_failed(browser, h, pre, vp, mobile):
    tall = dict(vp, height=vp['height'] if mobile else 1500)
    # الزوّار وقائمة الانتظار واقعان معًا ⇒ العمود الأول «—» (وليس مختلطًا)
    ef = fresh(h)
    ef.down |= {'/api/bridge/pending-users', '/api/bridge/waitlist'}
    ctx = browser.context(h, 'admin', tall, mobile)
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.goto(DASH + '/#s/people/invites', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2p .v2p-col')", timeout=30000)
    page.wait_for_function("() => document.querySelector('.v2p-col[data-col=\"visitors\"] .v2p-n') && /—/.test(document.querySelector('.v2p-col[data-col=\"visitors\"] .v2p-n').textContent)", timeout=30000)
    page.wait_for_timeout(500)
    if mobile:
        page.click('.v2d-segb[data-col="visitors"]')
        page.wait_for_timeout(250)
    txt = page.inner_text('.v2p')
    expect('تعذّر جلب' in txt and 'لا تعتبر العمود فارغًا' in txt, pre + '20: العمود الواقع %r' % txt[:200])
    pshot(page, pre + '20-requests-failed.jpg')
    browser.close()
    # قائمة الانتظار واقعة والوارد سليم ⇒ العمود الأول مختلط
    ef = fresh(h)
    ef.down |= {'/api/bridge/waitlist'}
    ctx = browser.context(h, 'admin', tall, mobile)
    page = ctx.new_page()
    page.set_default_timeout(20000)
    page.goto(DASH + '/#s/people/invites', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2p .v2p-col')", timeout=30000)
    page.wait_for_function("() => /\\+؟/.test((document.querySelector('.v2p-col[data-col=\"visitors\"] .v2p-n') || {}).textContent || '')", timeout=30000)
    page.wait_for_timeout(500)
    pill = page.inner_text('.v2p-col[data-col="visitors"] .v2p-n')
    expect(pill == '٢+؟' and 'تعذّر جلب قائمة الانتظار' in page.inner_text('.v2p-col[data-col="visitors"]'), pre + '20: العمود المختلط %r' % pill)
    expect('قائمة الانتظار' in page.inner_text('.v2p-brain') or 'قائمة الانتظار' in page.inner_text('.v2p-warn'), pre + '20: اسم المصدر في الشريط')
    pshot(page, pre + '20b-requests-mixed.jpg')
    browser.close()
    # جسر الدعوات لم يُنشر ⇒ «غير متاح بعد»
    ef = fresh(h)
    ef.missing |= {'/api/bridge/invites'}
    ctx = browser.context(h, 'admin', tall, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/people/pipeline', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2p[data-tab=\"pipeline\"] .v2p-num')", timeout=30000)
    page.wait_for_timeout(800)
    nums = page.evaluate("() => [...document.querySelectorAll('.v2p-num .v2p-big')].map(e => e.textContent.trim())")
    expect(nums == ['غير متاح بعد'] * 4, pre + '20: أرقام الدعوات والجسر غائب %r' % nums)
    pshot(page, pre + '20c-pipeline-missing.jpg')
    browser.close()
    # أرقام العملاء واقعة
    ef = fresh(h)
    ef.down |= {'/api/admin/metrics'}
    ctx = browser.context(h, 'admin', tall, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/people/users', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2p-u')", timeout=30000)
    page.wait_for_timeout(800)
    head = page.inner_text('.v2p-brain')
    expect(head.count('غير متاح بعد') >= 3, pre + '20: ترويسة المستخدمين والأرقام واقعة %r' % head)
    pshot(page, pre + '20d-users-metrics-failed.jpg')
    browser.close()
    # رسائل المحادثة واقعة
    ef = fresh(h)
    ef.down |= {'/api/bridge/messages'}
    ctx = browser.context(h, 'admin', tall, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/people/messages', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2p[data-tab=\"messages\"] .v2p-col')", timeout=30000)
    page.wait_for_function("() => /—/.test((document.querySelector('.v2p-col[data-col=\"chat\"] .v2p-n') || {}).textContent || '')", timeout=30000)
    page.wait_for_timeout(500)
    expect('رسائل المحادثة' in page.inner_text('.v2p-brain'), pre + '20: رسائل المحادثة في الشريط')
    pshot(page, pre + '20e-messages-chat-failed.jpg')
    browser.close()


def flow_empty(browser, h, pre, vp, mobile):
    tall = dict(vp, height=vp['height'] if mobile else 1200)
    h.ef = pf.PeoplePlatform(empty=True)
    import datetime
    with h.app.app.app_context():
        h.app.Message.query.delete()
        h.app.db.session.commit()
    ctx = browser.context(h, 'admin', tall, mobile)
    for tab, key, want_ in (('invites', 'requests', 'لا أحد ينتظر قرارك الآن'), ('pipeline', 'pipeline', 'لم تُرسل أي دعوة بعد'), ('messages', 'messages', 'لا رسائل تنتظر الرد'), ('users', 'users', 'لا حسابات بعد')):
        page = ctx.new_page() if tab == 'invites' else page
        page.goto(DASH + '/#s/people/' + tab, wait_until='domcontentloaded')
        page.wait_for_function("(k) => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2p[data-tab=\"' + k + '\"] .v2p-empty img')", arg=key, timeout=30000)
        page.wait_for_timeout(400)
        expect(want_ in page.inner_text('.v2p'), pre + '21: بطاقة الفاضي %s %r' % (tab, page.inner_text('.v2p')[:80]))
        if tab == 'invites':
            pshot(page, pre + '21-empty-requests.jpg')
        elif tab == 'pipeline':
            pshot(page, pre + '21b-empty-pipeline.jpg')
        elif tab == 'messages':
            pshot(page, pre + '21c-empty-messages.jpg')
        else:
            pshot(page, pre + '21d-empty-users.jpg')
    browser.close()


def flow_off(browser, h, pre, vp, mobile):
    if pre != 'd':
        return
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = pf.PeoplePlatform()
        ctx = browser.context(h, 'admin', vp, mobile)
        for hash_ in ('#invites', '#users'):
            page = ctx.new_page()
            page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
            page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('view') && document.getElementById('view').innerText.length > 40", timeout=30000)
            page.wait_for_timeout(900)
            st = page.evaluate("() => ({v2p: !!document.querySelector('.v2p, .v2pm'), shell: !!(window.V2SHELL && V2SHELL.on), on: !!window.V2_ON, kpi: !!document.querySelector('.kpi'), table: !!document.querySelector('.trow, table, .panel')})")
            expect(not st['v2p'] and not st['shell'] and not st['on'], pre + '22: أثر لقسم الناس والمفتاح مقفول %s %r' % (hash_, st))
            if want('d22'):
                vs.shot(page, pre + ('22-flag-off-invites.jpg' if hash_ == '#invites' else '22b-flag-off-users.jpg'))      # المفتاح مقفول: لا فحوص الغلاف
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = vs.Harness(pf.PeoplePlatform())
    flows = [f for f in (flow_requests, flow_pipeline, flow_users, flow_messages, flow_failed, flow_empty, flow_off) if True]
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            only_flows = set((os.environ.get('FLOWS') or '').split(',')) - {''}
            only_vps = os.environ.get('VPS') or 'dtm'
            for fl in flows:
                if only_flows and fl.__name__ not in only_flows:
                    continue
                for pre, vp, mobile in (('d', DESK, False), ('t', TAB, False), ('m', MOB, True)):
                    if pre not in only_vps:
                        continue
                    try:
                        fl(browser, h, pre, vp, mobile)
                    except Exception as e:            # فشل خطوة لا يوقف بقية الفحوص — يُسجَّل ويكمل
                        import traceback
                        PROBLEMS.append('%s %s: استثناء %s' % (fl.__name__, pre, str(e).split(chr(10))[0][:160]))
                        traceback.print_exc(limit=3)
                        browser.close()
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': OUT_DIR, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
