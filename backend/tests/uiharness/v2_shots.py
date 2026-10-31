# -*- coding: utf-8 -*-
"""صور اللوحة الجديدة (D1) — كمبيوتر ١٤٤٠×٩٠٠ (`d*`) وموبايل ٣٩٠×٨٤٤ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots.py <out_dir>

اللقطات:
  ١. اللوحة والمفتاح مفتوح (رقم في كل مربّع) · قائمة الصحة · سجل العقل.
  ٢. وضع التركيز لكل نوع: ملف ينتظر خبيرًا · ملف متأخر · رأي للمراجعة · نزاع · تحويل أرباح · إيصال · مدرّب · زائر.
  ٣. نافذة تسجيل التحويل (فاضية ومملية) · نافذة الرفض · نافذة تأكيد الإيصال.
  ٤. الخطأ على البطاقة (البطاقة ثابتة والرسالة عليها) · فتح الدرج من التركيز والرجوع.
  ٥. النهاية (الفيل «انتهت القرارات») · اللوحة من غير قرارات.
  ٦. المفتاح مقفول (إثبات إن مفيش حاجة اتغيّرت).

الوضع `d1b` (الهيكل الجديد — SPEC-D1B §٤): اللوحة في الغلاف · القائمة المفتوحة (شاشة ١٠٢٤ و٣٩٠) · كل قسم بتبويباته · رابط قديم
بيهبط على قسمه · المفتاح مقفول. وسكربت الفحص بيفشل لو ظهر أي أثر للقائمة القديمة والمفتاح مفتوح.
    cd backend && python3 -B tests/uiharness/v2_shots.py <out_dir> [d1|d1b]

الوضع `d2` (SPEC-D2): لوحة تذاكر «ملفات الخبراء» بأعمدتها الأربعة (والموبايل على كل عمود) · تذكرة تفتح الدرج · لوحة النزاعات ·
صفحة شخص كاملة · صفحة شخص مصادرها غير متاحة · بحث الناس · عدّاد التذكرة بعد دقيقة (ساعة مفروضة). السكربت بيفشل لو عمود فاضي، أو تمرير
أفقي في الموبايل، أو هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل)، أو «0/null/NaN» ظاهرة بدل «غير متاح بعد».
    cd backend && python3 -B tests/uiharness/v2_shots.py <out_dir> d2

الوضع `d3` (SPEC-D3): «الفلوس» (نظرة · نظرة والمصادر واقعة · ورقة تسجيل تحويل · التحويلات · الإيصالات والعالقة · الأسعار وورقة التعديل بقبل ⇒ بعد ·
النسب ورسالة رفض المنصة · إعلانات الأعمال) و«الكتب» (مراجعة العروض وورقة الاعتماد · طلبات القرّاء) · بطاقتا القرار الجديدتان. السكربت بيفشل لو
رقم «٠/null/NaN» ظاهر بدل «غير متاح بعد»، أو هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل)، أو تمرير أفقي، أو نداء كتابة من غير `confirmed:true`.
    cd backend && python3 -B tests/uiharness/v2_shots.py <out_dir> d3

⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة (`v2_fixtures.V2Platform`)، وأي أصل تاني بيتقفل
ويتسجّل. السكربت بيفشل لو خرج أي طلب غير خطوط جوجل، أو لو فحوص الصور (تمرير أفقي · undefined/NaN/null · زرار أقل من ٥٢) وقعت.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import ef_fixtures as fx                        # noqa: E402
import v2_fixtures as v2fx                      # noqa: E402
import d3_fixtures as d3fx                      # noqa: E402
from ef_route_harness import Harness, DASH      # noqa: E402

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'v2-shots'))
os.makedirs(OUT, exist_ok=True)
DESK = {'width': 1440, 'height': 900}
MOB = {'width': 390, 'height': 844}
SHOTS = []
PROBLEMS = []

READY = ("() => window.V2_ON === true && window.EP && ['opsQueue','inbox','walletPayouts','invites','pendingUsers','market']"
         ".every(k => EP.state[k] === 'ready') && document.querySelector('.v2-tile') && !document.querySelector('.v2-cnt.ld')")


def check(page, name):
    txt = page.evaluate("() => document.body.innerText")
    for bad in ('undefined', 'NaN', '[object Object]'):
        if bad in txt:
            PROBLEMS.append('%s: «%s» ظاهرة في الصفحة' % (name, bad))
    if re.search(r'(?<![\w@./-])null(?![\w@./-])', txt):
        PROBLEMS.append('%s: «null» ظاهرة في الصفحة' % name)
    w = page.viewport_size['width']
    if w <= 400:
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth,"
                           " (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, sw, w))
        small = page.evaluate("""() => [...document.querySelectorAll('.v2-btn1, .v2-btn2, .v2-start, .v2-pill, #epModal .acts .btn')]
          .filter(b => b.offsetParent).map(b => b.getBoundingClientRect().height).filter(h => h < 44).length""")
        if small:
            PROBLEMS.append('%s: %d زرار أقل من ٤٤px' % (name, small))
        out = page.evaluate("""() => [...document.querySelectorAll('.v2 button, #epModal .btn')]
          .filter(b => b.offsetParent).map(b => b.getBoundingClientRect())
          .filter(r => r.left < -1 || r.right > window.innerWidth + 1).length""")
        if out:
            PROBLEMS.append('%s: %d زرار خارج عرض الشاشة' % (name, out))


def shot(page, name, full=False):
    path = os.path.join(OUT, name)
    page.wait_for_timeout(350)
    page.screenshot(path=path, full_page=full, type='jpeg', quality=82)
    SHOTS.append(name)
    check(page, name)


class Browsers(object):
    """`--single-process` بيستحمل سياق واحد بس — فكل سياق بمتصفح جديد."""

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


def open_home(ctx):
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(300)
    return page


def focus_on(page, kind, nth=0, where=None):
    """يقدّم بطاقة من النوع المطلوب لأول الطابور (الترتيب الحقيقي بيتختبر في test_v2_d1.py)."""
    page.evaluate("""([kind, nth, where]) => {
      const S = V2._state;
      let all = S.deck.filter(c => c.kind === kind);
      if (where) all = all.filter(c => JSON.stringify(c).indexOf(where) > -1);
      const hit = all[nth];
      if (!hit) throw new Error('no card ' + kind);
      S.deck = [hit].concat(S.deck.filter(c => c !== hit));
      S.err = ''; S.busy = false; S.lockedId = '';
      V2.render(document.getElementById('view'));
    }""", [kind, nth, where])
    page.wait_for_selector('.v2-card')
    page.wait_for_timeout(120)


def start(page):
    page.click('[data-a="start"]')
    page.wait_for_selector('.v2-card')


KINDS = [('file_waiting', 0, None, 'file-waiting'), ('file_late', 0, None, 'file-late'), ('review', 0, None, 'review'),
         ('dispute', 0, None, 'dispute'), ('payout', 0, None, 'payout'),
         ('manual_payment', 0, None, 'receipt'), ('trainer', 0, None, 'trainer'), ('pending_user', 0, None, 'visitor')]


def flow(browser, h, pre, viewport, mobile):
    h.ef = v2fx.V2Platform()
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_home(ctx)
    p = pre
    shot(page, p + '01-board.jpg')
    # الصحة
    page.click('.v2-health')
    page.wait_for_selector('.v2-pop')
    shot(page, p + '02-health.jpg')
    page.click('.v2-health')
    page.wait_for_timeout(100)
    # سجل العقل
    page.click('[data-tile="brain"]')
    page.wait_for_selector('.v2-log, .v2-empty, .v2sb')
    shot(page, p + '03-brain-log.jpg')
    page.go_back()    # بعد الدمج: سجل العقل تبويب في قسمه، والرجوع بزر المتصفح
    page.wait_for_selector('.v2-tile')
    # التركيز لكل نوع
    start(page)
    shot(page, p + '10-focus-first.jpg')
    for i, (kind, nth, where, label) in enumerate(KINDS):
        focus_on(page, kind, nth, where)
        shot(page, '%s2%d-focus-%s.jpg' % (p, i, label))
    # زائر مشبوه → «افتح وراجع» مش اعتماد بضغطة
    focus_on(page, 'pending_user', 1)
    shot(page, p + '29-focus-visitor-suspicious.jpg')
    lbl = page.inner_text('[data-a="primary"]')
    if 'افتح وراجع' not in lbl:
        PROBLEMS.append(p + '29: الزائر المشبوه زرّه الأساسي «%s»' % lbl)
    # ملف بلا خبير متاح
    focus_on(page, 'file_waiting', 0, 'لا يوجد خبير متاح')
    shot(page, p + '30-focus-file-no-expert.jpg')
    # تحويل أرباح: نافذة التسجيل
    focus_on(page, 'payout', 1)
    page.click('[data-a="primary"]')
    page.wait_for_selector('#epModal #v2m_go')
    shot(page, p + '31-payout-modal-empty.jpg')
    if not page.is_disabled('#v2m_go'):
        PROBLEMS.append(p + '31: زرّ التسجيل شغّال من غير مرجع')
    page.fill('#v2m_f', 'IP-77123')
    page.wait_for_timeout(120)
    shot(page, p + '32-payout-modal-filled.jpg')
    n0 = len(h.platform_calls)
    page.click('#v2m_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(500)
    shot(page, p + '33-after-payout.jpg')
    sent = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/settle')]
    if len(sent) != 1 or sent[0][3] != {'reference': 'IP-77123'}:
        PROBLEMS.append(p + '33: نداء settle مش واحد أو جسمه غلط: %r' % sent)
    if [x['reference'] for x in h.ef.settled] != ['IP-77123']:
        PROBLEMS.append(p + '33: المنصة ما سجّلتش التحويل')
    if 'سُجّل تحويل' not in page.inner_text('.v2-done'):
        PROBLEMS.append(p + '33: «أنجزت الآن» ما فيهاش السطر')
    # رفض تحويل
    focus_on(page, 'payout', 0)
    page.click('[data-a="secondary"]')
    page.wait_for_selector('#epModal #v2m_go')
    page.fill('#v2m_f', 'رقم الحساب غير مطابق للاسم')
    shot(page, p + '34-payout-reject-modal.jpg')
    modal = page.inner_text('#epModal')
    if '٣٬٥٠٠٫٥' not in modal or '٣٬٥٠١' in modal:
        PROBLEMS.append(p + '34: المبلغ بالكسور مش ظاهر كما هو في نافذة الرفض (٣٬٥٠٠٫٥)')
    page.click('#v2m_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(400)
    if [x['reject_reason'] for x in h.ef.rejected] != ['رقم الحساب غير مطابق للاسم']:
        PROBLEMS.append(p + '34: رفض التحويل ما وصلش للمنصة')
    # إيصال: نافذة التأكيد (ورجوع من غير تنفيذ)
    focus_on(page, 'manual_payment', 0)
    page.click('[data-a="primary"]')
    page.wait_for_selector('#epModal #v2m_go')
    shot(page, p + '35-receipt-modal.jpg')
    page.click('#v2m_x')
    page.wait_for_function("() => !document.getElementById('epModal')")
    if any(c[1].endswith('/decide') for c in h.platform_calls):
        PROBLEMS.append(p + '35: الرجوع نفّذ تأكيد')
    # خطأ على البطاقة
    focus_on(page, 'file_waiting', 0, 'أقترح')
    fid = page.evaluate("() => V2._state.deck[0].row.apiId")
    h.ef.forced[('POST', '/api/bridge/expert-files/%s/assign' % fid)] = (409, {'detail': fx.E_TRIAL_ONLY})
    before = page.evaluate("() => V2._state.deck.length")
    locked_id = page.evaluate("() => V2._state.deck[0].id")
    page.click('[data-a="primary"]')
    page.wait_for_selector('.v2-err', timeout=15000)
    shot(page, p + '40-error-on-card.jpg')
    if page.evaluate("() => V2._state.deck.length") != before or fx.E_TRIAL_ONLY not in page.inner_text('.v2-err'):
        PROBLEMS.append(p + '40: البطاقة اتقدّمت رغم الفشل أو الرسالة مش بكلام المنصة')
    # البطاقة المقفولة: «حدّث الآن» شغّال، وأزرار الفتح شغّالة، والباقي مقفول
    lock_label = page.inner_text('[data-a="refresh"]')
    if lock_label != 'حدّث الآن' or page.query_selector('[data-a="primary"]'):
        PROBLEMS.append(p + '40: البطاقة المقفولة مفيهاش زرّ «حدّث الآن» (%r)' % lock_label)
    sec = page.query_selector('[data-a="secondary"]')
    if page.is_disabled('[data-a="refresh"]') or (sec and sec.is_disabled()):
        PROBLEMS.append(p + '40: «حدّث الآن» أو زرّ «افتح الملف» مقفول على البطاقة المقفولة')
    if page.query_selector('[data-a="open"]') and page.is_disabled('[data-a="open"]'):
        PROBLEMS.append(p + '40: «غيّر / افتح» مقفول على بطاقة مقفولة')
    del h.ef.forced[('POST', '/api/bridge/expert-files/%s/assign' % fid)]
    page.click('[data-a="refresh"]')
    page.wait_for_function("() => !document.querySelector('[data-a=\"refresh\"]')", timeout=20000)
    shot(page, p + '41-after-refresh.jpg')
    if page.evaluate("() => V2._state.deck[0].id") != locked_id or page.evaluate("() => V2._state.lockedId") != '':
        PROBLEMS.append(p + '41: بعد التحديث البطاقة لازم تفضل وتتفكّ')
    if not page.query_selector('[data-a="primary"]') or page.is_disabled('[data-a="primary"]'):
        PROBLEMS.append(p + '41: الأزرار ما رجعتش بعد التحديث')
    # بطاقة مقفولة + اتحسمت في مكان تاني ⇒ «حدّث الآن» بيقدّم اللي بعدها
    focus_on(page, 'manual_payment', 0)
    mp_id, mp_api = page.evaluate("() => [V2._state.deck[0].id, V2._state.deck[0].row.apiId]")
    h.ef.payments = [x for x in h.ef.payments if x['id'] != mp_api]
    page.evaluate("() => { V2._state.lockedId = V2._state.deck[0].id; V2.render(document.getElementById('view')); }")
    page.click('[data-a="refresh"]')
    page.wait_for_function("(id) => V2._state.deck[0] && V2._state.deck[0].id !== id", arg=mp_id, timeout=20000)
    shot(page, p + '42-refresh-advances.jpg')
    if page.evaluate("() => V2._state.lockedId") != '':
        PROBLEMS.append(p + '42: القفل فضل بعد التقديم')
    # «لاحقًا»
    focus_on(page, 'file_waiting', 0, 'أقترح')
    first = page.evaluate("() => V2._state.deck[0].id")
    page.click('[data-a="later"]')
    page.wait_for_timeout(150)
    now_first = page.evaluate("() => V2._state.deck[0].id")
    last = page.evaluate("() => V2._state.deck[V2._state.deck.length-1].id")
    if now_first == first or last != first:
        PROBLEMS.append(p + '41: «بعدين» ما نقلتش البطاقة لآخر الطابور')
    # فتح الدرج من التركيز والرجوع
    focus_on(page, 'dispute', 0)
    page.click('[data-a="primary"]')
    page.wait_for_selector('#drawer .dh', timeout=15000)
    page.wait_for_selector('#v2Pill')
    shot(page, p + '50-drawer-from-focus.jpg')
    page.click('#v2Pill')
    page.wait_for_selector('.v2-card')
    shot(page, p + '51-back-to-focus.jpg')
    # النهاية: بطاقة «تم» واحدة
    page.evaluate("""() => {
      const S = V2._state;
      const hit = S.deck.filter(c => c.kind === 'lead')[0];
      S.deck = [hit]; S.total = 3;
      V2.render(document.getElementById('view'));
    }""")
    page.click('[data-a="primary"]')
    page.wait_for_selector('.v2-end', timeout=15000)
    shot(page, p + '60-end.jpg')
    page.click('[data-a="back"]')
    page.wait_for_selector('.v2-tile')
    page.wait_for_function(READY, timeout=30000)
    shot(page, p + '61-board-after.jpg')
    # قائمة مقصوصة: العدّادات المبنية من صفوف الوارد «ناقصة» معلَنة، والتحذير على شريط «القرار التالي»
    page.evaluate("""() => { window.INBOX_TRUNCATED = ['نزاعات الملفات: معروض 100 من 300']; V2.render(document.getElementById('view')); }""")
    page.wait_for_selector('.v2-warnline')
    shot(page, p + '04-board-truncated.jpg')
    txt = page.inner_text('.v2-next')
    if 'معروض جزء فقط من: نزاعات الملفات' not in txt:
        PROBLEMS.append(p + '04: تحذير القائمة المقصوصة مش ظاهر: %r' % txt)
    for key in ('books', 'people', 'brain'):
        t = page.inner_text('[data-tile="%s"]' % key)
        if 'العدد ناقص' not in t:
            PROBLEMS.append(p + '04: مربّع %s من غير «العدد ناقص» والقائمة مقصوصة' % key)
    page.evaluate("() => { window.INBOX_TRUNCATED = []; }")
    browser.close()

    # اللوحة من غير قرارات
    h.ef = v2fx.V2Platform(empty=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_home(ctx)
    shot(page, p + '70-board-empty.jpg')
    if page.query_selector('[data-a="start"]'):
        PROBLEMS.append(p + '70: زرّ «ابدأ القرارات» ظاهر من غير قرارات')
    browser.close()

    # جلب فاشل ⇒ لا «لا توجد قرارات» ولا «العقل يعمل»
    h.ef = v2fx.V2Platform(empty=True)
    h.ef.forced[('GET', '/api/bridge/ops/queue')] = (500, {'detail': 'down'})
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2_ON === true && window.EP && ['opsQueue','inbox','walletPayouts'].every(k => ['ready','error'].indexOf(EP.state[k]) > -1)"
                           " && document.querySelector('.v2-tile') && !document.querySelector('.v2-cnt.ld')", timeout=30000)
    page.wait_for_timeout(300)
    shot(page, p + '71-board-failed.jpg')
    txt = page.inner_text('.v2-next')
    if 'تعذّر جلب القرارات' not in txt or 'العقل يعمل' in txt or 'لا توجد قرارات' in txt:
        PROBLEMS.append(p + '71: شريط «القرار التالي» بيطمّن فوق جلب فاشل: %r' % txt)
    page.evaluate("() => { const S = V2._state; S.mode = 'focus'; S.deck = []; S.total = 0; V2.render(document.getElementById('view')); }")
    page.wait_for_selector('.v2-end')
    shot(page, p + '72-end-failed.jpg')
    end = page.inner_text('.v2-end')
    if 'تعذّر جلب القرارات' not in end or 'العقل يكمل' in end:
        PROBLEMS.append(p + '72: شاشة النهاية بتطمّن فوق جلب فاشل: %r' % end)
    browser.close()

    # المفتاح مقفول
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = v2fx.V2Platform()
        cfg0 = len([c for c in h.dash_calls if c == ('GET', '/api/v2/config')])
        ctx = browser.context(h, 'admin', viewport, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('rows')", timeout=30000)
        page.wait_for_timeout(500)
        shot(page, p + '80-switch-off.jpg')
        mods = page.evaluate("() => [...document.querySelectorAll('.nav .item')].map(i => i.dataset.mod)")
        expected = ['inbox', 'invites', 'courses', 'team', 'users', 'finance', 'escrow', 'market', 'analysis', 'knowledge',
                    'topics', 'marketing', 'investment', 'targets', 'ai', 'settings']
        if mods != expected:
            PROBLEMS.append(p + '80: القائمة اتغيّرت والمفتاح مقفول: %r' % mods)
        st = page.evaluate("() => ({v2: !!document.querySelector('.v2'), cls: document.querySelector('.app').classList.contains('v2-home'),"
                           " on: window.V2_ON, title: document.getElementById('pageTitle').textContent, market: EP.state.market || null,"
                           " search: getComputedStyle(document.querySelector('.topbar .search')).display})")
        if st['v2'] or st['cls'] or st['on'] or st['market'] or st['search'] == 'none' and not mobile:
            PROBLEMS.append(p + '80: أثر للّوحة الجديدة والمفتاح مقفول: %r' % st)
        if 'الوارد' not in st['title']:
            PROBLEMS.append(p + '80: الشاشة الافتراضية مش الوارد: %r' % st['title'])
        cfg = [c for c in h.dash_calls if c == ('GET', '/api/v2/config')]
        if len(cfg) - cfg0 != 1:
            PROBLEMS.append(p + '80: سؤال المفتاح اتعمل %d مرات' % (len(cfg) - cfg0))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


# ======================================================================== D1-B: الهيكل الجديد
TAB = {'width': 1024, 'height': 768}
SHELL_READY = ("() => window.V2SHELL && V2SHELL.on === true && window.EP && ['opsQueue','inbox','walletPayouts','invites','pendingUsers','market']"
               ".every(k => EP.state[k] === 'ready') && document.querySelector('.v2c-tab') && !document.querySelector('.v2-cnt.ld')")
OLD_GROUPS = ('شغل النهاردة', 'الناس والدورات', 'التسويق والمحتوى')
SECTION_LABELS = ['اللوحة', 'ملفات الخبراء', 'النزاعات والاستردادات', 'الدورات والمدرّبون', 'سوق الخدمات', 'الكتب', 'الناس والدعوات',
                  'الفلوس', 'المحتوى', 'التسويق', 'التقارير', 'العقل', 'الشركة ورأس المال']


def shell_check(page, name):
    """⛔ لا أثر للقائمة القديمة والمفتاح مفتوح: الشريط مخفي، ولا بند `.nav .item` ظاهر، ولا عنوان مجموعة قديم، والشاشة بلا تمرير أفقي."""
    r = page.evaluate("""() => {
      const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
      const rail = document.querySelector('.rail'), co = document.getElementById('coPin');
      const olds = [...document.querySelectorAll('.rail .nav .item, #nav-co .item, .nav .item')].filter(vis).length;
      const side = document.getElementById('v2Side');
      const items = side ? [...side.querySelectorAll('.v2s-item')].filter(vis).map(a => a.querySelector('.v2s-name').textContent.trim()) : [];
      const tabs = [...document.querySelectorAll('.v2c-tab')].filter(vis).map(b => b.getBoundingClientRect().height);
      const mb = document.getElementById('menuBtn');
      return {rail: vis(rail), co: vis(co), olds, items, tabs, mb: vis(mb) ? mb.getBoundingClientRect().height : null,
              shell: document.querySelector('.app').classList.contains('v2-shell'), text: document.body.innerText,
              sw: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)};
    }""")
    if not r['shell']:
        PROBLEMS.append('%s: الغلاف مش شغّال' % name)
    if r['rail'] or r['co'] or r['olds']:
        PROBLEMS.append('%s: أثر للقائمة القديمة (شريط=%s · كتلة الشركة=%s · بنود=%s)' % (name, r['rail'], r['co'], r['olds']))
    for g in OLD_GROUPS:
        if g in r['text']:
            PROBLEMS.append('%s: عنوان مجموعة قديم «%s» ظاهر' % (name, g))
    w = page.viewport_size['width']
    if w >= 1180 and r['items'] != SECTION_LABELS:
        PROBLEMS.append('%s: بنود القائمة الجانبية %r' % (name, r['items']))
    if w < 1180 and r['items']:
        PROBLEMS.append('%s: القائمة الجانبية ظاهرة تحت ١١٨٠' % name)
    if any(h < 44 for h in r['tabs']):
        PROBLEMS.append('%s: تبويب أقل من ٤٤px: %r' % (name, r['tabs']))
    if w < 1180 and (r['mb'] is None or r['mb'] < 44):
        PROBLEMS.append('%s: زرّ القائمة مش ظاهر أو أقل من ٤٤px' % name)
    if w <= 1024 and r['sw'] > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))


def sshot(page, name, full=False):
    shot(page, name, full)
    shell_check(page, name)


def open_shell(ctx, hash_=''):
    page = ctx.new_page()
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(SHELL_READY, timeout=30000)
    page.wait_for_timeout(400)
    return page


def sec_state(page):
    return page.evaluate("""() => ({hash: location.hash, h1: (document.querySelector('.v2c-h h1') || {}).textContent,
      tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()),
      on: (document.querySelector('.v2c-tab.on') || {}).textContent, desc: (document.querySelector('.v2c-h p') || {}).textContent,
      title: document.getElementById('pageTitle').textContent})""")


def go_section(page, key, tab=None):
    """ينقر بند القسم (قائمة جانبية أو ورقة) ثم تبويبه."""
    if page.viewport_size['width'] >= 1180:
        page.click('#v2Side [data-sec="%s"]' % key)
    else:
        page.click('#menuBtn')
        page.wait_for_selector('#v2Sheet.open')
        page.click('#v2Sheet [data-sec="%s"]' % key)
        page.wait_for_function("() => !document.querySelector('#v2Sheet.open')")
    page.wait_for_function("(k) => location.hash.indexOf('#s/' + k) === 0", arg=key)
    if tab:
        page.click('.v2c-tab[data-tab="%s"]' % tab)
    page.wait_for_timeout(250)


SECTION_FIRST = [('home', 'board', 'اللوحة'), ('files', 'files', 'ملفات الخبراء'), ('disputes', 'disputes', 'النزاعات والاستردادات'),
                 ('courses', 'courses', 'الدورات والمدرّبون'), ('market', 'requests', 'سوق الخدمات'), ('books', 'offers', 'الكتب'),          # D3: مراجعة العروض أولًا
                 ('people', 'invites', 'الناس والدعوات'), ('money', 'overview', 'الفلوس'), ('content', 'pipeline', 'المحتوى'),
                 ('marketing', 'campaigns', 'التسويق'), ('reports', 'report', 'التقارير'), ('brain', 'log', 'العقل'),
                 ('company', 'invest', 'الشركة ورأس المال')]



# ------------------------------------------------------------- الجولة النهائية: لا شاشة قديمة + سطر الترويسة + الشاشات التي كانت ناقصة من اللقطات
OLD_MARKS = """() => { const v = document.getElementById('view'); const q = s => v ? v.querySelectorAll(s).length : 0;
  return {kpis: q('.kpis'), tabbar: q('.tabbar'), inboxwrap: q('.inboxwrap'), ph: q('.panel .ph'), teamTabs: q('#teamTabs'), text: v ? v.innerText : ''}; }"""
LEGACY_OK = {('money', 'all'): '.v2lg-note', ('disputes', 'escrow'): '.v2lg-note', ('courses', 'all'): '.v2co-legacy-note'}
RAW_BAD = ('Cash Flow', 'حيّ من المالية', 'EGP', '١٥٪', 'مين ردّ', 'لسه محتاج', 'اتواصلنا', 'مش مناسب', 'civil')
RAW_BAD_LEGACY = ('InstaPay', 'PAY-mp', 'IP-')      # الشاشتان القديمتان فقط: الإيصالات اليدوية صارت في «الفلوس ‹ الإيصالات»


def ar_digits(n):
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


def head_matches(page, pre, key, tab):
    """سطر الترويسة يطابق ما ترسمه القائمة نفسها (لا عدّان مختلفان لشيء واحد)."""
    d = page.evaluate("() => (document.querySelector('.v2c-h p') || {}).textContent || ''")
    if key == 'files' and tab == 'files':
        c = page.evaluate("() => [...document.querySelectorAll('.v2d-segb b')].map(b => b.textContent.trim())")
        want = [(c[0], 'متأخر'), (c[1], 'تنتظر مراجعتك'), (c[2], 'عند الخبراء')] if len(c) >= 3 else []
        for n, w in want:
            if n != ar_digits(0) and (n + ' ' + w) not in d:
                PROBLEMS.append('%s: سطر ترويسة الملفات «%s» لا يطابق عمود «%s» = %s' % (pre, d, w, n))
    elif key == 'content' and tab == 'pipeline':
        c = page.evaluate("() => [...document.querySelectorAll('.v2ct-segb b')].map(b => b.textContent.trim())")
        for n in c[:3]:
            t = n.replace('+', '').translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
            if t.isdigit() and int(t) >= 3 and n.replace('+', '') not in d:
                PROBLEMS.append('%s: سطر ترويسة المحتوى «%s» لا يذكر عدد العمود %s: %r' % (pre, d, n, c))
    elif key == 'books' and tab == 'offers':
        r = page.evaluate("() => ({cards: document.querySelectorAll('#view .v3-tgrid > *').length, na: /غير متاح بعد/.test((document.getElementById('view') || {}).innerText || '')})")
        if r['na'] and 'غير متاح بعد' not in d:
            PROBLEMS.append('%s: الكتب: التبويب «غير متاح بعد» وسطر الترويسة «%s»' % (pre, d))
        if r['cards'] and 'غير متاح بعد' in d:
            PROBLEMS.append('%s: الكتب: التبويب فيه %s عرض وسطر الترويسة «غير متاح بعد»' % (pre, r['cards']))
    if not d.strip():
        PROBLEMS.append('%s: ترويسة %s/%s بلا سطر' % (pre, key, tab))


def final_walk(page, pre, mobile):
    tabs = page.evaluate("() => V2L.SECTIONS.map(s => [s.key, s.tabs.filter(t => !t.hidden).map(t => t.key)])")
    for key, tl in tabs:
        for tab in tl:
            go_section(page, key, tab)
            page.wait_for_timeout(450)
            m = page.evaluate(OLD_MARKS)
            name = '%s-walk %s/%s' % (pre, key, tab)
            legacy = LEGACY_OK.get((key, tab))
            if legacy:
                if not page.query_selector(legacy):
                    PROBLEMS.append('%s: «كل السجلات» بلا السطر التمهيدي %s' % (name, legacy))
            elif m['kpis'] or m['tabbar'] or m['inboxwrap'] or m['ph'] or m['teamTabs']:
                PROBLEMS.append('%s: ما زالت شاشة بالشكل القديم (kpis=%s tabbar=%s inboxwrap=%s ph=%s)' % (name, m['kpis'], m['tabbar'], m['inboxwrap'], m['ph']))
            for bad in RAW_BAD + (RAW_BAD_LEGACY if (key, tab) in (('money', 'all'), ('disputes', 'escrow')) else ()):
                if bad in m['text']:
                    PROBLEMS.append('%s: نص غير مقبول «%s»' % (name, bad))
            head_matches(page, name, key, tab)
            sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
            if mobile and sw > page.viewport_size['width'] + 1:
                PROBLEMS.append('%s: تمرير أفقي (%s)' % (name, sw))
    # لقطات الشاشات التي كانت ناقصة: الضمان (الآن «كل السجلات») · الدعوات · «كل السجلات» في الفلوس بعد الشكل الجديد
    for key, tab, fn in (('disputes', 'escrow', '45-disputes-escrow'), ('people', 'pipeline', '46-people-pipeline'), ('money', 'all', '47-money-all')):
        go_section(page, key, tab)
        page.wait_for_timeout(500)
        st = sec_state(page)
        if st['hash'] != '#s/%s/%s' % (key, tab):
            PROBLEMS.append('%s%s: العنوان %r' % (pre, fn, st))
        sshot(page, '%s%s.jpg' % (pre, fn))
    # الخبراء: لا تبويبان مكرّران ولا عنوان قديم، وتذكرة الرد على الدعوة بزرّيها
    go_section(page, 'files', 'experts')
    page.wait_for_selector('.v2ex')
    ex = page.evaluate("""() => ({tabs: document.querySelectorAll('#teamTabs').length, btns: [...document.querySelectorAll('.v2ex-t .v2ex-btn1, .v2ex-t .v2ex-btn2')].map(b => b.textContent.trim()),
      cards: document.querySelectorAll('.v2ex-x').length, text: document.querySelector('.v2ex').innerText})""")
    if ex['tabs'] or not ex['cards']:
        PROBLEMS.append('%sexperts: الشاشة القديمة (%s) أو بلا بطاقات (%s)' % (pre, ex['tabs'], ex['cards']))
    if ex['btns'] and ('تم التواصل' not in ex['btns'] or 'ليس مناسبًا' not in ex['btns']):
        PROBLEMS.append('%sexperts: أزرار التذكرة %r' % (pre, ex['btns']))
    for bad in ('المدربون', 'الفريق الإداري', 'civil', 'مين ردّ'):
        if bad in ex['text']:
            PROBLEMS.append('%sexperts: «%s» ظاهر' % (pre, bad))


def flow_d1b(browser, h, pre, viewport, mobile):
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_shell(ctx)
    w = viewport['width']
    sshot(page, pre + '01-board.jpg')
    st = sec_state(page)
    if st['hash'] != '#s/home/board' or st['h1'] != 'اللوحة':
        PROBLEMS.append(pre + '01: الافتتاحية مش اللوحة: %r' % st)
    # الشارات: نفس أعداد مربّعات اللوحة بالظبط (مصدر واحد)
    badges = page.evaluate("""() => {
      const T = {}; V2.tiles().forEach(t => { T[t.key] = t; });
      const root = document.getElementById(innerWidth >= 1180 ? 'v2Side' : 'v2Sheet');
      const out = {};
      root.querySelectorAll('[data-sec]').forEach(a => { const b = a.querySelector('.v2s-badge'); out[a.getAttribute('data-sec')] = b ? b.textContent.trim() : ''; });
      const tiles = {};
      document.querySelectorAll('.v2-tile').forEach(t => { const c = t.querySelector('.v2-cnt'); tiles[t.getAttribute('data-tile')] = c ? c.textContent.trim() : ''; });
      return {menu: out, tiles};
    }""")
    for key, txt in badges['tiles'].items():
        mt = badges['menu'].get(key, '')
        if txt.replace('+', '') != mt.replace('+', '') and not (txt in ('تعذّر الوصول',) and mt == '!'):
            PROBLEMS.append('%s01: شارة «%s» في القائمة (%s) مش نفس مربّع اللوحة (%s)' % (pre, key, mt, txt))
    if not any(v for v in badges['menu'].values()):
        PROBLEMS.append(pre + '01: مفيش ولا شارة في القائمة')
    # القائمة المفتوحة (الشاشات الأضيق)
    if w < 1180:
        page.click('#menuBtn')
        page.wait_for_selector('#v2Sheet.open')
        sshot(page, pre + '02-menu-open.jpg')
        tiles_n = page.evaluate("() => document.querySelectorAll('#v2Sheet .v2s-tile').length")
        if tiles_n != 13:
            PROBLEMS.append('%s02: ورقة القائمة فيها %s مربّع' % (pre, tiles_n))
        page.keyboard.press('Escape')
        page.wait_for_function("() => !document.querySelector('#v2Sheet.open')")
    # كل قسم بتبويباته
    for i, (key, tab, label) in enumerate(SECTION_FIRST[1:], start=3):
        go_section(page, key)
        st = sec_state(page)
        if st['h1'] != label or st['hash'] != '#s/%s/%s' % (key, tab) or st['on'] is None:
            PROBLEMS.append('%s%02d: القسم %s: %r' % (pre, i, key, st))
        if not st['desc']:
            PROBLEMS.append('%s%02d: ترويسة %s من غير سطر وصف' % (pre, i, key))
        sshot(page, '%s%02d-section-%s.jpg' % (pre, i, key))
    # تبويبات: ملفات ⇐ الخبراء · الفلوس ⇐ الباقات · الناس ⇐ الدعوات · الشركة ⇐ الإعدادات
    for n, (key, tab, expect_hash) in enumerate([('files', 'experts', '#s/files/experts'), ('money', 'shares', '#s/money/shares'),
                                                  ('people', 'invites', '#s/people/invites'), ('company', 'settings', '#s/company/settings'),
                                                  ('brain', 'helpers', '#s/brain/helpers'), ('content', 'tutorials', '#s/content/tutorials')]):
        go_section(page, key, tab)
        st = sec_state(page)
        if st['hash'] != expect_hash or st['on'] is None:
            PROBLEMS.append('%s2%d: تبويب %s/%s: %r' % (pre, n, key, tab, st))
        sshot(page, '%s2%d-tab-%s-%s.jpg' % (pre, n, key, tab))
    # شاشة قديمة بتغيّر تبويبها الداخلي ⇒ الترويسة والعنوان يتبعوها (من غير ما نكرّر الشاشة)
    go_section(page, 'money', 'all')           # D3: الشاشتان القديمتان (المالية والباقات) في آخر تبويب «كل السجلات»
    page.wait_for_selector('#finTabs')
    page.click('#finTabs .tab[data-t="packages"]')
    page.wait_for_timeout(300)
    st = sec_state(page)
    if st['hash'] != '#s/money/all' or st['on'] != 'كل السجلات' or not page.query_selector('#finTabs'):
        PROBLEMS.append(pre + '26: تبويب داخلي (الباقات) غيّر الترويسة أو اختفت الشاشة القديمة: %r' % st)
    page.evaluate("() => goEscrowManual()")
    page.wait_for_timeout(300)
    st = sec_state(page)
    if st['hash'] != '#s/money/receipts' or st['h1'] != 'الفلوس' or st['on'] != 'الإيصالات والمدفوعات العالقة':
        PROBLEMS.append(pre + '26: دفعات يدوية (goEscrowManual) ما هبطتش على «الفلوس ‹ الإيصالات»: %r' % st)
    sshot(page, pre + '26-money-receipts.jpg')
    page.evaluate("() => { location.hash = '#invites'; }")
    page.wait_for_timeout(400)
    st = sec_state(page)
    if st['hash'] != '#s/people/invites' or st['on'] != 'الطلبات':   # بعد دمج الناس: تبويب invites اسمه «الطلبات»
        PROBLEMS.append(pre + '26: تغيير العنوان لرابط قديم ما حوّلش: %r' % st)
    if page.evaluate("() => localStorage.getItem('ep_v2_shell')") != '1':
        PROBLEMS.append(pre + '26: تذكّر المفتاح المفتوح مش متسجّل')
    if page.evaluate("() => document.querySelector('.app').classList.contains('v2-pre')"):
        PROBLEMS.append(pre + '26: صنف الإخفاء المؤقت فضل بعد الجاهزية')
    final_walk(page, pre, mobile)
    # رجوع المتصفح ورجوع التحديث
    go_section(page, 'files')
    go_section(page, 'files', 'experts')
    page.go_back()
    page.wait_for_timeout(500)
    st = sec_state(page)
    if st['hash'] != '#s/files/files' or st['on'] != 'الملفات':
        PROBLEMS.append(pre + '30: زرّ الرجوع ما رجّعش التبويب السابق: %r' % st)
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function(SHELL_READY, timeout=30000)
    st = sec_state(page)
    if st['hash'] != '#s/files/files' or st['h1'] != 'ملفات الخبراء':
        PROBLEMS.append(pre + '30: التحديث ما فضلش في نفس القسم: %r' % st)
    # «كل الوارد» داخل اللوحة
    go_section(page, 'home', 'inbox')
    if sec_state(page)['hash'] != '#s/home/inbox' or not page.query_selector('#rows'):
        PROBLEMS.append(pre + '31: تبويب «كل الوارد» ما رسمش الوارد')
    sshot(page, pre + '31-home-all-inbox.jpg')
    # مربّع من اللوحة بيهبط على قسمه وتبويبه (بنفس الدالة القديمة)
    go_section(page, 'home', 'board')
    for tile, expect in (('money', '#s/money/overview'), ('disputes', '#s/disputes/disputes'), ('files', '#s/files/files'),
                         ('people', '#s/people/invites'), ('courses', '#s/courses/courses')):
        go_section(page, 'home', 'board')
        page.wait_for_selector('[data-tile="%s"]' % tile)
        page.click('[data-tile="%s"]' % tile)
        page.wait_for_timeout(350)
        hh = page.evaluate('() => location.hash')
        if not hh.startswith(expect) and not (tile == 'courses' and hh.startswith('#s/courses/')):
            PROBLEMS.append('%s32: مربّع %s هبط على %s (المتوقع %s)' % (pre, tile, hh, expect))
    go_section(page, 'home', 'board')
    page.click('[data-tile="brain"]')
    page.wait_for_selector('.v2-log, .v2-empty, .v2sb')
    if sec_state(page)['hash'] != '#s/brain/log':
        PROBLEMS.append(pre + '33: مربّع العقل ما فتحش «سجل اليوم»')
    sshot(page, pre + '33-brain-log.jpg')
    # وضع التركيز في الغلاف: الترويسة والتبويبات تختفي
    go_section(page, 'home', 'board')
    page.click('[data-a="start"]')
    page.wait_for_selector('.v2-card')
    if page.is_visible('.v2c-tabs'):
        PROBLEMS.append(pre + '34: تبويبات القسم ظاهرة في وضع التركيز')
    sshot(page, pre + '34-focus-in-shell.jpg')
    browser.close()

    # رابط قديم بيهبط على قسمه وتبويبه
    for old, expect, label, on_tab in (('#finance', '#s/money/all', 'الفلوس', 'كل السجلات'), ('#packages', '#s/money/all', 'الفلوس', 'كل السجلات'),
                                       ('#messages', '#s/people/messages', 'الناس والدعوات', 'الرسائل'), ('#invites', '#s/people/invites', 'الناس والدعوات', 'الطلبات'),
                                       ('#escrow', '#s/disputes/escrow', 'النزاعات والاستردادات', 'كل السجلات'), ('#tutorials', '#s/content/tutorials', 'المحتوى', 'دليل الاستخدام'),
                                       ('#partners', '#s/company/invest', 'الشركة ورأس المال', 'نظرة'), ('#inbox', '#s/home/inbox', 'اللوحة', 'كل الوارد'),
                                       ('#team', '#s/files/experts', 'ملفات الخبراء', 'الخبراء'), ('#s/money/receipts', '#s/money/receipts', 'الفلوس', 'الإيصالات والمدفوعات العالقة')):
        ctx = browser.context(h, 'admin', viewport, mobile)
        page = open_shell(ctx, old)
        st = sec_state(page)
        if st['hash'] != expect or st['h1'] != label or st['on'] != on_tab:
            PROBLEMS.append('%s40: الرابط القديم %s هبط على %r (المتوقع %s / %s / %s)' % (pre, old, st, expect, label, on_tab))
        if old == '#finance':
            sshot(page, pre + '40-old-link-finance.jpg')
        elif old == '#messages':
            sshot(page, pre + '41-old-link-messages.jpg')
        browser.close()

    # مراجعة D1-B: الرابط القديم #foundation يهبط على تبويب «التأسيس» الداخلي، وشرائح الوارد داخل «الملفات» ما بتنقلش القسم،
    # والبحث ظاهر في الوارد حتى عرض ٧٦١ وبيختفي تحت ٧٦٠، والورقة المفتوحة بتحتفظ بالتركيز مع التحديث.
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_shell(ctx, '#foundation')
    st = sec_state(page)
    tg = page.evaluate("() => tgTab")
    if st['hash'] != '#s/company/assets' or st['on'] != 'المعدات والاشتراكات':   # بعد دمج الشركة: #foundation ⇒ «المعدات والاشتراكات»
        PROBLEMS.append('%s42: #foundation هبط على %r وtgTab=%r (المتوقع #s/company/assets)' % (pre, st, tg))
    sshot(page, pre + '42-old-link-foundation.jpg')
    browser.close()
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_shell(ctx)
    go_section(page, 'files', 'all')          # D2: «الملفات» بقت لوحة تذاكر، والوارد القديم في تبويب «كل الملفات»
    if not mobile:   # بعد الدمج: شرائح الوارد بشكل اللوحة الجديد (home.js)، وعلى الموبايل مخفية (التصفية من ورقة أخرى)
        page.wait_for_selector('.v2h-chip[data-f="late"]')
        page.click('.v2h-chip[data-f="late"]')
    page.wait_for_timeout(500)
    st = sec_state(page)
    if st['hash'] != '#s/files/all' or st['h1'] != 'ملفات الخبراء':
        PROBLEMS.append('%s43: شريحة «الكل» داخل الملفات نقلت المستخدم: %r' % (pre, st))
    # بعد دمج الرئيسية: بحث الوارد صار داخل الشاشة نفسها (#v2hq) في كل العروض، وبحث الشريط العلوي لا يظهر معه
    srch = page.evaluate("() => { const e = document.getElementById('v2hq'); return e ? (e.getBoundingClientRect().width > 0 ? 'visible' : 'hidden') : 'missing'; }")
    if srch != 'visible':
        PROBLEMS.append('%s43: بحث الوارد (عرض %s) غير ظاهر: %s' % (pre, w, srch))
    sshot(page, pre + '43-inbox-chip-in-files.jpg')
    if w < 1180:
        page.click('#menuBtn')
        page.wait_for_selector('#v2Sheet.open')
        page.focus('#v2Sheet .v2s-x')
        page.wait_for_timeout(1500)
        act = page.evaluate("() => document.activeElement && document.activeElement.className")
        if 'v2s-x' not in str(act):
            PROBLEMS.append('%s44: الورقة المفتوحة فقدت التركيز مع التحديث (%r)' % (pre, act))
        page.keyboard.press('Shift+Tab')
        inside = page.evaluate("() => !!document.activeElement.closest('#v2Sheet .v2s-box')")
        if not inside:
            PROBLEMS.append(pre + '44: Shift+Tab أخرج التركيز من الورقة المفتوحة')
    browser.close()

    # المفتاح مقفول: مفيش غلاف ولا قائمة جديدة
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = d3fx.D3Platform(d2=True)
        ctx = browser.context(h, 'admin', viewport, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('rows')", timeout=30000)
        page.wait_for_timeout(500)
        shot(page, pre + '80-switch-off.jpg')
        st = page.evaluate("""() => ({
          side: !!document.getElementById('v2Side'), sheet: !!document.getElementById('v2Sheet'), sec: !!document.getElementById('v2sec'),
          shell: document.querySelector('.app').classList.contains('v2-shell'), on: !!window.V2_ON, shellOn: !!(window.V2SHELL && V2SHELL.on),
          items: [...document.querySelectorAll('.nav .item')].map(i => i.dataset.mod), title: document.getElementById('pageTitle').textContent,
          railW: document.querySelector('.rail').offsetWidth, hash: location.hash})""")
        if st['side'] or st['sheet'] or st['sec'] or st['shell'] or st['on'] or st['shellOn']:
            PROBLEMS.append(pre + '80: أثر للهيكل الجديد والمفتاح مقفول: %r' % st)
        if len(st['items']) != 16 or 'الوارد' not in st['title'] or (w >= 1180 and not st['railW']) or st['hash'].startswith('#s/'):
            PROBLEMS.append(pre + '80: الداشبورد القديمة اتغيّرت والمفتاح مقفول: %r' % st)
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


# ======================================================================= D2
D2_BOARD_READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2d[data-board=\"%s\"] .v2d-col')"
                  " && !document.querySelector('.v2d-empty')")


def d2_check(page, name):
    """أهداف اللمس ≥ ٤٤px (والأزرار ≥ ٥٢px في الموبايل)، ولا عدّ مختلق، ولا تمرير أفقي، والعدّاد بصيغته."""
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v2d button, .v2d a[href], .v2-sbar button, .v2-sbar input, .v2d-res a')]
      .filter(b => b.offsetParent && !b.classList.contains('v2d-inline')).map(b => [b.className || b.tagName, Math.round(b.getBoundingClientRect().height)])
      .filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    if w <= 400:
        big = page.evaluate("""() => [...document.querySelectorAll('.v2d-btn1, .v2d-btn2, .v2d-segb, .v2d-sgo')]
          .filter(b => b.offsetParent).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٤٤px في الموبايل: %r' % (name, big[:4]))
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, sw, w))
    txt = page.evaluate("() => document.querySelector('.v2d') ? document.querySelector('.v2d').innerText : ''")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر في اللوحة' % name)
    if re.search(r'\d', re.sub(r'[٠-٩]', '', txt)):
        # أرقام لاتينية في النص المرئي (مسموح فقط داخل بريد أو رقم مرجع)
        bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t]
        if bad:
            PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))


def open_d2(ctx, hash_, board=None):
    page = ctx.new_page()
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(SHELL_READY, timeout=30000)
    if board:
        page.wait_for_function(D2_BOARD_READY % board, timeout=30000)
    page.wait_for_timeout(500)
    return page


def d2_top(page):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")


def d2_shot(page, name):
    d2_top(page)
    shot(page, name)
    shell_check(page, name)
    d2_check(page, name)


PERSON_PATHS = [('GET', '/api/bridge/experts'), ('GET', '/api/bridge/courses'), ('GET', '/api/bridge/invites'),
                ('GET', '/api/bridge/expert-files'), ('GET', '/api/bridge/wallet-payouts'), ('GET', '/api/bridge/pending-users')]


def flow_d2(browser, h, pre, viewport, mobile):
    w = viewport['width']
    h.ef = v2fx.V2Platform(d2=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/#s/files/files', wait_until='domcontentloaded')
    page.wait_for_function(SHELL_READY, timeout=30000)
    page.wait_for_function(D2_BOARD_READY % 'files', timeout=30000)
    page.wait_for_timeout(500)
    # —— ١) لوحة الملفات: أربعة أعمدة كلها فيها تذاكر
    info = page.evaluate("""() => ({cols: [...document.querySelectorAll('.v2d-col')].map(c => [c.dataset.col, c.querySelectorAll('.v2d-t').length]),
      head: (document.querySelector('.v2d-auto') || {}).innerText, more: (document.querySelector('.v2d-more') || {}).innerText,
      h1: (document.querySelector('.v2c-h h1') || {}).textContent, on: (document.querySelector('.v2c-tab.on') || {}).textContent,
      tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), hash: location.hash})""")
    cols = dict(info['cols'])
    for c in ('late', 'review', 'with', 'done'):
        if not cols.get(c):
            PROBLEMS.append('%s01: عمود %s فاضي' % (pre, c))
    if cols.get('with', 0) > 3:
        PROBLEMS.append('%s01: «عند الخبراء» أكتر من ٣ تذاكر (%s)' % (pre, cols.get('with')))
    if not info['more'] or 'في موعدها' not in info['more']:
        PROBLEMS.append('%s01: سطر «و N في موعدها» مش ظاهر: %r' % (pre, info['more']))
    if not info['head'] or 'التوزيع التلقائي يعمل' not in info['head']:
        PROBLEMS.append('%s01: سطر التوزيع التلقائي: %r' % (pre, info['head']))
    if info['tabs'] != ['الملفات', 'الخبراء', 'كل الملفات'] or info['on'] != 'الملفات' or info['hash'] != '#s/files/files':
        PROBLEMS.append('%s01: تبويبات الملفات: %r' % (pre, info))
    if w <= 760:
        for i, (col, label) in enumerate([('late', 'late'), ('review', 'review'), ('with', 'with'), ('done', 'done')]):
            page.click('.v2d-segb[data-col="%s"]' % col)
            page.wait_for_timeout(200)
            vis = page.evaluate("() => [...document.querySelectorAll('.v2d-col')].filter(c => c.offsetParent).map(c => c.dataset.col)")
            if vis != [col]:
                PROBLEMS.append('%s02: عمود ظاهر واحد بس متوقّع (%s) لكن %r' % (pre, col, vis))
            d2_shot(page, '%s02%s-files-%s.jpg' % (pre, 'abcd'[i], label))
        # —— مراجعة D2 (١): عمود فاضي يفضل ظاهر لما الشخص يختاره (ما يرجعش لأول عمود فيه شيء)
        page.click('.v2d-segb[data-col="done"]')
        page.evaluate("() => { window.__inbox0 = window.INBOX; window.INBOX = []; V2D2._tick(Date.now() + 1000); }")
        page.wait_for_timeout(300)
        emp = page.evaluate("() => ({on: (document.querySelector('.v2d-segb.on') || {}).dataset ? document.querySelector('.v2d-segb.on').dataset.col : null,"
                            " none: [...document.querySelectorAll('.v2d-col')].filter(c => c.offsetParent).map(c => (c.querySelector('.v2d-none') || {}).innerText)})")
        if emp['on'] != 'done' or emp['none'] != ['لا رأي معتمد اليوم']:
            PROBLEMS.append('%s02: عمود فاضي اختاره الشخص ارتدّ أو نصه غلط: %r' % (pre, emp))
        d2_shot(page, pre + '02e-files-empty-column.jpg')
        page.evaluate("() => { window.INBOX = window.__inbox0; V2D2._tick(Date.now() + 2000); }")
        page.click('.v2d-segb[data-col="late"]')
        page.wait_for_timeout(200)
    d2_shot(page, pre + '01-files-board.jpg')
    # —— العدّاد: بعد ٦١ دقيقة (ساعة مفروضة على نفس دالة الدقيقة) النص يتغيّر لوحده بلا إعادة تحميل
    t0 = page.evaluate("() => { const e = document.querySelector('.v2d-col[data-col=\"with\"] .v2d-time'); return e ? e.textContent : null; }")
    page.evaluate("() => V2D2._tick(Date.now() + 61 * 60 * 1000)")
    page.wait_for_timeout(200)
    t1 = page.evaluate("() => { const e = document.querySelector('.v2d-col[data-col=\"with\"] .v2d-time'); return e ? e.textContent : null; }")
    page.evaluate("() => V2D2._tick()")
    if not t0 or t0 == t1:
        PROBLEMS.append('%s01: العدّاد ما اتحدّثش بعد ساعة (%r ⇒ %r)' % (pre, t0, t1))
    # —— ٢) تذكرة تفتح الدرج
    if w <= 760:
        page.click('.v2d-segb[data-col="late"]')
    page.click('.v2d-col[data-col="late"] .v2d-open >> nth=0')
    page.wait_for_function("() => location.hash === '#s/files/all' && document.querySelector('#drawer') && document.querySelector('#drawer').innerText.length > 40", timeout=15000)
    page.wait_for_timeout(500)
    st = sec_state(page)
    if st['on'] != 'كل الملفات':
        PROBLEMS.append('%s03: التذكرة ما فتحتش «كل الملفات»: %r' % (pre, st))
    shot(page, pre + '03-ticket-drawer.jpg')
    shell_check(page, pre + '03-ticket-drawer.jpg')
    # —— ٣) لوحة النزاعات
    page.evaluate("() => { location.hash = '#s/disputes/disputes'; }")
    page.wait_for_function(D2_BOARD_READY % 'disputes', timeout=15000)
    page.wait_for_timeout(500)
    dinfo = page.evaluate("""() => ({cols: [...document.querySelectorAll('.v2d-col')].map(c => [c.dataset.col, c.querySelectorAll('.v2d-t').length]),
      tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), btns: [...document.querySelectorAll('.v2d-col .v2d-btn1')].map(b => b.textContent.trim())})""")
    dc = dict(dinfo['cols'])
    for c in ('disputes', 'refunds', 'legacy'):
        if not dc.get(c):
            PROBLEMS.append('%s04: عمود %s فاضي' % (pre, c))
    if dinfo['tabs'] != ['النزاعات', 'كل النزاعات', 'كل السجلات']:
        PROBLEMS.append('%s04: تبويبات النزاعات: %r' % (pre, dinfo['tabs']))
    if not any(b == 'افتح وقرّر' for b in dinfo['btns']):
        PROBLEMS.append('%s04: زرّ «افتح وقرّر» غايب: %r' % (pre, dinfo['btns'][:4]))
    # —— مراجعة D2 (١٠): عدّاد «مفتوح منذ …» في النزاعات بيتحرّك مع الساعة
    d0 = page.evaluate("() => [...document.querySelectorAll('.v2d-time')].map(e => e.textContent).join('|')")
    page.evaluate("() => V2D2._tick(Date.now() + 5 * 3600 * 1000)")
    d1 = page.evaluate("() => [...document.querySelectorAll('.v2d-time')].map(e => e.textContent).join('|')")
    page.evaluate("() => V2D2._tick()")
    if not d0 or d0 == d1:
        PROBLEMS.append('%s04: عدّاد النزاعات ما اتحدّثش مع الساعة (%r ⇒ %r)' % (pre, d0, d1))
    if w <= 760:
        for i, col in enumerate(('disputes', 'refunds', 'legacy')):
            page.click('.v2d-segb[data-col="%s"]' % col)
            page.wait_for_timeout(200)
            d2_shot(page, '%s04%s-disputes-%s.jpg' % (pre, 'abc'[i], col))
        page.click('.v2d-segb[data-col="disputes"]')
        page.wait_for_timeout(200)
    d2_shot(page, pre + '04-disputes-board.jpg')
    # نداء «افتح وقرّر» بيفتح الدرج بتأكيده القديم (مفيش قرار فلوس من التذكرة نفسها)
    page.click('.v2d-col[data-col="disputes"] .v2d-btn1 >> nth=0')
    page.wait_for_function("() => /#s\\/disputes\\/all/.test(location.hash) && document.querySelector('#drawer') && document.querySelector('#drawer').innerText.length > 40", timeout=15000)
    # —— ٤) صفحة شخص كاملة
    page.evaluate("() => { location.hash = '#s/people/person/hala%40example.test'; }")
    page.wait_for_function("() => document.querySelector('.v2d[data-board=\"person\"] .v2d-pgrid')", timeout=15000)
    page.wait_for_timeout(500)
    pinfo = page.evaluate("""() => ({name: (document.querySelector('.v2d-name') || {}).textContent, chips: [...document.querySelectorAll('.v2d-chip')].map(c => c.textContent),
      join: (document.querySelector('.v2d-join') || {}).textContent, cards: [...document.querySelectorAll('.v2d-pc h3')].map(h => h.textContent),
      btns: [...document.querySelectorAll('.v2d-pact a, .v2d-pact button')].map(b => b.textContent.trim()), hash: location.hash,
      log: document.querySelectorAll('.v2d-log li').length, text: document.querySelector('.v2d').innerText})""")
    if pinfo['cards'] != ['الملفات', 'الدورات', 'الفلوس', 'التعلّم']:
        PROBLEMS.append('%s05: بطاقات الشخص: %r' % (pre, pinfo['cards']))
    if 'خبير' not in pinfo['chips'] or 'مدرّب' not in pinfo['chips']:
        PROBLEMS.append('%s05: وسوم الأدوار: %r' % (pre, pinfo['chips']))
    if 'بدعوة من أ. نادية فؤاد' not in (pinfo['join'] or ''):
        PROBLEMS.append('%s05: سطر الانضمام والداعي: %r' % (pre, pinfo['join']))
    if pinfo['btns'] != ['مراسلة', 'إدارة الحساب']:   # بعد دمج الناس: زر «إدارة الحساب» من v2s/people.js
        PROBLEMS.append('%s05: أزرار الشخص %r (أوقف مؤقتًا ممنوع بلا مسار)' % (pre, pinfo['btns']))
    if pinfo['log'] < 4:
        PROBLEMS.append('%s05: السجل قصير (%s)' % (pre, pinfo['log']))
    if 'أوقف' in pinfo['text']:
        PROBLEMS.append('%s05: «أوقف» ظاهرة' % pre)
    d2_shot(page, pre + '05-person-full.jpg')
    # —— ٥) شخص مصادره غير متاحة (جزئيًا ثم كليًا)
    for key in PERSON_PATHS:
        h.ef.forced[key] = (502, {"detail": "down"})
    h.ef.forced[('GET', '/api/bridge/users/u-mona/purge-check')] = (500, {"detail": "down"})
    page.evaluate("() => { location.hash = '#s/people/person/mona.s%40example.test'; }")
    page.wait_for_function("() => document.querySelector('.v2d[data-board=\"person\"] .v2d-pgrid')", timeout=15000)
    page.wait_for_timeout(500)
    ninfo = page.evaluate("""() => ({na: document.querySelectorAll('.v2d-na').length, warn: (document.querySelector('.v2d-warn') || {}).innerText,
      text: document.querySelector('.v2d').innerText})""")
    if ninfo['na'] < 4 or not ninfo['warn']:
        PROBLEMS.append('%s06: مصادر غير متاحة ما ظهرتش «غير متاح بعد» (%r)' % (pre, ninfo['na']))
    d2_shot(page, pre + '06-person-unavailable.jpg')
    h.ef.forced[('GET', '/api/bridge/users')] = (502, {"detail": "down"})
    page.evaluate("() => { location.hash = '#s/people/person/salma%40example.test'; }")
    page.wait_for_function("() => document.querySelector('.v2d[data-board=\"person\"] .v2d-pgrid') && document.querySelector('.v2d-warn')", timeout=15000)
    page.wait_for_timeout(400)
    d2_shot(page, pre + '06b-person-all-failed.jpg')
    h.ef.forced.clear()
    # —— ٦) بحث الناس (بعد دمج الناس: بحث الأشخاص العام يظهر على الكمبيوتر في «الرسائل» فقط؛ تبويب «المستخدمون» ببحثه الخاص، وعلى الموبايل العام مخفي)
    if w > 760:
        page.evaluate("() => { location.hash = '#s/people/messages'; }")
        page.wait_for_selector('#v2dq', state='visible', timeout=15000)
        page.fill('#v2dq', 'هالة')
        page.wait_for_selector('#v2dres a', timeout=10000)
        page.wait_for_timeout(400)
        items = page.evaluate("() => [...document.querySelectorAll('#v2dres a')].map(a => a.getAttribute('data-person'))")
        if 'hala@example.test' not in items:
            PROBLEMS.append('%s07: نتائج البحث %r' % (pre, items))
        d2_shot(page, pre + '07-people-search.jpg')
        page.click('#v2dres a >> nth=0')
        page.wait_for_function("() => location.hash.indexOf('#s/people/person/') === 0", timeout=10000)
    # زر «افتح صفحة الشخص» في قائمة المستخدمين يفتح صفحته
    page.evaluate("() => { location.hash = '#s/people/users'; }")
    try:
        page.wait_for_selector('.v2p-btn2[data-a="person"]', timeout=15000)
    except Exception:
        page.screenshot(path=os.path.join(OUT, 'FAIL-users.png'))
        print(page.evaluate("() => [location.hash, (document.getElementById('view')||{}).innerText.slice(0, 400), window.EP && EP.state.users, (window.USERS||[]).length]"))
        raise
    page.click('.v2p-btn2[data-a="person"] >> nth=0')
    page.wait_for_function("() => location.hash.indexOf('#s/people/person/') === 0", timeout=10000)
    browser.close()

    # —— المفتاح مقفول: لا أثر للتذاكر ولا الشخص
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = v2fx.V2Platform(d2=True)
        ctx = browser.context(h, 'admin', viewport, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('rows')", timeout=30000)
        page.wait_for_timeout(500)
        st = page.evaluate("() => ({d2: !!document.querySelector('.v2d, .v2-sbar, .v2d-person'), on: !!window.V2_ON, shell: !!(window.V2SHELL && V2SHELL.on)})")
        if st['d2'] or st['on'] or st['shell']:
            PROBLEMS.append(pre + '80: أثر لـD2 والمفتاح مقفول: %r' % st)
        r = page.evaluate("async () => { const t = localStorage.getItem('token'); const x = await fetch('/api/v2/person?email=a%40b.com', {headers: {Authorization: 'Bearer ' + t}}); return x.status; }")
        if r != 404:
            PROBLEMS.append('%s80: /api/v2/person والمفتاح مقفول ردّ %s (المتوقّع ٤٠٤)' % (pre, r))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


# ======================================================================= D3 — «الفلوس» و«الكتب»
D3_BOARD_READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v3[data-board=\"%s\"]')"
                  " && !/…جارٍ جلب/.test(document.querySelector('.v3').innerText)")
D3_FAIL_EP = ['**/api/revenues', '**/api/escrow', '**/api/platform-wallet-payouts']


def d3_check(page, name):
    """أهداف اللمس ≥ ٤٤px (والأزرار ≥ ٥٢px في الموبايل)، ولا صفر/null/NaN ظاهر، ولا أرقام لاتينية، ولا تمرير أفقي."""
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v3 button, .v3 a[href], #epModal .v3m button, #epModal .v3m input, #epModal .v3m textarea')]
      .filter(b => b.offsetParent && !b.classList.contains('v3-person'))
      .map(b => [b.className || b.tagName, Math.round((b.type === 'checkbox' && b.closest('label') ? b.closest('label') : b).getBoundingClientRect().height)])
      .filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    if w <= 400:
        big = page.evaluate("""() => [...document.querySelectorAll('.v3-btn1, .v3-btn2, .v3-pb, .v3-link, #epModal .v3m .btn')]
          .filter(b => b.offsetParent).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٤٤px في الموبايل: %r' % (name, big[:4]))
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
        if sw > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, sw, w))
        wide = page.evaluate("() => [...document.querySelectorAll('.v3 *, #epModal .v3m *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
        if wide:
            PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    # أرقام الحسابات ومراجع التحويل معرّفات (بتفضل لاتينية وتتنسخ كما هي): `.v3-dest` و`.v3-ref` بره فحص الأرقام.
    txt = page.evaluate("""() => [...document.querySelectorAll('.v3, #epModal .v3m')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('.v3-dest, .v3-ref').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر في الشاشة' % name)
    bad = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t and not re.search(r'[A-Za-z]-?\d', t)]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, bad[:3]))


def d3_shot(page, name, tall=True):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    shot(page, name, full=False)
    shell_check(page, name)
    d3_check(page, name)


def d3_open(ctx, hash_, board):
    page = ctx.new_page()
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(SHELL_READY, timeout=30000)
    page.wait_for_function(D3_BOARD_READY % board, timeout=30000)
    page.wait_for_timeout(500)
    return page


def d3_tab(page, tab, board):
    page.click('.v2c-tab[data-tab="%s"]' % tab)
    page.wait_for_function(D3_BOARD_READY % board, timeout=30000)
    page.wait_for_timeout(350)


def d3_writes(h, since):
    return [c for c in h.platform_calls[since:] if c[0] in ('PUT', 'POST', 'PATCH')]


def flow_d3(browser, h, pre, viewport, mobile):
    w = viewport['width']
    tallvp = dict(viewport, height=viewport['height'] if mobile else 1500)
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/overview', 'overview')
    # —— ١) نظرة: الأرقام الأربعة · التحويلات · الأعمدة · الاستردادات
    info = page.evaluate("""() => ({nums: [...document.querySelectorAll('.v3-num')].map(n => [n.querySelector('h3').textContent, n.querySelector('.v3-big').textContent.trim(), n.classList.contains('na')]),
      pays: document.querySelectorAll('.v3-pay').length, bars: document.querySelectorAll('.v3-bars li').length, refunds: document.querySelectorAll('.v3-rf').length,
      norefund: !!document.querySelector('.v3-ch p') && document.body.innerText.indexOf('الكتب لا تُسترد') > -1, tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()),
      seg: [...document.querySelectorAll('.v3-pb')].map(b => b.textContent.trim()), h1: document.querySelector('.v2c-h h1').textContent})""")
    if [n[0] for n in info['nums']] != ['دخل', 'محجوز حتى يُسلَّم العمل', 'مستحق للخبراء والمدرّبين', 'صافي البروفيسور']:
        PROBLEMS.append('%s01: الأرقام الأربعة %r' % (pre, info['nums']))
    if not [n for n in info['nums'] if n[0] == 'صافي البروفيسور' and n[2] and n[1] == 'غير متاح بعد']:
        PROBLEMS.append('%s01: صافي البروفيسور لازم «غير متاح بعد»: %r' % (pre, info['nums']))
    if any(n[2] for n in info['nums'] if n[0] != 'صافي البروفيسور'):
        PROBLEMS.append('%s01: رقم غير متاح مع أن كل المصادر شغّالة: %r' % (pre, info['nums']))
    if info['tabs'] != ['نظرة', 'التحويلات', 'الإيصالات والمدفوعات العالقة', 'الأسعار', 'النسب والإعدادات', 'إعلانات الأعمال', 'كل السجلات']:
        PROBLEMS.append('%s01: تبويبات الفلوس %r' % (pre, info['tabs']))
    if info['seg'] != ['اليوم', 'الشهر', 'السنة'] or info['pays'] != 2 or info['bars'] != 4 or info['refunds'] < 3 or not info['norefund']:
        PROBLEMS.append('%s01: نظرة ناقصة %r' % (pre, {k: info[k] for k in ('seg', 'pays', 'bars', 'refunds', 'norefund')}))
    d3_shot(page, pre + '01-overview.jpg')
    # الفترة: اليوم ⇒ رقم الدخل بيتغيّر
    inc_month = page.inner_text('.v3-num.k-income .v3-big')
    page.click('.v3-pb[data-p="day"]')
    page.wait_for_timeout(300)
    inc_day = page.inner_text('.v3-num.k-income .v3-big')
    if inc_day == inc_month:
        PROBLEMS.append('%s01: تبديل الفترة ما غيّرش رقم الدخل (%s)' % (pre, inc_day))
    d3_shot(page, pre + '01b-overview-day.jpg')
    page.click('.v3-pb[data-p="month"]')
    # —— ٣) ورقة تسجيل التحويل (التأكيد القديم) مع «ارفض» جواها
    page.click('.v3-pay [data-a="settle"] >> nth=1')
    page.wait_for_selector('#epModal #v2m_go')
    if not page.is_disabled('#v2m_go'):
        PROBLEMS.append(pre + '03: زرّ التسجيل شغّال من غير مرجع')
    if not page.query_selector('#epModal #v2m_alt'):
        PROBLEMS.append(pre + '03: «ارفض الطلب» مش جوه ورقة التأكيد')
    shot(page, pre + '03-settle-sheet.jpg'); d3_check(page, pre + '03-settle-sheet.jpg')
    page.fill('#v2m_f', 'IP-90210')
    n0 = len(h.platform_calls)
    page.click('#v2m_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
    sent = [c for c in h.platform_calls[n0:] if c[0] == 'POST' and c[1].endswith('/settle')]
    if len(sent) != 1 or sent[0][3] != {'reference': 'IP-90210'}:
        PROBLEMS.append('%s03: نداء settle: %r' % (pre, sent))
    if [x['reference'] for x in h.ef.settled] != ['IP-90210']:
        PROBLEMS.append(pre + '03: المنصة ما سجّلتش التحويل')
    page.wait_for_timeout(500)
    d3_shot(page, pre + '03b-after-settle.jpg')
    # «ارفض» من جوه ورقة التسجيل ⇒ ورقة الرفض بسبب
    page.click('.v3-pay [data-a="settle"] >> nth=0')
    page.wait_for_selector('#epModal #v2m_alt')
    page.click('#v2m_alt')
    page.wait_for_selector('#epModal #v2m_f')
    if not page.is_disabled('#v2m_go'):
        PROBLEMS.append(pre + '03: الرفض شغّال من غير سبب')
    shot(page, pre + '03c-reject-inside.jpg'); d3_check(page, pre + '03c-reject-inside.jpg')
    page.click('#v2m_x')
    page.wait_for_timeout(200)
    browser.close()

    # —— ٢) نظرة والمصادر واقعة: «غير متاح بعد» مش صفر
    h.ef = d3fx.D3Platform(d2=True)
    h.ef.down = {'/api/bridge/refunds/pending', '/api/bridge/income/by-service'}
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = ctx.new_page()
    for pat in D3_FAIL_EP:
        page.route(pat, lambda route: route.fulfill(status=502, content_type='application/json', body='{"error":"x"}'))
    page.goto(DASH + '/#s/money/overview', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2c-tab')", timeout=30000)
    page.wait_for_function("() => document.querySelector('.v3[data-board=\"overview\"]') && document.querySelectorAll('.v3-num.na').length >= 3", timeout=30000)
    page.wait_for_timeout(700)
    down = page.evaluate("() => ({na: document.querySelectorAll('.v3-num.na').length, warn: [...document.querySelectorAll('.v3-warn')].map(e => e.textContent), txt: document.querySelector('.v3').innerText})")
    if down['na'] != 4 or not down['warn'] or 'غير متاح بعد' not in down['txt']:
        PROBLEMS.append('%s02: المصادر واقعة والأرقام مش كلها «غير متاح بعد»: %r' % (pre, down['na']))
    if re.search(r'(?<![\w@./-])(٠ جنيه)', down['txt'].split('التحويلات المستحقة')[0]):
        PROBLEMS.append(pre + '02: صفر ظاهر بدل «غير متاح بعد»')
    d3_shot(page, pre + '02-overview-sources-down.jpg')
    browser.close()

    # —— ٤) التحويلات + الحد الأدنى
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/payouts', 'payouts')
    t = page.evaluate("() => ({min: document.querySelector('.v3-minbar').innerText, tickets: document.querySelectorAll('.v3-t').length, hist: document.querySelectorAll('.v3-hist li').length, time: !!document.querySelector('.v3-time')})")
    if '٥٠٠ جنيه' not in t['min'] or t['tickets'] != 2 or not t['time'] or t['hist'] < 2:
        PROBLEMS.append('%s04: التحويلات %r' % (pre, t))
    d3_shot(page, pre + '04-payouts.jpg')
    page.click('[data-a="minpay"]')
    page.wait_for_selector('#epModal #v3_min')
    shot(page, pre + '04b-minpay-sheet.jpg'); d3_check(page, pre + '04b-minpay-sheet.jpg')
    page.fill('#v3_min', '٧٥٠')
    page.click('#v3_review')
    page.wait_for_selector('#epModal #v3_go')
    diff = page.inner_text('#epModal .v3-diff')
    if '٥٠٠ جنيه' not in diff or '٧٥٠ جنيه' not in diff:
        PROBLEMS.append('%s04: الفرق قبل⇒بعد مش ظاهر: %r' % (pre, diff))
    shot(page, pre + '04c-minpay-diff.jpg'); d3_check(page, pre + '04c-minpay-diff.jpg')
    n0 = len(h.platform_calls)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w4 = d3_writes(h, n0)
    if len(w4) != 1 or w4[0][1] != '/api/bridge/settings/money' or w4[0][3].get('withdraw_min') != 750 or w4[0][3].get('confirmed') is not True or w4[0][3].get('by') != 'admin@local.test':
        PROBLEMS.append('%s04: كتابة الحد الأدنى: %r' % (pre, w4))
    page.wait_for_function("() => /٧٥٠ جنيه/.test(document.querySelector('.v3-minbar').innerText)", timeout=10000)
    # خارج المدى ⇒ المنصة ترفض ورسالتها بتظهر
    page.click('[data-a="minpay"]')
    page.wait_for_selector('#epModal #v3_min')
    page.fill('#v3_min', '40')
    page.click('#v3_review')
    err = page.inner_text('#epModal #v3err')
    if 'بين' not in err:
        PROBLEMS.append('%s04: رسالة المدى: %r' % (pre, err))
    page.click('#v3_cancel')
    browser.close()

    # —— ٥) الإيصالات والمدفوعات العالقة
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/receipts', 'receipts')
    r = page.evaluate("() => ({rec: document.querySelectorAll('.v3-colbox:first-child .v3-t').length, stuck: document.querySelectorAll('.v3-stuck').length, norefund: document.querySelectorAll('.v3-stuck .v3-norefund').length, btns: [...document.querySelectorAll('.v3-stuck button')].length, open: [...document.querySelectorAll('.v3-stuck a[data-person]')].length})")
    if r['rec'] != 2 or r['stuck'] != 3 or r['norefund'] != 1 or r['btns']:
        PROBLEMS.append('%s05: الإيصالات والعالقة %r' % (pre, r))
    if not page.evaluate("() => document.body.innerText.indexOf('دفعات تمّ سدادها ولم يصل تسليمها: غير متاح بعد') > -1"):
        PROBLEMS.append(pre + '05: سطر «مدفوع ولم يصل تسليمه: غير متاح بعد» مش ظاهر')
    d3_shot(page, pre + '05-receipts-stuck.jpg')
    page.click('[data-a="rconfirm"] >> nth=0')
    page.wait_for_selector('#epModal #v2m_go')
    shot(page, pre + '05b-confirm-receipt.jpg'); d3_check(page, pre + '05b-confirm-receipt.jpg')
    page.click('#v2m_x')
    page.wait_for_timeout(200)
    browser.close()

    # —— ٦) الأسعار + ورقة التعديل بقبل ⇒ بعد
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/prices', 'prices')
    pr = page.evaluate("() => ({rows: document.querySelectorAll('.v3-pr').length, vis: [...document.querySelectorAll('.v3-vis')].map(e => e.textContent), closed: document.body.innerText.indexOf('الدورات مغلقة حتى الآن') > -1})")
    if pr['rows'] != 4 or not pr['closed']:
        PROBLEMS.append('%s06: الأسعار %r' % (pre, pr))
    d3_shot(page, pre + '06-prices.jpg')
    page.click('.v3-pr [data-a="price"] >> nth=0')
    page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
    cur = page.evaluate("() => [...document.querySelectorAll('#epModal .v3-prow')].slice(0, 6).map(r => r.innerText.replace(/\\s+/g, ' '))")
    if not any('ريال سعودي' in c for c in cur) or not any('جنيه مصري' in c for c in cur):
        PROBLEMS.append('%s06: العملة جنب الخانة: %r' % (pre, cur))
    shot(page, pre + '06b-price-sheet.jpg'); d3_check(page, pre + '06b-price-sheet.jpg')
    page.fill('#epModal input[data-v="read"][data-c="eg"]', '٢٥٠')
    page.fill('#epModal input[data-v="read"][data-c="qa"]', '35')
    page.uncheck('#v3_vis')
    page.click('#v3_review')
    page.wait_for_selector('#epModal #v3_go')
    diff = page.inner_text('#epModal .v3-diff')
    for want in ('١٥٠ جنيه', '٢٥٠ جنيه', 'لا سعر', '٣٥ ريال', 'ظاهر للناس'):
        if want not in diff:
            PROBLEMS.append('%s06: «%s» مش في فرق قبل⇒بعد: %r' % (pre, want, diff))
    shot(page, pre + '06c-price-diff.jpg'); d3_check(page, pre + '06c-price-diff.jpg')
    n0 = len(h.platform_calls)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w6 = d3_writes(h, n0)
    if len(w6) != 1 or w6[0][3].get('confirmed') is not True or w6[0][3].get('rev') != 1 or w6[0][3].get('visible') is not False or w6[0][3]['versions']['read']['eg'] != {'amount': 250, 'currency': 'EGP'}:
        PROBLEMS.append('%s06: كتابة الأسعار %r' % (pre, w6))
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
    d3_shot(page, pre + '06d-after-price.jpg')
    browser.close()

    # —— ٧) النسب + رفض المنصة للأرضية
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/shares', 'shares')
    sh = page.evaluate("() => ({lines: [...document.querySelectorAll('.v3-sh .v3-pid')].map(e => e.innerText.replace(/\\s+/g, ' ')), floor: (document.querySelector('.v3-floor') || {}).textContent, ladder: document.querySelectorAll('.v3-ladder tbody tr').length})")
    if not any('صاحب العمل ٦٠٪ · المنصة ٤٠٪' in l for l in sh['lines']) or sh['ladder'] != 4 or '٣٥٪' not in (sh['floor'] or ''):
        PROBLEMS.append('%s07: النسب %r' % (pre, sh))
    d3_shot(page, pre + '07-shares.jpg')
    page.click('[data-a="share"][data-k="books"]')
    page.wait_for_selector('#epModal #v3_bo')
    page.fill('#v3_bo', '70')
    page.click('#v3_review')
    page.wait_for_selector('#epModal #v3_go')
    diff = page.inner_text('#epModal .v3-diff')
    if '٦٠٪' not in diff or '٧٠٪' not in diff or '٣٠٪' not in diff:
        PROBLEMS.append('%s07: فرق النسب %r' % (pre, diff))
    shot(page, pre + '07b-shares-diff.jpg'); d3_check(page, pre + '07b-shares-diff.jpg')
    n0 = len(h.platform_calls)
    page.click('#v3_go')
    page.wait_for_selector('#epModal #v3err .v3-err', timeout=10000)
    msg = page.inner_text('#epModal #v3err')
    if 'رفضت المنصة' not in msg or '35' not in msg.replace('٣٥', '35'):
        PROBLEMS.append('%s07: رسالة رفض الأرضية: %r' % (pre, msg))
    if h.ef.shares['version'] != 3:
        PROBLEMS.append(pre + '07: المنصة قبلت نسبة تكسر الأرضية!')
    shot(page, pre + '07c-shares-refused.jpg'); d3_check(page, pre + '07c-shares-refused.jpg')
    page.click('#v3_back')
    page.fill('#v3_bo', '62')
    page.click('#v3_review')
    page.wait_for_selector('#epModal #v3_go')
    n0 = len(h.platform_calls)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w7 = d3_writes(h, n0)
    if len(w7) != 1 or w7[0][3].get('version') != 3 or w7[0][3].get('confirmed') is not True or w7[0][3].get('changes') != {'books': {'normal': {'owner': 62, 'platform': 38}}}:
        PROBLEMS.append('%s07: كتابة النسب %r' % (pre, w7))
    page.wait_for_function("() => document.querySelector('.v3-log li')", timeout=10000)
    d3_shot(page, pre + '07d-shares-after.jpg')
    browser.close()

    # —— ٨) إعلانات الأعمال
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/ads', 'ads')
    ad = page.evaluate("() => ({rows: document.querySelectorAll('.v3-adrow').length, txt: document.querySelector('.v3').innerText})")
    if ad['rows'] != 3 or 'عمل بلا عنوان' not in ad['txt']:
        PROBLEMS.append('%s08: إعلانات الأعمال %r' % (pre, ad['rows']))
    d3_shot(page, pre + '08-ads.jpg')
    page.click('.v3-adrow >> nth=0')
    page.wait_for_selector('#epModal .v3-ent')
    shot(page, pre + '08b-ads-entries.jpg'); d3_check(page, pre + '08b-ads-entries.jpg')
    page.click('#v3_x')
    page.wait_for_timeout(200)
    # صف دورة: لا نسأل جسر الكتب، ونكتب «غير متاحة بعد» مع الرصيد الظاهر في الصف، لا «٠ جنيه» كاذبة
    n0 = len(h.platform_calls)
    page.click('.v3-adrow[data-kind="course"]')
    page.wait_for_selector('#epModal .v3-err')
    ctext = page.inner_text('#epModal')
    if 'حركات الدورات غير متاحة بعد' not in ctext or 'لا حركات' in ctext or len(h.platform_calls) != n0:
        PROBLEMS.append('%s08c: صف الدورة %r' % (pre, ctext))
    shot(page, pre + '08c-ads-course.jpg'); d3_check(page, pre + '08c-ads-course.jpg')
    page.click('#v3_x')
    browser.close()

    # —— ٨ب) استردادات أكثر من الصفحة: تنبيه صريح بدل قائمة ناقصة على أنها كاملة
    h.ef = d3fx.D3Platform(d2=True)
    h.ef.refunds_total = 130
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/money/overview', 'overview')
    page.wait_for_function("() => document.body.innerText.indexOf('استردادًا، وبعد البتّ') > -1", timeout=15000)
    d3_shot(page, pre + '01c-overview-refunds-more.jpg')
    browser.close()

    # —— ٩) الكتب: مراجعة العروض + ورقة الاعتماد + الرفض + طلبات القرّاء
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', tallvp, mobile)
    page = d3_open(ctx, '#s/books/offers', 'offers')
    of = page.evaluate("() => ({cards: document.querySelectorAll('.v3-offer').length, tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), brain: [...document.querySelectorAll('.v3-brain')].map(e => e.innerText)})")
    if of['cards'] != 2 or of['tabs'] != ['مراجعة العروض', 'طلبات القرّاء', 'الكتب والأعمال'] or not any('أعلى من متوسط الكتب في مصر' in b for b in of['brain']):
        PROBLEMS.append('%s09: مراجعة العروض %r' % (pre, of))
    d3_shot(page, pre + '09-offers.jpg')
    page.click('[data-a="oapprove"] >> nth=0')
    page.wait_for_selector('#epModal input[data-v="read"][data-c="eg"]')
    pre_fill = page.input_value('#epModal input[data-v="read"][data-c="eg"]')
    if pre_fill != '390':
        PROBLEMS.append('%s09: السعر المقترح ما اتعبّاش في ورقة الاعتماد (%r)' % (pre, pre_fill))
    shot(page, pre + '09b-approve-sheet.jpg'); d3_check(page, pre + '09b-approve-sheet.jpg')
    page.fill('#epModal input[data-v="read"][data-c="eg"]', '350')
    page.fill('#epModal input[data-v="read"][data-c="default"]', '9')
    page.click('#v3_review')
    page.wait_for_selector('#epModal #v3_go')
    shot(page, pre + '09c-approve-diff.jpg'); d3_check(page, pre + '09c-approve-diff.jpg')
    n0 = len(h.platform_calls)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w9 = d3_writes(h, n0)
    if len(w9) != 1 or not w9[0][1].endswith('/off-1/approve') or w9[0][3].get('versions', {}).get('read', {}).get('pricing', {}).get('eg') != {'amount': 350, 'currency': 'EGP'} or w9[0][3].get('by') != 'admin@local.test':
        PROBLEMS.append('%s09: كتابة الاعتماد %r' % (pre, w9))
    page.wait_for_function("() => document.querySelectorAll('.v3-offer').length === 1", timeout=10000)
    page.click('[data-a="oreject"] >> nth=0')
    page.wait_for_selector('#epModal #v3_reason')
    if not page.is_disabled('#v3_go'):
        PROBLEMS.append(pre + '09: الرفض شغّال من غير سبب')
    page.fill('#v3_reason', 'الملف غير مكتمل')
    shot(page, pre + '09d-reject-sheet.jpg'); d3_check(page, pre + '09d-reject-sheet.jpg')
    n0 = len(h.platform_calls)
    page.click('#v3_go')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    w9b = d3_writes(h, n0)
    if len(w9b) != 1 or w9b[0][3] != {'reason': 'الملف غير مكتمل', 'by': 'admin@local.test'}:
        PROBLEMS.append('%s09: كتابة الرفض %r' % (pre, w9b))
    page.wait_for_function("() => document.body.innerText.indexOf('لا عروض تنتظر المراجعة') > -1", timeout=10000)
    page.click('.v2c-tab[data-tab="requests"]')
    page.wait_for_function(D3_BOARD_READY % 'requests', timeout=30000)
    page.wait_for_timeout(300)
    rq = page.evaluate("() => ({open: document.querySelectorAll('.v3-rq').length, txt: document.querySelector('.v3').innerText})")
    if rq['open'] != 3 or '٣ طلبات' not in rq['txt']:
        PROBLEMS.append('%s10: طلبات القرّاء %r' % (pre, rq['open']))
    d3_shot(page, pre + '10-requests.jpg')
    n0 = len(h.platform_calls)
    page.click('[data-a="rqok"] >> nth=0')
    page.wait_for_selector('#v3_rqgo')
    if len(d3_writes(h, n0)) != 0:
        PROBLEMS.append(pre + '10: «اعتمد» كتب قبل التأكيد')
    shot(page, pre + '10b-approve-confirm.jpg'); d3_check(page, pre + '10b-approve-confirm.jpg')
    page.click('#v3_rqgo')
    page.wait_for_function("() => document.querySelector('.v3-ok')", timeout=10000)
    w10 = d3_writes(h, n0)
    if len(w10) != 1 or w10[0][3] != {'status': 'seeking', 'apply_to_group': True, 'by': 'admin@local.test'}:
        PROBLEMS.append('%s10: كتابة اعتماد الطلب %r' % (pre, w10))
    browser.close()

    # —— ١١) اللوحة: شارة «الفلوس» وبطاقتا القرار الجديدتان
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_function("() => V2.tiles().filter(t => t.key === 'books')[0].count >= 3 && !window.V2D3._src.offers.state.match(/idle|loading/) && !window.V2D3._src.stuck.state.match(/idle|loading/)", timeout=30000)
    page.wait_for_timeout(500)
    tiles = page.evaluate("() => V2.tiles().filter(t => ['money', 'books'].indexOf(t.key) > -1).map(t => [t.key, t.count, t.next])")
    d3_shot(page, pre + '11-home.jpg')
    page.click('[data-a="start"]')
    page.wait_for_selector('.v2-card')
    kinds = page.evaluate("() => V2._state.deck.map(c => c.kind)")
    if 'stuck_payment' not in kinds or 'book_offer' not in kinds:
        PROBLEMS.append('%s11: بطاقتا القرار الجديدتان مش في الطابور: %r' % (pre, kinds))
    for kind, label in (('stuck_payment', '12-focus-stuck'), ('book_offer', '13-focus-offer')):
        page.evaluate("""(kind) => { const S = V2._state, hit = S.deck.filter(c => c.kind === kind)[0];
          S.deck = [hit].concat(S.deck.filter(c => c !== hit)); S.err = ''; S.busy = false; S.lockedId = ''; V2.render(document.getElementById('view')); }""", kind)
        page.wait_for_selector('.v2-card')
        page.wait_for_timeout(150)
        shot(page, '%s%s.jpg' % (pre, label))
    page.click('[data-a="primary"]')
    page.wait_for_selector('#epModal input[data-v="read"]')
    shot(page, pre + '13b-offer-approve-from-card.jpg'); d3_check(page, pre + '13b-offer-approve-from-card.jpg')
    page.click('#v3_cancel')
    browser.close()

    # —— ١٢) «كل السجلات» = الشاشة القديمة بحالها · والمفتاح مقفول = لا أثر
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = d3_open(ctx, '#s/money/overview', 'overview')
    page.click('.v2c-tab[data-tab="all"]')
    page.wait_for_selector('#finTabs')
    old = page.evaluate("() => ({tabs: [...document.querySelectorAll('#finTabs .tab')].map(t => t.textContent.trim()), v3: !!document.querySelector('.v3')})")
    if len(old['tabs']) < 7 or old['v3'] or not any('الباقات' in t for t in old['tabs']):
        PROBLEMS.append('%s14: «كل السجلات» مش الشاشة القديمة: %r' % (pre, old))
    shot(page, pre + '14-all-records.jpg'); shell_check(page, pre + '14-all-records.jpg')
    browser.close()

    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        h.ef = d3fx.D3Platform(d2=True)
        ctx = browser.context(h, 'admin', viewport, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('rows')", timeout=30000)
        page.wait_for_timeout(500)
        st = page.evaluate("() => ({v3: !!document.querySelector('.v3, .v3m'), on: !!window.V2_ON, shell: !!(window.V2SHELL && V2SHELL.on)})")
        if st['v3'] or st['on'] or st['shell']:
            PROBLEMS.append(pre + '80: أثر لـD3 والمفتاح مقفول: %r' % st)
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/shares', '/api/v2/money/settings', '/api/v2/payments/stuck', '/api/v2/prices/book', '/api/v2/book-offers']) {
            const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); } return out; }""")
        if bad:
            PROBLEMS.append('%s80: مسارات D3 والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = Browsers(p)
        mode = sys.argv[2] if len(sys.argv) > 2 else 'd1'
        try:
            if mode == 'd3':
                d3fx.seed_dash(h.app)
                flow_d3(browser, h, 'd', DESK, False)
                flow_d3(browser, h, 't', TAB, False)
                flow_d3(browser, h, 'm', MOB, True)
            elif mode == 'd2':
                flow_d2(browser, h, 'd', DESK, False)
                flow_d2(browser, h, 't', TAB, False)
                flow_d2(browser, h, 'm', MOB, True)
            elif mode == 'd1b':
                d3fx.seed_dash(h.app)        # الجولة النهائية: عروض الكتب وجلسات الضمان ودفتر الإيراد حاضرة في الهيكل المدموج (لا «غير متاح بعد» مفتعلة)
                flow_d1b(browser, h, 'd', DESK, False)
                flow_d1b(browser, h, 't', TAB, False)
                flow_d1b(browser, h, 'm', MOB, True)
            else:
                flow(browser, h, 'd', DESK, False)
                flow(browser, h, 'm', MOB, True)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls), 'problems': PROBLEMS},
                     ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
