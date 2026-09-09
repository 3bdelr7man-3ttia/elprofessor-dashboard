# -*- coding: utf-8 -*-
"""ثلاثة أعطالٍ من مراجعة ٢٠٢٦-٠٩-٠٩ على شاشة «المالية» — كلٌّ منها «رقمٌ صحيحٌ في مكانٍ خطأ».

Run:  cd backend && python3 -m pytest -q tests/test_dash_finance_sources.py

  ١) **الباقات تهرب من تبويبها.** بعد ابتلاعها في «المالية» صارت تُرسَم في `#pkHost` داخل
     `#finBody`، لكن مساراتِ إعادة الرسم الثلاثة (`pkPersist` · أزرار نافذة الباقة ·
     رابط «إعادة المحاولة») ظلّت تكتب في `#view` — فأوّل حفظٍ أو حذفٍ حقيقيّ يدهس شريط
     التبويبات والملخّص والدرج معًا، وتبقى الباقات وحدها على الشاشة والشريط الجانبي ما زال
     يقول «المالية». الحارس هنا يُشغّل الأفعال الثلاثة ويقيس **الحاوية** بعدها لا الشكل.

  ٢) **شارةٌ فوق قائمةٍ لا تحويها.** عدّاد «سحوبات محافظ» يأتي من `wallet_payouts_pending`
     (مجموعة `wallet_payouts` في مونجو) ويهبط على تبويب «السحوبات» — وكان التبويب يسرد
     `Withdrawal` من SQLite اللوحة (سحوبات المستثمرين): الشارة ١ والشاشة ٠، وكلاهما «صادق»
     عن دفترٍ مختلف. المصدر الآن واحد: جسر المنصّة نفسه.

  ٣) **اتجاهان متعاكسان في تبويبٍ واحد.** «أوامر دفع متعثّرة» أوامرُ بطاقةٍ **واردة** عالقة
     عند `created` (مجموعة `payments`)، وكانت شارتها تهبط على «السحوبات» وهي مالٌ **خارج**
     من المحافظ. لكل اتجاهٍ تبويبه، ومصدر التبويب هو حمولة الطابور نفسها.

⛔ صفر لمسٍ للإنتاج: نفس طقم `uiharness` (منصّةٌ وهميّة + SQLite مؤقّتة + صفر نداء ذكاء).
"""
import os

import pytest

from test_dash_ia_ui import (_go, _login, _shot, _stack, _until,  # noqa: F401
                             playwright, sync_playwright)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')
APP_PY = os.path.join(_ROOT, 'backend', 'app.py')

AR = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')


def _num(txt):
    digits = ''.join(c for c in (txt or '').translate(AR) if c.isdigit())
    return int(digits) if digits else 0


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apijs():
    with open(API_JS, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apppy():
    with open(APP_PY, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def server(tmp_path_factory):
    with _stack(tmp_path_factory.mktemp('fin') / 'fin.db') as url:
        yield url


@pytest.fixture(scope='module')
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope='module')
def page(server, pw):
    br, pg = _login(pw, server)
    pg.set_default_navigation_timeout(60000)
    pg.wait_for_timeout(2500)
    yield pg
    br.close()


def _packages_tab(page, server):
    """يفتح «المالية ← الباقات» وينتظر جهوز المحمّل ورسم مضيف التبويب."""
    _go(page, server, 'packages')
    _until(page, "!!(window.EP && ['ready','error'].indexOf(EP.state.packages)>=0)", 25000)
    _until(page, "!!document.getElementById('pkHost')", 15000)
    page.wait_for_timeout(400)


def _tab_state(page):
    """الحالة التي لا يجوز أن يكسرها أي فعلٍ على الباقات: المضيف داخل جسم التبويب،
    وشريط التبويبات حيّ على «الباقات»، والشريط الجانبي على «المالية»."""
    return page.evaluate(
        "(function(){var host=document.getElementById('pkHost'),"
        "body=document.getElementById('finBody'),"
        "tab=document.querySelector('#finTabs .tab.on'),"
        "nav=document.querySelector('.nav .item.on');"
        "return {host:!!host, inBody:!!(host&&body&&body.contains(host)),"
        " grid:!!document.getElementById('pkGrid'),"
        " tabs:!!document.getElementById('finTabs'),"
        " tab:tab?tab.dataset.t:null, nav:nav?nav.dataset.mod:null,"
        " cards:document.querySelectorAll('#pkGrid .pkcard').length};})()")


# ================================================================ ١) الباقات لا تغادر تبويبها

def test_no_packages_path_writes_into_the_view_node(html):
    """⛔ الحارس النصّي الذي يمنع العودة: `#view` ممنوعٌ في كل مسار باقات. (نفس نمط
    `viewTutorials(document.getElementById('view'))` المحظور في اختبار البنية.)"""
    assert "viewPackages(document.getElementById('view'))" not in html
    # ⛔ والمسار الميت في `renderView` هو نفس الكتابة مكتوبةً بمتغيّر — حُذف لا عُلِّق
    assert 'return viewPackages(v)' not in html
    assert 'function pkRerender(){' in html
    # وكل مسارٍ من الثلاثة يمرّ منه: الحفظ/الحذف · إعادة المحاولة · تبديل بلد المعاينة
    assert 'function pkPersist(nextList){pkRerender();EP.savePackages(nextList,pkRerender);}' in html
    assert "EP.reload('packages',pkRerender)" in html
    assert "EP.ensure('packages',pkRerender)" in html


def test_pkrerender_never_builds_a_screen_out_of_a_late_callback(html):
    """⛔ الهروب المؤجَّل: الرجوع إلى `#view` عند غياب المضيف كان يبني «المالية ← الباقات»
    فوق أي شاشةٍ يكون المؤسس فيها لحظةَ وصول الردّ. المضيف أوّلًا، ثم **حارسٌ لا بناء**:
    إن لم تكن «المالية» حيّةً على تبويب الباقات، لا شيء يحدث. ولا إسنادَ لـ`finTab` هنا
    إطلاقًا — الإسناد هو انتزاعُ المؤسس من تبويبٍ اختاره."""
    blk = html[html.index('function pkRerender(){'):html.index('function viewPackages(v){')]
    assert "document.getElementById('pkHost')" in blk
    assert 'viewPackages(host)' in blk
    assert "current!=='finance'||finTab!=='packages'" in blk, blk
    assert "finTab='packages'" not in blk, blk


def test_the_packages_tab_renders_inside_the_finance_body(page, server):
    _packages_tab(page, server)
    st = _tab_state(page)
    assert st['host'] and st['inBody'], st
    assert st['tab'] == 'packages' and st['nav'] == 'finance', st
    assert st['cards'] == 2, st            # الباقتان الحيّتان من جسر المنصّة
    _shot(page, 'fin_01_packages_tab.png')


def test_saving_a_package_keeps_the_screen_inside_the_finance_tab(page, server):
    """⛔ العطل بعينه: أوّل حفظٍ حقيقيّ كان يدهس شريط التبويبات ويترك الباقات وحدها."""
    _packages_tab(page, server)
    page.click('#pkGrid .pkcard:first-child')
    page.wait_for_timeout(500)
    assert page.eval_on_selector('#pk_s', 'e=>!!e'), 'نافذة الباقة لم تُفتح'
    page.click('#pk_s')
    _until(page, "!!document.getElementById('pkHost')", 20000)
    page.wait_for_timeout(1800)            # بعد PUT ثم إعادة الجلب ثم إعادة الرسم
    st = _tab_state(page)
    assert st['host'] and st['inBody'] and st['tabs'], st
    assert st['tab'] == 'packages' and st['nav'] == 'finance', st
    assert st['cards'] == 2, st
    _shot(page, 'fin_02_packages_after_save.png')


def test_deleting_a_package_keeps_the_screen_inside_the_finance_tab(page, server):
    _packages_tab(page, server)
    page.click('#pkGrid .pkcard:first-child')
    page.wait_for_timeout(500)
    assert page.eval_on_selector('#pk_d', 'e=>!!e'), 'زرّ الحذف غير موجود'
    page.click('#pk_d')
    _until(page, "!!document.getElementById('pkHost')", 20000)
    page.wait_for_timeout(1800)
    st = _tab_state(page)
    assert st['host'] and st['inBody'] and st['tabs'], st
    assert st['tab'] == 'packages' and st['nav'] == 'finance', st


def test_the_retry_link_redraws_into_the_tab_host_not_the_screen(page, server):
    """رابط «إعادة المحاولة» يظهر في حالة الخطأ وحدها — نضعها يدويًّا ثم نضغط الرابط نفسه
    (لا نستدعي الدالّة من بايثون: المقصود هو `onclick` المشحون حرفيًّا)."""
    _packages_tab(page, server)
    page.evaluate("EP.state.packages='error';pkRerender();")
    page.wait_for_timeout(400)
    assert 'إعادة المحاولة' in page.inner_text('#pkHost')
    st_err = _tab_state(page)
    assert st_err['inBody'] and st_err['tab'] == 'packages', st_err
    page.click("#pkHost b:has-text('إعادة المحاولة')")
    _until(page, "!!(window.EP && EP.state.packages==='ready')", 20000)
    page.wait_for_timeout(900)
    st = _tab_state(page)
    assert st['host'] and st['inBody'] and st['tabs'], st
    assert st['tab'] == 'packages' and st['nav'] == 'finance', st
    assert st['cards'] == 2, st
    _shot(page, 'fin_03_packages_after_retry.png')


def test_a_late_packages_callback_cannot_repaint_a_screen_the_founder_left(page, server):
    """⛔ **السباق الحقيقي**: احفظ باقةً ثم غادر التبويب قبل أن يعود الردّ. المسار كما هو في
    الإنتاج — `EP.savePackages(next,pkRerender)` ثم `EP.reload('packages',pkRerender)` —
    والتأخير مفروضٌ على نداء `/api/packages` نفسه كي يكون السباق مضمونًا لا صدفة. المطلوب
    بعد استقرار المحمّل: الشاشة **هي الوارد**، بلا شريط تبويبات مالية ولا شبكة باقات."""
    _packages_tab(page, server)
    # ⛔ التأخير من داخل المتصفّح (CDP) لا من مُعترِضٍ في بايثون: مُعترِضٌ ينام يوقف موزّع
    # playwright نفسه، فتُسلسَل نقراتُنا خلف الردّ ولا يقع السباق أصلًا — فيمرّ الاختبار
    # على الكود المعطوب. `emulateNetworkConditions` يبطّئ الشبكة والصفحة وحدها.
    cdp = page.context.new_cdp_session(page)
    cdp.send('Network.enable', {})
    slow = {'offline': False, 'latency': 700, 'downloadThroughput': -1, 'uploadThroughput': -1}
    fast = {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1}
    cdp.send('Network.emulateNetworkConditions', slow)
    try:
        page.click('#pkGrid .pkcard:first-child')
        page.wait_for_timeout(600)
        assert page.eval_on_selector('#pk_s', 'e=>!!e'), 'نافذة الباقة لم تُفتح'
        page.click('#pk_s')
        page.wait_for_timeout(250)
        page.click('.rail .item[data-mod="inbox"]')     # غادر قبل أن يعود الردّ
        page.wait_for_timeout(300)
        _until(page, "!!(window.EP && EP.state.packages==='ready')", 40000)
        page.wait_for_timeout(1500)                     # مهلةٌ كافية لأي ردٍّ متأخّر
    finally:
        cdp.send('Network.emulateNetworkConditions', fast)
        cdp.detach()
    st = page.evaluate(
        "(function(){var nav=document.querySelector('.nav .item.on');"
        "return {finTabs:!!document.getElementById('finTabs'),"
        " host:!!document.getElementById('pkHost'),"
        " grid:!!document.getElementById('pkGrid'),"
        " nav:nav?nav.dataset.mod:null,"
        " title:(document.getElementById('pageTitle')||{}).textContent.trim(),"
        " cur:window.current};})()")
    assert st['nav'] == 'inbox' and st['title'] == 'الوارد', st
    assert not st['finTabs'] and not st['host'] and not st['grid'], st
    _shot(page, 'fin_07_late_callback_left_the_inbox_alone.png')


def test_a_late_packages_callback_cannot_yank_the_founder_off_another_finance_tab(page, server):
    """الوجه الثاني: المؤسس على «المالية ← الإيرادات» — نداء `pkRerender` (وهو حرفيًّا ما
    تستدعيه `savePackages`/`reload`) لا يجوز أن ينقله إلى «الباقات»."""
    _go(page, server, 'finance')
    page.click('#finTabs .tab[data-t="revenues"]')
    page.wait_for_timeout(600)
    before = page.eval_on_selector('#finTabs .tab.on', 'e=>e.dataset.t')
    page.evaluate('pkRerender()')
    page.wait_for_timeout(400)
    after = page.eval_on_selector('#finTabs .tab.on', 'e=>e.dataset.t')
    assert before == after == 'revenues', (before, after)
    assert page.evaluate("!document.getElementById('pkHost')")


# ================================================================ ٢) الشارة والقائمة مصدرٌ واحد

def test_the_wallet_payout_proxy_reads_the_pending_bridge_list(apppy, apijs, html):
    """المصدر مكتوبٌ مرّة واحدة: بروكسي ⇒ محمّل ⇒ قائمة ⇒ عدّاد الشارة."""
    assert "@app.route('/api/platform-wallet-payouts'" in apppy
    assert "_platform_proxy('GET', '/api/bridge/wallet-payouts'" in apppy
    assert 'get("/platform-wallet-payouts")' in apijs
    assert 'function walletPayouts(){' in html and 'function walletPayoutsCount(Q){' in html
    # الشارة تقرأ العدّاد المشتقّ من القائمة، لا `Q.wallet_payouts_pending` مباشرةً
    blk = html[html.index('function opsQueueCounters(Q){'):html.index('function goOps(')]
    assert "['سحوبات محافظ',walletPayoutsCount(Q),'finance','wallet_payouts_pending']" in blk
    assert 'n(Q.wallet_payouts_pending)' not in blk


def test_the_badge_number_and_the_withdrawals_rows_agree(page, server):
    """⛔ الحارس الحقيقي: بذرةٌ واحدة معلَّقة في الطقم ⇒ الشارة ١ **وصفٌّ واحد** تحتها،
    وكلاهما من نفس النداء. والطقم يبذر **أيضًا** سحب مستثمرٍ واحدًا في دفتر اللوحة: لولاه
    كان الاتفاق صدفةَ صفرٍ لا نتيجةَ تصميم — فوجوده هو ما يجعل هذا الاختبار قابلًا للسقوط."""
    _go(page, server, 'inbox')
    _until(page, "!!(window.EP && EP.state.opsQueue==='ready'"
                 " && EP.state.walletPayouts==='ready')", 30000)
    chip = page.inner_text('.opsq[data-k="wallet_payouts_pending"]')
    assert 'سحوبات محافظ' in chip
    assert _num(chip) == 1, chip
    assert page.evaluate('walletPayouts().length') == 1
    assert page.evaluate('walletPayoutsCount((window.EP&&EP.data.opsQueue)||null)') == 1
    _shot(page, 'fin_04_queue_chip.png')
    page.click('.opsq[data-k="wallet_payouts_pending"]')
    page.wait_for_timeout(1400)
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'finance'
    assert page.eval_on_selector('#finTabs .tab.on', 'e=>e.dataset.t') == 'withdrawals'
    rows = page.eval_on_selector_all('#finBody .row', 'els=>els.length')
    assert rows == 1, rows
    txt = page.inner_text('#finBody')
    assert 'د. هالة سمير' in txt and 'محفظة المنصّة' in txt, txt
    assert '١٬٢٠٠' in txt, txt
    # ⛔ ولا صفَّ من الدفتر الآخر تحت هذا العدّاد: سحب المستثمر المبذور (١٥٬٠٠٠) في تبويبه
    assert 'مستثمر تجريبي' not in txt, txt
    assert '١٥٬٠٠٠' not in txt, txt
    # وعدّاد التبويب نفسه = الصفوف المرسومة تحته = رقم الشارة
    assert _num(page.inner_text('#finTabs .tab[data-t="withdrawals"]')) == rows
    assert 'سحوبات المحافظ' in page.inner_text('#finTabs .tab[data-t="withdrawals"]')
    _shot(page, 'fin_05_withdrawals_rows.png')


def test_the_investor_book_keeps_its_own_tab_and_its_own_counter(page, server):
    """⛔ **دفتران تحت عدّادٍ واحد**: الشارة تعدّ محافظ المنصّة وحدها، والتبويب كان يسرد
    المحافظ **زائد** سحوبات المستثمرين — فأوّل صفٍّ مستثمرٍ حقيقيّ يجعل «١» فوق صفّين،
    ومربّع «سحوبات بانتظار» يجمع الدفترين في مبلغٍ واحد. لكلٍّ تبويبُه وعدّادُه الآن."""
    _go(page, server, 'finance')
    _until(page, "!!(window.EP && EP.state.walletPayouts==='ready')", 30000)
    assert page.evaluate('walletPayouts().length') == 1
    assert page.evaluate('investorWithdrawals().length') == 1
    tab = page.inner_text('#finTabs .tab[data-t="investorwd"]')
    assert 'سحوبات المستثمرين' in tab and _num(tab) == 1, tab
    page.click('#finTabs .tab[data-t="investorwd"]')
    page.wait_for_timeout(800)
    rows = page.eval_on_selector_all('#finBody .row', 'els=>els.length')
    assert rows == 1, rows
    txt = page.inner_text('#finBody')
    assert 'مستثمر تجريبي' in txt and 'دفتر اللوحة' in txt, txt
    assert '١٥٬٠٠٠' in txt, txt
    assert 'د. هالة سمير' not in txt, txt
    # والمربّع لا يجمع الدفترين تحت عنوانٍ واحد: مبلغُه للمحافظ، والمستثمرون معدودون باسمهم
    kpi = page.eval_on_selector_all(
        '#view .kpi', "els=>els.find(e=>/سحوبات/.test(e.textContent)).textContent")
    assert 'سحوبات محافظ بانتظار' in kpi, kpi
    assert '١٬٢٠٠' in kpi and '١٦٬٢٠٠' not in kpi, kpi
    assert 'للمستثمرين تبويبهم' in kpi, kpi
    _shot(page, 'fin_08_investor_withdrawals_tab.png')


def test_the_payout_row_offers_no_dashboard_only_decision(page, server):
    """⛔ مساحة قرارٍ كاذبة: `PUT /admin/withdrawals/{id}` يكتب في دفتر اللوحة، فلا يجوز أن
    يظهر فوق طلب محفظةٍ على المنصّة. الدرج يقول أين تُنفَّذ التسوية بدل زرٍّ لا يفعلها."""
    _go(page, server, 'finance')
    page.click('#finTabs .tab[data-t="withdrawals"]')
    page.wait_for_timeout(700)
    page.click('#finBody .row:first-child')
    page.wait_for_timeout(400)
    drawer = page.inner_text('#drawer')
    assert 'محفظة المنصّة' in drawer
    assert 'التسوية تتمّ على المنصّة' in drawer
    assert page.eval_on_selector_all('#drawer [data-a]', 'els=>els.length') == 0


# ================================================================ ٣) الوارد لا يهبط في الصادر

def test_stuck_card_orders_land_on_their_own_tab(page, server):
    """⛔ الوجهة المقلوبة: أوامرُ دفعٍ واردة كانت تفتح قائمة سحوباتٍ خارجة."""
    _go(page, server, 'inbox')
    _until(page, "!!(window.EP && EP.state.opsQueue==='ready')", 30000)
    chip = page.inner_text('.opsq[data-k="stuck_card_payments"]')
    assert 'أوامر دفع متعثّرة' in chip and _num(chip) == 2, chip
    page.click('.opsq[data-k="stuck_card_payments"]')
    page.wait_for_timeout(1400)
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'finance'
    assert page.eval_on_selector('#finTabs .tab.on', 'e=>e.dataset.t') == 'stuck'
    assert 'أوامر دفع متعثّرة' in page.inner_text('#finTabs')
    rows = page.eval_on_selector_all('#finBody .row', 'els=>els.length')
    assert rows == 2, rows
    txt = page.inner_text('#finBody')
    assert 'nour@example.test' in txt and 'omar@example.test' in txt, txt
    assert 'paytabs' in txt, txt
    # نوع الأمر بالعربي — لا مفاتيح إنجليزية خامًا في وجه المؤسس
    assert 'دورة' in txt and 'توثيق إجابة' in txt, txt
    assert 'course' not in txt and 'verify' not in txt, txt
    # وليست قائمة السحوبات: صفّ السحب لا يظهر هنا إطلاقًا
    assert 'د. هالة سمير' not in txt, txt
    assert 'دفعات واردة لم تكتمل' in page.inner_text('#finBody')
    _shot(page, 'fin_06_stuck_orders_tab.png')


def test_the_stuck_tab_promises_no_action_it_cannot_perform(page, server):
    _go(page, server, 'finance')
    page.click('#finTabs .tab[data-t="stuck"]')
    page.wait_for_timeout(800)
    assert page.eval_on_selector_all('#finBody .row[onclick]', 'els=>els.length') == 0
    drawer = page.inner_text('#drawer')
    assert 'للقراءة فقط' in drawer and 'لا إجراء عليها من اللوحة' in drawer


def test_the_two_money_directions_never_share_a_tab(page, server):
    """التبويبان يقرآن مجموعتين مختلفتين — والحارس يمنع أن يعود أحدهما يسرد الآخر."""
    _go(page, server, 'finance')
    page.click('#finTabs .tab[data-t="withdrawals"]')
    page.wait_for_timeout(700)
    out = page.inner_text('#finBody')
    page.click('#finTabs .tab[data-t="stuck"]')
    page.wait_for_timeout(700)
    inn = page.inner_text('#finBody')
    assert 'nour@example.test' not in out and 'د. هالة سمير' not in inn, (out, inn)


def test_stuck_orders_badge_uses_platform_count_and_list_declares_truncation():
    """الشارة والتبويب يطبعان count من المنصّة (حتى ٢٠٠) والقائمة تعلن «أوّل N من M» حين تُقصّ."""
    import os, re
    html = open(os.path.join(os.path.dirname(__file__), '..', '..', 'dashboard-cloud', 'index.html'), encoding='utf-8').read()
    assert 'function stuckCount()' in html
    assert "أوامر دفع متعثّرة (${stuckCount()})" in html
    assert 'تُعرض أوّل ' in html and "n.textContent=STKN" in html
    # لا يبقى استعمالٌ للعدّ بطول القائمة في رأس التبويب أو الشارة
    assert "n.textContent=STK.length" not in html
