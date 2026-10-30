# -*- coding: utf-8 -*-
"""لقطات «سوق الخدمات» (الجولة النهائية) — كمبيوتر ١٤٤٠ (`d`) وتابلت ٨٢٠ (`t`) وموبايل ٣٩٠ (`m`).

    cd backend && python3 -B tests/uiharness/v2_shots_market.py ../docs/v2/final/shots-market

اللقطات (SPEC-market §١١): اللوحة بأعمدتها · كل عمود في الموبايل (مع فحص إن العمود الظاهر واحد وفيه تذكرة) · تصفية الحارة · ورقة التصفية في الموبايل ·
الدرج بالعروض (مع فحص إن الأعمدة ما اتضيّقتش) · الهاتف · طلب مفتوح اكتمل عدده · أوراق: إغلاق · إخفاء · نقل · ربط (بدورات وبلا دورات) · إنشاء دورة ·
أخطاء الربط ٤٠٤ بنوعيها · بعد الإغلاق · موظف (عرض فقط) · العدّاد ما يمسحش الحالة · ٤٠٩ · تحميل وفشل وغير متاح وفارغ · «كل الطلبات» بحالاتها ·
«ماذا يطلب الناس» بحالاتها · الرابط القديم · المفتاح مقفول.

السكربت بيفشل لو: شريط تذكرة عنّابي · كلمة «اعمل» ظاهرة · تمرير أفقي في أي عرض · هدف أقل من ٤٤px (والأزرار أقل من ٥٢px في الموبايل) ·
undefined/NaN/null ظاهرة · كلمة تقنية لاتينية ظاهرة · صنف قديم جوه `#view` · نداء كتابة على `/api/v2/market/*` من غير `confirmed:true` · أي طلب خرج برّه
الداشبورد الوهمي (غير خطوط جوجل).
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة جدول في الذاكرة (`market_fixtures.MarketPlatform`).
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import market_fixtures as mfx                   # noqa: E402
import v2_shots as vs                           # noqa: E402  (OUT/SHOTS/PROBLEMS/shot/shell_check/Browsers مشتركة، ولا تعديل عليه)
from ef_route_harness import Harness, DASH      # noqa: E402

PROBLEMS = vs.PROBLEMS
DESK = {'width': 1440, 'height': 1500}
TAB = {'width': 820, 'height': 1700}
MOB = {'width': 390, 'height': 844}
OLD_CLASSES = ['.kpis', '.inboxwrap', '.policy', '.tabbar', '.panel', '.row.esc-row', '#drawer', '.chip']
LATIN = re.compile(r'(?<![\w@.-])(bridge|api|need_kind|lane|native|titch|per-head)(?![\w@.-])|/api/|api\.elprofessor\.net', re.I)
BOARD_READY = ("() => window.V2SHELL && V2SHELL.on === true && window.V2S_MARKET && EP.state.market === 'ready' && document.querySelector('.v2s-mk[data-board=\"market\"] .v2d-t')")
ALL_READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-mk-all') && !document.querySelector('.v2s-mk-all .v2s-mk-sk')")
DEM_READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-mk-dem') && !document.querySelector('.v2s-mk-dem .v2s-mk-sk')")
WRITES = []


def mk_check(page, name):
    w = page.viewport_size['width']
    r = page.evaluate("""() => {
      const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
      const roots = [...document.querySelectorAll('#view, #mkOv, #epModal')].filter(vis);
      const text = roots.map(e => e.innerText).join('\\n');
      const wine = [...document.querySelectorAll('#view .v2d-t .v2d-strip')].filter(vis).filter(e => getComputedStyle(e).backgroundColor === 'rgb(158, 43, 78)').length;
      const tg = [...document.querySelectorAll('#view button, #view a[href], #mkOv button, #mkOv a[href], #mkOv input, #epModal button, #epModal input, #epModal textarea, #epModal select, #epModal summary')]
        .filter(vis).map(b => { const t = (b.type === 'checkbox' || b.type === 'radio') && b.closest('label') ? b.closest('label') : b; return [b.className || b.tagName, Math.round(t.getBoundingClientRect().height)]; });
      const bigBtn = [...document.querySelectorAll('#view .v2d-btn1, #view .v2d-btn2, #view .v2s-mk-fbtn, #mkOv .v2d-btn1, #mkOv .v2d-btn2, #epModal .btn')]
        .filter(vis).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]);
      const old = %s.filter(s => [...document.querySelectorAll('#view ' + s)].some(vis));
      const sw = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content') || {}).scrollWidth || 0);
      const clipped = e => { for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o !== 'visible') { const r = p.getBoundingClientRect(); if (r.right <= window.innerWidth + 1 && r.left >= -1) return true; } } return false; };
      const out = [...document.querySelectorAll('#view *, #mkOv *, #epModal *')].filter(vis).filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.right > window.innerWidth + 1 || r.left < -1) && !clipped(e); }).length;
      const clone = roots.map(e => { const c = e.cloneNode(true); c.querySelectorAll('.v2s-mk-ltr, .v2s-mk-tel, a[href^="tel:"], input, textarea').forEach(n => n.remove()); return c.innerText; }).join('\\n');
      return {text, wine, tg, bigBtn, old, sw, out, clone};
    }""" % json.dumps(OLD_CLASSES))
    for bad in ('undefined', 'NaN', '[object Object]'):
        if bad in r['text']:
            PROBLEMS.append('%s: «%s» ظاهرة في الصفحة' % (name, bad))
    if re.search(r'(?<![\w@./-])null(?![\w@./-])', r['text']):
        PROBLEMS.append('%s: «null» ظاهرة في الصفحة' % name)
    m = LATIN.search(r['text'])
    if m:
        PROBLEMS.append('%s: كلمة تقنية لاتينية ظاهرة «%s»' % (name, m.group(0)))
    if 'اعمل' in r['text']:
        PROBLEMS.append('%s: كلمة «اعمل» ظاهرة' % name)
    if 'يقوّم' in r['text'] or re.search(r'(^|\n)\s*الذكاء الاصطناعي', r['text']):
        PROBLEMS.append('%s: صياغة ممنوعة ظاهرة' % name)
    if r['wine']:
        PROBLEMS.append('%s: %d شريط تذكرة عنّابي' % (name, r['wine']))
    if r['old']:
        PROBLEMS.append('%s: صنف قديم جوه #view: %r' % (name, r['old']))
    small = [x for x in r['tg'] if x[1] < 44]
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    if w <= 400:
        big = [x for x in r['bigBtn'] if x[1] < 52]
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, big[:4]))
    if r['sw'] > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))
    if r['out']:
        PROBLEMS.append('%s: %d عنصر خارج عرض الشاشة' % (name, r['out']))
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', r['clone'])) if '@' not in t and not re.search(r'[A-Za-z]-?\d', t)]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))


def mshot(page, name):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    vs.shot(page, name)
    vs.shell_check(page, name)
    mk_check(page, name)


def watch(page):
    def on_req(req):
        if '/api/v2/market/' in req.url and req.method == 'POST':
            try:
                body = json.loads(req.post_data or '{}')
            except Exception:
                body = {}
            WRITES.append((req.url, body))
            if body.get('confirmed') is not True:
                PROBLEMS.append('نداء كتابة من غير confirmed:true: %s' % req.url)
    page.on('request', on_req)
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % e))


def open_at(ctx, hash_, ready):
    page = ctx.new_page()
    watch(page)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(ready, timeout=30000)
    page.wait_for_timeout(450)
    return page


def tickets_in(page, col):
    return page.evaluate("(c) => [...document.querySelectorAll('.v2s-mk .v2d-col[data-col=\"' + c + '\"] .v2d-t')].map(t => t.getAttribute('data-id'))", col)


def col_widths(page):
    return page.evaluate("() => [...document.querySelectorAll('.v2s-mk .v2d-col')].map(c => Math.round(c.getBoundingClientRect().width))")


def open_drawer(page, rid):
    page.click('.v2s-mk .v2d-t[data-id="%s"] [data-a="open"]' % rid)
    page.wait_for_selector('#mkOv .v2s-mk-panel')
    page.wait_for_timeout(350)


def close_drawer(page):
    page.click('#mkOv [data-a="dx"].v2s-mk-x')
    page.wait_for_function("() => !document.getElementById('mkOv')")


def expand(page, col='waiting'):
    b = page.query_selector('.v2s-mk [data-a="more"][data-col="%s"]' % col)
    if b and b.is_visible():
        b.click()
        page.wait_for_timeout(250)


def seed_courses(h, rows):
    m = h.app
    with m.app.app_context():
        m.Course.query.delete()
        for i, (title, trainer, slug) in enumerate(rows):
            m.db.session.add(m.Course(title=title, trainer_name=trainer, status='active', platform_course_id='pc-%d' % i, platform_course_slug=slug))
        m.db.session.commit()


def flow(browser, h, pre, vp, mobile):
    w = vp['width']
    ro_names = ('أغلق', 'أخفِ', 'أظهره', 'انقله', 'اربط', 'أنشئ', 'غيّر الدورة')
    # ================================================================ اللوحة
    h.ef = mfx.MarketPlatform()
    seed_courses(h, [('أساسيات صياغة العقود', 'د. هالة سمير', 'contract-basics'), ('تسويق مكتب المحاماة', 'فريق البروفيسور', 'marketing-basics')])
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market', BOARD_READY)
    st = page.evaluate("() => ({hash: location.hash, tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), tile: (V2.tiles().filter(t => t.key === 'market')[0] || {}).count})")
    if st['tabs'] != ['الطلبات', 'كل الطلبات', 'ماذا يطلب الناس']:
        PROBLEMS.append('%s01: تبويبات السوق %r' % (pre, st['tabs']))
    # الرقم في سطر العقل = المربّع = عدد التذاكر غير المخفية في «طلب جديد» + «ينتظر خبيرًا» (حالتها مفتوحة)
    n_tick = page.evaluate("""() => { const T = V2S_MARKET._state.T; let n = 0; ['new', 'waiting'].forEach(c => T.cols[c].forEach(t => { if (t.row.status === 'open' && !t.row.hidden) n++; })); return n; }""")
    brain_n = page.evaluate("() => V2S_MARKET._state.T.tileCount")
    if not (n_tick == brain_n == st['tile']):
        PROBLEMS.append('%s01: رقم العقل/المربّع/التذاكر مش واحد: %r %r %r' % (pre, n_tick, brain_n, st['tile']))
    counts = page.evaluate("() => V2S_MARKET._state.T.counts")
    if not all(counts[c] for c in ('new', 'waiting', 'offered', 'done')):
        PROBLEMS.append('%s01: عمود فاضي والفيكستشر مليان: %r' % (pre, counts))
    if w >= 1180:
        # لا زرّ تصفية ولا قفص: شريط الحارات ظاهر
        if not page.is_visible('.v2s-mk-desk'):
            PROBLEMS.append(pre + '01: صف الحارات مش ظاهر على الكمبيوتر')
    mshot(page, pre + '01-board-full.jpg')
    # عمود طويل: «اعرض الباقي»
    more = page.query_selector('.v2s-mk [data-a="more"][data-col="waiting"]')
    if w >= 761 and not more:
        PROBLEMS.append(pre + '01: «اعرض الباقي» مش ظاهر والعمود فيه أكتر من ٨')
    if w < 761:
        # كل عمود: ظاهر عمود واحد فقط وفيه تذكرة
        for c in ('new', 'waiting', 'offered', 'done'):
            page.click('.v2d-segb[data-col="%s"]' % c)
            page.wait_for_timeout(200)
            vis = page.evaluate("() => [...document.querySelectorAll('.v2s-mk .v2d-col')].filter(e => e.offsetParent).map(e => [e.getAttribute('data-col'), e.querySelectorAll('.v2d-t').length])")
            n = int(page.evaluate("(c) => document.querySelector('.v2d-segb[data-col=\"' + c + '\"] b').textContent.replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d))", c))
            if len(vis) != 1 or vis[0][0] != c or (n > 0 and vis[0][1] < 1):
                PROBLEMS.append('%s02: عمود %s: الظاهر %r والعدّاد %s' % (pre, c, vis, n))
            mshot(page, '%s02-board-col-%s.jpg' % (pre, c))
        # أعلى الأعمدة في الموبايل: سطر العقل وزرّ التصفية والشريط فقط
        above = page.evaluate("""() => [...document.querySelector('.v2s-mk[data-board="market"]').children].filter(e => e.offsetParent).map(e => e.className)""")
        extra = [c for c in above if not re.search(r'v2d-top|v2s-mk-mob|v2d-seg|v2d-cols|v2s-mk-ro|v2d-warn', c)]
        if extra:
            PROBLEMS.append('%s03b: فوق الأعمدة في الموبايل حاجات زيادة: %r' % (pre, extra))
        page.click('.v2s-mk-fbtn[data-a="fopen"]')
        page.wait_for_selector('#mkOv.v2s-mk-fs')
        page.wait_for_timeout(300)
        mshot(page, pre + '03b-board-filter-sheet.jpg')
        page.click('#mkOv [data-a="flane"][data-lane="course_request"]')
        page.wait_for_timeout(200)
        page.click('#mkOv [data-a="fclose"].v2d-btn1')
        page.wait_for_function("() => !document.getElementById('mkOv')")
        if not page.is_visible('.v2s-mk-mob .v2s-mk-chip.rm'):
            PROBLEMS.append(pre + '03: الشريحة القابلة للإزالة مش ظاهرة بعد اختيار حارة الدورات')
        mshot(page, pre + '03-board-lane-course.jpg')
        page.click('.v2s-mk-mob .v2s-mk-chip.rm')
        page.wait_for_timeout(200)
    else:
        page.click('.v2s-mk-desk [data-lane="course_request"]')
        page.wait_for_timeout(250)
        lane_ids = page.evaluate("() => V2S_MARKET._state.T.cols.new.concat(V2S_MARKET._state.T.cols.waiting).map(t => t.row.kind)")
        if any(k != 'course_request' for k in lane_ids):
            PROBLEMS.append('%s03: تصفية الدورات سابت طلبات من حارة تانية: %r' % (pre, lane_ids))
        mshot(page, pre + '03-board-lane-course.jpg')
        page.click('.v2s-mk-desk [data-lane="all"]')
        page.wait_for_timeout(200)
    # أظهر التجريبي
    if w >= 761:
        page.click('.v2s-mk-desk [data-a="test"]')
        page.wait_for_timeout(200)
        if 'mk-t1' not in (tickets_in(page, 'new') + tickets_in(page, 'waiting')):
            PROBLEMS.append(pre + '03: التجريبي ما ظهرش بعد الزرّ')
        page.click('.v2s-mk-desk [data-a="test"]')
        page.wait_for_timeout(200)

    # ================================================================ الدرج
    if w < 761:
        page.click('.v2d-segb[data-col="offered"]')
    before = col_widths(page) if w >= 1180 else None
    if w < 761:
        page.click('.v2d-segb[data-col="offered"]')
    open_drawer(page, 'mk-o1')
    pos = page.evaluate("() => getComputedStyle(document.getElementById('mkOv')).position")
    if pos != 'fixed':
        PROBLEMS.append('%s04: الدرج مش position:fixed (%s)' % (pre, pos))
    if w >= 1180:
        after = col_widths(page)
        if before != after:
            PROBLEMS.append('%s04: الدرج ضيّق الأعمدة %r ⇒ %r' % (pre, before, after))
    page.wait_for_function("() => document.querySelectorAll('#mkOv .v2s-mk-offers li').length === 3", timeout=10000)
    focus_in = page.evaluate("() => document.getElementById('mkOv').contains(document.activeElement)")
    if not focus_in:
        PROBLEMS.append(pre + '04: التركيز ما دخلش الدرج')
    mshot(page, pre + '04-drawer-offers.jpg')
    close_drawer(page)
    if page.evaluate("() => document.activeElement && document.activeElement.getAttribute('data-a')") != 'open':
        PROBLEMS.append(pre + '04: التركيز ما رجعش لزرّ التذكرة بعد الإغلاق')
    # هاتف
    if w < 761:
        page.click('.v2d-segb[data-col="new"]')
    open_drawer(page, 'mk-n1')
    if not page.query_selector('#mkOv .v2s-mk-f a[href^="tel:"]'):
        PROBLEMS.append(pre + '04b: رابط الاتصال مش ظاهر في الهاتف')
    if w < 761:
        hh = page.evaluate("() => { const a = document.querySelector('#mkOv .v2s-mk-callbar .v2s-mk-call'); return a ? a.getBoundingClientRect().height : 0; }")
        if hh < 52:
            PROBLEMS.append('%s04b: زرّ «اتصل» في الموبايل أقل من ٥٢px (%s)' % (pre, hh))
    mshot(page, pre + '04b-drawer-phone.jpg')
    close_drawer(page)
    # طلب مفتوح اكتمل عدده
    if w < 761:
        page.click('.v2d-segb[data-col="waiting"]')
    expand(page)
    open_drawer(page, 'mk-w4')
    mshot(page, pre + '05-drawer-open-demand.jpg')
    close_drawer(page)

    # ================================================================ الأوراق
    # إغلاق (من الدرج) — الأول يفشل ٤٠٩ ثم ينجح
    if w < 761:
        page.click('.v2d-segb[data-col="waiting"]')
    expand(page)
    open_drawer(page, 'mk-w2')
    page.click('#mkOv [data-a="dclose"]')
    page.wait_for_selector('#epModal.v2s-mk-sh #mkGo')
    page.fill('#mkReason', 'طلب مكرر')
    mshot(page, pre + '06-sheet-close.jpg')
    h.ef.forced[('POST', '/api/bridge/market/requests/mk-w2/close')] = (409, {'detail': 'A matched request cannot be closed'})
    page.click('#mkGo')
    page.wait_for_selector('#mkErr .v2d-err')
    if 'تمّت مطابقة هذا الطلب' not in page.inner_text('#mkErr'):
        PROBLEMS.append(pre + '08: رسالة ٤٠٩ مش بالنص المتفق عليه: ' + page.inner_text('#mkErr'))
    mshot(page, pre + '08-error-409.jpg')
    del h.ef.forced[('POST', '/api/bridge/market/requests/mk-w2/close')]
    page.click('#mkGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    if [x for x in h.ef.writes if x[1].endswith('/mk-w2/close')][-1][2].get('reason') != 'طلب مكرر':
        PROBLEMS.append(pre + '06: السبب ما وصلش للمنصة')
    page.wait_for_function("() => V2S_MARKET._state.T && V2S_MARKET._state.T.cols.done.some(t => t.id === 'mk-w2')", timeout=15000)
    close_drawer(page)
    if w < 761:
        page.click('.v2d-segb[data-col="done"]')
    page.wait_for_selector('.v2s-mk .v2d-col[data-col="done"] .v2d-t[data-id="mk-w2"] .v2d-ok')
    if 'أُغلق «رأي قانوني' not in page.inner_text('.v2s-mk .v2d-t[data-id="mk-w2"]'):
        PROBLEMS.append(pre + '07: التذكرة المغلقة ما فيهاش «أُغلق «…»»')
    mshot(page, pre + '07-after-close.jpg')
    # إخفاء
    if w < 761:
        page.click('.v2d-segb[data-col="waiting"]')
    expand(page)
    open_drawer(page, 'mk-w9')
    page.click('#mkOv [data-a="dhide"]')
    page.wait_for_selector('#epModal.v2s-mk-sh #mkGo')
    mshot(page, pre + '06-sheet-hide.jpg')
    page.fill('#mkReason', 'يخالف الشروط')
    page.click('#mkGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    if not h.ef._find('mk-w9')['hidden']:
        PROBLEMS.append(pre + '06: الإخفاء ما وصلش للمنصة')
    page.wait_for_function("() => V2S_MARKET._state.T.cols.waiting.some(t => t.id === 'mk-w9' && t.row.hidden)", timeout=15000)
    page.click('#mkOv [data-a="dshow"]')
    page.wait_for_function("() => !(V2S_MARKET._state.T.cols.waiting.find(t => t.id === 'mk-w9') || {row: {hidden: true}}).row.hidden", timeout=15000)
    if h.ef._find('mk-w9')['hidden']:
        PROBLEMS.append(pre + '06: الإظهار ما وصلش للمنصة')
    close_drawer(page)
    # نقل (الزرّ الرئيسي على التذكرة)
    if w < 761:
        page.click('.v2d-segb[data-col="new"]')
    page.click('.v2s-mk .v2d-t[data-id="mk-n3"] [data-a="primary"]')
    page.wait_for_selector('#epModal.v2s-mk-sh #mkGo')
    mshot(page, pre + '06-sheet-relane.jpg')
    page.click('#mkGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    sent = [x for x in WRITES if x[0].endswith('/mk-n3/relane')]
    if not sent or sent[-1][1].get('need_kind') != 'course' or sent[-1][1].get('confirmed') is not True:
        PROBLEMS.append(pre + '06: نداء النقل: %r' % sent)
    if h.ef._find('mk-n3')['kind'] != 'course_request':
        PROBLEMS.append(pre + '06: النقل ما وصلش للمنصة')
    # ربط دورة: بدورات · وأخطاء ٤٠٤ بنوعيها
    if w < 761:
        page.click('.v2d-segb[data-col="waiting"]')
    expand(page)
    page.click('.v2s-mk .v2d-t[data-id="mk-w4"] [data-a="primary"]')
    page.wait_for_selector('#epModal.v2s-mk-sh .v2s-mk-radio')
    page.wait_for_timeout(300)
    if not page.is_disabled('#mkGo'):
        PROBLEMS.append(pre + '06: زرّ الربط شغّال من غير اختيار')
    if 'سيصل إشعار داخل المنصة لكل من انضم (٢٠)' not in page.inner_text('#epModal'):
        PROBLEMS.append(pre + '06: إشعار المنضمّين مش ظاهر')
    mshot(page, pre + '06-sheet-link.jpg')
    page.click('#epModal .v2s-mk-radio:has(input[value="contract-basics"])')
    h.ef.forced[('POST', '/api/bridge/market/requests/mk-w4/annotate')] = (404, {'detail': 'Request not found'})
    page.click('#mkGo')
    page.wait_for_selector('#mkErr .v2d-err')
    if 'هذا الطلب لم يعد موجودًا على المنصة' not in page.inner_text('#mkErr'):
        PROBLEMS.append(pre + '06b: نص ٤٠٤ للطلب: ' + page.inner_text('#mkErr'))
    mshot(page, pre + '06b-error-link-404-request.jpg')
    del h.ef.forced[('POST', '/api/bridge/market/requests/mk-w4/annotate')]
    page.click('#mkNo')
    page.wait_for_function("() => !document.getElementById('epModal')")
    seed_courses(h, [('دورة محذوفة', 'فريق البروفيسور', 'gone-course')])
    h.ef.rows = h.ef.rows
    page.evaluate("() => new Promise(r => EP.reload('courses', r))")
    page.click('.v2s-mk .v2d-t[data-id="mk-w4"] [data-a="primary"]')
    page.wait_for_selector('#epModal.v2s-mk-sh .v2s-mk-radio')
    page.click('#epModal .v2s-mk-radio:has(input[value="gone-course"])')
    page.click('#mkGo')
    page.wait_for_selector('#mkErr .v2d-err')
    if 'الدورة غير موجودة على المنصة' not in page.inner_text('#mkErr'):
        PROBLEMS.append(pre + '06b: نص ٤٠٤ للدورة: ' + page.inner_text('#mkErr'))
    mshot(page, pre + '06b-error-link-404-course.jpg')
    page.click('#mkNo')
    page.wait_for_function("() => !document.getElementById('epModal')")
    seed_courses(h, [('أساسيات صياغة العقود', 'د. هالة سمير', 'contract-basics'), ('تسويق مكتب المحاماة', 'فريق البروفيسور', 'marketing-basics')])
    page.evaluate("() => new Promise(r => EP.reload('courses', r))")
    page.click('.v2s-mk .v2d-t[data-id="mk-w4"] [data-a="primary"]')
    page.wait_for_selector('#epModal.v2s-mk-sh .v2s-mk-radio')
    page.click('#epModal .v2s-mk-radio:has(input[value="contract-basics"])')
    page.click('#mkGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    sent = [x for x in WRITES if x[0].endswith('/mk-w4/link-course')][-1:]
    if not sent or sent[-1][1] != {'course': 'contract-basics', 'confirmed': True}:
        PROBLEMS.append(pre + '06: نداء الربط: %r' % sent)
    if h.ef._find('mk-w4')['linked_course_slug'] != 'contract-basics':
        PROBLEMS.append(pre + '06: الربط ما وصلش للمنصة')
    # ربط من غير دورات على المنصة
    seed_courses(h, [])
    page.evaluate("() => new Promise(r => EP.reload('courses', r))")
    if w < 761:
        page.click('.v2d-segb[data-col="waiting"]')
    expand(page)
    page.click('.v2s-mk .v2d-t[data-id="mk-w5"] [data-a="open"]')
    page.wait_for_selector('#mkOv .v2s-mk-panel')
    page.click('#mkOv [data-a="dlink"]')
    page.wait_for_selector('#epModal.v2s-mk-sh #mkMake')
    mshot(page, pre + '06-sheet-link-none.jpg')
    # إنشاء دورة من الطلب (النافذة القديمة بتلبيس الورقة الجديدة)
    page.click('#mkMake')
    page.wait_for_selector('#epModal.v2s-mk-cc .mb.v3m #m_title')
    page.wait_for_timeout(300)
    vis_note = page.evaluate("() => { const n = document.querySelector('#epModal .note-ai'); return !!(n && n.offsetParent); }")
    if vis_note:
        PROBLEMS.append(pre + '06: ملاحظة النافذة القديمة ظاهرة')
    txt = page.inner_text('#epModal')
    for bad in ('app.elprofessor.net', 'native', 'Titch', 'per-head'):
        if bad in txt:
            PROBLEMS.append('%s06: «%s» ظاهرة في نافذة إنشاء الدورة' % (pre, bad))
    mshot(page, pre + '06-sheet-create-course.jpg')
    page.click('#epModal [data-x]')
    page.wait_for_function("() => !document.getElementById('epModal')")
    close_drawer(page)
    seed_courses(h, [('أساسيات صياغة العقود', 'د. هالة سمير', 'contract-basics'), ('تسويق مكتب المحاماة', 'فريق البروفيسور', 'marketing-basics')])

    # ================================================================ العدّاد ما يمسحش الحالة
    if w >= 761:
        expand(page)
        n_before = len(tickets_in(page, 'waiting'))
        open_drawer(page, 'mk-w1')
        texts = page.evaluate("() => [...document.querySelectorAll('.v2s-mk *')].filter(e => !e.children.length).map(e => e.textContent).join('|')")
        page.evaluate("(t) => V2S_MARKET._tick(t)", page.evaluate("() => Date.now() + 2 * 3600 * 1000"))
        n_after = len(tickets_in(page, 'waiting'))
        still = page.evaluate("() => !!document.getElementById('mkOv') && document.getElementById('mkOv').contains(document.activeElement)")
        texts2 = page.evaluate("() => [...document.querySelectorAll('.v2s-mk *')].filter(e => !e.children.length).map(e => e.textContent).join('|')")
        if n_before != n_after or n_after <= 8:
            PROBLEMS.append('%s07c: العدّاد أعاد رسم العمود (%s ⇒ %s)' % (pre, n_before, n_after))
        if not still:
            PROBLEMS.append(pre + '07c: العدّاد قفل الدرج أو سحب التركيز')
        if texts == texts2:
            PROBLEMS.append(pre + '07c: العدّاد ما غيّرش أي نص (المفروض المدة تتحدّث)')
        close_drawer(page)
    browser.close()

    # ================================================================ موظف: عرض فقط
    h.ef = mfx.MarketPlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market', BOARD_READY)
    page.evaluate("() => { window.__vm = 0; const o = window.viewMarket; window.viewMarket = function () { window.__vm++; return o.apply(this, arguments); }; role = 'employee'; }")
    page.evaluate("() => V2_HOST.openSection('market', 'requests')")
    page.wait_for_selector('.v2s-mk-ro')
    page.wait_for_timeout(300)
    if w < 761:
        page.click('.v2d-segb[data-col="new"]')
    btns = page.evaluate("() => [...document.querySelectorAll('#view button')].filter(b => b.offsetParent).map(b => b.textContent.trim())")
    bad = [b for b in btns if any(b.startswith(n) for n in ro_names)]
    if bad:
        PROBLEMS.append('%s07b: أزرار كتابة ظاهرة لموظف: %r' % (pre, bad))
    page.click('.v2s-mk .v2d-t[data-id="mk-w1"] [data-a="open"]' if w >= 761 else '.v2s-mk .v2d-t >> nth=0')
    page.wait_for_selector('#mkOv .v2s-mk-panel')
    dbtns = page.evaluate("() => [...document.querySelectorAll('#mkOv button, #mkOv a')].filter(b => b.offsetParent).map(b => b.textContent.trim())")
    if [b for b in dbtns if any(b.startswith(n) for n in ro_names) or b == 'اتصل']:
        PROBLEMS.append('%s07b: أزرار كتابة في الدرج لموظف: %r' % (pre, dbtns))
    mshot(page, pre + '07b-readonly-employee.jpg')
    if page.evaluate("() => window.__vm") != 0:
        PROBLEMS.append(pre + '07b: viewMarket القديمة اتنادت')
    close_drawer(page)
    browser.close()

    # ================================================================ الحالات: تحميل · فشل · غير متاح · فاضي
    h.ef = mfx.MarketPlatform()
    h.hold.add(('GET', '/api/platform-market-requests'))
    ctx = browser.context(h, 'admin', vp, mobile)
    page = ctx.new_page()
    watch(page)
    page.goto(DASH + '/#s/market', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-mk .v2s-mk-sk')", timeout=30000)
    page.wait_for_timeout(300)
    if '٠' in page.inner_text('.v2s-mk'):
        PROBLEMS.append(pre + '09: «٠» ظاهر وهو لسه بيحمّل')
    mshot(page, pre + '09-board-loading.jpg')
    h.hold.discard(('GET', '/api/platform-market-requests'))
    h.release_held()
    page.wait_for_function(BOARD_READY, timeout=20000)
    browser.close()

    h.ef = mfx.MarketPlatform()
    h.ef.forced[('GET', '/api/bridge/market/requests')] = (500, {'detail': 'down'})
    ctx = browser.context(h, 'admin', vp, mobile)
    page = ctx.new_page()
    watch(page)
    page.goto(DASH + '/#s/market', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-mk .v2d-warn')", timeout=30000)
    if '٠' in page.inner_text('.v2s-mk') or page.query_selector('.v2s-mk .v2d-col'):
        PROBLEMS.append(pre + '09: فشل الجلب رسم أعمدة أو صفر')
    mshot(page, pre + '09-board-failed.jpg')
    browser.close()

    h.ef = mfx.MarketPlatform()
    h.ef.missing = True
    ctx = browser.context(h, 'admin', vp, mobile)
    page = ctx.new_page()
    watch(page)
    page.goto(DASH + '/#s/market', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-mk .v2s-mk-empty')", timeout=30000)
    if 'غير متاح بعد على المنصة' not in page.inner_text('.v2s-mk'):
        PROBLEMS.append(pre + '09: بطاقة «غير متاح بعد» مش ظاهرة')
    mshot(page, pre + '09-board-missing.jpg')
    browser.close()

    h.ef = mfx.MarketPlatform(empty=True)
    ctx = browser.context(h, 'admin', vp, mobile)
    page = ctx.new_page()
    watch(page)
    page.goto(DASH + '/#s/market', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-mk .v2s-mk-empty')", timeout=30000)
    if 'لا طلبات في السوق بعد' not in page.inner_text('.v2s-mk'):
        PROBLEMS.append(pre + '09: بطاقة «لا طلبات» مش ظاهرة')
    mshot(page, pre + '09-board-empty.jpg')
    browser.close()

    # ================================================================ كل الطلبات
    h.ef = mfx.MarketPlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market/all', ALL_READY)
    page.wait_for_selector('.v2s-mk-res .v2s-mk-rl')
    above = page.evaluate("() => [...document.querySelectorAll('.v2s-mk-all > *, #mkAllBody > *')].filter(e => e.offsetParent).map(e => e.className)")
    if not any('v2s-mk-search' in c for c in above) or not any('v2s-mk-ctl' in c for c in above):
        PROBLEMS.append('%s10: فوق النتائج مفيش بحث وشريحة حارات: %r' % (pre, above))
    line = page.inner_text('.v2s-mk-rl')
    if 'تجريبي مخفي' not in line:
        PROBLEMS.append(pre + '10: سطر النتيجة من غير «تجريبي مخفي»: ' + line)
    if any(x in page.inner_text('.v2s-mk-res') for x in ('طلب تجريبي للفحص',)):
        PROBLEMS.append(pre + '10: الطلب التجريبي ظاهر والافتراضي مخفي')
    mshot(page, pre + '10-all-default.jpg')
    page.click('.v2s-mk-fbtn[data-a="afopen"]')
    page.wait_for_selector('#mkOv.v2s-mk-fs')
    page.wait_for_timeout(300)
    mshot(page, pre + '10-all-filter-sheet.jpg')
    page.click('#mkOv [data-k="status"][data-v="open"]')
    page.click('#mkOv [data-k="need"][data-v="course"]')
    page.click('#mkOv [data-a="fapply"]')
    page.wait_for_function("() => !document.getElementById('mkOv') && !document.querySelector('.v2s-mk-all .v2s-mk-sk')")
    page.click('.v2s-mk-chips [data-lane="course_request"]')
    page.wait_for_function("() => !document.querySelector('.v2s-mk-all .v2s-mk-sk')")
    page.wait_for_timeout(300)
    if 'تصفية (٢)' not in page.inner_text('.v2s-mk-fbtn'):
        PROBLEMS.append(pre + '10: عدّاد التصفية: ' + page.inner_text('.v2s-mk-fbtn'))
    if not page.query_selector('.v2s-mk-act .rm'):
        PROBLEMS.append(pre + '10: شرائح التصفية القابلة للإزالة مش ظاهرة')
    # أرقام الحارات تحت الفلتر = أرقام المجموعة المفلترة نفسها (صفر حقيقي)، وتحت حارة محدّدة بتتحفظ من استعلام «كل الأنواع» بنفس الفلاتر
    lc = page.evaluate("() => V2S_MARKET._state.all.laneCache")
    if not lc or lc['by_lane'].get('course_request') != 3 or 'طلبات الدورات (٣)' not in page.inner_text('.v2s-mk-chips.strip'):
        PROBLEMS.append(pre + '10: أرقام الحارات تحت الفلتر: %r' % lc)
    mshot(page, pre + '10-all-filtered.jpg')
    # بحث بلا نتيجة
    page.fill('#mkq', 'لا يوجد شيء بهذا الاسم')
    page.press('#mkq', 'Enter')
    page.wait_for_selector('.v2s-mk-res [data-a="aclear"]')
    mshot(page, pre + '10-all-search-none.jpg')
    page.click('.v2s-mk-res [data-a="aclear"]')
    page.wait_for_function("() => !document.querySelector('.v2s-mk-all .v2s-mk-sk') && document.querySelector('.v2s-mk-rl')")
    # صفحات: ٥٠ فوق ٥٠
    rows = [mfx.req('mk-p%03d' % i, 'طلب إضافي رقم ' + ''.join('٠١٢٣٤٥٦٧٨٩'[int(c)] for c in str(i)), h=-1.0 - i / 10.0, name='عضو', alias='عضو') for i in range(70)]
    h.ef.rows.extend(rows)
    page.click('.v2s-mk-chips [data-lane="all"]')
    page.wait_for_function("() => !document.querySelector('.v2s-mk-all .v2s-mk-sk') && document.querySelector('[data-a=\"amore\"]')")
    page.click('[data-a="amore"]')
    page.wait_for_function("() => document.querySelector('.v2s-mk-pg') && !document.querySelector('[data-a=\"amore\"]') && !document.querySelector('.v2s-mk-all .v2s-mk-sk')", timeout=15000)
    pg = page.inner_text('.v2s-mk-pg')
    if 'معروض ٩٠ من ٩٠' not in pg and 'معروض' not in pg:
        PROBLEMS.append(pre + '10: سطر الصفحات: ' + pg)
    mshot(page, pre + '10-all-paged.jpg')
    for r in rows:
        h.ef.rows.remove(r)
    # أعلى صف يفتح الدرج
    page.click('.v2s-mk-res [data-a="arow"] >> nth=0') if w >= 761 else page.click('.v2s-mk-cards [data-a="arow"] >> nth=0')
    page.wait_for_selector('#mkOv .v2s-mk-panel')
    close_drawer(page)
    browser.close()

    # عروض المدرّبين من رابط اللوحة
    h.ef = mfx.MarketPlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market', BOARD_READY)
    if w >= 761:
        page.click('.v2s-mk-desk [data-a="supply"]')
    else:
        page.click('.v2s-mk-fbtn[data-a="fopen"]')
        page.wait_for_selector('#mkOv.v2s-mk-fs')
        page.click('#mkOv [data-a="fsupply"]')
    page.wait_for_function(ALL_READY, timeout=20000)
    page.wait_for_selector('.v2s-mk-res .v2s-mk-rl')
    if page.evaluate("() => V2S_MARKET._state.all.lane") != 'training_offer' or '(مدرّب)' not in page.inner_text('.v2s-mk-res'):
        PROBLEMS.append(pre + '10: رابط «عروض المدرّبين» ما فتحش حارة العروض')
    mshot(page, pre + '10-all-supply.jpg')
    browser.close()

    # قائمة «كل الطلبات» لا تبقى قديمة: ندخلها أولًا ثم نرجع إلى اللوحة ونضغط «عروض المدرّبين» (ومرة بزرّ التجريبي)
    h.ef = mfx.MarketPlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market/all', ALL_READY)
    page.wait_for_selector('.v2s-mk-res .v2s-mk-rl')
    page.evaluate("() => V2_HOST.openSection('market', 'requests')")
    page.wait_for_function(BOARD_READY, timeout=20000)
    if w >= 761:
        page.click('.v2s-mk-desk [data-a="supply"]')
    else:
        page.click('.v2s-mk-fbtn[data-a="fopen"]')
        page.wait_for_selector('#mkOv.v2s-mk-fs')
        page.click('#mkOv [data-a="fsupply"]')
    page.wait_for_function(ALL_READY, timeout=20000)
    page.wait_for_selector('.v2s-mk-res .v2s-mk-rl')
    page.wait_for_function("() => V2S_MARKET._state.all.state === 'ready'", timeout=20000)
    page.wait_for_timeout(200)
    if not page.evaluate("() => { const A = V2S_MARKET._state.all; return A.items.length > 0 && A.items.every(i => i.kind === 'training_offer'); }"):
        PROBLEMS.append(pre + '10: بعد زيارة «كل الطلبات» ثم الرجوع، عروض المدرّبين ما غيّرتش القائمة (قائمة قديمة)')
    page.evaluate("() => V2_HOST.openSection('market', 'requests')")
    page.wait_for_function(BOARD_READY, timeout=20000)
    if w >= 761 and page.query_selector('.v2s-mk-desk .v2s-mk-chip.tog'):
        page.evaluate("() => { V2S_MARKET._state.all.lane = 'all'; }")
        page.click('.v2s-mk-desk .v2s-mk-chip.tog')
        page.evaluate("() => V2_HOST.openSection('market', 'all')")
        page.wait_for_function(ALL_READY, timeout=20000)
        page.wait_for_selector('.v2s-mk-res .v2s-mk-rl')
        page.wait_for_function("() => V2S_MARKET._state.all.state === 'ready'", timeout=20000)
        page.wait_for_timeout(200)
        if 'تجريبي مخفي' in page.inner_text('.v2s-mk-rl') or 'طلب تجريبي للفحص' not in page.inner_text('.v2s-mk-res'):
            PROBLEMS.append(pre + '10: بعد «أظهر التجريبي» في اللوحة، «كل الطلبات» ما أظهرتش التجريبي (قائمة قديمة)')
    browser.close()

    # ================================================================ ماذا يطلب الناس
    h.ef = mfx.MarketPlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market/demand', DEM_READY)
    page.wait_for_selector('.v2s-mk-crs')
    dtxt = page.inner_text('.v2s-mk-dem')
    if 'الحالة' in page.inner_text('.v2s-mk-dem .v2s-mk-tbw thead') if page.query_selector('.v2s-mk-dem .v2s-mk-tbw thead') else False:
        PROBLEMS.append(pre + '11: عمود حالة في طلبات التدريب')
    if 'لم يُسجَّل تواصل مع أحد منهم بعد' not in dtxt:
        PROBLEMS.append(pre + '11: سطر «لم يُسجَّل تواصل» ناقص')
    if 'العقل: ٩ طلبات مفتوحة بلا عرض من ٤١ خلال آخر ٩٠ يومًا' not in dtxt:
        PROBLEMS.append(pre + '11: سطر العقل في الطلب: ' + dtxt[:200])
    mshot(page, pre + '11-demand-full.jpg')
    # مصدر فاشل: لا صفر
    browser.close()
    h.ef = mfx.MarketPlatform()
    h.ef.forced[('GET', '/api/bridge/market/demand')] = (500, {'detail': 'down'})
    ctx = browser.context(h, 'admin', vp, mobile)
    page = ctx.new_page()
    watch(page)
    page.goto(DASH + '/#s/market/demand', wait_until='domcontentloaded')
    page.wait_for_function("() => document.querySelector('.v2s-mk-dem .v2d-warn') && document.querySelector('.v2s-mk-dem .v2s-mk-tbw')", timeout=30000)
    page.wait_for_timeout(400)
    if '٠' in page.inner_text('.v2s-mk-dem .v2s-mk-grid section:nth-child(1)') or 'طلبات التدريب' in page.inner_text('.v2s-mk-dem .v2d-warn'):
        PROBLEMS.append(pre + '11: مصدر الطلب فاشل ورا «٠» أو أثّر على طلبات التدريب')
    mshot(page, pre + '11-demand-failed.jpg')
    browser.close()
    h.ef = mfx.MarketPlatform()
    h.ef.training = []
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market/demand', DEM_READY)
    page.wait_for_selector('.v2s-mk-crs')
    if 'لم يسجّل أحد اهتمامًا بالتدريب بعد' not in page.inner_text('.v2s-mk-dem'):
        PROBLEMS.append(pre + '11: نص «لم يسجّل أحد اهتمامًا» ناقص')
    mshot(page, pre + '11-demand-training-empty.jpg')
    browser.close()

    # ================================================================ الرابط القديم والمربّع
    h.ef = mfx.MarketPlatform()
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#market', BOARD_READY)
    hash_ = page.evaluate("() => location.hash")
    if hash_ != '#s/market/requests':
        PROBLEMS.append('%s12: الرابط القديم هبط على %s' % (pre, hash_))
    tile = page.evaluate("() => (V2.tiles().filter(t => t.key === 'market')[0] || {}).count")
    num = page.evaluate("() => V2S_MARKET._state.T.tileCount")
    if tile != num:
        PROBLEMS.append('%s12: مربّع السوق %s ≠ سطر العقل %s' % (pre, tile, num))
    browser.close()

    # ================================================================ قائمة مقصوصة: تحذير والقائمة الكاملة في «كل الطلبات»
    h.ef = mfx.MarketPlatform()
    num = lambda i: ''.join('٠١٢٣٤٥٦٧٨٩'[int(c)] for c in str(i))
    h.ef.rows.extend([mfx.req('mk-x%03d' % i, 'طلب كثير رقم ' + num(i), h=-0.1 - i / 100.0, name='عضو', alias='عضو') for i in range(215)])
    ctx = browser.context(h, 'admin', vp, mobile)
    page = open_at(ctx, '#s/market', BOARD_READY)
    wtxt = page.inner_text('.v2s-mk .v2d-warn')
    if 'معروض ٢٠٠ من ' + num(len(h.ef.rows)) + ' طلب' not in wtxt or 'ناقصة' not in wtxt:
        PROBLEMS.append('%s01c: تحذير القائمة المقصوصة: %r' % (pre, wtxt))
    mshot(page, pre + '01c-board-truncated.jpg')
    page.click('.v2s-mk [data-a="goall"]')
    page.wait_for_function("() => location.hash === '#s/market/all'")
    browser.close()

    # ================================================================ المفتاح مقفول
    os.environ['DASH_V2_ENABLED'] = 'false'
    try:
        h.ef = mfx.MarketPlatform()
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        watch(page)
        page.goto(DASH + '/#market', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.market === 'ready' && document.querySelector('#view .policy')", timeout=30000)
        if page.query_selector('.v2s-mk') or page.query_selector('#v2Side'):
            PROBLEMS.append(pre + '13: المفتاح مقفول وفيه أثر للشاشة الجديدة')
        vs.shot(page, pre + '13-flag-off.jpg')
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/market/requests']) { const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        if bad:
            PROBLEMS.append('%s13: مسار السوق والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(mfx.MarketPlatform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            only = sys.argv[2] if len(sys.argv) > 2 else ''
            for pre, vp, mobile in (('d', DESK, False), ('t', TAB, False), ('m', MOB, True)):
                if only and only != pre:
                    continue
                flow(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls), 'writes': len(WRITES), 'problems': PROBLEMS},
                     ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
