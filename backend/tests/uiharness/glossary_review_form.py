# -*- coding: utf-8 -*-
"""إثبات سلوك نموذج «أنت متخصص؟ راجِع هذا المصطلح» وعلامات الفهرس في متصفح حقيقي (docs/v2/glossary/SPEC.md، الجولة ٢).

    cd backend && python3 -B tests/uiharness/glossary_review_form.py [/path/to/site-checkout]

صفحات القاموس تُولَّد بالمولّد الحقيقي من القالبين الحقيقيين (فيد محلي، بلا شبكة) ثم تُخدَم من الذاكرة على https://elprofessor.net/...
⛔ صفر شبكة حقيقية: `window.fetch` مبدَّلة قبل أي سكربت (تسجّل الطلبات وتردّ بما نُملي: ٢٠١ ثم ٤٠٠ ثم ٤٢٩ ...)، وكل أصل غير ملفات
الموقع المحلية (css وصور) يُجهَض في المتصفح ويُعدّ، وملفات السكربت المحلية (الكوكيز والقياس) تُجهَض أيضًا. يُفشل السكربت إن وصل أي
طلب لمضيف الداشبورد عبر الشبكة.

يثبت: النموذج يُفتح بلوحة المفاتيح · التحقق يمنع الإرسال برسالة عربية لكل خطأ · الجسم المرسَل JSON حرفيًّا (ترتيب المفاتيح وقيمها) إلى الوجهة الحرفية
بلا بيانات اعتماد · ٢٠١ ⇒ رسالة النجاح وإخفاء الحقول · ٤٠٠ يعرض تفصيل الخادم أو رسالة عامة · ٤٢٩ و٤٠٤ والانقطاع ⇒ رسائل عربية والزر يعود يعمل ·
فخّ الروبوتات غير مرئي ولا يُصل بالتبويب، وإن امتلأ لا يُرسَل شيء · الأهداف ≥ ٤٤px والخانات ≥ ١٦px ولا تمرير أفقي · بلا JS: لا نموذج وكل مصطلح ظاهر ·
أزرار تصفية الفهرس تعمل وتحدّث العدّادات · الصفحة الخام (القالب) ترسم الحالة والنموذج من فيد وهمي.
خروج ٠ = نجاح · ١ = فشل · ٧٧ = لا متصفح في هذه البيئة.
"""
import json
import mimetypes
import os
import sys
import tempfile
from urllib.parse import urlparse, unquote

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, BACKEND)
os.environ.setdefault('SECRET_KEY', 'x' * 64)
SITE = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '/Users/abdelrhman/elprofessor-site/.worktrees/glossary')
HOST = 'elprofessor.net'
ENDPOINT = 'https://dashboard.elprofessor.net/api/public/expert-reviews'
FEED_URL = 'https://dashboard.elprofessor.net/api/content/glossary'
PROBLEMS = []
BLOCKED = {}
LOG = []

import prerender as pr  # noqa: E402

AREAS = [{'code': 'contracts', 'label': 'عقود'}, {'code': 'litigation', 'label': 'تقاضٍ'}, {'code': 'other', 'label': 'أخرى'}]


def term(slug, ar, en, **kw):
    t = {'id': 1, 'slug': slug, 'ar': ar, 'en': en, 'fr': None, 'area': 'contracts', 'area_label': 'عقود',
         'definition_ar': 'تعريف تجريبي للمصطلح يشرح معناه للقارئ بجملة واضحة وكافية للتحقق.', 'example_en': None, 'example_ar': None,
         'false_friend_note_ar': None, 'countries_note_ar': None, 'related': [], 'review_state': 'under_review',
         'reviewed_by_name': None, 'reviewed_by_role': None, 'reviewed_at': None, 'saha_topic_id': None,
         'published_at': '2026-11-01T10:05:00', 'updated_at': '2026-11-01T10:05:00'}
    t.update(kw)
    return t


TERMS = [
    term('offer', 'الإيجاب', 'offer'),
    term('breach', 'الإخلال', 'breach', area='litigation', area_label='تقاضٍ', review_state='confirmed', reviewed_by_name='أ. سلمى الحسيني',
         reviewed_by_role='محكّمة', reviewed_at='2026-11-01T09:00:00', countries_note_ar='يختلف الاسم في بعض البلاد.'),
    term('waiver', 'التنازل', 'waiver', review_state='confirmed', reviewed_at='2026-11-01T09:00:00'),
]


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def serve(route, pages):
    u = urlparse(route.request.url)
    if u.hostname != HOST:
        key = u.hostname or u.scheme
        BLOCKED[key] = BLOCKED.get(key, 0) + 1
        return route.abort()
    p = unquote(u.path)
    if p in pages:
        return route.fulfill(status=200, body=pages[p], content_type='text/html; charset=utf-8')
    f = os.path.normpath(os.path.join(SITE, p.lstrip('/')))
    ext = os.path.splitext(f)[1].lower()
    if f.startswith(SITE) and os.path.isfile(f) and ext in ('.css', '.png', '.svg', '.jpg', '.webp') or (p == '/glossary-term.html'):
        ctype = mimetypes.guess_type(f)[0] or 'text/html'
        return route.fulfill(status=200, body=open(f, 'rb').read(), content_type=ctype + ('; charset=utf-8' if ctype.startswith('text') else ''))
    BLOCKED['local-skipped:' + p] = BLOCKED.get('local-skipped:' + p, 0) + 1          # كوكيز/قياس/خطوط: لا تُحمَّل
    return route.abort()


FAKE_FETCH = """
window.__calls = []; window.__queue = []; window.__feed = %s;
window.fetch = function (url, init) {
  url = String(url);
  if (url === %s) return Promise.resolve({status: 200, ok: true, json: function () { return Promise.resolve(window.__feed); }});
  window.__calls.push({url: url, method: init && init.method, headers: init && init.headers, credentials: init && init.credentials,
                       mode: init && init.mode, body: init && init.body});
  var step = window.__queue.shift() || {status: 201, json: {ok: true}};
  if (step.reject) return Promise.reject(new TypeError('Failed to fetch'));
  return Promise.resolve({status: step.status, ok: step.status >= 200 && step.status < 300,
    json: function () { return step.badjson ? Promise.reject(new Error('no json')) : Promise.resolve(step.json); }});
};
"""


def build_pages(tmp):
    gf = os.path.join(tmp, 'g.json')
    json.dump({'source': 'dashboard', 'areas': AREAS, 'terms': TERMS}, open(gf, 'w', encoding='utf-8'), ensure_ascii=False)
    summary, built = pr.glossary_step(SITE, gf)
    assert summary['state'] == 'ok', summary
    return {'/glossary/' + os.path.basename(p): h for p, h in built.items() if not p.endswith('index.html')} | \
           {'/glossary/': [h for p, h in built.items() if p.endswith('index.html')][0]}


def fill(page, name='سلمى أحمد', email='salma@example.org', spec='law_practice', verdict='confirm', text='', show=False, other=''):
    page.fill('#glr-name', name)
    page.fill('#glr-email', email)
    page.select_option('#glr-spec', spec)
    if other:
        page.fill('#glr-other', other)
    if verdict:
        page.check('input[name=verdict][value=%s]' % verdict)
    if text:
        page.fill('#glr-text', text)
    if show:
        page.check('input[name=show_name]')
    else:
        page.uncheck('input[name=show_name]')


def calls(page):
    return page.evaluate('window.__calls')


def queue(page, *steps):
    page.evaluate('(s) => { window.__queue = s; window.__calls = []; }', list(steps))


def err_text(page):
    return page.evaluate("() => { const e = document.querySelector('[data-gl-err]'); return e.hidden ? '' : e.textContent; }")


def submit(page):
    page.click('form[data-gl-review] button[type=submit]')
    page.wait_for_timeout(60)


def run(ctxs):
    from playwright.sync_api import sync_playwright
    with tempfile.TemporaryDirectory() as tmp:
        pages = build_pages(tmp)
        with sync_playwright() as p:
            opened = []

            def mk(**kw):
                # --single-process (يعمل داخل الصندوق) لا يحتمل إلا سياقًا واحدًا لكل متصفح ⇒ متصفح جديد لكل سيناريو
                b = p.chromium.launch(args=['--single-process'])
                opened.append(b)
                return b.new_context(locale='ar', **kw)
            try:
                m = mk(viewport={'width': 390, 'height': 844})
            except Exception as exc:                                  # noqa: BLE001
                print('no browser available: %s' % str(exc)[:200])
                return 77
            m.add_init_script(FAKE_FETCH % (json.dumps({'terms': TERMS, 'areas': AREAS}), json.dumps(FEED_URL)))
            m.route('**/*', lambda r, _rq, pg=pages: serve(r, pg))
            page = m.new_page()
            page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت في الصفحة: %s' % e))
            page.on('dialog', lambda d: (PROBLEMS.append('نافذة منبثقة: %s' % d.message), d.dismiss()))

            # ——— ١) صفحة تحت التأكيد، النموذج يُفتح بلوحة المفاتيح
            page.goto('https://elprofessor.net/glossary/offer.html')
            expect(page.evaluate('window.EP_PRERENDERED') is True, 'الصفحة ليست مُسبقة العرض')
            body = page.inner_text('main')
            expect('تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' in body and 'راجعه' not in body, 'شارة تحت التأكيد غائبة أو معها مراجع')
            expect(page.is_visible('summary.gl-sum') and not page.is_visible('#glr-name'), 'الزر ظاهر والحقول مطوية')
            page.focus('summary.gl-sum')
            page.keyboard.press('Enter')
            page.wait_for_timeout(50)
            expect(page.is_visible('#glr-name') and page.is_visible('#glr-email'), 'Enter على الزر لا يفتح النموذج')
            page.keyboard.press('Enter')
            page.wait_for_timeout(50)
            expect(not page.is_visible('#glr-name'), 'Enter الثانية لا تطوي النموذج')
            page.keyboard.press('Space')
            page.wait_for_timeout(50)
            expect(page.is_visible('#glr-name'), 'Space لا تفتح النموذج')

            # فخّ الروبوتات: غير مرئي، لا يُصل بالتبويب، خارج شجرة الوصول
            hp = page.evaluate("""() => { const i = document.querySelector('input[name=website]'), w = i.closest('.gl-hp'), r = w.getBoundingClientRect(), s = getComputedStyle(w);
              return {w: r.width, h: r.height, op: s.opacity, pos: s.position, aria: w.getAttribute('aria-hidden'), tab: i.tabIndex, val: i.value}; }""")
            expect(hp['w'] <= 1 and hp['h'] <= 1 and hp['op'] == '0' and hp['pos'] == 'absolute' and hp['aria'] == 'true' and hp['tab'] == -1 and hp['val'] == '',
                   'فخّ الروبوتات ظاهر أو قابل للتبويب: %r' % hp)
            seen = []
            page.focus('#glr-name')
            for _ in range(14):
                seen.append(page.evaluate('document.activeElement.name || document.activeElement.tagName'))
                page.keyboard.press('Tab')
            expect('website' not in seen and 'email' in seen and 'specialty' in seen and 'verdict' in seen, 'ترتيب التبويب غير سليم: %r' % seen)

            # الأهداف والخطوط
            small = page.evaluate("""() => [...document.querySelectorAll('.gl-review summary, .gl-review button, .gl-review select, .gl-review input:not([type=hidden]):not([type=checkbox]):not([type=radio]), .gl-review textarea, .gl-review .gl-opt')]
              .filter(e => !e.closest('.gl-hp') && e.offsetParent).map(e => [e.name || e.className, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
            expect(not small, 'أهداف أقل من ٤٤px: %r' % small)
            fonts = page.evaluate("() => [...document.querySelectorAll('.gl-review input:not([type=hidden]):not([type=checkbox]):not([type=radio]), .gl-review select, .gl-review textarea')].filter(e => !e.closest('.gl-hp')).map(e => [e.name, parseFloat(getComputedStyle(e).fontSize)]).filter(x => x[1] < 16)")
            expect(not fonts, 'خطوط أقل من ١٦px: %r' % fonts)
            expect(page.evaluate('document.documentElement.scrollWidth') <= 391, 'تمرير أفقي على الجوال')

            # ——— ٢) التحقق: لا طلب مع أي خطأ، ورسالة عربية لكل خطأ
            queue(page)
            submit(page)
            expect('اكتب اسمك' in err_text(page) and calls(page) == [], 'الإرسال الفارغ: %r' % err_text(page))
            fill(page, name='س')
            submit(page)
            expect('اكتب اسمك' in err_text(page), 'اسم حرف واحد يمرّ')
            fill(page, email='not-an-email')
            submit(page)
            expect('بريدًا إلكترونيًا صحيحًا' in err_text(page), 'بريد خاطئ يمرّ')
            fill(page, email='a@b.co', spec='')
            submit(page)
            expect('اختر تخصصك' in err_text(page), 'بلا تخصص يمرّ')
            page.select_option('#glr-spec', 'other')
            expect(page.is_visible('#glr-other'), 'حقل «اكتب تخصصك» لا يظهر عند اختيار أخرى')
            submit(page)
            expect('اكتب تخصصك' in err_text(page), 'أخرى بلا نص تمرّ')
            page.fill('#glr-other', 'تحكيم دولي')
            page.evaluate("() => document.querySelectorAll('input[name=verdict]').forEach(r => r.checked = false)")
            submit(page)
            expect('اختر: أؤكد الترجمة والتعريف' in err_text(page), 'بلا رأي يمرّ')
            page.check('input[name=verdict][value=suggest]')
            expect('التعديل المقترح' in page.inner_text('[data-gl-textlabel]'), 'عنوان الحقل لا يتبدّل عند «أقترح تعديلًا»')
            submit(page)
            expect('اكتب التعديل الذي تقترحه' in err_text(page) and calls(page) == [], 'اقتراح بلا نص يمرّ')
            page.check('input[name=verdict][value=confirm]')
            page.fill('#glr-text', 'ن' * 1001)
            page.evaluate("() => { document.getElementById('glr-text').value = 'ن'.repeat(1001); }")
            submit(page)
            expect('أطول من الحد' in err_text(page) and calls(page) == [], 'نص التأكيد الأطول من ١٠٠٠ يمرّ')
            expect(err_text(page) != '' and page.evaluate("document.querySelector('[data-gl-err]').getAttribute('role')") == 'alert', 'الخطأ ليس role=alert')

            # ——— ٣) الإرسال الناجح: الجسم حرفيًّا
            page.reload()
            page.click('summary.gl-sum')
            queue(page, {'status': 201, 'json': {'ok': True}})
            fill(page, name=' سلمى أحمد ', email=' salma@example.org ', spec='judiciary', verdict='confirm', show=True)
            submit(page)
            c = calls(page)
            expect(len(c) == 1, 'عدد الطلبات %d' % len(c))
            if c:
                expect(c[0]['url'] == ENDPOINT and c[0]['method'] == 'POST' and c[0]['credentials'] == 'omit' and c[0]['mode'] == 'cors', 'الطلب: %r' % c[0])
                expect(c[0]['headers'] == {'Content-Type': 'application/json'}, 'الترويسات: %r' % c[0]['headers'])
                want = {'kind': 'glossary_term', 'ref': 'offer', 'name': 'سلمى أحمد', 'email': 'salma@example.org', 'specialty': 'judiciary',
                        'specialty_other': '', 'verdict': 'confirm', 'text': '', 'show_name': True, 'website': ''}
                expect(json.loads(c[0]['body']) == want, 'الجسم: %r' % c[0]['body'])
                expect(list(json.loads(c[0]['body']).keys()) == list(want.keys()), 'ترتيب مفاتيح الجسم')
            ok = page.inner_text('[data-gl-ok]')
            expect(ok == 'وصلت مراجعتك، شكرًا لك. سنراجعها ونتواصل معك.' and not page.is_visible('#glr-name') and err_text(page) == '',
                   'رسالة النجاح: %r' % ok)
            expect(page.evaluate("document.activeElement === document.querySelector('[data-gl-ok]')"), 'التركيز لا ينتقل لرسالة النجاح')

            # اقتراح + أخرى + بلا إظهار اسم
            page.reload()
            page.click('summary.gl-sum')
            queue(page, {'status': 201, 'json': {'ok': True}})
            fill(page, spec='other', other='تحكيم دولي', verdict='suggest', text='الأدق «العرض» لا «الإيجاب» في هذا السياق.', show=False)
            submit(page)
            c = calls(page)
            expect(len(c) == 1 and json.loads(c[0]['body']) == {
                'kind': 'glossary_term', 'ref': 'offer', 'name': 'سلمى أحمد', 'email': 'salma@example.org', 'specialty': 'other',
                'specialty_other': 'تحكيم دولي', 'verdict': 'suggest', 'text': 'الأدق «العرض» لا «الإيجاب» في هذا السياق.',
                'show_name': False, 'website': ''}, 'جسم الاقتراح: %r' % (c and c[0]['body']))

            # ——— ٤) ردود الخادم والانقطاع، ثم نجاح بعد إعادة المحاولة
            page.reload()
            page.click('summary.gl-sum')
            fill(page, verdict='suggest', text='اقتراح')
            for step, needle in (({'status': 400, 'json': {'error': 'invalid', 'detail': 'البريد الإلكتروني غير صالح.'}}, 'البريد الإلكتروني غير صالح.'),
                                 ({'status': 400, 'badjson': True}, 'تعذّر قبول البيانات'),
                                 ({'status': 429, 'json': {'error': 'rate_limited', 'detail': 'محاولات كثيرة، جرّب بعد قليل'}}, 'محاولات كثيرة، جرّب بعد قليل'),
                                 ({'status': 404, 'json': {'error': 'not_found'}}, 'لم نعثر على هذا المصطلح'),
                                 ({'status': 500, 'json': {}}, 'تعذّر الإرسال الآن'),
                                 ({'reject': True}, 'تعذّر الإرسال الآن')):
                queue(page, step)
                submit(page)
                expect(needle in err_text(page) and not page.is_disabled('form[data-gl-review] button[type=submit]') and page.is_visible('#glr-name'),
                       'الرد %r أعطى %r' % (step, err_text(page)))
            queue(page, {'status': 201, 'json': {'ok': True}})
            submit(page)
            expect(len(calls(page)) == 1 and err_text(page) == '' and 'وصلت مراجعتك' in page.inner_text('[data-gl-ok]'), 'النجاح بعد الأخطاء')

            # ——— ٥) فخّ الروبوتات الممتلئ: نجاح ظاهري بلا أي طلب
            page.reload()
            page.click('summary.gl-sum')
            queue(page)
            fill(page, verdict='confirm')
            page.evaluate("() => { document.querySelector('input[name=website]').value = 'http://spam.example'; }")
            submit(page)
            expect(calls(page) == [], 'فخّ الروبوتات الممتلئ أرسل طلبًا')

            # ——— ٦) المؤكّد باسم وبلا اسم، وبلا تمرير أفقي
            page.goto('https://elprofessor.net/glossary/breach.html')
            t = page.inner_text('main')
            expect('راجعه: أ. سلمى الحسيني، محكّمة' in t and 'تحت التأكيد' not in t and 'في البلاد العربية' in t and page.is_visible('summary.gl-sum'),
                   'مؤكّد باسم: %r' % t[:300])
            page.goto('https://elprofessor.net/glossary/waiver.html')
            t = page.inner_text('main')
            expect('راجعه متخصص' in t and 'راجعه:' not in t and 'تحت التأكيد' not in t, 'مؤكّد بلا اسم: %r' % t[:300])

            # ——— ٧) الفهرس: علامات وتصفية وعدّادات
            page.goto('https://elprofessor.net/glossary/')
            n_items = page.locator('.gl-list li').count()
            expect(n_items == 3 and page.locator('.gl-l-st.is-c').count() == 2 and page.locator('.gl-l-st.is-w').count() == 1, 'علامات الفهرس')
            expect(page.is_visible('[data-gl-filter]') and page.locator('[data-gl-f]').count() == 3, 'أزرار التصفية لا تظهر مع JS')
            small = page.evaluate("() => [...document.querySelectorAll('[data-gl-f]')].map(b => Math.round(b.getBoundingClientRect().height)).filter(h => h < 44)")
            expect(not small, 'أزرار التصفية أقل من ٤٤px')
            page.click('[data-gl-f=confirmed]')
            vis = page.evaluate("() => [...document.querySelectorAll('.gl-list li')].filter(l => l.offsetParent).map(l => l.dataset.st)")
            secs = page.evaluate("() => [...document.querySelectorAll('.gl-sec')].filter(s => s.offsetParent).map(s => [s.id, s.querySelector('h2 span').textContent])")
            expect(vis == ['confirmed', 'confirmed'] and sorted(s[1] for s in secs) == ['١', '١'], 'تصفية «مؤكّد»: %r %r' % (vis, secs))
            expect(page.get_attribute('[data-gl-f=confirmed]', 'aria-pressed') == 'true' and page.get_attribute('[data-gl-f=all]', 'aria-pressed') == 'false', 'aria-pressed')
            page.click('[data-gl-f=under_review]')
            vis = page.evaluate("() => [...document.querySelectorAll('.gl-list li')].filter(l => l.offsetParent).map(l => l.dataset.st)")
            secs = page.evaluate("() => [...document.querySelectorAll('.gl-sec')].filter(s => s.offsetParent).map(s => s.id)")
            expect(vis == ['under_review'] and secs == ['area-contracts'], 'تصفية «تحت التأكيد»: %r %r' % (vis, secs))
            page.click('[data-gl-f=all]')
            expect(page.evaluate("[...document.querySelectorAll('.gl-list li')].filter(l => l.offsetParent).length") == 3, 'الكل لا يعيد الجميع')
            expect(page.evaluate('document.documentElement.scrollWidth') <= 391, 'تمرير أفقي في الفهرس')
            m.close()
            opened.pop().close()

            # ——— ٨) بلا JS: كل مصطلح ظاهر بعلامته، وبلا نموذج ولا أزرار تصفية، وبلا إرسال ممكن
            n = mk(viewport={'width': 390, 'height': 844}, java_script_enabled=False)
            n.route('**/*', lambda r, _rq, pg=pages: serve(r, pg))
            q = n.new_page()
            q.goto('https://elprofessor.net/glossary/')
            expect(q.locator('.gl-list li').count() == 3 and all(q.locator('.gl-list li').nth(i).is_visible() for i in range(3)), 'بلا JS: المصطلحات لا تظهر كلها')
            expect(not q.is_visible('[data-gl-filter]'), 'بلا JS: أزرار التصفية ظاهرة بلا فائدة')
            expect('تحت التأكيد' in q.inner_text('.gl-list') and 'مؤكّد' in q.inner_text('.gl-list'), 'بلا JS: العلامات غائبة')
            q.goto('https://elprofessor.net/glossary/offer.html')
            expect(not q.is_visible('.gl-review') and 'تحت التأكيد: نبحث عن متخصص' in q.inner_text('main'), 'بلا JS: النموذج ظاهر أو الشارة غائبة')
            n.close()
            opened.pop().close()

            # ——— ٩) القالب الخام (بلا مولّد): يرسم الحالة والنموذج من فيد وهمي ويرسل بالجسم نفسه
            w = mk(viewport={'width': 1280, 'height': 900})
            w.add_init_script(FAKE_FETCH % (json.dumps({'terms': TERMS, 'areas': AREAS}), json.dumps(FEED_URL)))
            w.route('**/*', lambda r, _rq, pg=pages: serve(r, pg))
            r = w.new_page()
            r.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت (خام): %s' % e))
            r.goto('https://elprofessor.net/glossary-term.html?slug=offer')
            r.wait_for_selector('.gl-rev')
            expect('تحت التأكيد: نبحث عن متخصص' in r.inner_text('main') and r.is_visible('summary.gl-sum'), 'القالب الخام لا يرسم الحالة والنموذج')
            r.click('summary.gl-sum')
            queue(r, {'status': 201, 'json': {'ok': True}})
            fill(r, verdict='confirm', show=True)
            submit(r)
            c = calls(r)
            expect(len(c) == 1 and json.loads(c[0]['body'])['ref'] == 'offer' and json.loads(c[0]['body'])['show_name'] is True, 'القالب الخام: الجسم %r' % (c and c[0]['body']))
            expect(r.evaluate('document.documentElement.scrollWidth') <= 1281, 'تمرير أفقي على الكمبيوتر')
            w.close()
            opened.pop().close()
    return 0


if __name__ == '__main__':
    rc = run(None)
    if rc == 77:
        sys.exit(77)
    leaked = {k: v for k, v in BLOCKED.items() if 'dashboard.elprofessor.net' in k}
    if leaked:
        PROBLEMS.append('طلب وصل لمضيف الداشبورد عبر الشبكة: %r' % leaked)
    print(json.dumps({'problems': PROBLEMS, 'blocked_requests': BLOCKED}, ensure_ascii=False, indent=1))
    sys.exit(1 if PROBLEMS else 0)
