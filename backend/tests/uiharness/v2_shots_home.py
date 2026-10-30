# -*- coding: utf-8 -*-
"""صور «اللوحة + كل الوارد + الدرج + الجرس + الدخول» (الجولة النهائية، docs/v2/final/SPEC-home.md §١٣).

    cd backend && python3 -B tests/uiharness/v2_shots_home.py ../docs/v2/final/shots-home

كمبيوتر `d` ١٤٤٠×٩٠٠ · تابلت `t` ٨٢٠×١١٨٠ · موبايل `m` ٣٩٠×٨٤٤. الداشبورد بيتنفّذ جوه العملية والمنصة جدول في الذاكرة
(`v2_fixtures.V2Platform`)، وأي أصل تاني غير خطوط جوجل بيتقفل ويتسجّل. ⛔ ولا لقطة بتبعت قرار أو فلوس: السكربت بيفشل لو في أي
POST/PUT/PATCH/DELETE للداشبورد غير تسجيل الدخول الغلط (لقطة ٢٥).

السكربت بيفشل لو: تمرير أفقي في ٣٩٠/٨٢٠ · هدف أقل من ٤٤px (والأزرار ٥٢px في الموبايل) · تذكرة بلا زر رئيسي واحد بالضبط · أكثر من
بحث ظاهر · شريحة تمرّر جانبيًا في الموبايل · درج فيه زر رئيسي لا يستحوذ على السطر · نص عامي ظاهر في الشاشة الجديدة · نص فات طبقة النصوص
(`copy.missed`) · فرع درج في الكود لم يُفتح · «undefined/NaN/null» · أي طلب خارج الداشبورد. وبيكتب `copy-capture.json` (كل نص أصلي
مرّ على طبقة النصوص) عشان اختبار «لا مفاتيح ميتة» يقرأه.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import v2_fixtures as v2fx                      # noqa: E402
from ef_route_harness import Harness, DASH      # noqa: E402
import v2_shots as base                         # noqa: E402
from v2_shots import (Browsers, SHELL_READY, DESK, MOB, shell_check)  # noqa: E402

PROBLEMS = base.PROBLEMS
OUT = base.OUT
TAB = {'width': 820, 'height': 1180}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(_HERE)))
INDEX = os.path.join(ROOT, 'dashboard-cloud', 'index.html')

# فروع الدرج الموجودة في الكود ولم تُفتح هنا، وسبب كل واحد (تُنقل إلى STATUS)
UNCOVERED_OK = {}

MARKERS = ['مش ', 'دلوقتي', 'اتبعت', 'اتدفع', 'اتستلم', 'بتاع', 'عايز', 'هيت', 'ابعته', 'رجّع', 'مستني', 'لوحده', 'لوحدها', 'إيه', ' ليه',
           'كده', 'اللي', 'تاني', 'مالهاش', 'بقى', 'إزاي', 'خالص', 'يقوّم']
CAPTURE = set()
OPENED = set()
SEED_IDS = {}
RECEIPT_IDX = [0]

GRAB_JS = """() => { const c = window.V2SEC && V2SEC.home && V2SEC.home.copy; if (!c || !c.log) return []; const out = [...c.log]; c.log.clear(); return out; }"""

VIS = "const vis = e => !!e && !!(e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden' && getComputedStyle(e).display !== 'none';"


def hshot(page, name, kind='inbox', check_targets=True):
    """لقطة + فحوص الغلاف والجولة (§١٣)."""
    page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    base.shot(page, name)
    shell_check(page, name)
    home_check(page, name, kind, check_targets)
    grab(page)


def grab(page):
    try:
        for t in page.evaluate(GRAB_JS):
            if re.search(r'[؀-ۿ]', t):
                CAPTURE.add(t)
    except Exception:
        pass


def home_check(page, name, kind, check_targets):
    w = page.viewport_size['width']
    r = page.evaluate("""() => { %s
      const out = {};
      out.sw = Math.max(document.documentElement.scrollWidth, document.body.scrollWidth);
      out.small = check => [...document.querySelectorAll('button, [role=button], .v2h-chip, [role=tab]')].filter(vis)
        .map(b => [(b.className || b.tagName) + ':' + (b.textContent || '').trim().slice(0, 18), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 44);
      out.small = out.small(1);
      out.tickets = [...document.querySelectorAll('.v2h-t')].filter(vis).map(t => t.querySelectorAll('.v2h-btn1').length);
      out.stray = [...document.querySelectorAll('.v2h-btn1')].filter(b => !b.closest('.v2h-t') && !b.closest('.v2h-conf')).length;
      out.search = [...document.querySelectorAll('input[type=search], #q')].filter(vis).length;
      const f = document.getElementById('filters');
      out.fwide = f ? [...f.querySelectorAll('*')].filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX !== 'visible').map(e => e.className).slice(0, 3) : [];
      out.chips = [...document.querySelectorAll('.v2h-chip')].filter(vis).length;
      const acts = [...document.querySelectorAll('#drawer .acts')].filter(vis)[0];
      out.dom = null;
      if (acts) { const p = [...acts.querySelectorAll('.btn-primary, .btn-human')].filter(vis);
        if (p.length) { const aw = acts.getBoundingClientRect().width, pr = p[0].getBoundingClientRect();
          const others = [...acts.querySelectorAll('.btn')].filter(vis).filter(b => !p.includes(b)).map(b => b.getBoundingClientRect().width);
          out.dom = {pw: pr.width / aw, ow: others.map(x => x / aw), first: pr.top, otherTop: [...acts.querySelectorAll('.btn')].filter(vis).filter(b => !p.includes(b)).map(b => b.getBoundingClientRect().top)}; } }
      out.miss = window.V2SEC && V2SEC.home && V2SEC.home.copy && V2SEC.home.copy.missed ? [...V2SEC.home.copy.missed] : [];
      const zones = [...document.querySelectorAll('.v2h, #drawer, #epModal, #v2HBell, .v2-next, #epLogin')].filter(vis);
      out.text = zones.map(z => { const c = z.cloneNode(true);
        c.querySelectorAll('.ef-op').forEach(o => [...o.childNodes].forEach(n => { if (!(n.nodeType === 1 && n.classList.contains('meta'))) n.remove(); }));
        c.querySelectorAll('.ef-quote .row2, .ef-ms .row2, [data-nocopy], .v2h-sub, .v2h-brain, .v2h-ttl, .v2h-bl, textarea, input').forEach(n => n.remove());
        return c.innerText; }).join('\\n');
      out.small44 = 0;
      return out; }""" % VIS)
    if w <= 400 or w <= 830:
        if r['sw'] > w + 1:
            PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))
    if check_targets and r['small']:
        PROBLEMS.append('%s: أهداف أقل من ٤٤px: %r' % (name, r['small'][:4]))
    if w <= 400:
        small52 = page.evaluate("""() => { %s
          return [...document.querySelectorAll('.drawer .acts .btn, #epModal .acts .btn, .v2h-dbar button, .v2h-btn1, .v2h-btn2')].filter(vis)
            .map(b => [b.className + ':' + b.textContent.trim().slice(0, 14), Math.round(b.getBoundingClientRect().height)]).filter(x => x[1] < 52); }""" % VIS)
        if small52:
            PROBLEMS.append('%s: أزرار أقل من ٥٢px في الموبايل: %r' % (name, small52[:4]))
    if kind == 'inbox':
        bad = [n for n in r['tickets'] if n != 1]
        if bad or r['stray']:
            PROBLEMS.append('%s: تذكرة بلا زر رئيسي واحد بالضبط (%r) أو زر رئيسي شارد (%s)' % (name, bad[:3], r['stray']))
        if r['search'] != 1:
            PROBLEMS.append('%s: عدد خانات البحث الظاهرة %s (المطلوب واحدة)' % (name, r['search']))
        if w <= 400 and (r['fwide'] or r['chips']):
            PROBLEMS.append('%s: شرائح تمرّر جانبيًا أو صف شرائح ظاهر في الموبايل: %r / %s' % (name, r['fwide'], r['chips']))
    if r['dom']:
        d = r['dom']
        if d['pw'] < 0.9 or any(x >= 0.9 for x in d['ow']) or any(t <= d['first'] + 2 for t in d['otherTop']):
            PROBLEMS.append('%s: الزر الرئيسي في الدرج لا يستحوذ على سطره: %r' % (name, d))
    if r['miss']:
        PROBLEMS.append('%s: نصوص فاتت طبقة النصوص: %r' % (name, r['miss'][:5]))
    hits = [m for m in MARKERS if (re.search(r'(^|[^\u0621-\u064A])بقى', r['text']) if m == 'بقى' else m in r['text'])]
    if hits:
        ctxs = []
        for m in hits:
            i = r['text'].index(m)
            ctxs.append(r['text'][max(0, i - 25): i + 25].replace('\n', ' '))
        PROBLEMS.append('%s: نص عامي ظاهر %r — %r' % (name, hits[:4], ctxs[:3]))


# ----------------------------------------------------------------- مساعدات
def seed_dash(h):
    """رسالتان جديدتان وطلب سحب معلّق لمحفظة (للجرس) — في قاعدة الداشبورد المؤقتة."""
    import datetime
    m = h.app
    with m.app.app_context():
        w = m.InvestorWallet(investor_name='مستثمر تجريبي', balance=100.0)
        m.db.session.add(w)
        m.db.session.flush()
        m.db.session.add(m.WithdrawalRequest(wallet_id=w.id, amount=250.5, status='pending',
                                            requested_at=datetime.datetime.utcnow() - datetime.timedelta(hours=3)))
        ms = []
        for i, (nm, tp) in enumerate((('منى عادل', 'استفسار عن عقد'), ('كريم سمير', 'طلب شراكة'))):
            row = m.Message(name=nm, email='m%d@example.test' % i, topic=tp, body='نص الرسالة %d' % i, status='new',
                            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=i + 1))
            m.db.session.add(row)
            ms.append(row)
        m.db.session.commit()
        SEED_IDS['messages'] = [r.id for r in ms]


def set_messages_status(h, status):
    m = h.app
    with m.app.app_context():
        for r in m.Message.query.all():
            r.status = status
        m.db.session.commit()


def new_ctx(browser, h, vp, mobile, seen=None, anon=None):
    """سياق جديد. `anon` = None (مع توكن) أو {'flag': '1'|'0'|None} (بلا توكن، لشاشة الدخول)."""
    if anon is None:
        ctx = browser.context(h, 'admin', vp, mobile)
        if seen:
            ctx.add_init_script("try{localStorage.setItem('ep_v2h_seen',%s)}catch(e){}" % json.dumps(json.dumps(seen)))
        ctx.add_init_script("window.__v2hCap = true;")
        return ctx
    browser.close()
    browser.current = browser.p.chromium.launch(args=['--single-process'])
    opts = {'viewport': vp, 'locale': 'ar-EG'}
    if mobile:
        opts.update({'device_scale_factor': 2, 'is_mobile': True, 'has_touch': True})
    ctx = browser.current.new_context(**opts)
    if anon.get('flag') is not None:
        ctx.add_init_script("try{localStorage.setItem('ep_v2_shell','%s')}catch(e){}" % anon['flag'])
    ctx.route('**/*', h._route)
    return ctx


LIGHT_READY = "() => window.V2SHELL && V2SHELL.on === true && window.EP && ['inbox', 'opsQueue'].every(k => ['ready', 'error'].indexOf(EP.state[k]) > -1)"


def open_page(ctx, hash_, ready, shell_ready=SHELL_READY):
    last = None
    for attempt in (1, 2):
        page = ctx.new_page()
        page.set_default_timeout(10000)
        try:
            page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
            page.wait_for_function(shell_ready, timeout=30000)
            page.wait_for_function(ready, timeout=30000)
            page.wait_for_timeout(500)
            return page
        except Exception as e:      # noqa: BLE001 — تحميل بطيء: محاولة ثانية بصفحة جديدة
            last = e
            try:
                page.close()
            except Exception:
                pass
    raise last


INBOX_READY = "() => !!document.querySelector('.v2h') && (document.querySelector('.v2h-t') || document.querySelector('.v2h-empty'))"
BOARD_READY = "() => !!document.querySelector('.v2-tile') && !document.querySelector('.v2-cnt.ld') && !!document.querySelector('.v2h-healthline')"


def set_filter(page, f):
    page.evaluate("(f) => { activeFilter = f; selected = null; renderInbox(); }", f)
    page.wait_for_timeout(250)


def open_row(page, pred):
    """يفتح الصف الأول المطابق في الدرج (نفس مسار النقر) ويعيد رقمه؛ None لو لا صف."""
    n = page.evaluate("""(src) => { const f = new Function('r', 'return (' + src + ')');
      const i = INBOX.findIndex(r => { try { return f(r); } catch (e) { return false; } });
      if (i < 0) return -1;
      activeFilter = 'all'; selected = i; efDspOpen.id = null; efVoiceDrop(); efCaseUiReset(); renderInbox(); return i; }""", pred)
    page.wait_for_timeout(300)
    return n if n >= 0 else None


def inject(page, base_pred, patch):
    """يحقن صفًّا تركيبيًا (نسخة من أقرب صف في الفيكستشر + تعديل) في آخر INBOX ويعيد رقمه. بلا أي شبكة."""
    n = page.evaluate("""([src, patch]) => { const f = new Function('r', 'return (' + src + ')');
      const b = INBOX.find(r => { try { return f(r); } catch (e) { return false; } }) || INBOX[0];
      const c = JSON.parse(JSON.stringify(b));
      Object.assign(c, patch); c.apiId = 'syn-' + INBOX.length; c.synthetic = true;
      INBOX.push(c); return INBOX.length - 1; }""", [base_pred, patch])
    return n


def open_idx(page, i):
    page.evaluate("(i) => { activeFilter = 'all'; selected = i; efDspOpen.id = null; efVoiceDrop(); efCaseUiReset(); renderInbox(); }", i)
    page.wait_for_timeout(300)


def close_drawer(page):
    page.evaluate("() => { selected = null; efDspOpen.id = null; efVoiceDrop(); efCaseUiReset(); renderInbox(); }")
    page.wait_for_timeout(150)


def drawer_branches():
    """فروع الدرج من الكود نفسه (§٥.٣ خطوة ١): كل `apiKind===` و`efLane===` و`dsrc===` داخل دوال الدرج."""
    src = open(INDEX, encoding='utf-8').read()
    out = {'apiKind': set(), 'efLane': set(), 'dsrc': set()}
    for fn in ('drawInbox', 'inboxActs', 'drawExpertFile', 'drawDispute', 'drawCase', 'drawLegacy'):
        i = src.index('function ' + fn + '(')
        j = src.index('\nfunction ', i + 10)
        body = src[i:j]
        for k, rx in (('apiKind', r"apiKind\s*===?\s*'(\w+)'"), ('efLane', r"efLane\s*===?\s*'(\w+)'"), ('dsrc', r"dsrc\s*===?\s*'(\w+)'")):
            out[k].update(re.findall(rx, body))
    return out


# ----------------------------------------------------------------- الدخول والتحميل الأول
def flow_login(browser, h, pre, vp, mobile):
    # ٢٤) مسجَّل الخروج والمفتاح '1'
    ctx = new_ctx(browser, h, vp, mobile, anon={'flag': '1'})
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_selector('#epLogin')
    page.wait_for_timeout(400)
    cls = page.evaluate("() => document.documentElement.classList.contains('v2h-login')")
    if not cls:
        PROBLEMS.append(pre + '24: شاشة الدخول بلا الشكل الجديد والمفتاح مخزَّن «1»')
    login_shot(page, pre + '24-login.jpg')
    # ٢٤ب) جهاز جديد: لا مفتاح مخزَّن ⇒ الشكل الجديد
    ctx = new_ctx(browser, h, vp, mobile, anon={'flag': None})
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_selector('#epLogin')
    page.wait_for_timeout(400)
    if not page.evaluate("() => document.documentElement.classList.contains('v2h-login') && localStorage.getItem('ep_v2_shell') === null"):
        PROBLEMS.append(pre + '24b: جهاز جديد بلا مفتاح مخزَّن لا يرى الشكل الجديد')
    login_shot(page, pre + '24b-login-fresh.jpg')
    # ٢٥) كلمة مرور خطأ
    page.fill('#epEmail', 'admin@local.test')
    page.fill('#epPass', 'wrong-password')
    page.click('#epLoginBtn')
    page.wait_for_selector('#epLoginErr.show')
    page.wait_for_timeout(300)
    txt = page.inner_text('#epLoginErr').strip()
    if txt != 'بيانات الدخول غير صحيحة.':
        PROBLEMS.append(pre + '25: رسالة الخطأ «%s»' % txt)
    login_shot(page, pre + '25-login-error.jpg')


def login_shot(page, name):
    base.shot(page, name)
    w = page.viewport_size['width']
    r = page.evaluate("""() => { %s
      const c = document.querySelector('#epLogin .card'), inputs = [...document.querySelectorAll('#epLogin input, #epLogin button')].filter(vis);
      return {sw: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.getElementById('epLogin') || {}).scrollWidth || 0),
              hs: inputs.map(i => [i.id || i.tagName, Math.round(i.getBoundingClientRect().height)]), txt: document.getElementById('epLogin').innerText}; }""" % VIS)
    if r['sw'] > w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, r['sw'], w))
    if any(x[1] < 44 for x in r['hs']) or (w <= 400 and any(x[1] < 52 for x in r['hs'])):
        PROBLEMS.append('%s: هدف أقل من الحد: %r' % (name, r['hs']))
    for m in MARKERS:
        if m in r['txt']:
            PROBLEMS.append('%s: نص عامي «%s» في شاشة الدخول' % (name, m))


def flow_splash(browser, h, pre, vp, mobile):
    """التحميل الأول: `.v2-pre` ظاهر والرد على `/api/v2/config` محجوز. مهلة الثلاث ثواني في الصفحة (الاحتياط) بتتعطّل هنا فقط
    عشان اللقطة تاخد وقتها — الرد بعد الإفراج بيفتح اللوحة عادي."""
    ctx = browser.context(h, 'admin', vp, mobile)
    ctx.add_init_script("try{localStorage.setItem('ep_v2_shell','1')}catch(e){}"
                        "const __st = window.setTimeout; window.setTimeout = function (f, ms) { return __st.apply(this, [f, ms === 3000 ? 600000 : ms].concat([].slice.call(arguments, 2))); };")
    h.hold.add(('GET', '/api/v2/config'))
    page = None
    try:
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_selector('.app.v2-pre', timeout=15000)
        page.wait_for_timeout(400)
        txt = page.evaluate("() => getComputedStyle(document.querySelector('.app'), '::after').content")
        if 'جارٍ فتح لوحتك' not in txt:
            PROBLEMS.append(pre + '26: نص التحميل الأول مش ظاهر: %r' % txt)
        base.shot(page, pre + '26-splash.jpg')
    finally:
        h.hold.discard(('GET', '/api/v2/config'))
        h.release_held()
    if page is not None:
        page.wait_for_function(SHELL_READY, timeout=30000)
        if page.evaluate("() => !!document.querySelector('.app.v2-pre')"):
            PROBLEMS.append(pre + '26: صنف التحميل الأول ما اتشالش بعد الرد')


# ----------------------------------------------------------------- الجرس واللوحة
def flow_board_bell(browser, h, pre, vp, mobile):
    w = vp['width']
    seen = ['message:%d' % SEED_IDS['messages'][1]]
    # ٠١) لوحة بلا تنبيهات صحة: سطر «كل شيء يعمل» في الشريط الداكن، بلا الصف اليتيم
    q = h.ef.queue()
    q['alerts'] = []
    h.ef.forced[('GET', '/api/bridge/ops/queue')] = (200, q)
    ctx = new_ctx(browser, h, vp, mobile, seen=seen)
    page = open_page(ctx, '#s/home/board', BOARD_READY)
    info = page.evaluate("""() => { %s
      return {head: [...document.querySelectorAll('.v2-head')].filter(vis).length, line: (document.querySelector('.v2h-healthline') || {}).textContent,
              inside: !!document.querySelector('.v2-nt .v2h-healthline'), dark: !!document.querySelector('.v2-next')}; }""" % VIS)
    if info['head'] or not info['inside'] or 'كل شيء يعمل' not in (info['line'] or ''):
        PROBLEMS.append('%s01: اللوحة: صف الصحة اليتيم أو السطر الصحي %r' % (pre, info))
    hshot(page, pre + '01-board.jpg', 'board')
    # ٠٢) تنبيهات الصحة: السطر كهرماني
    del h.ef.forced[('GET', '/api/bridge/ops/queue')]
    page.reload(wait_until='domcontentloaded')
    page.wait_for_function(SHELL_READY, timeout=30000)
    page.wait_for_function(BOARD_READY, timeout=30000)
    page.wait_for_timeout(500)
    line = page.inner_text('.v2h-healthline')
    if 'تنبيه' not in line:
        PROBLEMS.append('%s02: سطر الصحة مع التنبيهات: «%s»' % (pre, line))
    hshot(page, pre + '02-board-health-alerts.jpg', 'board')
    # ٠٣) الجرس: حالة المنصة + ٣ إشعارات (واحد مقروء) + النبضات
    page.wait_for_function("() => V2SEC.home.bell.notif.state === 'ready'", timeout=15000)
    page.wait_for_timeout(300)
    bx = page.evaluate("""() => { const bb = document.getElementById('bellBtn'), n = bb.querySelector('.v2h-bn'); if (!n) return null;
      const r = bb.getBoundingClientRect(), nr = n.getBoundingClientRect(), cs = getComputedStyle(bb, '::after');
      const dot = cs.content && cs.content !== 'none' ? {l: r.left + bb.clientLeft + parseFloat(cs.left), t: r.top + bb.clientTop + parseFloat(cs.top), w: parseFloat(cs.width) + 4, h: parseFloat(cs.height) + 4} : null;
      return {num: n.textContent, hd: bb.classList.contains('v2h-hd'), n: [nr.left, nr.top, nr.right, nr.bottom], dot, btn: [r.left, r.top, r.right, r.bottom]}; }""")
    if not bx or not bx['num'] or not bx['hd'] or not bx['dot']:
        PROBLEMS.append('%s02: شارة الجرس: المطلوب عدّ + نقطة صحة معًا: %r' % (pre, bx))
    else:
        d = bx['dot']; n = bx['n']
        if d['l'] < n[2] and d['l'] + d['w'] > n[0] and d['t'] < n[3] and d['t'] + d['h'] > n[1]:
            PROBLEMS.append('%s02: نقطة الصحة تغطي رقم الجرس: %r' % (pre, bx))
    bc = bx['btn'] if bx else [0, 0, 60, 60]
    page.screenshot(path=os.path.join(OUT, pre + '03b-bell-badge-crop.jpg'), type='jpeg', quality=88,
                    clip={'x': max(0, bc[0] - 20), 'y': max(0, bc[1] - 14), 'width': 90, 'height': 74})
    page.click('#bellBtn')
    page.wait_for_selector('#v2HBell.open')
    page.wait_for_timeout(400)
    b = page.evaluate("""() => ({badge: (document.querySelector('.v2h-bn') || {}).textContent, items: document.querySelectorAll('.v2h-ni').length,
      unseen: document.querySelectorAll('.v2h-ni.unseen').length, alerts: document.querySelectorAll('.v2h-al').length, hb: document.querySelectorAll('.v2h-hb li').length,
      label: document.getElementById('bellBtn').getAttribute('aria-label'), z: [getComputedStyle(document.getElementById('v2HBell')).zIndex, getComputedStyle(document.getElementById('v2HBellScrim')).zIndex]})""")
    if b['items'] < 3 or b['unseen'] < 1 or b['unseen'] >= b['items'] or not b['alerts'] or not b['hb'] or b['z'] != ['78', '77']:
        PROBLEMS.append('%s03: الجرس: %r' % (pre, b))
    hshot(page, pre + '03-bell-open.jpg', 'board')
    # الإغلاق بـEscape يرجع التركيز للجرس
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)
    if page.evaluate("() => !!document.querySelector('#v2HBell.open')") or page.evaluate("() => document.activeElement && document.activeElement.id") != 'bellBtn':
        PROBLEMS.append(pre + '03: Escape ما قفلش الجرس أو التركيز ما رجعش')
    # فتحه من سطر الصحة في الشريط الداكن
    page.click('.v2h-healthline')
    page.wait_for_selector('#v2HBell.open')
    page.click('#v2HBell [data-a="bclose"]')
    page.wait_for_timeout(150)
    # ٠٤) المصدران فاشلان: «!» وفشلان نصّيان
    h.ef.forced[('GET', '/api/bridge/ops/queue')] = (503, {'error': 'down'})
    ctx = new_ctx(browser, h, vp, mobile)
    page = ctx.new_page()
    page.route('**/api/notifications', lambda r: r.fulfill(status=500, content_type='application/json', body='{"error":"x"}'))
    page.goto(DASH + '/#s/home/board', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2SHELL && V2SHELL.on === true && EP.state.opsQueue === 'error' && V2SEC.home.bell.notif.state === 'error'", timeout=30000)
    page.wait_for_timeout(600)
    bb = page.evaluate("() => [document.querySelector('.v2h-bn').textContent, document.querySelector('.v2h-bn').className, document.getElementById('bellBtn').getAttribute('aria-label')]")
    if bb[0] != '!' or 'tone-warn' not in bb[1]:
        PROBLEMS.append('%s04: شارة الجرس والمصدران فاشلان: %r' % (pre, bb))
    page.click('#bellBtn')
    page.wait_for_selector('#v2HBell.open')
    page.wait_for_timeout(300)
    t = page.inner_text('#v2HBell')
    for need in ('تعذّر فحص حالة المنصة — لا تعتبرها سليمة', 'تعذّر جلب الإشعارات'):
        if need not in t:
            PROBLEMS.append('%s04: نص الفشل «%s» ناقص' % (pre, need))
    hshot(page, pre + '04-bell-failed.jpg', 'board')
    del h.ef.forced[('GET', '/api/bridge/ops/queue')]


def settle(page):
    """ينتظر انتهاء التمرير السلس قبل اللقطة."""
    prev = None
    for _ in range(25):
        cur = page.evaluate("""() => { const c = document.querySelector('.content'); const q = document.getElementById('v2hQueue');
          return [Math.round(scrollY), c ? Math.round(c.scrollTop) : 0, q ? Math.round(q.getBoundingClientRect().top) : 0]; }""")
        if cur == prev:
            return
        prev = cur
        page.wait_for_timeout(150)


def queue_shot(page, name, need=None):
    """لقطة «أرقام المنصة» وهي في مجال الرؤية فعلًا (لا نعود إلى أعلى الصفحة كما يفعل hshot)."""
    settle(page)
    page.evaluate("() => { const d = document.getElementById('v2hQueue'); if (d) d.scrollIntoView({block: 'start', behavior: 'auto'}); }")
    page.wait_for_timeout(250)
    r = page.evaluate("""() => { const d = document.getElementById('v2hQueue').getBoundingClientRect(); return [Math.round(d.top), Math.round(d.bottom), innerHeight, document.getElementById('v2hQueue').innerText]; }""")
    if not (0 <= r[0] < r[2]) or r[1] <= 0:
        PROBLEMS.append('%s: لوحة «أرقام المنصة» ليست في مجال الرؤية (%s..%s من %s)' % (name, r[0], r[1], r[2]))
    if need and need not in r[3]:
        PROBLEMS.append('%s: النص المتوقع «%s» غير موجود: %r' % (name, need, r[3][:80]))
    base.shot(page, name)
    shell_check(page, name)
    home_check(page, name, 'inbox', True)
    grab(page)


# ----------------------------------------------------------------- كل الوارد
def flow_inbox(browser, h, pre, vp, mobile):
    w = vp['width']
    ctx = new_ctx(browser, h, vp, mobile)
    page = open_page(ctx, '#s/home/inbox', INBOX_READY)
    # ٠٥) كله
    hshot(page, pre + '05-inbox-all.jpg')
    if w <= 400:
        top = page.evaluate("() => { const t = document.querySelector('.v2h-t'); return t ? Math.round(t.getBoundingClientRect().top) : null; }")
        if top is None or top > 600:
            PROBLEMS.append('%s05: أول تذكرة تبدأ عند %s px في الموبايل (المطلوب أقل من ٦٠٠)' % (pre, top))
    info = page.evaluate("""() => ({bl: !!document.querySelector('.v2h-bl'), auto: !!document.querySelector('.v2h-auto'), fyi: document.querySelectorAll('.v2h-strip').length,
      groups: [...document.querySelectorAll('.v2h-g')].map(g => g.dataset.grp), top: document.getElementById('inboxN').textContent, queue: !!document.getElementById('v2hQueue')})""")
    if not (info['bl'] and info['auto'] and info['queue']):
        PROBLEMS.append('%s05: عناصر الشاشة الناقصة %r' % (pre, info))
    if w > 760 and info['groups'][:2] != ['late', 'wait']:
        PROBLEMS.append('%s05: ترتيب المجموعات %r' % (pre, info['groups']))
    # ٠٥ب) شارات الصف القديم وسطر وقوف الأموال ظاهرة في التذكرة نفسها
    fl = None
    for g in (('late', 'wait', 'auto') if mobile else (None,)):
        if g:
            page.click('.v2h-segb[data-g="%s"]' % g)
            page.wait_for_timeout(150)
        fl = page.evaluate("""() => { const e = document.querySelector('.v2h-warn') || document.querySelector('.v2h-flag.w'); if (!e) return null;
          e.closest('.v2h-t').scrollIntoView({block: 'center', behavior: 'auto'});
          return {warn: document.querySelectorAll('.v2h-warn').length, w: document.querySelectorAll('.v2h-flag.w').length, flags: document.querySelectorAll('.v2h-flag').length}; }""")
        if fl:
            break
    if not fl or not fl['warn'] or not fl['w']:
        PROBLEMS.append('%s05b: شارات التذكرة (تحذيرية) أو سطر وقوف الأموال لم تظهر: %r' % (pre, fl))
    else:
        page.wait_for_timeout(250)
        base.shot(page, pre + '05b-ticket-flags.jpg')
        shell_check(page, pre + '05b-ticket-flags.jpg')
        grab(page)
    if mobile:
        page.click('.v2h-segb[data-g="late"]')
        page.evaluate("() => { const c = document.querySelector('.content'); if (c) c.scrollTop = 0; window.scrollTo(0, 0); }")
    # شريط الموبايل: كل جزء مرة (٢٧) ثم ورقة النوع (٢٨)
    if mobile:
        for g, nm in (('late', 'a'), ('wait', 'b'), ('auto', 'c')):
            page.click('.v2h-segb[data-g="%s"]' % g)
            page.wait_for_timeout(200)
            if g != 'auto':
                hshot(page, pre + '27%s-inbox-mobile-bar-%s.jpg' % (nm, g))
            else:
                base.shot(page, pre + '27%s-inbox-mobile-bar-%s.jpg' % (nm, g))
        page.click('.v2h-segb[data-g="wait"]')
        page.click('.v2h-typebtn')
        page.wait_for_selector('.v2h.types-open #v2hTypes')
        page.wait_for_timeout(250)
        hshot(page, pre + '28-inbox-type-sheet-home.jpg')
        # اختيار نوع من الورقة يغلقها ويرشّح
        page.click('#v2hTypes .v2h-trow[data-f="t:files"]')
        page.wait_for_timeout(250)
        if page.evaluate("() => !!document.querySelector('.v2h.types-open')") or page.evaluate("() => activeFilter") != 't:files':
            PROBLEMS.append(pre + '28: اختيار النوع ما أغلقش الورقة أو ما رشّحش')
        set_filter(page, 'all')
        # Escape يغلق الورقة
        page.click('.v2h-typebtn')
        page.keyboard.press('Escape')
        page.wait_for_timeout(150)
        if page.evaluate("() => !!document.querySelector('.v2h.types-open')"):
            PROBLEMS.append(pre + '28: Escape ما أغلقش ورقة النوع')
    # ٠٦) متأخر
    set_filter(page, 'late')
    hshot(page, pre + '06-inbox-late.jpg')
    set_filter(page, 'all')
    # ٠٨) بحث «عقد»
    page.fill('#v2hq', 'عقد')
    page.wait_for_timeout(450)
    n = page.evaluate("() => document.querySelectorAll('.v2h-t').length")
    if not n:
        PROBLEMS.append(pre + '08: بحث «عقد» ما رجّعش شيء')
    hshot(page, pre + '08-inbox-search.jpg')
    # ٠٩) لا تطابق
    page.fill('#v2hq', 'غغغغغ')
    page.wait_for_timeout(450)
    if 'لا بنود تطابق «غغغغغ»' not in page.inner_text('#rows'):
        PROBLEMS.append(pre + '09: رسالة «لا بنود تطابق» ناقصة')
    hshot(page, pre + '09-inbox-nomatch.jpg')
    page.click('[data-a="clearq"]')
    page.wait_for_timeout(300)
    if page.input_value('#v2hq') != '':
        PROBLEMS.append(pre + '09: «امسح البحث» ما مسحش')
    # ٠٧) كل الملفات: شرائح فرعية، و«متأخر» لا تحرّك الترويسة
    page.evaluate("() => { location.hash = '#s/files/all'; }")
    page.wait_for_function("() => document.querySelector('.v2c-h h1') && document.querySelector('.v2c-h h1').textContent === 'ملفات الخبراء' && document.querySelector('.v2h[data-ctx=\"files\"]')", timeout=15000)
    page.wait_for_timeout(400)
    sub = page.evaluate("() => document.querySelectorAll('.v2h-chips.sub .v2h-chip').length")
    if not mobile and not sub:
        PROBLEMS.append(pre + '07: الشرائح الفرعية للملفات مش ظاهرة')
    hshot(page, pre + '07-inbox-files-sub.jpg')
    if not mobile:
        page.click('.v2h-chip[data-f="late"]')
        page.wait_for_timeout(300)
        hh = page.evaluate("() => [location.hash, document.querySelector('.v2c-h h1').textContent]")
        if hh != ['#s/files/all', 'ملفات الخبراء']:
            PROBLEMS.append('%s07: شريحة «متأخر» حرّكت الترويسة: %r' % (pre, hh))
        set_filter(page, 't:files')
    else:
        page.click('.v2h-typebtn')
        page.wait_for_selector('.v2h.types-open')
        page.wait_for_timeout(250)
        hshot(page, pre + '28b-inbox-type-sheet-files.jpg')
        page.keyboard.press('Escape')
    # ٢١) كل النزاعات · ٢٢) الرسائل
    page.evaluate("() => { location.hash = '#s/disputes/all'; }")
    page.wait_for_function("() => document.querySelector('.v2h[data-ctx=\"disputes\"]')", timeout=15000)
    page.wait_for_timeout(400)
    hshot(page, pre + '21-disputes-all.jpg')
    page.evaluate("() => { location.hash = '#s/people/messages'; }")
    page.wait_for_function("() => document.querySelector('.v2h[data-ctx=\"messages\"]')", timeout=15000)
    page.wait_for_timeout(400)
    ch = page.evaluate("() => document.querySelectorAll('.v2h-chips .v2h-chip').length")
    if ch:
        PROBLEMS.append(pre + '22: شرائح في شاشة الرسائل (المطلوب بلا شرائح)')
    hshot(page, pre + '22-messages.jpg')
    # ٢٠) أرقام المنصة
    page.evaluate("() => { location.hash = '#s/home/inbox'; }")
    page.wait_for_function("() => document.querySelector('.v2h[data-ctx=\"home\"]')", timeout=15000)
    page.wait_for_timeout(300)
    page.click('.v2h-qlink')
    if not page.evaluate("() => document.getElementById('v2hQueue').open"):
        PROBLEMS.append(pre + '20: «أرقام المنصة» ما فتحتش')
    nq = page.evaluate("() => document.querySelectorAll('.v2h-qb').length")
    if not nq:
        PROBLEMS.append(pre + '20: «أرقام المنصة» فاضية')
    queue_shot(page, pre + '20-queue-open.jpg')
    # حالتا الصفر والفشل (تُفرضان في الصفحة نفسها لأن الطابور قراءة فقط)
    page.evaluate("() => { window.__qc = window.opsQueueCounters; window.opsQueueCounters = () => []; V2SEC.home.list(); }")
    queue_shot(page, pre + '20b-queue-zero.jpg', need='لا أرقام تنتظرك الآن')
    page.evaluate("() => { window.opsQueueCounters = window.__qc; EP.state.opsQueue = 'error'; V2SEC.home.list(); }")
    queue_shot(page, pre + '20c-queue-failed.jpg', need='تعذّر جلب أرقام المنصة')
    page.evaluate("() => { EP.state.opsQueue = 'ready'; V2SEC.home.list(); }")
    # ١٨) أوقفه: التأكيد داخل الصفحة (بلا إرسال)
    page.evaluate("() => { document.getElementById('v2hQueue').open = false; window.scrollTo(0, 0); }")
    page.click('[data-a="auto_off"]')
    page.wait_for_selector('.v2h-conf')
    page.wait_for_timeout(200)
    hshot(page, pre + '18-auto-off-confirm.jpg')
    page.click('[data-a="auto_x"]')
    page.wait_for_timeout(200)
    # ١٩) للعلم
    page.click('[data-a="fyi_on"]')
    page.wait_for_timeout(350)
    if page.evaluate("() => activeFilter") != 'fyi':
        PROBLEMS.append(pre + '19: «اعرضها» ما فتحتش وضع للعلم')
    hshot(page, pre + '19-fyi.jpg')
    page.click('[data-a="fyi_back"]')
    page.wait_for_timeout(250)
    # ١٢) لا شيء في الفلتر ⇒ «اعرض الكل»
    set_filter(page, 't:verify')
    if 'لا بنود في هذا الاختيار' not in page.inner_text('#rows'):
        PROBLEMS.append(pre + '12b: رسالة «لا بنود في هذا الاختيار» ناقصة')
    page.click('[data-a="showall"]')
    page.wait_for_timeout(250)
    # التذكرة تفتح الدرج بلا تنفيذ
    set_filter(page, 'all')
    page.wait_for_selector('.v2h-t')


# ----------------------------------------------------------------- الدرج: كل فرع
BRANCH_PLAN = [
    # (اسم, شرط الصف JS | None للحقن, تعديل الحقن)
    ('file-waiting', "r.apiKind === 'expert_file' && r.efLane === 'waiting' && r.triage === 'human'", None),
    ('file-unactivated', "r.apiKind === 'expert_file' && r.unact", None),
    ('file-blocked', "r.apiKind === 'expert_file' && r.needsAttention && !r.unact", None),
    ('file-late', "r.apiKind === 'expert_file' && r.efLane === 'late'", None),
    ('file-review', "r.apiKind === 'expert_file' && r.efLane === 'review'", None),
    ('case', "r.apiKind === 'expert_file' && r.efLane === 'case_disputed'", None),
    ('dispute-consultation', "r.apiKind === 'dispute' && r.dsrc === 'consultation'", None),
    ('dispute-file', "r.apiKind === 'dispute' && r.dsrc === 'file'", None),
    ('legacy', "r.apiKind === 'legacy'", None),
    ('manual-payment', "r.apiKind === 'manual_payment'", None),
    ('trainer', "r.apiKind === 'trainer'", None),
    ('founding', "r.apiKind === 'founding'", None),
    ('pending-user', "r.apiKind === 'pending_user'", None),
    ('join-licensed', "r.apiKind === 'join'", None),
    ('book', "r.apiKind === 'book'", None),
    ('topic', "r.apiKind === 'topic'", None),
    ('lead-resolve', "r.apiKind === 'lead' && r.resolve", None),
]
SYNTHETIC = [
    ('verify', "r.apiKind === 'trainer'", {'apiKind': 'verify', 'candidates': [{'email': 'a@x.test', 'name': 'أ. خبير'}], 'dest': 'inbox'}),
    ('join-licence-missing', "r.apiKind === 'join'", {'licenceMissing': True, 'licensed': True, 'canRequestInfo': True, 'canReject': True, 'rejectNeedsReason': True,
                                                      'licenceNote': ''}),
    ('triage-auto', "r.apiKind === 'trainer'", {'triage': 'auto'}),
    ('program', "r.apiKind === 'trainer'", {'apiKind': 'program', 'dest': 'courses'}),
    ('plain-row', "r.apiKind === 'trainer'", {'apiKind': '', 'dest': 'users'}),
]


def flow_drawers(browser, h, pre, vp, mobile):
    w = vp['width']
    ctx = new_ctx(browser, h, vp, mobile)
    page = open_page(ctx, '#s/home/inbox', INBOX_READY)
    covered = set()
    kinds = {}

    def note_open(label):
        d = page.evaluate("""() => { const i = INBOX[selected] || {}; return [i.apiKind || '', i.efLane || '', i.dsrc || '']; }""")
        covered.add(('apiKind', d[0]))
        if d[1]:
            covered.add(('efLane', d[1]))
        if d[2]:
            covered.add(('dsrc', d[2]))
        kinds[label] = d

    shots = {'file-waiting': '13-drawer-file', 'dispute-consultation': '14-drawer-dispute', 'join-licensed': '15-drawer-join'}
    for label, pred, patch in BRANCH_PLAN:
        n = open_row(page, pred)
        if n is None:
            PROBLEMS.append('%s: لا صف في الفيكستشر لفرع الدرج «%s»' % (pre, label))
            continue
        OPENED.add(label)
        note_open(label)
        if label in shots:
            hshot(page, pre + shots[label] + '.jpg', 'drawer')
        else:
            grab(page)
            drawer_miss(page, pre, label)
    for label, base_pred, patch in SYNTHETIC:
        n = inject(page, base_pred, patch)
        open_idx(page, n)
        OPENED.add(label)
        note_open(label)
        grab(page)
        drawer_miss(page, pre, label)
        if label == 'join-licence-missing':
            hshot(page, pre + '15b-drawer-join-licence-missing.jpg', 'drawer')
            # تحقّق بلا كتابة: «رفض» بلا سبب ⇒ تنبيه فقط
            page.click('#drawer [data-a="reject"]')
            page.wait_for_timeout(250)
            grab(page)
            if not page.evaluate("() => !!document.querySelector('#toasts .toast')"):
                PROBLEMS.append(pre + '15b: تنبيه «اكتب سبب الرفض» ما ظهرش')
            drawer_miss(page, pre, 'reject-toast')
    # رسالة الموقع (من الجدول المحلي)
    n = open_row(page, "r.dest === 'messages' && r.msgSource === 'site'")
    if n is not None:
        OPENED.add('site-message')
        note_open('site-message')
        grab(page)
        drawer_miss(page, pre, 'site-message')
    else:
        PROBLEMS.append(pre + ': لا رسالة موقع في الوارد')
    # الغطاء: كل فرع في الكود لازم يكون اتفتح
    br = drawer_branches()
    for k in ('apiKind', 'efLane', 'dsrc'):
        for v in sorted(br[k]):
            if (k, v) not in covered and '%s=%s' % (k, v) not in UNCOVERED_OK:
                PROBLEMS.append('%s: فرع الدرج %s===\'%s\' في الكود ولم يُفتح' % (pre, k, v))
    # النوافذ (بلا إرسال): الاسترداد · اختيار الخبير · مقارنة الرأيين · قرار القضية · قرار الاستشارة القديمة · فحص المسح · تأكيد الدفعة
    modal_flows(page, pre, w)


def drawer_miss(page, pre, label):
    miss = page.evaluate("() => [...V2SEC.home.copy.missed]")
    if miss:
        PROBLEMS.append('%s: [%s] نصوص فاتت طبقة النصوص: %r' % (pre, label, miss[:6]))
        page.evaluate("() => V2SEC.home.copy.missed.clear()")


def open_modal_via(page, pred, selector, name, pre, shotname=None):
    n = open_row(page, pred)
    if n is None:
        PROBLEMS.append('%s: لا صف للنافذة «%s»' % (pre, name))
        return False
    btn = page.query_selector('#drawer ' + selector)
    if not btn or not btn.is_visible():
        PROBLEMS.append('%s: زر النافذة «%s» غير موجود (%s)' % (pre, name, selector))
        return False
    if btn.is_disabled():
        OPENED.add('modal-' + name + '-disabled')
        grab(page)
        drawer_miss(page, pre, 'modal-' + name)
        return True
    try:
        btn.click(timeout=4000)
    except Exception:
        page.evaluate("(b) => b.click()", btn)
    try:
        page.wait_for_selector('#epModal, .ef-conf', timeout=8000)
    except Exception:
        PROBLEMS.append('%s: النافذة «%s» لم تفتح' % (pre, name))
        return False
    page.wait_for_timeout(450)
    OPENED.add('modal-' + name)
    if shotname:
        hshot(page, pre + shotname + '.jpg', 'drawer')
    else:
        grab(page)
    drawer_miss(page, pre, 'modal-' + name)
    page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
    close_drawer(page)
    return True


def modal_flows(page, pre, w):
    open_modal_via(page, "r.apiKind === 'manual_payment'", '[data-a="approve"]', 'pay-ok', pre, '16-drawer-receipt-modal')
    open_modal_via(page, "r.apiKind === 'expert_file' && r.efLane === 'waiting' && r.triage === 'human'", '[data-a="ef_refund"]', 'refund', pre, '17-drawer-refund-modal')
    open_modal_via(page, "r.apiKind === 'expert_file' && r.efLane === 'waiting' && r.triage === 'human'", '[data-a="ef_pick"]', 'pick', pre)
    open_modal_via(page, "r.apiKind === 'dispute' && r.dsrc === 'file'", '[data-a="dsp_cmp"]', 'compare', pre)
    for sel, pred, nm in (('[data-a="dsp_ref"]', "r.apiKind === 'dispute' && r.dsrc === 'file'", 'dispute-refund'),
                          ('[data-a="dsp_rel"]', "r.apiKind === 'dispute' && r.dsrc === 'file'", 'dispute-release')):
        open_modal_via(page, pred, sel, nm, pre)
    for sel, pred, nm in (('[data-a="lg_ref"]', "r.apiKind === 'legacy'", 'legacy-refund'), ('[data-a="lg_rel"]', "r.apiKind === 'legacy'", 'legacy-release'),
                          ('[data-a="rv_ok"]', "r.apiKind === 'expert_file' && r.efLane === 'review'", 'review-ok'), ('[data-a="rv_back"]', "r.apiKind === 'expert_file' && r.efLane === 'review'", 'review-back')):
        open_modal_via(page, pred, sel, nm, pre)
    # قرار القضية والاستشارة القديمة: أول زر قرار ظاهر
    for pred, nm in (("r.apiKind === 'expert_file' && r.efLane === 'case_disputed'", 'case'), ("r.apiKind === 'legacy'", 'legacy')):
        n = open_row(page, pred)
        if n is None:
            continue
        btns = page.query_selector_all('#drawer .acts .btn:not([data-a="ef_close"]):not([data-a="cs_close"]):not([data-a="lg_close"])')
        for b in btns:
            if b.is_visible() and b.get_attribute('data-a') and 'close' not in (b.get_attribute('data-a') or ''):
                b.click()
                page.wait_for_timeout(500)
                OPENED.add('flow-' + nm)
                grab(page)
                if page.query_selector('#epModal'):
                    page.evaluate("() => document.getElementById('epModal').remove()")
                drawer_miss(page, pre, 'flow-' + nm)
                break
        close_drawer(page)
    # فحص المسح للزائر (بدون تنفيذ المسح)
    n = open_row(page, "r.apiKind === 'pending_user' && r.canPurge")
    if n is not None:
        b = page.query_selector('#drawer [data-a="purge"]')
        if b:
            b.click()
            page.wait_for_timeout(600)
            OPENED.add('modal-purge')
            grab(page)
            if page.query_selector('#epModal'):
                page.evaluate("() => document.getElementById('epModal').remove()")
            drawer_miss(page, pre, 'modal-purge')


# ----------------------------------------------------------------- الزر الرئيسي في التذكرة (١٣ب) وزر التركيز (٢٣)
def reveal_btn(page, idx, mobile):
    """يظهر زر تذكرة الصف `idx` (على الموبايل بتبديل المقطع المناسب) ويعيد محدّده."""
    sel = '.v2h-btn1[data-i="%d"]' % idx
    set_filter(page, 'all')
    page.fill('#v2hq', '')
    if page.evaluate("(s) => { const b = document.querySelector(s); return !!(b && b.getClientRects().length); }", sel):
        return sel
    if mobile:
        for g in ('late', 'wait', 'auto'):
            page.click('.v2h-segb[data-g="%s"]' % g)
            page.wait_for_timeout(150)
            if page.evaluate("(s) => { const b = document.querySelector(s); return !!(b && b.getClientRects().length); }", sel):
                return sel
    return sel


def flow_ticket_btn(browser, h, pre, vp, mobile):
    w = vp['width']
    ctx = new_ctx(browser, h, vp, mobile)
    page = open_page(ctx, '#s/home/inbox', INBOX_READY)
    n0 = len(h.dash_calls)
    for kind, expect, pred in (("manual_payment", 'approve', "r.apiKind === 'manual_payment'"),
                               ("expert_file", 'ef_pick', "r.apiKind === 'expert_file' && r.efLane === 'waiting' && r.triage === 'human' && !r.fyi")):
        idx = page.evaluate("(src) => { const f = new Function('r', 'return (' + src + ')'); return INBOX.findIndex(r => f(r)); }", pred)
        if kind == 'manual_payment':
            RECEIPT_IDX[0] = idx
        sel = reveal_btn(page, idx, mobile)
        page.click(sel)
        page.wait_for_timeout(700)
        if kind == 'expert_file':
            # «انقله/أرسله إلى فلان»: قائمة الاختيار الموجودة تُفتح والخبير المقترح محدَّد فيها (الإرسال بزرّها هي، لا من هنا)
            sug = page.evaluate("(i) => { const c = V2L.v2Card(INBOX[i], {now: Date.now()}); return c && c.primary && c.primary.act && (c.primary.act.name || c.primary.act.email) || null; }", idx)
            pk = page.evaluate("() => { const m = document.getElementById('epModal'); if (!m) return null; const on = m.querySelector('.ef-cand input:checked');"
                               " const go = m.querySelector('#ep_go'); return {pick: on ? on.closest('.ef-cand').querySelector('.nm').textContent.trim() : null, go: go && go.textContent.trim(), dis: go && go.disabled}; }")
            if not sug or not pk or pk['pick'] != sug or pk['dis'] or sug not in (pk['go'] or ''):
                PROBLEMS.append('%s13b: زر التذكرة (ملف) ما حدّدش الخبير المقترح في القائمة: مقترح=%r قائمة=%r' % (pre, sug, pk))
            hshot(page, pre + '13b-ticket-btn-file.jpg', 'drawer', check_targets=False)
            page.evaluate("() => { const m = document.getElementById('epModal'); if (m) m.remove(); }")
        else:
            got = page.evaluate("() => { const a = document.activeElement; return [a && a.getAttribute('data-a'), !!(a && a.classList.contains('v2h-hl')), selected]; }")
            if got[0] != expect:
                PROBLEMS.append('%s13b: زر التذكرة (%s) ركّز على %r والمتوقع %s' % (pre, kind, got, expect))
            hshot(page, pre + '13b-ticket-btn-receipt.jpg', 'inbox')
            if page.query_selector('#epModal'):
                PROBLEMS.append(pre + '13b: ضغط زر الإيصال فتح نافذة (المفروض يفتح الدرج فقط)')
        if kind == 'manual_payment':
            # «أكّد» في الدرج ⇒ ورقة التأكيد الموجودة (لا إرسال مباشر)
            page.click('#drawer [data-a="approve"]')
            page.wait_for_selector('#epModal', timeout=8000)
            page.wait_for_timeout(300)
            grab(page)
            page.evaluate("() => document.getElementById('epModal').remove()")
        close_drawer(page)
    # الإغلاق بالزر ثم Escape يرجعان التركيز
    if w < 1180:
        page.click(reveal_btn(page, RECEIPT_IDX[0], mobile))       # زر الإيصال يفتح الدرج فقط (زر الملف يفتح القائمة أيضًا)
        page.wait_for_timeout(500)
        page.keyboard.press('Escape')
        page.wait_for_timeout(250)
        st = page.evaluate("() => [selected, !!document.querySelector('.v2h-dw.open'), document.documentElement.classList.contains('v2-noscroll')]")
        if st != [None, False, False]:
            PROBLEMS.append('%s: Escape ما قفلش الورقة %r' % (pre, st))
    writes = [c for c in h.dash_calls[n0:] if c[0] in ('POST', 'PUT', 'PATCH', 'DELETE')]
    if writes:
        PROBLEMS.append('%s13b: كتابة للداشبورد من زر التذكرة: %r' % (pre, writes))
    # ٢٣) «غيّر / افتح» من بطاقة التركيز يفتح الدرج والزر العائد ظاهر فوقه
    page.evaluate("() => { location.hash = '#s/home/board'; }")
    page.wait_for_function(BOARD_READY, timeout=15000)
    page.wait_for_timeout(300)
    page.click('[data-a="start"]')
    page.wait_for_selector('.v2-card')
    for _ in range(12):
        txt = page.inner_text('.v2-acts')
        if 'افتح' in txt or 'غيّر' in txt:
            break
        page.click('[data-a="later"]')
        page.wait_for_timeout(200)
    btn = page.query_selector('.v2-acts [data-a="secondary"], .v2-acts [data-a="open"], .v2-acts [data-a="change"]')
    target = None
    for b in page.query_selector_all('.v2-acts button'):
        t = (b.inner_text() or '').strip()
        if t in ('غيّر', 'افتح', 'افتح الملف', 'افتح الطلب') or t.startswith('افتح') or t.startswith('غيّر'):
            target = b
            break
    if target:
        target.click()
        page.wait_for_timeout(700)
        pill = page.evaluate("""() => { %s const p = document.querySelector('.v2-pill'); return p && vis(p) ? [Math.round(p.getBoundingClientRect().height), getComputedStyle(p).zIndex] : null; }""" % VIS)
        if not pill or pill[1] != '75':
            PROBLEMS.append('%s23: الزر العائد ظاهر فوق الدرج؟ %r' % (pre, pill))
        hshot(page, pre + '23-focus-open-drawer.jpg', 'inbox', check_targets=True)
    else:
        PROBLEMS.append(pre + '23: ما لقيتش زر «غيّر/افتح» في بطاقة التركيز')


# ----------------------------------------------------------------- حالات الوارد الخاصة
def flow_inbox_states(browser, h, pre, vp, mobile):
    # ١٠) مصدر واحد فاشل
    h.ef.forced[('GET', '/api/bridge/trainer-applications')] = (500, {'error': 'x'})
    ctx = new_ctx(browser, h, vp, mobile)
    page = open_page(ctx, '#s/home/inbox', INBOX_READY, LIGHT_READY)
    fl = page.evaluate("() => (window.INBOX_FAILED || []).slice()")
    if not fl:
        PROBLEMS.append(pre + '10: المصدر الفاشل ما ظهرش في INBOX_FAILED')
    if 'تعذّر جلب' not in page.inner_text('#v2hHead'):
        PROBLEMS.append(pre + '10: شريط «تعذّر جلب» ناقص')
    hshot(page, pre + '10-inbox-partial.jpg')
    del h.ef.forced[('GET', '/api/bridge/trainer-applications')]
    # ١١) خطأ كامل (حالة المحمّل) والقائمة فارغة
    page.evaluate("() => { window.INBOX_FAILED = []; INBOX.length = 0; EP.state.inbox = 'error'; selected = null; renderInbox(); }")
    page.wait_for_timeout(300)
    t = page.inner_text('#rows')
    if 'لا نعرف الآن ما ينتظرك' not in t or 'لا شيء ينتظرك' in page.inner_text('#v2hHead'):
        PROBLEMS.append('%s11: حالة الخطأ تكذب %r' % (pre, t[:80]))
    hshot(page, pre + '11-inbox-error.jpg')
    # ١٢) كله تمام وصفر بنود
    h.ef = v2fx.V2Platform(empty=True)
    set_messages_status(h, 'replied')
    try:
        ctx = new_ctx(browser, h, vp, mobile)
        page = open_page(ctx, '#s/home/inbox', INBOX_READY)
        if 'لا شيء ينتظرك هنا الآن' not in page.inner_text('#rows'):
            PROBLEMS.append(pre + '12: حالة الفراغ الصادق ناقصة: ' + page.inner_text('#rows')[:60])
        hshot(page, pre + '12-inbox-empty.jpg')
    finally:
        set_messages_status(h, 'new')
        h.ef = v2fx.V2Platform()


# ----------------------------------------------------------------- المفتاح مقفول
def flow_off(browser, h, pre, vp, mobile):
    os.environ['DASH_V2_ENABLED'] = 'false'
    try:
        # دخول أول مرة بالمفتاح '1' مخزَّن: الرد الحاسم «مقفول» يخزّن '0'
        ctx = browser.context(h, 'admin', vp, mobile)
        ctx.add_init_script("try{if(localStorage.getItem('ep_v2_shell')===null)localStorage.setItem('ep_v2_shell','1')}catch(e){}")
        page = ctx.new_page()
        page.goto(DASH + '/', wait_until='domcontentloaded')
        page.wait_for_function("() => window.EP && EP.state.inbox === 'ready' && document.getElementById('rows')", timeout=30000)
        page.wait_for_function("() => localStorage.getItem('ep_v2_shell') === '0'", timeout=8000)
        page.wait_for_timeout(500)
        st = page.evaluate("""() => ({kpis: !!document.getElementById('ovKpis'), cards: document.querySelectorAll('.kpis .kpi').length,
          chips: document.querySelectorAll('#filters .chip').length, rows: document.querySelectorAll('.row.inbox-row').length,
          v2: !!(window.V2_ON || document.querySelector('.v2h, .v2-shell, #v2HBell, .v2h-bn')), stored: localStorage.getItem('ep_v2_shell'),
          bellOld: !!document.getElementById('notifPanel'), login: document.documentElement.classList.contains('v2h-login')})""")
        if st['v2'] or not st['rows'] or not st['kpis'] or st['stored'] != '0':
            PROBLEMS.append('%s30: الداشبورد القديمة اتغيّرت والمفتاح مقفول: %r' % (pre, st))
        if st['cards'] < 4 or not st['chips']:
            PROBLEMS.append('%s30: شاشة الوارد القديمة ناقصة: %r' % (pre, st))
        # الجرس القديم: ما فيهوش لمسة (لا شارة جديدة ولا لوحة الجرس الجديدة)
        base.shot(page, pre + '30-switch-off-inbox.jpg')
        # الدخول بعد تخزين '0': الشكل القديم
        page.evaluate("() => { localStorage.removeItem('token'); localStorage.removeItem('ep_dash_token'); }")
        ctx2 = new_ctx(browser, h, vp, mobile, anon={'flag': '0'})
        p2 = ctx2.new_page()
        p2.goto(DASH + '/', wait_until='domcontentloaded')
        p2.wait_for_selector('#epLogin')
        p2.wait_for_timeout(400)
        lg = p2.evaluate("() => [document.documentElement.classList.contains('v2h-login'), !!document.querySelector('.ep-login')]")
        if lg != [False, True]:
            PROBLEMS.append('%s30: شاشة الدخول والمفتاح «0»: %r (المطلوب الشكل القديم)' % (pre, lg))
        base.shot(p2, pre + '30b-switch-off-login.jpg')
    finally:
        os.environ['DASH_V2_ENABLED'] = 'true'


# ----------------------------------------------------------------- التشغيل
def guarded(fn, browser, h, pre, vp, mobile):
    import traceback
    try:
        fn(browser, h, pre, vp, mobile)
    except Exception as e:      # noqa: BLE001 — نكمل باقي الفلوات ونسجّل العطل
        PROBLEMS.append('%s: %s سقط: %s' % (pre, fn.__name__, str(e).strip().splitlines()[0][:160]))
        traceback.print_exc()


def run_viewport(browser, h, pre, vp, mobile):
    h.ef = v2fx.V2Platform()
    for fn in (flow_login, flow_splash, flow_board_bell, flow_inbox, flow_drawers, flow_ticket_btn, flow_inbox_states):
        h.ef = v2fx.V2Platform()
        guarded(fn, browser, h, pre, vp, mobile)
    if pre in ('d', 'm'):
        guarded(flow_off, browser, h, pre, vp, mobile)
    browser.close()


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    h = Harness(v2fx.V2Platform())
    seed_dash(h)
    before = len(h.dash_calls)
    with sync_playwright() as p:
        browser = Browsers(p)
        try:
            run_viewport(browser, h, 'd', DESK, False)
            run_viewport(browser, h, 't', TAB, False)
            run_viewport(browser, h, 'm', MOB, True)
        finally:
            browser.close()
    writes = [c for c in h.dash_calls if c[0] in ('POST', 'PUT', 'PATCH', 'DELETE') and c[1] != '/api/auth/login']
    if writes:
        PROBLEMS.append('كتابة للداشبورد أثناء اللقطات: %r' % writes[:5])
    with open(os.path.join(OUT, 'copy-capture.json'), 'w', encoding='utf-8') as fh:
        json.dump(sorted(CAPTURE), fh, ensure_ascii=False, indent=1)
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': base.SHOTS, 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc,
                      'unexpected': h.unexpected_blocked(), 'opened': sorted(OPENED), 'captured_strings': len(CAPTURE),
                      'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
