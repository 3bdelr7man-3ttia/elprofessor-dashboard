# -*- coding: utf-8 -*-
"""سطح «الشركة» بعد الدمج · شارات العدّ · الكود الميت المحذوف.

Run:  cd backend && python3 -m pytest -q tests/test_dash_company_badges.py

ثلاثة وعودٍ من مراجعة ٢٠٢٦-٠٩-٠٩ (`AUDIT/dash/00_dashboard_review.md` §٤ وسؤالا ٨ و١٢):

  ١) **الدمج**: الاستثمار + الشركاء ⇒ شاشةٌ واحدة بجدولٍ واحد وتبويبين؛ ومرحلة التأسيس +
     الأهداف ⇒ شاشةُ مراجعةٍ شهريةٍ واحدة بتبويبين. الوعد المقيس: لا شاشة اختفت — كلٌّ منهما
     صار **تبويبًا** له بابٌ يُفتح، والرابط القديم يهبط على تبويبه لا على أوّل تبويب.

  ٢) **الشارات**: «من غير الشارات أي ترتيب يبقى تخمين». الحارس هنا ليس «هل الرقم مرسوم؟»
     بل **هل هو نفس الرقم الذي تحته في الشاشة؟** — عدّادان لطابورٍ واحد أسوأ من صفر عدّادات.

  ٣) **الكود الميت**: اختباراتٌ سالبة. النوادي · فرع المعلنون · كروت الموديولات · زرّا
     «قريبًا» — كلّها كودٌ بلا مدخل، وبعضها **مساحة قرارٍ كاذبة** (زرّ اعتمادٍ يكتب في
     الذاكرة ويطبع نجاحًا). السالب هو الاختبار الوحيد الذي يمنع عودتها بلا انتباه.

⛔ صفر لمسٍ للإنتاج: نفس طقم `uiharness` (منصّةٌ وهميّة + SQLite مؤقّتة + صفر نداء ذكاء).
"""
import os
import re

import pytest

from test_dash_ia_ui import (_login, _go, _stack, _shot, playwright,  # noqa: F401
                             sync_playwright)

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
APP_PY = os.path.join(_ROOT, 'backend', 'app.py')


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apppy():
    with open(APP_PY, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def code(html):
    """`index.html` بلا تعليقات — الاختبار السالب يقيس **الكود المشحون** لا شواهد القبور.

    ⛔ الفخّ الذي وقع أوّل مرّة: كل حذفٍ هنا ترك خلفه تعليقًا يشرح ما حُذف وليه (وهو صواب،
    فبدونه يعود الكود الميت بعد شهر)، فالبحث النصّي الساذج عن الاسم كان يجده **في شاهد
    قبره** ويعلن أن الحذف لم يحدث."""
    out = []
    for line in html.splitlines():
        st = line.lstrip()
        if st.startswith('//') or st.startswith('/*') or st.startswith('*') or st.startswith('<!--'):
            continue
        out.append(line)
    return '\n'.join(out)


# ================================================================ أ) الكود الميت — سالب

DEAD_JS_SYMBOLS = [
    # النوادي: موديول «قريبًا» بلا واجهة خلفية، وأزراره تكتب في الذاكرة وتطبع نجاحًا
    'function viewClubs(', 'function renderClubs(', 'function drawClub(', 'function clubModal(',
    'const CLUB_PROPOSALS', 'const CLUB_JOINS', 'const CLUBS=',
    # فرع «المعلنون والممولون»: تبويبٌ لا يُوصَل إليه أبدًا (mktTab لا يبلغ 'advertisers')
    'const ADVERTISERS', 'function addAdvertiserModal(',
    # كروت الموديولات في «نظرة عامة» — الشاشة نفسها ابتُلعت في «الوارد»
    'ovcard', "id=\"ovMods\"", 'فتح الموديول',
]


@pytest.mark.parametrize('sym', DEAD_JS_SYMBOLS)
def test_dead_code_is_gone_from_the_dashboard(code, sym):
    assert sym not in code, sym


def test_no_route_leads_to_the_deleted_clubs_screen(code):
    """الحذف الكامل: لا مسار في renderView ولا بند في MODULES ولا صفٌّ في القائمة."""
    assert "current==='clubs'" not in code
    assert 'clubs:{label' not in code
    assert 'clubTab' not in code


def test_the_marketing_advertisers_branch_left_no_stump(code):
    """الفرع الميت يُحذف بجذره: المصفوفة والفرع والدرج والنافذة — لا «نصف حذف» يعيد نفسه."""
    assert "mktTab==='advertisers'" not in code
    assert 'المعلنون والممولون' not in code
    assert 'مموّل/معلن' not in code
    assert 'اختر حملة لرؤية الأداء والإجراء' in code      # نصّ الحالة الفارغة لم يعد يعد بممول


def test_the_single_tab_marketing_bar_left_no_stump(code):
    """أثر الحذف: بعد خروج «المعلنون» بقي شريطُ تبويبٍ **أحادي البند** يُقرأ كعنوان لا
    كأداة تحكّم — زرٌّ لا يبدّل شيئًا. الشريط ومتغيّر حالته حُذفا معًا."""
    assert 'id="mktTabs"' not in code
    assert 'mktTab' not in code
    assert "h3 id=\"mkH\"" in code                    # والعنوان باقٍ في ترويسة اللوحة


def test_the_dead_withdrawal_decision_branch_left_the_investment_drawer(code):
    """قرارٌ ماليٌّ ميّت: `drawInv` احتفظ بفرع يعتمد سحبًا (`EP.decideWithdrawal`) بعد خروج
    «طلبات السحب» إلى «المالية» — `selected` لا يأخذ 'w' في أيّ مسار. بابه الوحيد هناك."""
    inv = code[code.index('function drawInv(){'):code.index('function investorModal(')]
    assert "t==='w'" not in inv, inv[-700:]
    assert 'decideWithdrawal' not in inv
    # وهو حيٌّ في «المالية» — الحذف شال الباب المكرّر لا الفعل
    assert 'decideWithdrawal' in code


def test_go_resets_every_tab_variable_including_the_foundation_one(html):
    """`foundationTab` كان الوحيد الذي لا يصفّره `go()`، فتبويب «حالة الكيان» يبقى لاصقًا
    عبر التنقّل بينما كل أشقّائه يعودون لأوّلهم — حالةٌ تسرّبت بين شاشتين."""
    line = [ln for ln in html.splitlines() if ln.strip().startswith('current=mod;selected=null;')]
    assert len(line) == 1, line
    for var in ("escTab='sessions'", "finTab='summary'", "invTab='owners'",
                "tgTab='goals'", "foundationTab='assets'", "topicsTab='ideas'"):
        assert var in line[0], var


def test_the_two_soon_buttons_left_the_settings_screen(code):
    """زرّان بلا فعل: `2fa` و`backup` كانا يطبعان toast «قريبًا» ولا شيء وراءهما."""
    assert 'data-a="2fa"' not in code
    assert 'data-a="backup"' not in code
    assert "a==='2fa'" not in code
    assert 'قريبًا — غير مفعّلة بعد' not in code
    # وسجلّ العمليات (الزرّ الحقيقي الوحيد في اللوحة) باقٍ ومربوط
    assert 'data-a="log"' in code and 'auditModal()' in code


def test_no_server_route_backed_the_deleted_screens(apppy):
    """السالب على الخادم كذلك: مفيش `/api/clubs` ولا `/api/advertisers` ولا مسار 2FA/باك أب
    ورا الأزرار المحذوفة — فحذف الواجهة ما سابش مسارًا يتيمًا مفتوحًا."""
    routes = set(re.findall(r"@app\.route\('([^']+)'", apppy))
    for dead in ('/api/clubs', '/api/advertisers', '/api/2fa', '/api/backup'):
        assert not any(r.startswith(dead) for r in routes), (dead, sorted(routes))
    for word in ('club_proposal', 'advertiser', 'two_factor'):
        assert word not in apppy, word


# ================================================================ ب) شارات العدّ — بنيويًّا

def test_badges_read_the_platform_queue_not_a_second_count(html):
    """⛔ الشارة والرقم الذي تحتها من **مصدرٍ واحد**: `opsQueueCounters` هي نفسها التي
    ترسم «كل اللي مستنيك»، فلا يمكن للشريط أن يخالف الشاشة."""
    block = html[html.index('function applyNavCounts(){'):html.index('function opsQueuePanel(')]
    assert 'opsQueueCounters(Q)' in block
    assert 'navInboxCount()' in block and 'navInvitesQueue()' in block
    # «متأخّر» في شارة الوارد يقرأ نفس الدالّة التي يقرأها مربّع «متأخّر» فوق الشاشة
    assert 'inboxLateCount()' in block
    assert 'NAV_ALERT_HOURS' in block


def test_badges_are_requested_at_boot_not_on_screen_visit(html):
    """الغرض كلّه: «تعرف فين الشغل من غير ما تفتح شاشة واحدة». ثلاثة مصادر تُطلَب عند
    الإقلاع، وكلٌّ يكتب شاراته لمّا يجهز."""
    boot = html[html.index('function bootNavCounts(){'):]
    boot = boot[:boot.index('\n}')]
    for src in ('opsQueue', 'inbox', 'invites'):
        assert "EP.ensure('%s',applyNavCounts)" % src in boot, src


def test_zero_is_never_drawn_as_a_badge(html):
    """شارةٌ تعني «فيه مستنّي»: صفرٌ مرسوم يجعل كل بندٍ يبدو كأن فيه شغلًا."""
    assert 'const cnt=m.count?' in html                # itemHTML لا يرسم إلا الموجب
    block = html[html.index('function applyNavCounts(){'):html.index('function opsQueuePanel(')]
    assert 'if(nIn>0)' in block
    assert 'if(inv.length)' in block


# ================================================================ ج) المتصفّح — الرسم الحقيقي

@pytest.fixture(scope='module')
def server(tmp_path_factory):
    with _stack(tmp_path_factory.mktemp('co') / 'co.db') as url:
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


def _badges(page):
    """{module: count} لكل بندٍ يحمل شارة فعلًا (مرسومة، لا موجودة في الكائن)."""
    return page.eval_on_selector_all(
        '.rail .item', "els=>{const o={};els.forEach(e=>{const c=e.querySelector('.count');"
                       "if(c)o[e.dataset.mod]=c.textContent.trim();});return o;}")


def _alerts(page):
    return sorted(page.eval_on_selector_all(
        '.rail .item.alert', 'els=>els.map(e=>e.dataset.mod)'))


def test_badges_are_drawn_on_the_rail_with_the_stub_counts(page):
    """الأرقام المتوقّعة من الطقم الثابت (fake_platform + run_dash):
       الوارد ٤٣ (طلب مدرّب ١ + دفعتان يدويّتان + ٤٠ رسالة موقع) · الدعوات ٣ (بانتظار
       الموافقة وحدها من أصل ٤) · الدورات ١١ · **المالية ٣** (سحب محفظةٍ واحد + أمرا دفعٍ
       متعثّران، ولكلٍّ تبويبه) · الضمان ٢."""
    page.wait_for_timeout(1500)
    b = _badges(page)
    for mod in ('inbox', 'invites', 'courses', 'finance', 'escrow'):
        assert mod in b, (mod, b)
    ar = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    n = {k: int(v.translate(ar).replace(',', '').replace('٬', '')) for k, v in b.items()}
    assert n['invites'] == 3, n           # المُرسَلة لا تُعدّ: مش شغلًا عندك
    assert n['escrow'] == 2, n            # الدفعتان اليدويّتان
    assert n['finance'] == 3, n           # سحب محفظةٍ واحد + أمرا دفعٍ متعثّران
    assert n['courses'] == 11, n          # ١ اعتماد + ٧ اهتمام + ٢ تدريب + ١ حيّة
    assert n['inbox'] == 43, n
    assert n.get('settings') is None      # بندٌ بلا طابور: بلا شارة


def test_the_inbox_badge_equals_the_number_the_screen_prints(page, server):
    """⛔ العدّاد لا يخالف نفسه: الشارة على الشريط = `#inboxN` داخل الشاشة، حرفيًّا."""
    _go(page, server, 'inbox')
    on_screen = int(page.inner_text('#inboxN').strip() or '0')
    assert page.evaluate('navInboxCount()') == on_screen
    _shot(page, 'co_01_badges_inbox.png')


def test_the_invites_badge_equals_the_approval_queue_on_screen(page, server):
    _go(page, server, 'invites')
    assert page.evaluate('approvalQueueRows().length') == 3
    assert 'دعوات بانتظار الموافقة' in page.inner_text('#view')
    _shot(page, 'co_02_badges_invites.png')


def test_alert_badges_mark_only_the_queues_the_platform_calls_late(page):
    """أحمر = «أقدم بندٍ فيه تعدّى ٢٤ ساعة» بشهادة المنصّة نفسها، لا بحساب المتصفّح:
       الضمان (٣٠س) · الخبراء (٥١س) · المستخدمون (١٦٠٠س) · الدعوات (٧٢س) · الوارد (فيه
       دفعةٌ يدويّةٌ موسومةٌ متأخّرة). والمالية (٩س) والدورات: بلا إنذار."""
    a = _alerts(page)
    for late in ('escrow', 'team', 'users', 'invites', 'inbox'):
        assert late in a, (late, a)
    for on_time in ('finance', 'courses', 'settings', 'marketing'):
        assert on_time not in a, (on_time, a)


# ================================================================ ج٢) الشارة تهبط حيث الشغل

def test_the_landing_table_carries_a_tab_for_every_queue_with_one(html):
    """⛔ «الشاشة الفاضية بتكدب»: الشارة تعدّ شغلًا ثم تفتح تبويبًا يعرض صفرًا منه. الجدول
    الواحد `OPSQ_LANDINGS` هو مصدر الهبوط للشريحة **وللشارة** معًا — لا جدولان يفترقان."""
    blk = html[html.index('const OPSQ_LANDINGS={'):html.index('function opsQueueCounters(')]
    for key, tab in (('manual_payments_pending', "escTab='manual'"),
                     ('wallet_payouts_pending', "finTab='withdrawals'"),
                     # ⛔ اتجاهان متعاكسان: «متعثّرة» أوامرُ دفعٍ واردة، لا سحوبات خارجة
                     ('stuck_card_payments', "finTab='stuck'"),
                     ('courses_pending', "courseTab='platform'"),
                     ('topics_drafts', "topicsTab='ideas'")):
        assert key in blk and tab in blk, (key, tab)
    # ولا يُحقن في `go()`: مسارٌ عامّ له تبويباته (REDIRECTS)، وحقنُه فيه يدهسها
    go = html[html.index('function go(mod){'):html.index('function renderView(){')]
    assert 'OPSQ_LANDINGS' not in go and 'goOps' not in go


def test_the_manual_payments_badge_lands_on_the_manual_payments_tab(page, server):
    """مقيسٌ حيًّا: «الضمان ٢» (دفعتان يدويّتان) كان يهبط على «الجلسات في الضمان (0)»."""
    _go(page, server, 'inbox')
    page.wait_for_timeout(1200)
    page.click('.rail .item[data-mod="escrow"]')
    page.wait_for_timeout(900)
    assert page.eval_on_selector('#escTabs .tab.on', 'e=>e.dataset.t') == 'manual'
    assert page.eval_on_selector_all('#escRows .row', 'els=>els.length') == 2


def test_the_wallet_payout_badge_lands_on_the_withdrawals_tab(page, server):
    """«المالية ١» (سحب محفظة) كان يهبط على «الملخّص»."""
    _go(page, server, 'inbox')
    page.wait_for_timeout(1200)
    page.click('.rail .item[data-mod="finance"]')
    page.wait_for_timeout(900)
    assert page.eval_on_selector('#finTabs .tab.on', 'e=>e.dataset.t') == 'withdrawals'


def test_the_ops_queue_chip_lands_on_the_same_tab_as_its_badge(page, server):
    """الشريحة والشارة بابان لرقمٍ واحد — فلا يجوز أن يفتحا شاشتين."""
    _go(page, server, 'inbox')
    page.wait_for_timeout(1200)
    page.click('.opsq[data-k="manual_payments_pending"]')
    page.wait_for_timeout(900)
    assert page.eval_on_selector('#escTabs .tab.on', 'e=>e.dataset.t') == 'manual'


def test_a_queue_with_no_screen_gets_no_badge_and_no_click(page, server):
    """«وعود ملف لم تُسلَّم ٦» — شاشة التسويق بلا أي سطحٍ لوعود الملفات (وهي خارج نطاق هذه
    الموجة عمدًا). فالرقم يُعرَض كما ترسله المنصّة، **وبلا** شارةٍ على الشريط وبلا نقرةٍ
    تهبط على لا شيء: «شارةٌ تشير إلى لا شيء أسوأ من غيابها»."""
    _go(page, server, 'inbox')
    page.wait_for_timeout(1200)
    assert 'marketing' not in _badges(page), _badges(page)
    chip = page.eval_on_selector('.opsq-noscreen[data-k="lead_magnet_awaiting_asset"]',
                                 'e=>e.textContent')
    assert '٦' in chip and 'لا شاشة له بعد' in chip, chip
    assert page.eval_on_selector_all('.opsq[data-k="lead_magnet_awaiting_asset"]',
                                     'els=>els.length') == 0


# ================================================================ د) «الاستثمار والشركاء»

def test_investment_and_partners_are_one_screen_with_two_tabs(page, server):
    _go(page, server, 'investment')
    tabs = page.eval_on_selector_all('#invTabs .tab[data-t]',
                                     'els=>els.map(e=>e.dataset.t)')
    assert tabs == ['owners', 'opps'], tabs
    assert page.eval_on_selector('#invGoWd', 'e=>!!e')     # زرٌّ مُعلَن، لا تبويبًا ثالثًا
    assert page.inner_text('#pageTitle').strip() == 'الاستثمار والشركاء'
    _shot(page, 'co_03_investment_owners.png')


def test_the_owners_tab_is_one_table_holding_partners_and_investors(page, server):
    """الكيان واحد (حصّة ملكيةٍ ورأس مال) ⇒ جدولٌ واحد. الشركاء الثلاثة من دفتر الداشبورد
    (اثنان + «غير موزّع» الاحتياطي)، والمستثمرون تحتهم في **نفس** الجدول."""
    _go(page, server, 'investment')
    rows = page.eval_on_selector_all('#ivRows .row', 'els=>els.length')
    partners = page.eval_on_selector_all('#ivRows .row[data-p]', 'els=>els.length')
    assert partners == 3, partners
    assert rows == partners + page.evaluate('ivInvestors().length')
    txt = page.inner_text('#ivRows')
    assert 'عبدالرحمن عطية' in txt and 'غير موزّع' in txt
    assert 'حصة' in txt and 'رأس مال' in txt
    # شريط الحصص (الذي كان يعيش في شاشة «الشركاء») انتقل معها ولم يُفقَد
    assert 'توزيع الحصص' in page.inner_text('#view')


def test_the_owners_tab_count_equals_the_kpi_box_and_the_panel_counter(page, server):
    """⛔ كلمة «الملّاك» مطبوعة ثلاث مرّات على الشاشة الواحدة — المربّع · شارة التبويب ·
    عدّاد اللوحة — وكانت تحمل **رقمين**: المربّع يستثني صفّ الاحتياطي والتبويب يحسبه، على
    بُعد ٢٠٠ بكسل. التعريف الآن واحد يقرأه الثلاثة (الاحتياطي ليس مالكًا)، والحارس يشمل
    المربّع — أبرز رقم على الشاشة — لا الثلاثيّةَ القديمة وحدها."""
    _go(page, server, 'investment')
    ar = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    n = lambda t: int(re.sub(r'[^0-9]', '', t.translate(ar)) or '0')
    tab = page.inner_text('#invTabs .tab[data-t="owners"]')
    in_tab = n(re.search(r'\((\S+)\)', tab).group(1))
    in_panel = n(page.inner_text('#ivN').strip())
    in_kpi = n(page.eval_on_selector_all(
        '#view .kpi', "els=>els.find(e=>/الملّاك/.test(e.textContent))"
                      ".querySelector('b').textContent"))
    assert in_tab == in_panel == in_kpi == 2, (in_tab, in_panel, in_kpi)
    # الاحتياطي **مرسومٌ** رغم خروجه من العدّ — لا بيانات فُقدت، والفارق مُعلَن لا لغز
    assert page.eval_on_selector_all('#ivRows .row', 'els=>els.length') == 3
    assert 'غير موزّع' in page.inner_text('#ivRows')
    assert 'احتياطي' in page.inner_text('#ivHint')


def test_the_merged_investment_screen_prints_one_numeral_system(page, server):
    """رقمان بنظامين في الشريط الواحد والصفّ الواحد («(٣)» بجوار «(0)»، «حصة 60٪» بجوار
    «رأس مال ٥٠٬٠٠٠») — عينُ القارئ تقرؤهما كرقمين من مصدرين. `money()` على كلّ رقمٍ معروض."""
    _go(page, server, 'investment')
    for sel in ('#invTabs', '#ivRows', '#ivN'):
        txt = page.inner_text(sel)
        assert not re.search(r'[0-9]', txt), (sel, txt)
    # ومربّعات الشاشة كذلك (بما فيها «حصص غير موزّعة ١٥٪» و«أكبر حصة ٦٠٪»)
    kpis = page.eval_on_selector_all('#view .kpi b', 'els=>els.map(e=>e.textContent).join(" | ")')
    assert not re.search(r'[0-9]', kpis), kpis


def test_the_largest_share_kpi_survived_the_merge(page, server):
    """«أكبر حصة» (المؤسس الرئيس) كان أحد مربّعات «الشركاء» وسقط في الدمج بلا بديل، بينما
    «عوائد موزّعة» كان يطبع صفرًا دائمًا بلا مستثمرين. المؤشّر عاد، والعوائد انتقلت إلى
    سطر رأس المال (وهي مرسومة صفًّا صفًّا في عمود «عوائد» على أي حال)."""
    _go(page, server, 'investment')
    kpis = page.inner_text('#view')
    assert 'أكبر حصة' in kpis
    box = page.eval_on_selector_all(
        '#view .kpi', "els=>els.find(e=>/أكبر حصة/.test(e.textContent)).textContent")
    assert '٦٠٪' in box and 'عبدالرحمن عطية' in box, box
    assert 'عوائد موزّعة' in page.eval_on_selector_all(
        '#view .kpi', "els=>els.find(e=>/رأس المال/.test(e.textContent)).textContent")


def test_the_old_partners_link_lands_on_the_owners_tab(page, server):
    _go(page, server, 'partners')
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'investment'
    assert page.eval_on_selector('#invTabs .tab.on', 'e=>e.dataset.t') == 'owners'


def test_adding_a_partner_still_opens_the_wired_modal(page, server):
    """الفعل الحقيقي الوحيد في الشاشتين (POST /api/partners) نجا من الدمج."""
    _go(page, server, 'investment')
    page.click('#ivAdd')
    page.wait_for_timeout(400)
    assert page.eval_on_selector('#p_eq', 'e=>!!e'), 'نافذة الشريك لم تُفتح'
    page.keyboard.press('Escape')
    page.evaluate("closeModal()")


# ================================================================ هـ) «الأهداف والتأسيس»

def test_targets_and_foundation_are_one_monthly_review_with_two_tabs(page, server):
    _go(page, server, 'targets')
    tabs = page.eval_on_selector_all('#tgTabs .tab', 'els=>els.map(e=>e.dataset.t)')
    assert tabs == ['goals', 'foundation'], tabs
    assert page.eval_on_selector('#tgTabs .tab.on', 'e=>e.dataset.t') == 'goals'
    assert page.inner_text('#pageTitle').strip() == 'الأهداف والتأسيس'
    _shot(page, 'co_04_targets_goals.png')


def test_the_foundation_tab_renders_and_keeps_the_tabbar_alive(page, server):
    """⛔ فخّ «مكتوبٌ صحيحًا وبلا طريقٍ للشاشة»: الابن كان يكتب على `#view` فيمسح شريط
    الأب. الشريط لازم يعيش **بعد** ما يرسم الابن نفسه (وبعد استيقاظ EP.ensure جوّاه)."""
    _go(page, server, 'targets')
    page.click('#tgTabs .tab[data-t="foundation"]')
    page.wait_for_timeout(1800)
    assert page.eval_on_selector('#tgTabs', 'e=>!!e'), 'الشريط اتمسح بعد رسم التأسيس'
    assert page.eval_on_selector('#tgTabs .tab.on', 'e=>e.dataset.t') == 'foundation'
    assert page.eval_on_selector('#fndHost', 'e=>e.innerHTML.trim().length>200')
    txt = page.inner_text('#fndHost')
    for label in ('رأس المال', 'مصروف شهري ثابت', 'قيمة الأصول'):
        assert label in txt, label
    # ⛔ «المؤسسون» يُشتقّ من الشركاء: بلا طلبهم كان يطبع صفرًا بجوار رأس مالٍ صحيحٍ
    # مصدرُه **نفس** الشركاء — رقمٌ يكذّب جاره على شاشةٍ واحدة.
    assert page.evaluate('tmFounders()') == 2
    assert page.eval_on_selector_all(
        '#fndHost .kpi', "els=>els.some(e=>/المؤسسون/.test(e.textContent)"
                         "&&!/\\b0\\b|٠/.test(e.querySelector('b').textContent))")
    _shot(page, 'co_05_targets_foundation.png')
    page.click('#tgTabs .tab[data-t="goals"]')
    page.wait_for_timeout(600)
    assert page.eval_on_selector('#tgTabs .tab.on', 'e=>e.dataset.t') == 'goals'


def test_the_tabbar_does_not_jump_between_the_two_tabs(page, server):
    """⛔ الزرّ يهرب من تحت المؤشّر: الشريط كان تحت شريط المربّعات في «الأهداف» وفوقه في
    «التأسيس»، فيقفز ١٣٥ بكسل رأسيًّا في كل تبديل والصفحة كلّها تنزاح. موضعه الآن أوّلُ
    عقدةٍ في `#view` في **كلا** الفرعين — والمقياس هو `top` المرسوم لا شكل الكود."""
    _go(page, server, 'targets')
    top_goals = page.eval_on_selector('#tgTabs', 'e=>Math.round(e.getBoundingClientRect().top)')
    page.click('#tgTabs .tab[data-t="foundation"]')
    page.wait_for_timeout(1500)
    top_fnd = page.eval_on_selector('#tgTabs', 'e=>Math.round(e.getBoundingClientRect().top)')
    assert abs(top_goals - top_fnd) <= 4, (top_goals, top_fnd)


def test_the_child_tabbar_reads_as_a_child_not_a_second_parent(page, server):
    """شريطان متطابقا الشكل والحجم على بُعد ٢٠٠ بكسل يُقرآن كمستوىً واحد. الابن مسطّح
    وأصغر بخطٍّ سفليّ — التدرّج البصريّ هو ما يقول أيّهما يحكم الآخر."""
    _go(page, server, 'targets')
    page.click('#tgTabs .tab[data-t="foundation"]')
    page.wait_for_timeout(1500)
    assert page.eval_on_selector('#fTabs', "e=>e.classList.contains('sub')")
    st = page.evaluate(
        "(function(){var g=function(id){var e=document.getElementById(id),"
        "c=getComputedStyle(e);return {fs:parseFloat(getComputedStyle(e.querySelector('.tab')).fontSize),"
        "bg:c.backgroundColor,bw:parseFloat(c.borderTopWidth)};};"
        "return {p:g('tgTabs'),c:g('fTabs')};})()")
    assert st['c']['fs'] < st['p']['fs'], st          # الابن أصغر خطًّا
    assert st['c']['bw'] == 0 and st['p']['bw'] > 0, st   # الأب صندوق، الابن سطر
    assert st['c']['bg'] != st['p']['bg'], st


def test_the_foundation_tab_prints_one_numeral_system_too(page, server):
    """أثرٌ مباشر لتوحيد الأرقام في الشاشة المدموجة: شارات التبويب الابن صارت عربيةً-هنديّة،
    فعدّاد اللوحة تحتها («0») كان يبقى لاتينيًّا — نفس العطل الذي أُصلح فوقه بمائتَي بكسل."""
    _go(page, server, 'targets')
    page.click('#tgTabs .tab[data-t="foundation"]')
    page.wait_for_timeout(1500)
    for sel in ('#fTabs', '#fN'):
        txt = page.inner_text(sel)
        assert not re.search(r'[0-9]', txt), (sel, txt)


def test_the_old_foundation_link_lands_on_the_foundation_tab(page, server):
    _go(page, server, 'foundation')
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == 'targets'
    assert page.eval_on_selector('#tgTabs .tab.on', 'e=>e.dataset.t') == 'foundation'


# ================================================================ و) لا شاشة فقدت بابها

# «الموديول القديم ⇒ المدخل الجديد» — الاثنتان والعشرون كلّها. هذه هي الخريطة التي يطبعها
# سكربت الإثبات، ومصدرها هنا كي لا يفترق المطبوع عن المُختبَر.
REACHABILITY = [
    ('inbox',      'inbox',      None),
    ('invites',    'invites',    None),
    ('courses',    'courses',    None),
    ('team',       'team',       None),
    ('users',      'users',      None),
    ('finance',    'finance',    None),
    ('escrow',     'escrow',     None),
    ('market',     'market',     None),
    ('analysis',   'analysis',   None),
    ('knowledge',  'knowledge',  None),
    ('topics',     'topics',     None),
    ('marketing',  'marketing',  None),
    ('investment', 'investment', None),
    ('targets',    'targets',    None),
    ('ai',         'ai',         None),
    ('settings',   'settings',   None),
    ('overview',   'inbox',      None),
    ('messages',   'inbox',      None),
    ('packages',   'finance',    'packages'),
    ('tutorials',  'topics',     'tutorials'),
    ('partners',   'investment', 'owners'),
    ('foundation', 'targets',    'foundation'),
]


def test_the_reachability_map_covers_the_original_twenty_two():
    assert len(REACHABILITY) == 22
    assert len({old for old, _, _ in REACHABILITY}) == 22


@pytest.mark.parametrize('old,heir,tab', REACHABILITY)
def test_every_original_module_still_opens_from_the_new_sidebar(page, server, old, heir, tab):
    """الوعد الحاكم: مفيش شاشة اتقفلت. كل معرّفٍ قديم يفتح شاشةً مرسومةً فعلًا، والبند
    الوريث هو **المُبرَز** في الشريط (فالمؤسس يعرف هو فين، لا يهبط في مكانٍ بلا اسم)."""
    _go(page, server, old)
    assert page.eval_on_selector('.nav .item.on', 'e=>e.dataset.mod') == heir
    assert page.eval_on_selector('#view', 'e=>e.innerHTML.trim().length>200')
    if tab:
        # المبتلَعة تهبط على **تبويبها**، لا على أوّل تبويبٍ في الوريث: الفرق بين «الرابط
        # شغّال» و«الرابط بيوصّل». كل شريطٍ يسمّي تبويبه بسمته الخاصّة، ونقرأ المُبرَز منها.
        got = page.evaluate(
            "(function(){var e=document.querySelector('#invTabs .tab.on,#tgTabs .tab.on,"
            "#finTabs .tab.on,#topicsTabs .tab.on');"
            "return e?(e.dataset.t||e.dataset.tt||''):null;})()")
        assert got == tab, (old, heir, tab, got)
