import os
os.environ.setdefault('DASH_SCHEDULER', '0')   # R16: مراقبة التشغيل/الملخص اليومي ما يشتغلوش جوّه الأداة (كانوا بيبعتوا تليجرام عبر الجسر المزيّف)
# -*- coding: utf-8 -*-
"""لقطات بطاقة مراجعة طلب المدرّب بحقول الخطوة الثانية (الجولة r8) — كمبيوتر ١٤٤٠ وموبايل ٣٩٠.

    cd backend && python3 -B tests/uiharness/v2_shots_r8_apps.py ../docs/r8/shots

طلب كامل (ta-1: فيديو تعريفي وسنوات الخبرة والعمل الحالي والدورات والسيرة والنماذج) وطلب قديم بلا أي حقل جديد (ta-2) ليثبت أن الورقة لا تنهار ولا تُظهر صفوفًا فاضية.
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة في الذاكرة، وأي أصل تاني بيتقفل ويتسجّل.
"""
import json
import sys

import v2_shots_courses as sc                 # noqa: E402  (يضبط مجلد الخرج من sys.argv[1] ويستورد المساعدات)

vs, cf, PROBLEMS, DASH = sc.vs, sc.cf, sc.PROBLEMS, sc.DASH
from ef_route_harness import Harness          # noqa: E402

FULL = dict(experience_years=7, current_role='محامية في مكتب للقضايا التجارية', courses_given=['صياغة العقود التجارية', 'أساسيات الإثبات'],
            intro_video_url='https://youtu.be/example-intro')


def sheet_state(page):
    return page.evaluate("""() => ({
      rows: [...document.querySelectorAll('#epModal .v2co-facts > div')].map(d => [d.querySelector('dt').textContent.trim(), d.querySelector('dd').textContent.trim()]),
      links: [...document.querySelectorAll('#epModal .v2co-facts a')].map(a => [a.textContent.trim(), a.getAttribute('href'), a.getAttribute('rel')])})""")


def flow(browser, h, pre, vp, mobile):
    h.ef = cf.CoursesPlatform(with_abc=False)
    h.ef.trainer_apps[0].update(FULL)
    ctx = browser.context(h, 'admin', vp, mobile)
    page = sc.open_co(ctx, '#s/courses/trainers')
    if mobile:
        page.click('[data-a="trseg"][data-seg="apps"]')
        page.wait_for_timeout(250)
    # البطاقة في القائمة تذكر الفيديو التعريفي في سطر الحقائق
    line = page.evaluate("() => document.querySelector('[data-a=\"appopen\"][data-id=\"ta-1\"]').closest('article').innerText")
    if 'فيديو تعريفي' not in line:
        PROBLEMS.append('%s: سطر البطاقة لا يذكر الفيديو التعريفي: %r' % (pre, line))
    page.click('[data-a="appopen"][data-id="ta-1"] >> nth=-1')
    sc.sheet(page)
    st = sheet_state(page)
    want = {'سنوات الخبرة': '٧ سنوات', 'العمل الحالي أو الأخير': 'محامية في مكتب للقضايا التجارية', 'دورات قدّمها': 'صياغة العقود التجارية، أساسيات الإثبات'}
    got = dict((k, v) for k, v in st['rows'])
    for k, v in want.items():
        if got.get(k) != v:
            PROBLEMS.append('%s: صف «%s» = %r' % (pre, k, got.get(k)))
    if ['شاهد الفيديو', 'https://youtu.be/example-intro', 'noopener noreferrer'] not in st['links']:
        PROBLEMS.append('%s: رابط الفيديو %r' % (pre, st['links']))
    if [x[0] for x in st['links'] if x[0] != 'شاهد الفيديو'] != ['لينكدإن', 'السيرة الذاتية', 'نماذج الأعمال']:
        PROBLEMS.append('%s: روابط السيرة والنماذج %r' % (pre, st['links']))
    sc.co_shot(page, pre + '-r8-application-review-card.jpg')
    sc.close_sheet(page)
    page.click('[data-a="appopen"][data-id="ta-2"] >> nth=-1')
    sc.sheet(page)
    st = sheet_state(page)
    names = [k for k, _ in st['rows']]
    if any(n in names for n in ('سنوات الخبرة', 'العمل الحالي أو الأخير', 'دورات قدّمها', 'الفيديو التعريفي')):
        PROBLEMS.append('%s: طلب قديم يعرض صفوفًا جديدة فاضية %r' % (pre, names))
    sc.co_shot(page, pre + '-r8-application-review-card-old.jpg')
    sc.close_sheet(page)
    ctx.close()


def main():
    from playwright.sync_api import sync_playwright
    import os
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(cf.CoursesPlatform(with_abc=False))
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('d', sc.DESK, False), ('m', sc.MOB, True)):
                flow(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    print(json.dumps({'out': sc.OUT, 'names': sc.SHOTS, 'blocked_by_origin': h.blocked_report(), 'unexpected': h.unexpected_blocked(), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
