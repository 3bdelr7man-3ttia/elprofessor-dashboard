# -*- coding: utf-8 -*-
"""بنية القائمة المعتمدة (AUDIT/dash/00_dashboard_review.md §٤ · 04_information_architecture.md §٣).

Run:  cd backend && python3 -m pytest -q tests/test_dash_ia_structure.py

لماذا اختبارٌ نصّيّ على `index.html` وليس اختبار متصفّح؟ لأن ما يُثبَّت هنا هو **الترتيب
والانتماء** — أي مجموعة، بأي ترتيب، وأي بند فيها، وأين يعيش سطح «الشركة». دي حقائق ثابتة في
المصدر، وانحرافها صامتٌ تمامًا: إعادةُ ترتيبِ مفاتيحِ `MODULES` بالخطأ لا تكسر أي شيء ولا
تُسقِط أي تست سلوكيّ — تُغيّر الشاشة وبس. الاختبار السلوكي (الشرائح · التحويلات · التبويبات)
في `test_dash_ia_ui.py` بمتصفّحٍ حقيقي.

⛔ الشكوى المقيسة التي وُلد منها هذا الملف: «الاستثمار والشركاء ومرحلة التأسيس اختفوا» —
كانوا داخل مجموعةٍ مطويّةٍ **جوّه صندوق التمرير**، فبنودها تقع تحت حدّ الرؤية. الحارس هنا هو
`_pinned_outside_scrollbox`: سطح «الشركة» لازم يكون **خارج** `.navwrap` بنيويًّا، لا مجرّد
موجود.
"""
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_ROOT, 'dashboard-cloud', 'index.html')
API_JS = os.path.join(_ROOT, 'dashboard-cloud', 'dashboard-api.js')


@pytest.fixture(scope='module')
def html():
    with open(INDEX, encoding='utf-8') as fh:
        return fh.read()


@pytest.fixture(scope='module')
def apijs():
    with open(API_JS, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- ١) ترتيب المجموعات الخمس

EXPECTED_GROUPS = [
    ('شغل النهاردة', 'nav-today'),
    ('الناس والدورات', 'nav-people'),
    ('الفلوس', 'nav-money'),
    ('الطلب', 'nav-demand'),
    ('التسويق والمحتوى', 'nav-content'),
]


def _rail_groups(html):
    """(عنوان، مُعرّف الحاوية) لكل مجموعة مرسومة داخل صندوق التمرير، بترتيب ظهورها."""
    box = html[html.index('<div class="navwrap">'):html.index('<div class="copin"')]
    return re.findall(r'<div class="grp">([^<]+)</div><nav class="nav" id="([^"]+)">', box)


def test_five_visible_groups_in_the_approved_order(html):
    assert _rail_groups(html) == EXPECTED_GROUPS


def test_no_sixth_group_sneaks_into_the_scrollbox(html):
    """صندوق التمرير يحمل خمس مجموعات بالضبط — أي سادسة تعني عودة «الشركة» إلى الطيّ."""
    assert len(_rail_groups(html)) == 5


# ---------------------------------------------------------------- ٢) سطح «الشركة» المثبَّت

def test_pinned_company_container_exists(html):
    assert 'id="coPin"' in html
    assert '<nav class="nav" id="nav-co">' in html


def test_pinned_outside_scrollbox(html):
    """⛔ الحارس الحاكم: `#coPin` **بعد** إغلاق `.navwrap` وقبل `.me` — أي أنه ليس داخل الصندوق
    الذي يُمرَّر، فلا يمكن أن ينزل تحت حدّ الرؤية مهما صغرت الشاشة."""
    i_navwrap = html.index('<div class="navwrap">')
    i_pin = html.index('<div class="copin" id="coPin">')
    i_me = html.index('<div class="me">')
    assert i_navwrap < i_pin < i_me
    # الحاسم: آخر `</nav>` داخل الصندوق يليه `</div>` يغلقه، ثم يبدأ الـpin شقيقًا له.
    assert re.search(r'</nav>\s*</div>\s*(<!--.*?-->\s*)?<div class="copin" id="coPin">',
                     html, re.S)
    assert html[i_navwrap:i_pin].count('<div class="navwrap">') == 1


def test_pinned_carries_exactly_the_four_company_items(html):
    m = re.search(r"const CO_PINNED=\[([^\]]+)\]", html)
    assert m, 'CO_PINNED غير معرَّف — ترتيب سطح الشركة لازم يكون صريحًا لا مشتقًّا'
    items = re.findall(r"'([a-z_]+)'", m.group(1))
    assert items == ['investment', 'targets', 'ai', 'settings']


def test_the_old_collapsible_company_group_is_gone(html):
    """الطيّ نفسه هو العطل — لا زرّ توسيع ولا حالة محفوظة في localStorage."""
    assert 'grpCoCaret' not in html
    assert 'ep_grp_co' not in html


# ---------------------------------------------------------------- ٣) انتماء البنود

def _modules(html):
    """{id: grp أو None} من كائن MODULES نفسه (مصدر الحقيقة الذي يرسم منه renderNav)."""
    body = html[html.index('const MODULES={'):html.index('const CO_PINNED=')]
    out = {}
    for mid, rest in re.findall(r"^\s{2}([a-z_]+):\{(.*)\},?$", body, re.M):
        g = re.search(r"grp:'([a-z]+)'", rest)
        out[mid] = g.group(1) if g else None
    return out


EXPECTED_MEMBERSHIP = {
    'inbox': 'today', 'invites': 'today',
    'courses': 'people', 'team': 'people', 'users': 'people',
    'finance': 'money', 'escrow': 'money',
    'market': 'demand', 'analysis': 'demand', 'knowledge': 'demand',
    'topics': 'content', 'marketing': 'content',
    'investment': 'co', 'targets': 'co', 'ai': 'co', 'settings': 'co',
    # مبتلعة: بلا صفٍّ في القائمة (تُفتح من داخل وريثها)
    'overview': None, 'messages': None, 'packages': None,
    'partners': None, 'foundation': None, 'tutorials': None,
}


def test_every_module_sits_in_its_approved_group(html):
    assert _modules(html) == EXPECTED_MEMBERSHIP


def test_twelve_items_visible_plus_four_pinned(html):
    mods = _modules(html)
    visible = [m for m, g in mods.items() if g and g != 'co']
    pinned = [m for m, g in mods.items() if g == 'co']
    assert len(visible) == 12, visible
    assert len(pinned) == 4, pinned


def test_item_order_inside_each_group_follows_the_declaration(html):
    """renderNav يرسم بترتيب مفاتيح MODULES — فترتيب الإعلان هو ترتيب الشاشة."""
    mods = list(_modules(html).items())
    order = [m for m, g in mods if g == 'today']
    assert order == ['inbox', 'invites']
    assert [m for m, g in mods if g == 'money'] == ['finance', 'escrow']
    assert [m for m, g in mods if g == 'content'] == ['topics', 'marketing']


# ---------------------------------------------------------------- ٤) موديولات الأدوار: لا تُمسّ

def test_role_modules_untouched(html):
    role_block = html[html.index('const ROLE_MODULES={'):html.index('function moduleDef(')]
    for mid in ('t_home', 't_courses', 't_earnings', 'i_home', 'i_market', 'i_invest', 'v_pending'):
        assert mid + ':{' in role_block
    assert "employee:['users','courses','topics','tutorials']" in html


# ---------------------------------------------------------------- ٥) كل شاشة لها بابٌ ما زال يُفتح

# الاثنتان والعشرون كما كانت قبل إعادة البناء. المرحلة ٢ (دمج سطح «الشركة») ابتلعت
# `viewPartners` داخل «الاستثمار والشركاء»: جدول الحصص صار تبويب «الملّاك ورأس المال»
# هناك، فالدالّة لم تعد موجودة — لكن **الشاشة** موجودة، ولها مدخلٌ يُفتح. لذلك القائمة
# انقسمت: دوالٌّ يجب أن تبقى، وشاشةٌ واحدة ابتُلعت ويجب أن يظلّ لها بابٌ (الاختبار تحته).
RENDERERS = [
    'viewInbox', 'viewInvites', 'viewCourses', 'viewTeam', 'viewUsers', 'viewFinance',
    'viewEscrow', 'viewMarket', 'viewAnalysis', 'viewKnowledge', 'viewTopics', 'viewMarketing',
    'viewInvestment', 'viewTargets', 'viewAI', 'viewSettings', 'viewPackages',
    'viewFoundation', 'viewTutorials', 'viewMessages', 'viewOverview',
]
ABSORBED_RENDERERS = ['viewPartners']


@pytest.mark.parametrize('fn', RENDERERS)
def test_all_twenty_two_renderers_still_exist(html, fn):
    assert re.search(r'function %s\(' % fn, html), fn


def test_the_twenty_two_are_all_accounted_for(html):
    """٢١ دالّةً باقية + ١ مبتلَعة = ٢٢. العدد نفسه هو الحارس: حذفُ شاشةٍ بلا وريثٍ
    مُعلَن يكسر هذا السطر، لا يمرّ صامتًا."""
    assert len(RENDERERS) + len(ABSORBED_RENDERERS) == 22


@pytest.mark.parametrize('fn', ABSORBED_RENDERERS)
def test_absorbed_renderers_are_really_gone_not_orphaned(html, fn):
    """المبتلَعة تُحذف فعلًا — لا تبقى دالّةً ميتةً بلا نداء (هذا هو نصف الشكوى الأصلي)."""
    assert not re.search(r'function %s\(' % fn, html), fn


def test_swallowed_screens_have_a_declared_heir(html):
    """المبتلَعة لا تُترك بلا باب: REDIRECTS تقول لكل واحدة وريثها وحالته."""
    block = html[html.index('const REDIRECTS={'):html.index('const ROLE_MODULES={')]
    assert "overview:['inbox'" in block
    assert "messages:['inbox'" in block
    assert "packages:['finance'" in block
    assert "activeFilter='t:messages'" in block
    assert "finTab='packages'" in block


def test_orphan_screens_are_reachable_from_inside_their_parent(html):
    """الشركاء · مرحلة التأسيس · دليل الاستخدام — خرجت من القائمة ولها أبواب من داخل أبويها.

    ⭐ المرحلة ٢ رقّت البابين من «زرٍّ يفتح شاشةً أخرى» إلى **تبويبٍ داخل الشاشة المدموجة**:
    الشركاء ⇒ تبويب «الملّاك ورأس المال» في «الاستثمار والشركاء»، ومرحلة التأسيس ⇒ تبويب
    «التأسيس والأصول» في «الأهداف والتأسيس». الوعد الذي يحرسه الاختبار لم يتغيّر (لا شاشة
    بلا باب) — تغيّر شكل الباب.
    """
    assert 'data-t="owners">الملّاك ورأس المال' in html
    assert 'data-t="foundation">التأسيس والأصول' in html
    assert "['tutorials','دليل الاستخدام']" in html   # الدليل ← تبويب في «المحتوى»
    assert "tutorials:['topics'" in html         # والرابط القديم #tutorials يهبط عليه


def test_the_merged_company_screens_have_at_most_two_tabs(html):
    """قرار §٤ حرفيًّا: «جدول واحد، تبويبان على الأكثر». التبويب الثالث في «الاستثمار
    والشركاء» ليس تبويبًا بل زرٌّ مُعلَنٌ يفتح «المالية» (طلبات السحب لها بابٌ واحد هناك)،
    ولذلك هو بلا `data-t` — والعدّ هنا يعدّ التبويبات الحقيقية وحدها."""
    inv = html[html.index('<div class="tabbar" id="invTabs">'):]
    inv = inv[:inv.index('</div>\n    </div>') if '</div>\n    </div>' in inv[:2000] else 2000]
    assert inv.count('data-t="') == 2, inv[:600]
    assert 'id="invGoWd"' in inv                      # الزرّ المُعلَن، لا تبويبًا رابعًا
    tg = html[html.index("var _tb='<div class=\"tabbar\" id=\"tgTabs\">"):]
    tg = tg[:tg.index('</div>\';')]
    assert tg.count('data-t=') == 2, tg[:600]


def test_swallowed_company_screens_land_on_the_right_tab(html):
    """رابطٌ قديم إلى #partners / #foundation يهبط على وريثه **بتبويبه**، لا على أوّل تبويب."""
    block = html[html.index('const REDIRECTS={'):html.index('const ROLE_MODULES={')]
    assert "partners:['investment',function(){invTab='owners';}]" in block
    assert "foundation:['targets',function(){tgTab='foundation';}]" in block


# ---------------------------------------------------------------- ٦) السقف الصامت

def test_the_silent_twenty_five_row_cap_is_gone(apijs):
    """⛔ لا `slice(0,25)` في أي مصدر وارد: كان يقصّ الرسائل بصمت والشاشة تقول «لا وارد جديد»."""
    code = '\n'.join(l for l in apijs.splitlines() if not l.lstrip().startswith('//'))
    assert 'slice(0, 25)' not in code
    assert 'slice(0,25)' not in code


def test_any_truncation_is_declared_by_source_and_count(apijs, html):
    assert 'INBOX_SOURCE_CAP' in apijs
    assert 'window.INBOX_TRUNCATED' in apijs
    assert 'معروض " + INBOX_SOURCE_CAP + " من "' in apijs
    assert 'inboxTruncStrip' in html     # والشاشة ترسمه فوق العدّاد


# ---------------------------------------------------------------- ٧) الدمج مرسومٌ فعلًا

def test_inbox_carries_the_merged_overview_strip_and_the_platform_queue(html):
    body = html[html.index('function viewInbox(v){'):html.index('function renderInbox(){')]
    assert '${ovKpiStrip()}' in body
    assert '${opsQueuePanel()}' in body
    assert "EP.ensure('opsQueue'" in body


def test_overview_card_grid_is_removed(html):
    """شبكة كروت «الموديولات» — سطح تنقّل ثالث يكرّر الشريط الجانبي — لم تعد تُرسم."""
    assert 'ovMods' not in html
    assert 'ovcard' not in html


def test_finance_absorbed_packages_and_payouts_and_the_platform_pnl(html):
    body = html[html.index('function viewFinance(v){'):html.index('function renderFin(){')]
    assert 'الباقات — تسعير غير مُرسى' in body
    assert 'data-t="withdrawals"' in body
    assert 'data-t="pnl"' in body
    assert "EP.ensure('pnl'" in body


def test_payouts_are_rendered_in_exactly_one_place(html):
    """السحوبات كانت مرسومة مرّتين على نفس المصدر (المالية + الاستثمار) — بابٌ واحد الآن."""
    inv = html[html.index('function viewInvestment(v){'):html.index('function drawInv(){')]
    assert 'data-t="wd"' not in inv
    assert 'id="invGoWd"' in inv          # زرّ يفتح الباب الوحيد في «المالية»


def test_escrow_declares_itself_suspended_and_owns_the_manual_payments_tab(html):
    body = html[html.index('function viewEscrow(v){'):html.index('function renderEsc(){')]
    assert 'موقوف حتى أوّل جلسة مدفوعة' in body
    assert 'data-t="manual"' in body
    assert 'escManualRows' in html
    assert 'goEscrowManual' in html


# ---------------------------------------------------------------- ٨) جولة المراجعة (٢٠٢٦-٠٩-٠٩)

def test_late_has_exactly_one_definition(html):
    """⛔ تعريفان لكلمةٍ واحدة يطبعان رقمين متناقضين على شاشةٍ واحدة — وهو ما حدث فعلًا."""
    assert "function inboxIsLate(i){return i.triage==='late'||!!i.slaWarn;}" in html
    code = '\n'.join(l for l in html.splitlines() if not l.lstrip().startswith('//'))
    assert code.count("triage==='late'||i.slaWarn") == 0
    assert code.count("i.triage==='late'||!!i.slaWarn") == 1   # داخل الدالّة وحدها


def test_the_overview_strip_no_longer_prints_any_inbox_number(html):
    body = html[html.index('function ovKpiStrip(){'):html.index('function opsQueueCounters(')]
    assert 'وارد يحتاج تصرّفك' not in body
    assert 'INBOX.filter' not in body
    for keep in ('مستخدمو المنصة', 'صافي الربح', 'محجوز في الضمان'):
        assert keep in body


def test_the_tutorials_tab_bar_owns_its_own_node(html):
    """نمط «الباقات»: الأب يكتب الشريط + عقدة الابن، والابن يعيد رسم عقدته وحدها."""
    branch = html[html.index("if(topicsTab==='tutorials')"):]
    branch = branch[:branch.index('\n')]
    assert "v.innerHTML=topicsTabbar('tutorials')+'<div id=\"tutHost\"></div>'" in branch
    assert "viewTutorials(document.getElementById('tutHost'))" in branch
    assert 'insertAdjacentHTML' not in branch
    # وكل إعادة رسمٍ للدليل تمرّ من tutHost() لا من #view مباشرةً
    assert 'function tutHost(){' in html
    assert "viewTutorials(document.getElementById('view'))" not in html


def test_no_screen_route_survives_for_a_swallowed_tab(html):
    """⛔ **المسار الميت هو نفس الهروب مكتوبًا مرّةً أخرى**: `renderView` ظلّ يحمل
    `if(current==='packages')return viewPackages(v)` بـ`v`=`#view` بعد أن صارت الباقات
    تبويبًا. لا يصله أحدٌ اليوم (REDIRECTS تحوّل 'packages' إلى 'finance')، لكنه ينتظر أوّل
    نداءٍ يضبط `current` مباشرةً ليعيد بناء الشاشة الهجينة. البابُ الوحيد هو المدخل في
    REDIRECTS — والسطر حُذف لا عُلِّق."""
    body = html[html.index('function renderView(){'):html.index('function viewSoon(')]
    assert "current==='packages'" not in body, body[:400]
    assert 'return viewPackages(v)' not in html
    assert "viewPackages(document.getElementById('view'))" not in html
    # والوريث الوحيد المُعلَن باقٍ
    assert "packages:['finance',function(){finTab='packages';}]" in html


def test_the_investment_third_tab_state_is_truly_gone(html):
    """كودٌ ميت يوحي بتبويبٍ ثالثٍ ما زال قائمًا — حُذف لا عُطّل."""
    assert "invTab==='wd'" not in html
    assert 'طلبات السحب تُدار في «المالية» ← تبويب «السحوبات».' not in html   # الفرع الميت
    inv = html[html.index('function renderInv(){'):html.index('function drawInv(){')]
    assert inv.count('} else {') == 1 and 'else if' not in inv       # فرعان اثنان لا ثلاثة


def test_reply_by_email_is_a_real_action_in_both_copies(html):
    """⛔ زرٌّ بلا فعل: كان toast في نسختين. الآن mailto حقيقي من دالّةٍ واحدة."""
    assert "function mailReply(email,who){" in html
    assert "'mailto:'+encodeURIComponent(em)" in html
    assert "mailReply(i.email,i.who)" in html      # درج الوارد
    assert "mailReply(m.email,m.name)" in html     # شاشة الرسائل
    assert 'فتح الرد بالبريد' not in html


def test_the_manual_tab_gets_its_own_counters(html):
    body = html[html.index('function viewEscrow(v){'):html.index('function renderEsc(){')]
    assert "escTab==='manual'" in body and 'id="manKpis"' in body
    assert 'بلا إيصال مرفوع' in body and 'إجمالي المبلغ' in body


def test_the_pnl_tab_drawer_tells_the_truth(html):
    body = html[html.index('function drawFinInfo(){'):html.index('function svgLine(')]
    assert "finTab==='pnl'" in body
    assert 'للقراءة فقط' in body and 'لا إجراء هنا' in body


def test_rail_badges_are_written_from_the_platform_queue(html):
    assert 'function applyNavCounts(){' in html
    assert 'applyNavCounts();' in html
    assert 'oldest_hours' in html          # «تنبيه» يُقرأ من الطابور لا من تخمين


def test_the_rail_hints_that_it_scrolls(html):
    """صفٌّ مقصوصٌ عند حدّ التمرير كان يُقرأ عطلًا — تدرّجٌ فوق السطح المثبَّت يقول «فيه تحت»."""
    assert '.rail .copin::before{' in html
    assert 'pointer-events:none' in html
