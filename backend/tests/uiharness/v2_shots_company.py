# -*- coding: utf-8 -*-
"""لقطات قسم «الشركة ورأس المال» (SPEC-company §11) — كمبيوتر ١٤٤٠ (`d`) · تابلت ٨٢٠ (`t`) · موبايل ٣٩٠ (`m`) (الارتفاع طويل ليظهر المحتوى كله).

    cd backend && python3 -B tests/uiharness/v2_shots_company.py ../docs/v2/final/shots-company

⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة في الذاكرة. السكربت بيفشل لو: «undefined/NaN/null/[object Object]» ظاهرة · أكثر من `.co-btn1` ظاهر
(في الصفحة أو في ورقة مفتوحة) · صف فيه أكثر من `.co-btn2` · تبويب نشط بره شريط التبويبات في الموبايل · `input[type=month]` · عنصر `data-na` لا يقول «غير متاح بعد» ·
تمرير أفقي في الموبايل · زر أقل من ٤٤px (٥٢px في الموبايل) أو بره الشاشة · نداء كتابة من غير `confirmed:true` · أي طلب بره localhost (غير خطوط جوجل) ·
أي أثر لـ`.co` والمفتاح مقفول.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                         # noqa: E402  (يُستورد ولا يُعدَّل)
import d3_fixtures as d3fx                    # noqa: E402
import co_fixtures as cof                     # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

OUT = vs.OUT
PROBLEMS = vs.PROBLEMS
DESK = {'width': 1440, 'height': 1700}
TABL = {'width': 820, 'height': 1900}
MOBL = {'width': 390, 'height': 2700}
CONFIRMED = [('POST', r'/contributions$'), ('DELETE', r'/contributions/\d+$'), ('POST', r'/subscriptions/import$'), ('POST', r'/subscriptions/\d+/paid$'),
             ('DELETE', r'/subscriptions/\d+$'), ('POST', r'/agreements/\d+/renew$'), ('DELETE', r'/agreements/\d+$'), ('DELETE', r'/ad-clients/\d+$'),
             ('DELETE', r'/ad-results/\d+$'), ('POST', r'/income$')]


def ready(board):
    return ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.co[data-board=\"%s\"]') && !/…جارٍ جلب/.test(document.querySelector('.co').innerText)" % board)


class Rec(object):
    def __init__(self, ctx):
        self.reqs = []
        ctx.on('request', lambda r: self.reqs.append((r.method, r.url, r.post_data)) if '/api/v2/company/' in r.url or '/api/assets' in r.url or '/api/partners' in r.url else None)

    def writes(self, since=0):
        return [x for x in self.reqs[since:] if x[0] in ('POST', 'PUT', 'DELETE')]


def check_confirmed(rec, name):
    for m, url, body in rec.writes():
        for mm, pat in CONFIRMED:
            if m == mm and re.search(pat, url.split('?')[0]):
                try:
                    ok = json.loads(body or '{}').get('confirmed') is True
                except Exception:
                    ok = False
                if not ok:
                    PROBLEMS.append('%s: كتابة بلا confirmed:true — %s %s' % (name, m, url))


def check(page, name):
    w = page.viewport_size['width']
    txt = page.evaluate("() => document.body.innerText")
    for bad in ('undefined', 'NaN', '[object Object]'):
        if bad in txt:
            PROBLEMS.append('%s: «%s» ظاهرة' % (name, bad))
    if re.search(r'(?<![\w@./-])null(?![\w@./-])', txt):
        PROBLEMS.append('%s: «null» ظاهرة' % name)
    r = page.evaluate("""() => {
      const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
      const modal = document.getElementById('epModal');
      const pageBtn1 = [...document.querySelectorAll('.co .co-btn1')].filter(vis).length;
      const modalBtn1 = modal ? [...modal.querySelectorAll('.co-btn1')].filter(vis).length : 0;
      const rows = [...document.querySelectorAll('.co-lr, .co-tr')].filter(vis).filter(r => [...r.querySelectorAll('.co-btn2')].filter(vis).length > 1).length;
      const months = document.querySelectorAll('input[type=month]').length;
      const na = [...document.querySelectorAll('[data-na]')].filter(e => e.textContent.trim() !== 'غير متاح بعد').map(e => e.textContent.trim());
      const btns = [...document.querySelectorAll('.co button, .co input[type=text], .co select, .co textarea, #epModal .com button, #epModal .com input, #epModal .com select, #epModal .com textarea')].filter(vis);
      const small = btns.map(b => [b.className || b.tagName, Math.round(((b.type === 'checkbox' && b.closest('label')) ? b.closest('label') : b).getBoundingClientRect().height)]).filter(x => x[1] < 44);
      const small52 = [...document.querySelectorAll('.co-btn1, .co-btn2, #epModal .com .co-btn1, #epModal .com .co-btn2')].filter(vis).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52);
      const outside = btns.filter(b => { const q = b.getBoundingClientRect(); return q.left < -1 || q.right > window.innerWidth + 1; }).length;
      const strip = document.querySelector('.v2c-tabs'), on = document.querySelector('.v2c-tab.on');
      let tabIn = true;
      if (strip && on) { const s = strip.getBoundingClientRect(), o = on.getBoundingClientRect(); tabIn = o.left >= s.left - 1 && o.right <= s.right + 1; }
      return {pageBtn1, modalBtn1, rows, months, na, small, small52, outside, tabIn,
              sw: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content') || {}).scrollWidth || 0)};
    }""")
    if r['pageBtn1'] > 1:
        PROBLEMS.append('%s: %d زرّ رئيسي ظاهر في الصفحة' % (name, r['pageBtn1']))
    if r['modalBtn1'] > 1:
        PROBLEMS.append('%s: %d زرّ رئيسي في الورقة' % (name, r['modalBtn1']))
    if r['rows']:
        PROBLEMS.append('%s: %d صف فيه أكثر من فعل ظاهر' % (name, r['rows']))
    if r['months']:
        PROBLEMS.append('%s: input[type=month] موجود' % name)
    if r['na']:
        PROBLEMS.append('%s: data-na بنص غلط %r' % (name, r['na'][:3]))
    if r['small']:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px %r' % (name, r['small'][:4]))
    if w <= 400:
        if r['small52']:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل %r' % (name, r['small52'][:4]))
        if r['sw'] > w + 1:
            PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))
        if not r['tabIn']:
            PROBLEMS.append('%s: التبويب النشط خارج شريط التبويبات' % name)
    if r['outside']:
        PROBLEMS.append('%s: %d زرّ بره عرض الشاشة' % (name, r['outside']))


def snap(page, name):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    vs.shot(page, name)
    vs.shell_check(page, name)
    check(page, name)


def open_tab(h, browser, vp, mobile, hash_, board, rec_holder=None, routes=None):
    ctx = browser.context(h, 'admin', vp, mobile)
    rec = Rec(ctx)
    for pat, status in (routes or []):
        ctx.route(pat, (lambda st: (lambda route, *a: route.fulfill(status=st, content_type='application/json', body='{"error":"x"}')))(status))
    page = ctx.new_page()
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    for attempt in range(5):                           # ردّ مفتاح اللوحة له ٣ ثواني فقط، فالفتحة الباردة/البطيئة بتتعاد
        try:
            page.wait_for_function(vs.SHELL_READY, timeout=12000)
            break
        except Exception:
            if attempt == 4:
                raise
            page.reload(wait_until='domcontentloaded')
    page.wait_for_function(ready(board), timeout=30000)
    page.wait_for_timeout(500)
    return page, rec


def fresh(h):
    h.ef = d3fx.D3Platform(d2=True)
    h.ef.forced[('GET', '/api/bridge/visits/by-ref')] = (404, {'detail': 'Not Found'})
    return cof.seed_dash(h.app)


def db_count(h, model):
    with h.app.app.app_context():
        return h.app.db.session.query(model).count()


def sheet_wait(page):
    page.wait_for_selector('#epModal .com')
    page.wait_for_timeout(250)


def flow(browser, h, pre, vp, mobile):
    m = h.app
    import v2_company_routes as co
    # —— ٣) أول مرة (قاعدة فاضية)
    fresh(h)
    cof.clear_dash(h.app)
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/invest', 'invest')
    if not page.query_selector('.co-hero') or page.query_selector('.co-grid'):
        PROBLEMS.append(pre + '03: شاشة أول مرة ناقصة')
    snap(page, pre + '03-board-first-run.jpg')
    page.click('.co-hero [data-a="addPartner"]')
    sheet_wait(page)
    snap(page, pre + '03b-first-run-partner-sheet.jpg')
    # —— ١) اللوحة
    ids = fresh(h)
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/invest', 'invest')
    info = page.evaluate("""() => ({tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), lines: document.querySelectorAll('.co-brain:not(.tg) .co-bl').length,
      cards: [...document.querySelectorAll('.co-card .co-ch h2')].map(e => e.textContent.trim()), txt: document.querySelector('.co').innerText})""")
    if info['tabs'] != ['نظرة', 'الشركاء ورأس المال', 'المعدات والاشتراكات', 'الاتفاقات والرعاة', 'عملاء الإعلانات', 'الإعدادات']:
        PROBLEMS.append('%s01: التبويبات %r' % (pre, info['tabs']))
    if info['lines'] != 3 or 'غطّاه منذ' not in info['txt'] or '٤٠٠٬٠٠٠ جنيه' not in info['txt'] or '٣٧٥٬٠٠٠ جنيه' not in info['txt'] or 'باقٍ ٢٥٬٠٠٠ جنيه' not in info['txt']:
        PROBLEMS.append('%s01: أرقام اللوحة غير مطابقة للوحة المفاهيم %r' % (pre, info['lines']))
    snap(page, pre + '01-board.jpg')
    # —— ٢) الملخّص واقع والشركاء محمّلون
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/invest', 'invest', routes=[('**/api/v2/company/summary', 500)])
    d = page.evaluate("() => ({rows: document.querySelectorAll('.co-c-partners .co-pr').length, na: [...document.querySelectorAll('.co-c-partners [data-na]')].length, eq: !!document.querySelector('.co-c-partners .co-eq'),"
                      " chips: document.querySelectorAll('.co-c-partners .co-pr .co-st').length, txt: document.querySelector('.co-c-partners').innerText, warn: (document.querySelector('.co-warn')||{}).innerText||''})")
    if d['rows'] < 3 or not d['eq'] or d['chips'] or d['na'] < 1 or 'المتفق عليه' not in d['txt'] or 'ملخّص الشركة' not in d['warn']:
        PROBLEMS.append('%s02: كارت الشركاء بلا الملخّص مش كما في المواصفة %r' % (pre, d))
    snap(page, pre + '02-board-sources-down.jpg')
    # —— ٤) الشركاء ورأس المال
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/partners', 'partners')
    snap(page, pre + '04-partners.jpg')
    n_c = db_count(h, co.M['Contribution'])
    page.click('.co-top [data-a="contribution"]')
    sheet_wait(page)
    page.select_option('#co_ck', 'asset')
    page.select_option('#co_cp', str(ids['investor']))
    page.fill('#co_ca', '25000')
    page.fill('#co_cn', 'كاميرا مساعدة')
    snap(page, pre + '05-contribution-form.jpg')
    page.click('[data-s="go"]')
    page.wait_for_selector('.co-s2:not([hidden])')
    snap(page, pre + '06-contribution-review.jpg')
    n_assets0 = db_count(h, m.Asset)
    page.click('[data-s="confirm"]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.co-ok')", timeout=10000)
    if db_count(h, co.M['Contribution']) != n_c + 1 or db_count(h, m.Asset) != n_assets0 + 1:
        PROBLEMS.append(pre + '06: الدفعة أو المعدة المرتبطة ما اتسجّلتش')
    page.wait_for_timeout(500)
    snap(page, pre + '06b-after-contribution.jpg')
    check_confirmed(rec, pre + '06')
    # —— ٧) المعدات والاشتراكات
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/assets', 'assets')
    if not page.query_selector('.co-amber.strip') or '١٬٨٠٠' not in page.inner_text('.co-amber.strip') and 'اشتراك' not in page.inner_text('.co-amber.strip'):
        PROBLEMS.append(pre + '07: شريط الاشتراكات القديمة ناقص')
    snap(page, pre + '07-assets.jpg')
    page.click('.co-amber.strip [data-a="importSubs"]')
    sheet_wait(page)
    page.click('[data-s="go"]')
    page.wait_for_selector('.co-s2:not([hidden])')
    snap(page, pre + '07b-subs-import-review.jpg')
    n_sub = db_count(h, co.M['Subscription'])
    page.click('[data-s="confirm"]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(900)
    if db_count(h, co.M['Subscription']) != n_sub + 1 or page.query_selector('.co-amber.strip'):
        PROBLEMS.append(pre + '07b: نقل الاشتراك القديم ما اشتغلش')
    check_confirmed(rec, pre + '07b')
    snap(page, pre + '07c-after-import.jpg')
    page.click('.co-lr[data-id^="s"] [data-a="paySub"] >> nth=0')
    sheet_wait(page)
    page.click('[data-s="go"]')
    page.wait_for_selector('.co-s2:not([hidden])')
    snap(page, pre + '08-subscription-paid-review.jpg')
    page.click('[data-s="back"]')
    page.click('[data-s="cancel"]')
    # —— ٩) الاتفاقات والرعاة
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/deals', 'deals')
    page.wait_for_function("() => document.querySelector('.co-info')", timeout=20000)
    if 'لم يُفعَّل بعد' not in page.inner_text('.co') or page.query_selector('.co-vis'):
        PROBLEMS.append(pre + '09: شريط الزيارات أو سطر الزيارات غلط')
    snap(page, pre + '09-deals.jpg')
    page.click('.co-lr.deal [data-a="more"] >> nth=0')
    sheet_wait(page)
    snap(page, pre + '09b-deal-more.jpg')
    page.click('#epModal [data-x]')
    page.click('.co-lr.deal [data-a="renewDeal"] >> nth=0')
    sheet_wait(page)
    page.click('[data-s="go"]')
    page.wait_for_selector('.co-s2:not([hidden])')
    snap(page, pre + '10-agreement-renew-review.jpg')
    page.click('[data-s="confirm"]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(800)
    with m.app.app_context():
        ended = m.db.session.query(co.M['Agreement']).filter_by(id=ids['smart']).one().status
    if ended != 'ended':
        PROBLEMS.append(pre + '10: التجديد ما أنهاش القديم')
    check_confirmed(rec, pre + '10')
    # —— ١١) عملاء الإعلانات
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/ads', 'ads')
    page.wait_for_function("() => document.querySelector('.co-info')", timeout=20000)
    snap(page, pre + '11-ads.jpg')
    page.click('.co-cl [data-a="statement"] >> nth=0')
    sheet_wait(page)
    if not page.query_selector('#coStmt'):
        PROBLEMS.append(pre + '12: كشف الحساب ما ظهرش')
    snap(page, pre + '12-statement.jpg')
    page.click('#epModal [data-x]')
    page.click('.co-top [data-a="statements"]')
    sheet_wait(page)
    snap(page, pre + '12b-statements-all.jpg')
    page.click('#epModal [data-x]')
    # ١٣) تحصيل نتيجة لم تُرسل: افتح كشفها ثم «سجّل التحصيل»
    page.click('.co-cl >> nth=0 >> [data-a="statement"] >> nth=0')
    sheet_wait(page)
    page.click('#epModal .co-link[data-s="collect"]')
    sheet_wait(page)
    page.click('[data-s="go"]')
    page.wait_for_selector('.co-s2:not([hidden])')
    snap(page, pre + '13-collect-review.jpg')
    n_rev = db_count(h, m.Revenue)
    page.click('[data-s="confirm"]')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(800)
    if db_count(h, m.Revenue) != n_rev + 1:
        PROBLEMS.append(pre + '13: التحصيل ما اتسجّلش في الدخل')
    check_confirmed(rec, pre + '13')
    # —— ١٤) الرابط القديم #targets
    page, rec = open_tab(h, browser, vp, mobile, '#targets', 'invest')
    page.wait_for_timeout(700)
    pos = page.evaluate("() => { const t = document.getElementById('coTargets'); if (!t) return null; const r = t.getBoundingClientRect(); return [Math.round(r.top), window.innerHeight, location.hash]; }")
    if not pos or pos[2] != '#s/company/invest' or pos[0] > pos[1] - 60:
        PROBLEMS.append('%s14: #targets ما هبطش على «الأهداف الشهرية» %r' % (pre, pos))
    snap(page, pre + '14-old-link-targets.jpg')
    # —— ١٥) ورقة هدف شهر (قائمتا الشهر والسنة)
    page.click('[data-a="addForecast"]')
    sheet_wait(page)
    if len(page.query_selector_all('#epModal select')) != 2 or page.query_selector('#epModal input[type=month]'):
        PROBLEMS.append(pre + '15: اختيار الشهر مش بقائمتين')
    snap(page, pre + '15-forecast-sheet.jpg')
    page.click('[data-s="cancel"]')
    # —— ١٦) الإعدادات + ١٧) تغيير السعر
    page, rec = open_tab(h, browser, vp, mobile, '#s/company/settings', 'settings')
    page.wait_for_function("() => document.querySelector('.co [data-a=\"saveCompany\"]') && document.querySelectorAll('.co .co-lr').length > 2", timeout=20000)
    st = page.inner_text('.co')
    for bad in ('ANTHROPIC', 'OPENAI', 'DEEPSEEK', 'API_KEY', 'sk-'):
        if bad in st:
            PROBLEMS.append('%s16: «%s» ظاهر في الإعدادات' % (pre, bad))
    snap(page, pre + '16-settings.jpg')
    page.click('[data-a="auditOpen"]')
    page.wait_for_function("() => document.querySelectorAll('.co-lr.au').length >= 20", timeout=15000)
    snap(page, pre + '16b-settings-audit.jpg')
    page.click('[data-a="rate"]')
    sheet_wait(page)
    page.fill('#co_xr', '52.25')
    page.click('[data-s="go"]')
    page.wait_for_selector('.co-s2:not([hidden])')
    snap(page, pre + '17-rate-review.jpg')
    page.click('[data-s="back"]')
    page.click('[data-s="cancel"]')
    # —— ١٨) الرابط القديم #foundation
    page, rec = open_tab(h, browser, vp, mobile, '#foundation', 'assets')
    page.wait_for_timeout(500)
    if page.evaluate("() => location.hash") != '#s/company/assets':
        PROBLEMS.append('%s18: #foundation ما هبطش على المعدات (%s)' % (pre, page.evaluate("() => location.hash")))
    snap(page, pre + '18-old-link-foundation.jpg')
    browser.close()
    # —— ١٩) المفتاح مقفول = الشاشة القديمة بحالها ولا أثر للجديد
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = d3fx.D3Platform(d2=True)
        ctx = browser.context(h, 'admin', {'width': vp['width'], 'height': 900}, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#investment', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('view')", timeout=30000)
        page.wait_for_timeout(1200)
        st = page.evaluate("() => ({co: document.querySelectorAll('.co, .com').length, shell: !!(window.V2SHELL && V2SHELL.on), inv: !!document.getElementById('invTabs'), on: !!window.V2_ON})")
        if st['co'] or st['shell'] or st['on'] or not st['inv']:
            PROBLEMS.append('%s19: المفتاح مقفول والشاشة مش القديمة %r' % (pre, st))
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/company/summary', '/api/v2/company/subscriptions', '/api/v2/company/agreements']) { const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        if bad:
            PROBLEMS.append('%s19: مسارات الشركة والمفتاح مقفول لازم ٤٠٤ %r' % (pre, bad))
        vs.shot(page, pre + '19-switch-off.jpg')
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(d3fx.D3Platform(d2=True))
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            flow(browser, h, 'd', DESK, False)
            flow(browser, h, 't', TABL, False)
            flow(browser, h, 'm', MOBL, True)
        finally:
            browser.close()
    print(json.dumps({'out': OUT, 'shots': vs.SHOTS, 'blocked_by_origin': h.blocked_report(), 'unexpected': h.unexpected_blocked(), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
