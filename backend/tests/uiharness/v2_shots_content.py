# -*- coding: utf-8 -*-
"""لقطات قسم «المحتوى» (الجولة الأخيرة) — كمبيوتر ١٤٤٠ (`d-`) وتابلت ٨٢٠ (`t-`) وموبايل ٣٩٠ (`m-`).

    cd backend && python3 -B tests/uiharness/v2_shots_content.py ../docs/v2/final/shots-content

⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة (`content_fixtures.ContentPlatform`)، وأي أصل تاني بيتقفل
ويتسجّل. `_prerender_push_async` متبدّلة بدالة فاضية (ولا SFTP). السكربت بيفشل لو:
  - تمرير أفقي في الموبايل · هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · أكتر من زرّ أساسي في بطاقة أو ورقة · قائمة «…».
  - «undefined/NaN/null/[object Object]» ظاهرة · «٠» ظاهر في خانة مصدرها فاشل · أرقام لاتينية في نص ظاهر.
  - أي نداء كتابة (منصة أو دفتر الداشبورد) من غير ضغطة تأكيد قبله بأقل من ٥ ثواني، إلا الخطوات المستثناة بالاسم (`EXEMPT`).
  - نداء `/opinions/analysis` من غير `summarize=false` خارج لقطة الخلاصة · نداء `daily-run` أو `generate-article` خارج لقطات ٥ و٦.
  - أي طلب لأصل غير محلي.
"""
import json
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as base                         # noqa: E402  (OUT من argv[1])
import content_fixtures as cfx                  # noqa: E402
from ef_route_harness import Harness, DASH      # noqa: E402

PROBLEMS = base.PROBLEMS
DESK = {'width': 1440, 'height': 900}
TAB = {'width': 820, 'height': 1180}
MOB = {'width': 390, 'height': 844}
EXEMPT = {'segment-select', 'sync-now', 'to-write', 'save-draft-article', 'save-draft-new', 'hide-tutorial', 'save-news-sources', 'save-draft-tutorial',
          'save-topic-draft', 'save-news-draft'}
BOARD_READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2ct[data-tab=\"%s\"]')"
               " && !document.querySelector('.v2ct-t.ph')")


def ct_check(page, name):
    w = page.viewport_size['width']
    info = page.evaluate("""() => {
      const vis = e => !!e && !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
      const roots = [...document.querySelectorAll('.v2ct, #epModal .v2ct-m')];
      const targets = [...document.querySelectorAll('.v2ct button, .v2ct a[href], .v2ct select, #epModal .v2ct-m button, #epModal .v2ct-m a[href], #epModal .v2ct-m input:not([type=checkbox]), #epModal .v2ct-m textarea, #epModal .v2ct-m select')]
        .filter(e => vis(e) && !e.classList.contains('v2ct-person'));
      const small = targets.map(e => [e.className || e.tagName, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 44);
      const btns = [...document.querySelectorAll('.v2ct-b1, .v2ct-b2, .v2ct-b3, .v2ct-chip, .v2ct-link')].filter(vis).map(e => [e.className, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 52);
      const segs = [...document.querySelectorAll('.v2ct-segb')].filter(vis).map(e => [e.className, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 60);
      const multi = [...document.querySelectorAll('.v2ct-t, .v2ct-card, .v2ct-row, #epModal .v2ct-m')].filter(vis)
        .filter(e => [...e.querySelectorAll('.v2ct-b1')].filter(vis).length > 1).map(e => e.className);
      const dots = [...document.querySelectorAll('.v2ct button, .v2ct-m button')].filter(vis).filter(b => /^[\\s…⋯⋮.]{1,4}$/.test(b.textContent)).length;
      const out = w2 => [...document.querySelectorAll('.v2ct *, #epModal .v2ct-m *')].filter(e => vis(e) && e.getBoundingClientRect().right > w2 + 1).length;
      const clone = roots.map(r => { const c = r.cloneNode(true); c.querySelectorAll('input,select,textarea,.v2ct-ltr,[dir=ltr],script,style').forEach(n => n.remove()); return c.innerText; }).join('\\n');
      return {small, btns, segs, multi, dots, wide: out(window.innerWidth), text: clone,
              sw: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content') || {}).scrollWidth || 0)};
    }""")
    if info['small']:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, info['small'][:4]))
    if info['multi']:
        PROBLEMS.append('%s: أكتر من زرّ أساسي: %r' % (name, info['multi'][:3]))
    if info['dots']:
        PROBLEMS.append('%s: قائمة «…»' % name)
    if w <= 400:
        if info['btns']:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, info['btns'][:4]))
        if info['segs']:
            PROBLEMS.append('%s: مفاتيح الأعمدة أقل من ٦٠px: %r' % (name, info['segs'][:3]))
        if info['sw'] > w + 1:
            PROBLEMS.append('%s: تمرير أفقي في الموبايل (%s > %s)' % (name, info['sw'], w))
        if info['wide']:
            PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, info['wide']))
    txt = info['text']
    for bad in ('undefined', 'NaN', '[object Object]'):
        if bad in txt:
            PROBLEMS.append('%s: «%s» ظاهرة' % (name, bad))
    if re.search(r'(?<![\w@./-])null(?![\w@./-])', txt):
        PROBLEMS.append('%s: «null» ظاهرة' % name)
    latin = [t for t in re.findall(r'\S*\d\S*', re.sub(r'[٠-٩]', '', txt)) if '@' not in t]
    if latin:
        PROBLEMS.append('%s: أرقام لاتينية ظاهرة: %r' % (name, latin[:3]))
    return info


def cshot(page, name, scroll_top=True):
    if scroll_top:
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    base.shot(page, name)
    base.shell_check(page, name)
    return ct_check(page, name)


def open_tab(ctx, hash_, tab, setup=None):
    page = ctx.new_page()
    if setup:
        setup(page)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    try:
        page.wait_for_function(base.SHELL_READY, timeout=30000)
    except Exception:
        diag = page.evaluate("() => ({states: window.EP && JSON.stringify(EP.state), shell: window.V2SHELL && V2SHELL.on, tab: !!document.querySelector('.v2c-tab'), ld: !!document.querySelector('.v2-cnt.ld'), hash: location.hash})")
        raise RuntimeError('الغلاف ما جهّزش: %r' % diag)
    page.wait_for_function(BOARD_READY % tab, timeout=30000)
    page.wait_for_timeout(500)
    return page


def reopen(browser, h, tall, mobile, hash_, tab, setup=None):
    """`--single-process` ما بيستحملش صفحة تتقفل وتتفتح غيرها في نفس السياق ⇒ متصفح جديد لكل فتحة."""
    ctx = browser.context(h, 'admin', tall, mobile)
    return open_tab(ctx, hash_, tab, setup), ctx


def goto_tab(page, tab_key, board):
    page.click('.v2c-tab[data-tab="%s"]' % tab_key)
    page.wait_for_function(BOARD_READY % board, timeout=30000)
    page.wait_for_timeout(350)


class Guard(object):
    """يمسك نداءات الكتابة (منصة + دفتر الداشبورد) ويقارنها بضغطة التأكيد."""

    def __init__(self, h, page):
        self.h, self.page = h, page
        self.mark()

    def mark(self):
        self.p0, self.d0 = len(self.h.platform_calls), len(self.h.dash_calls)
        self.page.evaluate("() => { window.__v2ctConfirmAt = 0; }")

    def writes(self):
        out = [(c[0], c[1]) for c in self.h.platform_calls[self.p0:] if c[0] in ('POST', 'PUT', 'PATCH', 'DELETE')]
        out += [(c[0], c[1]) for c in self.h.dash_calls[self.d0:] if c[0] in ('POST', 'PUT', 'PATCH', 'DELETE')
                and c[1].startswith(('/api/content/', '/api/platform-', '/api/tutorials', '/api/v2/testimonials'))]
        return out

    def check(self, step):
        w = self.writes()
        if w and step not in EXEMPT:
            at = self.page.evaluate("() => window.__v2ctConfirmAt || 0")
            age = self.page.evaluate("(a) => a ? Date.now() - a : -1", at)
            if not at or age < 0 or age > 5000:
                PROBLEMS.append('الخطوة «%s»: نداء كتابة بلا ضغطة تأكيد قبله بأقل من ٥ ثواني: %r' % (step, w[:3]))
        return w


def click_wait(page, sel, timeout=15000):
    page.wait_for_selector(sel, timeout=timeout)
    page.click(sel)


def sheet_open(page):
    page.wait_for_selector('#epModal .v2ct-m', timeout=10000)
    page.wait_for_timeout(300)


def sheet_closed(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)


def note_text(page):
    return page.evaluate("() => (document.querySelector('.v2ct-ok') || {}).textContent || ''")


def settle(page, ms=500):
    page.wait_for_timeout(ms)


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def flow(browser, h, pre, viewport, mobile):
    mob = viewport['width'] <= 400
    tall = dict(viewport, height=viewport['height'] if mob else (1500 if viewport['width'] >= 1180 else 1700))

    def fresh(empty=False, **kw):
        h.ef = cfx.ContentPlatform(empty=empty)
        ids = cfx.seed_site(h.app) if not empty else []
        if empty:
            with h.app.app.app_context():
                h.app.Article.query.delete()
                h.app.db.session.commit()
        h.app._prerender_last = {'state': 'ok', 'reason': 'x', 'uploaded': 3, 'at': (__import__('datetime').datetime.utcnow() - __import__('datetime').timedelta(hours=3)).isoformat()}
        h.app._prerender_running = False
        return ids

    # =========================================================== ١) خط النشر
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/pipeline', 'pipeline')
    g = Guard(h, page)
    st = page.evaluate("""() => ({cols: [...document.querySelectorAll('.v2ct-col')].map(c => [c.dataset.col, c.querySelector('.v2ct-ch b').textContent, c.querySelector('.v2ct-n').textContent.trim(), c.querySelectorAll('.v2ct-t').length]),
      hero: document.querySelector('.v2ct-hero p').textContent, facts: [...document.querySelectorAll('.v2ct-fact')].map(f => f.textContent.trim()),
      tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()), h1: document.querySelector('.v2c-h h1').textContent,
      old: !!document.querySelector('#topicsTabs, .tabbar, .kpis, .inboxwrap, .policy'), hash: location.hash})""")
    expect([c[0] for c in st['cols']] == ['wait', 'draft', 'idea', 'done'], pre + '01: ترتيب الأعمدة %r' % st['cols'])
    expect([c[1] for c in st['cols']] == ['ينتظرك', 'مسودات', 'أفكار', 'نُشر هذا الأسبوع'], pre + '01: أسماء الأعمدة %r' % [c[1] for c in st['cols']])
    expect(all(c[3] > 0 for c in st['cols']), pre + '01: عمود فاضي %r' % st['cols'])
    expect(st['hero'].startswith('ابدأ بموضوعات الأعضاء: ٣ ينتظر صاحبه قرارك'), pre + '01: سطر العقل «%s»' % st['hero'])
    expect(any(f.startswith('نُشر على الموقع اليوم: ١') for f in st['facts']) and any('هذا الأسبوع: ٣' in f for f in st['facts']), pre + '01: حقائق النشر %r' % st['facts'])
    expect(any(f.startswith('صفحات محركات البحث حُدّثت منذ') for f in st['facts']), pre + '01: حالة صفحات البحث %r' % st['facts'])
    expect(st['tabs'] == ['خط النشر', 'المقالات', 'الموضوعات', 'الأخبار', 'التعليقات', 'دليل الاستخدام'] and st['h1'] == 'المحتوى', pre + '01: التبويبات %r' % st['tabs'])
    expect(not st['old'], pre + '01: أثر لشاشة قديمة في #view')
    cshot(page, pre + '01-pipeline.jpg')
    if mob:
        for c, nm in (('draft', '01b-pipeline-draft'), ('idea', '01c-pipeline-idea'), ('done', '01d-pipeline-done')):
            page.click('.v2ct-segb[data-col="%s"]' % c)
            page.wait_for_timeout(250)
            cshot(page, '%s%s.jpg' % (pre, nm))
        page.click('.v2ct-segb[data-col="wait"]')
        page.wait_for_timeout(250)
    # —— تأكيد اعتماد موضوع عضو
    g.mark()
    page.click('.v2ct-t[data-id^="m:"] [data-a="primary"] >> nth=0')
    sheet_open(page)
    expect('سيظهر على اللوحة العامة، ويصل القرار إلى صاحبه.' in page.inner_text('#epModal'), pre + '03: نص تأكيد موضوع العضو')
    cshot(page, pre + '03-confirm-member-topic.jpg')
    n0 = len(h.ef.topics)
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('approve-member-topic')
    expect('تمّ: اعتُمد' in note_text(page), pre + '03: شريط التمّ بعد الاعتماد: %s' % note_text(page))
    expect(any(c[1].endswith('/approve') and '/topics/' in c[1] for c in h.platform_calls), pre + '03: لم يصل نداء الاعتماد للمنصة')
    # —— ورقة التعليق (غير محسوم ⇒ «افتح واقرأ»)
    g.mark()
    labels = page.evaluate("() => [...document.querySelectorAll('.v2ct-t[data-id^=\"c:\"]')].map(t => [t.dataset.id, t.querySelector('[data-a=primary]').textContent])")
    expect(dict(labels).get('c:op-3') == 'افتح واقرأ' and dict(labels).get('c:op-2') == 'ارفض', pre + '03: أزرار التعليقات %r' % labels)
    page.click('.v2ct-t[data-id="c:op-3"] [data-a="primary"]')
    sheet_open(page)
    cshot(page, pre + '03b-comment-sheet.jpg')
    page.click('#v2ctOk')
    sheet_open(page)
    expect('سيظهر التعليق للجميع تحت الموضوع.' in page.inner_text('#epModal'), pre + '03c: نص تأكيد اعتماد التعليق')
    cshot(page, pre + '03c-confirm-comment-approve.jpg')
    page.click('#v2ctNo')
    sheet_closed(page)
    expect(not g.writes(), pre + '03c: كتابة قبل الضغط على التأكيد')
    # —— رأي متعلّم بلا اسم
    page.click('.v2ct-t[data-id="t:TST_A2"] [data-a="primary"]')
    sheet_open(page)
    expect('سيظهر الرأي بلا اسم على صفحة الدورة.' in page.inner_text('#epModal'), pre + '03d: نص تأكيد الرأي بلا اسم')
    cshot(page, pre + '03d-testimonial-confirm-no-name.jpg')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('approve-testimonial')
    expect(any('/api/v2/testimonials/TST_A2/approve' == c[1] for c in h.dash_calls[g.d0:]), pre + '03d: نداء اعتماد الرأي')
    expect(any(c[1].endswith('/testimonials/TST_A2/approve') for c in h.platform_calls[g.p0:]), pre + '03d: لم يصل اعتماد الرأي للمنصة')
    # —— عمل إبداعي (مخبّأ تحت «و… أخرى» ⇒ يُوسَّع في مكانه)
    page.click('.v2ct-b2.more[data-col="wait"]')
    page.wait_for_timeout(250)
    expect(page.inner_text('.v2ct-t[data-id="c:op-1"]').find('ارفض') > -1, pre + '03: زرّ ارفض لتعليق مسيء')
    page.click('.v2ct-t[data-id="w:cr-2"] [data-a="primary"]')
    sheet_open(page)
    cshot(page, pre + '03e-creative-sheet.jpg')
    page.click('#v2ctRej')
    sheet_open(page)
    expect(page.is_disabled('#v2ctGo'), pre + '03e: زرّ الرفض شغّال بلا سبب')
    cshot(page, pre + '03f-creative-reject-reason.jpg')
    page.click('#v2ctNo')
    sheet_closed(page)
    browser.close()

    # =========================================================== ٢) خط النشر والمصادر واقعة
    fresh()
    ctx = browser.context(h, 'admin', tall, mobile)

    def down(pg):
        pg.route('**/api/platform-opinions?*', lambda r: r.fulfill(status=502, content_type='application/json', body='{"error":"x"}') if 'pending' in r.request.url else r.fallback())
        pg.route('**/api/platform-creative*', lambda r: r.fulfill(status=502, content_type='application/json', body='{"error":"x"}'))
        pg.route('**/api/v2/content/overview', lambda r: r.fulfill(status=502, content_type='application/json', body='{"error":"x"}'))
    page = open_tab(ctx, '#s/content/pipeline', 'pipeline', down)
    txt = page.evaluate("""() => ({warn: (document.querySelector('.v2ct-warn') || {}).textContent || '', chips: [...document.querySelectorAll('.v2ct-n')].map(n => n.textContent.trim()),
      facts: [...document.querySelectorAll('.v2ct-fact')].map(f => f.textContent.trim()), hero: document.querySelector('.v2ct-hero p').textContent})""")
    expect('تعذّر جلب' in txt['warn'] and 'التعليقات' in txt['warn'] and 'أعمال ركن الإبداع' in txt['warn'] and 'حالة مقالات الموقع' in txt['warn'], pre + '02: شريط الفشل «%s»' % txt['warn'])
    expect(any(c.endswith('+') for c in txt['chips']), pre + '02: عدّاد ناقص «+» غير ظاهر %r' % txt['chips'])
    expect('٠' not in ''.join(txt['chips']), pre + '02: «٠» في عدّاد %r' % txt['chips'])
    expect(any('غير متاح بعد' in f for f in txt['facts']), pre + '02: خانة غير متاحة %r' % txt['facts'])
    expect(not txt['hero'].startswith('لا شيء ينتظر'), pre + '02: سطر العقل ادّعى لا شيء مع مصدر فاشل: %s' % txt['hero'])
    cshot(page, pre + '02-pipeline-down.jpg')
    browser.close()

    # =========================================================== ٣) المقالات (الموقع)
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/articles', 'articles')
    g = Guard(h, page)
    info = page.evaluate("""() => ({chips: [...document.querySelectorAll('.v2ct-chip')].map(c => c.textContent.trim()), cards: document.querySelectorAll('.v2ct-card.art').length,
      sw: [...document.querySelectorAll('.v2ct-sw button')].map(b => b.textContent.trim()), line: document.querySelector('.v2ct-line').textContent,
      bar: [...document.querySelectorAll('.v2ct-bar button')].map(b => b.textContent.trim())})""")
    expect(info['chips'] == ['مسودات (٣)', 'منشورة (٤)'] and info['cards'] == 3, pre + '04: قائمة المقالات %r' % info)
    expect(info['sw'] == ['على الموقع', 'على المنصة'] and info['bar'] == ['مقال جديد', 'أدوات الكتابة'], pre + '04: أزرار المقالات %r' % info)
    cshot(page, pre + '04-articles-site.jpg')
    page.click('.v2ct-card.art[data-id="%s"]' % ids[0])
    sheet_open(page)
    body = page.inner_text('#epModal')
    expect('انشر على الموقع' in body and 'عدّل' in body and 'احذف المسودة' in body and '٨٤٢ كلمة' in body, pre + '04b: قارئ المسودة ناقص')
    cshot(page, pre + '04b-article-read.jpg')
    page.click('#v2ctEdit')
    page.wait_for_selector('#ae_t')
    cshot(page, pre + '04d-article-edit.jpg')
    page.click('#v2ctBack')
    page.wait_for_selector('#v2ctPub')
    # ورقة النشر (حالة الصفحات سليمة)
    g.mark()
    page.click('#v2ctPub')
    sheet_open(page)
    expect('وتتحدّث صفحته لمحركات البحث خلال دقائق.' in page.inner_text('#epModal'), pre + '04e: جملة صفحات البحث غائبة والحالة سليمة')
    cshot(page, pre + '04e-article-publish-confirm.jpg')
    page.click('#v2ctNo')
    sheet_closed(page)
    expect(not g.writes(), pre + '04e: كتابة قبل التأكيد')
    # المسودة المكرّرة ⇒ مقارنة وحذف المكرر
    page.click('.v2ct-card.art[data-id="%s"]' % ids[2])
    sheet_open(page)
    body = page.inner_text('#epModal')
    expect('المقال المنشور بنفس العنوان' in body and 'احذف المكرر' in body, pre + '04c: صف المقارنة أو زر المكرر غائب')
    expect(page.query_selector('#epModal .v2ct-b1.danger') is not None, pre + '04c: الزر الأساسي للمكرر مش «حذف»')
    cshot(page, pre + '04c-article-compare.jpg')
    page.click('#v2ctNo') if page.query_selector('#v2ctNo') else page.click('#epModal [data-x]')
    sheet_closed(page)
    # حالة الصفحات «تعذّر» ⇒ جملة النشر بلا وعد
    h.app._prerender_last = {'state': 'error', 'reason': 'x', 'error': 'boom', 'at': (__import__('datetime').datetime.utcnow() - __import__('datetime').timedelta(hours=1)).isoformat()}
    page, ctx = reopen(browser, h, tall, mobile, '#s/content/articles', 'articles')
    g = Guard(h, page)
    page.click('.v2ct-card.art[data-id="%s"]' % ids[0])
    sheet_open(page)
    page.click('#v2ctPub')
    sheet_open(page)
    lead = page.inner_text('#epModal .v2ct-lead')
    expect('لمحركات البحث' not in lead and lead.startswith('سيظهر «'), pre + '04f: وعد صفحات البحث والحالة فاشلة: %s' % lead)
    cshot(page, pre + '04f-article-publish-confirm-plain.jpg')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('publish-article')
    expect('تمّ: نُشر على الموقع.' in note_text(page), pre + '04g: شريط النشر')
    expect(any(c[1].endswith('/publish') for c in h.dash_calls[g.d0:]), pre + '04g: نداء النشر على الدفتر')
    cshot(page, pre + '04g-article-published-note.jpg')
    # مقال منشور: بلا حذف وسطر الخطوتين
    page.click('.v2ct-chip[data-v="published"]')
    page.wait_for_timeout(250)
    page.click('.v2ct-card.art >> nth=0')
    sheet_open(page)
    body = page.inner_text('#epModal')
    expect('لحذف مقال منشور: أوقف نشره أولًا، ثم احذفه من المسودات.' in body, pre + '04h: سطر الخطوتين')
    expect(page.query_selector('#v2ctDel') is None and page.query_selector('#v2ctDelDup') is None, pre + '04h: زرّ حذف على مقال منشور')
    expect('أوقف النشر' in body and 'عدّل' in body and 'اعرضه على الموقع' in body, pre + '04h: أزرار المنشور')
    cshot(page, pre + '04h-article-read-published.jpg')
    # تعديل مقال منشور ⇒ تأكيد داخل الورقة نفسها (ما كُتب يبقى)
    g.mark()
    page.click('#v2ctEdit')
    page.wait_for_selector('#ae_t')
    page.fill('#ae_t', 'عنوان معدّل لمقال منشور')
    page.click('#v2ctSave')
    page.wait_for_selector('#v2ctGo2')
    expect('يظهر التعديل على الموقع فور الحفظ.' in page.inner_text('#epModal .v2ct-inconf'), pre + '04j: جملة تأكيد تعديل المنشور')
    expect(not g.writes(), pre + '04j: كتابة قبل التأكيد')
    cshot(page, pre + '04j-article-edit-confirm.jpg')
    page.click('#v2ctNo2')
    page.wait_for_selector('#ae_t')
    expect(page.input_value('#ae_t') == 'عنوان معدّل لمقال منشور', pre + '04j: «رجوع» أضاع ما كُتب')
    page.click('#v2ctSave')
    page.wait_for_selector('#v2ctGo2')
    page.click('#v2ctGo2')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('save-published-article')
    expect('تمّ: حُفظ «عنوان معدّل لمقال منشور».' in note_text(page), pre + '04j: شريط حفظ المنشور')
    # مقال جديد (مسودة: مستثنى)
    g.mark()
    page.click('[data-a="newart"]')
    page.wait_for_selector('#ae_t')
    expect(page.input_value('#ae_by') == 'فريق البروفيسور', pre + '04i: كاتب المقال الجديد «%s»' % page.input_value('#ae_by'))
    cshot(page, pre + '04i-article-new.jpg')
    page.fill('#ae_t', 'مقال تجريبي جديد')
    page.fill('#ae_body', 'الفقرة الأولى.\n\n## عنوان\n\nالفقرة الثانية.')
    page.click('#v2ctSave')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('save-draft-new')
    expect('تمّ: حُفظت مسودة' in note_text(page), pre + '04i: شريط حفظ المسودة')
    # —— أدوات الكتابة
    page.click('.v2ct-chip[data-v="draft"]') if page.query_selector('.v2ct-chip[data-v="draft"]') else None
    g.mark()
    page.click('[data-a="tools"]')
    sheet_open(page)
    expect(page.query_selector('[data-t="tblog"]') is not None and page.query_selector('[data-t="tsync"]') is not None and page.query_selector('[data-t="twrite"]') is not None, pre + '05b: أدوات الكتابة ناقصة')
    cshot(page, pre + '05b-writing-tools.jpg')
    page.click('[data-t="tblog"]')
    page.wait_for_selector('#epModal .v2ct-bt', timeout=10000)
    page.wait_for_timeout(300)
    cshot(page, pre + '05c-blog-topics.jpg')
    page.click('#epModal [data-x]')
    sheet_closed(page)
    page.click('[data-a="tools"]')
    sheet_open(page)
    page.click('[data-t="tsync"]')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('sync-now')
    page.click('[data-a="tools"]')
    sheet_open(page)
    page.click('[data-t="twrite"]')
    sheet_open(page)
    expect('رصيد الكتابة الآلية' in page.inner_text('#epModal .v2ct-lead'), pre + '05d: جملة الرصيد غائبة')
    cshot(page, pre + '05d-write-now-confirm.jpg')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('write-now')
    expect(h.ef.daily_runs == [{'articles': 3, 'topics': 2, 'publish': False}], pre + '05d: نداء الكتابة الآلية %r' % h.ef.daily_runs)
    browser.close()

    # =========================================================== ٤) المقالات (المنصة)
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/articles', 'articles')
    g = Guard(h, page)
    page.click('[data-a="asub"][data-v="auto"]')
    page.wait_for_function("() => document.querySelector('.v2ct-card.art[data-a=pread]')", timeout=10000)
    page.wait_for_timeout(300)
    t = page.inner_text('.v2ct')
    expect('مقالات صفحة المقالات داخل المنصة.' in t and 'عناوينها مطابقة لمقالات منشورة على الموقع' in t and 'عنوانه مطابق لمقال على الموقع' in t, pre + '05: صفحة مقالات المنصة ناقصة')
    expect(page.query_selector('[data-a="newart"]') is None, pre + '05: «مقال جديد» على قائمة المنصة')
    cshot(page, pre + '05-articles-platform.jpg')
    page.click('[data-a="tools"]')
    sheet_open(page)
    expect(page.query_selector('[data-t="tblog"]') is None and page.query_selector('[data-t="twrite"]') is not None, pre + '05: أدوات المنصة لازم صف واحد')
    page.click('#v2ctNo')
    sheet_closed(page)
    page.click('.v2ct-card.art[data-id="pa-2"]')
    sheet_open(page)
    expect('احذف المكرر' in page.inner_text('#epModal') and 'المقال المنشور بنفس العنوان' in page.inner_text('#epModal'), pre + '05e: مقارنة مقال المنصة')
    cshot(page, pre + '05e-platform-article-compare.jpg')
    page.click('#epModal [data-x]')
    sheet_closed(page)
    browser.close()

    # =========================================================== ٥) الموضوعات
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/topics', 'topics')
    g = Guard(h, page)
    chips = page.evaluate("() => [...document.querySelectorAll('.v2ct-chip')].map(c => c.textContent.trim().replace(/\\s+/g, ' '))")
    expect(chips == ['من الأعضاء ٣', 'أفكار ٢', 'من الخبراء ١', 'يُكتب ٢', 'على اللوحة ٢', 'مرفوضة ١'], pre + '06: شرائح الموضوعات %r' % chips)
    expect(page.query_selector('.v2ct-card.topic') is not None, pre + '06: بطاقات الموضوعات')
    cshot(page, pre + '06-topics-pending.jpg')
    n_before = len(h.ef.topics)
    # عدّ «من الأعضاء» فاشل ⇒ «—» لا رقم PTOPICS
    def pdown(pg):
        pg.route('**/api/platform-pending-topics*', lambda r: r.fulfill(status=502, content_type='application/json', body='{"error":"x"}'))
    page, ctx = reopen(browser, h, tall, mobile, '#s/content/topics', 'topics', pdown)
    chips = page.evaluate("() => [...document.querySelectorAll('.v2ct-chip')].map(c => c.textContent.trim().replace(/\\s+/g, ' '))")
    expect(chips[0] == 'من الأعضاء —' and 'موضوعات الأعضاء' in page.inner_text('.v2ct-warn') and 'غير متاح بعد' in page.inner_text('.v2ct-warn'), pre + '06b: شريحة الأعضاء والمصدر فاشل %r' % chips)
    cshot(page, pre + '06b-topics-pending-down.jpg')
    page, ctx = reopen(browser, h, tall, mobile, '#s/content/topics', 'topics')
    g = Guard(h, page)
    page.click('.v2ct-chip[data-v="ideas"]')
    page.wait_for_function("() => document.querySelector('.v2ct-card.topic [data-chip=ideas]')", timeout=10000)
    expect('الاعتماد يضعها على اللوحة العامة، والرفض يحذفها.' in page.inner_text('.v2ct'), pre + '06c: سطر العقل للأفكار')
    cshot(page, pre + '06c-topics-ideas.jpg')
    page.click('.v2ct-card.topic [data-a="topen"]')
    sheet_open(page)
    page.wait_for_selector('select[data-seg]')
    cshot(page, pre + '06e-topic-sheet.jpg')
    g.mark()
    page.select_option('select[data-seg]', 'labor')
    page.wait_for_timeout(700)
    g.check('segment-select')
    expect(any('/segment' in c[1] for c in h.platform_calls[g.p0:]), pre + '06e: لم يصل نداء الفئة')
    page.click('#epModal [data-x]')
    sheet_closed(page)
    page.click('.v2ct-chip[data-v="board"]')
    page.wait_for_function("() => document.querySelector('.v2ct-card.topic [data-chip=board]')", timeout=10000)
    page.wait_for_timeout(300)
    expect('أقل الفئات موضوعات: النيابة الإدارية والتحقيق (٠).' in page.inner_text('.v2ct'), pre + '06d: سطر الفئات')
    cshot(page, pre + '06d-topics-board.jpg')
    # موضوع جديد: الورقة هي التأكيد
    g.mark()
    page.click('[data-a="newtopic"]')
    sheet_open(page)
    expect('رصيد الكتابة الآلية' in page.inner_text('#epModal .v2ct-lead'), pre + '06f: جملة الرصيد')
    cshot(page, pre + '06f-new-topic.jpg')
    page.fill('#nt_t', 'موضوع تجريبي')
    page.fill('#nt_q', 'سؤال تجريبي؟')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('new-topic')
    # اكتب منه مقالًا (نجاح) ⇒ ينتقل للمقالات ويفتح مسودته
    page.click('.v2ct-chip[data-v="board"]')
    page.wait_for_timeout(300)
    g.mark()
    page.click('.v2ct-card.topic[data-id="t:tp-b2"] [data-a="tmain"]')
    sheet_open(page)
    expect('ولا ينسخ نصه، ويستهلك ذلك من رصيد الكتابة الآلية' in page.inner_text('#epModal .v2ct-lead'), pre + '06g: جملة الرصيد')
    cshot(page, pre + '06g-make-article-confirm.jpg')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_selector('#epModal .v2ct-m', timeout=20000)
    g.check('make-article')
    expect(h.ef.generated == ['tp-b2'], pre + '06g: توليد المقال %r' % h.ef.generated)
    expect(page.evaluate("() => location.hash") == '#s/content/articles', pre + '06g: ما انتقلناش للمقالات: ' + page.evaluate("() => location.hash"))
    cshot(page, pre + '06h-make-article-done.jpg')
    page.click('#epModal [data-x]')
    sheet_closed(page)
    # فشل التوليد: الموضوع كما هو + ورقة الخطأ
    h.ef.forced[('POST', '/api/bridge/topics/tp-w2/generate-article')] = (503, {'detail': {'message': 'خدمة الكتابة الآلية غير متاحة الآن.'}})
    page, ctx = reopen(browser, h, tall, mobile, '#s/content/topics', 'topics')
    g = Guard(h, page)
    page.click('.v2ct-chip[data-v="working"]')
    page.wait_for_function("() => document.querySelector('.v2ct-card.topic [data-chip=working]')", timeout=10000)
    page.click('.v2ct-card.topic[data-id="t:tp-w2"] [data-a="topen"]')
    sheet_open(page)
    page.click('#v2ctMk')
    sheet_open(page)
    page.click('#v2ctGo')
    page.wait_for_function("() => document.querySelector('#epModal #v2ctRetry')", timeout=20000)
    expect('لم يُنشأ أي مقال، والموضوع بقي كما هو.' in page.inner_text('#epModal') and 'خدمة الكتابة الآلية غير متاحة الآن.' in page.inner_text('#epModal'), pre + '06i: ورقة فشل الكتابة')
    cshot(page, pre + '06i-make-article-failed.jpg')
    page.click('#v2ctNo')
    sheet_closed(page)
    # أرقام الموضوعات
    page.evaluate("() => { const b = [...document.querySelectorAll('.v2ct-box h2')].find(h => h.textContent.indexOf('أرقام الموضوعات') > -1); b.scrollIntoView(); }")
    page.wait_for_timeout(300)
    expect('الأكثر تعليقًا' in page.inner_text('.v2ct') and 'ما يسأل عنه الناس في المحادثة' in page.inner_text('.v2ct'), pre + '06j: أرقام الموضوعات ناقصة')
    cshot(page, pre + '06j-topics-numbers.jpg', scroll_top=False)
    browser.close()

    # =========================================================== ٦) الأخبار
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/news', 'news')
    g = Guard(h, page)
    expect(page.inner_text('.v2ct-chips').replace('\n', ' ').startswith('مسودات (٢)'), pre + '07: شرائح الأخبار')
    cshot(page, pre + '07-news.jpg')
    page.click('[data-a="nmain"][data-id="nw-2"]')
    sheet_open(page)
    cshot(page, pre + '07b-news-edit.jpg')
    page.click('#v2ctNo')
    sheet_closed(page)
    page.click('[data-a="nsources"]')
    sheet_open(page)
    cshot(page, pre + '07c-news-sources.jpg')
    page.click('#v2ctNo')
    sheet_closed(page)
    g.mark()
    page.click('[data-a="nmain"][data-id="nw-1"]')
    sheet_open(page)
    expect('سيظهر الخبر للأعضاء على المنصة.' in page.inner_text('#epModal'), pre + '07d: جملة نشر الخبر')
    cshot(page, pre + '07d-news-publish-confirm.jpg')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('publish-news')
    expect([n['status'] for n in h.ef.news if n['id'] == 'nw-1'] == ['published'], pre + '07d: الخبر ما اتنشرش على المنصة')
    page.click('.v2ct-chip[data-v="published"]')
    page.wait_for_timeout(250)
    g.mark()
    page.click('[data-a="nopen"][data-id="nw-3"]')
    sheet_open(page)
    page.click('#v2ctDerive')
    sheet_open(page)
    expect('يصبح الخبر موضوع نقاش على اللوحة.' in page.inner_text('#epModal'), pre + '07e: جملة تحويل الخبر')
    page.click('#v2ctGo')
    page.wait_for_function("() => location.hash.indexOf('#s/content/topics') === 0", timeout=20000)
    g.check('derive-news')
    page.wait_for_timeout(500)
    expect(page.query_selector('.v2ct-card.hl') is not None, pre + '07e: الموضوع الجديد ما اتبرزش')
    browser.close()

    # =========================================================== ٧) التعليقات
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/comments', 'comments')
    g = Guard(h, page)
    expect(set(h.ef.opinions_summarize) == {'false'} and h.ef.opinions_summarize, pre + '08: نداء تحليل التعليقات بلا summarize=false: %r' % h.ef.opinions_summarize)
    t = page.inner_text('.v2ct')
    expect('تنتظر قرارك' in t and 'ظاهرة الآن' in t and 'أرقام التعليقات' in t and 'خلاصة مكتوبة آليًا' not in t, pre + '08: بطاقات التعليقات')
    cshot(page, pre + '08-comments.jpg')
    page.click('[data-a="csummary"]')
    sheet_open(page)
    expect('رصيد الكتابة الآلية' in page.inner_text('#epModal .v2ct-lead'), pre + '08b: جملة الرصيد')
    cshot(page, pre + '08b-summary-confirm.jpg')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-sumbox')", timeout=15000)
    expect(h.ef.opinions_summarize.count('true') == 1, pre + '08c: عدد نداءات الخلاصة %r' % h.ef.opinions_summarize)
    page.evaluate("() => document.querySelector('.v2ct-sumbox').scrollIntoView()")
    cshot(page, pre + '08c-comments-summary.jpg', scroll_top=False)
    g.mark()
    page.click('[data-a="creply"][data-id="oa-2"]')
    sheet_open(page)
    cshot(page, pre + '08d-reply-sheet.jpg')
    page.fill('#rp_t', 'شكرًا لك على كلماتك الطيبة.')
    page.click('#v2ctGo')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('reply-comment')
    expect([o['editor_reply'] for o in h.ef.approved if o['id'] == 'oa-2'] == ['شكرًا لك على كلماتك الطيبة.'], pre + '08d: الرد ما وصلش للمنصة')
    expect(h.ef.opinions_summarize.count('true') == 1 and set(h.ef.opinions_summarize) <= {'false', 'true'}, pre + '08: نداءات الخلاصة بعد الرد')
    browser.close()

    # =========================================================== ٨) دليل الاستخدام
    ids = fresh()
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/tutorials', 'tutorials')
    g = Guard(h, page)
    expect('٢ قسمًا منشورًا · ١ مسودة · ١ بفيديو' in page.inner_text('.v2ct-line'), pre + '09: سطر الحقائق %r' % page.inner_text('.v2ct-line'))
    cshot(page, pre + '09-tutorials.jpg')
    page.click('[data-a="tedit"][data-id="tu-1"] >> nth=0')
    sheet_open(page)
    cshot(page, pre + '09b-tutorial-edit.jpg')
    # قسم جديد منشور ⇒ تأكيد داخل الورقة
    page.click('#epModal [data-x]')
    sheet_closed(page)
    g.mark()
    page.click('[data-a="newtut"]')
    sheet_open(page)
    page.fill('#tu_t', 'قسم جديد للدليل')
    page.click('#v2ctSave')
    page.wait_for_selector('#v2ctGo2')
    expect('يظهر هذا القسم للأعضاء فور الحفظ.' in page.inner_text('#epModal .v2ct-inconf'), pre + '09c: جملة نشر القسم')
    cshot(page, pre + '09c-tutorial-publish-confirm.jpg')
    page.click('#v2ctGo2')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('save-tutorial-published')
    page.click('[data-a="tedit"][data-id="tu-1"] >> nth=0')
    sheet_open(page)
    g.mark()
    page.click('#v2ctHide')
    sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('hide-tutorial')
    expect([t['is_published'] for t in h.ef.tutorials if t['id'] == 'tu-1'] == [False], pre + '09b: الإخفاء ما وصلش')
    browser.close()

    # =========================================================== ٩) فاضي + الروابط القديمة
    fresh(empty=True)
    ctx = browser.context(h, 'admin', tall, mobile)
    page = open_tab(ctx, '#s/content/pipeline', 'pipeline')
    hero = page.inner_text('.v2ct-hero p')
    expect(hero == 'لا شيء ينتظر قرارك الآن.', pre + '10: سطر العقل مع الفاضي «%s»' % hero)
    expect(page.evaluate("() => document.querySelector('.v2ct-cols').textContent").count('لا شيء هنا الآن') >= 3, pre + '10: أعمدة فاضية بلا نص')
    cshot(page, pre + '10-empty.jpg')
    for old, want, tabtxt in (('#topics', '#s/content/pipeline', 'خط النشر'), ('#tutorials', '#s/content/tutorials', 'دليل الاستخدام'), ('#s/content/topics', '#s/content/topics', 'الموضوعات')):
        pg, ctx = reopen(browser, h, tall, mobile, old, {'#topics': 'pipeline', '#tutorials': 'tutorials', '#s/content/topics': 'topics'}[old])
        got = pg.evaluate("() => ({hash: location.hash, on: document.querySelector('.v2c-tab.on').textContent.trim(), old: !!document.querySelector('#topicsTabs, .tabbar, .kpis, .inboxwrap')})")
        expect(got['hash'] == want and got['on'] == tabtxt and not got['old'], pre + '10: الرابط %s ⇒ %r' % (old, got))
    ctx = browser.context(h, 'admin', tall, mobile)
    pg = ctx.new_page()
    pg.goto(DASH + '/#s/home', wait_until='domcontentloaded')
    pg.wait_for_function(base.SHELL_READY, timeout=30000)
    pg.wait_for_selector('[data-tile="content"]', timeout=20000)
    pg.click('[data-tile="content"]')
    pg.wait_for_function("() => document.querySelector('.v2ct')", timeout=15000)
    expect(pg.evaluate("() => location.hash") == '#s/content/pipeline', pre + '10: مربّع المحتوى ما فتحش خط النشر')
    browser.close()
    return ids


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    only = sys.argv[2] if len(sys.argv) > 2 else ''
    h = Harness(cfx.ContentPlatform())
    # لا SFTP ولا خيط توليد: التوليد الثابت مبدَّل بدالة فاضية (الحالة الظاهرة للمستخدم تُضبط في fresh()).
    h.app._prerender_push_async = lambda reason='': {'state': 'started', 'reason': reason}
    with sync_playwright() as p:
        browser = base.Browsers(p)
        try:
            for pre, vp, mobile in (('d-', DESK, False), ('t-', TAB, False), ('m-', MOB, True)):
                if only and not pre.startswith(only):
                    continue
                flow(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': base.OUT, 'shots': base.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
