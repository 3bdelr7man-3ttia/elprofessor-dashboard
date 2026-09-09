# -*- coding: utf-8 -*-
"""سلوك البنية الجديدة في متصفّحٍ حقيقي — الشرائح · التحويلات · التبويبات · السقف.

Run:  cd backend && python3 -m pytest -q tests/test_dash_ia_ui.py

الاختبار البنيويّ (`test_dash_ia_structure.py`) يثبّت **ما هو مكتوب**؛ هذا يثبّت **ما
يُرسَم فعلًا**: أن الوارد يعرض أكثر من ٢٥ صفًّا، وأن شريحة «رسائل» تسرد الرسائل ويعمل الردّ
من الدرج، وأن `#overview` يهبط على الوارد، وأن تبويب «الدفعات اليدوية» يستقبل ما يوجّهه
الوارد إليه، وأن P&L والطابور يصلان من المنصّة إلى الشاشة.

⛔ الوجود في الملفّ ليس رسمًا: مكوّنٌ مكتوبٌ صحيحًا وبلا طريقٍ إلى الشاشة عطلٌ متكرّر في هذا
الريبو، ولا يكشفه إلا تشغيلُ الصفحة.

⛔ صفر لمسٍ للإنتاج: خادمٌ محلّيّ على منفذٍ حرّ + قاعدة SQLite مؤقّتة + منصّةٌ وهميّة.
"""
import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time

import pytest

playwright = pytest.importorskip('playwright.sync_api',
                                 reason='playwright غير متاح — اختبار الواجهة يُتخطّى')
from playwright.sync_api import sync_playwright  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
HARNESS = os.path.join(_HERE, 'uiharness')
SHOTS = os.environ.get('EP_UI_SHOTS', '').strip()

ADMIN_EMAIL = 'admin@local.test'
ADMIN_PASSWORD = 'LocalVerify!2026'


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _log_text(proc):
    """سجلّ العملية من ملفّها المؤقّت (لا من أنبوب)."""
    fh = getattr(proc, '_ep_log', None)
    if not fh:
        return ''
    try:
        fh.seek(0)
        return fh.read().decode('utf-8', 'replace')
    except Exception:
        return ''


def _wait(url, proc, timeout=45):
    import urllib.error
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('العملية ماتت قبل أن تستجيب:\n' + _log_text(proc))
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except urllib.error.HTTPError:
            return                                   # ردّ ولو بخطأ = واقف
        except Exception:
            time.sleep(0.3)
    raise RuntimeError('لم يستجب %s خلال %ss' % (url, timeout))


@contextlib.contextmanager
def _stack(db_path, msg_count=None):
    """منصّةٌ وهميّة + لوحةٌ محلّيّة على منفذين حرّين. `msg_count` يبذر عددًا مختلفًا من
    الرسائل — هو ما يسمح باختبار وجهَي السقف: تحته (٤٠) وفوقه (٥٢٠)."""
    p_port, d_port = _free_port(), _free_port()
    argv = [sys.executable, os.path.join(HARNESS, 'run_dash.py'), str(d_port),
            str(db_path), 'http://127.0.0.1:%d' % p_port]
    if msg_count is not None:
        argv.append(str(msg_count))
    # ⛔ لا `subprocess.PIPE` هنا: لا أحد يقرأ الأنبوب، وخادم التطوير يسجّل كل طلبٍ — فبعد
    # ~٦٤ كيلوبايت (بضع عشرات من تنقّلات الاختبار) يمتلئ الأنبوب ويتجمّد الخادم على write()
    # فتسقط الاختبارات المتأخّرة بـ«Timeout» لسببٍ لا علاقة له بما تقيسه. ملفّان مؤقّتان
    # يستوعبان السجلّ كلّه ويظلّان مقروءَين عند الفشل.
    plog, dlog = tempfile.TemporaryFile(), tempfile.TemporaryFile()
    plat = subprocess.Popen([sys.executable, os.path.join(HARNESS, 'fake_platform.py'), str(p_port)],
                            stdout=plog, stderr=subprocess.STDOUT)
    dash = subprocess.Popen(argv, stdout=dlog, stderr=subprocess.STDOUT)
    plat._ep_log, dash._ep_log = plog, dlog
    try:
        _wait('http://127.0.0.1:%d/api/bridge/ops/queue' % p_port, plat)
        _wait('http://127.0.0.1:%d/' % d_port, dash)
        yield 'http://127.0.0.1:%d' % d_port
    finally:
        for pr in (dash, plat):
            pr.terminate()
            try:
                pr.wait(timeout=5)
            except Exception:
                pr.kill()
        for fh in (plog, dlog):
            try:
                fh.close()
            except Exception:
                pass


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    with _stack(tmp_path_factory.mktemp('ui') / 'ui.db') as url:
        yield url


@pytest.fixture(scope='module')
def pw():
    """سياق playwright واحدٌ للملفّ كلّه: فتح سياقٍ ثانٍ بينما الأوّل قائم يرمي
    «Sync API inside the asyncio loop» — فكل متصفّحٍ هنا يُولد من هذا الواحد."""
    with sync_playwright() as p:
        yield p


def _login(pw, url, viewport=None):
    try:
        br = pw.chromium.launch()
    except Exception as exc:                         # متصفّح غير منزَّل
        pytest.skip('chromium غير متاح لـplaywright: %s' % exc)
    ctx = br.new_context(viewport=viewport or {'width': 1280, 'height': 900}, locale='ar-EG')
    pg = ctx.new_page()
    pg.goto(url, wait_until='networkidle')
    pg.fill('#epLogin input[type=email]', ADMIN_EMAIL)
    pg.fill('#epLogin input[type=password]', ADMIN_PASSWORD)
    pg.click('#epLoginBtn')
    pg.wait_for_selector('#epLogin', state='detached', timeout=20000)
    return br, pg


@pytest.fixture(scope='module')
def page(server, pw):
    br, pg = _login(pw, server)
    pg.set_default_navigation_timeout(60000)
    pg.wait_for_timeout(1500)
    yield pg
    br.close()


def _go(page, server, mod):
    """تنقّلٌ نظيف عبر **الرابط المباشر**: goto إلى هاشٍ مختلفٍ فقط لا يعيد تحميل المستند
    (نفس الوثيقة، تغيّر الجزء وحده) — فالسكربت لا يُعاد تشغيله ويبقى `current` على حاله،
    وهو فخٌّ يجعل الاختبار يقيس الشاشة السابقة ويمرّ كذبًا. لذلك: goto ثم reload صريح.

    ⛔ لا `networkidle` هنا: اللوحة تفتح عشرات نداءات الجسر معًا، فشرط «هدوء الشبكة» يصير
    رهانًا على عتادٍ فارغ — سقط بعد ٤٠ تنقّلًا في نفس الجلسة لسببٍ لا يخصّ ما يُقاس.
    الانتظار الصحيح هو انتظار **ما نقيسه**: طبقة الربط جاهزة والشاشة رُسمت."""
    page.goto(server + '/#' + mod)
    page.reload(wait_until='domcontentloaded')
    _until(page, "!!(window.EP && window.EP.authed && document.getElementById('view')"
                 " && document.getElementById('view').innerHTML.trim().length>120)", 40000)
    page.wait_for_timeout(1400)


def _until(page, expr, timeout=30000, step=150):
    """انتظارٌ آمنٌ تحت CSP: `wait_for_function` تحقن مُستطلِعًا يستدعي `eval` داخل الصفحة،
    و`script-src` هنا بلا `unsafe-eval` — فتنفجر **فقط** حين لا يتحقّق الشرط من أول نظرة،
    أي أنها تمرّ صدفةً وتنفجر يوم يبطؤ التحميل. القياس من بايثون عبر `evaluate` لا يمسّ CSP."""
    deadline = time.time() + timeout / 1000.0
    last = None
    while time.time() < deadline:
        last = page.evaluate(expr)
        if last:
            return last
        page.wait_for_timeout(step)
    raise AssertionError('لم يتحقّق الشرط خلال %sms: %s (آخر قيمة: %r)' % (timeout, expr, last))


def _shot(page, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        page.screenshot(path=os.path.join(SHOTS, name), full_page=False)


# ---------------------------------------------------------------- ١) الشريط

def test_rail_draws_five_groups_then_the_pinned_company_surface(page):
    groups = page.eval_on_selector_all('.rail .navwrap .grp', 'els=>els.map(e=>e.textContent.trim())')
    assert groups == ['شغل النهاردة', 'الناس والدورات', 'الفلوس', 'الطلب', 'التسويق والمحتوى']
    pinned = page.eval_on_selector_all('#coPin .item', 'els=>els.map(e=>e.dataset.mod)')
    assert pinned == ['investment', 'targets', 'ai', 'settings']


def test_pinned_surface_is_visible_without_scrolling_the_rail(page):
    """⛔ جوهر الشكوى: البنود الأربعة **مرئيّة** لا «موجودة». نقيس أنها داخل حدود الشريط."""
    box = page.eval_on_selector('#coPin', 'e=>{const r=e.getBoundingClientRect();'
                                          'return {top:r.top,bottom:r.bottom,h:r.height};}')
    vh = page.viewport_size['height']
    assert box['h'] > 0 and 0 < box['top'] < vh and box['bottom'] <= vh + 1, box
    assert page.eval_on_selector_all('#coPin .item', 'els=>els.every(e=>e.offsetHeight>0)')


def test_the_default_screen_after_login_is_the_inbox(page, server):
    page.goto(server, wait_until='networkidle')
    page.wait_for_timeout(1200)
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'inbox'


# ---------------------------------------------------------------- ٢) الوارد

def test_inbox_shows_more_than_the_old_twenty_five_row_cap(page, server):
    _go(page, server, 'inbox')
    n = int(page.inner_text('#inboxN').strip() or '0')
    assert n > 25, 'الوارد ما زال مقصوصًا عند سقفٍ صامت: %d صفًّا' % n
    rows = page.eval_on_selector_all('#rows .row', 'els=>els.length')
    assert rows == n
    assert not page.eval_on_selector_all('.policy', 'els=>els.some(e=>/الطابور مقصوص/.test(e.textContent))')


def test_messages_chip_lists_the_messages_and_the_drawer_replies(page, server):
    _go(page, server, 'inbox')
    chips = page.eval_on_selector_all('#filters .chip', 'els=>els.map(e=>e.textContent.trim())')
    assert any(c.startswith('رسائل') for c in chips), chips
    page.click('#filters .chip[data-f="t:messages"]')
    page.wait_for_timeout(400)
    listed = page.eval_on_selector_all('#rows .row', 'els=>els.length')
    assert listed > 25, listed
    # الصفّ يعلن مصدره، والدرج يحمل زرّ الردّ نفسه (لا «فتح الرسائل» ثم بحث)
    assert 'من الموقع' in page.inner_text('#rows')
    page.click('#rows .row:first-child')
    page.wait_for_timeout(300)
    acts = page.eval_on_selector_all('#drawer .acts [data-a]', 'els=>els.map(e=>e.dataset.a)')
    assert 'msg_reply' in acts and 'msg_del' in acts, acts
    # الردّ ينفَّذ فعلًا: نُدخل النصّ في prompt ثم نتأكّد أن الصفّ غادر طابور «الجديدة».
    before = int(page.inner_text('#inboxN').strip())
    page.once('dialog', lambda d: d.accept('تم استلام رسالتك، وهذا ردّي.'))
    page.click('#drawer [data-a="msg_reply"]')
    page.wait_for_timeout(2500)
    after = int(page.inner_text('#inboxN').strip())
    assert after == before - 1, (before, after)


def test_the_platform_waiting_queue_is_rendered_in_the_inbox(page, server):
    _go(page, server, 'inbox')
    txt = page.inner_text('#view')
    assert 'كل اللي مستنيك' in txt
    assert 'طلبات مدرّبين' in txt and 'مسودّات مواضيع' in txt
    assert 'طلب بلا أول رد منذ 40 ساعة' in txt        # تنبيهات المنصّة تُطبع حرفيًّا


def test_the_merged_overview_kpi_strip_sits_on_top_of_the_inbox(page, server):
    """شريط «نظرة عامة» بعد الدمج = سياق الشركة وحده. ثلاثة مربّعات، ولا رقم وارد فيها."""
    _go(page, server, 'inbox')
    assert page.eval_on_selector('#ovKpis', 'e=>!!e')
    txt = page.inner_text('#ovKpis')
    for label in ('مستخدمو المنصة', 'صافي الربح', 'محجوز في الضمان'):
        assert label in txt
    assert page.eval_on_selector_all('#ovKpis .kpi', 'els=>els.length') == 3
    for gone in ('وارد يحتاج تصرّفك', 'وارد جديد', 'متأخّر'):
        assert gone not in txt, gone


def test_only_one_strip_prints_inbox_numbers_and_late_is_defined_once(page, server):
    """⛔ عدّادٌ يخالف نفسه: شريطان فوق بعضهما كانا يحسبان «متأخّر» بتعبيرين مختلفين،
    فطبعت الشاشة الواحدة رقمَي تأخّرٍ متناقضين. الآن: شريطٌ واحد يملك كل رقم وارد،
    و«متأخّر» يُقرأ من `inboxLateCount()` في القيمة والوصف والشريحة معًا."""
    _go(page, server, 'inbox')
    # لا مربّع وارد خارج شريط الفرز
    strips = page.eval_on_selector_all('#view .kpis', 'els=>els.map(e=>e.id)')
    assert strips == ['ovKpis', 'kpis'], strips
    tiles = page.eval_on_selector_all('#kpis .kpi', 'els=>els.map(e=>e.dataset.f)')
    assert tiles == ['all', 'human', 'auto', 'late']
    late_tile = page.inner_text('#kpis .kpi[data-f="late"]')
    late_n = page.evaluate('inboxLateCount()')
    chip = page.eval_on_selector_all(
        '#filters .chip', 'els=>els.filter(e=>e.dataset.f==="late").length')
    # القيمة والوصف والشريحة والفلترة: أربعتها من نفس المصدر، فلا يمكن أن تختلف
    assert page.evaluate("INBOX.filter(i=>inboxMatches(i,'late')).length") == late_n
    if late_n:
        assert chip == 1
        assert 'فات ميعاده أو قارَبه' in late_tile
        page.click('#filters .chip[data-f="late"]')
        page.wait_for_timeout(400)
        assert page.eval_on_selector_all('#rows .row', 'els=>els.length') == late_n
        page.click('#filters .chip[data-f="all"]')
        page.wait_for_timeout(300)
    else:
        assert chip == 0
        assert 'لا شيء فات ميعاده' in late_tile
    # ولا رقمٌ آخر يدّعي أنه «متأخّر» في أي مكان على الشاشة
    assert page.inner_text('#view').count('متأخّر عن المهلة') == 1


# ---------------------------------------------------------------- ٣) تحويل الروابط المبتلَعة

@pytest.mark.parametrize('deep,expect_mod', [('overview', 'inbox'), ('messages', 'inbox'),
                                             ('packages', 'finance')])
def test_deep_links_to_swallowed_screens_land_on_their_heir(page, server, deep, expect_mod):
    _go(page, server, deep)
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == expect_mod


def test_the_messages_deep_link_lands_with_the_messages_chip_active(page, server):
    _go(page, server, 'messages')
    active = page.eval_on_selector('#filters .chip.on', 'e=>e.dataset.f')
    assert active == 't:messages'


def test_the_packages_deep_link_lands_on_the_unsettled_pricing_tab(page, server):
    _go(page, server, 'packages')
    assert 'الباقات — تسعير غير مُرسى' in page.inner_text('#finTabs')
    assert page.eval_on_selector('#finTabs .tab.on', 'e=>e.dataset.t') == 'packages'
    assert 'تسعير غير مُرسى' in page.inner_text('#finBody')


def test_the_overview_module_has_no_row_in_the_rail(page):
    mods = page.eval_on_selector_all('.rail .item', 'els=>els.map(e=>e.dataset.mod)')
    assert 'overview' not in mods and 'messages' not in mods and 'packages' not in mods
    assert len(mods) == 16, mods            # ١٢ ظاهرًا + ٤ مثبَّتة


# ---------------------------------------------------------------- ٤) المالية

def test_finance_carries_the_five_absorbed_tabs(page, server):
    """`stuck` انضمّ بعد مراجعة ٢٠٢٦-٠٩-٠٩: «أوامر دفع متعثّرة» مالٌ **وارد**، وكان يُوجَّه
    إلى «السحوبات» (مالٌ خارج) — تبويبٌ لكل اتجاه. و`investorwd` انضمّ بعد جولتها الثانية:
    دفتر اللوحة (سحوبات المستثمرين) ودفتر المنصّة (سحوبات المحافظ) كانا في تبويبٍ واحد
    فوقه عدّادٌ لا يعدّ إلا أحدهما — **تبويبٌ لكل دفتر**."""
    _go(page, server, 'finance')
    tabs = page.eval_on_selector_all('#finTabs .tab', 'els=>els.map(e=>e.dataset.t)')
    assert tabs == ['summary', 'revenues', 'expenses', 'withdrawals', 'investorwd',
                    'stuck', 'pnl', 'packages']


def test_the_platform_pnl_report_reaches_the_finance_screen(page, server):
    _go(page, server, 'finance')
    page.click('#finTabs .tab[data-t="pnl"]')
    page.wait_for_timeout(1500)
    body = page.inner_text('#finBody')
    assert '2026-09' in body
    assert 'استشارات' in body and 'دورات' in body
    assert 'SAR' in body                              # العملات لا تُجمع: تظهر كما هي
    # الأرقام تُعرض بأرقامٍ عربيّة-هنديّة (toLocaleString('ar-EG')) — نقيسها كما تُقرأ فعلًا.
    assert '٨٠١' in body                              # الصافي/التكاليف من دفتر المنصّة
    assert 'الصافي بالجنيه' in body


def test_the_revenue_curve_moved_into_finance(page, server):
    _go(page, server, 'finance')
    assert 'نمو الإيرادات الشهري' in page.inner_text('#finBody')


# ---------------------------------------------------------------- ٥) الضمان

def test_escrow_declares_itself_suspended_on_the_sessions_tab(page, server):
    _go(page, server, 'escrow')
    assert 'موقوف حتى أوّل جلسة مدفوعة' in page.inner_text('#view')


def test_the_manual_payments_tab_receives_what_the_inbox_routes_to_it(page, server):
    """⛔ الوجهة المعطّلة: الوارد كان يوجّه الدفعات اليدوية إلى `escrow` وهناك لا شاشة تستقبلها."""
    _go(page, server, 'inbox')
    page.click('#filters .chip[data-f="t:money"]')
    page.wait_for_timeout(400)
    assert page.eval_on_selector_all('#rows .row', 'els=>els.length') == 2
    page.click('#rows .row:first-child')
    page.wait_for_timeout(300)
    page.click('#drawer [data-a="goto"]')             # «فتح الضمان والنزاعات»
    page.wait_for_timeout(1500)
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'escrow'
    assert page.eval_on_selector('#escTabs .tab.on', 'e=>e.dataset.t') == 'manual'
    rows = page.inner_text('#escRows')
    assert 'سلمى عبد الله' in rows and 'ياسر فؤاد' in rows
    assert 'موقوف حتى أوّل جلسة مدفوعة' not in page.inner_text('#view')   # التبويب الشغّال بلا لافتة وقف


def test_the_manual_payment_drawer_offers_the_same_decision_as_the_inbox(page, server):
    _go(page, server, 'escrow')
    page.click('#escTabs .tab[data-t="manual"]')
    page.wait_for_timeout(500)
    page.click('#escRows .row:first-child')
    page.wait_for_timeout(300)
    acts = page.eval_on_selector_all('#drawer .acts [data-a]', 'els=>els.map(e=>e.dataset.a)')
    assert acts == ['pay_ok', 'pay_no', 'pay_inbox']


# ---------------------------------------------------------------- ٦) لا شاشة فقدت بابها

@pytest.mark.parametrize('mod', ['inbox', 'invites', 'courses', 'team', 'users', 'finance',
                                 'escrow', 'market', 'analysis', 'knowledge', 'topics',
                                 'marketing', 'investment', 'targets', 'ai', 'settings',
                                 'partners', 'foundation', 'tutorials'])
def test_every_module_still_renders_something(page, server, mod):
    _go(page, server, mod)
    assert page.eval_on_selector('#view', 'e=>e.innerHTML.trim().length') > 120, mod


# ---------------------------------------------------------------- ٧) الشريط الذي كُتب ولم يُرسم

def test_the_tutorials_tab_bar_survives_the_loader_rerender(page, server):
    """⛔ فخّ الريبو المسجَّل: `viewTutorials` كانت تُستدعى ثم يُحقن الشريط فوقها، فيستيقظ
    `EP.ensure('tutorials')` ويعيد كتابة نفس العقدة فيمسحه. نقيس **بعد** جهوز المُحمِّل،
    وعلى مدى ثوانٍ — لا في الإطار الأول وحده."""
    _go(page, server, 'tutorials')
    _until(page, "!!(window.EP && ['ready','error'].indexOf(EP.state.tutorials)>=0)", 20000)
    for wait in (50, 200, 600, 1500, 3000):
        page.wait_for_timeout(wait)
        tabs = page.eval_on_selector_all('#topicsTabs .tab', 'els=>els.map(e=>e.dataset.tt)')
        assert len(tabs) == 9, (wait, tabs)
        assert tabs[-1] == 'tutorials'
        assert page.eval_on_selector('#topicsTabs .tab.on', 'e=>e.dataset.tt') == 'tutorials'
    # الطريق ذهابًا وإيابًا: الشريط يعمل، والشريط الجانبي يُبرز «المحتوى»
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'topics'
    assert page.eval_on_selector('#tutHost', 'e=>e.innerHTML.trim().length') > 120
    page.click('#topicsTabs .tab[data-tt="articles"]')
    page.wait_for_timeout(900)
    assert page.eval_on_selector('#topicsTabs .tab.on', 'e=>e.dataset.tt') == 'articles'


# ---------------------------------------------------------------- ٨) الصدق يوم يُقَصّ الطابور

def test_the_truncation_notice_actually_renders_when_a_source_exceeds_the_cap(pw, tmp_path):
    """⛔ ضمانةٌ بلا اختبار = كودٌ لم يُشغَّل مرّة. السقف ٥٠٠/مصدر، فنبذر ٥٢٠ رسالة ونتأكّد
    أن السطر «معروض ٥٠٠ من ٥٢٠» يُرسَم باسم مصدره — وأن الجدول يقف عند ٥٠٠ لا يصمت."""
    with _stack(tmp_path / 'big.db', msg_count=520) as url:
        br, pg = _login(pw, url)
        try:
            _until(pg, "!!(window.EP && EP.state.inbox==='ready')", 60000)
            pg.wait_for_timeout(1200)
            trunc = pg.evaluate('window.INBOX_TRUNCATED || []')
            assert trunc and any('رسائل الموقع' in t for t in trunc), trunc
            strips = pg.eval_on_selector_all('.policy', 'els=>els.map(e=>e.textContent)')
            hit = [t for t in strips if 'الطابور مقصوص' in t]
            assert hit, strips
            assert 'رسائل الموقع' in hit[0] and 'معروض 500 من 520' in hit[0], hit[0]
            # المصدر المقصوص وحده يقف عند السقف؛ بقيّة الطوابير تمرّ كاملة
            assert pg.evaluate("INBOX.filter(i=>inboxType(i)==='messages').length") == 500
            assert int(pg.inner_text('#inboxN').strip()) == 503     # ٥٠٠ + دفعتان + طلب مدرّب
        finally:
            br.close()


# ---------------------------------------------------------------- ٩) لا صفرَ يصف غير ما تحته

def test_the_manual_tab_shows_manual_counters_not_zeroed_escrow_ones(page, server):
    """⛔ أربعة أصفارٍ فوق صفّين حيّين: مؤشّرات جلسات الضمان لا تصف الدفعات اليدوية."""
    _go(page, server, 'escrow')
    page.click('#escTabs .tab[data-t="manual"]')
    page.wait_for_timeout(600)
    assert page.eval_on_selector('#manKpis', 'e=>!!e')
    assert page.eval_on_selector_all('#escKpis', 'els=>els.length') == 0
    txt = page.inner_text('#manKpis')
    for label in ('بانتظار التأكيد', 'بلا إيصال مرفوع', 'إجمالي المبلغ'):
        assert label in txt, label
    for gone in ('محجوز حاليًا', 'نزاعات مفتوحة', 'حُرِّر مؤخرًا'):
        assert gone not in txt, gone
    # العدّاد الأول = عدد الصفوف تحته بالضبط
    rows = page.eval_on_selector_all('#escRows .row', 'els=>els.length')
    assert rows == 2
    assert page.inner_text('#manKpis .kpi:first-child b').strip() == '٢'
    assert page.inner_text('#manKpis .kpi:nth-child(2) b').strip() == '١'   # mp-2 بلا إيصال
    assert '١٬٦٥٠' in page.inner_text('#manKpis .kpi:nth-child(3) b')       # ٤٥٠ + ١٢٠٠
    # والتبويبان الموقوفان يحتفظان بمؤشّرات الضمان ولافتة الوقف
    page.click('#escTabs .tab[data-t="sessions"]')
    page.wait_for_timeout(500)
    assert page.eval_on_selector('#escKpis', 'e=>!!e')
    assert 'موقوف حتى أوّل جلسة مدفوعة' in page.inner_text('#view')


def test_the_pnl_drawer_states_that_there_is_no_action_here(page, server):
    """تعليمةٌ لا تُنفَّذ = كذبة: صفوف تقرير المنصّة غير قابلة للنقر، فالدرج لا يقول «اختر بندًا»."""
    _go(page, server, 'finance')
    page.click('#finTabs .tab[data-t="pnl"]')
    page.wait_for_timeout(1200)
    drawer = page.inner_text('#drawer')
    assert 'للقراءة فقط' in drawer and 'لا إجراء هنا' in drawer
    assert 'اختر تبويبًا ثم بندًا' not in drawer
    assert page.eval_on_selector_all('#finBody .row[onclick]', 'els=>els.length') == 0
    page.click('#finTabs .tab[data-t="revenues"]')
    page.wait_for_timeout(700)
    assert 'اختر تبويبًا ثم بندًا' in page.inner_text('#drawer')


# ---------------------------------------------------------------- ١٠) شارات العدّ

def test_the_rail_badges_carry_the_platform_queue_numbers(page, server):
    """الشارة تُكتب من طابور المنصّة نفسه — لا عدٌّ ثانٍ في المتصفّح يخالف «كل اللي مستنيك».
    والقياس من **رابطٍ مباشر إلى شاشةٍ أخرى**: الشارات لا تنتظر زيارة «الوارد»."""
    _go(page, server, 'escrow')
    # ⛔ انتظرْ ما تقيسه، لا نومًا ثابتًا: التأكيدات تحت تقرأ شارات **ثلاثة** مصادر
    # (الطابور · الوارد · الدعوات)، والوارد وحده يفتح عشرة نداءات جسر. ٦٠٠ms كانت تكفي
    # وحدها وتحت الطقم الكامل تسقط — فكان الاختبار أحمر في ~نصف التشغيلات النظيفة.
    _until(page, "!!(window.EP && EP.state.opsQueue==='ready'"
                 " && EP.state.inbox==='ready' && EP.state.invites==='ready')", 30000)
    counts = page.eval_on_selector_all(
        '.rail .item', 'els=>els.filter(e=>e.querySelector(".count"))'
                       '.map(e=>[e.dataset.mod,e.querySelector(".count").textContent])')
    got = dict(counts)
    assert got.get('topics') == '٣١١', got            # مسودّات المواضيع
    assert got.get('team') == '٣', got                # طلبات المدرّبين
    assert got.get('escrow') == '٢', got              # الدفعات اليدوية
    assert got.get('users') == '٩', got               # ليدات الخبراء المؤسسين
    assert got.get('courses') == '١١', got            # ١ + ٧ + ٢ + ١ (دورة حيّة)
    # صفرٌ لا يُرسم: بندٌ بلا طابورٍ ينتظرك يبقى بلا شارة (وإلا بدا كل بندٍ كأن فيه شغلًا)
    assert 'market' not in got and 'analysis' not in got and 'settings' not in got, got
    # المرحلة ٢ أضافت شارتَي «الوارد» و«الدعوات» من مصدريهما (الطابور الموحَّد · طابور
    # الموافقة) — تفصيلهما وعلاقتهما بما تطبعه الشاشة في `test_dash_company_badges.py`.
    assert got.get('invites') == '٣', got
    assert got.get('inbox'), got
    # «تنبيه» أحمر للطوابير التي تجاوز أقدمُها ٢٤ ساعة (٥١س · ٣٠س · ١٦٠٠س · دعوةٌ ٧٢س ·
    # والوارد لأن فيه دفعةً يدويّةً موسومةً متأخّرة)
    alerts = page.eval_on_selector_all('.rail .item.alert', 'els=>els.map(e=>e.dataset.mod)')
    assert sorted(alerts) == ['escrow', 'inbox', 'invites', 'team', 'users'], alerts
