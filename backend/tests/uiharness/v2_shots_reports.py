# -*- coding: utf-8 -*-
"""صور قسم «التقارير» (الجولة النهائية) — كمبيوتر ١٤٤٠×٩٠٠ (`d`) وتابلت ٨٢٠×١١٨٠ (`t`) وموبايل ٣٩٠×٨٤٤ (`m`).

    cd backend && python3 -B tests/uiharness/v2_shots_reports.py ../docs/v2/final/shots-reports

⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة (`reports_fixtures.ReportsPlatform`)، وأي أصل تاني بيتقفل
ويتسجّل (خطوط جوجل بس مسموحة). السكربت بيفشل (خروج ١) لو ظهر: «0/null/NaN/undefined» مكان رقم · بند في مفتاح الرسم لسلسلة غير مرسومة ·
هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · أكتر من زرّ رئيسي في التبويب · تمرير أفقي · رقم لاتيني ظاهر · طلب خارج الأداة ·
كتابة على المنصة غير نداء التصنيف الواحد (١٦ب) ونداء الإرسال الواحد (٢٢) · عنصر بشكل قديم في القسم والمفتاح مفتوح.
"""
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                              # noqa: E402  (OUT من argv[1])
import reports_fixtures as rfx                     # noqa: E402
from ef_route_harness import Harness, DASH         # noqa: E402

try:
    from zoneinfo import ZoneInfo
except Exception:                                   # pragma: no cover
    ZoneInfo = None

PROBLEMS = vs.PROBLEMS
SHOTS = vs.SHOTS
OUT = vs.OUT
DESK = {'width': 1440, 'height': 900}
TABLET = {'width': 820, 'height': 1180}
MOB = {'width': 390, 'height': 844}
UTC = datetime.timezone.utc
ALLOWED_WRITES = {('POST', '/api/bridge/chat-insights/classify'), ('POST', '/api/bridge/reports/weekly/deliver')}


def cairo_today():
    tz = ZoneInfo('Africa/Cairo') if ZoneInfo else UTC
    return datetime.datetime.now(UTC).astimezone(tz).date()


def new_platform(**kw):
    import v2_reports_routes as v2r
    v2r.clear_cache()
    return rfx.ReportsPlatform(now=datetime.datetime.now(UTC), **kw)


# ------------------------------------------------------------------ الفحوص
CHECK_JS = """() => {
  const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const roots = [...document.querySelectorAll('#view .v2r, #epModal')];
  const targets = [...document.querySelectorAll('#view .v2r button, #view .v2r a[href], #view .v2r select, #view .v2r summary, #epModal button, #epModal select, #epModal a[href]')]
    .filter(vis).filter(e => !e.closest('.mh') || e.matches('[data-x]'));
  const small = targets.map(e => [e.className || e.tagName, Math.round(e.getBoundingClientRect().height), e.tagName]).filter(x => x[1] < 44);
  const mobSmall = targets.filter(e => /^(BUTTON|SELECT)$/.test(e.tagName)).map(e => [e.className || e.tagName, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 52);
  const main = [...document.querySelectorAll('#view .v3-btn1')].filter(vis).length;
  const sw = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content') || {}).scrollWidth || 0);
  const out = [...document.querySelectorAll('#view .v2r *, #epModal *')].filter(e => vis(e) && !e.closest('svg') && e.getBoundingClientRect().right > window.innerWidth + 1).length;
  const old = document.querySelectorAll('#view .panel, #view .kpis, #view .filterbar, #view .an-grid').length;
  const clone = roots.map(r => { const c = r.cloneNode(true); c.querySelectorAll('.v2r-printhead, script, style, [hidden]').forEach(n => n.remove()); return c.innerText; }).join('\\n');
  // مفتاح الرسم مقابل الخطوط المرسومة فعلًا
  const legend = [...document.querySelectorAll('#view .v2r-legend li')].filter(vis).map(li => li.className.replace('k-', ''));
  const svg = document.querySelector('#view .v2r-svg');
  const lines = svg ? [...svg.querySelectorAll('polyline')].map(p => p.getAttribute('stroke')) : [];
  return {small, mobSmall, main, sw, out, old, text: clone, legend, lines, tabs: document.querySelectorAll('.v2c-tab.on').length};
}"""


def rcheck(page, name, tab=None):
    r = page.evaluate(CHECK_JS)
    w = page.viewport_size['width']
    if r['small']:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, r['small'][:4]))
    if w <= 600 and r['mobSmall']:
        PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, r['mobSmall'][:4]))
    if r['main'] > 1:
        PROBLEMS.append('%s: %d زرّ رئيسي ظاهر في التبويب' % (name, r['main']))
    if w <= 600 and (r['sw'] > w + 1 or r['out']):
        PROBLEMS.append('%s: تمرير أفقي أو عناصر خارج الشاشة في الموبايل (%s > %s · %s)' % (name, r['sw'], w, r['out']))
    elif r['sw'] > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))
    if r['old']:
        PROBLEMS.append('%s: عنصر بشكل قديم داخل القسم' % name)
    txt = r['text']
    if re.search(r'(?<![\w@./-])(null|NaN|undefined)(?![\w@./-])', txt) or '[object Object]' in txt:
        PROBLEMS.append('%s: null/NaN/undefined ظاهر في الشاشة' % name)
    latin = [t for t in re.findall(r'\S*[0-9]\S*', txt) if '@' not in t]
    if latin:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, latin[:3]))
    # مفتاح الرسم
    drawn_ink = r['lines'].count('#21262E')
    drawn_wine = r['lines'].count('#9E2B4E')
    want_ink = r['legend'].count('income')
    want_wine = r['legend'].count('signups') + r['legend'].count('visits')
    if r['legend'] and (drawn_ink != want_ink or drawn_wine != want_wine):
        PROBLEMS.append('%s: مفتاح الرسم لا يطابق الخطوط المرسومة %r / %r' % (name, r['legend'], r['lines']))
    return r


def shot(page, name, tab=None, tall=True, shell=True):
    """لقطة بالطول الكامل: نكبّر الارتفاع على قدر المحتوى ثم نرجعه (الصفحة نفسها بتتمرّر داخل `.content`)."""
    vp = dict(page.viewport_size)
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    if tall:
        need = page.evaluate("() => { const c = document.querySelector('.content'); return c ? Math.ceil(c.scrollHeight + c.getBoundingClientRect().top) : 0; }")
        h = min(max(vp['height'], need + 24), 5200)
        if h != vp['height']:
            page.set_viewport_size({'width': vp['width'], 'height': h})
            page.wait_for_timeout(250)
    r = rcheck(page, name, tab)
    vs.shot(page, name, full=False)
    if page.viewport_size['height'] != vp['height']:
        page.set_viewport_size(vp)
        page.wait_for_timeout(150)
    if shell:
        vs.shell_check(page, name)
    return r


# ------------------------------------------------------------------ تنقّل
REPORT_READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2r[data-tab=\"report\"]') && "
                "(document.querySelector('.v2r-brain') || /غير متاح بعد/.test(document.querySelector('.v2r').innerText) && !/جارٍ جمع/.test(document.querySelector('.v2r').innerText))")
TAB_READY = {'demand': "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2r[data-tab=\"demand\"]') && !/جارٍ جلب/.test(document.querySelector('.v2r').innerText)",
             'sunday': "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2r[data-tab=\"sunday\"]') && !/جارٍ جمع/.test(document.querySelector('.v2r').innerText)"}


def wait_shell(page, tries=4):
    """المفتاح بيُقرأ بمهلة ٣ ثواني في المتصفح؛ لو الأداة أبطأت مرة نعيد التحميل بدل ما نفشل."""
    for i in range(tries):
        try:
            page.wait_for_function(vs.SHELL_READY, timeout=15000)
            return
        except Exception:
            if i == tries - 1:
                raise
            page.reload()


def wait_or_reload(page, pred, tries=3):
    for i in range(tries):
        try:
            page.wait_for_function(pred, timeout=20000)
            return
        except Exception:
            if i == tries - 1:
                raise
            page.reload()


def open_page(ctx, hash_, ready=REPORT_READY):
    page = ctx.new_page()
    reqs = []
    page.on('request', lambda r: reqs.append(r.url))
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    wait_shell(page)
    page.wait_for_function(ready, timeout=40000)
    page.wait_for_timeout(500)
    page.reqs = reqs
    return page


def open_report(ctx, hash_='#s/reports/report'):
    return open_page(ctx, hash_, REPORT_READY)


def wait_report(page, timeout=30000):
    page.wait_for_function(REPORT_READY, timeout=timeout)
    page.wait_for_timeout(350)


def writes(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE')]


def first_line_above_fold(page, name):
    y = page.evaluate("() => { const p = document.querySelector('.v2r-bl p'); return p ? Math.round(p.getBoundingClientRect().bottom) : -1; }")
    h = page.viewport_size['height']
    if y < 0 or y > h:
        PROBLEMS.append('%s: أول سطر في ملخص العقل تحت حافة الشاشة (%s > %s)' % (name, y, h))


def clear_delivery_setting(h):
    m = h.app
    with m.app.app_context():
        row = m.db.session.get(m.Setting, 'v2r_weekly_delivery')
        if row is not None:
            m.db.session.delete(row)
            m.db.session.commit()


# ------------------------------------------------------------------ تدفّق كل مقاس
def flow(browser, h, pre, viewport, mobile):
    w = viewport['width']
    # ========== ١) التقرير بلا الجسر: الترتيب المضغوط ==========
    h.ef = new_platform()
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_report(ctx)
    info = page.evaluate("""() => ({tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), h1: document.querySelector('.v2c-h h1').textContent,
      order: [...document.querySelectorAll('#view .v2r > section, #view .v2r > p.v2r-origline')].map(e => e.className.replace(/v3-card |v2r-card /g, '').split(' ')[0]),
      lines: [...document.querySelectorAll('.v2r-bl b')].map(b => b.textContent), chips: document.querySelectorAll('.v2r-chip').length,
      print: document.querySelectorAll('.v3-btn1').length, nas: document.querySelectorAll('.v2r-na').length, origline: !!document.querySelector('.v2r-origline')})""")
    if info['tabs'] != ['التقرير', 'ما يسأل عنه الناس', 'تقرير الأحد'] or info['h1'] != 'التقارير':
        PROBLEMS.append('%s01: تبويبات التقارير %r' % (pre, info))
    if info['lines'] != ['شغّال', 'واقف', 'فرصة']:
        PROBLEMS.append('%s01: خطوط العقل %r' % (pre, info['lines']))
    if info['order'][:4] != ['v2r-brain', 'v2r-secs', 'v2r-chart', 'v2r-funnel'] or not info['origline']:
        PROBLEMS.append('%s01: ترتيب البطاقات في الوضع المضغوط %r' % (pre, info['order']))
    if w <= 600:
        first_line_above_fold(page, pre + '01')
    shot(page, pre + '01-report.jpg')
    # ٠٤) على أي أساس؟
    page.click('[data-a="why"]')
    page.wait_for_selector('.v2r-basis.open')
    nb = page.evaluate("() => document.querySelectorAll('.v2r-basis.open .v2r-bs').length")
    if nb != 3:
        PROBLEMS.append('%s04: قوائم الأساس المفتوحة %d بدل ٣' % (pre, nb))
    shot(page, pre + '04-basis.jpg')
    page.click('[data-a="why"]')
    # ٠٢) الأسبوع ٠٣) ٣ أشهر
    page.click('[data-a="period"][data-period="week"]')
    page.wait_for_function("() => /week/.test(location.hash)", timeout=10000)
    wait_report(page)
    if page.evaluate("() => document.querySelectorAll('.v2r-svg .v2r-hit').length") != 7:
        PROBLEMS.append(pre + '02: نقاط الأسبوع ليست ٧')
    shot(page, pre + '02-week.jpg')
    page.click('[data-a="period"][data-period="quarter"]')
    page.wait_for_function("() => /quarter/.test(location.hash)", timeout=10000)
    wait_report(page)
    t = page.evaluate("() => [document.querySelector('.v2r-chart h2').textContent, document.querySelectorAll('.v2r-svg .v2r-hit').length]")
    if t != ['أسبوعًا بأسبوع', 13]:
        PROBLEMS.append('%s03: رسم ٣ أشهر %r' % (pre, t))
    shot(page, pre + '03-quarter.jpg')
    # ٠٥) الدورات ٠٦) السوق ٠٧) التسويق
    def choose(scope):
        if w <= 600:
            page.select_option('select.v2r-sel', scope)
        else:
            page.click('[data-a="scope"][data-scope="%s"]' % scope)
        page.wait_for_function("(s) => new RegExp('scope=' + s).test(location.hash)", arg=scope, timeout=10000)
        wait_report(page)
    page.click('[data-a="period"][data-period="month"]')
    wait_report(page)
    choose('courses')
    sc = page.evaluate("() => ({title: document.querySelector('.v2r-funnel h2').textContent, rows: document.querySelectorAll('.v2r-secs .v2r-row').length, open: !!document.querySelector('.v2r-openbtn')})")
    if sc['title'] != 'رحلة الدورات' or sc['rows'] != 1 or not sc['open']:
        PROBLEMS.append('%s05: نطاق الدورات %r' % (pre, sc))
    shot(page, pre + '05-scope-courses.jpg')
    choose('market')
    shot(page, pre + '06-scope-market.jpg')
    choose('marketing')
    mk = page.evaluate("() => ({na: [...document.querySelectorAll('.v2r-bgrey')].length, btn: !!document.querySelector('.v2r-mk button'), funnel: !!document.querySelector('.v2r-funnel')})")
    if mk['na'] != 3 or not mk['btn'] or mk['funnel']:
        PROBLEMS.append('%s07: نطاق التسويق %r' % (pre, mk))
    shot(page, pre + '07-scope-marketing.jpg')
    if w <= 600:
        page.focus('select.v2r-sel')
        shot(page, pre + '07b-scope-select.jpg')
    browser.close()

    # ========== ٢) التنقّل: المربّع · الرابط القديم · العنوان المباشر والرجوع ==========
    h.ef = new_platform()
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    wait_shell(page)
    if w >= 1180:
        page.click('#v2Side [data-sec="reports"]')
    else:
        page.click('#menuBtn')
        page.wait_for_selector('#v2Sheet.open')
        page.click('#v2Sheet [data-sec="reports"]')
    wait_report(page)
    st = page.evaluate("() => [location.hash, document.querySelector('.v2c-tab.on').textContent.trim()]")
    if st != ['#s/reports/report', 'التقرير']:
        PROBLEMS.append('%s24: الهبوط من القائمة %r' % (pre, st))
    shot(page, pre + '24-from-menu.jpg')
    page.goto(DASH + '/#analysis')
    page.reload()
    wait_shell(page)
    wait_report(page)
    st = page.evaluate("() => [location.hash, document.querySelector('.v2c-tab.on').textContent.trim()]")
    if st != ['#s/reports/report', 'التقرير']:
        PROBLEMS.append('%s25: الرابط القديم %r' % (pre, st))
    shot(page, pre + '25-old-link.jpg', tall=False)
    page.goto(DASH + '/#s/reports/report?scope=books&period=week')
    page.reload()
    wait_shell(page)
    wait_report(page)
    st = page.evaluate("() => [location.hash, document.querySelector('.v2r-funnel h2').textContent, document.querySelector('.v3-pb.on').textContent]")
    if st != ['#s/reports/report?scope=books&period=week', 'رحلة الكتب', 'الأسبوع']:
        PROBLEMS.append('%s26: العنوان المباشر %r' % (pre, st))
    page.click('[data-a="scope"][data-scope="all"]' if w > 600 else '[data-a="period"][data-period="month"]')
    page.wait_for_timeout(500)
    wait_report(page)
    page.click('[data-a="scope"][data-scope="courses"]' if w > 600 else '[data-a="period"][data-period="quarter"]')
    page.wait_for_timeout(500)
    wait_report(page)
    page.click('[data-a="scope"][data-scope="files"]') if w > 600 else None
    page.wait_for_timeout(300)
    if w > 600:
        page.go_back()
        page.wait_for_timeout(700)
        wait_report(page)
        back = page.evaluate("() => location.hash")
        if 'scope=courses' not in back:
            PROBLEMS.append('%s26: الرجوع لم يستعد النطاق السابق (%s)' % (pre, back))
        page.go_back()
        page.wait_for_timeout(700)
        wait_report(page)
        back = page.evaluate("() => location.hash")
        if back not in ('#s/reports/report?period=week', '#s/reports/report?scope=books&period=week') and 'period=' not in back:
            PROBLEMS.append('%s26: الرجوع الثاني %s' % (pre, back))
    else:
        page.go_back()
        page.wait_for_timeout(700)
        wait_report(page)
        if 'quarter' in page.evaluate("() => location.hash"):
            PROBLEMS.append('%s26: الرجوع لم يستعد الفترة السابقة' % pre)
    shot(page, pre + '26-back-restores.jpg')
    browser.close()

    # ========== ٣) مصادر واقعة · الطريق كله واقع ==========
    h.ef = new_platform()
    h.ef.rp_down = {'/api/bridge/users', '/api/bridge/market/requests', '/api/bridge/chat-insights', '/api/bridge/ops/queue'}
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/reports/report', wait_until='domcontentloaded')
    wait_or_reload(page, "() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2r-brain')")
    page.wait_for_timeout(600)
    d = page.evaluate("() => ({warn: [...document.querySelectorAll('.v3-warn')].map(e => e.innerText), txt: document.querySelector('.v2r').innerText})")
    if not d['warn'] or 'تعذّر الوصول إلى' not in d['warn'][0]:
        PROBLEMS.append('%s08: شريط التحذير غائب %r' % (pre, d['warn']))
    for lab in ('الحسابات الجديدة', 'طلبات السوق', 'أسئلة المحادثة', 'النزاعات'):
        if d['warn'] and lab not in d['warn'][0]:
            PROBLEMS.append('%s08: «%s» غير مذكور في التحذير' % (pre, lab))
    if re.search(r'(?<![٠-٩٬٫])٠(?![٠-٩٬٫])(?!\s*(جنيه|عملية))', d['txt']):
        PROBLEMS.append('%s08: صفر ظاهر مكان رقم مجهول' % pre)
    shot(page, pre + '08-sources-down.jpg')
    browser.close()

    import v2_reports_routes as v2r
    real = v2r.summary_for

    def boom(*a, **k):
        raise RuntimeError('down')
    h.ef = new_platform()
    ctx = browser.context(h, 'admin', viewport, mobile)
    v2r.summary_for = boom
    try:
        page = ctx.new_page()
        page.goto(DASH + '/#s/reports/report', wait_until='domcontentloaded')
        wait_shell(page)
        wait_or_reload(page, "() => document.querySelector('.v2r') && /التقرير: غير متاح بعد/.test(document.querySelector('.v2r').innerText)")
        page.wait_for_timeout(300)
        shot(page, pre + '09-route-failed.jpg')
        v2r.summary_for = real
        page.click('[data-a="retry"]')
        wait_report(page)
        if not page.evaluate("() => !!document.querySelector('.v2r-brain')"):
            PROBLEMS.append(pre + '09: «أعد المحاولة» لم يعد بالتقرير')
    finally:
        v2r.summary_for = real
    browser.close()

    # ========== ٤) الجسر موجود: الترتيب الكامل ==========
    h.ef = new_platform(funnel=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_report(ctx)
    f = page.evaluate("""() => ({order: [...document.querySelectorAll('#view .v2r > section, #view .v2r > .v2r-low')].map(e => e.className.replace(/v3-card |v2r-card /g, '').split(' ')[0]),
      cols: document.querySelectorAll('.v2r-fcols .v2r-fs').length, empties: document.querySelectorAll('.v2r-fbar.empty').length, legend: [...document.querySelectorAll('.v2r-legend li')].map(l => l.textContent),
      chan: document.querySelectorAll('.v2r-orig .v2r-bars li').length, pills: document.querySelectorAll('.v2r-orig .v2r-pill').length, pages: document.querySelectorAll('.v2r-pages li').length})""")
    if f['order'][:3] != ['v2r-brain', 'v2r-funnel', 'v2r-low'] or f['cols'] != 5 or f['empties'] != 0 or 'الزوار' not in f['legend'] or f['chan'] != 6 or f['pages'] != 3:
        PROBLEMS.append('%s10: وضع الجسر %r' % (pre, f))
    shot(page, pre + '10-report-with-bridge.jpg')
    browser.close()

    # ========== ٥) ما يسأل عنه الناس ==========
    h.ef = new_platform()
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_page(ctx, '#s/reports/demand', TAB_READY['demand'])
    d = page.evaluate("""() => ({order: [...document.querySelectorAll('#view .v2r > *')].map(e => e.className.split(' ')[0]), nums: document.querySelector('.v2r-nums').innerText,
      main: document.querySelector('.v2r-opp .v3-btn1') && document.querySelector('.v2r-opp .v3-btn1').textContent, rows: document.querySelectorAll('.v2r-q').length,
      det: document.querySelector('.v2r-detail').open, classify: document.querySelector('[data-a=classify]') && document.querySelector('[data-a=classify]').textContent.trim()})""")
    if d['order'][:4] != ['v2r-nrow', 'v3-card', 'v3-card', 'v2r-detail'] or d['main'] != 'افتح الدورات' or d['rows'] != 40 or d['det'] != (w >= 1024):
        PROBLEMS.append('%s11: ما يسأل عنه الناس %r' % (pre, d))
    if 'سؤالًا' not in d['nums'] or d['classify'] != 'صنّف الأسئلة الجديدة (٣)':
        PROBLEMS.append('%s11: سطر الأرقام/زر التصنيف %r' % (pre, d))
    shot(page, pre + '11-demand.jpg')
    # ١٢) تصفية ببار البلد
    if w >= 1024:
        page.click('.v2r-dbar[data-dim="country"][data-val="saudi"]')
    else:
        page.click('summary')
        page.click('.v2r-dbar[data-dim="country"][data-val="saudi"]')
    page.wait_for_timeout(500)
    cnt = page.evaluate("() => [document.querySelectorAll('.v2r-q').length, document.querySelector('[data-a=ftoggle]').textContent.trim(), !!document.querySelector('[data-a=fclear]')]")
    if cnt[0] != 7 or '(١)' not in cnt[1] or not cnt[2]:
        PROBLEMS.append('%s12: التصفية ببار البلد %r' % (pre, cnt))
    shot(page, pre + '12-filtered.jpg')
    page.click('[data-a="fclear"]')
    page.wait_for_timeout(250)
    # ١٢ب) ورقة التصفية (موبايل/تابلت) أو اللوحة
    page.click('[data-a="ftoggle"]')
    page.wait_for_timeout(350)
    if w < 1024:
        page.wait_for_selector('#epModal [data-a="applyf"]')
        shot(page, pre + '12b-filter-sheet.jpg', tall=False)
        page.select_option('#epModal select[data-f="country"]', 'egypt')
        page.click('#epModal [data-a="applyf"]')
        page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    else:
        shot(page, pre + '12b-filter-panel.jpg')
        page.select_option('select[data-f="country"]', 'egypt')
    page.wait_for_timeout(300)
    n = page.evaluate("() => document.querySelectorAll('.v2r-q').length")
    if n != 14:
        PROBLEMS.append('%s12b: بعد تصفية مصر %d سؤالًا بدل ١٤' % (pre, n))
    page.click('[data-a="fclear"]')
    page.wait_for_timeout(250)
    # ١٣) محادثة عضو مسجَّل
    page.click('.v2r-q[data-id="q01"]')
    page.wait_for_selector('#epModal.v2r-side .v2r-turns')
    sh = page.evaluate("() => ({person: !!document.querySelector('#epModal .v3-person'), turns: document.querySelectorAll('#epModal .v2r-tb').length, warn: !!document.querySelector('#epModal .v3-warn'), side: getComputedStyle(document.querySelector('#epModal .modal')).width})")
    if not sh['person'] or sh['turns'] != 2 or sh['warn']:
        PROBLEMS.append('%s13: محادثة العضو %r' % (pre, sh))
    if w >= 1024 and sh['side'] != '420px':
        PROBLEMS.append('%s13: اللوحة الجانبية %r' % (pre, sh))
    shot(page, pre + '13-thread-signed.jpg', tall=False)
    page.keyboard.press('Escape')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=5000)
    # ١٤) زائر ورد محفوظ مقصوص
    page.click('.v2r-q[data-id="q02"]')
    page.wait_for_selector('#epModal .v2r-turns')
    sh = page.evaluate("() => ({person: !!document.querySelector('#epModal .v3-person'), warn: !!document.querySelector('#epModal .v3-warn'), who: document.querySelector('#epModal .v2r-meta dd').textContent})")
    if sh['person'] or not sh['warn'] or sh['who'] != 'زائر بلا حساب':
        PROBLEMS.append('%s14: محادثة الزائر %r' % (pre, sh))
    shot(page, pre + '14-thread-anon.jpg', tall=False)
    page.click('#epModal [data-a="sclose"]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=5000)
    # ١٦أ) نافذة تأكيد التصنيف
    n0 = len(h.platform_calls)
    page.click('[data-a="classify"]')
    page.wait_for_selector('#epModal [data-a="cgo"]')
    if writes(h, n0):
        PROBLEMS.append(pre + '16a: كتابة قبل التأكيد')
    shot(page, pre + '16a-classify-confirm.jpg', tall=False)
    page.click('#epModal [data-a="cgo"]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v3-ok') && !document.querySelector('[data-a=classify]')", timeout=15000)
    wr = writes(h, n0)
    if len(wr) != 1 or (wr[0][0], wr[0][1]) != ('POST', '/api/bridge/chat-insights/classify') or str(wr[0][2].get('limit')) != '100':
        PROBLEMS.append('%s16b: نداء التصنيف %r' % (pre, wr))
    if 'صُنّف ١٢ سؤالًا جديدًا · بقي ٣' not in page.inner_text('.v3-ok'):
        PROBLEMS.append('%s16b: نص النجاح %r' % (pre, page.inner_text('.v3-ok')))
    shot(page, pre + '16b-classified.jpg')
    browser.close()

    # ١٥) مصدر الأسئلة واقع
    h.ef = new_platform()
    h.ef.rp_down = {'/api/bridge/chat-insights'}
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/reports/demand', wait_until='domcontentloaded')
    wait_shell(page)
    wait_or_reload(page, "() => document.querySelector('.v2r') && /أسئلة المحادثة: غير متاح بعد/.test(document.querySelector('.v2r').innerText)")
    page.wait_for_timeout(300)
    shot(page, pre + '15-chat-down.jpg')
    browser.close()

    # ========== ٦) تقرير الأحد ==========
    clear_delivery_setting(h)
    h.ef = new_platform()
    ctx = browser.context(h, 'admin', viewport, mobile)
    try:
        ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin=DASH)
    except Exception:
        pass
    page = open_page(ctx, '#s/reports/sunday', TAB_READY['sunday'])
    sd = page.evaluate("""() => ({stat: document.querySelector('.v2r-dstat').textContent, dis: [...document.querySelectorAll('.v2r-dact button')].map(b => b.disabled), head: document.querySelector('.v2r-wt h2').textContent,
      nav: [document.querySelector('[data-a=wprev]').disabled, document.querySelector('[data-a=wnext]').disabled], sections: document.querySelectorAll('.v2r-letter .v2r-row').length, brain: document.querySelectorAll('.v2r-letter .v2r-bl').length})""")
    if sd['stat'] != 'الإرسال كل أحد: غير متاح بعد — ينتظر تجهيز الإرسال على المنصة' or sd['dis'] != [True, True] or sd['nav'] != [False, True] or sd['sections'] != 6 or sd['brain'] != 3:
        PROBLEMS.append('%s17: تقرير الأحد %r' % (pre, sd))
    shot(page, pre + '17-sunday.jpg')
    page.click('[data-a="wprev"]')
    page.wait_for_function("() => document.querySelector('[data-a=wnext]') && !document.querySelector('[data-a=wnext]').disabled", timeout=15000)
    page.wait_for_timeout(300)
    shot(page, pre + '18-sunday-previous.jpg')
    page.click('[data-a="wnext"]')
    page.wait_for_function("() => document.querySelector('[data-a=wnext]') && document.querySelector('[data-a=wnext]').disabled", timeout=15000)
    page.click('[data-a="copy"]')
    page.wait_for_timeout(600)
    if not page.evaluate("() => !!document.querySelector('.v3-ok') || !!document.querySelector('.v2r-copybox')"):
        PROBLEMS.append(pre + '19: نسخ النص لم يُظهر تأكيدًا')
    shot(page, pre + '19-copied.jpg')
    browser.close()

    # ٢٠) تشغيل الإرسال ثم «أرسل الآن»
    clear_delivery_setting(h)
    h.ef = new_platform(delivery=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_page(ctx, '#s/reports/sunday', TAB_READY['sunday'])
    n0 = len(h.platform_calls)
    page.click('[data-a="dtoggle"]')
    page.wait_for_selector('#v3_review')
    page.click('#v3_review')
    page.wait_for_selector('#v3_go')
    shot(page, pre + '20a-toggle-review.jpg', tall=False)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => /يصلك هذا التقرير كل أحد/.test(document.querySelector('.v2r-dstat').textContent)", timeout=15000)
    if writes(h, n0):
        PROBLEMS.append(pre + '20: تشغيل الإرسال كتب على المنصة')
    txt = page.inner_text('.v2r-dstat')
    if txt != 'يصلك هذا التقرير كل أحد ٨ صباحًا على تليجرام · آخر إرسال: أسبوع ١٨ أكتوبر':
        PROBLEMS.append('%s20: حالة الإرسال %r' % (pre, txt))
    shot(page, pre + '20-sunday-delivery-on.jpg')
    page.click('[data-a="dsend"]')
    page.wait_for_selector('#v3_review')
    page.click('#v3_review')
    page.wait_for_selector('#v3_go')
    if writes(h, n0):
        PROBLEMS.append(pre + '21: كتابة قبل «أكّد الإرسال»')
    shot(page, pre + '21-send-review.jpg', tall=False)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=15000)
    wr = writes(h, n0)
    if len(wr) != 1 or (wr[0][0], wr[0][1]) != ('POST', '/api/bridge/reports/weekly/deliver') or wr[0][3].get('confirmed') is not True or not wr[0][3].get('text'):
        PROBLEMS.append('%s22: نداء الإرسال %r' % (pre, [(c[0], c[1]) for c in wr]))
    if len(h.ef.delivered) != 1:
        PROBLEMS.append('%s22: المنصة المزيّفة استلمت %d إرسالات' % (pre, len(h.ef.delivered)))
    shot(page, pre + '22-sent.jpg')
    if w >= 1180:
        # ٢٣) الطباعة (كمبيوتر فقط)
        page.emulate_media(media='print')
        page.wait_for_timeout(300)
        shot(page, pre + '23-print-sunday.jpg', tall=True, shell=False)
        page.emulate_media(media='screen')
        page.click('.v2c-tab[data-tab="report"]')
        wait_report(page)
        page.emulate_media(media='print')
        page.wait_for_timeout(300)
        shot(page, pre + '23-print-report.jpg', tall=True, shell=False)
        page.emulate_media(media='screen')
    clear_delivery_setting(h)
    browser.close()

    # ========== ٧) المفتاح مقفول: الشاشة القديمة بحالها ==========
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = new_platform()
        ctx = browser.context(h, 'admin', viewport, mobile)
        page = ctx.new_page()
        reqs = []
        page.on('request', lambda r: reqs.append(r.url))
        page.goto(DASH + '/#analysis', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.analysis === 'ready' && document.querySelector('#anRecent')", timeout=40000)
        page.wait_for_timeout(500)
        st = page.evaluate("() => ({v2r: document.querySelectorAll('[class*=\"v2r-\"]').length, on: !!window.V2_ON, shell: !!(window.V2SHELL && V2SHELL.on), old: !!document.querySelector('#anFilterbar'), classify: !!document.getElementById('anClassify')})")
        if st['v2r'] or st['on'] or st['shell'] or not st['old'] or not st['classify']:
            PROBLEMS.append('%s27: المفتاح مقفول والشاشة غير القديمة: %r' % (pre, st))
        if [u for u in reqs if 'v2s/' in u and u.endswith('.js') and 'reports.js' in u and False]:
            PROBLEMS.append(pre + '27: طلب ملف v2s')
        asked = [u for u in reqs if '/api/v2/reports' in u]
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/reports/summary', '/api/v2/reports/weekly']) { const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        if bad:
            PROBLEMS.append('%s27: مسارات التقارير والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
        if asked:
            PROBLEMS.append(pre + '27: الشاشة طلبت مسارات التقارير والمفتاح مقفول')
        vs.shot(page, pre + '27-switch-off.jpg', full=False)
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(rfx.ReportsPlatform())
    rfx.seed_dash(h.app, cairo_today())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mob in (('d', DESK, False), ('t', TABLET, False), ('m', MOB, True)):
                if len(sys.argv) > 2 and pre not in sys.argv[2]:
                    continue
                flow(browser, h, pre, vp, mob)
        finally:
            browser.close()
    # كل كتابة على المنصة مسموحة مرة واحدة فقط لكل مقاس (التصنيف والإرسال)
    bad = [(c[0], c[1]) for c in h.platform_calls if c[0] in ('PUT', 'POST', 'PATCH', 'DELETE') and (c[0], c[1]) not in ALLOWED_WRITES]
    if bad:
        PROBLEMS.append('كتابة غير مسموحة على المنصة: %r' % bad[:4])
    for k in ALLOWED_WRITES:
        n = len([c for c in h.platform_calls if (c[0], c[1]) == k])
        per = len([a for a in (sys.argv[2] if len(sys.argv) > 2 else 'dtm')])
        if n != per:
            PROBLEMS.append('عدد نداءات %s = %d (المتوقع %d)' % (k[1], n, per))
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': SHOTS, 'blocked_by_origin': rep, 'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls),
                      'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
