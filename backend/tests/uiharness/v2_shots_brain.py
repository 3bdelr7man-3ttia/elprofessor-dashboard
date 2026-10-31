# -*- coding: utf-8 -*-
"""لقطات قسم «العقل» (الجولة الأخيرة — SPEC-brain §٩): كمبيوتر ١٤٤٠×٩٠٠ (`d`) · تابلت ٨٢٠×١١٨٠ (`t`) · موبايل ٣٩٠×٨٤٤ (`m`).

    cd backend && python3 -B tests/uiharness/v2_shots_brain.py [out_dir]        # الافتراضي: docs/v2/final/shots-brain

⛔ صفر طلبات حقيقية: الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة (`brain_fixtures.BrainPlatform`)، وأي أصل تاني بيتقفل ويتسجّل.
⛔ صفر نداء ذكاء: `_run_agent` و`ai_call` و`call_anthropic` مستبدلة، ومفتاح الذكاء نص تجريبي لا يخرج منه شيء.

السكربت بيفشل لو: تمرير أفقي (أي مقاس) · هدف أقل من ٤٤px (والأزرار والمفاتيح أقل من ٥٢px في الموبايل) · «0/null/NaN/undefined/[object Object]» ظاهرة ·
نص لاتيني خارج الإيميلات وكتل المساعد · أي من «اعكس · لما · ⇒ · الكنسة · نداء · ✓» ظاهر · أكثر من عنوان h1 · طلب برّه المنصة الوهمية وخطوط جوجل ·
كتابة بلا `confirmed:true` · نداء `/api/ai/agents/run` غير اللي ضغطه السكربت عمدًا.
"""
import json
import os
import re
import sys
from urllib.parse import parse_qsl, urlparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
_out = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, 'docs', 'v2', 'final', 'shots-brain')
sys.argv = [sys.argv[0], _out]
os.environ.setdefault('DASHBOARD_AI_DAILY_CAP', '40')

import v2_shots as vs                 # noqa: E402  (يقرأ sys.argv[1] عند الاستيراد)
import brain_fixtures as bfx          # noqa: E402
from ef_route_harness import Harness, DASH    # noqa: E402

DESK, MOB = vs.DESK, vs.MOB
TAB = {'width': 820, 'height': 1180}
PROBLEMS = vs.PROBLEMS
SHOTS = vs.SHOTS
TZ = 'Africa/Cairo'
FORBID = ['اعكس', '⇒', 'الكنسة', '✓']
FORBID_WORDS = ['لما ', 'نداء']
READY_SHELL = ("() => window.V2SHELL && V2SHELL.on === true && window.EP && ['opsQueue','inbox'].every(k => ['ready','error'].includes(EP.state[k]))")
READY_BRAIN = "() => { const b = document.querySelector('.v2sb'); return !!b && b.getAttribute('data-ready') === '1'; }"


def widths(page):
    return page.viewport_size['width']


def b_check(page, name):
    """فحوص الصورة (SPEC §٩): تمرير أفقي · أهداف اللمس · أرقام وحروف · نصوص ممنوعة · h1 واحد."""
    w = widths(page)
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, sw, w))
    small = page.evaluate("""() => [...document.querySelectorAll('.v2sb button, .v2sb a[href], .v2sb input, .v2sb textarea, .v2sb [role=radio], #epModal .v2sbm button, #epModal .v2sbm input')]
      .filter(b => b.offsetParent)
      .map(b => [b.className || b.tagName, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44)""")
    if small:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, small[:4]))
    if w <= 400:
        big = page.evaluate("""() => [...document.querySelectorAll('.v2sb button, .v2sb [role=radio], #epModal .v2sbm button')]
          .filter(b => b.offsetParent).map(b => [b.className || b.tagName, Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52)""")
        if big:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, big[:4]))
        wide = page.evaluate("() => [...document.querySelectorAll('.v2sb *, #epModal .v2sbm *')].filter(e => e.offsetParent && e.getBoundingClientRect().right > window.innerWidth + 1).length")
        if wide:
            PROBLEMS.append('%s: %d عنصر يخرج من عرض الشاشة' % (name, wide))
    # نص الصفحة بلا إيميلات وكتل كتبها المساعد (dir=auto) وكتل الإيميل (dir=ltr)
    txt = page.evaluate("""() => [...document.querySelectorAll('.v2sb, #epModal .v2sbm, #toasts')].map(e => { const c = e.cloneNode(true);
      c.querySelectorAll('[dir="auto"], [dir="ltr"]').forEach(n => n.remove()); return c.innerText; }).join('\\n')""")
    if re.search(r'(?<![\w@./-])(0|null|NaN|undefined)(?![\w@./-])', txt) or '[object Object]' in txt:
        PROBLEMS.append('%s: صفر/null/NaN/undefined ظاهر' % name)
    plain = re.sub(r'\S+@\S+', ' ', txt)
    lat = re.findall(r'[A-Za-z0-9][\w.-]*', plain)
    if lat:
        PROBLEMS.append('%s: نص لاتيني ظاهر: %r' % (name, lat[:4]))
    full = page.evaluate("() => document.body.innerText")
    for bad in FORBID:
        if bad in full:
            PROBLEMS.append('%s: «%s» ظاهر' % (name, bad))
    for bad in FORBID_WORDS:
        if re.search(r'(?<![؀-ۿ])' + bad, full):
            PROBLEMS.append('%s: «%s» ظاهر' % (name, bad))
    if page.evaluate("() => [...document.querySelectorAll('h1')].filter(h => h.offsetParent).length") != 1:
        PROBLEMS.append('%s: أكثر من h1 أو بلا h1' % name)


def b_shot(page, name, keep_scroll=False, keep_toast=False):
    if not keep_toast:        # توستات الخطوات السابقة لا تدخل اللقطة: كل لقطة تمثّل حالتها الصافية
        page.evaluate("() => { const t = document.getElementById('toasts'); if (t) t.innerHTML = ''; }")
    if not keep_scroll:
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    path = os.path.join(vs.OUT, name)
    page.wait_for_timeout(350)
    page.screenshot(path=path, full_page=False, type='jpeg', quality=82)
    SHOTS.append(name)
    vs.shell_check(page, name)
    b_check(page, name)


def b_full(page, name):
    """لقطة للمراجعة بالطول كله: نكبّر نافذة العرض مؤقتًا (التمرير داخل `.content` فلا تكفي `full_page`) ثم نرجّعها."""
    vp = dict(page.viewport_size)
    page.set_viewport_size({'width': vp['width'], 'height': 2600})
    page.wait_for_timeout(450)
    path = os.path.join(vs.OUT, name)
    page.screenshot(path=path, full_page=False, type='jpeg', quality=78)
    SHOTS.append(name)
    page.set_viewport_size(vp)
    page.wait_for_timeout(250)


class Rec(object):
    """يسجّل طلبات المتصفح غير GET للداشبورد (الجسم) ليفحص `confirmed:true` وعدد نداءات التشغيل."""

    def __init__(self):
        self.writes = []

    def attach(self, page):
        def on(req):
            if '/api/' in req.url and req.method != 'GET':
                try:
                    body = req.post_data
                except Exception:
                    body = None
                self.writes.append((req.method, req.url.split(DASH)[-1], body))
        page.on('request', on)

    def run_calls(self):
        return [w for w in self.writes if '/api/ai/agents/run' in w[1]]


def open_brain(ctx, rec, hash_='#s/brain/log'):
    page = ctx.new_page()
    rec.attach(page)
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    page.wait_for_function(READY_SHELL, timeout=30000)
    page.wait_for_function(READY_BRAIN, timeout=30000)
    page.wait_for_timeout(500)
    return page


B2_KEYS = ('items', 'writer', 'used', 'cap', 'active', 'down')


def setup(h, dash_kw=None, **kw):
    """`items/writer/used/cap/active/down` تذهب لمسارات العقل الجديدة المزيّفة (`Brain2Fake`)، والباقي للمنصة."""
    b2 = {k: kw.pop(k) for k in B2_KEYS if k in kw}
    h.b2 = bfx.Brain2Fake(**b2)
    h.ef = bfx.BrainPlatform(**kw)
    bfx.seed_brain_dash(h.app, **(dash_kw or {}))
    h.hold.clear()
    h.held = []


def seg(page, which):
    """تابلت/موبايل: المبدّل بين القواعد وسجل اليوم."""
    if widths(page) < 1180:
        page.click('.v2sb-seg [data-s="%s"]' % which)
        page.wait_for_timeout(250)


def writes_ok(rec, label):
    for m, p, body in rec.writes:
        if '/api/ai/agents/run' in p:
            continue
        try:
            ok = json.loads(body or '{}').get('confirmed') is True
        except Exception:
            ok = False
        if not ok:
            PROBLEMS.append('%s: كتابة بلا confirmed:true — %s %s %s' % (label, m, p, body))


def txt(page, sel):
    return page.inner_text(sel)


def flow(browser, h, pre, viewport, mobile):
    w = viewport['width']
    desk = w >= 1180
    tall = dict(viewport, height=viewport['height'])

    # ============================================================ 01 · القواعد وسجل اليوم
    setup(h)
    rec = Rec()
    ctx = browser_ctx(browser, h, tall, mobile)
    page = open_brain(ctx, rec)
    st = vs.sec_state(page)
    if st['hash'] != '#s/brain/log' or st['h1'] != 'العقل' or st['on'] != 'القواعد وسجل اليوم':
        PROBLEMS.append(pre + '01: الترويسة %r' % st)
    info = page.evaluate("""() => ({discs: [...document.querySelectorAll('.v2sb-disc')].map(d => [d.querySelector('b').textContent, d.querySelector('span').textContent]),
      line: document.querySelector('.v2sb-line p').textContent, firstIsLine: document.querySelector('.v2sb > .v3-top > .v2sb-line') !== null,
      sw: document.querySelectorAll('.v2sb-sw').length, radios: [...document.querySelectorAll('.v2sb-sw [role=radio]')].map(b => [b.textContent, b.getAttribute('aria-checked')]),
      groups: [...document.querySelectorAll('.v2sb-gh')].map(b => [b.querySelector('.v2sb-gt').textContent, b.getAttribute('aria-expanded')]),
      logrows: document.querySelectorAll('.v2sb-lr').length, acts: [...document.querySelectorAll('.v2sb-la')].map(b => b.textContent),
      want: !!document.querySelector('.v2sb-want'), imgs: document.querySelectorAll('.v2sb img').length, tabs: [...document.querySelectorAll('.v2c-tab')].map(b => b.textContent.trim()),
      desc: document.querySelector('.v2c-h p').textContent})""")
    if [d[1] for d in info['discs']] != ['وُزّع وحده اليوم', 'غيّرت خبيره يدويًا'] or [d[0] for d in info['discs']] != ['٤', '١']:
        PROBLEMS.append(pre + '01: القرصان %r' % info['discs'])
    if info['line'] != 'وُزّع اليوم ٤ ملفات وحده، وغُيّر خبير ملف واحد منها يدويًا.':
        PROBLEMS.append(pre + '01: سطر العقل «%s»' % info['line'])
    if info['sw'] != 1 or info['radios'] != [['وحده', 'true'], ['يسألني', 'false']]:
        PROBLEMS.append(pre + '01: المفتاح %r' % info['radios'])
    if info['logrows'] != 7:
        PROBLEMS.append(pre + '01: صفوف السجل %d (المتوقع ٧: أربع توزيعات + تغيير المؤسس + تقريران)' % info['logrows'])
    if info['acts'].count('أرسله لخبير آخر') != 2:
        PROBLEMS.append(pre + '01: «أرسله لخبير آخر» لازم مرتين (ملفان لم يُستلما بعد): %r' % info['acts'])
    if info['tabs'] != ['القواعد وسجل اليوم', 'المساعدون']:
        PROBLEMS.append(pre + '01: التبويبات %r' % info['tabs'])
    if mobile:
        opened = [g for g in info['groups'] if g[1] == 'true']
        if [g[0] for g in opened] != ['ما يكتبه العقل', 'ملفات الخبراء والاستشارات']:
            PROBLEMS.append(pre + '01: على الموبايل لازم «ما يكتبه العقل» و«ملفات الخبراء» مفتوحتين فقط: %r' % info['groups'])
    b_shot(page, pre + '01-rules-log.jpg')
    b_full(page, pre + '01c-rules-log-full.jpg')
    if not desk:
        seg(page, 'log')
        b_shot(page, pre + '01b-rules-log-log.jpg')
        b_full(page, pre + '01d-log-full.jpg')
        seg(page, 'rules')

    # ============================================================ 08 · قاعدة تريدها: ضغطة حفظ واحدة
    page.fill('#v2sbWant', 'لا توزّع ملفات الخليج على خبير من مصر')
    page.wait_for_timeout(150)
    n0 = len(rec.writes)
    page.click('#v2sbSave')
    page.wait_for_function("() => document.querySelector('.v2sb-row.req')", timeout=15000)
    page.wait_for_timeout(300)
    posts = [x for x in rec.writes[n0:] if x[0] == 'POST' and x[1] == '/api/v2/brain/rules']
    if len(posts) != 1 or json.loads(posts[0][2]) != {'text': 'لا توزّع ملفات الخليج على خبير من مصر', 'confirmed': True}:
        PROBLEMS.append(pre + '08: حفظ القاعدة لازم نداء واحد بـconfirmed: %r' % rec.writes[n0:])
    if not page.query_selector('#epModal') is None:
        PROBLEMS.append(pre + '08: ظهرت ورقة تأكيد عند الحفظ (لا يجب)')
    if 'لم تُبنَ بعد' not in txt(page, '.v2sb-row.req') or page.input_value('#v2sbWant') != '':
        PROBLEMS.append(pre + '08: صف القاعدة المطلوبة أو الخانة لم تُفرَّغ')
    if not desk:
        seg(page, 'rules')
    page.evaluate("() => document.querySelector('.v2sb-row.req').scrollIntoView({block: 'center'})")
    b_shot(page, pre + '08-requested-rule.jpg', keep_scroll=True)
    page.click('.v2sb-row.req [data-a="del"]')
    page.wait_for_selector('#epModal .v2sbm')
    b_shot(page, pre + '08b-delete-confirm.jpg')
    page.click('#v2sbNo')
    page.wait_for_function("() => !document.getElementById('epModal')")

    # ============================================================ 09 · ورقة القاعدة (قبل أي تغيير من الخطوات: تاريخ نظيف من البيانات)
    page.click('.v2sb-rt[data-key="assign"]')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    sheet = txt(page, '#epModal')
    if 'متى يعمل' not in sheet or 'أين ترى نتيجته' not in sheet or 'شُغّل بواسطة' not in sheet or 'أُوقف بواسطة' not in sheet:
        PROBLEMS.append(pre + '09: ورقة القاعدة ناقصة: %s' % sheet[:200])
    b_shot(page, pre + '09-rule-sheet.jpg')
    page.click('#v2sbX')
    page.wait_for_function("() => !document.getElementById('epModal')")
    page.click('.v2sb-rt[data-key="release"]')
    page.wait_for_selector('#epModal .v2sbm')
    if '٣ أيام' not in txt(page, '#epModal'):
        PROBLEMS.append(pre + '09: مهلة التحرير ٣ أيام غايبة')
    page.click('#v2sbX')
    page.wait_for_function("() => !document.getElementById('epModal')")
    # ============================================================ 03/04 · تأكيد المفتاح
    page.evaluate("() => document.querySelector('.v2sb-sw').scrollIntoView({block: 'center'})")
    page.click('.v2sb-sw [data-v="0"]')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    b_shot(page, pre + '03-confirm-off.jpg')
    if h.ef.settings_puts:
        PROBLEMS.append(pre + '03: المفتاح اتغيّر قبل التأكيد')
    n0 = len(rec.writes)
    page.click('#v2sbGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v2sb-sw [data-v=\"0\"][aria-checked=\"true\"]')", timeout=15000)
    puts = [x for x in rec.writes[n0:] if x[0] == 'PUT' and x[1] == '/api/platform-expert-files/settings']
    if len(puts) != 1 or json.loads(puts[0][2]) != {'auto_assign': False, 'confirmed': True}:
        PROBLEMS.append(pre + '03: PUT المفتاح %r' % puts)
    if [p.get('auto_assign') for p in h.ef.settings_puts] != [False] or h.ef.auto_assign is not False:
        PROBLEMS.append(pre + '03: المنصة ما سجّلت الإيقاف %r' % h.ef.settings_puts)
    if page.evaluate("() => EP.data.efSettings && EP.data.efSettings.auto_assign") is not False:
        PROBLEMS.append(pre + '03: EP.data.efSettings ما اتحدّث')
    page.wait_for_timeout(500)
    b_shot(page, pre + '02b-after-off.jpg')
    # الحالة المطفأة: سطر العقل + «افتح الملفات»
    line = txt(page, '.v2sb-line')
    if not line.startswith('التوزيع التلقائي متوقّف') or 'افتح الملفات' not in line:
        PROBLEMS.append(pre + '02: سطر العقل بعد الإيقاف «%s»' % line)
    page.evaluate("() => document.querySelector('.v2sb-sw').scrollIntoView({block: 'center'})")
    page.click('.v2sb-sw [data-v="1"]')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    if 'ينتظر الآن' not in txt(page, '#epModal'):
        PROBLEMS.append(pre + '04: سطر «ينتظر الآن» غايب')
    b_shot(page, pre + '04-confirm-on.jpg')
    page.click('#v2sbGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v2sb-sw [data-v=\"1\"][aria-checked=\"true\"]')", timeout=15000)

    writes_ok(rec, pre + '01-09')
    page.close()

    # ============================================================ 02 · التوزيع مقفول
    setup(h, auto=False)
    rec2 = Rec()
    page = open_brain(browser_ctx(browser, h, tall, mobile), rec2)
    line = txt(page, '.v2sb-line')
    if not line.startswith('التوزيع التلقائي متوقّف، وينتظر توزيعك: ') or 'افتح الملفات' not in line:
        PROBLEMS.append(pre + '02: سطر العقل «%s»' % line)
    b_shot(page, pre + '02-auto-off.jpg')
    page.click('.v2sb-line [data-a="goto"]')
    page.wait_for_function("() => location.hash.indexOf('#s/files') === 0")
    page.close()

    # ============================================================ 05 · تشغيل متوقّف
    setup(h, alert=True)
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    info = page.evaluate("""() => ({stops: document.querySelectorAll('.v2sb-chip.tone-stop').length, line: document.querySelector('.v2sb-line p').textContent,
      sw: document.querySelectorAll('.v2sb-sw').length})""")
    if info['stops'] < 8 or not info['line'].startswith('حارس المهلة والاسترداد: متوقفة') or info['sw'] != 1:
        PROBLEMS.append(pre + '05: «متوقّف» %r' % info)
    b_shot(page, pre + '05-stopped-run.jpg')
    page.close()

    # ============================================================ 06 · المصادر واقعة
    setup(h)
    h.ef.down = {'/api/bridge/ops/queue', '/api/bridge/expert-files/settings', '/api/policies'}
    h.ef.today_status = (500, {'detail': 'x'})
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    info = page.evaluate("""() => ({line: document.querySelector('.v2sb-line p').textContent, discs: [...document.querySelectorAll('.v2sb-disc b')].map(b => b.textContent),
      chips: [...document.querySelectorAll('.v2sb-row')].filter(r => ['assign','move'].includes(r.getAttribute('data-key'))).map(r => r.querySelector('.v2sb-chip') ? r.querySelector('.v2sb-chip').textContent : ''),
      lines: [...document.querySelectorAll('.v2sb-row')].filter(r => r.getAttribute('data-key') === 'move').map(r => r.querySelector('.v2sb-st').textContent),
      notes: [...document.querySelectorAll('.v3-warn')].map(n => n.textContent.trim())})""")
    if info['chips'] != ['غير متاح بعد', 'غير متاح بعد']:
        PROBLEMS.append(pre + '06: assign/move لازم «غير متاح بعد»: %r' % info)
    if not info['line'].startswith('وُزّع اليوم على الأقل'):
        PROBLEMS.append(pre + '06: سطر العقل (الاحتياط من الوارد) «%s»' % info['line'])
    if not any('من الملفات المفتوحة فقط' in n for n in info['notes']):
        PROBLEMS.append(pre + '06: ملاحظة الاحتياط من الوارد غايبة: %r' % info['notes'])
    b_shot(page, pre + '06-sources-down.jpg')
    if not desk:
        seg(page, 'log')
        b_shot(page, pre + '06b-sources-down-log.jpg')
    page.close()

    # ============================================================ 18 · سجل التوزيع غير موجود على المنصة (لا نعرف ⇒ لا نقول «لم يحدث شيء»)
    setup(h, entries=False, dash_kw={'today_reports': (), 'used': 0})
    h.ef.today_status = (404, {'detail': 'Not Found'})
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    seg(page, 'log')
    info = page.evaluate("""() => ({elephant: !!document.querySelector('.v2sb-empty'), says: document.body.innerText.indexOf('لم يحدث شيء وحده اليوم') >= 0,
      note: [...document.querySelectorAll('.v3-warn')].map(n => n.textContent.trim()), na: !!document.querySelector('.v2sb-na') && document.querySelector('.v2sb-na b').textContent,
      discs: [...document.querySelectorAll('.v2sb-disc b')].map(b => b.textContent)})""")
    if info['elephant'] or info['says'] or info['na'] != 'غير متاح بعد' or 'سجل التوزيع غير موجود على المنصة بعد' not in info['note'] or info['discs'] != ['غير متاح بعد', 'غير متاح بعد']:
        PROBLEMS.append(pre + '18: سجل التوزيع غير موجود لازم «غير متاح بعد» بلا فيل ولا «لم يحدث شيء»: %r' % info)
    b_shot(page, pre + '18-log-missing.jpg')
    page.close()

    # ============================================================ 07 · يوم فاضي
    setup(h, entries=False, dash_kw={'today_reports': (), 'used': 0})
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    seg(page, 'log')
    info = page.evaluate("() => ({empty: !!document.querySelector('.v2sb-empty img'), text: document.querySelector('.v2sb-empty b') && document.querySelector('.v2sb-empty b').textContent, line: document.querySelector('.v2sb-line p').textContent, discs: [...document.querySelectorAll('.v2sb-disc b')].map(b => b.textContent)})")
    if not info['empty'] or info['text'] != 'لم يحدث شيء وحده اليوم حتى الآن' or info['discs'] != ['لا شيء', 'لا شيء']:
        PROBLEMS.append(pre + '07: اليوم الفاضي %r' % info)
    if info['line'] != 'لم يوزّع العقل شيئًا اليوم، وكل ما يعمل وحده يعمل.':
        PROBLEMS.append(pre + '07: سطر العقل «%s»' % info['line'])
    b_shot(page, pre + '07-empty-day.jpg')
    page.close()

    # ============================================================ 18-21 · ما يكتبه العقل (الجولة الثانية — SPEC brain2 §4.4)
    setup(h)
    rec4 = Rec()
    page = open_brain(browser_ctx(browser, h, tall, mobile), rec4)
    page.wait_for_function("() => document.querySelectorAll('.v2sb-md').length === 8", timeout=15000)
    info = page.evaluate("""() => ({grp: [...document.querySelectorAll('.v2sb-gh')].map(b => [b.querySelector('.v2sb-gt').textContent, b.getAttribute('aria-expanded')]),
      hint: (document.querySelector('.v2sb-whint') || {}).textContent,
      rows: [...document.querySelectorAll('.v2sb-row.has-md')].map(r => ({id: r.getAttribute('data-key'), title: r.querySelector('.v2sb-rt').textContent,
        radios: [...r.querySelectorAll('[role=radio]')].map(b => [b.textContent, b.getAttribute('aria-checked')]), group: r.querySelector('[role=radiogroup]').getAttribute('aria-label'), st: r.querySelector('.v2sb-st').textContent})),
      run: (document.querySelector('.v2sb-runbtn') || {}).textContent, runOff: !!(document.querySelector('.v2sb-runbtn') || {}).disabled})""")
    rows = {r['id']: r for r in info['rows']}
    if info['grp'][0] != ['ما يكتبه العقل', 'true'] or info['hint'] != 'اقتراحات يكتبها العقل من بيانات حقيقية' or len(rows) != 8:
        PROBLEMS.append(pre + '18: مجموعة «ما يكتبه العقل» %r' % info['grp'])
    if rows['w:opinion']['radios'] != [['وحده', 'true'], ['متوقّف', 'false']]:
        PROBLEMS.append(pre + '18: الرأي لازم «وحده | متوقّف»: %r' % rows['w:opinion']['radios'])
    for k, reason in (('w:reply_draft', 'يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.'), ('w:course_review', 'يسألك دائمًا لأن النشر يظهر للناس.'),
                      ('w:market_match', 'يسألك دائمًا لأنه يغيّر بيانات الطلب على المنصة.')):
        if rows[k]['radios'] != [['يسألني', 'true'], ['متوقّف', 'false']] or rows[k]['st'] != reason:
            PROBLEMS.append(pre + '18: المقفول %s لازم «يسألني | متوقّف» وسطر السبب: %r' % (k, rows[k]))
    for k in ('w:seo_notes', 'w:campaign_comment', 'w:weekly_read', 'w:forecast_comment'):
        if rows[k]['radios'] != [['وحده', 'true'], ['يسألني', 'false'], ['متوقّف', 'false']]:
            PROBLEMS.append(pre + '18: %s لازم ثلاثة خيارات: %r' % (k, rows[k]['radios']))
    if rows['w:seo_notes']['group'] != 'ملاحظات الظهور في البحث على المسودات' or info['run'] != 'اكتب الاقتراحات الآن' or info['runOff']:
        PROBLEMS.append(pre + '18: اسم المجموعة أو زرّ الكتابة %r' % info['run'])
    page.evaluate("() => document.querySelector('.v2sb-rules').scrollIntoView({block: 'start'})")
    b_shot(page, pre + '18-switches.jpg', keep_scroll=True)
    page.evaluate("() => document.querySelector('.v2sb-runnow').scrollIntoView({block: 'center'})")
    b_shot(page, pre + '18b-switches-run-button.jpg', keep_scroll=True)
    # تغيير اختيار: ورقة التأكيد ⇐ PUT بـconfirmed ⇐ «حُفظ الاختيار»
    page.evaluate("() => document.querySelector('.v2sb-row[data-key=\"w:seo_notes\"]').scrollIntoView({block: 'center'})")
    page.click('.v2sb-row[data-key="w:seo_notes"] [role=radio].off')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    cf = txt(page, '#epModal')
    if 'يتوقف العقل عن كتابة «ملاحظات الظهور في البحث على المسودات»' not in cf or 'نعم، أوقفه' not in cf:
        PROBLEMS.append(pre + '18: ورقة تأكيد الإيقاف «%s»' % cf[:200])
    if h.b2.writes:
        PROBLEMS.append(pre + '18: الاختيار اتغيّر قبل التأكيد')
    b_shot(page, pre + '18c-mode-confirm.jpg')
    n0 = len(rec4.writes)
    page.click('#v2sbGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v2sb-row[data-key=\"w:seo_notes\"] [role=radio].off[aria-checked=\"true\"]')", timeout=15000)
    puts = [x for x in rec4.writes[n0:] if x[0] == 'PUT' and x[1] == '/api/v2/brain/switches/seo_notes']
    if len(puts) != 1 or json.loads(puts[0][2]) != {'mode': 'off', 'confirmed': True} or h.b2.modes['seo_notes'] != 'off':
        PROBLEMS.append(pre + '18: PUT الاختيار %r' % puts)
    if 'حُفظ الاختيار' not in page.inner_text('#toasts'):
        PROBLEMS.append(pre + '18: توست «حُفظ الاختيار» غايب')
    # ورقة قاعدة مقفولة: الجملة + سبب القفل + «أين ترى نتيجته»
    page.evaluate("() => document.querySelector('.v2sb-row[data-key=\"w:reply_draft\"]').scrollIntoView({block: 'center'})")
    page.click('.v2sb-row[data-key="w:reply_draft"] .v2sb-rt')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    sheet = txt(page, '#epModal')
    for need in ('عندما تصل رسالة أو طلب تواصل، يكتب العقل مسودة رد تراجعها قبل أن تصل إلى صاحبها.', 'يسألك دائمًا لأن الرد يصل إلى صاحب الرسالة.', 'أين ترى نتيجته', 'افتح الناس والدعوات'):
        if need not in sheet:
            PROBLEMS.append(pre + '19: ورقة القاعدة المقفولة ينقصها «%s»' % need)
    b_shot(page, pre + '19-locked-sheet.jpg')
    page.click('#v2sbGo')
    page.wait_for_function("() => location.hash.indexOf('#s/people') === 0", timeout=15000)
    writes_ok(rec4, pre + '18-19')
    page.close()

    # —— 20 · سجل اليوم بعناصر العقل
    setup(h, entries=False, items=bfx.brain2_items())
    rec5 = Rec()
    page = open_brain(browser_ctx(browser, h, tall, mobile), rec5)
    page.wait_for_function("() => document.querySelector('.v2sb-log-card').textContent.indexOf('كتب رأيه في') >= 0", timeout=15000)
    line = txt(page, '.v2sb-line')
    if not line.startswith('ينتظرك من العقل: اقتراحان') or 'ابدأ القرارات' not in line:
        PROBLEMS.append(pre + '20: سطر العقل 2b «%s»' % line)
    seg(page, 'log')
    got = page.evaluate("() => [...document.querySelectorAll('.v2sb-lr')].map(r => [r.querySelector('.v2sb-lt > span').textContent, (r.querySelector('.v2sb-la') || {}).textContent || ''])")
    want = {'كتب ملاحظة على «مقال: عقود الإيجار التجاري»': 'احذفها', 'كتب ملاحظة على «حملة الإيجار — فيسبوك»': 'احذفها',
            'اقترح «مسودة رد» على «رسالة من منى عن موعد الاستشارة»': 'افتح', 'اقترح «مراجعة دورة» على «دورة أساسيات التسويق القانوني»': 'افتح',
            'نُفّذ «ربط بدورة» على «طلب: تدريب على عقود العمل» بموافقتك': '', 'رُفض اقتراح على «رسالة من كريم»': '',
            'حُذفت ملاحظة على «مقال: نفقة الزوجة»': '', 'تعذّرت الكتابة عن «الأسبوع الماضي»': '', 'كتب رأيه في ٣ قرارات': ''}
    have = {t: a for t, a in got}
    for t, a in want.items():
        if t not in have or have[t] != a:
            PROBLEMS.append(pre + '20: صف السجل «%s» (الإجراء «%s») غير موجود أو إجراؤه خطأ: %r' % (t, a, got))
    if sum(1 for t, a in got if t.startswith('كتب رأيه في')) != 1 or any('بياناتي' in t for t, a in got):
        PROBLEMS.append(pre + '20: الآراء لازم صف واحد مجمَّع')
    if h.b2.item_queries and not (h.b2.item_queries[0].get('status') == 'all' and re.match(r'^\d{4}-\d\d-\d\dT', h.b2.item_queries[0].get('since', ''))):
        PROBLEMS.append(pre + '20: استعلام العناصر %r' % h.b2.item_queries[:1])
    b_shot(page, pre + '20-log-items.jpg')
    b_full(page, pre + '20c-log-items-full.jpg')
    # حذف ملاحظة: ورقة ثم توست ثم تتحول لصف «حُذفت»
    page.click('.v2sb-lr:has-text("عقود الإيجار التجاري") .v2sb-la')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    if 'تُحذف هذه الملاحظة. لم تغيّر شيئًا في المنصة.' not in txt(page, '#epModal'):
        PROBLEMS.append(pre + '20: نص ورقة الحذف «%s»' % txt(page, '#epModal')[:120])
    b_shot(page, pre + '20b-discard-sheet.jpg')
    n0 = len(rec5.writes)
    page.click('#v2sbGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => [...document.querySelectorAll('.v2sb-lt > span')].some(s => s.textContent === 'حُذفت ملاحظة على «مقال: عقود الإيجار التجاري»')", timeout=15000)
    posts = [x for x in rec5.writes[n0:] if x[0] == 'POST' and x[1] == '/api/v2/brain/items/bi-note-1/discard']
    if len(posts) != 1 or json.loads(posts[0][2]) != {'confirmed': True}:
        PROBLEMS.append(pre + '20: نداء الحذف %r' % posts)
    if 'حُذفت الملاحظة' not in page.inner_text('#toasts'):
        PROBLEMS.append(pre + '20: توست «حُذفت الملاحظة» غايب')
    b_shot(page, pre + '20d-after-discard.jpg', keep_toast=True)
    # «ابدأ القرارات» تفتح الرئيسية
    page.click('.v2sb-line [data-a="goto"]')
    page.wait_for_function("() => location.hash.indexOf('#s/home') === 0", timeout=15000)
    writes_ok(rec5, pre + '20')
    page.close()

    # —— 21 · اكتب الاقتراحات الآن
    setup(h)
    rec6 = Rec()
    page = open_brain(browser_ctx(browser, h, tall, mobile), rec6)
    page.wait_for_function("() => document.querySelector('.v2sb-runbtn')", timeout=15000)
    page.evaluate("() => document.querySelector('.v2sb-runnow').scrollIntoView({block: 'center'})")
    page.click('.v2sb-runbtn')
    page.wait_for_selector('#epModal .v2sbm #v2sbGo')
    lead = txt(page, '#epModal .mc-lead')
    if lead != 'يكتب العقل الآن ما ينقص من اقتراحات، بحد أقصى ٢٠ كتابة.' or 'نعم، ابدأ' not in txt(page, '#epModal'):
        PROBLEMS.append(pre + '21: نص ورقة التشغيل «%s»' % lead)
    if h.b2.writes:
        PROBLEMS.append(pre + '21: نداء التشغيل قبل التأكيد')
    b_shot(page, pre + '21-run-sheet.jpg')
    n0 = len(rec6.writes)
    page.click('#v2sbGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function("() => document.querySelector('.v2sb-runbtn').disabled", timeout=15000)
    runs = [x for x in rec6.writes[n0:] if x[0] == 'POST' and x[1] == '/api/v2/brain/run']
    if len(runs) != 1 or json.loads(runs[0][2]) != {'confirmed': True}:
        PROBLEMS.append(pre + '21: نداء التشغيل %r' % runs)
    if 'بدأ العقل الكتابة' not in page.inner_text('#toasts') or 'العقل يكتب الآن' not in txt(page, '.v2sb-runnow'):
        PROBLEMS.append(pre + '21: توست أو سبب التعطيل غايب')
    b_shot(page, pre + '21b-run-active.jpg', keep_scroll=True, keep_toast=True)
    writes_ok(rec6, pre + '21')
    page.close()
    # جولة جارية من قبل ⇒ الزرّ معطّل من أول لحظة · سقف اليوم ⇒ معطّل بسببه
    setup(h, active=True)
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    page.wait_for_function("() => document.querySelector('.v2sb-runbtn')", timeout=15000)
    if not page.evaluate("() => document.querySelector('.v2sb-runbtn').disabled"):
        PROBLEMS.append(pre + '21: جولة جارية والزرّ مفتوح')
    page.close()
    setup(h, used=60, cap=60)
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    page.wait_for_function("() => document.querySelector('.v2sb-runbtn')", timeout=15000)
    if not page.evaluate("() => document.querySelector('.v2sb-runbtn').disabled") or 'بلغ العقل حدّ كتابته اليوم' not in txt(page, '.v2sb-runnow'):
        PROBLEMS.append(pre + '21: سقف اليوم لازم يعطّل الزرّ بسببه')
    page.close()

    # —— 22 · كل مصدر يفشل لوحده ⇒ «غير متاح بعد» لا صفر
    setup(h, down={'/api/v2/brain/switches', '/api/v2/brain/items', '/api/v2/brain/runs/latest'})
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec())
    page.wait_for_function("() => document.querySelector('.v2sb-whint') && document.querySelector('.v2sb-whint').parentElement.querySelector('.v3-warn')", timeout=15000)
    info = page.evaluate("""() => ({md: document.querySelectorAll('.v2sb-md').length, run: !!document.querySelector('.v2sb-runbtn'),
      warn: document.querySelector('.v2sb-whint').parentElement.querySelector('.v3-warn').textContent,
      log: document.querySelector('.v2sb-log-card').textContent})""")
    if info['md'] or info['run'] or 'غير متاح بعد' not in info['warn'] or 'ما كتبه العقل اليوم: غير متاح بعد' not in info['log']:
        PROBLEMS.append(pre + '22: المصادر الواقعة %r' % info)
    b_shot(page, pre + '22-brain2-sources-down.jpg')
    page.close()
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec(), '#s/brain/helpers')
    wd = page.evaluate("() => [...document.querySelectorAll('.v2sb-wdiscs .v2sb-disc b')].map(b => b.textContent)")
    if wd != ['غير متاح بعد', 'غير متاح بعد']:
        PROBLEMS.append(pre + '22: قرصا المساعدين لازم «غير متاح بعد» حين يقع المصدر: %r' % wd)
    b_shot(page, pre + '22b-helpers-discs-down.jpg')
    page.close()
    for writer, expect in (('backup', 'الكاتب الاحتياطي'), (None, 'لا أحد')):
        setup(h, writer=writer)
        page = open_brain(browser_ctx(browser, h, tall, mobile), Rec(), '#s/brain/helpers')
        page.wait_for_function("() => document.querySelector('.v2sb-wdiscs .v2sb-disc b').textContent !== 'غير متاح بعد'", timeout=15000)
        got = page.inner_text('.v2sb-wdiscs .v2sb-disc b')
        if got != expect:
            PROBLEMS.append(pre + '22: قرص الكاتب %r بدل %r' % (got, expect))
        page.close()

    # ============================================================ 10-14 · المساعدون
    setup(h)
    rec3 = Rec()
    page = open_brain(browser_ctx(browser, h, tall, mobile), rec3, '#s/brain/helpers')
    info = page.evaluate("""() => ({cards: document.querySelectorAll('.v2sb-hc').length, master: !!document.querySelector('.v2sb-master'),
      onlyNums: [...document.querySelectorAll('.v2sb-hc .v2sb-chip')].map(c => c.textContent), disc: document.querySelector('.v2sb-disc b').textContent,
      line: document.querySelector('.v2sb-line p').textContent, h1: document.querySelector('.v2c-h h1').textContent, on: document.querySelector('.v2c-tab.on').textContent,
      labels: [...document.querySelectorAll('.v2sb-hc h3')].map(h => h.textContent), runs: [...document.querySelectorAll('[data-run]')].filter(b => b.disabled).length})""")
    if info['cards'] != 10 or not info['master'] or info['onlyNums'] != ['أرقام فقط'] or info['disc'] != '٣ من ٤٠' or info['runs']:
        PROBLEMS.append(pre + '10: المساعدون %r' % info)
    if info['on'] != 'المساعدون' or info['h1'] != 'العقل':
        PROBLEMS.append(pre + '10: الترويسة %r' % info)
    if not info['line'].startswith('آخر صورة كاملة كُتبت'):
        PROBLEMS.append(pre + '10: سطر العقل «%s»' % info['line'])
    wd = page.evaluate("() => [...document.querySelectorAll('.v2sb-wdiscs .v2sb-disc')].map(d => [d.querySelector('b').textContent, d.querySelector('span').textContent])")
    if wd != [['الكاتب الأساسي', 'من يكتب الآن'], ['١٢ من ٦٠', 'كتابات العقل اليوم']]:
        PROBLEMS.append(pre + '10: قرصا الكاتب وعدّاد اليوم %r' % wd)
    b_shot(page, pre + '10-helpers.jpg')
    b_full(page, pre + '10c-helpers-full.jpg')
    # 11 · ورقة تقرير مساعد
    page.click('.v2sb-hc[data-id="sales"] [data-a="hview"]')
    page.wait_for_selector('#epModal .v2sbm #v2sbRun')
    if 'كتبه المساعد' not in txt(page, '#epModal') or 'ما يقترحه' not in txt(page, '#epModal'):
        PROBLEMS.append(pre + '11: ورقة التقرير ناقصة')
    b_shot(page, pre + '11-helper-sheet.jpg')
    page.click('#v2sbX')
    page.wait_for_function("() => !document.getElementById('epModal')")
    # 13 · حدّث الكل
    page.click('[data-a="hall"]')
    page.wait_for_selector('#epModal #v2sbAllGo')
    cf = txt(page, '#epModal .mc-lead')
    if 'سيكتب المساعدون ١١ مساعدًا' not in cf or 'المتبقي: ٣٧' not in cf:
        PROBLEMS.append(pre + '13: نص تأكيد «حدّث الكل» «%s»' % cf)
    b_shot(page, pre + '13-run-all-confirm.jpg')
    page.click('#v2sbNo')
    page.wait_for_function("() => !document.getElementById('epModal')")
    if rec3.run_calls():
        PROBLEMS.append(pre + '13: نداء تشغيل قبل التأكيد')
    # 14 · قيد الكتابة: ضغطة واحدة تقفل الكل
    runs0 = h.dash_calls.count(('POST', '/api/ai/agents/run'))
    h.hold.add(('POST', '/api/ai/agents/run'))
    page.click('.v2sb-hc[data-id="sales"] [data-run="sales"]')
    page.wait_for_function("() => document.querySelector('[data-run=\"sales\"]').textContent.trim() === 'جارٍ الكتابة…'", timeout=10000)
    state = page.evaluate("() => [...document.querySelectorAll('[data-run]')].map(b => [b.getAttribute('data-run'), b.disabled, b.textContent.trim()])")
    if not all(s[1] for s in state) or [s for s in state if s[2] == 'جارٍ الكتابة…'][0][0] != 'sales':
        PROBLEMS.append(pre + '14: زرار التشغيل لازم تتقفل كلها والمضغوط يقول «جارٍ الكتابة…»: %r' % state)
    page.evaluate("() => document.querySelector('[data-run=sales]').scrollIntoView({block: 'center'})")
    b_shot(page, pre + '14-running.jpg', keep_scroll=True)
    page.evaluate("() => document.querySelectorAll('[data-run]').forEach(b => b.click())")      # ضغطات ثانية: لازم لا ترسل شيئًا
    page.wait_for_timeout(300)
    h.hold.clear()
    h.release_held()
    page.wait_for_selector('.toast', timeout=10000)
    page.wait_for_timeout(300)
    if len(rec3.run_calls()) != 1 or h.dash_calls.count(('POST', '/api/ai/agents/run')) - runs0 != 1:
        PROBLEMS.append(pre + '14: نداءات التشغيل لازم واحد بالظبط: %r' % rec3.run_calls())
    toast = page.inner_text('#toasts')
    if 'كُتب تقرير «المبيعات»' not in toast:
        PROBLEMS.append(pre + '14: توست التشغيل «%s»' % toast)
    b_shot(page, pre + '14b-after-run.jpg', keep_toast=True)
    writes_ok(rec3, pre + '10-14')
    page.close()
    # 12 · سقف اليوم
    setup(h, dash_kw={'used': 40})
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec(), '#s/brain/helpers')
    info = page.evaluate("() => ({line: document.querySelector('.v2sb-line p').textContent, off: [...document.querySelectorAll('[data-run]')].every(b => b.disabled), n: document.querySelectorAll('[data-run]').length, disc: document.querySelector('.v2sb-disc b').textContent})")
    if not info['off'] or info['n'] < 11 or not info['line'].startswith('وصلت تحديثات اليوم إلى حدّها') or info['disc'] != '٤٠ من ٤٠':
        PROBLEMS.append(pre + '12: سقف اليوم %r' % info)
    b_shot(page, pre + '12-helpers-cap.jpg')
    page.close()

    # ============================================================ 15 · الرابط القديم · 17 · المربّع
    setup(h)
    page = open_brain(browser_ctx(browser, h, tall, mobile), Rec(), '#ai')
    if page.evaluate("() => location.hash") != '#s/brain/helpers' or not page.query_selector('.v2sb-helpers'):
        PROBLEMS.append(pre + '15: #ai ما هبطش على المساعدين بالشكل الجديد (%s)' % page.evaluate("() => location.hash"))
    b_shot(page, pre + '15-old-link.jpg')
    page.close()
    if desk:
        setup(h)
        page = browser_ctx(browser, h, tall, mobile).new_page()
        page.goto(DASH + '/#s/home/board', wait_until='domcontentloaded')
        page.wait_for_function(vs.READY, timeout=30000)
        page.wait_for_function("() => { const c = document.querySelector('[data-tile=\"brain\"] .v2-cnt'); return c && !c.classList.contains('ld') && c.textContent.trim() === '٤'; }", timeout=20000)
        tile = page.inner_text('[data-tile="brain"] .v2-cnt')
        page.click('[data-tile="brain"]')
        page.wait_for_function(READY_BRAIN, timeout=20000)
        d1 = page.inner_text('.v2sb-disc b')
        if tile != d1 or d1 != '٤':
            PROBLEMS.append(pre + '17: رقم المربّع «%s» ≠ رقم القرص «%s»' % (tile, d1))
        page.go_back()
        page.wait_for_selector('[data-tile="brain"]')
        page.wait_for_timeout(400)
        vs.shot(page, pre + '17-tile.jpg')
        page.close()

    # ============================================================ 16 · المفتاح مقفول (كمبيوتر فقط)
    if desk:
        os.environ['DASH_V2_ENABLED'] = 'false'
        try:
            h.ef = bfx.BrainPlatform()
            ctx = browser_ctx(browser, h, tall, mobile)
            page = ctx.new_page()
            page.goto(DASH + '/#ai', wait_until='domcontentloaded')
            page.wait_for_function("() => window.EP && EP.authed && document.querySelector('#view') && /الفريق/.test(document.querySelector('#view').innerText)", timeout=30000)
            if page.query_selector('.v2sb') or page.query_selector('#v2Side') or 'v2-shell' in (page.evaluate("() => document.querySelector('.app').className") or ''):
                PROBLEMS.append(pre + '16: المفتاح مقفول ومع ذلك ظهر أثر للغلاف الجديد')
            vs.shot(page, pre + '16-flag-off.jpg')
            page.close()
        finally:
            os.environ['DASH_V2_ENABLED'] = 'true'


def browser_ctx(browser, h, viewport, mobile):
    """سياق جديد بمتصفح جديد (`--single-process` يستحمل سياقًا واحدًا) وتوقيت جهاز المؤسس = القاهرة."""
    browser.close()
    browser.current = browser.p.chromium.launch(args=['--single-process'])
    return h.context(browser.current, 'admin', viewport, mobile, tz=TZ)


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(bfx.BrainPlatform())
    appmod = h.app
    os.environ['DEEPSEEK_API_KEY'] = 'shots-fake-key-never-used'

    def no_ai(*a, **k):
        raise RuntimeError('نداء ذكاء ممنوع في اللقطات')

    appmod.ai_call = no_ai
    appmod.call_anthropic = no_ai

    # مسارات العقل الجديدة (الباكدج P1 يبنيها في الخادم): تُجاب هنا من `Brain2Fake` فلا يعتمد اللقط على وجودها. باقي المسارات للتطبيق نفسه.
    orig_api = h._api

    def api(route):
        req = route.request
        u = urlparse(req.url)
        b2 = getattr(h, 'b2', None)
        if b2 is not None and b2.owns(u.path):
            try:
                body = json.loads(req.post_data) if req.post_data else None
            except Exception:
                body = None
            out = b2.handle(req.method, u.path, dict(parse_qsl(u.query)), body)
            if out is not None:
                return route.fulfill(status=out[0], headers={'content-type': 'application/json'}, body=json.dumps(out[1], ensure_ascii=False))
        return orig_api(route)

    h._api = api
    h.b2 = bfx.Brain2Fake()

    def fake_run(agent):
        meta = appmod.AI_AGENT_MAP.get(agent)
        if not meta:
            return None
        only = agent == 'marketing'
        row = appmod.AgentReport(agent=agent, summary='ملخص جديد للتقرير.' if not only else 'تعذّر التحليل الآن — هذه أرقام حقيقية بلا تحليل نصّي.',
                                 bullets_json=json.dumps(['ملاحظة جديدة'], ensure_ascii=False), actions_json=json.dumps(['إجراء جديد'], ensure_ascii=False))
        appmod.db.session.add(row)
        appmod.db.session.commit()
        return appmod._serialize_report(agent, row, source='data' if only else None)

    appmod._run_agent = fake_run
    with sync_playwright() as p:
        browser = vs.Browsers(p)
        try:
            flow(browser, h, 'd', DESK, False)
            flow(browser, h, 't', TAB, False)
            flow(browser, h, 'm', MOB, True)
        finally:
            browser.close()
    rep = h.blocked_report()
    print(json.dumps({'out': vs.OUT, 'shots': SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'platform_calls': len(h.platform_calls), 'problems': PROBLEMS},
                     ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
