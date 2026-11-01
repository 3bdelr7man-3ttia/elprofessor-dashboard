# -*- coding: utf-8 -*-
"""لقطات صفحات «القاموس» على الموقع (docs/v2/glossary/SPEC.md) — كمبيوتر ١٤٤٠ (`d-s*`) وموبايل ٤٣٠ (`m-s*`).

    cd backend && python3 -B tests/uiharness/glossary_site_shots.py ../docs/v2/glossary/shots [/path/to/site-checkout]

الخطوات: نسخة مؤقتة من ريبو الموقع (بلا .git ولا فيديو) ⇐ فيد قاموس محلي من البذرة (٨٠ مصطلحًا بحالات المراجعة الجديدة) وفيد مقالات من ٦٢ مقالًا ⇐
`prerender.py` بسطر الأوامر (لا شبكة) ⇐ صفحات حقيقية مولَّدة ⇐ playwright يفتحها من الملفات بمسار `https://elprofessor.net/...` يخدمه المسار المحلي،
وأي أصل آخر `route.abort()` ويُسجَّل. `window.fetch` مبدَّلة قبل أي سكربت فلا يخرج نموذج المراجعة إلى الشبكة (يسجّل الجسم ويردّ ٢٠١).
  s01 مصطلح «تحت التأكيد» والنموذج مغلق (الفسخ) · s02 المصطلح نفسه والنموذج مفتوح وفيه أخطاء التحقق · s03 رسالة النجاح بعد إرسال سليم ·
  s04 مصطلح مؤكَّد باسم المراجع ومعه نقاش الساحة (القوة القاهرة) · s05 مؤكَّد بلا اسم معلن · s06 الفهرس بالعلامات وأزرار التصفية.

السكربت بيفشل (exit 1) لو: خروج المولّد ≠ ٠ أو حالة القاموس ≠ ok · صفحة ناقصة · الشارة أو «راجعه» أو النموذج أو النقاش في غير مكانه · هدف أقل من ٤٤px · خانة أقل من ١٦px ·
تمرير أفقي · عنصر يخرج من العرض · رقم لاتيني في نص عربي · «·» ملاصقة لرقم · كلمة ممنوعة · لون أصفر · طلب خرج لغير الموقع المحلي بغير ما هو معروف ·
جسم الإرسال ليس ما كتبه الزائر · JSON-LD لا يُقرأ أو ليس DefinedTerm.
⛔ صفر شبكة حقيقية: كل شيء من الديسك.
"""
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import urlparse, unquote

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(os.path.dirname(_HERE))
PRERENDER = os.path.join(BACKEND, 'prerender.py')
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(os.path.dirname(BACKEND), 'docs', 'v2', 'glossary', 'shots')
SITE = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else '/Users/abdelrhman/elprofessor-site/.worktrees/glossary')
SEED = os.path.join(BACKEND, 'data', 'glossary_seed.json')
HOST = 'elprofessor.net'
PROBLEMS = []
SHOTS = []
BLOCKED = {}
AREAS = [('contracts', 'عقود'), ('litigation', 'تقاضٍ'), ('corporate', 'شركات'), ('general', 'عام'), ('arbitration', 'تحكيم'),
         ('criminal', 'جنائي'), ('ip', 'ملكية فكرية'), ('labor', 'عمل'), ('family', 'أسرة'), ('other', 'أخرى')]
TOPIC = 'c0ffee00-1111-4222-8333-444455556666'
UNDER = 'rescission'                  # تحت التأكيد، بلا نقاش ولا فرنسي (s01 إلى s03)
CONF_ANON = 'consideration'             # مؤكَّد بلا اسم معلن (s05)
ENDPOINT = 'https://dashboard.elprofessor.net/api/public/expert-reviews'
BADGE = 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح'
SHOTS_SPEC = (('s01', UNDER + '.html', 'under-review-closed'), ('s02', UNDER + '.html', 'form-errors'), ('s03', UNDER + '.html', 'form-success'),
              ('s04', 'force-majeure.html', 'confirmed-named'), ('s05', CONF_ANON + '.html', 'confirmed-anonymous'), ('s06', '', 'index'))
FAKE_FETCH = """
window.__calls = [];
window.fetch = function (url, init) {
  window.__calls.push({url: String(url), method: init && init.method, credentials: init && init.credentials, body: init && init.body});
  return Promise.resolve({status: 201, ok: true, json: function () { return Promise.resolve({ok: true}); }});
};
"""
BANNED = ('يقوّم', 'API', 'JSON', 'Claude', 'DeepSeek', 'Anthropic', 'endpoint', 'token', 'undefined', 'null', 'NaN', 'slug', 'draft')


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def build_feeds(tmp):
    seed = json.load(open(SEED, encoding='utf-8'))['items']
    by = {i['id']: i for i in seed}
    label = dict(AREAS)
    terms = []
    for n, i in enumerate(seed):
        # كل ثالث مصطلح مؤكَّد؛ والباقي «تحت التأكيد». المؤكَّد باسم معلن إلا كل ثالث مؤكَّد (يبقى «راجعه متخصص»).
        rev = (n % 3 == 0) or i['id'] == 'force-majeure'
        if i['id'] == UNDER:
            rev = False
        public = rev and (i['id'] == 'force-majeure' or n % 9 != 0)
        if i['id'] == CONF_ANON:
            public = False
        t = {'id': n + 1, 'slug': i['id'], 'ar': i['ar'], 'en': i['en'], 'fr': i.get('fr') or None, 'area': i['area'], 'area_label': label[i['area']],
             'definition_ar': i['definition_ar'], 'example_en': i.get('example_en') or None, 'example_ar': i.get('example_ar') or None,
             'false_friend_note_ar': i.get('false_friend_note_ar') or None,
             'countries_note_ar': (i.get('countries_note_ar') or None) if rev else None,       # يحجبها الخادم لغير المؤكَّد
             'related': [{'slug': r, 'ar': by[r]['ar'], 'en': by[r]['en']} for r in i.get('related', []) if r in by and r != i['id']],
             'review_state': 'confirmed' if rev else 'under_review',
             'reviewed_by_name': 'أ. هبة الجندي' if public else None, 'reviewed_by_role': 'محامية' if public else None,   # لا اسم إلا مؤكَّدًا وبموافقة
             'reviewed_at': '2026-11-01T10:00:00' if rev else None,
             'saha_topic_id': TOPIC if i['id'] == 'force-majeure' else None,
             'published_at': '2026-11-01T10:05:00', 'updated_at': '2026-11-01T10:05:00'}
        terms.append(t)
    gf = os.path.join(tmp, '_glossary.json')
    json.dump({'source': 'dashboard', 'areas': [{'code': c, 'label': l} for c, l in AREAS], 'terms': terms}, open(gf, 'w', encoding='utf-8'), ensure_ascii=False)
    arts = []
    for n in range(1, 63):                        # فهرس المدوّنة يرفض فيدًا قصيرًا، فنولّد ٦٢ مقالًا تجريبيًّا
        title = 'مقال تجريبي لفيد المقالات رقم %d' % n
        body = ['## ' + title, 'نص تجريبي يكفي لمرور التحقق. ' * 20, 'فقرة ثانية تجريبية. ' * 20]
        arts.append({'id': n, 'slug': 'sample-%d' % n, 'title': title, 'excerpt': 'مقال تجريبي لفحص التوليد ' * 5, 'cat': 'دليل', 'kicker': 'دليل', 'date': '١ أكتوبر ٢٠٢٦',
                     'by': 'فريق منصة البروفيسور', 'tone': None, 'video': None, 'image_url': None, 'body': body, 'meta_description': 'مقال تجريبي.', 'keywords': [], 'faq': [],
                     'target_audience': 'عام', 'status': 'published', 'published_at': '2026-09-%02dT00:00:00' % (1 + n % 28), 'updated_at': None, 'content_hash': None,
                     'primary_kw': None, 'cluster_id': None, 'role': None, 'parent_id': None, 'topic_slug': None, 'topic_label': None})
    af = os.path.join(tmp, '_articles.json')
    json.dump({'source': 'dashboard', 'articles': arts, 'topics': []}, open(af, 'w', encoding='utf-8'), ensure_ascii=False)
    return af, gf, terms


def copy_site(tmp):
    dst = os.path.join(tmp, 'site')
    shutil.copytree(SITE, dst, ignore=shutil.ignore_patterns('.git', '.worktrees', '*.mp4', '*.webm', 'node_modules', 'tools'))
    return dst


def serve(route, site):
    """يخدم https://elprofessor.net/... من الديسك فقط؛ أي أصل آخر يُجهَض ويُعدّ."""
    u = urlparse(route.request.url)
    if u.hostname != HOST:
        BLOCKED[u.hostname or u.scheme] = BLOCKED.get(u.hostname or u.scheme, 0) + 1
        return route.abort()
    p = unquote(u.path)
    if p.endswith('/'):
        p += 'index.html'
    f = os.path.normpath(os.path.join(site, p.lstrip('/')))
    if not f.startswith(site) or not os.path.isfile(f):
        BLOCKED['local-404:' + p] = BLOCKED.get('local-404:' + p, 0) + 1
        return route.fulfill(status=404, body='not found')
    ctype = mimetypes.guess_type(f)[0] or 'application/octet-stream'
    return route.fulfill(status=200, body=open(f, 'rb').read(), content_type=ctype + ('; charset=utf-8' if ctype.startswith('text') or 'javascript' in ctype else ''))


SCOPE_JS = """() => { const c = document.body.cloneNode(true);
  c.querySelectorAll('[dir="ltr"], [lang="en"], [lang="fr"], script, style, noscript, svg, .gl-lang, .gl-ex-en').forEach(n => n.remove()); return c.innerText; }"""


def check_page(page, name, viewport_w):
    small = page.evaluate("""() => [...document.querySelectorAll('main a, main button, main summary, header a, header button, footer a, footer button, .ep-consent button, #epConsent button, [class*="consent"] button, [class*="cookie"] button')]
      .filter(b => b.offsetParent && getComputedStyle(b).visibility !== 'hidden')
      .map(b => [(b.className || b.tagName).toString().slice(0, 28), (b.textContent || '').trim().slice(0, 18), Math.round(b.getBoundingClientRect().height)]).filter(x => x[2] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:6]))
    # فخّ الروبوتات (name=website) مخفي بالقصّ فلا يدخل في فحص الخط
    boxes = page.evaluate("() => [...document.querySelectorAll('input:not([type=checkbox]):not([type=radio]):not([name=website]), select, textarea')].filter(b => b.offsetParent).map(b => [b.id || b.className, parseFloat(getComputedStyle(b).fontSize)])")
    for ident, fs in boxes:
        if fs < 16:
            PROBLEMS.append('%s: خانة %s خطها %s أقل من ١٦' % (name, ident, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
    if sw > viewport_w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, sw, viewport_w))
    wide = page.evaluate("() => [...document.querySelectorAll('body *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed' && !e.closest('video')).map(e => (e.className || e.tagName).toString().slice(0, 30)).slice(0, 5)")
    if wide:
        PROBLEMS.append('%s: عناصر تخرج من العرض %r' % (name, wide))
    txt = page.evaluate(SCOPE_JS)
    bad = [t for t in re.findall(r'\S*[0-9]\S*', txt) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية في نص عربي: %r' % (name, bad[:4]))
    if re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', txt):
        PROBLEMS.append('%s: «·» ملاصقة لرقم' % name)
    for word in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    yellow = page.evaluate("""() => { const out = new Set(); const hue = (c) => { const m = c.match(/rgba?\\((\\d+), (\\d+), (\\d+)(?:, ([\\d.]+))?\\)/); if (!m) return null; if (m[4] !== undefined && +m[4] < 0.3) return null;
        const r = m[1] / 255, g = m[2] / 255, b = m[3] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn; if (d < 0.25 || mx < 0.5) return null;
        let h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4; h = (h * 60 + 360) % 360; return h; };
      document.querySelectorAll('body *').forEach(e => { if (!e.offsetParent) return; const s = getComputedStyle(e); for (const k of ['color', 'backgroundColor', 'borderTopColor']) { const h = hue(s[k]); if (h !== null && h >= 42 && h <= 65) out.add(e.tagName + '.' + (e.className || '') + ':' + k + ':' + s[k]); } }); return [...out].slice(0, 5); }""")
    if yellow:
        PROBLEMS.append('%s: لون أصفر %r' % (name, yellow))
    ld = page.evaluate("() => [...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent)")
    types = []
    for raw in ld:
        try:
            j = json.loads(raw)
            for node in (j if isinstance(j, list) else j.get('@graph', [j])):
                types.append(node.get('@type'))
        except Exception as e:  # noqa: BLE001
            PROBLEMS.append('%s: JSON-LD لا يُقرأ %s' % (name, e))
    return types


def main():
    from playwright.sync_api import sync_playwright
    os.makedirs(OUT, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        af, gf, terms = build_feeds(tmp)
        site = copy_site(tmp)
        before = {p for p in os.listdir(SITE)}
        proc = subprocess.run(['python3', '-B', PRERENDER, '--site', site, '--feed-file', af, '--glossary-feed-file', gf, '--min-articles', '1'],
                              capture_output=True, text=True, timeout=600)
        lines = proc.stdout.strip().splitlines()
        info = {'exit': proc.returncode, 'glossary_line': lines[-1] if lines else None}
        expect(proc.returncode == 0, 'المولّد خرج %s: %s' % (proc.returncode, proc.stderr[-600:]))
        gl = json.loads(lines[-1]).get('glossary', {}) if lines else {}
        expect(gl.get('state') == 'ok', 'حالة القاموس %r' % gl)
        expect(not os.path.exists(os.path.join(SITE, 'glossary')), 'المولّد كتب في ريبو الموقع نفسه')
        expect(before == set(os.listdir(SITE)), 'تغيّر محتوى ريبو الموقع')
        if PROBLEMS:                                  # لا لقطات من صفحات لم تُولَّد
            print(json.dumps({'problems': PROBLEMS}, ensure_ascii=False, indent=1))
            sys.exit(1)
        gdir = os.path.join(site, 'glossary')
        files = sorted(os.listdir(gdir)) if os.path.isdir(gdir) else []
        expect(len(files) == 81 and 'index.html' in files, 'عدد ملفات القاموس %d (المتوقع ٨١)' % len(files))
        expect(all(re.match(r'^[a-z0-9.-]+$', f) for f in files), 'اسم غير ASCII')
        info['files'] = len(files)
        with sync_playwright() as p:
            for pre, w, h, mobile in (('d-', 1440, 900, False), ('m-', 430, 932, True)):
                browser = p.chromium.launch(args=['--single-process'])        # نفس إطلاق v2_shots: السياق الواحد لكل متصفح
                try:
                    ctx = browser.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile, locale='ar')
                    ctx.route('**/*', lambda r, _rq, s=site: serve(r, s))
                    ctx.add_init_script("try { localStorage.setItem('ep_consent', 'no'); } catch (e) {}\n" + FAKE_FETCH)
                    page = ctx.new_page()
                    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
                    page.on('dialog', lambda d: (PROBLEMS.append('نافذة منبثقة: %s' % d.message[:60]), d.dismiss()))
                    for code, slug, kind in SHOTS_SPEC:
                        name = pre + code
                        page.goto('https://%s/glossary/%s' % (HOST, slug), wait_until='load')
                        page.wait_for_timeout(700)
                        body = page.inner_text('main')
                        kinds = {'s01', 's02', 's03'}
                        if code in kinds:
                            # تحت التأكيد: الشارة مرة واحدة، لا «راجعه»، لا ملاحظة بلاد، زر المراجعة موجود
                            expect(body.count(BADGE) == 1 and 'راجعه' not in body and 'في البلاد العربية' not in body, name + ': شارة تحت التأكيد أو تسرّب مراجع')
                            expect(page.is_visible('summary.gl-sum') and 'أنت متخصص؟ راجِع هذا المصطلح' in body, name + ': زر المراجعة غائب')
                            expect(page.locator('[lang="fr"]').count() == 0 and 'ناقشه في الساحة' not in body, name + ': ظهر ما يجب أن يغيب')
                        if code == 's01':
                            expect(not page.is_visible('#glr-name'), name + ': النموذج مفتوح والمفروض مغلق')
                        if code in ('s02', 's03'):
                            page.click('summary.gl-sum')
                            page.wait_for_timeout(150)
                            expect(page.is_visible('#glr-name'), name + ': النموذج لم يُفتح')
                        if code == 's02':
                            page.fill('#glr-email', 'ليس-بريدا')
                            page.click('form[data-gl-review] button[type=submit]')
                            page.wait_for_timeout(200)
                            err = page.evaluate("() => { const e = document.querySelector('[data-gl-err]'); return e.hidden ? '' : e.textContent; }")
                            expect(err and 'name' not in err and not page.evaluate('window.__calls.length'), name + ': لا رسالة تحقق أو خرج طلب %r' % err)
                        if code == 's03':
                            page.fill('#glr-name', 'سلمى أحمد')
                            page.fill('#glr-email', 'salma@example.org')
                            page.select_option('#glr-spec', 'other')
                            page.fill('#glr-other', 'تحكيم دولي')
                            page.check('input[name=verdict][value=suggest]')
                            page.fill('#glr-text', 'أقترح إضافة مثال عن عقد توريد.')
                            page.check('input[name=show_name]')
                            page.click('form[data-gl-review] button[type=submit]')
                            page.wait_for_timeout(300)
                            calls = page.evaluate('window.__calls')
                            sent = json.loads(calls[0]['body']) if len(calls) == 1 else {}
                            expect(len(calls) == 1 and calls[0]['url'] == ENDPOINT and sent.get('kind') == 'glossary_term' and sent.get('ref') == slug[:-5]
                                   and sent.get('verdict') == 'suggest' and sent.get('specialty') == 'other' and sent.get('specialty_other') == 'تحكيم دولي'
                                   and sent.get('show_name') is True and sent.get('website') == '' and sent.get('email') == 'salma@example.org', name + ': جسم الإرسال %r' % calls)
                            ok = page.inner_text('[data-gl-ok]')
                            expect(ok == 'وصلت مراجعتك، شكرًا لك. سنراجعها ونتواصل معك.' and not page.is_visible('#glr-name'), name + ': رسالة النجاح %r' % ok)
                        if code == 's04':
                            expect('راجعه: أ. هبة الجندي، محامية' in body and BADGE not in body and 'ناقشه في الساحة' in body and 'في البلاد العربية' in body, name + ': مؤكَّد باسم ناقص')
                            expect(page.locator('a[href="https://app.elprofessor.net/?page=saha&topic=%s"]' % TOPIC).count() == 1, name + ': رابط الساحة')
                            expect(page.locator('[lang="fr"]').count() >= 1 and page.is_visible('summary.gl-sum'), name + ': الفرنسي أو زر المراجعة')
                        if code == 's05':
                            expect('راجعه متخصص' in body and 'راجعه:' not in body and 'هبة' not in body and BADGE not in body, name + ': مؤكَّد بلا اسم، تسرّب اسم أو شارة')
                        types = check_page(page, name, w)
                        if code != 's06':
                            expect('DefinedTerm' in types, name + ': JSON-LD DefinedTerm %r' % types)
                        else:
                            expect(page.locator('a[href^="/glossary/"]').count() >= 80 and page.locator('input[type=search], input[type=text]').count() == 0, name + ': روابط الفهرس أو خانة بحث')
                            n_conf = sum(1 for t in terms if t['review_state'] == 'confirmed')
                            n_all = len(terms)
                            marks = page.evaluate("() => [...document.querySelectorAll('.gl-list li')].map(li => li.dataset.st)")
                            expect(len(marks) == n_all and marks.count('confirmed') == n_conf, name + ': علامات الفهرس %d/%d' % (marks.count('confirmed'), len(marks)))
                            expect(page.locator('[data-gl-f]').count() == 3 and page.is_visible('[data-gl-filter]'), name + ': أزرار التصفية')
                            page.click('[data-gl-f=under_review]')
                            page.wait_for_timeout(200)
                            shown = page.evaluate("() => [...document.querySelectorAll('.gl-list li')].filter(li => li.offsetParent).map(li => li.dataset.st)")
                            expect(shown and set(shown) == {'under_review'} and len(shown) == n_all - n_conf, name + ': التصفية تحت التأكيد %d' % len(shown))
                            page.click('[data-gl-f=all]')
                            page.wait_for_timeout(200)
                        expect(page.evaluate('window.EP_PRERENDERED') is True, name + ': الصفحة ليست مُسبقة العرض')
                        canon = page.evaluate("() => (document.querySelector('link[rel=canonical]') || {}).href")
                        expect(canon and canon.startswith('https://elprofessor.net/glossary/'), name + ': canonical %r' % canon)
                        expect(page.evaluate("() => (document.querySelector('meta[name=description]') || {content: ''}).content.length") > 20, name + ': meta description')
                        stray = [c for c in page.evaluate('window.__calls') if c['url'] != ENDPOINT]
                        expect(not stray, name + ': طلب خارج نقطة المراجعة %r' % stray)
                        fn = os.path.join(OUT, name + '-' + kind + '.png')
                        page.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, 0); }")          # الترويسة الثابتة لا تظهر وسط اللقطة الكاملة
                        page.wait_for_timeout(700)
                        page.screenshot(path=fn, full_page=code != 's06')
                        SHOTS.append(os.path.basename(fn))
                    page.close()
                    ctx.close()
                finally:
                    browser.close()
        info['shots'] = SHOTS
    info['blocked'] = BLOCKED
    info['problems'] = PROBLEMS
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
