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
          .filter(b => b.offsetParent).map(b => b.getBoundingClientRect().height).filter(h => h < 52).length""")
        if small:
            PROBLEMS.append('%s: %d زرار أقل من ٥٢px' % (name, small))
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
    page.wait_for_selector('.v2-log, .v2-empty')
    shot(page, p + '03-brain-log.jpg')
    page.click('[data-a="back"]')
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
    # قائمة مقصوصة: العدّادات المبنية من صفوف الوارد «ناقصة» معلَنة، والتحذير على شريط «الحاجة الجاية»
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
        PROBLEMS.append(p + '71: شريط «الحاجة الجاية» بيطمّن فوق جلب فاشل: %r' % txt)
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
                 ('courses', 'courses', 'الدورات والمدرّبون'), ('market', 'requests', 'سوق الخدمات'), ('books', 'books', 'الكتب'),
                 ('people', 'users', 'الناس والدعوات'), ('money', 'finance', 'الفلوس'), ('content', 'topics', 'المحتوى'),
                 ('marketing', 'campaigns', 'التسويق'), ('reports', 'demand', 'التقارير'), ('brain', 'log', 'العقل'),
                 ('company', 'invest', 'الشركة ورأس المال')]


def flow_d1b(browser, h, pre, viewport, mobile):
    h.ef = v2fx.V2Platform()
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
        if txt.replace('+', '') != mt.replace('+', '') and not (txt in ('تعذّر الجلب',) and mt == '!'):
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
    for n, (key, tab, expect_hash) in enumerate([('files', 'experts', '#s/files/experts'), ('money', 'packages', '#s/money/packages'),
                                                  ('people', 'invites', '#s/people/invites'), ('company', 'settings', '#s/company/settings'),
                                                  ('brain', 'helpers', '#s/brain/helpers'), ('content', 'tutorials', '#s/content/tutorials')]):
        go_section(page, key, tab)
        st = sec_state(page)
        if st['hash'] != expect_hash or st['on'] is None:
            PROBLEMS.append('%s2%d: تبويب %s/%s: %r' % (pre, n, key, tab, st))
        sshot(page, '%s2%d-tab-%s-%s.jpg' % (pre, n, key, tab))
    # شاشة قديمة بتغيّر تبويبها الداخلي ⇒ الترويسة والعنوان يتبعوها (من غير ما نكرّر الشاشة)
    go_section(page, 'money')
    page.click('#finTabs .tab[data-t="packages"]')
    page.wait_for_timeout(300)
    st = sec_state(page)
    if st['hash'] != '#s/money/packages' or st['on'] != 'الباقات والأسعار':
        PROBLEMS.append(pre + '26: تبويب داخلي (الباقات) ما حرّكش الترويسة: %r' % st)
    page.evaluate("() => goEscrowManual()")
    page.wait_for_timeout(300)
    st = sec_state(page)
    if st['hash'] != '#s/money/receipts' or st['h1'] != 'الفلوس' or st['on'] != 'الإيصالات':
        PROBLEMS.append(pre + '26: دفعات يدوية (goEscrowManual) ما هبطتش على «الإيصالات»: %r' % st)
    sshot(page, pre + '26-money-receipts.jpg')
    page.evaluate("() => { location.hash = '#invites'; }")
    page.wait_for_timeout(400)
    st = sec_state(page)
    if st['hash'] != '#s/people/invites' or st['on'] != 'الدعوات':
        PROBLEMS.append(pre + '26: تغيير العنوان لرابط قديم ما حوّلش: %r' % st)
    if page.evaluate("() => localStorage.getItem('ep_v2_shell')") != '1':
        PROBLEMS.append(pre + '26: تذكّر المفتاح المفتوح مش متسجّل')
    if page.evaluate("() => document.querySelector('.app').classList.contains('v2-pre')"):
        PROBLEMS.append(pre + '26: صنف الإخفاء المؤقت فضل بعد الجاهزية')
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
    for tile, expect in (('money', '#s/money/finance'), ('disputes', '#s/disputes/disputes'), ('files', '#s/files/files'),
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
    page.wait_for_selector('.v2-log, .v2-empty')
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
    for old, expect, label, on_tab in (('#finance', '#s/money/finance', 'الفلوس', 'المالية'), ('#packages', '#s/money/packages', 'الفلوس', 'الباقات والأسعار'),
                                       ('#messages', '#s/people/messages', 'الناس والدعوات', 'الرسائل'), ('#invites', '#s/people/invites', 'الناس والدعوات', 'الدعوات'),
                                       ('#escrow', '#s/disputes/escrow', 'النزاعات والاستردادات', 'الضمان'), ('#tutorials', '#s/content/tutorials', 'المحتوى', 'دليل الاستخدام'),
                                       ('#partners', '#s/company/invest', 'الشركة ورأس المال', 'الاستثمار والشركاء'), ('#inbox', '#s/home/inbox', 'اللوحة', 'كل الوارد'),
                                       ('#team', '#s/files/experts', 'ملفات الخبراء', 'الخبراء'), ('#s/money/receipts', '#s/money/receipts', 'الفلوس', 'الإيصالات')):
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
    if st['hash'] != '#s/company/targets' or tg != 'foundation':
        PROBLEMS.append('%s42: #foundation هبط على %r وtgTab=%r (المتوقع foundation)' % (pre, st, tg))
    sshot(page, pre + '42-old-link-foundation.jpg')
    browser.close()
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_shell(ctx)
    go_section(page, 'files', 'all')          # D2: «الملفات» بقت لوحة تذاكر، والوارد القديم في تبويب «كل الملفات»
    page.wait_for_selector('.chip[data-f="all"]')
    page.click('.chip[data-f="all"]')
    page.wait_for_timeout(500)
    st = sec_state(page)
    if st['hash'] != '#s/files/all' or st['h1'] != 'ملفات الخبراء':
        PROBLEMS.append('%s43: شريحة «الكل» داخل الملفات نقلت المستخدم: %r' % (pre, st))
    srch = page.evaluate("() => getComputedStyle(document.querySelector('.topbar .search')).display")
    if (w > 760 and srch == 'none') or (w <= 760 and srch != 'none'):
        PROBLEMS.append('%s43: البحث في الوارد (عرض %s) display=%s' % (pre, w, srch))
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
        h.ef = v2fx.V2Platform()
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
          .filter(b => b.offsetParent).map(b => [b.className, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, big[:4]))
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
    if dinfo['tabs'] != ['النزاعات', 'الضمان', 'كل النزاعات']:
        PROBLEMS.append('%s04: تبويبات النزاعات: %r' % (pre, dinfo['tabs']))
    if not any(b == 'افتح وقرّر' for b in dinfo['btns']):
        PROBLEMS.append('%s04: زرّ «افتح وقرّر» غايب: %r' % (pre, dinfo['btns'][:4]))
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
    if pinfo['btns'] != ['مراسلة']:
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
    # —— ٦) بحث الناس
    page.evaluate("() => { location.hash = '#s/people/users'; }")
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
    # الاسم في قائمة المستخدمين يفتح صفحته
    page.evaluate("() => { location.hash = '#s/people/users'; }")
    try:
        page.wait_for_selector('.parties .v2d-person', timeout=15000)
    except Exception:
        page.screenshot(path=os.path.join(OUT, 'FAIL-users.png'))
        print(page.evaluate("() => [location.hash, (document.getElementById('view')||{}).innerText.slice(0, 400), window.EP && EP.state.users, (window.USERS||[]).length]"))
        raise
    page.click('.parties .v2d-person >> nth=0')
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


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = Browsers(p)
        mode = sys.argv[2] if len(sys.argv) > 2 else 'd1'
        try:
            if mode == 'd2':
                flow_d2(browser, h, 'd', DESK, False)
                flow_d2(browser, h, 't', TAB, False)
                flow_d2(browser, h, 'm', MOB, True)
            elif mode == 'd1b':
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
