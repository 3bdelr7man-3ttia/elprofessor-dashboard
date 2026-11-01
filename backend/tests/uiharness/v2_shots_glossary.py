# -*- coding: utf-8 -*-
"""لقطات وفحوص تبويب «القاموس» (docs/v2/glossary/SPEC.md) — كمبيوتر ١٤٤٠ (`d*`) وموبايل ٤٣٠ (`m*`).

    cd backend && python3 -B tests/uiharness/v2_shots_glossary.py ../docs/v2/glossary/shots [only-prefix,...]

الخطوات: ٠١ المربّعات · ٠٢ القائمة (بحث · مجال · حالة · مراجعة) · ٠٣ شاشة مصطلح منشور مُراجَع · ٠٤ مصطلح بلا ختم (النشر معطّل وسببه) · ٠٥ «راجعه» ثم النشر ·
٠٦ تعديل منشور مُراجَع (تحذير الختم والرجوع مسودة · قريبة بالإضافة والحذف) · ٠٧ مصطلح جديد (رابط يُشتق · «أخرى» · رابط مكرر) · ٠٨ نقاش الساحة (ربط وفصل) ·
٠٩ حذف مسودة · ١٠ الاستيراد (الأساسي · المرشّحة · ملف) · ١١ شرط المراجعة (إغلاقه وأثره ثم إعادته) · ١٢ مصدر واقع وحالات فاضية وجسر النقاشات غايب · ١٣ المفتاح مقفول ·
١٤ الوضع الافتراضي (الشرط مغلق): نشر بلا ختم ⇒ «تحت التأكيد» ⇒ ختم مع موافقة ظهور الاسم ⇒ تعديل يعيده «تحت التأكيد» · ١٥ «مراجعات القاموس»: اعتمد تأكيدًا ·
اعتمد اقتراحًا (يفتح المحرّر ومعه الاقتراح) · تمّ لدورة · ارفض بملاحظة وبلا · تنبيه تغيّر المصطلح · حالات فاضية.
(١ إلى ١٣ تعمل والشرط مفعّل صراحةً كي تثبت قاعدة المنع، و١٤ و١٥ بالافتراضي المغلق.)
الجولة ٣ (قرار المؤسس ٢٠٢٦-١١-٠١، «نفتحه للنقاش ونلمّ الاعتراضات»): الخطوات ٠١ إلى ١٥ تُصوَّر والإعداد `glossary.expert_reviews_enabled` **مفعّل** (شكل الجولة ٢ كما كان،
وصندوق المراجعات وشرط المراجعة يظهران فيه فقط)؛ و١٦ إلى ١٨ بالافتراضي الجديد (مطفأ): ١٦ شاشات «مسودة / منشور» بلا مراجعات (والختم داخلي) · ١٧ فتح نقاش لمصطلح واحد
(معاينة بلا كتابة ⇒ تأكيد · ربط بنقاش موجود · عنوان مكرر غير علني · مسودة) · ١٨ «نقاشات المصطلحات» دفعةً (تجربة ⇒ تأكيد ⇒ نتيجة لكل مصطلح).

السكربت بيفشل (exit 1) لو: «0/null/NaN/undefined» ظاهر · هدف أقل من ٤٤px · خانة أقل من ١٦px · تمرير أفقي · رقم لاتيني في نص عربي · «·» ملاصقة لرقم · كلمة ممنوعة ·
نافذة متصفح · كتابة وصلت الخادم قبل ضغطة التأكيد أو بلا `confirmed:true` بالضبط أو فيها `by` أو حقل خارج قائمة المسار · كتابة وصلت المنصة (المصطلح لا يكتب فيها) ·
حفظ في المتصفح · أي طلب خرج من العملية غير خطوط جوجل.
⛔ صفر طلبات حقيقية: الداشبورد وقاعدته جوه العملية، والمنصة بديل في الذاكرة بجسر النقاشات فقط (`glossary_fixtures.GlossaryPlatform`). التوليد (`_prerender_push_async`) متبدّل بمسجّل أسباب.
"""
import json
import os
import re
import sys
import tempfile
from urllib.parse import urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_shots as vs                         # noqa: E402  (يقرأ مجلد الخرج من sys.argv[1])
import glossary_fixtures as gfx               # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

PROBLEMS = vs.PROBLEMS
ONLY = [x for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else []) if x]
DESK = vs.DESK
MOB = {'width': 430, 'height': 932}
READY = ("() => window.V2SHELL && V2SHELL.on === true && document.querySelector('.v2s-sh[data-board]') && !document.querySelector('.v2s-sh .sh-skel')"
         " && !/…/.test((document.querySelector('.sh-tiles') || {innerText: ''}).innerText)")
BANNED = ('يقوّم', 'يقوم', 'API', 'JSON', 'Claude', 'DeepSeek', 'Anthropic', 'endpoint', 'token', 'bridge', 'dry_run', 'undefined', 'slug', 'draft', 'published')
G = r'^/api/v2/content/glossary'
TERM_FIELDS = {'slug', 'ar', 'en', 'fr', 'area', 'definition_ar', 'example_en', 'example_ar', 'false_friend_note_ar', 'countries_note_ar', 'related'}
OK_WRITES = [('POST', re.compile(G + r'$'), TERM_FIELDS), ('PUT', re.compile(G + r'/\d+$'), TERM_FIELDS), ('DELETE', re.compile(G + r'/\d+$'), set()),
             ('POST', re.compile(G + r'/\d+/(publish|unpublish|unreview|detach-topic)$'), set()),
             ('POST', re.compile(G + r'/\d+/review$'), {'reviewer_name', 'reviewer_role', 'reviewer_name_public'}),
             ('POST', re.compile(G + r'/reviews/\d+/approve$'), set()), ('POST', re.compile(G + r'/reviews/\d+/reject$'), {'admin_note'}),
             ('POST', re.compile(G + r'/\d+/attach-topic$'), {'saha_topic_id'}), ('PUT', re.compile(G + r'/settings$'), {'require_review', 'expert_reviews_enabled'}),
             ('POST', re.compile(G + r'/\d+/saha-topic/open$'), {'title', 'question'}), ('POST', re.compile(G + r'/saha-topics/bulk/open$'), set()),
             ('POST', re.compile(G + r'/seed/import$'), {'source', 'payload'})]
SCOPE_JS = """() => [...document.querySelectorAll('.v2s-sh, #epModal.v2s-sh-sh')].map(e => { const c = e.cloneNode(true);
  c.querySelectorAll('[dir="ltr"], [dir="auto"], .sh-who, script, style, input, textarea, select, option').forEach(n => n.remove()); return c.innerText; }).join('\\n')"""
PUSHES = []


def want(code):
    return not ONLY or any(code.startswith(o) for o in ONLY)


def expect(cond, msg):
    if not cond:
        PROBLEMS.append(msg)


def shcheck(page, name):
    w = page.viewport_size['width']
    small = page.evaluate("""() => [...document.querySelectorAll('.v2s-sh button, .v2s-sh a.sh-lnk, .v2s-sh select, .v2s-sh input:not([type=checkbox]):not([type=radio]):not([type=file]), #epModal.v2s-sh-sh button, #epModal.v2s-sh-sh a.sh-lnk, #epModal.v2s-sh-sh input:not([type=checkbox]):not([type=radio]), #epModal.v2s-sh-sh select, #epModal.v2s-sh-sh textarea, #epModal.v2s-sh-sh .sh-chk, #epModal.v2s-sh-sh summary')].filter(b => b.offsetParent && !b.closest('[hidden]') && !(b.closest('details') && !b.closest('details').open && b.tagName !== 'SUMMARY'))
      .map(b => [(b.className || b.id || b.tagName).toString().slice(0, 30), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    boxes = page.evaluate("""() => [...document.querySelectorAll('.v2s-sh input:not([type=checkbox]):not([type=radio]):not([type=file]), .v2s-sh select, #epModal.v2s-sh-sh input:not([type=checkbox]):not([type=radio]), #epModal.v2s-sh-sh textarea, #epModal.v2s-sh-sh select')].filter(b => b.offsetParent).map(b => [b.id || b.className, parseFloat(getComputedStyle(b).fontSize)])""")
    for ident, fs in boxes:
        if fs < 16:
            PROBLEMS.append('%s: خانة %s خطها %s أقل من ١٦' % (name, ident, fs))
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي في الصفحة (%s > %s)' % (name, sw, w))
    wide = page.evaluate("() => [...document.querySelectorAll('.v2s-sh *, #epModal.v2s-sh-sh *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(e).position !== 'fixed').length")
    if wide:
        PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    txt = page.evaluate(SCOPE_JS)
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt):
        PROBLEMS.append('%s: صفر/null/NaN ظاهر: %r' % (name, re.findall(r'.{0,10}(?<![\w@./-])(?:0|null|NaN|undefined)(?![\w@./-]).{0,10}', txt)[:2]))
    bad = [t for t in re.findall(r'\S*[0-9]\S*', txt) if '@' not in t]
    if bad:
        PROBLEMS.append('%s: أرقام لاتينية في نص عربي: %r' % (name, bad[:3]))
    if re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', txt):
        PROBLEMS.append('%s: «·» ملاصقة لرقم: %r' % (name, re.findall(r'.{0,8}[0-9٠-٩]\s*·.{0,8}|.{0,8}·\s*[0-9٠-٩].{0,8}', txt)[:2]))
    for word in BANNED:
        if re.search(r'(?<![A-Za-z])%s(?![A-Za-z])' % re.escape(word), txt):
            PROBLEMS.append('%s: كلمة ممنوعة ظاهرة «%s»' % (name, word))
    if re.search(r'#[0-9A-Fa-f]{6}\b|\bnull\b|Choose File|No file chosen', txt):
        PROBLEMS.append('%s: نص تقني أو زرّ ملفات أصلي ظاهر' % name)
    keys = page.evaluate("() => { try { return Object.keys(localStorage).concat(Object.keys(sessionStorage)).filter(k => /glossary|term|seed|review/i.test(k)); } catch (e) { return []; } }")
    if keys:
        PROBLEMS.append('%s: حفظ في المتصفح %r' % (name, keys))


def mshot(page, name, keep=True, focus=None):
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    if focus:                                  # لقطة عند عنصر تحت الطيّة (لوحة النقاش في آخر شاشة المصطلح)
        page.evaluate("s => { const e = document.querySelector(s); if (e) e.scrollIntoView({block: 'center'}); }", focus)
    page.wait_for_timeout(300)
    if keep:
        vs.shot(page, name, full=False)
    vs.shell_check(page, name)
    shcheck(page, name)


# ---------------------------------------------------------------- سجل الطلبات من المتصفح للداشبورد (الجسم والمسار)
def gwrites(page, since=0):
    out = []
    for m, p, body in page._glog[since:]:
        if m in ('POST', 'PUT', 'DELETE') and p.startswith('/api/v2/content/glossary') and not p.endswith('/preview'):
            out.append((m, p, json.loads(body) if body else None))
    return out


def check_writes(name, page, since, expected):
    got = gwrites(page, since)
    for m, p, body in got:
        rule = next((r for r in OK_WRITES if r[0] == m and r[1].match(p)), None)
        if rule is None:
            PROBLEMS.append('%s: كتابة غير مسموحة %s %s' % (name, m, p))
            continue
        if not isinstance(body, dict) or body.get('confirmed') is not True:
            PROBLEMS.append('%s: كتابة بلا confirmed:true بالضبط %s %s %r' % (name, m, p, body))
            continue
        if 'by' in body:
            PROBLEMS.append('%s: `by` في الجسم %s %s' % (name, m, p))
        extra = set(body) - rule[2] - {'confirmed'}
        if extra:
            PROBLEMS.append('%s: حقول خارج قائمة المسار %s %s %r' % (name, m, p, sorted(extra)))
    if len(got) != expected:
        PROBLEMS.append('%s: عدد الكتابات %d بدل %d: %r' % (name, len(got), expected, [(m, p) for m, p, _b in got]))
    return got


def platform_clean(name, h, base):
    bad = [(c[0], c[1]) for c in h.platform_calls[base:] if str(c[0]).upper() != 'GET']
    if bad:
        PROBLEMS.append('%s: كتابة وصلت المنصة والمصطلح لا يكتب فيها: %r' % (name, bad))


def sopen(browser, h, viewport, mobile, hash_='#s/content/glossary', rows=None, require=True, topics=None, down=(), pre_route=None, ready=READY, reviews=False, expert=True):
    gfx.seed_terms(h, rows, require, expert)
    if reviews:
        h.rv = gfx.seed_reviews(h)
    ef = gfx.GlossaryPlatform(topics)
    ef.down = set(down)
    h.ef = ef
    h.app._prerender_push_async = lambda reason='': PUSHES.append(reason)
    ctx = browser.context(h, 'admin', viewport, mobile)
    page = ctx.new_page()
    page._glog = []
    page.on('request', lambda r: page._glog.append((r.method, urlparse(r.url).path, r.post_data)) if urlparse(r.url).path.startswith('/api/') else None)
    page.set_default_timeout(20000)
    page.on('dialog', lambda d: (PROBLEMS.append('نافذة متصفح ظهرت: %s' % d.message[:60]), d.dismiss()))
    page.on('pageerror', lambda e: PROBLEMS.append('خطأ جافاسكربت: %s' % str(e)[:200]))
    page.on('console', lambda m: PROBLEMS.append('console.error: %s' % m.text[:200]) if m.type == 'error' and 'Failed to load resource' not in m.text else None)
    if pre_route:
        page.route(*pre_route)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(vs.SHELL_READY, timeout=30000)
    page.wait_for_function(ready, timeout=30000)
    page.wait_for_timeout(350)
    return page


def vis(sel):
    return sel + ' >> visible=true'


def click(page, sel, wait=300):
    page.locator(vis(sel)).first.click()
    page.wait_for_timeout(wait)


def go_sub(page, sub, head='.sh-head'):
    click(page, '.sh-tile[data-sub="%s"]' % sub, 500)
    page.wait_for_function("h => !document.querySelector('.v2s-sh .sh-skel') && document.querySelector(h)", arg=head, timeout=15000)
    page.wait_for_timeout(300)


def back_hub(page):
    click(page, '[data-a="hub"]', 400)
    page.wait_for_function("() => document.querySelector('.sh-tiles') && !/…/.test(document.querySelector('.sh-tiles').innerText)", timeout=15000)


def sheet_open(page):
    page.wait_for_selector('#epModal.v2s-sh-sh', timeout=10000)
    page.wait_for_timeout(250)


def sheet_gone(page):
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_timeout(450)


def confirm(page, wait=900):
    click(page, '#shGo', wait)


def tile_numbers(page):
    return {t[0]: (t[1], t[2]) for t in page.evaluate("() => [...document.querySelectorAll('.sh-tile')].map(t => [t.dataset.sub, t.querySelector('.sh-n').textContent.trim(), t.querySelector('small').textContent.trim()])")}


def wait_rows(page, n, sel='[data-id]'):
    page.wait_for_function("a => new Set([...document.querySelectorAll('.v2s-sh #gList ' + a[1])].filter(e => e.offsetParent).map(e => e.dataset.id)).size === a[0]", arg=[n, sel], timeout=12000)
    page.wait_for_timeout(200)


def note_text(page):
    return page.evaluate("() => (document.querySelector('.sh-note') || {textContent: ''}).textContent.trim()")


def err_text(page, sel='#shErr'):
    return page.evaluate("s => (document.querySelector(s) || {textContent: ''}).textContent.trim()", sel)


def sheet_text(page):
    return page.evaluate("() => (document.getElementById('epModal') || {innerText: ''}).innerText")


def view_text(page):
    return page.evaluate("() => (document.querySelector('.v2s-sh') || {innerText: ''}).innerText")


def tid(h, slug):
    return str(gfx.term(h, slug)['id'])


def open_term(page, h, slug):
    click(page, '[data-a="gopen"][data-id="%s"]' % tid(h, slug), 500)
    page.wait_for_function("() => document.querySelector('.g-ar')", timeout=10000)
    page.wait_for_timeout(300)


def term_screen(page, h, slug):
    """مباشرة من المربّعات إلى شاشة مصطلح: المصطلحات ⇒ افتح."""
    go_sub(page, 'terms')
    open_term(page, h, slug)


# ======================================================================= السيناريوهات
def flow_glossary(browser, h, pre, vp, mobile):
    # —— ٠١) المربّعات
    if want('01'):
        page = sopen(browser, h, vp, mobile)
        nums = tile_numbers(page)
        expect(nums.get('terms') == ('١٤', 'مؤكّد ١، تحت التأكيد ١، مسودة ١٢') and nums.get('wait') == ('١١', 'مصطلح ينتظر مراجعة خبير') and nums.get('import', ('',))[0] == 'استورد'
               and nums.get('reviews') == ('٠', 'لا مراجعات تنتظر') and nums.get('rules') == ('مطلوبة', 'مراجعة الخبير قبل النشر'), '%s01: أرقام المربّعات %r' % (pre, nums))
        tabs = page.evaluate("() => [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim())")
        expect('القاموس' in tabs and tabs.index('القاموس') == tabs.index('الديوان') + 1 and len(tabs) == 10, '%s01: تبويبات المحتوى %r' % (pre, tabs))
        imgs = page.evaluate("() => [...document.querySelectorAll('.sh-timg')].map(e => getComputedStyle(e).backgroundImage.replace(/.*\\//, ''))")
        expect(len(imgs) == 6 and all('.jpg' in i for i in imgs), '%s01: صور المربّعات %r' % (pre, imgs))
        order = page.evaluate("() => [...document.querySelectorAll('.sh-tile')].map(t => t.dataset.sub)")
        expect(order == ['terms', 'topics', 'wait', 'reviews', 'import', 'rules'] and nums.get('topics') == ('١', 'مصطلح منشور بلا نقاش في الساحة'), '%s01: ترتيب المربّعات ونقاشاتها %r %r' % (pre, order, nums.get('topics')))
        mshot(page, pre + '01-hub.jpg')
        browser.close()

    # —— ٠٢) القائمة
    if want('02'):
        page = sopen(browser, h, vp, mobile)
        go_sub(page, 'terms')
        wait_rows(page, 14)
        nums = page.evaluate("() => [...document.querySelectorAll('.sh-nums li')].map(l => l.innerText.replace(/\\s+/g, ' ').trim())")
        expect(nums == ['١ مؤكّد', '١ تحت التأكيد', '١٢ مسودة'], '%s02: عدّادات الرأس %r' % (pre, nums))
        chips = page.evaluate("() => [...document.querySelectorAll('[data-k=gst]')].map(b => b.textContent.trim())")
        expect(chips == ['الكل', 'مؤكّد', 'تحت التأكيد', 'مسودة'], '%s02: شرائح الحالة %r' % (pre, chips))
        areas = page.evaluate("() => [...document.querySelectorAll('[data-k=garea]')].map(b => b.textContent.trim())")
        expect(len(areas) == 11 and areas[0] == 'الكل' and areas[-1].startswith('أخرى') and areas[1].startswith('عقود (٥)'), '%s02: شرائح المجال %r' % (pre, areas))
        mshot(page, pre + '02-list.jpg')
        for q, n in (('قاهره', 1), ('ARBITRAL', 1), ('sentence', 1), ('هيئة', 1), ('hardship-clause', 1), ('zzzz', 0), ('', 14)):
            page.fill('#shQ', q)
            page.wait_for_timeout(350)
            if n:
                wait_rows(page, n)
            else:
                expect('لا مصطلحات تطابق بحثك' in view_text(page), '%s02: رسالة بلا نتائج' % pre)
        page.fill('#shQ', 'قاهرة')
        page.wait_for_timeout(350)
        wait_rows(page, 1)
        expect(page.input_value('#shQ') == 'قاهرة' and page.evaluate("() => document.activeElement.id") == 'shQ', '%s02: الكتابة في البحث لا تفقد التركيز' % pre)
        mshot(page, pre + '02b-search.jpg')
        page.fill('#shQ', '')
        page.wait_for_timeout(350)
        click(page, '[data-k="garea"][data-v="other"]', 400)
        wait_rows(page, 1)
        mshot(page, pre + '02d-area-other.jpg')
        click(page, '[data-k="garea"][data-v="contracts"]', 400)
        wait_rows(page, 5)
        click(page, '[data-k="garea"][data-v="all"]', 400)
        click(page, '[data-k="gst"][data-v="confirmed"]', 400)
        wait_rows(page, 1)
        click(page, '[data-k="gst"][data-v="under_review"]', 400)
        wait_rows(page, 1)
        expect(page.evaluate("() => document.querySelector('#gList .sh-t').textContent.trim()") == 'الأمر القضائي المؤقت', '%s02: تحت التأكيد' % pre)
        click(page, '[data-k="gst"][data-v="draft"]', 400)
        wait_rows(page, 12)
        click(page, '[data-k="gst"][data-v="all"]', 400)
        click(page, '[data-k="grev"][data-v="reviewed"]', 400)
        wait_rows(page, 3)
        click(page, '[data-k="grev"][data-v="unreviewed"]', 400)
        wait_rows(page, 11)
        mshot(page, pre + '02c-unreviewed.jpg', keep=False)
        browser.close()

    # —— ٠٣) شاشة مصطلح منشور مُراجَع
    if want('03'):
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'force-majeure')
        t = view_text(page)
        expect('القوة القاهرة' in t and 'راجعه: أ. هبة الجندي، محامية' in t and 'خطأ شائع' in t and 'ملاحظة الدول' in t and 'مؤكّد' in t, '%s03: محتوى الشاشة %r' % (pre, t[:200]))
        expect('على الموقع' in t and 'يظهر للناس' in t, '%s03: ما يظهر على الموقع وموافقة الاسم %r' % (pre, t[-400:]))
        expect('٣٠ يومًا' in t and '٥٠,٠٠٠' in t and '50,000' not in t, '%s03: المثال العربي بأرقام هندية' % pre)
        expect(page.evaluate("() => document.querySelectorAll('.g-lang').length") == 2 and page.inner_text('.g-lang >> nth=0').strip().startswith('EN'), '%s03: صفّا الإنجليزي والفرنسي' % pre)
        expect('30 days' in page.inner_text('.g-ex >> nth=0'), '%s03: المثال الإنجليزي يبقى لاتينيًا' % pre)
        prev = page.evaluate("() => [...document.querySelectorAll('.v2s-sh a.sh-lnk')].map(a => [a.textContent.trim(), a.getAttribute('href')])")
        expect(['معاينة صفحة المصطلح على الموقع', 'https://elprofessor.net/glossary/force-majeure.html'] in prev
               and ['فتح النقاش في الساحة', 'https://app.elprofessor.net/?page=saha&topic=' + gfx.TOPIC_PUB] in prev, '%s03: روابط المعاينة والنقاش %r' % (pre, prev))
        expect('متى تُعفي القوة القاهرة من التنفيذ؟' in t and 'افصل النقاش' in t, '%s03: عنوان النقاش المرتبط' % pre)
        rel = page.evaluate("() => [...document.querySelectorAll('.g-rel .sh-chip')].map(b => b.textContent.trim())")
        expect(rel == ['استحالة التنفيذ', 'شرط المشقة'] and 'لم يُستورد بعد' in t, '%s03: المصطلحات القريبة %r' % (pre, rel))
        expect(page.evaluate("() => !document.querySelector('[data-a=gdel]') && !document.querySelector('[data-a=gpub]') && !!document.querySelector('[data-a=gunpub]')"), '%s03: أزرار المنشور' % pre)
        mshot(page, pre + '03-term.jpg')
        click(page, '.g-rel .sh-chip >> nth=0', 500)
        expect('استحالة التنفيذ' in page.inner_text('.g-ar'), '%s03: فتح مصطلح قريب' % pre)
        click(page, '[data-a="gtolist"]', 500)
        expect(page.evaluate("() => !!document.querySelector('#shQ')"), '%s03: الرجوع إلى القائمة' % pre)
        browser.close()

    # —— ٠٤) مصطلح بلا ختم: النشر معطّل وسببه ظاهر
    if want('04'):
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'hardship-clause')
        dis = page.evaluate("() => { const b = document.querySelector('[data-a=gpub]'); return {disabled: b.disabled, why: (document.getElementById('gWhy') || {}).textContent || ''}; }")
        expect(dis['disabled'] and dis['why'].strip() == 'يُنشر بعد أن يراجعه خبير', '%s04: النشر معطّل بسبب %r' % (pre, dis))
        expect(page.evaluate("() => !document.querySelector('.v2s-sh a.sh-lnk') && !!document.querySelector('[data-a=gdel]')"), '%s04: لا معاينة لمسودة، والحذف متاح' % pre)
        base = len(page._glog)
        page.evaluate("() => document.querySelector('[data-a=gpub]').click()")
        page.wait_for_timeout(400)
        expect(not page.evaluate("() => !!document.getElementById('epModal')"), '%s04: ضغطة على زرّ معطّل فتحت ورقة' % pre)
        check_writes(pre + '04', page, base, 0)
        mshot(page, pre + '04-unreviewed.jpg')
        browser.close()

    # —— ٠٥) «راجعه» ثم النشر
    if want('05'):
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'hardship-clause')
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        click(page, '[data-a="grev"]', 400)
        sheet_open(page)
        click(page, '#shNext', 250)
        expect(page.inner_text('[data-e="reviewer_name"]') != '' and page.inner_text('[data-e="reviewer_role"]') != '', '%s05: اسم وصفة فاضيان مرّا' % pre)
        page.fill('#f_reviewer_name', 'x@example.test')
        page.fill('#f_reviewer_role', 'محامية')
        click(page, '#shNext', 250)
        expect(page.inner_text('[data-e="reviewer_name"]') != '', '%s05: بريد في الاسم مرّ' % pre)
        page.fill('#f_reviewer_name', 'أ. سلمى منصور')
        page.fill('#f_reviewer_role', 'أستاذة قانون')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('لن يظهر اسم المراجع للناس' in t and 'راجعه متخصص' in t, '%s05: بلا موافقة ظهور الاسم %r' % (pre, t[:300]))
        click(page, '#shBack', 300)
        expect(page.evaluate("() => document.querySelector('[data-f=reviewer_name_public]').type") == 'checkbox' and 'وافق المراجع على ظهور اسمه' in sheet_text(page), '%s05: خانة موافقة الاسم' % pre)
        page.check('[data-f="reviewer_name_public"]')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('يظهر هذا الاسم' in t and 'أ. سلمى منصور، أستاذة قانون' in t and 'ضع ختم المراجعة' in t and 'يبقى مسودة' in t, '%s05: ورقة مراجعة الختم %r' % (pre, t[:300]))
        mshot(page, pre + '05a-review-confirm.jpg')
        check_writes(pre + '05-before-confirm', page, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '05-review', page, base, 1)
        if got:
            expect(got[0][0] == 'POST' and got[0][1].endswith('/review') and got[0][2] == {'reviewer_name': 'أ. سلمى منصور', 'reviewer_role': 'أستاذة قانون', 'reviewer_name_public': True, 'confirmed': True}, '%s05: جسم الختم %r' % (pre, got[0]))
        row = gfx.term(h, 'hardship-clause')
        expect(row['reviewed_by_name'] == 'أ. سلمى منصور' and row['reviewed_by_role'] == 'أستاذة قانون' and row['reviewed_at'] is not None and row['status'] == 'draft' and row['reviewer_name_public'] is True, '%s05: الختم في القاعدة %r' % (pre, row))
        a = [x for x in gfx.audits(h, 'glossary.review')]
        expect(len(a) == 1 and a[0][0] == 'admin@local.test' and a[0][2] == str(row['id']), '%s05: التدقيق بإيميل التوكن %r' % (pre, a))
        expect('خُتم المصطلح' in note_text(page) and 'راجعه: أ. سلمى منصور، أستاذة قانون' in view_text(page), '%s05: الرسالة والسطر %r' % (pre, note_text(page)))
        expect(page.evaluate("() => { const b = document.querySelector('[data-a=gpub]'); return !!b && !b.disabled && !document.getElementById('gWhy'); }"), '%s05: النشر صار متاحًا' % pre)
        click(page, '[data-a="gpub"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('ستظهر صفحة المصطلح على الموقع خلال دقائق' in t and 'مسودة' in t and 'مؤكّد' in t and 'يتجمّد رابط المصطلح' in t, '%s05: ورقة النشر %r' % (pre, t[:200]))
        mshot(page, pre + '05b-publish-confirm.jpg')
        check_writes(pre + '05-publish-before', page, base, 1)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '05-publish', page, base, 2)
        row = gfx.term(h, 'hardship-clause')
        expect(row['status'] == 'confirmed' and row['published_at'] is not None, '%s05: النشر مؤكَّدًا في القاعدة' % pre)
        expect(PUSHES[pn:] == ['glossary:%s' % row['id']], '%s05: طلب توليد واحد عند النشر (الختم على مسودة لا يطلب) %r' % (pre, PUSHES[pn:]))
        expect(page.evaluate("() => [...document.querySelectorAll('.v2s-sh a.sh-lnk')].some(a => a.getAttribute('href') === 'https://elprofessor.net/glossary/hardship-clause.html')"), '%s05: رابط المعاينة ظهر' % pre)
        platform_clean(pre + '05', h, pbase)
        mshot(page, pre + '05c-published.jpg')
        browser.close()

    # —— ٠٦) تعديل منشور مُراجَع
    if want('06'):
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'force-majeure')
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        click(page, '[data-a="gedit"]', 400)
        sheet_open(page)
        vals = page.evaluate("() => ({ar: f_ar.value, en: f_en.value, area: f_area.value, slug: f_slug.value, slugDisabled: f_slug.disabled, opts: [...f_area.options].map(o => o.textContent.trim()), "
                             "chips: [...document.querySelectorAll('.g-rc')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())})")
        expect(vals['ar'] == 'القوة القاهرة' and vals['en'] == 'force majeure' and vals['area'] == 'contracts' and vals['slug'] == 'force-majeure' and vals['slugDisabled'], '%s06: النموذج %r' % (pre, vals))
        expect(vals['opts'][-1] == 'أخرى' and len(vals['opts']) == 10, '%s06: «أخرى» آخر المجالات %r' % (pre, vals['opts']))
        expect(len(vals['chips']) == 3 and vals['chips'][0].startswith('استحالة التنفيذ') and 'لم يُستورد بعد' in vals['chips'][2], '%s06: القريبة في النموذج %r' % (pre, vals['chips']))
        expect('لا يتغيّر بعد أول نشر' in sheet_text(page), '%s06: ملاحظة تجمّد الرابط' % pre)
        click(page, '#shNext', 300)
        expect(err_text(page) == 'لا يوجد تغيير', '%s06: لا تغيير يُرفض %r' % (pre, err_text(page)))
        page.fill('#f_definition_ar', 'حدث خارج عن إرادة الطرفين لا يمكن توقعه ولا دفعه ويجعل التنفيذ مستحيلًا.')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('سيُلغى ختم المراجعة لأنك عدّلت النص (راجعه أ. هبة الجندي)' in t and 'وسيعود المصطلح مسودة' in t and 'تختفي صفحته من الموقع' in t, '%s06: تحذير الختم %r' % (pre, t[:300]))
        mshot(page, pre + '06a-edit-warning.jpg')
        click(page, '#shBack', 300)
        expect(page.input_value('#f_definition_ar').endswith('مستحيلًا.'), '%s06: الرجوع للنموذج يحفظ ما كُتب' % pre)
        page.click('[data-relx="hardship-clause"]')
        page.select_option('#gRelPick', 'burden-of-proof')
        page.click('#gRelAdd')
        chips = page.evaluate("() => [...document.querySelectorAll('.g-rc')].map(c => c.innerText.replace(/\\s+/g, ' ').trim())")
        expect(len(chips) == 3 and any(c.startswith('عبء الإثبات') for c in chips) and not any(c.startswith('شرط المشقة') for c in chips), '%s06: حذف وإضافة قريبة %r' % (pre, chips))
        mshot(page, pre + '06b-edit-form.jpg')
        click(page, '#shNext', 300)
        expect('مصطلحات قريبة' in sheet_text(page) and 'التعريف' in sheet_text(page), '%s06: الفروق في المراجعة' % pre)
        check_writes(pre + '06-before', page, base, 0)
        confirm(page, 1100)
        sheet_gone(page)
        got = check_writes(pre + '06-edit', page, base, 1)
        if got:
            expect(got[0][0] == 'PUT' and set(got[0][2]) == {'definition_ar', 'related', 'confirmed'} and got[0][2]['related'] == ['frustration', 'not-imported-yet', 'burden-of-proof'], '%s06: جسم التعديل %r' % (pre, got[0][2]))
        row = gfx.term(h, 'force-majeure')
        expect(row['status'] == 'draft' and row['reviewed_at'] is None and row['reviewed_by_name'] is None and row['published_at'] is not None and row['slug'] == 'force-majeure', '%s06: الختم مُسح وعاد مسودة والرابط ثابت %r' % (pre, row))
        expect('عاد المصطلح مسودة' in note_text(page) and 'أُلغي ختم المراجعة' in note_text(page), '%s06: رسالة الأثر %r' % (pre, note_text(page)))
        expect('لم يراجعه خبير بعد' in view_text(page) and not page.evaluate("() => !!document.querySelector('.v2s-sh a.sh-lnk[href*=\"elprofessor.net/glossary\"]')"), '%s06: الشاشة بعد الرجوع مسودة' % pre)
        expect(PUSHES[pn:] == ['glossary:%s' % row['id']], '%s06: طلب توليد واحد لمنشور %r' % (pre, PUSHES[pn:]))
        mshot(page, pre + '06c-after-edit.jpg')
        # تعديل غير جوهري على مصطلح مُراجَع منشور: المجال وحده يُبقي الختم والنشر
        gfx.seed_terms(h)
        page.reload(wait_until='domcontentloaded')
        page.wait_for_function(READY, timeout=30000)
        term_screen(page, h, 'force-majeure')
        base = len(page._glog)
        click(page, '[data-a="gedit"]', 400)
        sheet_open(page)
        page.select_option('#f_area', 'other')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('سيُلغى ختم' not in t and 'وسيعود المصطلح مسودة' not in t and 'تتحدّث صفحته' in t, '%s06: تعديل المجال بلا تحذير %r' % (pre, t[:200]))
        confirm(page, 1100)
        sheet_gone(page)
        got = check_writes(pre + '06-soft', page, base, 1)
        row = gfx.term(h, 'force-majeure')
        expect(row['status'] == 'confirmed' and row['reviewed_at'] is not None and row['area'] == 'other', '%s06: المجال يُبقي الختم والنشر %r' % (pre, row['status']))
        platform_clean(pre + '06', h, pbase)
        browser.close()

    # —— ٠٧) مصطلح جديد
    if want('07'):
        page = sopen(browser, h, vp, mobile)
        go_sub(page, 'terms')
        base = len(page._glog)
        click(page, '[data-a="gnew"]', 400)
        sheet_open(page)
        opts = page.evaluate("() => [...document.querySelectorAll('#f_area option')].map(o => o.textContent.trim())")
        expect(opts[0] == 'اختر المجال' and opts[-1] == 'أخرى' and len(opts) == 11, '%s07: المجال بـ«أخرى» %r' % (pre, opts))
        click(page, '#shNext', 300)
        errs = page.evaluate("() => [...document.querySelectorAll('[data-e]')].filter(e => e.textContent.trim()).map(e => e.dataset.e)")
        expect({'ar', 'en', 'area', 'definition_ar'} <= set(errs), '%s07: الناقص مرفوض %r' % (pre, errs))
        mshot(page, pre + '07a-new-errors.jpg')
        page.fill('#f_ar', 'الظرف الطارئ')
        page.fill('#f_en', 'Unforeseen Circumstances')
        page.select_option('#f_area', 'other')
        page.fill('#f_definition_ar', 'واقعة لم تكن متوقعة عند التعاقد وتجعل التنفيذ مرهقًا.')
        page.fill('#f_slug', 'Bad Slug')
        click(page, '#shNext', 300)
        expect('حروف إنجليزية صغيرة' in page.inner_text('[data-e="slug"]'), '%s07: رابط سيئ مرّ' % pre)
        page.fill('#f_definition_ar', 'انظر https://example.test')
        page.fill('#f_slug', '')
        click(page, '#shNext', 300)
        expect('روابط' in page.inner_text('[data-e="definition_ar"]'), '%s07: رابط في النص مرّ' % pre)
        page.fill('#f_definition_ar', 'واقعة لم تكن متوقعة عند التعاقد وتجعل التنفيذ مرهقًا.')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('unforeseen-circumstances' in t and 'يتجمّد رابط المصطلح' in t and 'ولا يظهر على الموقع قبل أن يراجعه خبير' in t, '%s07: ورقة المراجعة %r' % (pre, t[:250]))
        mshot(page, pre + '07b-new-confirm.jpg')
        check_writes(pre + '07-before', page, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '07-create', page, base, 1)
        if got:
            expect(got[0][0] == 'POST' and got[0][2] == {'slug': 'unforeseen-circumstances', 'ar': 'الظرف الطارئ', 'en': 'Unforeseen Circumstances', 'area': 'other',
                                                       'definition_ar': 'واقعة لم تكن متوقعة عند التعاقد وتجعل التنفيذ مرهقًا.', 'confirmed': True}, '%s07: جسم الإنشاء %r' % (pre, got[0][2]))
        row = gfx.term(h, 'unforeseen-circumstances')
        expect(row and row['source'] == 'manual' and row['status'] == 'draft' and row['reviewed_at'] is None and row['published_at'] is None, '%s07: مسودة يدوية بلا ختم %r' % (pre, row and row['status']))
        wait_rows(page, 15)
        expect('أُضيف المصطلح «الظرف الطارئ» مسودة' in note_text(page), '%s07: رسالة الإضافة %r' % (pre, note_text(page)))
        # رابط مكرر: الخادم يرفض والورقة تبقى
        click(page, '[data-a="gnew"]', 400)
        sheet_open(page)
        page.fill('#f_ar', 'نسخة')
        page.fill('#f_en', 'unforeseen circumstances')
        page.select_option('#f_area', 'general')
        page.fill('#f_definition_ar', 'تعريف.')
        click(page, '#shNext', 300)
        confirm(page, 900)
        expect('مستخدم لمصطلح آخر' in err_text(page) and page.evaluate("() => !!document.getElementById('epModal')"), '%s07: الرابط المكرر %r' % (pre, err_text(page)))
        expect(gfx.count(h) == 15, '%s07: لا صف زائد بعد الرفض' % pre)
        mshot(page, pre + '07c-duplicate.jpg')
        browser.close()

    # —— ٠٨) نقاش الساحة
    if want('08'):
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'frustration')
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        opts = page.evaluate("() => [...document.querySelectorAll('#gTopic option')].map(o => [o.value, o.textContent.trim()])")
        expect(len(opts) == 4 and opts[0][0] == '' and gfx.TOPIC_DRAFT not in [o[0] for o in opts] and opts[2][1] == 'هل يكفي شرط التحكيم وحده؟', '%s08: النقاشات المنشورة فقط %r' % (pre, opts))
        expect('أو اربط نقاشًا موجودًا في الساحة' in view_text(page) and page.evaluate("() => { const b = document.querySelector('[data-a=gtopen]'); return !!b && b.disabled; }")
               and 'انشر المصطلح أولًا ثم افتح نقاشه' in view_text(page), '%s08: الربط بموجود بديل ثانوي والمسودة لا يُفتح لها نقاش' % pre)
        mshot(page, pre + '08a-topic-picker.jpg')
        click(page, '[data-a="gattach"]', 300)
        expect('اختر نقاشًا' in err_text(page, '#gTopicErr') and not page.evaluate("() => !!document.getElementById('epModal')"), '%s08: ربط بلا اختيار %r' % (pre, err_text(page, '#gTopicErr')))
        page.select_option('#gTopic', gfx.TOPIC_OPEN)
        click(page, '[data-a="gattach"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('ناقشه في الساحة' in t and 'هل يكفي شرط التحكيم وحده؟' in t, '%s08: ورقة الربط %r' % (pre, t[:200]))
        check_writes(pre + '08-before', page, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '08-attach', page, base, 1)
        if got:
            expect(got[0][2] == {'saha_topic_id': gfx.TOPIC_OPEN, 'confirmed': True}, '%s08: جسم الربط %r' % (pre, got[0][2]))
        expect(gfx.term(h, 'frustration')['saha_topic_id'] == gfx.TOPIC_OPEN, '%s08: الربط في القاعدة' % pre)
        expect(PUSHES[pn:] == [], '%s08: مسودة لا تطلب توليدًا' % pre)
        expect(page.evaluate("(u) => [...document.querySelectorAll('.v2s-sh a.sh-lnk')].some(a => a.getAttribute('href') === u)", 'https://app.elprofessor.net/?page=saha&topic=' + gfx.TOPIC_OPEN), '%s08: رابط النقاش' % pre)
        mshot(page, pre + '08b-attached.jpg')
        click(page, '[data-a="gdetach"]', 400)
        sheet_open(page)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '08-detach', page, base, 2)
        expect(gfx.term(h, 'frustration')['saha_topic_id'] is None and got[-1][2] == {'confirmed': True}, '%s08: الفصل' % pre)
        platform_clean(pre + '08', h, pbase)
        browser.close()

    # —— ٠٩) حذف مسودة
    if want('09'):
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'misc-term')
        base = len(page._glog)
        click(page, '[data-a="gdel"]', 400)
        sheet_open(page)
        expect('نهائيًا' in sheet_text(page), '%s09: ورقة الحذف' % pre)
        check_writes(pre + '09-before', page, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '09-delete', page, base, 1)
        expect(gfx.term(h, 'misc-term') is None and got and got[0][0] == 'DELETE' and got[0][2] == {'confirmed': True}, '%s09: الحذف' % pre)
        wait_rows(page, 13)
        browser.close()
        page = sopen(browser, h, vp, mobile)
        term_screen(page, h, 'injunction')
        expect(page.evaluate("() => !document.querySelector('[data-a=gdel]')"), '%s09: المنشور بلا زرّ حذف' % pre)
        browser.close()

    # —— ١٠) الاستيراد
    if want('10'):
        import_flow(browser, h, pre, vp, mobile)

    # —— ١١) شرط المراجعة
    if want('11'):
        page = sopen(browser, h, vp, mobile)
        go_sub(page, 'rules')
        t = view_text(page)
        expect('مراجعة الخبير قبل النشر: مطلوبة' in t and 'مصطلح واحد تحت التأكيد' in t and 'أغلق شرط المراجعة' in t and 'عند الإغلاق، وهو الوضع الافتراضي' in t, '%s11: شاشة الشرط %r' % (pre, t[:300]))
        mshot(page, pre + '11a-rules-on.jpg')
        click(page, '[data-a="gwaitpub"]', 500)
        wait_rows(page, 1)
        expect(page.evaluate("() => document.querySelector('#gList .sh-t').textContent.trim()") == 'الأمر القضائي المؤقت', '%s11: المنشور بلا ختم' % pre)
        click(page, '[data-k="gst"][data-v="all"]', 400)
        click(page, '[data-a="hub"]', 400)
        go_sub(page, 'rules')
        base, pn = len(page._glog), len(PUSHES)
        click(page, '[data-a="grules"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('سيُنشر أي مصطلح بشارة «تحت التأكيد»' in t and 'غير مطلوبة' in t and 'أغلق شرط المراجعة' in t, '%s11: ورقة الإغلاق %r' % (pre, t[:300]))
        mshot(page, pre + '11b-rules-off-confirm.jpg')
        check_writes(pre + '11-before', page, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '11-off', page, base, 1)
        expect(got and got[0][0] == 'PUT' and got[0][2] == {'require_review': False, 'confirmed': True} and gfx.setting(h) == '0', '%s11: الإغلاق %r' % (pre, got))
        expect('غير مطلوبة' in view_text(page), '%s11: الشاشة بعد الإغلاق' % pre)
        mshot(page, pre + '11c-rules-off.jpg')
        # والشرط مغلق: النشر بلا ختم ممكن، وتعديل منشور مُراجَع يمسح الختم ويبقيه منشورًا
        back_hub(page)
        go_sub(page, 'terms')
        open_term(page, h, 'hardship-clause')
        expect(page.evaluate("() => { const b = document.querySelector('[data-a=gpub]'); return !b.disabled && !document.getElementById('gWhy'); }"), '%s11: النشر متاح والشرط مغلق' % pre)
        click(page, '[data-a="gpub"]', 400)
        sheet_open(page)
        expect('لم يراجعه خبير بعد' in sheet_text(page) and 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' in sheet_text(page), '%s11: تحذير النشر بلا مراجعة' % pre)
        confirm(page, 1000)
        sheet_gone(page)
        expect(gfx.term(h, 'hardship-clause')['status'] == 'under_review', '%s11: نُشر بلا ختم تحت التأكيد' % pre)
        click(page, '[data-a="gtolist"]', 400)
        open_term(page, h, 'force-majeure')
        click(page, '[data-a="gedit"]', 400)
        sheet_open(page)
        page.fill('#f_definition_ar', 'تعريف معدّل لمصطلح منشور والشرط مغلق.')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('سيُلغى ختم المراجعة' in t and 'سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا' in t and 'وسيعود المصطلح مسودة' not in t, '%s11: تحذير الشرط المغلق %r' % (pre, t[:300]))
        mshot(page, pre + '11d-edit-off-warning.jpg')
        confirm(page, 1100)
        sheet_gone(page)
        row = gfx.term(h, 'force-majeure')
        expect(row['status'] == 'under_review' and row['reviewed_at'] is None, '%s11: يبقى ظاهرًا تحت التأكيد والختم مُسح' % pre)
        # إعادته: يعدّ المنشور بلا ختم ولا يُنزله
        click(page, '[data-a="gtolist"]', 400)
        back_hub(page)
        go_sub(page, 'rules')
        click(page, '[data-a="grules"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('٣ مصطلحات تحت التأكيد' in t and 'لا يُنزَل تلقائيًا' in t, '%s11: عدّ تحت التأكيد عند التفعيل %r' % (pre, t[:300]))
        mshot(page, pre + '11e-rules-on-confirm.jpg')
        confirm(page, 1000)
        sheet_gone(page)
        row = gfx.term(h, 'force-majeure')
        expect(gfx.setting(h) == '1' and row['status'] == 'under_review', '%s11: التفعيل لا يُنزل شيئًا' % pre)
        expect(len(gwrites(page, base)) == 4, '%s11: عدد الكتابات %r' % (pre, [(m, p) for m, p, _b in gwrites(page, base)]))
        browser.close()

    # —— ١٢) مصادر واقعة وحالات فاضية
    if want('12'):
        failing = (re.compile(r'.*/api/v2/content/glossary\?limit=500$'), lambda r: r.fulfill(status=500, content_type='application/json', body='{"error":"x"}'))
        page = sopen(browser, h, vp, mobile, pre_route=failing)
        nums = tile_numbers(page)
        expect(nums.get('terms') == ('—', 'غير متاح بعد') and nums.get('topics') == ('—', 'غير متاح بعد') and 'wait' not in nums, '%s12: مربّعات المصدر الواقع %r' % (pre, nums))
        expect(page.evaluate("() => !!document.querySelector('.sh-warn')"), '%s12: تنبيه الأرقام غير المتاحة' % pre)
        mshot(page, pre + '12a-hub-down.jpg')
        go_sub(page, 'terms', '.sh-warn')
        expect('غير متاح بعد' in page.inner_text('.sh-warn') and page.evaluate("() => !document.querySelector('.sh-empty')"), '%s12: شاشة المصدر الواقع' % pre)
        mshot(page, pre + '12b-list-down.jpg')
        page.unroute(failing[0])
        click(page, '[data-a="retry"]', 900)
        wait_rows(page, 14)
        browser.close()
        page = sopen(browser, h, vp, mobile, rows=[])
        nums = tile_numbers(page)
        expect(nums.get('terms') == ('٠', 'لا مصطلحات بعد، استورد القاموس الأساسي') and nums.get('wait') == ('٠', 'لا مصطلحات تنتظر'), '%s12: مربّعات القاموس الفاضي %r' % (pre, nums))
        mshot(page, pre + '12c-hub-empty.jpg')
        go_sub(page, 'terms', '.sh-empty')
        expect('لا مصطلحات بعد' in view_text(page), '%s12: حالة فاضية بلا «غير متاح»' % pre)
        expect(page.evaluate("() => !document.querySelector('.sh-warn')"), '%s12: فاضي لكن ظهر «غير متاح بعد»' % pre)
        mshot(page, pre + '12d-list-empty.jpg')
        click(page, '#gList [data-a="gimport"]', 500)
        expect('استيراد المصطلحات' in page.inner_text('.sh-head'), '%s12: زرّ الاستيراد من الفراغ' % pre)
        browser.close()
        page = sopen(browser, h, vp, mobile, down=['/api/bridge/topics'])
        term_screen(page, h, 'frustration')
        expect('قائمة النقاشات' in view_text(page) and 'غير متاح بعد' in view_text(page) and page.evaluate("() => !document.querySelector('#gTopic')"), '%s12: جسر النقاشات غايب' % pre)
        mshot(page, pre + '12e-topics-down.jpg')
        browser.close()
        page = sopen(browser, h, vp, mobile, hash_='#s/content/glossary')
        go_sub(page, 'wait')
        click(page, '[data-k="gst"][data-v="confirmed"]', 400)
        click(page, '[data-k="garea"][data-v="family"]', 400)
        expect('لا مصطلحات تطابق بحثك' in view_text(page), '%s12: فلاتر بلا نتيجة' % pre)
        browser.close()


    # —— ١٤) الوضع الافتراضي (الشرط مغلق): تحت التأكيد ⇒ مؤكّد ⇒ تعديل يعيده تحت التأكيد
    if want('14'):
        page = sopen(browser, h, vp, mobile, require=None)
        nums = tile_numbers(page)
        expect(nums.get('rules') == ('غير مطلوبة', 'مراجعة الخبير قبل النشر'), '%s14: الشرط مغلق افتراضيًا %r' % (pre, nums.get('rules')))
        go_sub(page, 'rules')
        t = view_text(page)
        expect('مراجعة الخبير قبل النشر: غير مطلوبة' in t and 'عند التفعيل' in t and 'بشارة «تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح»' in t and 'اجعل المراجعة مطلوبة' in t, '%s14: شاشة الشرط المغلق %r' % (pre, t[:400]))
        mshot(page, pre + '14a-rules-default-off.jpg')
        back_hub(page)
        go_sub(page, 'terms')
        open_term(page, h, 'hardship-clause')
        dis = page.evaluate("() => { const b = document.querySelector('[data-a=gpub]'); return {disabled: b.disabled, why: !!document.getElementById('gWhy')}; }")
        expect(not dis['disabled'] and not dis['why'], '%s14: النشر متاح بلا مراجعة %r' % (pre, dis))
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        click(page, '[data-a="gpub"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('تحت التأكيد' in t and 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' in t and 'لم يراجعه خبير بعد' in t, '%s14: ورقة النشر تقول تحت التأكيد %r' % (pre, t[:300]))
        mshot(page, pre + '14b-publish-under-review.jpg')
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '14-publish', page, base, 1)
        row = gfx.term(h, 'hardship-clause')
        expect(row['status'] == 'under_review' and row['published_at'] is not None and PUSHES[pn:] == ['glossary:%s' % row['id']], '%s14: نُشر تحت التأكيد %r' % (pre, row['status']))
        t = view_text(page)
        expect('تحت التأكيد' in t and 'على الموقع' in t and 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' in t and 'تحت التأكيد' in note_text(page), '%s14: الشاشة والرسالة بعد النشر %r' % (pre, note_text(page)))
        mshot(page, pre + '14c-under-review.jpg')
        # ختم مع موافقة ظهور الاسم ⇒ مؤكّد
        click(page, '[data-a="grev"]', 400)
        sheet_open(page)
        page.fill('#f_reviewer_name', 'د. سلمى منصور')
        page.fill('#f_reviewer_role', 'أستاذة قانون')
        page.check('[data-f="reviewer_name_public"]')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('تحت التأكيد' in t and 'مؤكّد' in t and 'ظهور الاسم للناس' in t and 'يظهر هذا الاسم' in t, '%s14: ورقة الختم تعرض قبل وبعد %r' % (pre, t[:300]))
        mshot(page, pre + '14d-stamp-confirm.jpg')
        confirm(page, 1000)
        sheet_gone(page)
        row = gfx.term(h, 'hardship-clause')
        expect(row['status'] == 'confirmed' and row['reviewer_name_public'] is True and row['reviewed_by_name'] == 'د. سلمى منصور', '%s14: صار مؤكَّدًا %r' % (pre, row))
        expect('راجعه: د. سلمى منصور، أستاذة قانون' in view_text(page) and PUSHES[pn:] == ['glossary:%s' % row['id']] * 2, '%s14: شارة الموقع وطلب التوليد %r' % (pre, PUSHES[pn:]))
        # تعديل جوهري ⇒ «تحت التأكيد» ويبقى ظاهرًا (لا مسودة)
        click(page, '[data-a="gedit"]', 400)
        sheet_open(page)
        page.fill('#f_definition_ar', 'بند يتيح إعادة التفاوض حين ينقلب توازن العقد بظرف طارئ غير متوقع.')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا' in t and 'سيُلغى ختم المراجعة' in t and 'وسيعود المصطلح مسودة' not in t, '%s14: تحذير التعديل %r' % (pre, t[:300]))
        mshot(page, pre + '14e-edit-warning.jpg')
        confirm(page, 1100)
        sheet_gone(page)
        row = gfx.term(h, 'hardship-clause')
        expect(row['status'] == 'under_review' and row['reviewed_at'] is None and row['reviewer_name_public'] is False and row['published_at'] is not None, '%s14: عاد تحت التأكيد %r' % (pre, row['status']))
        expect('تحت التأكيد' in note_text(page) and 'أُلغي ختم المراجعة' in note_text(page), '%s14: رسالة الأثر %r' % (pre, note_text(page)))
        check_writes(pre + '14-all', page, base, 3)
        platform_clean(pre + '14', h, pbase)
        # القائمة: شارة الحالة بثلاث درجات
        click(page, '[data-a="gtolist"]', 400)
        wait_rows(page, 14)
        pills = page.evaluate("() => [...new Set([...document.querySelectorAll('#gList .sh-tb tbody .sh-st')].map(e => e.textContent.trim()))]")
        expect({'مؤكّد', 'تحت التأكيد', 'مسودة'} <= set(pills), '%s14: شارات القائمة %r' % (pre, pills))
        browser.close()

    # —— ١٥) مراجعات القاموس
    if want('15'):
        page = sopen(browser, h, vp, mobile, require=None, reviews=True)
        rv = h.rv
        nums = tile_numbers(page)
        expect(nums.get('reviews') == ('٥', 'مراجعة من متخصصين تنتظر قرارك'), '%s15: مربّع المراجعات %r' % (pre, nums.get('reviews')))
        mshot(page, pre + '15a-hub.jpg')
        go_sub(page, 'reviews')
        page.wait_for_function("() => document.querySelectorAll('#rvList [data-id]').length > 0", timeout=10000)
        rows = page.evaluate("() => new Set([...document.querySelectorAll('#rvList [data-id]')].filter(e => e.offsetParent).map(e => e.dataset.id)).size")
        t = view_text(page)
        expect(rows == 5 and 'تنتظر القرار' in t and 'يؤكد الترجمة والتعريف' in t and 'يقترح تعديلًا' in t and 'تغيّر المصطلح بعدها' in t, '%s15: قائمة المعلّقة %r %r' % (pre, rows, t[:300]))
        expect('nader@example.test' not in t, '%s15: البريد لا يظهر في القائمة' % pre)
        mshot(page, pre + '15b-list.jpg')
        click(page, '[data-k="grk"][data-v="course"]', 400)
        expect(page.evaluate("() => new Set([...document.querySelectorAll('#rvList [data-id]')].filter(e => e.offsetParent).map(e => e.dataset.id)).size") == 1, '%s15: فلتر النوع' % pre)
        click(page, '[data-k="grk"][data-v="all"]', 400)
        click(page, '[data-k="grst"][data-v="rejected"]', 400)
        expect('خارج النطاق' not in view_text(page) and 'رامي كمال' in view_text(page), '%s15: المرفوضة' % pre)
        click(page, '[data-k="grst"][data-v="pending"]', 400)
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        # —— اعتمد تأكيدًا ⇒ يختم المصطلح مؤكَّدًا
        click(page, '[data-a="rvopen"][data-id="%d"]' % rv['confirm'], 500)
        t = view_text(page)
        expect('nader@example.test' in t and 'د. نادر فؤاد' in t and 'تدريس القانون' in t and 'وافق على ظهور اسمه' in t and 'الأمر القضائي المؤقت' in t and 'المصطلح الآن' in t and 'تحت التأكيد' in t, '%s15: شاشة المراجعة %r' % (pre, t[:400]))
        mshot(page, pre + '15c-review-screen.jpg')
        click(page, '[data-a="rvok"][data-id="%d"]' % rv['confirm'], 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('ختم المصطلح' in t and 'د. نادر فؤاد، تدريس القانون' in t and 'بلا ختم' in t and 'تحت التأكيد' in t and 'مؤكّد' in t and 'اعتمد وضع الختم' in t and 'يظهر' in t, '%s15: ورقة الاعتماد قبل وبعد %r' % (pre, t[:400]))
        mshot(page, pre + '15d-approve-confirm.jpg')
        check_writes(pre + '15-before', page, base, 0)
        confirm(page, 1100)
        sheet_gone(page)
        got = check_writes(pre + '15-approve', page, base, 1)
        expect(got and got[0][1].endswith('/reviews/%d/approve' % rv['confirm']) and got[0][2] == {'confirmed': True}, '%s15: جسم الاعتماد %r' % (pre, got))
        row = gfx.term(h, 'injunction')
        expect(row['status'] == 'confirmed' and row['reviewed_by_name'] == 'د. نادر فؤاد' and row['reviewed_by_role'] == 'تدريس القانون' and row['reviewer_name_public'] is True, '%s15: الختم في المصطلح %r' % (pre, row))
        expect(gfx.review(h, rv['confirm'])['status'] == 'approved' and gfx.review(h, rv['confirm'])['decided_by'] == 'admin@local.test', '%s15: المراجعة اعتُمدت بإيميل التوكن' % pre)
        expect(PUSHES[pn:] == ['glossary:%s' % row['id']] and 'صار المصطلح «الأمر القضائي المؤقت» مؤكّدًا' in note_text(page), '%s15: توليد واحد والرسالة %r' % (pre, note_text(page)))
        # —— مراجعة المصطلح الذي تغيّر بعدها: تحذير ثم رفض بملاحظة
        click(page, '[data-a="rvtolist"]', 400) if page.query_selector('[data-a="rvtolist"]') else None
        wait_rows_rv = lambda n: page.wait_for_function("n => new Set([...document.querySelectorAll('#rvList [data-id]')].filter(e => e.offsetParent).map(e => e.dataset.id)).size === n", arg=n, timeout=12000)
        wait_rows_rv(4)
        click(page, '[data-a="rvok"][data-id="%d"]' % rv['changed'], 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('تغيّر نص المصطلح بعد وصول هذه المراجعة' in t and 'يحلّ هذا المراجع محلّ أ. هبة الجندي' in t, '%s15: تحذير تغيّر المصطلح %r' % (pre, t[:300]))
        mshot(page, pre + '15e-term-changed-warning.jpg')
        click(page, '#shBack', 300)
        sheet_gone(page)
        click(page, '[data-a="rvno"][data-id="%d"]' % rv['changed'], 400)
        sheet_open(page)
        page.fill('#f_admin_note', 'خارج النطاق الحالي')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('خارج النطاق الحالي' in t and 'لا يصل إلى صاحب المراجعة أي رد من هنا' in t and 'ارفض المراجعة' in t, '%s15: ورقة الرفض %r' % (pre, t[:300]))
        mshot(page, pre + '15f-reject-confirm.jpg')
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '15-reject', page, base, 2)
        expect(got and got[-1][2] == {'admin_note': 'خارج النطاق الحالي', 'confirmed': True} and gfx.review(h, rv['changed'])['status'] == 'rejected'
               and gfx.review(h, rv['changed'])['admin_note'] == 'خارج النطاق الحالي', '%s15: الرفض بملاحظة %r' % (pre, got[-1:]))
        expect(gfx.term(h, 'force-majeure')['reviewed_by_name'] == 'أ. هبة الجندي', '%s15: الرفض لا يمسّ المصطلح' % pre)
        wait_rows_rv(3)
        # —— اعتمد اقتراحًا ⇒ المحرّر ومعه الاقتراح، والمصطلح كما هو
        click(page, '[data-a="rvok"][data-id="%d"]' % rv['suggest'], 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('يفتح محرّر المصطلح والاقتراح بجانبه' in t and 'اعتمد وافتح المحرّر' in t and 'أقترح أن يُضاف إلى التعريف' in t and 'مؤكّد' in t, '%s15: ورقة اعتماد الاقتراح %r' % (pre, t[:400]))
        mshot(page, pre + '15g-suggest-confirm.jpg')
        before_def = gfx.term(h, 'force-majeure')['definition_ar']
        confirm(page, 1400)
        sheet_open(page)
        t = sheet_text(page)
        expect('تعديل المصطلح' in t and 'الاقتراح الذي وصلنا' in t and 'ليلى حسن' in t and 'أقترح أن يُضاف إلى التعريف' in t, '%s15: المحرّر ومعه الاقتراح %r' % (pre, t[:300]))
        expect(page.evaluate("() => !!document.querySelector('#epModal .g-sugbox') && document.querySelector('#f_ar').value === 'القوة القاهرة'"), '%s15: صندوق الاقتراح وحقول المصطلح' % pre)
        mshot(page, pre + '15h-editor-with-suggestion.jpg')
        got = check_writes(pre + '15-suggest', page, base, 3)
        expect(gfx.review(h, rv['suggest'])['status'] == 'approved' and gfx.term(h, 'force-majeure')['definition_ar'] == before_def, '%s15: الاقتراح اعتُمد والمصطلح لم يتغيّر' % pre)
        click(page, '#shNo', 300)
        sheet_gone(page)
        t = view_text(page)
        expect('اقتراح تعديل من متخصص' in t and 'ليلى حسن' in t and 'أخفِ الاقتراح' in t, '%s15: لوحة الاقتراح بجانب المصطلح %r' % (pre, t[:200]))
        mshot(page, pre + '15i-term-with-suggestion.jpg')
        click(page, '[data-a="gsugx"]', 300)
        expect('اقتراح تعديل من متخصص' not in view_text(page), '%s15: إخفاء الاقتراح' % pre)
        click(page, '[data-a="gtolist"]', 500)
        wait_rows_rv(2)
        # —— دورة: «تمّ» بلا ختم
        lab = page.evaluate("id => document.querySelector('[data-a=rvok][data-id=\"' + id + '\"]').textContent.trim()", str(rv['course']))
        expect(lab == 'تمّ', '%s15: زرّ الدورة «تمّ» %r' % (pre, lab))
        click(page, '[data-a="rvok"][data-id="%d"]' % rv['course'], 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('بلا أي ختم' in t and 'من المنصة' in t and 'تمّ' in t, '%s15: ورقة تمّ %r' % (pre, t[:300]))
        mshot(page, pre + '15j-course-done.jpg')
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '15-course', page, base, 4)
        expect(gfx.review(h, rv['course'])['status'] == 'approved' and 'تمّت المراجعة' in note_text(page), '%s15: الدورة تمّت %r' % (pre, note_text(page)))
        # —— مسار: رفض بلا ملاحظة
        wait_rows_rv(1)
        click(page, '[data-a="rvno"][data-id="%d"]' % rv['track'], 400)
        sheet_open(page)
        click(page, '#shNext', 300)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '15-track', page, base, 5)
        expect(got and got[-1][2] == {'confirmed': True} and gfx.review(h, rv['track'])['status'] == 'rejected' and gfx.review(h, rv['track'])['admin_note'] is None, '%s15: رفض بلا ملاحظة %r' % (pre, got[-1:]))
        expect('لا مراجعات تنتظر قرارك' in view_text(page), '%s15: حالة فاضية بعد البتّ في الكل' % pre)
        mshot(page, pre + '15k-empty.jpg')
        click(page, '[data-k="grst"][data-v="all"]', 400)
        wait_rows_rv(7)
        platform_clean(pre + '15', h, pbase)
        expect(gfx.review(h, rv['done_ok'])['status'] == 'approved' and gfx.term(h, 'frustration')['reviewed_by_name'] == 'أ. هبة الجندي', '%s15: القديمة لم تُمسّ' % pre)
        browser.close()
        # مصدر المراجعات واقع: المربّع والقائمة لا يكذبان
        failing = (re.compile(r'.*/api/v2/content/glossary/reviews.*'), lambda r: r.fulfill(status=500, content_type='application/json', body='{"error":"x"}'))
        page = sopen(browser, h, vp, mobile, require=None, reviews=True, pre_route=failing)
        go_sub(page, 'reviews', '.sh-warn')
        expect('مراجعات القاموس: غير متاح بعد' in page.inner_text('.sh-warn') and page.evaluate("() => !document.querySelector('.sh-empty')"), '%s15: مصدر المراجعات الواقع' % pre)
        mshot(page, pre + '15l-reviews-down.jpg')
        browser.close()
        page = sopen(browser, h, vp, mobile, require=None)
        go_sub(page, 'reviews', '.sh-empty')
        expect('لا مراجعات بعد' in view_text(page), '%s15: لا مراجعات أصلًا' % pre)
        browser.close()


def import_flow(browser, h, pre, vp, mobile):
    import glossary_fixtures as fx
    seed = json.load(open(os.path.join(os.path.dirname(os.path.dirname(_HERE)), 'data', 'glossary_seed.json'), encoding='utf-8'))['items']
    course = json.load(open(os.path.join(os.path.dirname(os.path.dirname(_HERE)), 'data', 'glossary_course1.json'), encoding='utf-8'))['items']
    have = {r['slug'] for r in fx.ROWS}
    exist_seed = len({s['id'] for s in seed} & have)
    new_seed = len(seed) - exist_seed
    page = sopen(browser, h, vp, mobile)
    go_sub(page, 'import')
    chips = page.evaluate("() => [...document.querySelectorAll('[data-a=gsrc]')].map(b => b.textContent.trim())")
    expect(chips == ['القاموس الأساسي (٨٠)', 'مرشّحة من دورة القراءة (٣١)', 'ملف من جهازك'], '%s10: مصادر الاستيراد %r' % (pre, chips))
    base, pbase = len(page._glog), len(h.platform_calls)
    n0 = gfx.count(h)
    click(page, '[data-a="gprev"]', 1200)
    page.wait_for_selector('[data-r="gimp"]')
    nums = page.evaluate("() => [...document.querySelectorAll('[data-r=gimp] .sh-nums b')].map(b => b.textContent.trim())")
    expect(nums[:2] == [str(new_seed).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')), str(exist_seed).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))], '%s10: أرقام التجربة %r (متوقع %d جديد و%d موجود)' % (pre, nums, new_seed, exist_seed))
    expect(gfx.count(h) == n0 and gwrites(page, base) == [], '%s10: التجربة لا تكتب' % pre)
    expect('لم يُحفظ شيء بعد' in view_text(page), '%s10: عبارة بلا حفظ' % pre)
    mshot(page, pre + '10a-import-preview.jpg')
    click(page, '[data-a="ggo"]', 400)
    sheet_open(page)
    t = sheet_text(page)
    expect('مسودات بلا ختم مراجعة' in t and 'استورد المصطلحات' in t, '%s10: ورقة الاستيراد %r' % (pre, t[:200]))
    check_writes(pre + '10-before', page, base, 0)
    mshot(page, pre + '10b-import-confirm.jpg')
    confirm(page, 1500)
    sheet_gone(page)
    got = check_writes(pre + '10-import', page, base, 1)
    expect(got and got[0][2] == {'source': 'seed', 'confirmed': True}, '%s10: جسم الاستيراد %r' % (pre, got))
    expect(gfx.count(h) == n0 + new_seed, '%s10: عدد الصفوف بعد الاستيراد %d' % (pre, gfx.count(h)))
    m = h.app
    with m.app.app_context():
        fresh = m.GlossaryTerm.query.filter_by(source='seed').all()
        imported = [t for t in fresh if t.slug not in have]
        expect(len(imported) == new_seed and all(t.status == 'draft' and t.reviewed_at is None and t.reviewed_by_name is None and t.published_at is None for t in imported), '%s10: المستورد مسودات بلا ختم' % pre)
        mine = m.GlossaryTerm.query.filter_by(slug='force-majeure').first()
        expect(mine.status == 'confirmed' and mine.reviewed_at is not None and mine.source == 'seed', '%s10: لا كتابة فوق موجود' % pre)
    expect('تم الاستيراد' in note_text(page) and gfx.audits(h, 'glossary.seed_import')[0][3]['imported'] == new_seed, '%s10: الرسالة والتدقيق' % pre)
    click(page, '[data-a="gprev"]', 1200)
    page.wait_for_selector('[data-r="gimp"]')
    expect(page.evaluate("() => document.querySelector('[data-a=ggo]').disabled") and 'لا شيء جديد يُستورد' in view_text(page), '%s10: إعادة الاستيراد لا تجد جديدًا' % pre)
    # المرشّحة
    click(page, '[data-a="gsrc"][data-v="course1"]', 400)
    expect(page.evaluate("() => !document.querySelector('[data-r=gimp]')"), '%s10: تغيير المصدر يمسح التجربة' % pre)
    click(page, '[data-a="gprev"]', 1200)
    page.wait_for_selector('[data-r="gimp"]')
    nums = page.evaluate("() => [...document.querySelectorAll('[data-r=gimp] .sh-nums b')].map(b => b.textContent.trim())")
    expect(nums[0] == '٣١' and nums[1:] == ['٠', '٠', '٠'], '%s10: المرشّحة %r' % (pre, nums))
    mshot(page, pre + '10c-course1-preview.jpg')
    # ملف مرفوع: واحد جديد + موجود + مكرر + خطأ بعربية، والزرّ المحلي بدل زرّ المتصفح
    click(page, '[data-a="gsrc"][data-v="upload"]', 400)
    click(page, '[data-a="gprev"]', 500)
    expect('اختر ملفًا من جهازك أولًا' in view_text(page), '%s10: ملف بلا اختيار' % pre)
    lab = page.evaluate("() => { const l = document.querySelector('label.sh-filebtn'); return l ? l.innerText.trim() : null; }")
    expect(lab == 'اختر ملفًا', '%s10: زرّ الملف المحلي %r' % (pre, lab))
    tmp = tempfile.mkdtemp()

    def upload(name, text):
        p = os.path.join(tmp, name)
        open(p, 'w', encoding='utf-8').write(text)
        page.set_input_files('#gImpFile', p)
        page.wait_for_timeout(500)
    upload('bad.json', 'not json at all')
    expect('تعذّرت قراءة الملف' in view_text(page), '%s10: ملف تالف' % pre)
    upload('wrong.json', json.dumps({'items': 5}))
    expect('لا توجد فيه قائمة مصطلحات' in view_text(page), '%s10: ملف بلا قائمة' % pre)
    rows = [{'id': 'uploaded-one', 'ar': 'مصطلح مرفوع', 'en': 'uploaded one', 'area': 'general', 'definition_ar': 'تعريف مرفوع.'},
            {'id': 'force-majeure', 'ar': 'موجود', 'en': 'exists', 'area': 'contracts', 'definition_ar': 'x'},
            {'id': 'uploaded-one', 'ar': 'مكرر', 'en': 'dup', 'area': 'general', 'definition_ar': 'x'},
            {'id': 'bad-row', 'ar': 'خطأ', 'en': 'bad row', 'area': 'general', 'definition_ar': 'انظر https://example.test'}]
    upload('terms.json', json.dumps({'items': rows}, ensure_ascii=False))
    expect('terms.json' in page.inner_text('.sh-cur') and '٤ مصطلحات' in page.inner_text('.sh-cur'), '%s10: الملف المختار %r' % (pre, page.inner_text('.sh-cur') if page.query_selector('.sh-cur') else None))
    click(page, '[data-a="gprev"]', 1200)
    page.wait_for_selector('[data-r="gimp"]')
    nums = page.evaluate("() => [...document.querySelectorAll('[data-r=gimp] .sh-nums b')].map(b => b.textContent.trim())")
    expect(nums == ['١', '١', '١', '١'], '%s10: أرقام الملف %r' % (pre, nums))
    t = view_text(page)
    expect('الصف ٤' in t and 'لا تضع روابط في النص' in t and 'definition_ar' not in t and 'التعريف' in t, '%s10: خطأ الصف بالعربية %r' % (pre, t[-300:]))
    mshot(page, pre + '10d-upload-preview.jpg')
    click(page, '[data-a="ggo"]', 400)
    sheet_open(page)
    confirm(page, 1200)
    sheet_gone(page)
    got = check_writes(pre + '10-upload', page, base, 2)
    expect(len(got) == 2 and got[1][2]['source'] == 'upload' and got[1][2]['payload'] == {'items': rows} and gfx.term(h, 'uploaded-one')['status'] == 'draft', '%s10: جسم الملف %r' % (pre, got[-1:]))
    platform_clean(pre + '10', h, pbase)
    browser.close()


# ======================================================================= الجولة ٣ (المراجعات مطفأة: الافتراضي الجديد) — ١٦ إلى ١٨
def off_rows():
    return gfx.published_rows()


def topics_with(*extra):
    t = [dict(x) for x in gfx.TOPICS]
    t.extend(extra)
    return t


def flow_round3(browser, h, pre, vp, mobile):
    # —— ١٦) الافتراضي الجديد: «مسودة / منشور» بلا مراجعات، و«راجعه» ختم داخلي
    if want('16'):
        page = sopen(browser, h, vp, mobile, rows=off_rows(), require=None, expert=False)
        nums = tile_numbers(page)
        order = page.evaluate("() => [...document.querySelectorAll('.sh-tile')].map(t => t.dataset.sub)")
        expect(order == ['terms', 'topics', 'import'], '%s16: مربّعات الافتراضي الجديد %r' % (pre, order))
        expect(nums.get('terms') == ('١٤', 'منشور ٧، مسودة ٧') and nums.get('topics') == ('٦', 'مصطلح منشور بلا نقاش في الساحة'), '%s16: أرقام المربّعات %r' % (pre, nums))
        expect(not re.search('مراجعات القاموس|شرط المراجعة|تنتظر مراجعة خبير|تحت التأكيد', view_text(page)), '%s16: لا أثر للمراجعات في المربّعات' % pre)
        mshot(page, pre + '16a-hub-default.jpg')
        go_sub(page, 'terms')
        wait_rows(page, 14)
        t = view_text(page)
        nums_ = page.evaluate("() => [...document.querySelectorAll('.sh-nums li')].map(l => l.innerText.replace(/\\s+/g, ' ').trim())")
        chips = page.evaluate("() => [...document.querySelectorAll('.sh-chip')].map(c => c.textContent.trim())")
        heads = page.evaluate("() => [...document.querySelectorAll('.sh-tb thead th')].map(c => c.textContent.trim())")
        expect(nums_ == ['٧ منشور', '٧ مسودة'] and not re.search('تحت التأكيد|مؤكّد|ينتظر خبيرًا|المراجعة', t), '%s16: القائمة بلا مراجعات %r %r' % (pre, nums_, t[:200]))
        expect('منشور' in chips and 'مسودة' in chips and 'مؤكّد' not in chips and 'تحت التأكيد' not in chips and 'راجعه خبير' not in chips and any(c.startswith('أخرى') for c in chips), '%s16: شرائح الحالة %r' % (pre, chips))
        expect('المراجعة' not in heads and heads[:3] == ['المصطلح', 'المجال', 'الحالة'], '%s16: أعمدة الجدول %r' % (pre, heads))
        mshot(page, pre + '16b-list-default.jpg')
        click(page, '[data-k="gst"][data-v="published"]', 400)
        wait_rows(page, 7)
        click(page, '[data-k="gst"][data-v="all"]', 300)
        # شاشة مصطلح منشور: الحالة «منشور» والمراجعة داخلية
        open_term(page, h, 'injunction')
        t = view_text(page)
        expect('منشور' in t and 'مراجعة داخلية، لا تظهر على الموقع' in t and not re.search('تحت التأكيد|على الموقع: ', t), '%s16: شاشة المصطلح %r' % (pre, t[:300]))
        mshot(page, pre + '16c-term-published.jpg')
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        click(page, '[data-a="grev"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('مراجعة داخلية، لا تظهر على الموقع' in t and 'وافق المراجع' not in t and page.evaluate("() => !document.querySelector('#epModal .sh-chk')"), '%s16: ورقة «راجعه» الداخلية %r' % (pre, t[:200]))
        mshot(page, pre + '16d-stamp-form.jpg')
        page.fill('#f_reviewer_name', 'أ. سلمى منصور')
        page.fill('#f_reviewer_role', 'محامية')
        click(page, '#shNext', 300)
        t = sheet_text(page)
        expect('مراجعة داخلية: تُحفظ في الداشبورد ولا تظهر على الموقع.' in t and 'ظهور الاسم' not in t and 'تحت التأكيد' not in t, '%s16: مراجعة الختم %r' % (pre, t[:300]))
        mshot(page, pre + '16e-stamp-confirm.jpg')
        check_writes(pre + '16-before', page, base, 0)
        confirm(page, 1000)
        sheet_gone(page)
        got = check_writes(pre + '16-stamp', page, base, 1)
        expect(got and got[0][2] == {'reviewer_name': 'أ. سلمى منصور', 'reviewer_role': 'محامية', 'reviewer_name_public': False, 'confirmed': True}, '%s16: جسم الختم %r' % (pre, got[-1:]))
        expect(gfx.term(h, 'injunction')['reviewed_by_name'] == 'أ. سلمى منصور' and PUSHES[pn:] == ['glossary:%s' % tid(h, 'injunction')], '%s16: الختم والتوليد' % pre)
        expect('تحت التأكيد' not in view_text(page) and 'منشور' in view_text(page), '%s16: الحالة بعد الختم تبقى «منشور»' % pre)
        # نشر مسودة: لا ذكر لـ«تحت التأكيد»
        click(page, '[data-a="gtolist"]', 400)
        open_term(page, h, 'child-custody')
        click(page, '[data-a="gpub"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('مسودة' in t and 'منشور' in t and 'تحت التأكيد' not in t and 'لم يراجعه خبير' not in t, '%s16: ورقة النشر بلا شارة %r' % (pre, t[:300]))
        mshot(page, pre + '16f-publish-confirm.jpg')
        confirm(page, 1000)
        sheet_gone(page)
        expect(gfx.term(h, 'child-custody')['status'] == 'under_review' and 'تحت التأكيد' not in note_text(page) and 'نُشر المصطلح' in note_text(page), '%s16: نُشر %r' % (pre, note_text(page)))
        # ملاحظة الدول تُعرض بلا شرط التأكيد
        click(page, '[data-a="gtolist"]', 400)
        open_term(page, h, 'consideration')
        expect('ملاحظة الدول' in view_text(page) and 'لا تظهر هذه الملاحظة' not in view_text(page), '%s16: ملاحظة الدول %r' % (pre, view_text(page)[:100]))
        # صندوق المراجعات وشرطها مغلقان من الخادم أيضًا، والاستمارة العامة ٤٠٤
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const H = {Authorization: 'Bearer ' + t, 'Content-Type': 'application/json'}; const out = {};
          out.list = (await fetch('/api/v2/content/glossary/reviews', {headers: H})).status;
          out.approve = (await fetch('/api/v2/content/glossary/reviews/1/approve', {method: 'POST', headers: H, body: JSON.stringify({confirmed: true})})).status;
          out.pub = (await fetch('/api/public/expert-reviews', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({kind: 'glossary_term', ref: 'injunction'})})).status;
          out.generic = (await fetch('/api/settings', {method: 'PUT', headers: H, body: JSON.stringify({'glossary.expert_reviews_enabled': '1'})})).status;
          const feed = await (await fetch('/api/content/glossary')).json(); out.feedKeys = [...new Set(feed.terms.flatMap(x => Object.keys(x)))].filter(k => /review/.test(k));
          return out; }""")
        expect(bad['list'] == 404 and bad['approve'] == 404 and bad['pub'] == 404 and bad['generic'] == 400 and bad['feedKeys'] == [], '%s16: الإغلاق من الخادم %r' % (pre, bad))
        expect(gfx.expert_setting(h) is None, '%s16: الإعداد ما زال مغلقًا' % pre)
        browser.close()

    # —— ١٧) نقاش «الساحة» لمصطلح واحد: معاينة بلا كتابة ⇒ تأكيد
    if want('17'):
        arb = [r for r in off_rows() if r['slug'] == 'arbitral-award'][0]
        bur = [r for r in off_rows() if r['slug'] == 'burden-of-proof'][0]
        dup_live = {'id': 'e1e1e1e1-0000-4000-8000-000000000001', 'title': gfx.default_title(arb), 'status': 'open'}
        dup_dead = {'id': 'e2e2e2e2-0000-4000-8000-000000000002', 'title': gfx.default_title(bur), 'status': 'draft'}
        page = sopen(browser, h, vp, mobile, rows=off_rows(), require=None, expert=False, topics=topics_with(dup_live, dup_dead))
        term_screen(page, h, 'injunction')
        row = [r for r in off_rows() if r['slug'] == 'injunction'][0]
        base, pbase, pn = len(page._glog), len(h.platform_calls), len(PUSHES)
        t = view_text(page)
        expect('افتح نقاشًا لهذا المصطلح' in t and 'أو اربط نقاشًا موجودًا في الساحة' in t and page.evaluate("() => !document.querySelector('[data-a=gtopen]').disabled"), '%s17: لوحة النقاش %r' % (pre, t[-400:]))
        mshot(page, pre + '17a-topic-panel.jpg', focus='[data-a="gtopen"]')
        click(page, '[data-a="gtopen"]', 400)
        sheet_open(page)
        vals = page.evaluate("() => ({t: f_title.value, q: f_question.value})")
        expect(vals['t'] == gfx.default_title(row) and vals['q'] == 'هل الترجمة أو التعريف دقيق في نظامك القانوني؟ اكتب اعتراضك أو اقتراحك.', '%s17: العنوان والسؤال الافتراضيان %r' % (pre, vals))
        mshot(page, pre + '17b-topic-form.jpg')
        page.fill('#f_title', '')
        click(page, '#shNext', 300)
        expect('عنوان النقاش من' in page.inner_text('#epModal [data-e="title"]') and len(h.ef.seed_calls) == 0, '%s17: عنوان فارغ يُرفض قبل أي نداء %r' % (pre, h.ef.seed_calls))
        edited = gfx.default_title(row) + ' (نسخة)'
        page.fill('#f_title', edited)
        click(page, '#shNext', 1000)
        page.wait_for_selector('#shGo', timeout=10000)
        t = sheet_text(page)
        expect('سيُفتح نقاش جديد في الساحة' in t and edited in t and 'افتح النقاش' in t and 'حين تُفتح الساحة' in t, '%s17: مراجعة النقاش الجديد %r' % (pre, t[:400]))
        expect(h.ef.seed_calls == [(False, 1, edited)] and gfx.term(h, 'injunction')['saha_topic_id'] is None, '%s17: المعاينة بلا كتابة %r' % (pre, h.ef.seed_calls))
        mshot(page, pre + '17c-topic-review-new.jpg')
        check_writes(pre + '17-before', page, base, 0)
        click(page, '#shBack', 300)
        expect(page.input_value('#f_title') == edited, '%s17: الرجوع يحفظ العنوان' % pre)
        click(page, '#shNext', 1000)
        page.wait_for_selector('#shGo', timeout=10000)
        confirm(page, 1200)
        sheet_gone(page)
        got = check_writes(pre + '17-open', page, base, 1)
        q = 'هل الترجمة أو التعريف دقيق في نظامك القانوني؟ اكتب اعتراضك أو اقتراحك.'
        expect(got and got[0][2] == {'title': edited, 'question': q, 'confirmed': True}, '%s17: جسم الفتح %r' % (pre, got[-1:]))
        row_db = gfx.term(h, 'injunction')
        made = [x for x in h.ef.topics if x['title'] == edited]
        expect(len(made) == 1 and row_db['saha_topic_id'] == made[0]['id'] and [c[0] for c in h.ef.seed_calls] == [False, False, True], '%s17: النقاش فُتح وربط %r %r' % (pre, h.ef.seed_calls, row_db['saha_topic_id']))
        expect(PUSHES[pn:] == ['glossary:%s' % row_db['id']] and 'فُتح للمصطلح' in note_text(page), '%s17: التوليد والرسالة %r %r' % (pre, PUSHES[pn:], note_text(page)))
        expect(page.evaluate("(u) => [...document.querySelectorAll('.v2s-sh a.sh-lnk')].some(a => a.getAttribute('href') === u)", 'https://app.elprofessor.net/?page=saha&topic=' + (row_db['saha_topic_id'] or '')), '%s17: رابط النقاش المفتوح' % pre)
        mshot(page, pre + '17d-topic-opened.jpg')
        # عنوان موجود وعلنيّ: يُربط به ولا يتكرر
        click(page, '[data-a="gtolist"]', 400)
        open_term(page, h, 'arbitral-award')
        n_topics = len(h.ef.topics)
        base = len(page._glog)
        click(page, '[data-a="gtopen"]', 400)
        sheet_open(page)
        click(page, '#shNext', 1000)
        page.wait_for_selector('#shGo', timeout=10000)
        t = sheet_text(page)
        expect('يوجد نقاش بنفس العنوان، سيُربط به' in t and 'اربط النقاش' in t and 'فلن يُفتح نقاش ثانٍ' in t, '%s17: مراجعة الربط بموجود %r' % (pre, t[:300]))
        mshot(page, pre + '17e-topic-review-existing.jpg')
        confirm(page, 1200)
        sheet_gone(page)
        check_writes(pre + '17-adopt', page, base, 1)
        expect(gfx.term(h, 'arbitral-award')['saha_topic_id'] == dup_live['id'] and len(h.ef.topics) == n_topics and 'رُبط المصطلح' in note_text(page), '%s17: ربط بالموجود بلا تكرار' % pre)
        # عنوان موجود لكنه غير علني: لا ربط
        click(page, '[data-a="gtolist"]', 400)
        open_term(page, h, 'burden-of-proof')
        base = len(page._glog)
        click(page, '[data-a="gtopen"]', 400)
        sheet_open(page)
        click(page, '#shNext', 1000)
        page.wait_for_function("() => document.querySelector('#shErr') && document.querySelector('#shErr').textContent.trim()", timeout=10000)
        expect(err_text(page) == 'يوجد نقاش بنفس العنوان لكنه غير منشور في الساحة' and page.evaluate("() => !!document.querySelector('#f_title')"), '%s17: عنوان غير علني %r' % (pre, err_text(page)))
        mshot(page, pre + '17f-topic-not-live.jpg')
        click(page, '#shNo', 300)
        sheet_gone(page)
        check_writes(pre + '17-dead', page, base, 0)
        expect(gfx.term(h, 'burden-of-proof')['saha_topic_id'] is None, '%s17: لم يُربط' % pre)
        # مسودة: الزرّ معطّل وسببه ظاهر
        click(page, '[data-a="gtolist"]', 400)
        open_term(page, h, 'child-custody')
        expect(page.evaluate("() => document.querySelector('[data-a=gtopen]').disabled") and 'انشر المصطلح أولًا ثم افتح نقاشه' in view_text(page), '%s17: المسودة' % pre)
        mshot(page, pre + '17g-topic-draft.jpg')
        browser.close()
        # ضياع الرد في المعاينة: رسالة عربية والورقة تبقى
        page = sopen(browser, h, vp, mobile, rows=off_rows(), require=None, expert=False, down=['/api/bridge/topics/seed'])
        term_screen(page, h, 'injunction')
        click(page, '[data-a="gtopen"]', 400)
        sheet_open(page)
        click(page, '#shNext', 1000)
        page.wait_for_function("() => document.querySelector('#shErr') && document.querySelector('#shErr').textContent.trim()", timeout=10000)
        expect('لم يصل رد' in err_text(page) and page.evaluate("() => !!document.querySelector('#f_title')"), '%s17: ضياع الرد %r' % (pre, err_text(page)))
        mshot(page, pre + '17h-topic-no-reply.jpg')
        browser.close()

    # —— ١٨) نقاشات المصطلحات دفعةً
    if want('18'):
        arb = [r for r in off_rows() if r['slug'] == 'arbitral-award'][0]
        bur = [r for r in off_rows() if r['slug'] == 'burden-of-proof'][0]
        dup_live = {'id': 'e1e1e1e1-0000-4000-8000-000000000001', 'title': gfx.default_title(arb), 'status': 'published'}
        dup_dead = {'id': 'e2e2e2e2-0000-4000-8000-000000000002', 'title': gfx.default_title(bur), 'status': 'rejected'}
        page = sopen(browser, h, vp, mobile, rows=off_rows(), require=None, expert=False, topics=topics_with(dup_live, dup_dead))
        expect(tile_numbers(page).get('topics') == ('٦', 'مصطلح منشور بلا نقاش في الساحة') and page.evaluate("() => document.querySelector('.sh-tile[data-sub=topics]').classList.contains('hot')"), '%s18: مربّع نقاشات المصطلحات حارّ' % pre)
        go_sub(page, 'topics')
        t = view_text(page)
        expect('٦ مصطلحات' in t and 'جرّب فتح النقاشات (بلا فتح)' in t and 'هل الترجمة والتعريف دقيقان؟' in t, '%s18: شاشة الدفعة %r' % (pre, t[:300]))
        mshot(page, pre + '18a-bulk-start.jpg')
        base, pbase = len(page._glog), len(h.platform_calls)
        click(page, '[data-a="gbprev"]', 1200)
        page.wait_for_selector('[data-r="gtpprev"]', timeout=10000)
        nums = page.evaluate("() => [...document.querySelectorAll('[data-r=gtpprev] .sh-nums b')].map(b => b.textContent.trim())")
        t = view_text(page)
        expect(nums == ['٤', '١', '١'] and 'يوجد نقاش بنفس العنوان لكنه غير منشور في الساحة' in t and 'ستُربط بنقاش موجود' in t and 'سيُفتح لها نقاش جديد' in t and 'لم يُفتح شيء بعد' in t, '%s18: نتيجة التجربة %r %r' % (pre, nums, t[-500:]))
        expect(h.ef.seed_calls == [(False, 6, h.ef.seed_calls[0][2] if h.ef.seed_calls else None)] and gfx.count(h) == 14 and all(not x['saha_topic_id'] for x in [gfx.term(h, 'trademark')]), '%s18: التجربة بلا كتابة %r' % (pre, h.ef.seed_calls))
        check_writes(pre + '18-preview', page, base, 0)
        mshot(page, pre + '18b-bulk-preview.jpg')
        click(page, '[data-a="gbgo"]', 400)
        sheet_open(page)
        t = sheet_text(page)
        expect('نقاش جديد يُفتح' in t and 'تُربط بنقاش موجود' in t and 'تُترك لمشكلة' in t and 'حين تُفتح الساحة' in t and 'افتح النقاشات' in t, '%s18: ورقة التأكيد %r' % (pre, t[:400]))
        mshot(page, pre + '18c-bulk-confirm.jpg')
        check_writes(pre + '18-before', page, base, 0)
        confirm(page, 1500)
        sheet_gone(page)
        got = check_writes(pre + '18-open', page, base, 1)
        expect(got and got[0][2] == {'confirmed': True}, '%s18: جسم الفتح %r' % (pre, got[-1:]))
        page.wait_for_selector('[data-r="gtpres"]', timeout=10000)
        nums = page.evaluate("() => [...document.querySelectorAll('[data-r=gtpres] .sh-nums b')].map(b => b.textContent.trim())")
        t = view_text(page)
        expect(nums == ['٤', '١', '١'] and 'نقاش جديد فُتح لها' in t and 'رُبطت بنقاش موجود' in t and 'مصطلحات بها مشكلة' in t, '%s18: النتيجة لكل مصطلح %r' % (pre, nums))
        linked = {s: gfx.term(h, s)['saha_topic_id'] for s in ('injunction', 'hardship-clause', 'trademark', 'consideration', 'arbitral-award', 'burden-of-proof')}
        expect(all(linked[s] for s in ('injunction', 'hardship-clause', 'trademark', 'consideration', 'arbitral-award')) and linked['burden-of-proof'] is None and linked['arbitral-award'] == dup_live['id'], '%s18: الربط في القاعدة %r' % (pre, linked))
        expect([c[0] for c in h.ef.seed_calls] == [False, True] and note_text(page).startswith('اكتملت العملية'), '%s18: التجربة ثم الفتح %r %r' % (pre, h.ef.seed_calls, note_text(page)))
        mshot(page, pre + '18d-bulk-result.jpg')
        back_hub(page)
        expect(tile_numbers(page).get('topics') == ('١', 'مصطلح منشور بلا نقاش في الساحة'), '%s18: المربّع بعد الفتح %r' % (pre, tile_numbers(page).get('topics')))
        browser.close()
        # ضياع الرد: رسالة عربية ولا شيء يُربط
        page = sopen(browser, h, vp, mobile, rows=off_rows(), require=None, expert=False, down=['/api/bridge/topics/seed'])
        go_sub(page, 'topics')
        click(page, '[data-a="gbprev"]', 1000)
        page.wait_for_selector('.v2s-sh .sh-err', timeout=10000)
        expect('لم يصل رد' in page.inner_text('.v2s-sh .sh-err') and page.evaluate("() => !document.querySelector('[data-r=gtpprev]')"), '%s18: ضياع الرد %r' % (pre, page.inner_text('.v2s-sh .sh-err')))
        mshot(page, pre + '18e-bulk-no-reply.jpg')
        browser.close()
        # كل المنشور له نقاش: لا شيء للدفعة
        rows = [dict(r, saha_topic_id=r['saha_topic_id'] or gfx.TOPIC_PUB) if r['status'] != 'draft' else r for r in off_rows()]
        page = sopen(browser, h, vp, mobile, rows=rows, require=None, expert=False)
        go_sub(page, 'topics')
        expect('لا مصطلحات، لكل منشور نقاشه' in view_text(page) and page.evaluate("() => document.querySelector('[data-a=gbprev]').disabled"), '%s18: لا شيء للدفعة' % pre)
        mshot(page, pre + '18f-bulk-none.jpg')
        browser.close()


def flow_closed(browser, h, pre, vp, mobile):
    if not want('13'):
        return
    os.environ.pop('DASH_V2_ENABLED', None)
    try:
        gfx.seed_terms(h)
        h.ef = gfx.GlossaryPlatform()
        ctx = browser.context(h, 'admin', vp, mobile)
        page = ctx.new_page()
        page.goto(DASH + '/#market', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.market === 'ready' && document.getElementById('view')", timeout=30000)
        st = page.evaluate("() => ({new: !!document.querySelector('.v2s-sh'), on: !!window.V2_ON})")
        expect(not st['new'] and not st['on'], '%s13: المفتاح مقفول وفيه أثر %r' % (pre, st))
        before, n0 = len(h.platform_calls), gfx.count(h)
        bad = page.evaluate("""async () => { const t = localStorage.getItem('token'); const out = [];
          for (const p of ['/api/v2/content/glossary', '/api/v2/content/glossary/1', '/api/v2/content/glossary/settings', '/api/v2/content/glossary/topics']) {
            const x = await fetch(p, {headers: {Authorization: 'Bearer ' + t}}); if (x.status !== 404) out.push([p, x.status]); }
          for (const [m, p] of [['POST', '/api/v2/content/glossary'], ['PUT', '/api/v2/content/glossary/settings'], ['POST', '/api/v2/content/glossary/seed/import'], ['POST', '/api/v2/content/glossary/1/publish']]) {
            const x = await fetch(p, {method: m, headers: {Authorization: 'Bearer ' + t, 'Content-Type': 'application/json'}, body: JSON.stringify({confirmed: true, source: 'seed', require_review: false})}); if (x.status !== 404) out.push([m, p, x.status]); }
          return out; }""")
        expect(not bad, '%s13: مسارات القاموس والمفتاح مقفول لازم ٤٠٤: %r' % (pre, bad))
        expect(gfx.count(h) == n0 and gfx.setting(h) is None, '%s13: كتابة وصلت القاعدة والمفتاح مقفول' % pre)
        expect(len([c for c in h.platform_calls[before:] if '/topics' in c[1]]) == 0, '%s13: نداء للمنصة والمفتاح مقفول' % pre)
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(gfx.GlossaryPlatform())
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            for pre, vp, mobile in (('dash-d', DESK, False), ('dash-m', MOB, True)):
                if pre[-1] not in os.environ.get('GLOSSARY_VP', 'dm'):
                    continue
                flow_glossary(browser, h, pre, vp, mobile)
                flow_round3(browser, h, pre, vp, mobile)
                flow_closed(browser, h, pre, vp, mobile)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': vs.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'platform_calls': len(h.platform_calls), 'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
