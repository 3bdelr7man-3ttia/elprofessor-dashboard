# -*- coding: utf-8 -*-
"""صور «ملف للخبير» في الداشبورد (الجولة ٦ · SPEC §١١) — كمبيوتر ١٤٤٠×٩٠٠ وموبايل ٣٩٠×٨٤٤.

    cd backend && python3 tests/uiharness/expert_files_shots.py <out_dir>

⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية (`app.test_client()`) والمنصة جدول في الذاكرة
(`ef_fixtures.EFPlatform`)، وأي أصل تاني بيتقفل ويتسجّل. آخر السكربت بيطبع اللي اتقفل لكل أصل، وبيفشل لو
فيه أي حاجة غير خطوط جوجل — أو لو فحوص الصور (تمرير أفقي في الموبايل · undefined/null/NaN) وقعت.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import ef_fixtures as fx                     # noqa: E402
from ef_route_harness import Harness, DASH   # noqa: E402

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'r6-shots'))
os.makedirs(OUT, exist_ok=True)

DESK = {'width': 1440, 'height': 900}
MOB = {'width': 390, 'height': 844}
SHOTS = []
PROBLEMS = []

READY = ("() => window.EP && EP.state && EP.state.inbox==='ready' && EP.state.opsQueue==='ready'"
         " && document.getElementById('rows')")


def shot(page, name, el=None):
    path = os.path.join(OUT, name)
    page.wait_for_timeout(250)
    if el is not None:
        page.locator(el).first.screenshot(path=path)
    else:
        page.screenshot(path=path)
    SHOTS.append(name)
    check(page, name)


def check(page, name):
    txt = page.evaluate("() => document.body.innerText")
    for bad in ('undefined', 'NaN', '[object Object]'):
        if bad in txt:
            PROBLEMS.append('%s: «%s» ظاهرة في الصفحة' % (name, bad))
    # «null» ككلمة لوحدها (مش جوه إيميل/رابط)
    import re
    if re.search(r'(?<![\w@./-])null(?![\w@./-])', txt):
        PROBLEMS.append('%s: «null» ظاهرة في الصفحة' % name)
    w = page.viewport_size['width']
    if w <= 400:
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth,"
                           " (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, sw, w))
        # كل زرار ظاهر جوه عرض الشاشة
        out = page.evaluate("""() => [...document.querySelectorAll('#epModal .btn, #drawer .btn')]
          .filter(b => b.offsetParent).map(b => b.getBoundingClientRect())
          .filter(r => r.left < -1 || r.right > window.innerWidth + 1).length""")
        if out:
            PROBLEMS.append('%s: %d زرار خارج عرض الشاشة' % (name, out))


class Browsers(object):
    """`--single-process` (جوه صندوق الأوامر Chromium العادي بيموت: mach port rendezvous ⇒ SIGTRAP) بيستحمل
    سياق واحد بس — فكل سياق بمتصفح جديد، والمتصفح بيتقفل مع السياق."""

    def __init__(self, p):
        self.p = p
        self.current = None

    def context(self, h, role='admin', viewport=None, mobile=False):
        self.close()
        self.current = self.p.chromium.launch(args=['--single-process'])
        return h.context(self.current, role, viewport, mobile)

    def close(self):
        if self.current is not None:
            try:
                self.current.close()
            except Exception:
                pass
            self.current = None


def open_inbox(ctx, h):
    page = ctx.new_page()
    page.goto(DASH + '/#inbox', wait_until='domcontentloaded')
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(300)
    return page


def chip(page, f):
    page.click('#filters .chip[data-f="%s"]' % f)
    page.wait_for_timeout(150)


def row_by_id(page, fid):
    idx = page.evaluate("id => INBOX.findIndex(r => r.apiId === id)", fid)
    if idx < 0:
        raise RuntimeError('الصفّ مش موجود: ' + fid)
    page.click('#rows .row[data-i="%d"]' % idx)
    page.wait_for_timeout(200)


def scroll_to(page, sel):
    page.evaluate("s => { const e = document.querySelector(s); if (e) e.scrollIntoView({block: 'start'}); }", sel)
    page.wait_for_timeout(150)


def wait_gone(page, fid):
    page.wait_for_function("id => window.EP && EP.state.inbox==='ready' && !INBOX.some(r => r.apiId === id)",
                           arg=fid, timeout=15000)


def desktop(browser, h):
    # ٠٠ — قايمة فاضية: المنصة بترد ومفيش ولا ملف (ولا «تعذّر»)
    h.ef = fx.EFPlatform(empty=True)
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    shot(page, '00-empty-desktop.png')
    browser.close()

    h.ef = fx.EFPlatform()
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    # ٠١ — العدّادات
    shot(page, '01-queue-chips-desktop.png')
    # ٠٢ — شريحة «ملفات للخبير»
    chip(page, 't:files')
    scroll_to(page, '#filters')
    shot(page, '02-files-chip-desktop.png')
    # ٠٣ — قرب الـ٤٨ ساعة (F2: فاضل ٥ ساعة + علم البلد)
    row_by_id(page, fx.F2['id'])
    scroll_to(page, '#filters')
    shot(page, '03-drawer-near48-desktop.png')
    # ٠٤ — اختيار خبير على F1 (مرشّح مختار)
    row_by_id(page, fx.F1['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    shot(page, '04-pick-expert-desktop.png')
    page.click('#ep_go')                                  # توزيع فعلي ⇒ سطر في السجل
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.wait_for_function("() => window.EP && EP.state.inbox==='ready'", timeout=15000)
    page.wait_for_timeout(400)
    # ٠٥ — نقل ملف متأخر (F5) بشريط التحذير
    chip(page, 't:files')
    row_by_id(page, fx.F5['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    shot(page, '05-reassign-late-desktop.png')
    page.click('#ep_x')
    # ٠٦ — تأكيد رجوع الفلوس (F3 — «أ. هالة سمير» اتبعتله وما استلمش)
    row_by_id(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    shot(page, '06-refund-confirm-desktop.png')
    # ٠٧ — ضغطتين ورا بعض والمنصة لسه ما ردّتش ⇒ «بيرجع…» وطلب واحد بس
    path = '/api/platform-expert-files/%s/refund' % fx.F3['id']
    h.hold.add(('POST', path))
    page.locator('#mc_go').dblclick()
    page.wait_for_timeout(300)
    shot(page, '07-refund-busy-desktop.png')
    n_dash = sum(1 for c in h.dash_calls if c == ('POST', path))
    h.hold.discard(('POST', path))
    h.release_held()
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.F3['id'])
    page.wait_for_timeout(200)
    n_plat = sum(1 for c in h.platform_calls if c[0] == 'POST' and c[1].endswith(fx.F3['id'] + '/refund'))
    if n_dash != 1 or n_plat != 1:
        PROBLEMS.append('ضغطتين على «رجّع» عملوا %d طلب للداشبورد و%d للمنصة (لازم ١)' % (n_dash, n_plat))
    # ٠٨ — بعد الرجوع: F3 اختفى + رسالة النجاح
    chip(page, 't:files')
    shot(page, '08-after-refund-desktop.png')
    # ٠٩ — شريحة «نزاعات»: D1 · D2 · D3 (ومفيش D1′)
    chip(page, 't:disputes')
    shot(page, '09-disputes-chip-desktop.png')
    n_d1 = page.evaluate("id => INBOX.filter(r => r.apiKind==='dispute' && (r.apiId===id || (r.cons && r.cons.expert_file_id===id))).length",
                         fx.D1['id'])
    if n_d1 != 1:
        PROBLEMS.append('نزاع الملف D1 ظاهر %d مرة (لازم مرة واحدة)' % n_d1)
    # ١٠ — درج D1 بالرأيين
    row_by_id(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    shot(page, '10-drawer-file-dispute-desktop.png')
    # ١١ — المقارنة
    page.click('#drawer [data-a="dsp_cmp"]')
    page.wait_for_selector('#epModal .cmp2')
    shot(page, '11-compare-opinions-desktop.png')
    page.click('#cmp_x')
    # ١٢ — تأكيد «للخبير» على D1 — وبعدين تنفيذ فعلي (سطر سجل)
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    shot(page, '12-resolve-release-desktop.png')
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.D1['id'])
    # ١٣ — تأكيد «للعميل» على D2 (استشارة)
    chip(page, 't:disputes')
    row_by_id(page, fx.D2['id'])
    page.click('#drawer [data-a="dsp_ref"]')
    page.wait_for_selector('#mc_go')
    shot(page, '13-resolve-refund-consultation-desktop.png')
    page.click('#mc_x')
    # ١٤ — D3: «للعميل» مقفول لأن الفلوس رجعت يدوي
    row_by_id(page, fx.D3['id'])
    shot(page, '14-manual-refunded-disabled-desktop.png')
    if page.is_enabled('#drawer [data-a="dsp_ref"]'):
        PROBLEMS.append('D3: «للعميل — رجّع فلوسه» مش مقفول مع إن الفلوس رجعت يدوي')
    # ١٥ — «الضمان والنزاعات» ← «النزاعات» بسطر التحويل
    page.evaluate("() => { go('escrow'); escTab='disputes'; viewEscrow(document.getElementById('view')); }")
    page.wait_for_selector('.ef-esc-ptr', timeout=15000)
    shot(page, '15-escrow-pointer-desktop.png')
    # ١٦ — سجل العمليات بعد الأفعال
    page.evaluate("() => auditModal()")
    page.wait_for_function("() => document.getElementById('auditRows') && !/جارٍ التحميل/.test(document.getElementById('auditRows').innerText)",
                           timeout=15000)
    shot(page, '16-audit-desktop.png')
    browser.close()

    # ١٧ — الخدمة مقفولة على المنصة: مفيش صفوف ولا «تعذّر»، والتنبيه ظاهر
    h.ef = fx.EFPlatform(enabled=False, cons_enabled=False, off_open_total=2)
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    failed = page.evaluate("() => (window.INBOX_FAILED||[]).slice()")
    if failed:
        PROBLEMS.append('المفتاح مقفول وظهر «تعذّر جلب»: %r' % failed)
    shot(page, '17-feature-off-desktop.png')
    browser.close()

    # ١٨ — الموظف على «الدورات»: ولا شريط «تعذّر» ولا نداء لمسارات الملفات
    h.ef = fx.EFPlatform()
    before = len(h.dash_calls)
    ctx = browser.context(h, 'employee', DESK)
    page = ctx.new_page()
    page.goto(DASH + '/#courses', wait_until='domcontentloaded')
    page.wait_for_function("() => window.EP && EP.authed && document.getElementById('view') && document.getElementById('view').innerText.length > 20",
                           timeout=30000)
    page.evaluate("() => { if (window.EP) EP.reload('inbox'); }")
    page.wait_for_function("() => window.EP && EP.state.inbox==='ready'", timeout=30000)
    page.wait_for_timeout(500)
    failed = page.evaluate("() => (window.INBOX_FAILED||[]).slice()")
    ef_calls = [c for c in h.dash_calls[before:] if 'expert-files' in c[1] or 'consultation-disputes' in c[1]]
    if ef_calls:
        PROBLEMS.append('الموظف نادى مسارات الملفات: %r' % ef_calls)
    if any('ملف' in f or 'نزاع' in f or 'آراء' in f for f in failed):
        PROBLEMS.append('الموظف شاف «تعذّر» على الملفات: %r' % failed)
    shot(page, '18-employee-desktop.png')
    browser.close()


def mobile(browser, h):
    h.ef = fx.EFPlatform(empty=True)
    ctx = browser.context(h, 'admin', MOB, mobile=True)
    page = open_inbox(ctx, h)
    shot(page, 'm00-empty-mobile.png')
    browser.close()

    h.ef = fx.EFPlatform()
    ctx = browser.context(h, 'admin', MOB, mobile=True)
    page = open_inbox(ctx, h)
    scroll_to(page, '.opsq')
    shot(page, 'm01-queue-chips-mobile.png')
    chip(page, 't:files')
    scroll_to(page, '#filters')
    shot(page, 'm02-files-chip-mobile.png')
    row_by_id(page, fx.F2['id'])                         # الدرج بيتمرّر لوحده (efDrawerIntoView)
    page.wait_for_timeout(300)
    shot(page, 'm03-drawer-near48-mobile.png')
    row_by_id(page, fx.F1['id'])
    page.wait_for_timeout(300)
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    shot(page, 'm04-pick-expert-mobile.png')
    page.click('#ep_x')
    row_by_id(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'm05-refund-confirm-mobile.png')
    page.click('#mc_x')
    chip(page, 't:disputes')
    row_by_id(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    page.evaluate("() => document.getElementById('drawer').scrollIntoView({block:'start'})")
    shot(page, 'm06-dispute-drawer-mobile.png')
    page.click('#drawer [data-a="dsp_cmp"]')
    page.wait_for_selector('#epModal .cmp2')
    shot(page, 'm07-compare-opinions-mobile.png')
    page.click('#cmp_x')
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'm08-resolve-release-mobile.png')
    page.click('#mc_x')
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    h = Harness(fx.EFPlatform())
    with sync_playwright() as p:
        browser = Browsers(p)
        try:
            desktop(browser, h)
            mobile(browser, h)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': SHOTS, 'blocked_by_origin': rep,
                      'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS},
                     ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
