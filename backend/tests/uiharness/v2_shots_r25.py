# -*- coding: utf-8 -*-
"""لقطات r25 — سعر الدورة لكل بلد · الفلوس بكل عملة + سطر الدولار · شرائط «محتاج قرارك» (الدورات والسوق).

    cd backend && python3 -B tests/uiharness/v2_shots_r25.py <out_dir>

موبايل ٣٩٠ (`m`) وكمبيوتر ١٢٨٠ (`d`). ⛔ صفر شبكة: الداشبورد جوه العملية والمنصة في الذاكرة (دورات + سوق)، وأسعار الصرف بديل ثابت (`fetch_rates` مستبدل).
"""
import copy
import os
os.environ.setdefault('DASH_SCHEDULER', '0')
os.environ['DASH_V2_ENABLED'] = 'true'
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'shots-r25'))
os.makedirs(OUT, exist_ok=True)

import courses_fixtures as cf               # noqa: E402
import market_fixtures as mfx               # noqa: E402
import v2_shots as vs                       # noqa: E402
from ef_route_harness import Harness, DASH  # noqa: E402

PROBLEMS = vs.PROBLEMS
DESK = {'width': 1280, 'height': 1500}
MOB = {'width': 390, 'height': 1500}


class R25Platform(mfx.MarketPlatform):
    """سوق + دورات: المسارات اللي للدورات بتتحوّل لـ`CoursesPlatform`، والطابور بيتجمّع من الاتنين."""

    def __init__(self, **kw):
        super(R25Platform, self).__init__(**kw)
        self.co = cf.CoursesPlatform(with_abc=True)
        self.extra_prices = {'pc-03': {'sa': 150.0, 'default': 40.0}}
        self.price_writes = []

    def _route(self, method, path, params, body):
        m = method.upper()
        if path.startswith('/api/bridge/courses') or path.startswith('/api/bridge/schedules') or path.startswith('/api/bridge/live/') \
                or path in ('/api/bridge/experts', '/api/bridge/trainer-applications', '/api/bridge/course-offers', '/api/bridge/program-requests'):
            if m == 'PUT' and re.match(r'^/api/bridge/courses/[^/]+$', path) and isinstance((body or {}).get('prices'), dict):
                cid = path.rsplit('/', 1)[1]
                self.price_writes.append((cid, copy.deepcopy(body)))
                cur = self.extra_prices.setdefault(cid, {})
                for k, v in body['prices'].items():
                    if k == 'eg':
                        c = self.co._find(cid)
                        if c and v:
                            c['price_amount'] = v
                    elif v is None:
                        cur.pop(k, None)
                    else:
                        cur[k] = v
                return 200, {'id': cid}
            out = self.co._co(m, path, params or {}, body or {})
            if out is not None:
                if m == 'GET' and path == '/api/bridge/courses':
                    for row in out[1]['courses']:
                        pr = dict(self.extra_prices.get(row['id'], {}))
                        if row.get('price_amount'):
                            pr['eg'] = row['price_amount']
                        row['prices'] = pr
                return out
        return super(R25Platform, self)._route(method, path, params, body)

    def queue(self):
        q = super(R25Platform, self).queue()
        cq = self.co.queue()
        pend = [c for c in self.co.courses if c['approval_status'] == 'pending']
        q['courses_pending'] = {'count': len(pend), 'titles': [c['title'] for c in pend],
                                'items': [{'id': c['id'], 'slug': c['slug'], 'title': c['title'], 'instructor_name': c['instructor_name'], 'type': c['type'],
                                           'submitted_at': c['_abc']['submitted_at'] or c['created_at']} for c in pend]}
        q['live_needs_decision'] = cq.get('live_needs_decision', [])
        return q


def seed(h):
    """دفتر الإيرادات: جنيه + ريال + دولار (مرة واحدة)، وأسعار الصرف بديل ثابت."""
    import datetime
    import v2_fx_routes
    v2_fx_routes.fetch_rates = lambda: {'rates': {'USD': 1, 'EGP': 50.0, 'SAR': 3.75, 'AED': 3.6725, 'KWD': 0.307, 'QAR': 3.64, 'OMR': 0.385}, 'date': '2026-11-13'}
    app = h.app
    with app.app.app_context():
        today = datetime.date.today()
        app.Revenue.query.delete()
        rows = [dict(source='course', amount_egp=12000, amount_usd=0), dict(source='course', amount_egp=None, amount_usd=0, needs_fx=True, currency='SAR', amount_original=850),
                dict(source='book', amount_egp=0, amount_usd=40), dict(source='consultation', amount_egp=3500, amount_usd=0)]
        for i, r in enumerate(rows):
            app.db.session.add(app.Revenue(date=today, payment_id='r25-%d' % i, description='r25', **r))
        app.db.session.commit()


def shot(page, name, focus=None):
    page.wait_for_timeout(450)
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    if focus:      # نمرّر لحد العنصر المقصود (الأرقام تحت شريط القرارات)
        page.evaluate("s => { const e = document.querySelector(s); if (e) e.scrollIntoView({block: 'start'}); }", focus)
        page.wait_for_timeout(200)
    path = os.path.join(OUT, name)
    page.screenshot(path=path, full_page=False)
    print('shot', path)
    vs.check(page, name)


def go(ctx, hash_, ready):
    page = ctx.new_page()
    page.on('pageerror', lambda e: (PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]), print('PAGEERROR', str(e)[:300], flush=True)))
    page.on('console', lambda m: print('CONSOLE', m.type, m.text[:200], flush=True) if m.type == 'error' else None)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    try:
        page.wait_for_function(vs.SHELL_READY, timeout=30000)
    except Exception:
        print('SHELL NOT READY; V2SHELL=', page.evaluate('() => [window.V2_ON, window.V2SHELL && V2SHELL.on, location.href, document.body.innerText.slice(0,200)]'), flush=True)
        raise
    page.wait_for_function(ready, timeout=30000)
    page.wait_for_timeout(900)
    return page


def run(browser, pre, vp):
    h = Harness(R25Platform())
    seed(h)
    # —— ١) محرّر السعر (مليان: مصر + السعودية + باقي البلاد) — موبايل وكمبيوتر
    ctx = browser.context(h, 'admin', vp, vp['width'] < 500)
    page = go(ctx, '#s/courses/course/pc-03', "() => document.querySelector('.v2co[data-screen=course] .v2co-tile')")
    tile = page.inner_text('.v2co-tile:nth-child(3)')
    if 'بره مصر: السعودية ١٥٠ ر.س، باقي البلاد ٤٠ دولار' not in tile:
        PROBLEMS.append('%s: خانة السعر في صفحة الدورة: %r' % (pre, tile))
    page.click('[data-a="prices"]')
    page.wait_for_selector('#epModal .v2co-prr', timeout=10000)
    vals = page.evaluate("() => [...document.querySelectorAll('#epModal .v2co-prin input')].map(i => i.value)")
    if vals != ['300', '150', '', '', '', '', '40']:
        PROBLEMS.append('%s: الخانات اتملت غلط %r' % (pre, vals))
    # تعديل: مصر ٣٥٠ والسعودية ١٧٥
    page.fill('#co_pr_eg', '٣٥٠')
    page.fill('#co_pr_sa', '175')
    shot(page, pre + '1-price-editor.png')
    page.click('#co_next')
    page.wait_for_selector('#epModal .v2co-diff')
    shot(page, pre + '1b-price-review.png')
    page.click('#co_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(600)
    w = h.ef.price_writes
    if not w or w[-1][1].get('prices') != {'eg': 350.0, 'sa': 175.0, 'ae': None, 'kw': None, 'qa': None, 'om': None, 'default': 40.0}:
        PROBLEMS.append('%s: الكتابة اللي وصلت المنصة %r' % (pre, w))
    if '٣٥٠ جنيه' not in page.inner_text('.v2co-tile:nth-child(3)') and '٣٥٠ ج' not in page.inner_text('.v2co-tile:nth-child(3)'):
        PROBLEMS.append('%s: السعر ما اتحدّثش في الصفحة: %r' % (pre, page.inner_text('.v2co-tile:nth-child(3)')))
    page.close()
    # —— ٢) الفلوس: ٣ عملات + سطر الدولار
    page = go(ctx, '#s/money/overview', "() => document.querySelector('.v3[data-board=overview] .v3-num') && EP.state.walletPayouts === 'ready' && document.querySelector('.v3-usd')")
    txt = page.inner_text('.v3-nums')
    if '١٢٬٠٠٠ ج' not in txt and '١٥٬٥٠٠ ج' not in txt:
        PROBLEMS.append('%s: دخل الجنيه مش ظاهر: %r' % (pre, txt[:200]))
    if 'ر.س' not in txt or 'دولار' not in txt:
        PROBLEMS.append('%s: العملات ما ظهرتش كلها: %r' % (pre, txt[:300]))
    usd = page.inner_text('.v3-usd')
    if 'تقريبًا بالدولار' not in usd or 'أسعار يوم' not in usd:
        PROBLEMS.append('%s: سطر الدولار %r' % (pre, usd))
    shot(page, pre + '2-money-3-currencies.png', focus='.v3-nums')
    page.close()
    # —— ٣) الدورات: شريط «محتاج قرارك» ببطاقة دورة مستنية
    page = go(ctx, '#s/courses/courses', "() => document.querySelector('.v2z-c[data-kind=course]')")
    if page.query_selector('[data-more]'):
        page.click('[data-more]')
        page.wait_for_timeout(300)
    cards = page.evaluate("() => [...document.querySelectorAll('.v2z-c')].map(c => [c.dataset.kind, [...c.querySelectorAll('.v2z-acts button')].map(b => b.textContent.trim())])")
    if not any(k == 'course' and a[:3] == ['افتح وراجع', 'انشرها', 'أعِدها بملاحظات'] for k, a in cards):
        PROBLEMS.append('%s: بطاقة الدورة المستنية بلا الأزرار %r' % (pre, cards))
    shot(page, pre + '3-courses-strip.png')
    # زرّ «انشرها» بيفتح ورقة النشر فعلًا
    page.click('.v2z-c[data-kind=course] [data-a="s"]')
    page.wait_for_selector('#epModal .v2co-m', timeout=15000)
    if 'انشر الدورة' not in page.inner_text('#epModal'):
        PROBLEMS.append('%s: زرّ انشرها ما فتحش ورقة النشر' % pre)
    shot(page, pre + '3b-courses-strip-approve-sheet.png')
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
    print('KINDS', [c[0] for c in cards], flush=True)
    live = page.evaluate("() => [...document.querySelectorAll('.v2z-c[data-kind=live] .v2z-acts button')].map(b => b.textContent.trim())")
    if live[:3] != ['ثبّتها', 'مدّد المهلة ٤٨ ساعة', 'ألغِها']:
        PROBLEMS.append('%s: أزرار بطاقة الدورة الحيّة %r' % (pre, live))
    page.close()
    # —— ٤) سوق الخدمات: شريط ببطاقة طلب في حارة غلط
    page = go(ctx, '#s/market/requests', "() => document.querySelector('.v2z-c[data-kind=market_lane]')")
    shot(page, pre + '4-market-strip.png')
    page.click('.v2z-c[data-kind=market_lane] [data-a="p"]')
    page.wait_for_selector('#epModal', timeout=15000)
    if 'نقل الطلب' not in page.inner_text('#epModal'):
        PROBLEMS.append('%s: زرّ انقله ما فتحش ورقة النقل' % pre)
    page.close()
    bad = [u for u in (h.blocked + h.blocked_inproc) if 'fonts.g' not in u]
    if bad:
        PROBLEMS.append('%s: طلبات خرجت برّه %r' % (pre, bad))


if __name__ == '__main__':
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = vs.Browsers(p)
        try:
            run(b, 'm', MOB)
            run(b, 'd', DESK)
        finally:
            b.close()
    print('PROBLEMS:', len(PROBLEMS))
    for x in PROBLEMS:
        print(' -', x)
    sys.exit(1 if PROBLEMS else 0)
