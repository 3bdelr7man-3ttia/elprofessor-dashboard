# -*- coding: utf-8 -*-
"""لقطات شاشات غير الأدمن (القسم «roles») — كمبيوتر ١٤٤٠ (`d`) وتابلت ٨٢٠ (`t`) وموبايل ٣٩٠ (`m`).

    cd backend && python3 -B tests/uiharness/v2_shots_roles.py ../docs/v2/final/shots-roles

⛔ صفر طلبات حقيقية: الداشبورد جوه العملية والمنصة جدول في الذاكرة (`roles_fixtures.RolesPlatform`)، وأي أصل تاني بيتقفل ويتسجّل.
السكربت بيفشل (خروج ١) لو: خرج طلب برّه الداشبورد (غير خطوط جوجل) · تمرير أفقي · هدف أقل من ٤٤px (أو زرّ `v2ro-btn` أقل من ٥٢px في الموبايل) ·
`undefined/null/NaN` ظاهرة · رقم «٠/0» في بطاقة مصدرها واقع أو حساب غير مربوط · القائمة القديمة أو الشريط ذو الإيموجي ظاهر والمفتاح مفتوح ·
كتابة سحب من غير `confirmed:true` أو نداء مباشر لـ`/api/investor/withdraw` · المدرّب طلب `investment-opportunities` · الأدمن رأى أي `v2ro` ·
زرّ السحب تحت الطي في الموبايل · أكثر من `v2ro-btn1` على شاشة · بريد في البانر · تبويب مكرّر ظاهر في «كل السجلات» · لوحة الجرس بشكل قديم ·
قائمة/جرس ظاهرَين في شاشة الحساب المعلّق.
"""
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

import roles_fixtures as rf                      # noqa: E402
from ef_route_harness import Harness, DASH       # noqa: E402
from v2_shots import Browsers                    # noqa: E402

OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), 'shots-roles'))
os.makedirs(OUT, exist_ok=True)
DESK = {'width': 1440, 'height': 900}
TAB = {'width': 820, 'height': 1180}
MOB = {'width': 390, 'height': 844}
SHOTS = []
PROBLEMS = []
EMOJI = re.compile('[' + chr(0x1F300) + '-' + chr(0x1FAFF) + chr(0x2600) + '-' + chr(0x2714) + chr(0x2716) + '-' + chr(0x27BF) + chr(0x2B50) + chr(0x23F0) + chr(0x23F3) + chr(0x231A) + chr(0x231B) + ']')   # chr(0x2715) = زرّ إغلاق النافذة الموجودة، مش إيموجي
NA = 'غير متاح بعد'

READY = """() => !!document.querySelector('.app.v2-roles') && !!document.querySelector('.v2ro, .v2ro-vw, .v2ro-solo')
  && !document.querySelector('.v2ro-load') && ![...document.querySelectorAll('.v2ro-big')].some(n => n.textContent.trim() === '…')"""


class Run(object):
    def __init__(self, pre, vp, mobile):
        self.pre, self.vp, self.mobile = pre, vp, mobile
        self.w = vp['width']
        self.reqs = []

    def tag(self, name):
        return '%s-%s' % (self.pre, name)


def check(run, page, name, roles_on=True):
    txt = page.evaluate("() => document.body.innerText")
    for bad in ('undefined', 'NaN', '[object Object]'):
        if bad in txt:
            PROBLEMS.append('%s: «%s» ظاهرة في الصفحة' % (name, bad))
    if re.search(r'(?<![\w@./-])null(?![\w@./-])', txt):
        PROBLEMS.append('%s: «null» ظاهرة في الصفحة' % name)
    sw = page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth, (document.querySelector('.content')||{}).scrollWidth||0)")
    if sw > run.w + 1:
        PROBLEMS.append('%s: تمرير أفقي (%s > %s)' % (name, sw, run.w))
    small = [] if not roles_on else page.evaluate("""() => [...document.querySelectorAll('a[href], button, input, [role=button], select, textarea')]
      .filter(n => { const r = n.getBoundingClientRect(), cs = getComputedStyle(n);
        return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && !n.closest('[hidden]') && !n.closest('[aria-hidden="true"]'); })
      .map(n => ({t: (n.innerText || n.value || n.getAttribute('aria-label') || '').trim().slice(0, 24), h: Math.round(n.getBoundingClientRect().height * 10) / 10, c: String(n.className).slice(0, 30)}))
      .filter(x => x.h < 43.5)""")
    if small:
        PROBLEMS.append('%s: %d هدف أقل من ٤٤px: %r' % (name, len(small), small[:4]))
    if run.mobile:
        btn = page.evaluate("""() => [...document.querySelectorAll('.v2ro-btn1, .v2ro-btn2')]
          .filter(n => n.offsetParent).map(n => n.getBoundingClientRect().height).filter(h => h < 51.5).length""")
        if btn:
            PROBLEMS.append('%s: %d زرار أقل من ٥٢px في الموبايل' % (name, btn))
    out = page.evaluate("""() => [...document.querySelectorAll('.v2ro a, .v2ro button, .v2rom button')].filter(b => b.offsetParent && !b.closest('.v2ro-chips'))
      .map(b => b.getBoundingClientRect()).filter(r => r.left < -1 || r.right > window.innerWidth + 1).length""")
    if out:
        PROBLEMS.append('%s: %d عنصر خارج عرض الشاشة' % (name, out))
    if roles_on:
        st = page.evaluate("""() => { const rail = document.querySelector('.rail'), rb = document.getElementById('roBanner');
          return {rail: rail && getComputedStyle(rail).display !== 'none', banner: rb && getComputedStyle(rb).display !== 'none'}; }""")
        if st['rail']:
            PROBLEMS.append('%s: القائمة القديمة ظاهرة والمفتاح مفتوح' % name)
        if st['banner']:
            PROBLEMS.append('%s: شريط الدور القديم ظاهر' % name)
        if EMOJI.search(txt):
            PROBLEMS.append('%s: إيموجي ظاهر: %r' % (name, EMOJI.findall(txt)[:3]))
    hero = page.evaluate("() => { const h = document.querySelector('.v2ro-hero'); return h ? h.innerText : ''; }")
    if '@' in hero:
        PROBLEMS.append('%s: بريد في البانر' % name)
    if len(page.query_selector_all('.v2ro .v2ro-btn1')) > 1 and any(k in name for k in ('investor-home', 'trainer-home', 'trainer-earnings')):
        vis = page.evaluate("() => [...document.querySelectorAll('.v2ro .v2ro-btn1')].filter(n => n.offsetParent).length")
        if vis > 1:
            PROBLEMS.append('%s: %d زرّ رئيسي ظاهر' % (name, vis))


def shot(run, page, name, roles_on=True, full=False):
    path = os.path.join(OUT, name)
    page.wait_for_timeout(300)
    page.screenshot(path=path, full_page=full, type='jpeg', quality=82)
    SHOTS.append(name)
    check(run, page, name, roles_on)


def open_page(ctx, run, hash_='', ready=True):
    page = ctx.new_page()
    page.on('request', lambda r: run.reqs.append((r.method, r.url, r.post_data)))
    page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
    if ready:
        page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(250)
    return page


def goto(page, mod):
    page.evaluate("(m) => { go(m); if (m === 'tutorials') history.replaceState(null, '', '#tutorials'); }", mod)
    page.wait_for_function(READY, timeout=30000)
    page.wait_for_timeout(200)


def bigs(page):
    return page.evaluate("() => [...document.querySelectorAll('.v2ro-num')].map(n => [n.querySelector('h3').textContent.trim(), n.querySelector('.v2ro-big').textContent.trim()])")


def expect_na(name, page, labels):
    got = dict(bigs(page))
    for lb in labels:
        if got.get(lb) != NA:
            PROBLEMS.append('%s: بطاقة «%s» لازم تكون «%s» وهي «%s»' % (name, lb, NA, got.get(lb)))


def expect_text(name, page, needle, absent=False):
    txt = page.evaluate("() => document.querySelector('#view').innerText")
    if (needle in txt) == absent:
        PROBLEMS.append('%s: النص «%s» %s' % (name, needle, 'موجود وما كان لازم' if absent else 'مش موجود'))


def check_calls(run, who):
    for method, url, body in run.reqs:
        if url.endswith('/api/investor/withdraw'):
            PROBLEMS.append('%s: نداء مباشر لـ/api/investor/withdraw' % who)
        if url.endswith('/api/v2/roles/withdraw') and method == 'POST':
            try:
                ok = json.loads(body or '{}').get('confirmed') is True
            except Exception:
                ok = False
            if not ok:
                PROBLEMS.append('%s: POST سحب من غير confirmed:true' % who)
        if who.startswith('trainer') and url.endswith('/api/investment-opportunities'):
            PROBLEMS.append('%s: المدرّب طلب فرص الاستثمار' % who)


LEGACY_BAD = re.compile(r'native|app\.elprofessor\.net|\bAPI\b|\bn8n\b|\bHTML\b|\bUSD\b|\bEGP\b|prerender|إيراد\s*[·٠0]\s*(ج|جنيه)', re.I)


def scan_legacy(page, name, tabs_sel):
    """«كل السجلات»: لا كلمة تقنية ولا رقم لاتيني ولا خانة إيراد فاضية في أي تبويب فرعي ظاهر (والبريد/الروابط بعلامة dir=ltr مستثناة)."""
    def one(label):
        page.wait_for_timeout(700)
        bad = page.evaluate("""() => { const out = [], w = document.createTreeWalker(document.querySelector('#view'), NodeFilter.SHOW_TEXT);
          while (w.nextNode()) { const n = w.currentNode, p = n.parentNode;
            if (!p || /^(SCRIPT|STYLE|TEXTAREA|OPTION)$/.test(p.nodeName) || p.closest('[dir="ltr"], .v2ro-mail, code') || !p.offsetParent) continue;
            const t = n.nodeValue; if (/\d/.test(t) || /[A-Za-z]{2,}/.test(t) || /^\s*[·—]\s*$/.test(t)) out.push(t.trim().slice(0, 60)); }
          return out; }""")
        for t in bad[:4]:
            if t:
                PROBLEMS.append('%s [%s]: نص تقني أو رقم لاتيني في «كل السجلات»: %r' % (name, label, t))
        txt = page.evaluate("() => document.querySelector('#view').innerText")
        m = LEGACY_BAD.search(txt)
        if m:
            PROBLEMS.append('%s [%s]: «%s» ظاهرة في «كل السجلات»' % (name, label, m.group(0)))
    one('أول تبويب')
    tabs = page.evaluate("(sel) => [...document.querySelectorAll(sel)].filter(n => n.offsetParent).map(n => n.getAttribute('data-t') || n.getAttribute('data-tt'))", tabs_sel)
    for tid in tabs:
        page.evaluate("([sel, id]) => { const n = [...document.querySelectorAll(sel)].find(x => (x.getAttribute('data-t') || x.getAttribute('data-tt')) === id); if (n) n.click(); }", [tabs_sel, tid])
        one(tid)


# ----------------------------------------------------------------------------------------------------------------- المدرّب
def flow_trainer(br, h, run):
    h.ef = rf.RolesPlatform()
    ctx = br.context(h, 'trainer', run.vp, run.mobile)
    page = open_page(ctx, run)
    shot(run, page, run.tag('01-trainer-home.jpg'))
    got = dict(bigs(page))
    if got.get('مستحق لك في دفتر الإدارة') != '٢٬٣٥٠ جنيه':
        PROBLEMS.append('trainer-home: المستحق مش ٢٬٣٥٠ جنيه بل %r' % got)
    if run.w < 1180:
        page.click('#menuBtn')
        page.wait_for_selector('#v2roSheet.open')
        shot(run, page, run.tag('07-trainer-menu-sheet.jpg'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(250)
    goto(page, 't_courses')
    shot(run, page, run.tag('02-trainer-courses.jpg'))
    goto(page, 't_earnings')
    shot(run, page, run.tag('03-trainer-earnings.jpg'))
    page.evaluate("() => { document.querySelector('.content').style.overflow = 'visible'; document.querySelector('.app').style.height = 'auto'; }")
    shot(run, page, run.tag('03b-trainer-earnings-wallet.jpg'), full=True)
    page.evaluate("() => { document.querySelector('.content').style.overflow = ''; document.querySelector('.app').style.height = ''; }")
    if len(page.query_selector_all('.v2ro-btn1')) != 1 or not page.query_selector('[data-r-act="wd"]'):
        PROBLEMS.append('trainer-earnings: لازم زرّ رئيسي واحد هو السحب')
    check_calls(run, 'trainer')
    br.close()

    # حساب بلا ربط
    ctx = br.context(h, 'trainer_unlinked', run.vp, run.mobile)
    page = open_page(ctx, run)
    shot(run, page, run.tag('04-trainer-home-unlinked.jpg'))
    expect_na('trainer-home-unlinked', page, ['دوراتي', 'المسجّلون في دوراتي', 'مستحق لك في دفتر الإدارة'])
    goto(page, 't_courses')
    shot(run, page, run.tag('05-trainer-courses-empty.jpg'))
    goto(page, 't_earnings')
    shot(run, page, run.tag('05b-trainer-earnings-unlinked.jpg'))
    if page.query_selector('.v2ro-h2:has-text("محفظة الاستثمار")'):
        PROBLEMS.append('trainer-earnings-unlinked: جزء المحفظة مرسوم لمدرّب بلا محفظة')
    br.close()

    # مصدر المستحقات واقع
    ctx = br.context(h, 'trainer', run.vp, run.mobile)
    ctx.route('**/api/payouts', lambda route: route.fulfill(status=500, content_type='application/json', body='{"error":"x"}'))
    page = open_page(ctx, run)
    shot(run, page, run.tag('06-trainer-home-failed.jpg'))
    expect_na('trainer-home-failed', page, ['مستحق لك في دفتر الإدارة'])
    got = dict(bigs(page))
    if got.get('دوراتي') == NA:
        PROBLEMS.append('trainer-home-failed: بطاقة الدورات سقطت بسبب المستحقات')
    br.close()


# ----------------------------------------------------------------------------------------------------------------- المستثمر
def flow_investor(br, h, run):
    h.ef = rf.RolesPlatform()
    ctx = br.context(h, 'investor', run.vp, run.mobile)
    page = open_page(ctx, run)
    shot(run, page, run.tag('10-investor-home.jpg'))
    top = page.evaluate("() => { const b = document.querySelector('[data-r-act=\"wd\"].v2ro-btn1'); return b ? b.getBoundingClientRect().top + scrollY : -1; }")
    if top < 0:
        PROBLEMS.append('investor-home: زرّ السحب مش موجود')
    elif run.w <= 400 and top > 800:
        PROBLEMS.append('investor-home (m): زرّ السحب تحت الطي (%d)' % top)
    # طلب السحب: النموذج ⇒ المراجعة ⇒ خطأ الخادم ⇒ نجاح
    page.click('[data-r-act="wd"].v2ro-btn1')
    page.wait_for_selector('#v2roAmt')
    shot(run, page, run.tag('13-investor-withdraw-form.jpg'))
    page.fill('#v2roAmt', '1000')
    page.click('#v2roRev')
    page.wait_for_selector('#v2roGo')
    shot(run, page, run.tag('14-investor-withdraw-review.jpg'))
    n0 = len(run.reqs)
    page.click('#v2roGo')
    page.wait_for_selector('.v2ro-err')
    if 'الحد الأدنى' not in page.inner_text('.v2ro-err') or '٥٠' not in page.inner_text('.v2ro-err'):
        PROBLEMS.append('investor-withdraw-error: رسالة الخادم مش بالأرقام العربية: %r' % page.inner_text('.v2ro-err'))
    shot(run, page, run.tag('15-investor-withdraw-error.jpg'))
    page.click('#v2roBack')
    page.fill('#v2roAmt', '5000')
    page.click('#v2roRev')
    page.wait_for_selector('#v2roGo')
    page.click('#v2roGo')
    page.wait_for_function("() => !document.getElementById('epModal')", timeout=15000)
    page.wait_for_function(READY, timeout=15000)
    page.wait_for_timeout(300)
    posts = [r for r in run.reqs[n0:] if r[0] == 'POST' and r[1].endswith('/api/v2/roles/withdraw')]
    if len(posts) != 2 or any(json.loads(p[2]).get('confirmed') is not True or json.loads(p[2]).get('currency') != 'EGP' for p in posts):
        PROBLEMS.append('investor-withdraw: نداءات الإرسال غير المتوقعة: %r' % [(p[1], p[2]) for p in posts])
    shot(run, page, run.tag('16-investor-withdraw-done.jpg'))
    goto(page, 'i_market')
    shot(run, page, run.tag('11-investor-market.jpg'))
    goto(page, 'i_invest')
    shot(run, page, run.tag('17-investor-invest-active.jpg'))
    page.click('.v2c-tab[data-id="history"]')
    page.wait_for_function(READY, timeout=15000)
    shot(run, page, run.tag('18-investor-invest-history.jpg'))
    check_calls(run, 'investor')
    br.close()

    ctx = br.context(h, 'investor_unlinked', run.vp, run.mobile)
    page = open_page(ctx, run)
    shot(run, page, run.tag('12-investor-home-unlinked.jpg'))
    expect_na('investor-home-unlinked', page, ['متاح للسحب', 'إجمالي ما استثمرته', 'عوائد مستلمة', 'سحب قيد المراجعة'])
    br.close()

    # فرص الاستثمار والمصدر واقع
    ctx = br.context(h, 'investor', run.vp, run.mobile)
    ctx.route('**/api/investment-opportunities', lambda route: route.fulfill(status=500, content_type='application/json', body='{"error":"x"}'))
    page = open_page(ctx, run, '#i_market')
    shot(run, page, run.tag('19-investor-market-failed.jpg'))
    expect_text('investor-market-failed', page, 'تعذّر جلب فرص الاستثمار')
    br.close()


# ----------------------------------------------------------------------------------------------------------------- فريق المتابعة
def flow_staff(br, h, run):
    h.ef = rf.RolesPlatform()
    ctx = br.context(h, 'employee', run.vp, run.mobile)
    page = open_page(ctx, run)
    shot(run, page, run.tag('20-staff-people.jpg'))
    page.click('.v2ro-x >> nth=0')
    page.wait_for_selector('.v2ro-det:not([hidden])')
    shot(run, page, run.tag('21-staff-people-open.jpg'))
    goto(page, 'courses')
    shot(run, page, run.tag('22-staff-courses.jpg'))
    page.click('.v2c-tab[data-id="legacy"]')
    page.wait_for_selector('#cTabs')
    page.wait_for_timeout(600)
    shot(run, page, run.tag('23-staff-courses-legacy.jpg'))
    scan_legacy(page, run.tag('courses-legacy'), '#cTabs .tab')
    page.evaluate("() => { const n = [...document.querySelectorAll('#cTabs .tab')].find(x => x.offsetParent); if (n) n.click(); }")
    page.wait_for_timeout(500)
    vis = page.evaluate("() => [...document.querySelectorAll('#cTabs .tab[data-t=\"platform\"]')].filter(n => n.offsetParent).length")
    if vis:
        PROBLEMS.append('staff-courses-legacy: تبويب الكتالوج القديم ظاهر')
    visible_writes = page.evaluate("() => [...document.querySelectorAll('#view button')].filter(b => b.offsetParent).map(b => b.textContent.trim().slice(0, 30))")
    legacy_buttons = {'courses': visible_writes}
    goto(page, 'topics')
    shot(run, page, run.tag('24-staff-topics.jpg'))
    page.click('.v2c-tab[data-id="legacy"]')
    page.wait_for_selector('#topicsTabs')
    page.wait_for_timeout(600)
    shot(run, page, run.tag('25-staff-topics-legacy.jpg'))
    scan_legacy(page, run.tag('topics-legacy'), '#topicsTabs .tab')
    page.evaluate("() => { const n = [...document.querySelectorAll('#topicsTabs .tab')].find(x => x.offsetParent); if (n) n.click(); }")
    page.wait_for_timeout(500)
    hidden = page.evaluate("""() => [...document.querySelectorAll('#topicsTabs .tab')].filter(n => n.offsetParent && ['pending','ideas','working','board','incoming','rejected','tutorials'].indexOf(n.dataset.tt) > -1).length""")
    if hidden:
        PROBLEMS.append('staff-topics-legacy: %d تبويب مكرّر ظاهر' % hidden)
    legacy_buttons['topics'] = page.evaluate("() => [...document.querySelectorAll('#view button')].filter(b => b.offsetParent).map(b => b.textContent.trim().slice(0, 30))")
    page.click('.v2c-tab[data-id="topics"]')
    page.wait_for_function(READY, timeout=15000)
    page.click('.v2c-tab[data-id="tut"]')
    page.wait_for_function(READY, timeout=15000)
    page.wait_for_timeout(200)
    shot(run, page, run.tag('26-staff-topics-guide-tab.jpg'))
    goto(page, 'tutorials')
    page.click('.v2ro-x >> nth=0')
    shot(run, page, run.tag('27-staff-tutorials.jpg'))
    # الجرس
    page.click('#bellBtn')
    page.wait_for_selector('#notifPanel .np-row, #notifPanel .np-empty')
    page.wait_for_timeout(500)
    shot(run, page, run.tag('28-staff-bell.jpg'))
    pan = page.evaluate("""() => { const p = document.getElementById('notifPanel'), cs = getComputedStyle(p);
      return {open: cs.display !== 'none', radius: cs.borderTopLeftRadius, bg: cs.backgroundColor,
              rows: [...p.querySelectorAll('.np-row')].map(r => Math.round(r.getBoundingClientRect().height))}; }""")
    if not pan['open'] or pan['radius'] != '18px' or pan['bg'] != 'rgb(255, 255, 255)' or any(r < 44 for r in pan['rows']):
        PROBLEMS.append('staff-bell: لوحة الجرس بشكل قديم أو صفوف صغيرة: %r' % pan)
    if not pan['rows']:
        PROBLEMS.append('staff-bell: لا صفوف لفحصها')
    br.close()
    print(json.dumps({'legacy_buttons_%s' % run.pre: legacy_buttons}, ensure_ascii=False))

    # أكثر من ٥٠٠ عضو
    h.ef = rf.RolesPlatform(capped=True)
    ctx = br.context(h, 'employee', run.vp, run.mobile)
    page = open_page(ctx, run)
    shot(run, page, run.tag('29-staff-people-capped.jpg'))
    expect_text('staff-people-capped', page, 'المعروض أحدث')
    n0 = len(h.dash_calls)
    page.fill('#v2roQ', 'منى')
    page.wait_for_timeout(900)
    page.wait_for_function(READY, timeout=15000)
    if not any(p == '/api/platform-users' for _m, p in h.dash_calls[n0:]):
        PROBLEMS.append('staff-people-capped: البحث ما راحش للخادم')
    if not any('search=' in u for _m, u, _b in run.reqs):
        PROBLEMS.append('staff-people-capped: ما فيش نداء search=')
    shot(run, page, run.tag('29b-staff-people-capped-search.jpg'))
    br.close()


def flow_viewer(br, h, run):
    h.ef = rf.RolesPlatform()
    for who, name in (('viewer', '30-viewer.jpg'), ('pending', '31-pending.jpg')):
        ctx = br.context(h, who, run.vp, run.mobile)
        page = open_page(ctx, run)
        shot(run, page, run.tag(name))
        st = page.evaluate("""() => ({menu: !!document.getElementById('menuBtn').offsetParent, bell: !!document.getElementById('bellBtn').offsetParent,
          title: document.getElementById('pageTitle').textContent.trim(), side: !!(document.getElementById('v2roSide') && document.getElementById('v2roSide').offsetParent)})""")
        if st['menu'] or st['bell'] or st['side'] or st['title'] != 'حسابك':
            PROBLEMS.append('viewer: قائمة/جرس ظاهر أو عنوان غلط: %r' % st)
        br.close()
    # الأدمن: لا v2ro
    ctx = br.context(h, 'admin', run.vp, run.mobile)
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_function("() => window.V2_ON === true && document.querySelector('.v2-tile')", timeout=30000)
    page.wait_for_timeout(500)
    leaks = page.evaluate("() => document.querySelectorAll('[class*=\"v2ro\"], #v2roSide, #v2roSec, #v2roSheet').length")
    if leaks:
        PROBLEMS.append('admin: ظهر %d عنصر v2ro' % leaks)
    shot(run, page, run.tag('32-admin-home.jpg'), roles_on=False)
    br.close()


def _set_perms(h, perms):
    m = h.app
    with m.app.app_context():
        row = m.Setting.query.get('role_permissions')
        if perms is None:
            if row is not None:
                m.db.session.delete(row)
        elif row is None:
            m.db.session.add(m.Setting(key='role_permissions', value=json.dumps(perms)))
        else:
            row.value = json.dumps(perms)
        m.db.session.commit()


def flow_edge(br, h, run):
    """أول رسمة بذاكرة المفتاح (لا ومضة للشكل القديم) · صلاحيات مقيَّدة · موظف بلا أي شاشة."""
    h.ef = rf.RolesPlatform()
    # ١) المفتاح متذكَّر والرد متأخر ⇒ الشريط القديم مخفي والشاشة هيكل محايد، ثم تتحوّل
    ctx = br.context(h, 'trainer', run.vp, run.mobile)
    ctx.add_init_script("try{localStorage.setItem('ep_v2_roles','1')}catch(e){}")
    h.hold.add(('GET', '/api/v2/roles/config'))
    page = ctx.new_page()
    page.goto(DASH + '/', wait_until='domcontentloaded')
    page.wait_for_function("() => window.EP && EP.role === 'trainer' && document.querySelector('.app').classList.contains('v2-pre')", timeout=30000)
    st = page.evaluate("""() => ({rail: getComputedStyle(document.querySelector('.rail')).display, main: getComputedStyle(document.querySelector('.main')).visibility,
      skel: !!document.querySelector('#view .v2ro-load'), old: !!document.querySelector('#view .kpis')})""")
    if st['rail'] != 'none' or st['main'] != 'hidden' or st['old']:
        PROBLEMS.append('memo: ومضة للشكل القديم قبل رد المفتاح: %r' % st)
    h.hold.discard(('GET', '/api/v2/roles/config'))
    h.release_held()
    page.wait_for_function(READY, timeout=30000)
    if page.evaluate("() => document.querySelector('.app').classList.contains('v2-pre')"):
        PROBLEMS.append('memo: v2-pre ما اتشالتش بعد الرد')
    br.close()
    # ٢) خريطة صلاحيات مقيَّدة: بندان فقط
    _set_perms(h, {'employee': {'modules': ['users', 'tutorials']}})
    try:
        ctx = br.context(h, 'employee', run.vp, run.mobile)
        page = open_page(ctx, run)
        page.wait_for_timeout(600)
        names = page.evaluate("() => [...document.querySelectorAll('#v2roSheet .v2s-tn, #v2roSide .v2s-name')].map(n => n.textContent.trim())")
        if sorted(set(names)) != ['الأعضاء', 'دليل الاستخدام']:
            PROBLEMS.append('staff-perms: بنود القائمة مش الاثنين المسموحين: %r' % names)
        shot(run, page, run.tag('40-staff-restricted.jpg'))
        br.close()
        _set_perms(h, {'employee': {'modules': []}})
        ctx = br.context(h, 'employee', run.vp, run.mobile)
        page = open_page(ctx, run)
        page.wait_for_function("() => document.querySelector('.v2ro-solo')", timeout=15000)
        shot(run, page, run.tag('41-staff-no-screens.jpg'))
        br.close()
    finally:
        _set_perms(h, None)


def _swap_account(page, token, ready=True):
    """يحاكي ٤٠١ ثم دخول حساب آخر في نفس الصفحة بلا إعادة تحميل (نفس ما يفعله الدخول: EP.user + EP.role ثم epBootCore)."""
    page.evaluate("""(tok) => { try { localStorage.setItem('token', tok); localStorage.setItem('ep_dash_token', tok); } catch (e) {}
      return EP.api('/auth/me').then(me => { EP.user = me; EP.role = me.role || me.dashboard_role || 'viewer'; epBootCore(); }); }""", token)
    if ready:
        page.wait_for_function(READY, timeout=30000)
        page.wait_for_timeout(400)


def flow_switch(br, h, run):
    """حساب جديد في نفس الصفحة: لا رقم ولا زرّ ولا صنف من الحساب السابق."""
    h.ef = rf.RolesPlatform()
    ctx = br.context(h, 'trainer', run.vp, run.mobile)
    page = open_page(ctx, run)
    goto(page, 't_earnings')
    if not page.query_selector('[data-r-act="wd"]'):
        PROBLEMS.append('switch: المدرّب (أ) لازم يرى زرّ السحب قبل التبديل')
    before = page.evaluate("() => document.querySelector('#view').innerText")
    if '٢٬٣٥٠' not in before:
        PROBLEMS.append('switch: مبلغ المدرّب (أ) مش ظاهر قبل التبديل')
    _swap_account(page, h.tokens['investor_unlinked'])
    st = page.evaluate("""() => ({cls: document.querySelector('.app').className, txt: document.querySelector('#view').innerText,
      wd: !!document.querySelector('[data-r-act="wd"]'), side: document.querySelectorAll('#v2roSide').length})""")
    if 'v2ro-trainer' in st['cls'] or 'v2ro-investor' not in st['cls']:
        PROBLEMS.append('switch: صنف الدور لم يتبدّل: %r' % st['cls'])
    if st['wd'] or '٢٬٣٥٠' in st['txt'] or 'محفظة الاستثمار' in st['txt'] and 'متاح للسحب' not in st['txt']:
        PROBLEMS.append('switch: أثر من حساب المدرّب (أ) على المستثمر (ب): %r' % st['txt'][:200])
    if st['side'] != 1:
        PROBLEMS.append('switch: عدد القوائم الجانبية %d' % st['side'])
    got = dict(bigs(page))
    for lb in ('متاح للسحب', 'إجمالي ما استثمرته'):
        if got.get(lb) != NA:
            PROBLEMS.append('switch: «%s» للحساب (ب) غير المربوط لازم «%s» وهي %r' % (lb, NA, got.get(lb)))
    shot(run, page, run.tag('91-switch-account.jpg'))
    br.close()


def flow_off(br, h, run):
    """المفتاح مقفول (أو مفتاح الأدوار) ⇒ الشاشات القديمة كما هي، ولا أثر للجديد."""
    cases = [('trainer', 'trainer', {'DASH_V2_ENABLED': None}), ('investor', 'investor', {'DASH_V2_ENABLED': None}), ('employee', 'staff', {'DASH_V2_ENABLED': None}),
             ('trainer', 'roles-off-trainer', {'DASH_V2_ENABLED': 'true', 'DASH_V2_ROLES_ENABLED': 'false'})]
    saved = {k: os.environ.get(k) for k in ('DASH_V2_ENABLED', 'DASH_V2_ROLES_ENABLED')}
    try:
        for role, label, env in cases:
            for k in ('DASH_V2_ENABLED', 'DASH_V2_ROLES_ENABLED'):
                os.environ.pop(k, None)
            for k, v in env.items():
                if v is not None:
                    os.environ[k] = v
            h.ef = rf.RolesPlatform()
            ctx = br.context(h, role, run.vp, run.mobile)
            page = ctx.new_page()
            page.goto(DASH + '/', wait_until='domcontentloaded')
            page.wait_for_function("() => window.EP && EP.role && document.querySelector('.rail .nav .item')", timeout=30000)
            page.wait_for_timeout(1200)
            st = page.evaluate("""() => ({rail: getComputedStyle(document.querySelector('.rail')).display !== 'none', side: !!document.getElementById('v2roSide'),
              roles: document.querySelector('.app').classList.contains('v2-roles'), memo: localStorage.getItem('ep_v2_roles')})""")
            if run.w >= 1180 and not st['rail']:
                PROBLEMS.append('%s: القائمة القديمة مش ظاهرة والمفتاح مقفول' % label)
            if st['side'] or st['roles'] or st['memo']:
                PROBLEMS.append('%s: أثر للشاشات الجديدة والمفتاح مقفول: %r' % (label, st))
            shot(run, page, run.tag('90-switch-off-%s.jpg' % label), roles_on=False)
            br.close()
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def main():
    from playwright.sync_api import sync_playwright
    os.environ['DASH_V2_ENABLED'] = 'true'
    os.environ.pop('DASH_V2_ROLES_ENABLED', None)
    h = Harness(rf.RolesPlatform())
    m = h.app
    with m.app.app_context():
        users = rf.seed(m)
        h.tokens.update(rf.tokens(m, users))
    only = sys.argv[3].split(',') if len(sys.argv) > 3 else None
    vps = (('d', DESK, False), ('t', TAB, False), ('m', MOB, True))
    if len(sys.argv) > 2 and sys.argv[2] != 'all':
        vps = tuple(v for v in vps if v[0] in sys.argv[2])
    with sync_playwright() as p:
        br = Browsers(p)
        try:
            for pre, vp, mobile in vps:
                run = Run(pre, vp, mobile)
                for name, fn in (('trainer', flow_trainer), ('investor', flow_investor), ('staff', flow_staff), ('viewer', flow_viewer), ('edge', flow_edge), ('switch', flow_switch), ('off', flow_off)):
                    if only and name not in only:
                        continue
                    fn(br, h, run)
                for who in ('trainer', 'investor', 'staff', 'viewer'):
                    pass
                check_calls(run, 'run-' + pre)
        finally:
            br.close()
    rep = h.blocked_report()
    print(json.dumps({'out': OUT, 'shots': len(SHOTS), 'blocked_by_origin': rep, 'blocked_inproc': h.blocked_inproc, 'unexpected': h.unexpected_blocked(),
                      'problems': PROBLEMS}, ensure_ascii=False, indent=1))
    h.uninstall()
    if h.unexpected_blocked() or PROBLEMS:
        sys.exit(1)


if __name__ == '__main__':
    main()
