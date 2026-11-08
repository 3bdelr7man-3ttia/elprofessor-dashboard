# -*- coding: utf-8 -*-
"""لقطات وفحوص «ناقشها في الساحة» من محرّر المقال (docs/v2/saha-link/SPEC.md) — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٤٣٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_saha_link.py ../docs/v2/saha-link/shots [site-dir]

الخطوات: ٠١ قارئ مقال منشور بلا نقاش · ٠٢ نموذج المراجعة · ٠٣ ورقة التأكيد · ٠٤ القارئ والنقاش مفتوح · ٠٥ ورقة الفصل ·
٠٦ مسودة (لا نقاش قبل النشر) · ٠٧ الرد الضايع ثم إعادة المحاولة (تبنّي النقاش اللي اتفتح) · ٠٨ صفحة المقال المُسبقة العرض بالزرّ (لو مُرِّر مجلد الموقع).

السكربت بيفشل (exit 1) لو: هدف أقل من ٤٤px · تمرير أفقي · «undefined/NaN/null» ظاهرة · رقم لاتيني ظاهر · «·» ملاصقة لرقم · كلمة ممنوعة ·
نافذة متصفح · كتابة وصلت المنصة قبل ضغطة التأكيد · نقاش اتكرّر · أي طلب خرج من العملية غير خطوط جوجل.
⛔ صفر طلبات حقيقية: الداشبورد جوه العملية، والمنصة في الذاكرة (`saha_link_fixtures.SahaLinkPlatform`)، و`_prerender_push_async` متبدّلة بدالة فاضية.
"""
import json
import os
os.environ.setdefault('DASH_SCHEDULER', '0')   # R16: مراقبة التشغيل/الملخص اليومي ما يشتغلوش جوّه الأداة (كانوا بيبعتوا تليجرام عبر الجسر المزيّف)
import re
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as base                         # noqa: E402  (OUT من argv[1])
import v2_shots_content as vc                   # noqa: E402
import saha_link_fixtures as sfx                # noqa: E402
import content_fixtures as cfx                  # noqa: E402
from ef_route_harness import Harness, DASH      # noqa: E402

PROBLEMS = base.PROBLEMS
DESK = {'width': 1440, 'height': 900}
MOB = {'width': 430, 'height': 932}
BANNED = ('يقوّم', 'يقوم', 'API', 'JSON', 'Claude', 'DeepSeek', 'bridge', 'token')
SAHA_URL = re.compile(r'^https://app\.elprofessor\.net/\?page=saha&topic=[A-Za-z0-9_-]{8,64}$')


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def sheet_text_check(page, name):
    txt = page.evaluate("""() => { const m = document.querySelector('#epModal .v2ct-m'); if (!m) return '';
      const c = m.cloneNode(true); c.querySelectorAll('input,textarea,.v2ct-ltr,[dir=ltr],script,style').forEach(n => n.remove()); return c.innerText; }""")
    for w in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(w), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, w))
    if re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', txt):
        PROBLEMS.append('%s: «·» ملاصقة لرقم' % name)


def snap(page, name):
    vc.sheet_open(page) if page.query_selector('#epModal') else None
    page.evaluate("() => { const b = document.querySelector('#epModal .v2ct-saha'); if (b) b.scrollIntoView({block: 'center'}); }")
    base.shot(page, name)
    vc.ct_check(page, name)
    sheet_text_check(page, name)


def open_reader(page, aid, published=True):
    if published:
        page.click('.v2ct-chip[data-v="published"]')
        page.wait_for_timeout(300)
    else:
        page.click('.v2ct-chip[data-v="draft"]')
        page.wait_for_timeout(300)
    page.click('.v2ct-card.art[data-id="%s"]' % aid)
    vc.sheet_open(page)


def close_sheet(page):
    page.click('#epModal [data-x]')
    vc.sheet_closed(page)


def flow(browser, h, pre, viewport, mobile, site_dir):
    tall = dict(viewport, height=viewport['height'] if viewport['width'] <= 440 else 1500)

    def fresh():
        h.ef = sfx.SahaLinkPlatform()
        ids = cfx.seed_site(h.app)
        with h.app.app.app_context():
            h.app.AuditLog.query.filter(h.app.AuditLog.action.like('article.saha%')).delete(synchronize_session=False)
            h.app.db.session.commit()
        return ids

    ids = fresh()
    pub_id, draft_id = ids[4], ids[1]
    pushes = []
    h.app._prerender_push_async = lambda reason='': pushes.append(reason) or {'state': 'started', 'reason': reason}

    # ١) قارئ مقال منشور بلا نقاش
    ctx = browser.context(h, 'admin', tall, mobile)
    page = vc.open_tab(ctx, '#s/content/articles', 'articles')
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح ظهرت: %s' % d.message[:60]), d.dismiss()))
    g = vc.Guard(h, page)
    open_reader(page, pub_id)
    body = page.inner_text('#epModal')
    expect('النقاش في الساحة' in body and 'افتح نقاشًا لهذا المقال' in body and 'لا نقاش لهذا المقال' in body, pre + '01: كتلة الساحة ناقصة')
    expect(page.query_selector('#v2ctSahaDetach') is None, pre + '01: زرّ «افصل» ظاهر بلا نقاش')
    snap(page, pre + '01-reader-no-topic.jpg')

    # ٢) نموذج المراجعة (عنوان وسؤال جاهزان من المقال)
    page.click('#v2ctSahaOpen')
    page.wait_for_selector('#sh_t')
    expect(page.input_value('#sh_t') == 'كيف تقرأ عقد الإيجار', pre + '02: عنوان النقاش الافتراضي %r' % page.input_value('#sh_t'))
    expect(page.input_value('#sh_q').startswith('مقتطف قصير عن'), pre + '02: سؤال النقاش الافتراضي')
    expect('صورة المقال تصير غلاف النقاش' in page.inner_text('#epModal'), pre + '02: سطر الغلاف')
    snap(page, pre + '02-form.jpg')

    # ٣) ورقة التأكيد: لا كتابة قبلها، و«رجوع» لا يضيّع ما كُتب
    g.mark()
    page.fill('#sh_t', 'هل يكفي عقد الإيجار غير الموثّق لإثبات العلاقة؟')
    page.click('#v2ctSahaGo')
    page.wait_for_selector('#v2ctGo2')
    expect('سيُفتح نقاش «هل يكفي عقد الإيجار غير الموثّق لإثبات العلاقة؟» للناس في الساحة الآن' in page.inner_text('#epModal .v2ct-inconf'), pre + '03: جملة التأكيد')
    expect(not g.writes() and not h.ef.writes, pre + '03: كتابة قبل التأكيد')
    snap(page, pre + '03-confirm.jpg')
    page.click('#v2ctNo2')
    page.wait_for_selector('#sh_t')
    expect(page.input_value('#sh_t').startswith('هل يكفي عقد الإيجار'), pre + '03: «رجوع» أضاع ما كُتب')
    page.click('#v2ctSahaGo')
    page.wait_for_selector('#v2ctGo2')
    page.click('#v2ctGo2')
    vc.sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    g.check('open-saha-topic')
    expect('تمّ: فُتح النقاش' in vc.note_text(page), pre + '03: شريط النجاح %r' % vc.note_text(page))
    posts = [w for w in h.ef.writes if w[0] == 'POST' and w[1] == '/api/bridge/topics']
    expect(len(posts) == 1 and posts[0][2]['source_article_slug'].endswith('-%d' % pub_id) and posts[0][2]['cover_url'].startswith('https://'), pre + '03: نداء الإنشاء %r' % posts)
    expect(len(h.ef.topics) >= 1 and h.ef.topics[0]['status'] == 'published', pre + '03: النقاش لم يُفتح للناس')
    expect(pushes and pushes[-1] == 'article-saha:%d' % pub_id, pre + '03: توليد الصفحات لم يُطلب %r' % pushes)
    vc.cshot(page, pre + '03b-note.jpg')

    # ٤) القارئ والنقاش مفتوح
    page.click('.v2ct-card.art[data-id="%s"]' % pub_id)
    vc.sheet_open(page)
    body = page.inner_text('#epModal')
    expect('النقاش مفتوح' in body and 'افتح النقاش في الساحة' in body and 'افصل' in body and 'افتح نقاشًا لهذا المقال' not in body, pre + '04: حالة «النقاش مفتوح» %r' % body[-300:])
    href = page.get_attribute('#epModal a.v2ct-link[href*="page=saha"]', 'href')
    expect(bool(href) and bool(SAHA_URL.match(href)), pre + '04: رابط النقاش %r' % href)
    expect(page.get_attribute('#epModal a.v2ct-link[href*="page=saha"]', 'rel') == 'noopener noreferrer', pre + '04: rel الرابط')
    snap(page, pre + '04-reader-open.jpg')

    # ٥) الفصل: ورقة تأكيد، ولا نداء للمنصة
    g.mark()
    n_plat = len(h.platform_calls)
    page.click('#v2ctSahaDetach')
    vc.sheet_open(page)
    expect('النقاش نفسه يبقى في الساحة' in page.inner_text('#epModal'), pre + '05: جملة الفصل')
    expect(not [c for c in h.dash_calls[g.d0:] if 'saha-topic' in c[1]], pre + '05: نداء قبل التأكيد')
    snap(page, pre + '05-detach-confirm.jpg')
    page.click('#v2ctGo')
    vc.sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    expect('تمّ: فُصل النقاش عن المقال.' in vc.note_text(page), pre + '05: شريط الفصل')
    expect(len(h.platform_calls) == n_plat, pre + '05: الفصل نادى المنصة')
    mine = [t for t in h.ef.topics if str(t.get('source_article_slug') or '').endswith('-%d' % pub_id)]
    expect(len(mine) == 1 and mine[0]['status'] == 'published', pre + '05: الفصل مسّ النقاش نفسه %r' % mine)
    page.click('.v2ct-card.art[data-id="%s"]' % pub_id)
    vc.sheet_open(page)
    expect('لا نقاش لهذا المقال' in page.inner_text('#epModal'), pre + '05: القارئ بعد الفصل')
    close_sheet(page)

    # ٦) مسودة: لا نقاش قبل النشر
    page.click('.v2ct-chip[data-v="draft"]')
    page.wait_for_timeout(300)
    page.click('.v2ct-card.art[data-id="%s"]' % draft_id)
    vc.sheet_open(page)
    body = page.inner_text('#epModal')
    expect('يُفتح النقاش بعد نشر المقال على الموقع' in body and page.query_selector('#v2ctSahaOpen') is None, pre + '06: المسودة تعرض زرّ فتح')
    snap(page, pre + '06-draft.jpg')
    close_sheet(page)

    # ٧) الرد الضايع: النقاش اتفتح عند المنصة والرد ضاع ⇒ رسالة صادقة، وإعادة المحاولة تتبنّى الموجود (لا تكرار)
    h.ef.lost_after_create = True
    page.click('.v2ct-chip[data-v="published"]')
    page.wait_for_timeout(300)
    n_topics = len(h.ef.topics)
    page.click('.v2ct-card.art[data-id="%s"]' % ids[5])
    vc.sheet_open(page)
    page.click('#v2ctSahaOpen')
    page.wait_for_selector('#sh_t')
    page.click('#v2ctSahaGo')
    page.wait_for_selector('#v2ctGo2')
    page.click('#v2ctGo2')
    page.wait_for_function("() => { const e = document.querySelector('#v2ctErr2 .v2ct-err'); return e && e.textContent.length > 5; }", timeout=15000)
    err = page.inner_text('#v2ctErr2')
    expect('لم يصل رد' in err and 'ولن يتكرر' in err, pre + '07: رسالة الرد الضايع %r' % err)
    expect(len(h.ef.topics) == n_topics + 1, pre + '07: النقاش لم يُنشأ عند المنصة')
    snap(page, pre + '07-lost-reply.jpg')
    h.ef.lost_after_create = False
    page.click('#v2ctGo2')
    vc.sheet_closed(page)
    page.wait_for_function("() => document.querySelector('.v2ct-ok')", timeout=15000)
    expect('ربطنا بالمقال نقاشًا سابقًا' in vc.note_text(page), pre + '07: شريط التبنّي %r' % vc.note_text(page))
    expect(len(h.ef.topics) == n_topics + 1, pre + '07: النقاش اتكرّر بعد إعادة المحاولة')
    expect(h.ef.topics[0]['status'] == 'published', pre + '07: النقاش المتبنّى لم يُفتح للناس')
    browser.close()

    # ٨) صفحة المقال المُسبقة العرض بالزرّ (القالب الحقيقي من ريبو الموقع)
    if site_dir:
        render_site_page(browser, h, pre, viewport, mobile, site_dir)
    return ids


def render_site_page(browser, h, pre, viewport, mobile, site_dir):
    """يُولّد صفحة المقال بـprerender.py الحقيقي (ملف فيد من الدفتر) ويصوّرها بلا شبكة: كل طلب غير الصفحة نفسها بيتقفل."""
    import datetime
    app = h.app
    with app.app.app_context():
        app.Article.query.delete()
        long = ('هذا نص تجريبي طويل يشرح المبدأ القانوني بالتفصيل ويعطي القارئ خطوات عملية واضحة. ' * 12).strip()
        rows = []
        for i in range(30):
            rows.append(app.Article(title='مقال تحليلي عن موضوع قانوني رقم %d' % i, excerpt=long[:160], cat='دليل', kicker='دليل', by='فريق منصة البروفيسور', date='١ أكتوبر ٢٠٢٦',
                                    body=json.dumps(['## ' + str(i), long, long], ensure_ascii=False), keywords='[]', faq='[]', target_audience='المحامون', status='published',
                                    published_at=datetime.datetime(2026, 9, 1) + datetime.timedelta(days=i)))
        a = app.Article(title='هل يكفي عقد الإيجار غير الموثّق لإثبات العلاقة الإيجارية؟', excerpt='مسألة تتكرر أمام المحاكم وتختلف الإجابة فيها بحسب الوقائع.', cat='دليل', kicker='دليل',
                        by='فريق منصة البروفيسور', date='١ نوفمبر ٢٠٢٦', body=json.dumps(['## الفكرة', long, '## التطبيق', long, long], ensure_ascii=False), keywords='[]', faq='[]',
                        target_audience='المحامون', status='published', published_at=datetime.datetime(2026, 11, 1), saha_topic_id=sfx.TID_PREFIX + '000000000001')
        app.db.session.add_all(rows + [a])
        app.db.session.commit()
        aid = a.id
        feed = app._prerender_feed_json()
    tmp = tempfile.mkdtemp(prefix='saha-shot-')
    try:
        for name in ('article.html', 'blog.html'):
            shutil.copy(os.path.join(site_dir, name), os.path.join(tmp, name))
        os.makedirs(os.path.join(tmp, 'blog', '_pre'))
        os.makedirs(os.path.join(tmp, 'blog', '_topic'))
        ff = os.path.join(tmp, '_feed.json')
        with open(ff, 'w', encoding='utf-8') as fh:
            fh.write(feed)
        proc = subprocess.run(['python3', os.path.join(os.path.dirname(os.path.dirname(_HERE)), 'prerender.py'), '--site', tmp, '--feed-file', ff, '--min-articles', '1'],
                              capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            PROBLEMS.append(pre + '08: prerender فشل: %s' % proc.stderr[-400:])
            return
        html = open(os.path.join(tmp, 'blog', '_pre', '%d.html' % aid), encoding='utf-8').read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    from playwright.sync_api import sync_playwright  # noqa: F401
    b = browser.p.chromium.launch(args=['--single-process'])
    try:
        ctx = b.new_context(viewport=viewport, locale='ar-EG', **({'device_scale_factor': 2, 'is_mobile': True, 'has_touch': True} if mobile else {}))
        url = 'https://elprofessor.net/blog/page-%d' % aid
        blocked = []

        def route(r):
            u = r.request.url
            if u == url:
                return r.fulfill(status=200, content_type='text/html; charset=utf-8', body=html)
            path = u.split('://', 1)[-1].split('/', 1)[-1].split('?', 1)[0]
            local = os.path.join(site_dir, path)
            if u.startswith('https://elprofessor.net/') and path.endswith(('.css', '.png', '.svg', '.jpg')) and os.path.isfile(local):
                ctype = {'css': 'text/css', 'png': 'image/png', 'svg': 'image/svg+xml', 'jpg': 'image/jpeg'}[path.rsplit('.', 1)[-1]]
                with open(local, 'rb') as fh:
                    return r.fulfill(status=200, content_type=ctype, body=fh.read())
            blocked.append(u)
            return r.abort()
        ctx.route('**/*', route)
        page = ctx.new_page()
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_selector('.art .saha-btn', timeout=15000)
        page.evaluate("() => document.querySelector('.art .saha').scrollIntoView({block: 'center'})")
        page.wait_for_timeout(400)
        href = page.get_attribute('.art .saha-btn', 'href')
        expect(bool(href) and bool(SAHA_URL.match(href)), pre + '08: رابط الزرّ %r' % href)
        box = page.evaluate("() => { const b = document.querySelector('.art .saha-btn').getBoundingClientRect(); return [Math.round(b.height), Math.round(b.width)]; }")
        expect(box[0] >= 44, pre + '08: الزرّ أقل من ٤٤px %r' % box)
        sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        expect(sw <= viewport['width'] + 1, pre + '08: تمرير أفقي %s' % sw)
        page.screenshot(path=os.path.join(base.OUT, pre + '08-site-article-button.jpg'), type='jpeg', quality=82)
        base.SHOTS.append(pre + '08-site-article-button.jpg')
        # السكربتات (تتبّع · محمّل المقالات) بتتقفل عمدًا؛ المهم إن مفيش طلب لأصل غريب
        unexpected = [u for u in blocked if not u.startswith(('https://elprofessor.net/', 'https://fonts.googleapis.com', 'https://fonts.gstatic.com',
                                                               'https://www.googletagmanager.com', 'https://www.facebook.com'))]
        expect(not unexpected, pre + '08: طلبات غير متوقعة %r' % unexpected[:3])
    finally:
        b.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    site_dir = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else ''
    h = Harness(sfx.SahaLinkPlatform())
    with sync_playwright() as p:
        browser = base.Browsers(p)
        try:
            for pre, vp, mobile in (('d-', DESK, False), ('m-', MOB, True)):
                flow(browser, h, pre, vp, mobile, site_dir)
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
