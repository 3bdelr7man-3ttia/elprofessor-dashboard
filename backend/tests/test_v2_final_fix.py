# -*- coding: utf-8 -*-
"""الإصلاح النهائي للداشبورد (الجولة النهائية): ما بقي من شاشات قديمة، وتوحيد الأوراق، وسطور الأقسام، والنصوص.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2_final_fix.py

⛔ صفر شبكة: منطق نقي في node + قراءة ملفات. اللي بيثبّته:
  ١. «الخبراء» بالشكل الجديد: التخصص بالعربي (لا إنجليزية خام) · تذاكر ردود دعوة المؤسس (ترتيب · أزرار · نهاية) · بطاقات الخبراء · لا تبويبان مكرّران.
  ٢. «الضمان» لم يعد تبويبًا: آخر تبويب «كل السجلات» · الإيصالات اليدوية في الفلوس · لا نسبة عمولة مخترعة · «صاحب الطلب».
  ٣. «كل السجلات» في الفلوس بشكل جديد: سطر تمهيدي · صنف `v2lg` · نص عربي بلا Cash Flow ولا «حيّ من المالية» ولا «ج».
  ٤. ورقة قرار واحدة في v2-shell.css (لا `.mh` في ملفات الأقسام) وزرّ «رجوع».
  ٥. سطر ترويسة القسم من قائمة القسم نفسه (`V2SEC.head`) وشارة المحتوى تعدّ القرارات فقط.
  ٦. النصوص: «القرار التالي» · لا «تعذّر الجلب» · عملة واحدة · «من الفريق».
"""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = 1792000000000
HOUR = 3600 * 1000


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _strip(js):
    js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    return re.sub(r'(?m)^\s*//.*$', '', js)


HTML = _read('dashboard-cloud', 'index.html')


def _region(start, end):
    return HTML[HTML.index(start):HTML.index(end)]


ESCROW_FINANCE = re.sub(r'(?m)^\s*//.*$', '', _region('function goEscrowManual', 'function viewCourses('))     # بلا سطور التعليق (شرح المطوّر)


# ====================================================================== ١) الخبراء

@needs_node
def test_specialties_come_through_the_arabic_map_and_never_show_raw_english():
    f = lambda v: v2_node.logic('v2s.experts.specialties', v)
    assert f('civil') == ['مدني وعقود'] and f('criminal, family') == ['جنائي', 'أحوال شخصية']
    assert f(['civil', 'مدني وعقود', 'labor']) == ['مدني وعقود', 'عمالي']          # بلا تكرار
    assert f('مدني، جنائي') == ['مدني', 'جنائي']                                   # العربي يمرّ كما هو
    assert f('quantum physics') == ['تخصص آخر']                                    # المجهول بالإنجليزية لا يظهر خامًا
    assert f('') == [] and f(None) == []
    assert v2_node.logic('v2s.experts.specialty', 'Real Estate') == 'عقارات وإيجارات'


def _lead(i, status, hours=None, **kw):
    r = {'id': 'L%s' % i, 'name': 'خبير %s' % i, 'whatsapp': '+20 100 000 00%s' % i, 'email': 'x%s@y.test' % i, 'specialization': 'civil',
         'country': 'مصر', 'years': '12', 'status': status, 'at': (NOW - hours * HOUR) if hours is not None else None}
    r.update(kw)
    return r


@needs_node
def test_founding_lead_tickets_have_one_main_action_and_a_reject_and_end_states_leave():
    rows = [_lead(1, 'contacted', 30), _lead(2, 'new', 5), _lead(3, 'converted', 90), _lead(4, 'rejected', 80), _lead(5, 'new', 50), _lead(6, 'invited', 10)]
    B = v2_node.logic('v2s.experts.leadBoard', rows, NOW)
    assert [t['id'] for t in B['open']] == ['L5', 'L2', 'L1', 'L6'], 'الجديد أولًا (الأقدم فالأحدث) ثم التواصل ثم الدعوة'
    assert B['converted'] == 1 and B['rejected'] == 1 and B['total'] == 6
    t5 = B['open'][0]
    assert t5['primary'] == {'status': 'contacted', 'label': 'تم التواصل'} and t5['secondary'] == {'status': 'rejected', 'label': 'ليس مناسبًا'}
    assert t5['specs'] == ['مدني وعقود'] and t5['statusLabel'] == 'جديد' and 'لم يتم التواصل معه بعد' in t5['brain'] and t5['since'].startswith('منذ')
    nxt = {t['id']: t['primary']['status'] for t in B['open']}
    assert nxt == {'L5': 'contacted', 'L2': 'contacted', 'L1': 'invited', 'L6': 'converted'}
    assert v2_node.logic('v2s.experts.leadBoard', None, NOW) is None, 'المصدر الفاشل null لا قائمة فاضية'
    assert t5['years'] == '١٢', 'الخبرة بأرقام عربية'
    # حالة غير معروفة تُقرأ «جديد» (لا نص خام)، والصف بلا اسم «بلا اسم»
    t = v2_node.logic('v2s.experts.leadTicket', {'id': 'z', 'status': 'weird'}, NOW)
    assert t['status'] == 'new' and t['name'] == 'بلا اسم' and t['since'] == ''


@needs_node
def test_expert_cards_say_why_an_expert_is_hidden_and_never_invent_numbers():
    ex = [{'name': 'د. هالة', 'email': 'H@x.test', 'expertise': ['civil'], 'online': True, 'rating_avg': 4.75, 'rating_count': 12, 'referral_count': 3,
           'courses_count': 2, 'students_count': 50, 'bio': 'نبذة طويلة تكفي لتتجاوز العشرين حرفًا بسهولة', 'public_ready': True},
          {'name': 'م. سامي', 'email': 's@x.test', 'expertise': ['quantum'], 'online': False, 'rating_avg': None, 'rating_count': 0, 'referral_count': 9,
           'courses_count': 0, 'students_count': 0, 'bio': 'قصيرة', 'public_ready': False, 'is_test': True},
          {'name': 'أ. نور', 'email': 'n@x.test', 'expertise': [], 'bio': 'نبذة ' * 10, 'public_ready': None, 'referral_count': 1}]
    B = v2_node.logic('v2s.experts.expertBoard', ex)
    assert [r['name'] for r in B['rows']] == ['م. سامي', 'د. هالة', 'أ. نور'], 'من لا يظهر للناس أولًا ثم الأكثر إحالات'
    sami, hala, nour = B['rows']
    assert sami['hidden'] and 'تجريبيًّا' in ' '.join(sami['reasons']) and sami['brain'].startswith('لا يظهر في دليل الخبراء للناس')
    assert sami['specs'] == ['تخصص آخر'] and sami['rating'] == 'لا تقييم بعد'
    assert hala['email'] == 'h@x.test' and hala['rating'] == '٤٫٨ (١٢)' and hala['brain'] == 'يظهر في دليل الخبراء للناس.'
    assert nour['hidden'] is False and 'غير متاح بعد' in nour['brain'], 'ظهوره في الدليل مجهول ⇒ لا حكم'
    assert B['online'] == 1 and B['hidden'] == 1
    assert v2_node.logic('v2s.experts.expertBoard', None) is None
    line = v2_node.logic('v2s.experts.summaryLine', B, {'open': [1, 2]})
    assert line == '٣ خبراء معتمدون · متصل الآن · خبير لا يظهر للناس · ردّان على دعوة المؤسس ينتظرانك', line
    assert v2_node.logic('v2s.experts.summaryLine', None, None) == 'الخبراء: غير متاح بعد'


def test_the_experts_screen_owns_the_tab_and_the_old_sub_tabs_are_gone():
    js = _read('dashboard-cloud', 'v2s', 'experts.js')
    css = _read('dashboard-cloud', 'v2s', 'experts.css')
    code = _strip(js)
    assert "V2SEC.add({ key: 'experts', take: EX.take })" in js and "mod !== 'team'" in js and "snap.teamTab === 'trainers'" in js
    assert 'EP.setFoundingLeadStatus' in js or 'E.setFoundingLeadStatus' in js
    for banned in ('confirm(', 'prompt(', 'alert(', 'مين ردّ', 'لسه', 'اتواصلنا', 'مش مناسب', 'يقوّم'):
        assert banned not in code, banned
    for needed in ('افتح صفحته', 'رجوع', 'سجّل الحالة', 'أعد المحاولة'):
        assert needed in code, needed
    assert 'var X = L.v2s.experts' in js and 'NA = X.NA' in js
    # الشاشة القديمة ما زالت تحرس المدخل: السطر الأول في viewTeam يسأل السجلّ
    assert "V2SEC.take('team',v)" in HTML.split('function viewTeam(v){')[1][:120]
    block = HTML[HTML.index('<!-- v2 sections begin -->'):HTML.index('<!-- v2 sections end -->')]
    assert 'href="v2s/experts.css"' in block and 'src="v2s/experts.js"' in block and block.index('v2s/courses.js') < block.index('v2s/experts.js') < block.index('v2s/home.js')
    # كل القواعد تحت `.v2ex` (المفتاح مقفول ⇒ لا أثر)
    bare = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for sel in re.findall(r'([^{}]+)\{', bare):
        sel = sel.strip()
        if sel.startswith('@'):
            continue
        for part in sel.split(','):
            assert part.strip().startswith('.v2ex'), part
    assert 'min-height:52px' in css.split('@media(max-width:760px)')[1]          # الأزرار ٥٢ في الموبايل


def test_founding_lead_copy_is_standard_arabic_in_the_dashboard_files():
    api = _read('dashboard-cloud', 'dashboard-api.js')
    fl = HTML[HTML.index('const FL_STATUS='):HTML.index('function flRows()')]
    panel = HTML[HTML.index('function foundingLeadsPanel()'):HTML.index('function wireFoundingLeads(')]
    for bad in ('اتواصلنا', 'اتدعى', 'اتحوّل لمدرّب', 'مش مناسب', 'اتعالج', 'مين ردّ على دعوة المؤسس', 'لسه محتاج', 'اكثر'):
        assert bad not in api and bad not in fl and bad not in panel, bad
    assert 'من ردّ على دعوة المؤسس' in HTML and 'ينتظر ردًّا' in HTML and "t:'تم التواصل'" in HTML and "t:'ليس مناسبًا'" in HTML
    assert 'تم التواصل' in api and 'ليس مناسبًا' in api and 'صار مدرّبًا' in api
    assert 'EP.reload("foundingLeads", function () { if (after) after(true); })' in api and 'after(false)' in api


# ====================================================================== ٢) الضمان

@needs_node
def test_escrow_is_the_last_tab_named_all_records_and_manual_receipts_live_in_money():
    secs = {s['key']: s for s in v2_node.logic('SECTIONS')}
    assert [(t['key'], t['label'], t['mod']) for t in secs['disputes']['tabs']] == [
        ('disputes', 'النزاعات', 'v2disputes'), ('all', 'كل النزاعات', 'inbox'), ('escrow', 'كل السجلات', 'escrow')]
    assert not [t for t in secs['money']['tabs'] if t['key'] == 'manual'] and secs['money']['tabs'][-1]['label'] == 'كل السجلات'
    # الإيصالات اليدوية تروح للفلوس ‹ الإيصالات من كل مدخل
    assert re.search(r"function goEscrowManual\(\)\{if\(window\.V2_ON&&window\.V2SHELL&&V2SHELL\.on\)\{v2OpenSection\('money','receipts'\);return;\}", HTML)
    assert re.search(r"function viewEscrow\(v\)\{\s*//[^\n]*\n\s*if\(escTab==='manual'&&window\.V2_ON&&window\.V2SHELL&&V2SHELL\.on\)\{escTab='sessions';v2OpenSection\('money','receipts'\);return;\}", HTML)


def test_the_old_escrow_screen_has_no_made_up_commission_and_no_gendered_word():
    e = ESCROW_FINANCE[:ESCROW_FINANCE.index('/* ===== FINANCE VIEW')]
    assert 'COMMISSION' not in HTML and '١٥٪' not in e and 'عمولة المنصة' not in e
    assert 'نصيب المنصة' in e and "id=\"escShareLink\"" in e and "v2OpenSection('money','shares')" in e
    assert 'الطالب' not in e and 'للطالب' not in e and 'صاحب الطلب' in e
    # الحقول الناقصة «غير متاح بعد» لا قيمة محسوبة من نسبة ثابتة
    assert "net==null?'غير متاح بعد'" in e and "comm==null?'غير متاح بعد'" in e
    assert 'InstaPay' in e, 'تبويب اليدوي ما زال في الشاشة القديمة خارج الغلاف، ويُخفى تحته بالمنظومة'


# ====================================================================== ٣) المالية القديمة

def test_the_old_finance_screen_is_restyled_and_its_copy_is_clean():
    f = ESCROW_FINANCE[ESCROW_FINANCE.index('/* ===== FINANCE VIEW'):]
    for bad in ('Cash Flow', 'حيّ من المالية', 'اوامر', 'ارباح', 'من الخادم', 'بالألف ج)'):
        assert bad not in f, bad
    assert 'الملخص الشهري: الداخل والخارج' in f and 'أوامر دفع متعثّرة' in f and 'أرباح وخسائر المنصة' in f
    assert re.search(r"<small style=\"font-size:13px\">جنيه</small>", f) and not re.search(r"<small[^>]*>ج</small>", f)
    assert f.count('${v2LegacyNote()}') >= 1 and ESCROW_FINANCE.count('${v2LegacyNote()}') == 2
    assert 'هنا ما بقي من الشاشة السابقة للاطلاع؛ القرارات في التبويبات الجديدة.' in HTML
    assert "ap.classList.toggle('v2lg',current==='finance'||current==='escrow')" in HTML
    css = _read('dashboard-cloud', 'v2-d3.css')
    for sel in ('.app.v2-shell.v2lg #view .kpi{', '.app.v2-shell.v2lg #view .tabbar .tab{', '.app.v2-shell.v2lg #view .row{', '.app.v2-shell.v2lg #view .status{', '.v2lg-note{'):
        assert sel in css, sel
    assert 'min-height:52px' in css[css.index('@media(max-width:599px){.app.v2-shell.v2lg') if '@media(max-width:599px){.app.v2-shell.v2lg' in css else css.rindex('@media(max-width:599px)'):]


def test_the_courses_legacy_revenue_is_never_an_estimate():
    line = [l for l in HTML.split('\n') if 'سجل الإدارة' in l and 'courseTab===' in l][0]
    assert 'c.enrolled*(c.priceNum||0)' not in HTML
    assert "var rev=(c.total_revenue!=null&&(window.EP&&EP.data.courses))?c.total_revenue:null;" in HTML
    assert "rev==null?'غير متاح بعد':money(rev)+' جنيه'" in HTML
    assert 'Math.max(35,100-rt)' in HTML and 'نصيب المنصة' in HTML and 'نصيب صاحب الدورة' in HTML and 'نحن <b' not in HTML
    assert line


# ====================================================================== ٤) ورقة قرار واحدة

SECTION_CSS = ['books', 'brain', 'company', 'content', 'courses', 'market', 'marketing', 'people', 'reports', 'roles', 'home', 'experts']


def test_one_sheet_header_rule_lives_in_the_shell_and_no_section_overrides_it():
    shell = _read('dashboard-cloud', 'v2-shell.css')
    rule = re.search(r"body:has\(> \.app\.v2-shell\) #epModal \.modal \.mh\{([^}]*)\}", shell).group(1)
    for need in ('background:#F6F1EA', 'color:#21262E', 'border-top:4px solid #9E2B4E', "font:800 19px/1.5 'Cairo'"):
        assert need in rule, need
    assert re.search(r"\.mh button\{width:44px;height:44px;[^}]*border:1px solid #E9E1D6", shell)
    assert re.search(r"@media\(max-width:560px\)\{\s*body:has\(> \.app\.v2-shell\) #epModal \.modal \.mh button\{width:52px;height:52px\}", shell)
    for name in SECTION_CSS:
        css = re.sub(r'/\*.*?\*/', '', _read('dashboard-cloud', 'v2s', name + '.css'), flags=re.S)
        for sel in re.findall(r'([^{}]+)\{([^}]*)\}', css):
            if '.mh' in sel[0]:
                assert name == 'people' and sel[1].replace(' ', '') in ('position:sticky;top:0;z-index:3', 'overflow-wrap:anywhere'), (name, sel)    # الثبات والالتفاف فقط، لا ألوان
    for name in ('v2-d2', 'v2-d3', 'v2-home'):
        assert '.mh' not in _read('dashboard-cloud', name + '.css'), name


def test_cancel_buttons_say_back_in_every_section_sheet():
    for name in ('books', 'market', 'courses', 'company', 'roles', 'reports'):
        js = _strip(_read('dashboard-cloud', 'v2s', name + '.js'))
        assert not re.search(r">(إلغاء|تراجع)</button>", js), name
        assert "'إلغاء'" not in js, name
    assert 'id="mkNo">رجوع<' in _read('dashboard-cloud', 'v2s', 'market.js') and "o.cancel || 'رجوع'" in _read('dashboard-cloud', 'v2s', 'books.js')


# ====================================================================== ٥) سطر الترويسة وشارة المحتوى

def test_each_section_head_line_comes_from_its_own_list():
    reg = _read('dashboard-cloud', 'v2s', '_registry.js')
    assert "def('head'" in reg and 'window.V2D2' in reg and 'window.V2D3' in reg
    shell = _read('dashboard-cloud', 'v2-shell.js')
    assert 'var own = headOf(sec.key);' in shell and shell.index('var own = headOf(sec.key);') < shell.index('var t = T[sec.key];')
    assert "headOf((host.state() || {}).section)" in shell                                     # يدخل في بصمة التحديث
    assert 'D2.head = function (key)' in _read('dashboard-cloud', 'v2-d2.js') and 'D3.head = function (key)' in _read('dashboard-cloud', 'v2-d3.js')
    assert 'CO.head = function ()' in _read('dashboard-cloud', 'v2s', 'courses.js') and 'head: CO.head' in _read('dashboard-cloud', 'v2s', 'courses.js')
    assert 'API.head = function ()' in _read('dashboard-cloud', 'v2s', 'content.js')
    # تعذّر المصدر ⇒ «غير متاح بعد» لا عدّ المربّع
    assert "if (g.inboxState === 'error') return L.NA;" in _read('dashboard-cloud', 'v2-d2.js')
    assert "if (st === 'error') return L.NA;" in _read('dashboard-cloud', 'v2-d3.js') and "if (st === 'error' || st === 'closed') return NA;" in _read('dashboard-cloud', 'v2s', 'courses.js')
    # شريحة «متأخر» في الوارد اسمها «تجاوز المهلة» فلا تتصادم مع عمود «متأخر» في لوحة الملفات
    assert "late: 'تجاوز المهلة'" in _read('dashboard-cloud', 'v2-logic.js')


@needs_node
def test_content_badge_counts_decisions_only_and_keeps_the_ideas_as_text():
    ex = {'inbox': [], 'inboxFailed': [], 'pendingVisitors': 0, 'invitesAwaiting': 0, 'market': 0, 'now': NOW}
    q = {'topics_drafts': 311, 'testimonials_pending': 1, 'topics_pending_review': 2, 'opinions_pending': 3, 'creative_pending': 4}
    t = {x['key']: x for x in v2_node.logic('v2Tiles', q, ex)}['content']
    assert t['count'] == 10, 'الشارة = ما ينتظر قرارًا فقط (٢+١+٣+٤) لا ٣١١ مسودة فكرة'
    assert t['next'] == 'موضوعان من أعضاء · رأي متعلّم واحد · ٣ تعليقات · ٤ أعمال إبداعية · ٣١١ فكرة في الأرشيف', t['next']
    only = {x['key']: x for x in v2_node.logic('v2Tiles', {'topics_drafts': 311}, ex)}['content']
    assert only['count'] == 0 and only['next'] == '٣١١ فكرة في الأرشيف'


# ====================================================================== ٦) النصوص

def test_visible_copy_has_no_colloquial_label_no_fetch_words_and_one_currency_map():
    for name in ('v2-home.js', 'v2-d3.js', 'v2-logic.js'):
        code = _strip(_read('dashboard-cloud', name))
        body = code.split('var V2H_COLLOQUIAL')[0] if name == 'v2-logic.js' else code
        assert 'الحاجة الجاية' not in body and 'لسه مقفولة' not in body, name
    assert 'القرار التالي' in _read('dashboard-cloud', 'v2-home.js') and 'الدورات مغلقة حتى الآن' in _read('dashboard-cloud', 'v2-d3.js')
    assert "'الحاجة الجاية', 'لسه مقفولة'" in _read('dashboard-cloud', 'v2-logic.js')
    for name in ('v2-logic.js', 'v2-d3.js', 'v2s/courses.js', 'v2s/content.js', 'v2s/books.js', 'v2s/reports.js', 'v2s/people.js'):
        assert 'تعذّر الجلب' not in _read('dashboard-cloud', name), name
    assert 'غير متصل بالخادم' not in _read('dashboard-cloud', 'v2s', 'content.js') and 'انقطع الاتصال — حدّث الصفحة ثم جرّب' in _read('dashboard-cloud', 'v2s', 'content.js')
    api = _read('dashboard-cloud', 'dashboard-api.js')
    cur = re.search(r'var CUR_AR = (\{[^}]*\})', api).group(1)
    for a, b in (('EGP', 'جنيه'), ('SAR', 'ريال'), ('AED', 'درهم'), ('KWD', 'دينار'), ('USD', 'دولار')):
        assert '%s: "%s"' % (a, b) in cur, cur
    assert 'ر.س' not in cur and '"ج"' not in cur
    assert v2_node.NODE is None or v2_node.logic('util.cur', 'SAR') == 'ريال' and v2_node.logic('util.cur', 'EGP') == 'جنيه'


def test_content_idea_source_is_readable_and_the_company_card_is_plain():
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert "human: 'من الفريق' };" in logic and "IDEA_SRC[src2] || 'فكرة'" in logic and "'بشري'" not in logic
    co = _read('dashboard-cloud', 'v2s', 'company.js')
    assert "card('التحليل المكتوب', '', aiBody)" in co and 'Claude' not in co and 'ChatGPT' not in co
    assert "case 'openHelpers': if (host().openSection) host().openSection('brain', 'helpers'); break;" in co
    assert 'التحليل المكتوب: <b>' in co and 'مفعّل' in co and 'غير مفعّل' in co


def test_old_screens_inside_all_records_show_arabic_digits():
    shell = _read('dashboard-cloud', 'v2-shell.js')
    assert 'SH.legacyDigits = function (on)' in shell and "p.closest('[dir=\"ltr\"],a,input,textarea')" in shell
    assert "if(V2SHELL.legacyDigits)V2SHELL.legacyDigits(current==='finance'||current==='escrow')" in HTML


def test_the_integration_walk_covers_the_screens_that_were_missing():
    shots = _read('backend', 'tests', 'uiharness', 'v2_shots.py')
    for needed in ("('disputes', 'escrow', '45-disputes-escrow')", "('people', 'pipeline', '46-people-pipeline')", "('money', 'all', '47-money-all')",
                   'd3fx.seed_dash(h.app)', 'd3fx.D3Platform(d2=True)', 'def final_walk(page, pre, mobile):', 'def head_matches(page, pre, key, tab):'):
        assert needed in shots, needed


def test_the_book_offer_main_button_is_standard_arabic():
    for name in ('v2-logic.js', 'v2-d3.js'):
        code = _read('dashboard-cloud', name)
        assert 'بالأسعار دي' not in code and 'اعتمد هذه الأسعار' in code, name
