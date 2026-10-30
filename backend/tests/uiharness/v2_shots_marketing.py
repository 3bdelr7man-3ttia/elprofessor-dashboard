# -*- coding: utf-8 -*-
"""لقطات «التسويق» (الجولة النهائية) — كمبيوتر ١٤٤٠×٩٠٠ (d) · تابلت ٨٢٠×١١٨٠ (t) · موبايل ٣٩٠×٨٤٤ (m).

    cd backend && python3 -B tests/uiharness/v2_shots_marketing.py ../docs/v2/final/shots-marketing

الأسماء `mk-<رقم>-<اسم>-<d|t|m>.jpg`. ⛔ صفر طلبات حقيقية: الداشبورد يتنفّذ جوه العملية والمنصة جدول في الذاكرة (`mk_fixtures.MKPlatform`)،
وأي أصل غير `https://dash.test` (وخطوط جوجل المقفولة) بيوقّع السكربت.

فحوص كل لقطة (الفشل ⇒ خروج ١): بلا تمرير أفقي · بلا أصناف الشاشة القديمة داخل `#view` (إلا لقطة المفتاح المقفول) · زرّ رئيسي ظاهر واحد على الأكثر ·
كل زرّ/صف ظاهر ≥٤٤px (≥٥٢px على ٣٩٠) · بلا حروف لاتينية ظاهرة خارج حقل الرابط · «غير متاح بعد» حيث غاب المصدر · بلا «undefined/NaN/null».
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                           # noqa: E402  (يقرأ sys.argv[1] مجلدًا للمخرجات)
import mk_fixtures as mkfx                      # noqa: E402
from ef_route_harness import Harness, DASH      # noqa: E402

DESK = {'width': 1440, 'height': 900}
TAB = {'width': 820, 'height': 1180}
MOB = {'width': 390, 'height': 844}
READY = "() => document.querySelector('.v3.mk[data-board=\"%s\"]') && !/…جارٍ جلب/.test(document.querySelector('.v3.mk').innerText)"
OLD = '.kpis, .kpi, .inboxwrap, .panel, .drawer, .policy'
PROBLEMS = vs.PROBLEMS


def mk_check(page, name, expect_na=False, allow_old=False, sheet=False):
    w = page.viewport_size['width']
    r = page.evaluate("""([old, w]) => {
      const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length);
      const v = document.getElementById('view');
      const big = e => w <= 400 && e.matches('.v3-btn1, .v3-btn2, .v3-pb, .v3-link, .mk-later, #epModal .v3m .btn');
      const small = [...document.querySelectorAll('.mk button, .mk [role=button], .mk a[href], #epModal .v3m button, #epModal .v3m select, #epModal .v3m input:not([type=hidden])')]
        .filter(vis).map(b => [b.className || b.tagName, Math.round(b.getBoundingClientRect().height), big(b) ? 52 : 44]).filter(x => x[1] < x[2]);
      const btn1 = [...(v ? v.querySelectorAll('.v3-btn1') : [])].filter(vis).length;
      const olds = v ? [...v.querySelectorAll(old)].filter(vis).length : 0;
      const txt = [...document.querySelectorAll('.v3.mk, #epModal .v3m')].map(e => { const c = e.cloneNode(true);
        c.querySelectorAll('input, textarea, select, script, style').forEach(n => n.remove()); return c.innerText; }).join('\\n');
      const sw = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
      const wide = [...document.querySelectorAll('.mk *, #epModal .v3m *')].filter(e => vis(e) && e.getBoundingClientRect().right > window.innerWidth + 1).length;
      return {small, btn1, olds, txt, sw, wide};
    }""", [OLD, w])
    if r['sw'] > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))
    if r['wide'] and w <= 400:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, r['wide']))
    if r['small']:
        PROBLEMS.append('%s: أهداف أصغر من الحد: %r' % (name, r['small'][:4]))
    if r['btn1'] > 1:
        PROBLEMS.append('%s: %d زرّ رئيسي ظاهر (الحد واحد)' % (name, r['btn1']))
    if r['olds'] and not allow_old:
        PROBLEMS.append('%s: أثر للشاشة القديمة داخل #view (%d)' % (name, r['olds']))
    txt = r['txt']
    latin = re.findall(r'[A-Za-z]{2,}', txt)
    if latin:
        PROBLEMS.append('%s: حروف لاتينية ظاهرة: %r' % (name, latin[:4]))
    for bad in ('undefined', 'NaN', '[object Object]', 'يقوّم'):
        if bad in txt:
            PROBLEMS.append('%s: «%s» ظاهرة' % (name, bad))
    if re.search(r'(?<![\w@./-])(null)(?![\w@./-])', txt):
        PROBLEMS.append('%s: «null» ظاهرة' % name)
    if expect_na and 'غير متاح بعد' not in txt:
        PROBLEMS.append('%s: «غير متاح بعد» غير موجودة والمصدر غائب' % name)
    if not sheet and re.search(r'(^|\n)\s*[0٠]\s*(\n|$)', txt):
        PROBLEMS.append('%s: صفر وحيد ظاهر' % name)


def snap(page, pre, nn, name, **kw):
    fname = 'mk-%s-%s-%s.jpg' % (nn, name, pre)
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    full = kw.pop('full', False)
    # الموبايل: الصفحة تتمرّر جوّه حاوية، فنطوّل النافذة لحظة اللقطة عشان تظهر الشاشة كلها (ليس الورقات)
    tall = full and not kw.get('sheet') and page.viewport_size['width'] <= 400
    if tall:
        page.set_viewport_size({'width': 390, 'height': 3400})
        page.wait_for_timeout(250)
    vs.shot(page, fname, full=full)
    if tall:
        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(150)
    vs.shell_check(page, fname)
    mk_check(page, fname, **kw)


def open_tab(ctx, hash_, board):
    page = ctx.new_page()
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY % board, timeout=30000)
    page.wait_for_timeout(500)
    return page


def sheet_open(page):
    page.wait_for_selector('#epModal .v3m', timeout=8000)
    page.wait_for_timeout(250)


def close_sheet(page):
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
    page.wait_for_timeout(120)


def flow(browser, h, pre, viewport, mobile):
    tall = dict(viewport, height=viewport['height'] if mobile else max(viewport['height'], 1500))
    full = True
    ef = mkfx.MKPlatform(d2=True)
    h.ef = ef
    ids = mkfx.seed_mk(h)
    ef.campaign_ids = ids
    ctx = browser.context(h, 'admin', tall, mobile)

    # ١) الحملات: النشطة الآن (المصدر الناقص: من أين جاء كل شخص ⇒ ٤٠٤)
    page = open_tab(ctx, '#s/marketing/campaigns', 'campaigns')
    info = page.evaluate("""() => ({nums: [...document.querySelectorAll('.v3-num')].map(n => [n.querySelector('h3').textContent, n.querySelector('.v3-big').textContent.trim(), n.classList.contains('na')]),
      tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), brain: !!document.querySelector('.mk-brainstrip'),
      rows: [...document.querySelectorAll('.mk-desk .mk-row, .mk-tab .mk-row')].length, legacy: !!document.querySelector('.mk-legacy'), h1: (document.querySelector('.v2c-h h1')||{}).textContent})""")
    if [n[0] for n in info['nums']] != ['صُرف على الإعلانات', 'دخل جاء من الإعلانات', 'دخل جاء بلا إعلانات', 'كلفة العميل الواحد']:
        PROBLEMS.append('%s01: الأرقام الأربعة %r' % (pre, info['nums']))
    if not [n for n in info['nums'] if n[0] == 'دخل جاء بلا إعلانات' and n[2] and n[1] == 'غير متاح بعد']:
        PROBLEMS.append('%s01: «دخل جاء بلا إعلانات» لازم «غير متاح بعد» والمصدر ٤٠٤: %r' % (pre, info['nums']))
    if info['tabs'] != ['الحملات', 'السوشيال ميديا', 'خطة النشر'] or not info['brain'] or not info['legacy']:
        PROBLEMS.append('%s01: الصفحة ناقصة %r' % (pre, {k: info[k] for k in ('tabs', 'brain', 'legacy')}))
    snap(page, pre, '01', 'campaigns', expect_na=True, full=full)

    # ٢) كل الحملات
    page.click('.v3-pb[data-f="all"]')
    page.wait_for_timeout(300)
    snap(page, pre, '02', 'campaigns-all', full=full)
    page.click('.v3-pb[data-f="active"]')
    page.wait_for_timeout(200)

    # ٦) ورقة «أوقفها» من شريط العقل (أول اقتراح: الحملة الخاسرة)
    page.click('.mk-brainstrip [data-a="brain"]')
    sheet_open(page)
    if 'هذا لا يوقف الإعلان نفسه' not in page.inner_text('#epModal'):
        PROBLEMS.append(pre + '06: تحذير «لا يوقف الإعلان» غائب')
    snap(page, pre, '06', 'brain-stop', sheet=True, full=False)
    n0 = len(h.platform_calls)
    close_sheet(page)

    # ٧) التفاصيل
    vis_sel = '.mk-cards .mk-ccard[data-id="%d"]' % ids['losing'] if mobile else ('.mk-tab .mk-row[data-id="%d"]' % ids['losing'] if viewport['width'] < 1180 else '.mk-desk .mk-row[data-id="%d"]' % ids['losing'])
    page.click(vis_sel)
    sheet_open(page)
    if 'utm_campaign=c%d' % ids['losing'] not in page.input_value('#mk_url'):
        PROBLEMS.append(pre + '07: رابط الحملة غير صحيح')
    if 'أساسيات صياغة العقود' not in page.inner_text('#epModal'):
        PROBLEMS.append(pre + '07: صاحب الحملة غير ظاهر')
    snap(page, pre, '07', 'detail', sheet=True)
    # ٩) التعديل مع قفل صاحب الحملة لو قائمة الأعمال غابت: نختبره لاحقًا بصفحة جديدة؛ هنا التعديل العادي
    page.click('#mk_edit')
    sheet_open(page)
    snap(page, pre, '08a', 'edit-open', sheet=True)
    close_sheet(page)
    # التعديل بـ«أخرى» وصف الدولار على الحملة القديمة
    old_sel = '.mk-cards .mk-ccard[data-id="%d"]' % ids['legacy'] if mobile else ('.mk-tab .mk-row[data-id="%d"]' % ids['legacy'] if viewport['width'] < 1180 else '.mk-desk .mk-row[data-id="%d"]' % ids['legacy'])
    page.click('.v3-pb[data-f="all"]')
    page.wait_for_timeout(250)
    page.click(old_sel)
    sheet_open(page)
    page.click('#mk_edit')
    sheet_open(page)
    if page.input_value('#mk_cur') != 'USD':
        PROBLEMS.append(pre + '08: العملة المخزّنة (دولار) لازم تكون مختارة: ' + page.input_value('#mk_cur'))
    page.select_option('#mk_plat', 'other')
    page.fill('#mk_plat_t', 'قناة الشريك')
    snap(page, pre, '08', 'edit', sheet=True)
    close_sheet(page)

    # ١٠) الحذف
    page.click(old_sel)
    sheet_open(page)
    page.click('#mk_del')
    sheet_open(page)
    snap(page, pre, '10', 'delete', sheet=True)
    close_sheet(page)

    # ١١) الحملات القديمة بعملة الدولار
    page.click('.v3-pb[data-f="active"]')
    page.wait_for_timeout(250)
    page.click('.mk-legacy [data-a="legacy"]')
    sheet_open(page)
    snap(page, pre, '11', 'legacy', sheet=True)
    close_sheet(page)

    # ١٢) كيف تُربط المصادر
    page.click('.mk-tail [data-a="how"]')
    sheet_open(page)
    snap(page, pre, '12', 'needs-how', sheet=True)
    close_sheet(page)
    page.close()

    # ٣) من أين جاء كل شخص يشتغل
    ef.attribution = True
    page = open_tab(ctx, '#s/marketing/campaigns', 'campaigns')
    info = page.evaluate("() => [...document.querySelectorAll('.v3-num')].map(n => [n.querySelector('.v3-big').textContent.trim(), n.classList.contains('na')])")
    if info[2][1]:
        PROBLEMS.append('%s03: رقم «بلا إعلانات» لازم يضيء مع الجسر: %r' % (pre, info))
    snap(page, pre, '03', 'campaigns-attr', full=full)
    page.close()
    ef.attribution = False

    # ٤) مصادر واقعة: الحملات والدخل والأرصدة
    ef.down = {'/api/bridge/income/by-service', '/api/bridge/ads-ledger'}
    page = ctx.new_page()
    page.route('**/api/campaigns', lambda r: r.fulfill(status=502, content_type='application/json', body='{"error":"x"}'))
    page.goto(DASH + '/#s/marketing/campaigns', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY % 'campaigns', timeout=30000)
    page.wait_for_timeout(500)
    dis = page.evaluate("() => { const b = document.querySelector('[data-a=\"new\"]'); return b ? b.disabled : null; }")
    if dis is not True:
        PROBLEMS.append(pre + '04: «حملة جديدة» لازم تكون معطّلة والحملات واقعة')
    snap(page, pre, '04', 'campaigns-down', expect_na=True, full=full)
    page.close()

    # ٩) التعديل وقائمة الأعمال غائبة: صاحب الحملة مقفول
    ctx2 = ctx
    ef.down = {'/api/bridge/ads-ledger'}
    page = open_tab(ctx2, '#s/marketing/campaigns', 'campaigns')
    sel = '.mk-cards .mk-ccard[data-id="%d"]' % ids['losing'] if mobile else ('.mk-tab .mk-row[data-id="%d"]' % ids['losing'] if viewport['width'] < 1180 else '.mk-desk .mk-row[data-id="%d"]' % ids['losing'])
    page.click(sel)
    sheet_open(page)
    page.click('#mk_edit')
    sheet_open(page)
    state = page.evaluate("() => { const s = document.getElementById('mk_owner'); return [s.disabled, s.options.length, s.options[0].textContent]; }")
    if not (state[0] and state[1] == 1 and 'الحالي' in state[2]):
        PROBLEMS.append('%s09: صاحب الحملة لازم مقفول بخيار «الحالي»: %r' % (pre, state))
    snap(page, pre, '09', 'edit-owner-locked', sheet=True)
    close_sheet(page)
    page.close()
    ef.down = set()

    # ٥) لا حملات
    mkfx.seed_mk(h, campaigns=False)
    page = open_tab(ctx, '#s/marketing/campaigns', 'campaigns')
    cnt = page.evaluate("() => ({b1: [...document.querySelectorAll('.v3-btn1')].filter(b => b.offsetParent).length, top: !!document.querySelector('.v3-top [data-a=\"new\"]')})")
    if cnt['b1'] != 1 or cnt['top']:
        PROBLEMS.append('%s05: لا حملات ⇒ زرّ رئيسي واحد في شريط العقل بلا زر علوي: %r' % (pre, cnt))
    snap(page, pre, '05', 'campaigns-empty', full=full)
    page.close()

    # ١٣) السوشيال + ورقة مدار
    ids = mkfx.seed_mk(h)
    page = open_tab(ctx, '#s/marketing/social', 'social')
    nb = page.evaluate("() => [...document.querySelectorAll('.v3.mk button')].filter(b => b.offsetParent && b.getAttribute('data-a') !== 'retry').length")
    if nb != 1 or page.query_selector('.mk-need'):
        PROBLEMS.append('%s14: السوشيال لازم زرّ واحد بلا «العقل يحتاج»: %r' % (pre, nb))
    snap(page, pre, '14', 'social', full=full)
    page.click('[data-a="madar"]')
    sheet_open(page)
    snap(page, pre, '13', 'madar', sheet=True)
    close_sheet(page)
    page.close()

    # ١٥) خطة النشر
    page = open_tab(ctx, '#s/marketing/plan', 'plan')
    if len(page.query_selector_all('.mk-pub')) != 2:
        PROBLEMS.append('%s15: لازم مقالان منشوران في آخر ٧ أيام' % pre)
    snap(page, pre, '15', 'plan', full=full)
    page.close()
    page = ctx.new_page()
    page.route('**/api/v2/marketing/published*', lambda r: r.fulfill(status=500, content_type='application/json', body='{"error":"x"}'))
    page.goto(DASH + '/#s/marketing/plan', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY % 'plan', timeout=30000)
    page.wait_for_timeout(400)
    snap(page, pre, '16', 'plan-down', expect_na=True, full=full)
    page.close()

    # ١٧) الرابط القديم
    page = ctx.new_page()
    page.goto(DASH + '/#marketing', wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(READY % 'campaigns', timeout=30000)
    page.wait_for_timeout(400)
    if not page.url.endswith('#s/marketing/campaigns'):
        PROBLEMS.append('%s17: الرابط القديم #marketing ما هبطش على التسويق/الحملات: %s' % (pre, page.url))
    snap(page, pre, '17', 'old-link', full=full)
    page.close()
    browser.close()


def _camp(h, cid):
    with h.app.app.app_context():
        c = h.app.Campaign.query.get(cid)
        return None if c is None else {'name': c.name, 'status': c.status, 'currency': c.currency, 'platform': c.platform, 'spent': c.spent,
                                       'revenue_attributed': c.revenue_attributed, 'clicks': c.clicks, 'target_audience': c.target_audience,
                                       'start_date': str(c.start_date or ''), 'end_date': str(c.end_date or '')}


def _owner(h, cid):
    with h.app.app.app_context():
        row = h.app.db.session.execute(__import__('sqlalchemy').text(
            'SELECT owner_kind, owner_id, owner_title, updated_by FROM v2_campaign_owner WHERE campaign_id = :c'), {'c': cid}).fetchone()
        return None if row is None else list(row)


def flow_writes(browser, h):
    """الكتابة فعلًا (سطح المكتب): إنشاء بصاحب كتاب · إيقاف من العقل · «بعدين» · تعديل · عملة الحملات القديمة بالطريقتين · حذف · الكيبورد."""
    ef = mkfx.MKPlatform(d2=True)
    h.ef = ef
    ids = mkfx.seed_mk(h)
    ctx = browser.context(h, 'admin', dict(DESK, height=1500), False)
    page = open_tab(ctx, '#s/marketing/campaigns', 'campaigns')
    # «بعدين»: يخفي الاقتراح الأول ويظهر التالي
    first = page.inner_text('.mk-bs')
    page.click('.mk-brainstrip [data-a="later"]')
    page.wait_for_timeout(500)
    second = page.inner_text('.mk-bs')
    if first == second or 'لينكدإن' not in second:
        PROBLEMS.append('w01: «بعدين» لازم يظهر الاقتراح التالي (لا نتائج لحملة لينكدإن): %r' % second[:60])
    if page.query_selector('.mk-brainstrip [data-a="later"]') is None:
        PROBLEMS.append('w01: «بعدين» غائب')
    # إنشاء حملة بصاحب كتاب
    page.click('.v3-top [data-a="new"]')
    sheet_open(page)
    page.fill('#mk_name', 'حملة اختبار الكتب')
    page.select_option('#mk_plat', 'google_ads')
    page.select_option('#mk_owner', 'book:bk-tenant-guide')
    page.fill('#mk_bud', '١٬٥٠٠')          # أرقام عربية وفاصل آلاف
    page.fill('#mk_sp', '٣٠٠٫٥')
    page.fill('#mk_clk', '-4')
    page.click('#mk_save')
    page.wait_for_timeout(250)
    if 'الأرقام لا تكون سالبة' not in page.inner_text('#mkerr'):
        PROBLEMS.append('w02: الرقم السالب لازم يتمنع: ' + page.inner_text('#mkerr'))
    page.fill('#mk_clk', '٤٠')
    n0 = len(h.dash_calls)
    page.click('#mk_save')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
    posts = [c for c in h.dash_calls[n0:] if c == ('POST', '/api/campaigns')]
    if len(posts) != 1:
        PROBLEMS.append('w02: لازم POST واحد للحملات: %r' % h.dash_calls[n0:])
    with h.app.app.app_context():
        row = h.app.Campaign.query.filter_by(name='حملة اختبار الكتب').first()
        new_id = row.id if row else None
        got = (row.currency, row.budget, row.spent, row.clicks, row.platform) if row else None
    if got != ('EGP', 1500.0, 300.5, 40, 'google_ads'):
        PROBLEMS.append('w02: الحملة المحفوظة غير صحيحة (العملة الافتراضية للجديد جنيه): %r' % (got,))
    ow = _owner(h, new_id) if new_id else None
    if not ow or ow[:2] != ['book', 'bk-tenant-guide'] or ow[3] != 'admin@local.test':
        PROBLEMS.append('w02: صاحب الحملة لم يُحفظ بالكتاب والفاعل من التوكن: %r' % (ow,))
    snap(page, 'd', '19', 'after-create', full=True)
    # إيقاف الحملة من شريط العقل (نعود للاقتراح الأول بتصفير «بعدين»)
    page.evaluate("() => { try { sessionStorage.clear(); } catch (e) {} V2SEC.marketing._state.skipped = []; V2SEC.marketing._tick(); }")
    page.wait_for_timeout(400)
    page.click('.mk-brainstrip [data-a="brain"]')
    sheet_open(page)
    n0 = len(h.dash_calls)
    page.click('#mk_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
    st = _camp(h, ids['losing'])
    if not st or st['status'] != 'paused':
        PROBLEMS.append('w03: الإيقاف ما غيّرش الحالة: %r' % (st,))
    if [c for c in h.dash_calls[n0:] if c[0] in ('PUT', 'POST', 'DELETE')] != [('PUT', '/api/campaigns/%d' % ids['losing'])]:
        PROBLEMS.append('w03: نداءات غير متوقعة: %r' % h.dash_calls[n0:])
    # كل الاستدعاءات لمنصة المال: ولا واحد (التسويق سجلّ فقط)
    if [c for c in h.platform_calls if c[0] in ('PUT', 'POST', 'PATCH') and 'attribution' not in c[1]]:
        PROBLEMS.append('w03: كتابة غير متوقعة على المنصة: %r' % [c for c in h.platform_calls if c[0] in ('PUT', 'POST', 'PATCH')][:3])
    # الكيبورد: Enter على اسم الحملة (زرّ حقيقي) يفتح التفاصيل
    page.click('.v3-pb[data-f="all"]')
    page.wait_for_timeout(300)
    page.focus('.mk-desk .mk-row[data-id="%d"] .mk-namebtn' % ids['winning'])
    page.keyboard.press('Enter')
    sheet_open(page)
    if 'حملة: حملة الدورات على فيسبوك' not in page.inner_text('#epModal'):
        PROBLEMS.append('w04: Enter على اسم الحملة ما فتحش التفاصيل')
    page.click('#mk_copy')
    page.wait_for_timeout(300)
    if 'نُسخ الرابط' not in page.inner_text('#toasts'):
        PROBLEMS.append('w04: رسالة «نُسخ الرابط» غائبة')
    # تعديل: دخل جديد بلا تغيير للمالك (لا نداء owner)
    page.click('#mk_edit')
    sheet_open(page)
    page.fill('#mk_rev', '11000')
    n0 = len(h.dash_calls)
    page.click('#mk_save')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    page.wait_for_timeout(300)
    if _camp(h, ids['winning'])['revenue_attributed'] != 11000.0:
        PROBLEMS.append('w05: التعديل ما اتحفظش')
    if [c for c in h.dash_calls[n0:] if c[0] == 'PUT' and c[1].endswith('/owner')]:
        PROBLEMS.append('w05: نداء صاحب الحملة رغم أنه لم يتغيّر')
    # حذف
    page.click('.mk-desk .mk-row[data-id="%d"]' % ids['paused'])
    sheet_open(page)
    page.click('#mk_del')
    sheet_open(page)
    page.click('#mk_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    page.wait_for_timeout(300)
    if _camp(h, ids['paused']) is not None:
        PROBLEMS.append('w06: الحذف ما حذفش')
    # عملة الحملات القديمة: «هي بالدولار فعلًا» ثم يختفي الشريط للأبد
    page.click('.mk-legacy [data-a="legacy"]')
    sheet_open(page)
    page.click('#mk_keep')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    page.wait_for_timeout(600)
    if page.query_selector('.mk-legacy'):
        PROBLEMS.append('w07: الشريط لازم يختفي بعد «هي بالدولار فعلًا»')
    if _camp(h, ids['legacy'])['currency'] != 'USD':
        PROBLEMS.append('w07: «هي بالدولار فعلًا» غيّرت العملة!')
    page.close()
    # «اجعلها كلها بالجنيه»
    ids = mkfx.seed_mk(h)
    page = open_tab(ctx, '#s/marketing/campaigns', 'campaigns')
    page.click('.mk-legacy [data-a="legacy"]')
    sheet_open(page)
    page.click('#mk_all')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=10000)
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
    c = _camp(h, ids['legacy'])
    if c['currency'] != 'EGP' or c['spent'] != 200.0:
        PROBLEMS.append('w08: العملة لازم تتغيّر للجنيه بلا تحويل رقم: %r' % (c,))
    page.wait_for_timeout(500)
    if page.query_selector('.mk-legacy'):
        PROBLEMS.append('w08: الشريط لازم يختفي')
    page.close()
    # «سأراجعها واحدة واحدة»: الشريط يغيب في الجلسة
    ids = mkfx.seed_mk(h)
    page = open_tab(ctx, '#s/marketing/campaigns', 'campaigns')
    page.click('.mk-legacy [data-a="legacy"]')
    sheet_open(page)
    page.click('#mk_later')
    page.wait_for_timeout(500)
    if page.query_selector('.mk-legacy') or _camp(h, ids['legacy'])['currency'] != 'USD':
        PROBLEMS.append('w09: «سأراجعها» لازم يخفي الشريط بلا تغيير')
    page.close()
    # تعديل حملة قديمة: التاريخ لا يُمسح، والعملة المخزّنة ظاهرة
    browser.close()



def flow_off(browser, h):
    import os as _os
    _os.environ['DASH_V2_ENABLED'] = 'false'
    try:
        ctx = browser.context(h, 'admin', DESK, False)
        page = ctx.new_page()
        page.goto(DASH + '/#marketing', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state && EP.state.marketing === 'ready'", timeout=30000)
        page.wait_for_timeout(600)
        st = page.evaluate("() => ({kpis: !!document.querySelector('#view .kpis'), mk: !!document.querySelector('.v3.mk, .mk-brainstrip'), on: !!window.V2_ON, shell: !!(window.V2SHELL && V2SHELL.on)})")
        if not st['kpis'] or st['mk'] or st['on'] or st['shell']:
            PROBLEMS.append('dflag-off: المفتاح مقفول لازم الشاشة القديمة كما هي بلا أثر جديد: %r' % st)
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/marketing/owners', '/api/v2/marketing/published', '/api/v2/marketing/attribution']) {
            const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        if bad:
            PROBLEMS.append('dflag-off: مسارات التسويق والمفتاح مقفول لازم ٤٠٤: %r' % bad)
        vs.shot(page, 'mk-18-flag-off-d.jpg', full=False)
    finally:
        _os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(mkfx.MKPlatform(d2=True))
    only = sys.argv[2] if len(sys.argv) > 2 else ''
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            if only in ('', 'd'):
                flow(browser, h, 'd', DESK, False)
            if only in ('', 't'):
                flow(browser, h, 't', TAB, False)
            if only in ('', 'm'):
                flow(browser, h, 'm', MOB, True)
            if only in ('', 'w'):
                flow_writes(browser, h)
            if only == '':
                flow_off(browser, h)
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
