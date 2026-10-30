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
        small = page.evaluate("""() => [...document.querySelectorAll('.v2-btn1, .v2-btn2, .v2-start, .v2-pill')]
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
    page.click('[data-a="primary"]')
    page.wait_for_selector('.v2-err', timeout=15000)
    shot(page, p + '40-error-on-card.jpg')
    if page.evaluate("() => V2._state.deck.length") != before or fx.E_TRIAL_ONLY not in page.inner_text('.v2-err'):
        PROBLEMS.append(p + '40: البطاقة اتقدّمت رغم الفشل أو الرسالة مش بكلام المنصة')
    # «بعدين»
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
    browser.close()

    # اللوحة من غير قرارات
    h.ef = v2fx.V2Platform(empty=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = open_home(ctx)
    shot(page, p + '70-board-empty.jpg')
    if page.query_selector('[data-a="start"]'):
        PROBLEMS.append(p + '70: زرّ «ابدأ القرارات» ظاهر من غير قرارات')
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


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = Browsers(p)
        try:
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
