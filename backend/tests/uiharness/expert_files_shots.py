# -*- coding: utf-8 -*-
"""صور «ملف للخبير» في الداشبورد (الجولة ٦ · SPEC §١١ + الجولة ٧ · §١٥) — كمبيوتر ١٤٤٠×٩٠٠ وموبايل ٣٩٠×٨٤٤.

    cd backend && python3 tests/uiharness/expert_files_shots.py <out_dir> [--only-r7 | --only-r8]

`--only-r7` = صور الجولة ٧ بس (`r7-*` · `mr7-*`): «اتدفعت وما وصلتش» ورجوع فلوسها · شارة «محتاج تدخّلك» ·
عدّادات الطابور الجديدة ونزاعات الاستشارات · الخدمة مقفولة والصفوف ظاهرة · السجل باسم الأدمن · ومراجعة الجولة ٧:
الخدمة مقفولة من غير أي وعد إن الفلوس ترجع لوحدها والملف اللي اتبعت بند (`r7-09`/`r7-10`/`mr7-05`/`mr7-06`) ·
فلوس رجعت للعميل قبل كده من غير «رجّع الفلوس» (`r7-11`).

`--only-r8` = صور الجولة ٨ بس (`r8-*` · `mr8-*`): «مستنية مراجعتك» (الصفوف · الدرج بالرأي زي ما العميل هيشوفه و«مبني
على» · اعتمده وابعته بتأكيد · رجّعه للخبير بملاحظة لازمة · رفض الرجوع التاني بكلام المنصة) · «للخبير» مقفول بسبب المنصة
(نزاع ملف · نزاع استشارة · رفض وقت الحسم) · «استشارات قديمة محتاجة قرارك» (الصفوف · الدرج · تأكيد التحويل · مقفولة بسبب) ·
وضع التجربة (السطر فوق الصفوف · رفض التوزيع بكلام المنصة) · السجل.

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

_ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
ONLY_R7 = '--only-r7' in sys.argv[1:]
ONLY_R8 = '--only-r8' in sys.argv[1:]
OUT = os.path.abspath(_ARGS[0] if _ARGS else os.path.join(os.getcwd(), 'r7-shots'))
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
    page.wait_for_function("id => window.EP && EP.state.inbox==='ready' && INBOX.some(r => r.apiId === id && r.fyi)",
                           arg=fx.F1['id'], timeout=15000)
    page.wait_for_timeout(400)
    # ٠٤ب — بعد التوزيع: F1 خرج من البنود والعدّ، وفاضل سطر «للعلم» واحد
    chip(page, 't:files')
    scroll_to(page, '#filters')
    shot(page, '04b-after-assign-fyi-desktop.png')
    if page.evaluate("id => INBOX.filter(r => !r.fyi).some(r => r.apiId === id)", fx.F1['id']):
        PROBLEMS.append('F1 بعد التوزيع لسه بند في الوارد')
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
    # ١٤ب — «للخبير» بعد ما الفلوس رجعت يدوي: ممنوع من الجولة ٨ (البند ٥) — مقفول والسبب تحته بكلام المنصة
    shot(page, '14b-release-locked-after-manual-desktop.png', el='#drawer')
    if page.is_enabled('#drawer [data-a="dsp_rel"]') or fx.E_RELEASE_MANUAL not in page.inner_text('#drawer'):
        PROBLEMS.append('D3: «للخبير» بعد الرجوع اليدوي مش مقفول بسبب المنصة')
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

    # ١٧ — الجسر لسه مش على المنصة (الإنتاج قبل النشر): مفيش صفوف ولا «تعذّر»
    h.ef = fx.EFPlatform(deployed=False, cons_enabled=False)
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
    # ٠١ب — الضغط على عدّاد «ملفات لسه ما اتستلمتش» بينزل لحد الشرايح والصفوف (كان بيرجع لأول الصفحة)
    page.click('.opsq[data-k="expert_files_awaiting_assignment"]')
    page.wait_for_timeout(400)
    shot(page, 'm01b-opsq-lands-on-rows-mobile.png')
    top = page.evaluate("() => document.getElementById('filters').getBoundingClientRect().top")
    if not (0 <= top < 844 * 0.4):
        PROBLEMS.append('الموبايل: بعد الضغط على العدّاد الشرايح مش قدّام العين (top=%s)' % top)
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


def _writes_carry_the_admin(h, since, who='admin@local.test'):
    """ج١: كل كتابة وصلت المنصة المزيّفة فيها `by` = إيميل الأدمن اللي داخل."""
    bad = [c for c in h.ef.calls[since:] if c[0] == 'POST' and (c[3] or {}).get('by') != who]
    if bad:
        PROBLEMS.append('كتابة وصلت المنصة من غير by الأدمن: %r' % bad)


def round7(browser, h):
    """الجولة ٧ (ج١–ج٥) على الكمبيوتر."""
    h.ef = fx.EFPlatform()
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    # r7-01 — عدّادات الطابور: «مستنية توزيعك» منفصل عن «ما اتستلمش من ١٢ ساعة» + نزاعات الاستشارات + فلوس واقفة
    scroll_to(page, '.opsq')
    shot(page, 'r7-01-queue-counters-desktop.png')
    for k in ('expert_files_awaiting_assignment', 'expert_files_assign_overdue', 'consultation_disputes',
              'expert_files_blocked', 'expert_files_unactivated'):
        if not page.query_selector('.opsq[data-k="%s"]' % k):
            PROBLEMS.append('عدّاد %s مش ظاهر' % k)
    # r7-02 — شريحة «محتاج تدخّلك»: «اتدفعت وما وصلتش» صفوف + أختام التوقّف بالشارة
    page.click('.opsq[data-k="expert_files_unactivated"]')
    page.wait_for_timeout(300)
    shot(page, 'r7-02-attention-rows-desktop.png')
    if page.evaluate("() => activeFilter") != 'attn':
        PROBLEMS.append('عدّاد «اتدفعت وما وصلتش» ما فتحش «محتاج تدخّلك»')
    # r7-03 — درج «اتدفع وما وصلش» (U2: مش لاقيين الملف + ختم الكنسة)
    row_by_id(page, fx.U2['consultation_id'])
    scroll_to(page, '#filters')
    shot(page, 'r7-03-unactivated-drawer-desktop.png')
    # r7-04 — تأكيد رجوع فلوس U1
    row_by_id(page, fx.U1['consultation_id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'r7-04-unactivated-refund-confirm-desktop.png')
    since = len(h.ef.calls)
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.U1['consultation_id'])
    page.wait_for_timeout(200)
    n = sum(1 for c in h.ef.calls if c[0] == 'POST' and c[1].endswith('/unactivated/%s/refund' % fx.U1['consultation_id']))
    if n != 1:
        PROBLEMS.append('رجوع فلوس U1 وصل المنصة %d مرة (لازم ١)' % n)
    # r7-05 — بعد الرجوع: U1 اختفى + رسالة النجاح
    page.evaluate("() => { activeFilter='attn'; renderInbox(); }")
    scroll_to(page, '#filters')
    shot(page, 'r7-05-after-unactivated-refund-desktop.png')
    # r7-06 — شارة «محتاج تدخّلك» على الصفّ + الدرج بالسبب (F6: أجر ما اتحوّلش لوحده بعد الـ٣ أيام)
    row_by_id(page, fx.F6['id'])
    scroll_to(page, '#filters')
    shot(page, 'r7-06-blocked-badge-drawer-desktop.png')
    if fx.BLOCK_LABELS['release_blocked_at'] not in page.inner_text('#drawer'):
        PROBLEMS.append('F6: سبب التوقّف مش في الدرج')
    # r7-07 — نزاع ملف: «لو اتحسم للخبير» + تأكيد التحويل باللي المنصة بعتته (release_amount · الاسم)
    chip(page, 't:disputes')
    row_by_id(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'r7-07-release-reads-the-platform-desktop.png')
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.D1['id'])
    # r7-08 — توزيع ملف (F4) ⇒ السجل باسم الأدمن
    chip(page, 't:files')
    row_by_id(page, fx.F4['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    page.click('#ep_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.wait_for_function("() => EP.state.inbox==='ready'", timeout=15000)
    page.evaluate("() => auditModal()")
    page.wait_for_function("() => document.getElementById('auditRows') && !/جارٍ التحميل/.test(document.getElementById('auditRows').innerText)",
                           timeout=15000)
    shot(page, 'r7-08-audit-admin-desktop.png')
    if 'admin@local.test' not in page.inner_text('#auditRows'):
        PROBLEMS.append('السجل ما فيهوش إيميل الأدمن')
    _writes_carry_the_admin(h, 0)
    browser.close()

    # r7-09/10 — الخدمة مقفولة للناس والجسر شغّال: الصفوف ظاهرة + سطر «مقفولة» + من غير «ابعته لـ…». ومراجعة الجولة ٧:
    # F1 اتبعت لخبير من ساعتين (كان هيبقى «للعلم») ⇒ بند، ومفيش «فلوسه ترجع لوحدها» في أي حتة (الكنسة واقفة).
    h.ef = _closed_with_a_sent_file()
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    chip(page, 't:files')
    shot(page, 'r7-09-service-closed-rows-desktop.png')
    if not page.query_selector('#rows .ef-off-line'):
        PROBLEMS.append('الخدمة مقفولة ومفيش سطر يقول كده فوق الصفوف')
    _no_auto_money_promise(page, 'r7-09')
    row_by_id(page, fx.F1['id'])
    scroll_to(page, '#filters')
    shot(page, 'r7-10-service-closed-drawer-desktop.png')
    if page.query_selector('#drawer [data-a="ef_pick"]'):
        PROBLEMS.append('الخدمة مقفولة وزرار «ابعته لـ…» لسه ظاهر')
    _no_auto_money_promise(page, 'r7-10')
    browser.close()

    # r7-11 — مراجعة الجولة ٧: الكنسة ختمت F7 لأن الفلوس رجعت للعميل يدوي قبل كده ⇒ الصفّ بيقول كده، والدرج من غير
    # «رجّع الفلوس» ومن غير «رجّعها من هنا» (العميل ما ياخدهاش مرتين).
    h.ef = fx.EFPlatform()
    h.ef.waiting = [fx.money_already_back(f) if f['id'] == fx.F7['id'] else f for f in h.ef.waiting]
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    chip(page, 'attn')
    row_by_id(page, fx.F7['id'])
    scroll_to(page, '#filters')
    shot(page, 'r7-11-money-already-back-drawer-desktop.png')
    if page.query_selector('#drawer [data-a="ef_refund"]'):
        PROBLEMS.append('F7: الفلوس رجعت قبل كده وزرار «رجّع الفلوس» لسه ظاهر')
    if fx.REFUND_BLOCK_LABELS['manual_refund'] not in page.inner_text('#drawer'):
        PROBLEMS.append('F7: جملة «الفلوس رجعت يدوي قبل كده» مش في الدرج')
    browser.close()


def _closed_with_a_sent_file():
    ef = fx.EFPlatform(service_open=False)
    ef.waiting = [fx.sent_inside_12h(f) if f['id'] == fx.F1['id'] else f for f in ef.waiting]
    return ef


def _no_auto_money_promise(page, name):
    """الخدمة مقفولة ⇒ ولا «فلوسه ترجع لوحدها» ولا «للعلم» في الصفحة ولا في التلميحات (مراجعة الجولة ٧)."""
    txt = page.evaluate("() => document.body.innerText + ' ' + [...document.querySelectorAll('[title]')].map(e => e.title).join(' ')")
    if 'ترجع لوحدها' in txt.replace('مش هترجع لوحدها', ''):
        PROBLEMS.append('%s: الخدمة مقفولة والشاشة بتقول إن الفلوس ترجع لوحدها' % name)
    if 'للعلم' in page.inner_text('#rows'):
        PROBLEMS.append('%s: الخدمة مقفولة وسطر «للعلم» ظاهر' % name)


def round7_mobile(browser, h):
    h.ef = fx.EFPlatform()
    ctx = browser.context(h, 'admin', MOB, mobile=True)
    page = open_inbox(ctx, h)
    scroll_to(page, '.opsq')
    shot(page, 'mr7-01-queue-counters-mobile.png')
    page.click('.opsq[data-k="expert_files_blocked"]')
    page.wait_for_timeout(400)
    shot(page, 'mr7-02-attention-rows-mobile.png')
    row_by_id(page, fx.U2['consultation_id'])
    page.wait_for_timeout(300)
    shot(page, 'mr7-03-unactivated-drawer-mobile.png')
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'mr7-04-unactivated-refund-confirm-mobile.png')
    page.click('#mc_x')
    browser.close()
    h.ef = _closed_with_a_sent_file()
    ctx = browser.context(h, 'admin', MOB, mobile=True)
    page = open_inbox(ctx, h)
    chip(page, 't:files')
    scroll_to(page, '#filters')
    shot(page, 'mr7-05-service-closed-rows-mobile.png')
    _no_auto_money_promise(page, 'mr7-05')
    row_by_id(page, fx.F1['id'])
    page.wait_for_timeout(300)
    shot(page, 'mr7-06-service-closed-drawer-mobile.png')
    _no_auto_money_promise(page, 'mr7-06')
    browser.close()


# --------------------------------------------------------------------------- الجولة ٨ (SPEC §١٧)
def _has(page, sel, name):
    if not page.query_selector(sel):
        PROBLEMS.append('%s: مش لاقي %s' % (name, sel))


def _wait_based_on(page):
    page.wait_for_function("() => /الرأي ده مبني على/.test((document.getElementById('drawer')||{}).innerText||'')",
                           timeout=15000)


def round8(browser, h):
    """الجولة ٨ على الكمبيوتر — قرارات المؤسس على أشكال جسر المنصة الجديدة."""
    h.ef = fx.EFPlatform(r8=True)
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    since = len(h.ef.calls)
    # r8-01 — «كل اللي مستنيك»: «آراء مستنية مراجعتك» و«استشارات قديمة محتاجة قرارك» (والتنبيهين ما بيتكرروش)
    scroll_to(page, '.opsq')
    shot(page, 'r8-01-queue-counters-desktop.png')
    for k in ('expert_files_in_review', 'consultations_legacy'):
        _has(page, '.opsq[data-k="%s"]' % k, 'r8-01')
    panel = page.inner_text('section.panel >> nth=0')
    if 'رأي مستني مراجعتك قبل ما يوصل للعميل' in panel or 'استشارة قديمة اتسلّمت' in panel:
        PROBLEMS.append('r8-01: تنبيه المراجعة/القديمة اتكرر مع إن عدّاده ظاهر')
    # r8-02 — العدّاد بيفتح شريحة «مستنية مراجعتك»: اسم الملف والخبير والقانون والمبلغ ومن إمتى
    page.click('.opsq[data-k="expert_files_in_review"]')
    page.wait_for_timeout(300)
    if page.evaluate("() => activeFilter") != 'review':
        PROBLEMS.append('r8-02: عدّاد المراجعة ما فتحش شريحتها')
    shot(page, 'r8-02-review-rows-desktop.png')
    rows = page.inner_text('#rows')
    for t in (fx.R1['title'], 'أ. رنا عادل', 'القانون المصري', '٥٠٠ ج', 'اتبعت للمراجعة'):
        if t not in rows:
            PROBLEMS.append('r8-02: «%s» مش على الصفوف' % t)
    # r8-03 — درج R1: الرأي زي ما العميل هيشوفه (كل سؤال وتحته الرد · الخطوة الجاية · «مبني على»)
    row_by_id(page, fx.R1['id'])
    _wait_based_on(page)
    scroll_to(page, '#filters')
    shot(page, 'r8-03-review-drawer-desktop.png')
    # الدرج بيتمرّر لوحده جنب القايمة (`.ef-scroll`) — آخره: «مبني على» والأزرار
    page.evaluate("() => { const d = document.getElementById('drawer'); d.scrollTop = d.scrollHeight; }")
    shot(page, 'r8-03b-review-drawer-bottom-desktop.png')
    if not page.evaluate("() => { const d = document.getElementById('drawer'), b = d.querySelector('[data-a=\"rv_ok\"]').getBoundingClientRect(); return b.bottom <= window.innerHeight && b.top >= 0; }"):
        PROBLEMS.append('r8-03b: زرار «اعتمده وابعته» مش قدّام العين بعد تمرير الدرج')
    page.evaluate("() => { document.getElementById('drawer').scrollTop = 0; }")
    drawer = page.inner_text('#drawer')
    for t in [a['question'] for a in fx.R1_OPINION['answers']] + ['الخطوة الجاية: محتاج حد متخصص يكمّل معاك',
                                                                   'مبني على', 'ومستندين، وعلى القانون المصري']:
        if t not in drawer:
            PROBLEMS.append('r8-03: «%s» مش في الدرج' % t)
    # r8-04 — تأكيد «اعتمده وابعته للعميل» بالمبلغ والعملة والأسماء (من غير ما نبعت)
    page.click('#drawer [data-a="rv_ok"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'r8-04-review-approve-confirm-desktop.png')
    body = page.inner_text('#epModal')
    for t in ('٥٠٠', 'جنيه مصري', 'سمر', 'أ. رنا عادل', '٣٠٠ ج'):
        if t not in body:
            PROBLEMS.append('r8-04: «%s» مش في التأكيد' % t)
    page.click('#mc_x')
    # r8-05 — «رجّعه للخبير»: الزرار مقفول لحد ما الملاحظة تتكتب، وبعدها بيتبعت
    page.click('#drawer [data-a="rv_back"]')
    page.wait_for_selector('#mc_go')
    if page.is_enabled('#mc_go'):
        PROBLEMS.append('r8-05: «رجّعه» شغّال من غير ملاحظة')
    page.fill('#mc_note', 'الإجابة الأولى محتاجة تذكر مدة سقوط الدعوى من القانون المدني بالظبط.')
    shot(page, 'r8-05-review-return-note-desktop.png')
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.R1['id'])
    # r8-06 — بعد الرجوع: R1 خرج من «مستنية مراجعتك» + رسالة النجاح
    page.evaluate("() => { activeFilter='review'; renderInbox(); }")
    scroll_to(page, '#filters')
    shot(page, 'r8-06-after-return-desktop.png')
    # r8-07 — درج R2: اترجع للخبير مرة قبل كده + مواعيد الجلسة
    row_by_id(page, fx.R2['id'])
    _wait_based_on(page)
    scroll_to(page, '#filters')
    shot(page, 'r8-07-review-drawer-returned-desktop.png')
    if 'رجّعته للخبير قبل كده' not in page.inner_text('#drawer'):
        PROBLEMS.append('r8-07: سطر «رجّعته قبل كده» مش في الدرج')
    # r8-08 — الرجوع التاني: المنصة بترفض بكلامها جوه النافذة
    page.click('#drawer [data-a="rv_back"]')
    page.wait_for_selector('#mc_go')
    page.fill('#mc_note', 'محتاج توضيح تاني.')
    page.click('#mc_go')
    page.wait_for_selector('#epModal .ef-err', timeout=15000)
    shot(page, 'r8-08-review-return-refused-desktop.png')
    if fx.E_REVIEW_RETURNED not in page.inner_text('#epModal .ef-err'):
        PROBLEMS.append('r8-08: رفض المنصة مش بكلامها')
    page.click('#mc_x')
    # r8-09 — «اعتمده وابعته» على R2 (رأي + جلسة) — وبعدين بيتبعت فعلًا
    page.click('#drawer [data-a="rv_ok"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'r8-09-review-approve-session-desktop.png')
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.R2['id'])
    # r8-10 — بعد الاعتماد: مفيش آراء مستنية (الشريحة اختفت) + رسالة النجاح
    page.evaluate("() => { activeFilter='all'; renderInbox(); }")
    scroll_to(page, '#filters')
    shot(page, 'r8-10-after-approve-desktop.png')
    if page.query_selector('#filters .chip[data-f="review"]'):
        PROBLEMS.append('r8-10: شريحة «مستنية مراجعتك» لسه ظاهرة والآراء خلصت')
    # r8-11 — «استشارات قديمة»: الصفوف
    chip(page, 't:legacy')
    scroll_to(page, '#filters')
    shot(page, 'r8-11-legacy-rows-desktop.png')
    # r8-12 — درج L1 (ميعاد التحويل عدّى) — وتأكيد «حوّل للخبير»
    row_by_id(page, fx.L1['id'])
    scroll_to(page, '#filters')
    shot(page, 'r8-12-legacy-drawer-desktop.png')
    page.click('#drawer [data-a="lg_rel"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'r8-13-legacy-release-confirm-desktop.png')
    if page.inner_text('#mc_go') != 'حوّل ٤٨٠ ج لـأ. عمرو الشريف':
        PROBLEMS.append('r8-13: زرار التحويل «%s»' % page.inner_text('#mc_go'))
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    wait_gone(page, fx.L1['id'])
    chip(page, 't:legacy')
    scroll_to(page, '#filters')
    shot(page, 'r8-14-after-legacy-release-desktop.png')
    # r8-15 — L2: الفلوس رجعت يدوي ⇒ الزرارين مقفولين والسبب تحت كل واحد بكلام المنصة
    row_by_id(page, fx.L2['id'])
    scroll_to(page, '#filters')
    shot(page, 'r8-15-legacy-locked-desktop.png')
    whys = page.evaluate("() => [...document.querySelectorAll('#drawer .ef-why')].map(e => e.innerText)")
    if whys != [fx.E_RELEASE_MANUAL, fx.E_RESOLVE_MANUAL]:
        PROBLEMS.append('r8-15: أسباب القفل %r' % whys)
    # r8-16 — نزاع استشارة D3: «للخبير» مقفول بكلام المنصة (العميل خد فلوسه يدوي)
    chip(page, 't:disputes')
    row_by_id(page, fx.D3['id'])
    scroll_to(page, '#filters')
    shot(page, 'r8-16-consultation-release-locked-desktop.png')
    if fx.E_RELEASE_MANUAL not in page.inner_text('#drawer'):
        PROBLEMS.append('r8-16: سبب قفل «للخبير» مش تحت الزرار')
    # r8-17 — رفض وقت الحسم: D2 صفّه ما كانش مقفول، والمنصة رفضت «للخبير» (البوابة رجّعت) ⇒ نفس الكلام جوه النافذة
    for c in h.ef.cons:
        if c['id'] == fx.D2['id']:
            c.update({'release_blocked': 'gateway_refund', 'release_blocked_reason': fx.E_RELEASE_GATEWAY})
    row_by_id(page, fx.D2['id'])
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    page.click('#mc_go')
    page.wait_for_selector('#epModal .ef-err', timeout=15000)
    shot(page, 'r8-17-release-refused-at-decision-desktop.png')
    if fx.E_RELEASE_GATEWAY not in page.inner_text('#epModal .ef-err'):
        PROBLEMS.append('r8-17: رفض «للخبير» وقت الحسم مش بكلام المنصة')
    page.click('#mc_x')
    # r8-18 — السجل: اعتماد الرأي · رجوعه بملاحظة · القرار على القديمة — باسم الأدمن
    page.evaluate("() => auditModal()")
    page.wait_for_function("() => document.getElementById('auditRows') && !/جارٍ التحميل/.test(document.getElementById('auditRows').innerText)",
                           timeout=15000)
    shot(page, 'r8-18-audit-desktop.png')
    au = page.inner_text('#auditRows')
    for t in ('اعتماد رأي وبعته للعميل', 'رجوع رأي للخبير بملاحظة', 'قرار على استشارة قديمة', 'admin@local.test'):
        if t not in au:
            PROBLEMS.append('r8-18: «%s» مش في السجل' % t)
    _writes_carry_the_admin(h, since)
    browser.close()

    # r8-19 — نزاع ملف العميل خد فلوسه فيه يدوي ⇒ «للخبير» مقفول والسبب تحته (والرأيين ظاهرين)
    h.ef = fx.EFPlatform(r8=True)
    h.ef.disputed = [fx.release_locked(f, 'manual_refund') for f in h.ef.disputed]
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    chip(page, 't:disputes')
    row_by_id(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    scroll_to(page, '#filters')
    shot(page, 'r8-19-file-release-locked-desktop.png')
    if page.is_enabled('#drawer [data-a="dsp_rel"]') or fx.E_RELEASE_MANUAL not in page.inner_text('#drawer'):
        PROBLEMS.append('r8-19: «للخبير» على نزاع ملف فلوسه رجعت يدوي مش مقفول بسببه')
    browser.close()

    # r8-20/21 — وضع التجربة: سطر «الخدمة مفتوحة للتجربة بس (٤ حساب)» فوق الصفوف · التوزيع لخبير برّه القايمة ⇒ رفض المنصة
    h.ef = fx.EFPlatform(r8=True, mode='allowlist')
    ctx = browser.context(h, 'admin', DESK)
    page = open_inbox(ctx, h)
    chip(page, 't:files')
    scroll_to(page, '#filters')
    shot(page, 'r8-20-allowlist-rows-desktop.png')
    line = page.inner_text('#rows .ef-trial-line') if page.query_selector('#rows .ef-trial-line') else ''
    if 'الخدمة مفتوحة للتجربة بس (%s حساب)' % '٤' not in line:
        PROBLEMS.append('r8-20: سطر وضع التجربة «%s»' % line)
    if page.query_selector('#rows .ef-off-line'):
        PROBLEMS.append('r8-20: وضع التجربة بيتعرض كأنه مقفول')
    row_by_id(page, fx.F1['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    idx = page.evaluate("() => [...document.querySelectorAll('#epModal .ef-cand')].findIndex(c => c.innerText.includes('م. سامي فؤاد'))")
    page.click('#epModal .ef-cand >> nth=%d' % idx)
    page.click('#ep_go')
    page.wait_for_selector('#epModal .ef-err', timeout=15000)
    shot(page, 'r8-21-allowlist-trial-refused-desktop.png')
    if fx.E_TRIAL_ONLY not in page.inner_text('#epModal .ef-err'):
        PROBLEMS.append('r8-21: رفض وضع التجربة مش بكلام المنصة')
    browser.close()


def round8_mobile(browser, h):
    h.ef = fx.EFPlatform(r8=True)
    ctx = browser.context(h, 'admin', MOB, mobile=True)
    page = open_inbox(ctx, h)
    scroll_to(page, '.opsq')
    shot(page, 'mr8-01-queue-counters-mobile.png')
    page.click('.opsq[data-k="expert_files_in_review"]')
    page.wait_for_timeout(400)
    shot(page, 'mr8-02-review-rows-mobile.png')
    row_by_id(page, fx.R1['id'])
    _wait_based_on(page)
    page.evaluate("() => document.getElementById('drawer').scrollIntoView({block:'start'})")
    shot(page, 'mr8-03-review-drawer-mobile.png')
    page.evaluate("() => { const b = document.querySelector('#drawer .acts'); if (b) b.scrollIntoView({block:'end'}); }")
    shot(page, 'mr8-03b-review-drawer-actions-mobile.png')
    page.click('#drawer [data-a="rv_ok"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'mr8-04-review-approve-confirm-mobile.png')
    page.click('#mc_x')
    page.click('#drawer [data-a="rv_back"]')
    page.wait_for_selector('#mc_go')
    page.fill('#mc_note', 'الإجابة الأولى محتاجة تذكر مدة سقوط الدعوى بالظبط.')
    shot(page, 'mr8-05-review-return-note-mobile.png')
    page.click('#mc_x')
    chip(page, 't:legacy')
    row_by_id(page, fx.L2['id'])
    page.wait_for_timeout(300)
    page.evaluate("() => { const b = document.querySelector('#drawer .acts'); if (b) b.scrollIntoView({block:'end'}); }")
    shot(page, 'mr8-06-legacy-locked-mobile.png')
    row_by_id(page, fx.L1['id'])
    page.wait_for_timeout(300)
    page.click('#drawer [data-a="lg_rel"]')
    page.wait_for_selector('#mc_go')
    shot(page, 'mr8-07-legacy-release-confirm-mobile.png')
    page.click('#mc_x')
    chip(page, 't:disputes')
    row_by_id(page, fx.D3['id'])
    page.wait_for_timeout(300)
    page.evaluate("() => { const b = document.querySelector('#drawer .acts'); if (b) b.scrollIntoView({block:'end'}); }")
    shot(page, 'mr8-08-consultation-release-locked-mobile.png')
    browser.close()
    h.ef = fx.EFPlatform(r8=True, mode='allowlist')
    ctx = browser.context(h, 'admin', MOB, mobile=True)
    page = open_inbox(ctx, h)
    chip(page, 't:files')
    scroll_to(page, '#filters')
    shot(page, 'mr8-09-allowlist-rows-mobile.png')
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    h = Harness(fx.EFPlatform())
    with sync_playwright() as p:
        browser = Browsers(p)
        try:
            if not (ONLY_R7 or ONLY_R8):
                desktop(browser, h)
                mobile(browser, h)
            if not ONLY_R8:
                round7(browser, h)
                round7_mobile(browser, h)
            if not ONLY_R7:
                round8(browser, h)
                round8_mobile(browser, h)
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
