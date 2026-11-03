# -*- coding: utf-8 -*-
"""لقطات «اللوحة وابدأ القرارات» داخل الغلاف الجديد — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٣٩٠ (`m*`) (الجولة r6).

    cd backend && python3 -B tests/uiharness/v2_shots_decide.py ../docs/r6-mobile/after-decide

اللقطات: ٠١ اللوحة · ٠٢ التنبيهات · ١٠ أول بطاقة (ابدأ القرارات) · ١١ ملف متأخر · ١٢ تحويل أرباح (مبلغ بكسر ورقم حساب) ·
١٣ نافذة تسجيل التحويل (زرّان + رابط الرفض) · ١٤ زائر · ١٥ مدرّب · ١٦ نزاع.
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة جدول في الذاكرة (`v2_fixtures.V2Platform`). يفشل لو خرج طلب غير خطوط جوجل.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                            # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import v2_fixtures as v2fx                       # noqa: E402
import d3_fixtures as d3fx                       # noqa: E402
from ef_route_harness import Harness              # noqa: E402

PROBLEMS = vs.PROBLEMS


def flow(browser, h, pre, viewport, mobile):
    h.ef = d3fx.D3Platform(d2=True)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = vs.open_shell(ctx)
    vs.shot(page, pre + '01-board.jpg')
    try:
        page.click('#bellBtn, .v2-health', timeout=3000)
        page.wait_for_timeout(300)
        vs.shot(page, pre + '02-bell.jpg')
        page.keyboard.press('Escape')
        page.mouse.click(5, 300)
        page.wait_for_timeout(200)
    except Exception:
        pass
    vs.start(page)
    page.wait_for_timeout(250)
    vs.shot(page, pre + '10-first-card.jpg')
    for i, (kind, label) in enumerate([('file_late', 'file-late'), ('payout', 'payout'), ('pending_user', 'visitor'), ('trainer', 'trainer'), ('dispute', 'dispute')]):
        try:
            vs.focus_on(page, kind, 0, None)
        except Exception as e:                     # نوع غير موجود في هذه الحزمة
            PROBLEMS.append('%s1%d: لا بطاقة من نوع %s (%s)' % (pre, i + 1, kind, str(e)[:40]))
            continue
        vs.shot(page, '%s1%d-%s.jpg' % (pre, i + 1, label))
        if kind == 'payout':
            page.click('[data-a="primary"]')
            page.wait_for_selector('#epModal #v2m_go')
            vs.shot(page, pre + '13-payout-modal.jpg')
            page.click('#epModal #v2m_x')
            page.wait_for_timeout(250)


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            d3fx.seed_dash(h.app)
            flow(browser, h, 'd', vs.DESK, False)
            flow(browser, h, 'm', vs.MOB, True)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked():
        sys.exit(1)


if __name__ == '__main__':
    main()
