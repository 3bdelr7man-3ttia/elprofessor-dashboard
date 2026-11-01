# -*- coding: utf-8 -*-
"""لقطات صفحات «القاموس» على الموقع (docs/v2/glossary/SPEC.md) — كمبيوتر ١٤٤٠ (`d-s*`) وموبايل ٤٣٠ (`m-s*`).

    cd backend && python3 -B tests/uiharness/glossary_site_shots.py ../docs/v2/glossary/shots [/path/to/site-checkout]

الخطوات: نسخة مؤقتة من ريبو الموقع (بلا .git ولا فيديو) ⇐ فيد قاموس محلي من البذرة (٨٠ مصطلحًا بشكل الإعداد المغلق: بلا أي مفتاح مراجعة، إلا أن كل ثالث مصطلح
يحمل مفاتيح المراجعة بقيم مؤكَّدة واسم مراجع لنثبت أنها تُتجاهل) وفيد مقالات من ٦٢ مقالًا ⇐ `prerender.py` بسطر الأوامر (لا شبكة) ⇐ صفحات حقيقية مولَّدة ⇐
playwright يفتحها من الملفات بمسار `https://elprofessor.net/...` يخدمه المسار المحلي، وأي أصل آخر `route.abort()` ويُسجَّل. `window.fetch` مبدَّلة قبل أي سكربت
وتسجّل كل نداء: صفحة القاموس لا تنادي شيئًا.
  s01 مصطلح بنقاش (يظهر «ناقشه في الساحة») ومعه ملاحظة بلاد · s02 مصطلح بلا نقاش ولا فرنسي ولا ملاحظة بلاد · s03 مصطلح بملاحظة بلاد بلا نقاش · s04 الفهرس بشرائح المجالات.
(قبل الجولة ٣ كانت s01 إلى s06 تُظهر شارة «تحت التأكيد» ونموذج المراجعة وعلامات الفهرس؛ نسخها محفوظة باسم `before-*`.)

السكربت بيفشل (exit 1) لو: خروج المولّد ≠ ٠ أو حالة القاموس ≠ ok · صفحة ناقصة · شارة أو «راجعه» أو «مؤكّد» أو نموذج أو خانة إدخال أو زر في المحتوى · اسم مراجع من الفيد على الصفحة ·
النقاش في غير مكانه · هدف أقل من ٤٤px · خانة أقل من ١٦px · تمرير أفقي · عنصر يخرج من العرض · رقم لاتيني في نص عربي · «·» ملاصقة لرقم · كلمة ممنوعة · لون أصفر ·
طلب خرج لغير الموقع المحلي · نداء fetch من الصفحة · JSON-LD لا يُقرأ أو ليس DefinedTerm.
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
WITH_TOPIC = 'force-majeure'          # بنقاش وفرنسي وملاحظة بلاد (s01)
NO_TOPIC = 'rescission'               # بلا نقاش ولا فرنسي ولا ملاحظة بلاد (s02)
WITH_NOTE = 'liquidated-damages'      # ملاحظة بلاد بلا نقاش (s03)
ENDPOINT_PART = 'expert-reviews'
REVIEWER = 'هبة الجندي'               # يحملها الفيد في مفاتيح المراجعة للتجاهل؛ يجب ألا تظهر في أي صفحة
SHOTS_SPEC = (('s01', WITH_TOPIC + '.html', 'topic'), ('s02', NO_TOPIC + '.html', 'no-topic'), ('s03', WITH_NOTE + '.html', 'country-note'), ('s04', '', 'index'))
FAKE_FETCH = """
window.__calls = [];
window.fetch = function (url, init) {
  window.__calls.push({url: String(url), method: init && init.method});
  return Promise.resolve({status: 404, ok: false, json: function () { return Promise.resolve({}); }});
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
        t = {'id': n + 1, 'slug': i['id'], 'ar': i['ar'], 'en': i['en'], 'fr': i.get('fr') or None, 'area': i['area'], 'area_label': label[i['area']],
             'definition_ar': i['definition_ar'], 'example_en': i.get('example_en') or None, 'example_ar': i.get('example_ar') or None,
             'false_friend_note_ar': i.get('false_friend_note_ar') or None,
             'countries_note_ar': (i.get('countries_note_ar') or None) if i['id'] != NO_TOPIC else None,       # تظهر متى وُجدت
             'related': [{'slug': r, 'ar': by[r]['ar'], 'en': by[r]['en']} for r in i.get('related', []) if r in by and r != i['id']],
             'saha_topic_id': TOPIC if i['id'] == WITH_TOPIC else None,
             'published_at': '2026-11-01T10:05:00', 'updated_at': '2026-11-01T10:05:00'}
        if n % 3 == 0 or i['id'] in (WITH_TOPIC, WITH_NOTE):          # شكل الإعداد المفتوح: مفاتيح المراجعة موجودة وتُتجاهل
            t.update({'review_state': 'confirmed', 'reviewed_by_name': 'أ. ' + REVIEWER, 'reviewed_by_role': 'محامية', 'reviewed_at': '2026-11-01T10:00:00'})
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
                        # كل الصفحات: لا شارة ولا «راجعه» ولا «مؤكّد» ولا زر مراجعة ولا نموذج ولا خانة إدخال ولا اسم مراجع من الفيد
                        for word in ('تحت التأكيد', 'راجعه', 'مؤكّد', 'أنت متخصص', 'تصفية'):
                            expect(word not in body, name + ': ظهرت كلمة «%s»' % word)
                        expect(REVIEWER not in page.content() and ENDPOINT_PART not in page.content(), name + ': اسم مراجع أو نقطة إرسال المراجعة في الصفحة')
                        expect(page.locator('main form, main input, main select, main textarea, main summary, main details').count() == 0, name + ': نموذج أو خانة في المحتوى')
                        if code != 's04':
                            expect(page.locator('main button').count() == 0 and page.locator('[data-st], .gl-l-st, .gl-rev, .gl-review').count() == 0, name + ': زر أو علامة حالة في الصفحة')
                        if code == 's01':
                            expect('ناقشه في الساحة' in body and page.locator('a[href="https://app.elprofessor.net/?page=saha&topic=%s"]' % TOPIC).count() == 1, name + ': رابط الساحة')
                            expect(page.locator('[lang="fr"]').count() >= 1 and 'في البلاد العربية' in body, name + ': الفرنسي أو ملاحظة البلاد')
                        if code == 's02':
                            expect('ناقشه في الساحة' not in body and page.locator('a[href*="page=saha"]').count() == 0, name + ': رابط الساحة على مصطلح بلا نقاش')
                            expect(page.locator('[lang="fr"]').count() == 0 and 'في البلاد العربية' not in body, name + ': فرنسي أو ملاحظة بلاد على مصطلح بلا ما يبررهما')
                        if code == 's03':
                            expect('في البلاد العربية' in body and 'ناقشه في الساحة' not in body, name + ': ملاحظة البلاد غائبة أو ظهر رابط نقاش')
                        if code in ('s01', 's02', 's03'):
                            expect(page.locator('a[href="https://app.elprofessor.net/?page=chat"]').count() == 1, name + ': «اسأل خبيرًا»')
                        types = check_page(page, name, w)
                        if code != 's04':
                            expect('DefinedTerm' in types, name + ': JSON-LD DefinedTerm %r' % types)
                        else:
                            n_areas = len({t['area'] for t in terms})
                            expect(page.locator('a[href^="/glossary/"]').count() >= 80 and page.locator('input[type=search], input[type=text]').count() == 0, name + ': روابط الفهرس أو خانة بحث')
                            expect(page.locator('.gl-areas a.chip').count() == n_areas and page.locator('main button, [data-gl-f], [data-gl-filter]').count() == 0, name + ': شرائح المجالات (%d) أو زر تصفية' % n_areas)
                            expect(page.locator('.gl-list li').count() == len(terms) and page.locator('[data-st], .gl-l-st').count() == 0, name + ': عناصر الفهرس أو علامة حالة')
                            # شريحة المجال تنقل إلى قسمه
                            page.click('.gl-areas a.chip >> nth=0')
                            page.wait_for_timeout(200)
                            expect(page.evaluate("() => location.hash.indexOf('#area-') === 0"), name + ': شريحة المجال لا تنقل إلى قسمها')
                        expect(page.evaluate('window.EP_PRERENDERED') is True, name + ': الصفحة ليست مُسبقة العرض')
                        canon = page.evaluate("() => (document.querySelector('link[rel=canonical]') || {}).href")
                        expect(canon and canon.startswith('https://elprofessor.net/glossary/'), name + ': canonical %r' % canon)
                        expect(page.evaluate("() => (document.querySelector('meta[name=description]') || {content: ''}).content.length") > 20, name + ': meta description')
                        calls = page.evaluate('window.__calls')
                        expect(not calls, name + ': الصفحة نادت fetch %r' % calls)
                        fn = os.path.join(OUT, name + '-' + kind + '.png')
                        page.evaluate("() => { document.documentElement.style.scrollBehavior = 'auto'; window.scrollTo(0, 0); }")          # الترويسة الثابتة لا تظهر وسط اللقطة الكاملة
                        page.wait_for_timeout(700)
                        page.screenshot(path=fn, full_page=code != 's04')
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
