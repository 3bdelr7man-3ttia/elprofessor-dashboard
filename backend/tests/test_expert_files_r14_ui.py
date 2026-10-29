# -*- coding: utf-8 -*-
"""«ملف للخبير» الجولة ١٤ في المتصفح — مفتاح التوزيع التلقائي · نوع الملف والتخصص · «مين اتبعتله الملف» · الاعتذارات بسببها ·
المرشّحين بتخصصاتهم · «مالهاش خبير متاح» · وثيقة العقد في درج المراجعة (SPEC-R14 §٤).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_r14_ui.py

نفس الأداة (`uiharness/ef_route_harness.py`): الواجهة من الديسك على أصل وهمي، `/api/*` جوه العملية، والمنصة جدول في الذاكرة
(`EFPlatform(r8=True, r14=True)`). ⛔ ولا نافذة متصفح (`alert`/`confirm`/`prompt`) في أي اختبار — لو ظهرت نافذة الاختبار يقع.
"""
import os
import sys

import pytest

playwright = pytest.importorskip('playwright.sync_api', reason='playwright غير متاح — اختبار الواجهة يُتخطّى')
from playwright.sync_api import sync_playwright  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import ef_fixtures as fx                      # noqa: E402
from ef_route_harness import Harness, DASH   # noqa: E402

READY = ("() => window.EP && EP.state && EP.state.inbox==='ready' && EP.state.opsQueue==='ready'"
         " && document.getElementById('rows')")
K1, K2, K3, KR = fx.K1['id'], fx.K2['id'], fx.K3['id'], fx.KR['id']
F1, F2 = fx.F1['id'], fx.F2['id']
SETTINGS_PATH = '/api/bridge/expert-files/settings'


def _platform(**kw):
    return fx.EFPlatform(r8=True, r14=True, **kw)


@pytest.fixture(scope='module')
def harness():
    h = Harness(_platform())
    yield h
    h.uninstall()


@pytest.fixture(scope='module')
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture
def open_page(pw, harness):
    browsers = []

    def _open(role='admin', ef=None, hash_='#inbox', mobile=False, wait_ready=True):
        harness.ef = ef or _platform()
        try:
            br = pw.chromium.launch(args=['--single-process'])
        except Exception as exc:
            pytest.skip('chromium غير متاح لـplaywright: %s' % exc)
        browsers.append(br)
        ctx = harness.context(br, role, {'width': 390, 'height': 844} if mobile else {'width': 1440, 'height': 900}, mobile)
        page = ctx.new_page()
        page.dialogs = []
        page.on('dialog', lambda d: (page.dialogs.append(d.message), d.dismiss()))      # ⛔ أي نافذة = فشل (بنتأكد تحت)
        harness.platform_calls.clear()
        page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
        if wait_ready:
            page.wait_for_function(READY, timeout=30000)
        return page

    yield _open
    for br in browsers:
        try:
            br.close()
        except Exception:
            pass


def _row(page, rid, lane=None):
    idx = page.evaluate("([id, lane]) => INBOX.findIndex(r => r.apiId === id && (!lane || r.efLane === lane))", [rid, lane])
    assert idx >= 0, rid
    fyi = page.evaluate("i => INBOX[i].fyi", idx)
    in_fyi = page.evaluate("() => activeFilter === 'fyi'")
    if fyi != in_fyi:                                                  # اتبعت لخبير وفي مهلته ⇒ «للعلم» (برّه الشريحة الافتراضية)
        page.click('#rows .ef-fyi-line [data-a="ef_fyi"]')
    page.click('#rows .row[data-i="%d"]' % idx)


def _ar(page, n):
    return page.evaluate("n => Number(n).toLocaleString('ar-EG')", n)


def _drawer(page):
    return page.inner_text('#drawer')


def _puts(harness):
    return [c for c in harness.platform_calls if c[0] == 'PUT' and c[1] == SETTINGS_PATH]


def _line(page):
    return page.inner_text('#rows .ef-auto-line')


# ---------------------------------------------------------------- ١) مفتاح التوزيع التلقائي

def test_the_switch_shows_on_above_the_list_and_says_what_it_does(open_page):
    page = open_page()
    line = _line(page)
    assert 'التوزيع التلقائي شغّال' in line
    assert 'بيتبعت لوحده لأنسب خبير متاح' in line and 'تقدر تغيّر الخبير بإيدك' in line
    assert page.query_selector('#rows .ef-auto-line [data-auto="off"]') is not None
    assert page.query_selector('#rows .ef-auto-line [data-auto="on"]') is None
    assert page.dialogs == []


def test_closing_it_asks_inside_the_page_and_sends_nothing_until_yes(open_page, harness):
    page = open_page()
    page.click('#rows [data-auto="off"]')
    conf = page.inner_text('#rows .ef-auto-line .ef-conf')
    assert 'هيستنى توزيعك بإيدك' in conf and 'تقفله؟' in conf
    assert page.get_attribute('#rows .ef-auto-line .ef-conf', 'role') == 'group'
    assert _puts(harness) == [] and harness.ef.auto_assign is True
    assert page.evaluate("() => document.activeElement && document.activeElement.dataset.auto") == 'x'   # التركيز على «رجوع»
    page.click('#rows [data-auto="x"]')                                       # رجوع ⇒ ولا نداء
    assert page.query_selector('#rows .ef-auto-line .ef-conf') is None
    assert 'التوزيع التلقائي شغّال' in _line(page)
    assert _puts(harness) == [] and harness.ef.auto_assign is True
    assert page.dialogs == []


def test_yes_closes_it_with_the_confirmation_flag_and_the_line_turns_off(open_page, harness):
    page = open_page()
    page.click('#rows [data-auto="off"]')
    page.click('#rows [data-auto="go"]')
    page.wait_for_function("() => document.querySelector('#rows .ef-auto-line.off')")
    puts = _puts(harness)
    assert len(puts) == 1                                                       # نداء واحد
    # الخادم رفض القفل من غير `confirmed: true` (اختبار البروكسي) — فوصول النداء للمنصة = المتصفح بعته مؤكَّد.
    assert puts[0][3]['auto_assign'] is False and puts[0][3].get('by')           # `by` من التوكن (الخادم بيحطه)
    assert sorted(puts[0][3]) == ['auto_assign', 'by']                           # ⛔ `confirmed` مابيعدّيش للمنصة
    assert harness.ef.auto_assign is False
    line = _line(page)
    assert 'التوزيع التلقائي مقفول' in line and 'بتستنى توزيعك بإيدك' in line
    assert page.query_selector('#rows .ef-auto-line [data-auto="on"]') is not None
    assert page.dialogs == []


def test_turning_it_back_on_needs_no_confirmation(open_page, harness):
    ef = _platform()
    ef.auto_assign = False
    page = open_page(ef=ef)
    assert 'التوزيع التلقائي مقفول' in _line(page)
    page.click('#rows [data-auto="on"]')
    page.wait_for_function("() => !document.querySelector('#rows .ef-auto-line.off') && document.querySelector('#rows .ef-auto-line')")
    assert harness.ef.auto_assign is True and len(_puts(harness)) == 1
    assert 'التوزيع التلقائي شغّال' in _line(page)
    assert page.query_selector('#rows .ef-auto-line .ef-conf') is None


def test_a_refusal_shows_inside_the_confirmation_and_keeps_it_open(open_page, harness):
    ef = _platform()
    ef.settings_fail = (409, {'detail': 'الإعداد اتغيّر — حدّث الصفحة'})
    page = open_page(ef=ef)
    page.click('#rows [data-auto="off"]')
    page.click('#rows [data-auto="go"]')
    page.wait_for_function("() => document.querySelector('#rows .ef-conf-err') && document.querySelector('#rows .ef-conf-err').textContent.trim()")
    assert 'الإعداد اتغيّر' in page.inner_text('#rows .ef-conf-err')
    assert page.query_selector('#rows [data-auto="go"]') is not None          # لسه مفتوح — تقدر ترجع أو تجرّب تاني
    assert ef.auto_assign is True
    assert page.dialogs == []


def test_no_switch_on_a_platform_before_round_14(open_page, harness):
    page = open_page(ef=fx.EFPlatform(r8=True))
    assert page.query_selector('#rows .ef-auto-line') is None
    assert [c for c in harness.platform_calls if c[1] == SETTINGS_PATH] != []   # اتسأل، والمنصة ردت ٤٠٤ بهدوء
    assert page.inner_text('#rows').strip() != ''


def test_an_employee_neither_asks_for_nor_sees_the_switch(open_page, harness):
    page = open_page(role='employee', hash_='#courses', wait_ready=False)
    page.wait_for_function("() => window.EP && EP.authed", timeout=30000)
    page.evaluate("() => EP.reload('inbox')")
    page.wait_for_function("() => EP.state.inbox==='ready'", timeout=30000)
    assert [c for c in harness.platform_calls if c[1] == SETTINGS_PATH] == []
    assert page.evaluate("() => EP.data.efSettings === undefined || EP.data.efSettings === null")
    assert page.evaluate("() => (window.INBOX_FAILED||[]).length") == 0


def test_the_switch_shows_on_the_files_filters_and_hides_elsewhere(open_page):
    page = open_page()
    page.click('#filters .chip[data-f="t:files"]')
    assert page.query_selector('#rows .ef-auto-line') is not None
    page.click('#filters .chip[data-f="t:disputes"]')
    assert page.query_selector('#rows .ef-auto-line') is None


def test_the_for_your_info_line_says_what_auto_assign_does_to_a_file_nobody_takes(open_page):
    page = open_page()
    line = page.inner_text('#rows .ef-fyi-line:not(.ef-off-line):not(.ef-trial-line)')
    assert 'هيتبعت لخبير تاني لوحده' in line and 'هيرجع هنا' not in line
    page.click('#rows [data-auto="off"]')
    page.click('#rows [data-auto="go"]')
    page.wait_for_function("() => document.querySelector('#rows .ef-auto-line.off')")
    line = page.inner_text('#rows .ef-fyi-line:not(.ef-off-line):not(.ef-trial-line)')
    assert 'هيرجع هنا' in line


# ---------------------------------------------------------------- ٢) الصفوف والفلاتر

def test_contract_and_specialty_badges_are_on_the_row_and_old_files_have_none(open_page):
    page = open_page()
    got = dict((k, v) for k, v in page.evaluate(
        "() => INBOX.filter(r => r.apiKind === 'expert_file').map(r => [r.apiId, (r.badges || []).map(b => b.t)])"))
    assert 'عقد · %s صفحات' % _ar(page, 8) in got[K1] and 'عقارات وإيجارات' in got[K1]
    assert 'أخرى: قانون بحري' in got[K3]
    assert 'عمالي' in got[K2]
    assert all('عقد' not in t and 'عمالي' not in t for t in got[F1])                    # ملف قديم: زي ما كان
    assert 'عقد · %s صفحات' % _ar(page, 6) in got[KR]


def test_the_no_candidate_file_is_a_real_item_with_its_own_filter(open_page):
    page = open_page()
    chips = page.inner_text('#filters')
    assert 'مالهاش خبير متاح (%s)' % _ar(page, 1) in chips
    page.click('#filters .chip[data-f="nocand"]')
    rows = page.inner_text('#rows')
    assert fx.K3['title'] in rows and 'ملف مالوش خبير متاح' in rows
    assert fx.K1['title'] not in rows and fx.F1['title'] not in rows
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).fyi", K3) is False
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).slaWarn", K3) is True


def test_no_such_chip_when_nothing_is_stuck(open_page):
    ef = _platform()
    for f in ef.waiting:
        f['no_candidate_alerted_at'] = None if 'no_candidate_alerted_at' in f else None
    page = open_page(ef=ef)
    assert 'مالهاش خبير متاح' not in page.inner_text('#filters')


def test_the_contracts_filter_counts_files_and_reviews(open_page):
    page = open_page()
    assert 'عقود (%s)' % _ar(page, 2) in page.inner_text('#filters')           # K1 + KR
    page.click('#filters .chip[data-f="contract"]')
    rows = page.inner_text('#rows')
    assert fx.K1['title'] in rows and fx.KR['title'] in rows and fx.F1['title'] not in rows


def test_an_assigned_file_with_the_no_candidate_stamp_is_stuck_too(open_page):
    # الكنسة لو ملقتش خبير تاني بعد ١٢ ساعة بتسيب الملف `assigned` عند اللي اتبعتله وتنبّه المؤسس مرة ⇒ بند حقيقي.
    ef = _platform()
    k2 = next(f for f in ef.waiting if f['id'] == K2)
    k2['no_candidate_alerted_at'] = fx.iso(-3.0)
    page = open_page(ef=ef)
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).noCandidate", K2) is True
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).fyi", K2) is False
    assert 'مالهاش خبير متاح (%s)' % _ar(page, 2) in page.inner_text('#filters')
    page.click('#filters .chip[data-f="nocand"]')
    assert fx.K2['title'] in page.inner_text('#rows')
    _row(page, K2)
    d = _drawer(page)
    assert 'لسه ما استلمش' in d and 'ابعته بإيدك' in d and 'اعتذروا ومفيش غيرهم' not in d


def test_a_stamp_on_a_file_that_is_no_longer_before_claim_means_nothing(open_page):
    ef = _platform()
    k2 = next(f for f in ef.waiting if f['id'] == K2)
    k2['no_candidate_alerted_at'] = fx.iso(-3.0)
    k2['status'] = 'claimed'
    page = open_page(ef=ef)
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).noCandidate", K2) is False


# ---------------------------------------------------------------- ٣) الدرج: النوع والتخصص وسجل التوزيع والاعتذارات

def test_drawer_shows_kind_and_specialty_chips(open_page):
    page = open_page()
    _row(page, K1)
    chips = page.inner_text('#drawer .ef-chips')
    assert 'عقد · %s صفحات' % _ar(page, 8) in chips and 'عقارات وإيجارات' in chips
    assert page.inner_text('#drawer .ef-chip.k').startswith('عقد')


def test_an_old_file_drawer_is_exactly_as_before(open_page):
    page = open_page()
    _row(page, F2)
    assert page.query_selector('#drawer .ef-chips') is None
    assert page.query_selector('#drawer .ef-log') is None
    assert 'مين اتبعتله الملف' not in _drawer(page)


def test_the_assign_timeline_says_who_when_and_why(open_page):
    page = open_page()
    _row(page, K2)
    assert 'مين اتبعتله الملف' in _drawer(page)
    items = page.query_selector_all('#drawer .ef-log li')
    assert len(items) == 2
    first, second = (i.inner_text() for i in items)
    assert 'اتبعت تلقائي لـ%s' % fx.EXPERTS['hala@experts.test'][0] in first and 'بعد الدفع' in first
    assert 'نفس بلد القانون · أقل حمل' in first
    assert 'اتبعت تلقائي لـ%s' % fx.EXPERTS['nada@experts.test'][0] in second and 'بعد اعتذار الخبير اللي قبله' in second
    assert all(i.get_attribute('class') == 'auto' for i in items)
    assert page.query_selector('#drawer .ef-log li:last-child .when').inner_text().count('·') >= 1   # التاريخ والوقت النسبي


def test_declines_show_their_reason_and_not_my_field_stands_out(open_page):
    page = open_page()
    _row(page, K2)
    field = page.inner_text('#drawer .field:has(.lab:text("اعتذروا"))')
    assert 'مش تخصصه' in field and 'ده مش مجال تخصصي' in field
    assert page.query_selector('#drawer .ef-pill.warn') is not None
    _row(page, K3)
    field = page.inner_text('#drawer .field:has(.lab:text("اعتذروا"))')
    assert 'مشغول دلوقتي — مشغولة' in field
    assert 'عنده تعارض مصالح — عندي تعارض' in field
    assert 'سبب تاني' in field                                                  # ندى: كود `other` من غير نص


def test_the_no_candidate_drawer_says_so_and_what_to_do(open_page):
    page = open_page()
    _row(page, K3)
    d = _drawer(page)
    assert 'التوزيع التلقائي ما لقاش خبير متاح للملف ده' in d and '%s اعتذروا ومفيش غيرهم' % _ar(page, 3) in d
    assert 'ابعته بإيدك' in d and 'هيترد للعميل بعد ٤٨ ساعة من الدفع' in d
    assert 'أخرى: قانون بحري' in page.inner_text('#drawer .ef-chips')


def test_a_manual_send_is_logged_and_clears_the_stuck_state(open_page, harness):
    ef = _platform()
    page = open_page(ef=ef)
    _row(page, K1)
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('.ef-cand')
    page.click('.ef-cand[data-k="0"]')
    page.click('#ep_go')
    page.wait_for_function("() => !document.querySelector('.ef-cand')")
    k1 = next(f for lane in (ef.waiting,) for f in lane if f['id'] == K1)
    assert [(e['by'], e['reason']) for e in k1['assign_log']] == [('founder', 'manual')]
    page.wait_for_function("() => window.EP && EP.state.inbox==='ready'")
    _row(page, K1)
    page.wait_for_selector('#drawer .ef-log')
    li = page.inner_text('#drawer .ef-log li')
    assert 'اتبعت بإيدك لـ%s' % fx.EXPERTS['hala@experts.test'][0] in li and 'بإيدك' in li
    assert page.dialogs == []


# ---------------------------------------------------------------- ٤) قايمة المرشّحين

def test_candidates_keep_the_platforms_order_with_specialties_contracts_and_leave(open_page):
    page = open_page()
    _row(page, K1)
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('.ef-cand')
    names = [n.inner_text() for n in page.query_selector_all('.ef-cand .nm')]
    assert names == [fx.EXPERTS[e][0] for e in ('hala@experts.test', 'nada@experts.test', 'karim@experts.test')]
    hala, nada, karim = (c.inner_text() for c in page.query_selector_all('.ef-cand'))
    assert 'عقارات وإيجارات' in hala and 'مدني وعقود' in hala and 'بيراجع عقود' in hala
    assert 'أخرى: عقود التأمين' in nada and 'بيراجع عقود' not in nada
    assert 'في إجازة' in karim and 'عمالي' in karim
    assert 'في إجازة' not in hala


def test_a_candidate_on_leave_can_still_be_picked_by_hand(open_page, harness):
    page = open_page()
    _row(page, K1)
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('.ef-cand')
    assert page.query_selector('.ef-cand[data-k="2"] input').is_enabled()
    page.click('.ef-cand[data-k="2"]')
    assert page.inner_text('#ep_go') == 'ابعته لـ%s' % fx.EXPERTS['karim@experts.test'][0]
    assert page.is_enabled('#ep_go')


def test_old_candidates_without_the_new_keys_render_exactly_as_before(open_page):
    page = open_page()
    _row(page, F1)
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('.ef-cand')
    tags = [t.inner_text() for t in page.query_selector_all('.ef-cand .tags span')]
    assert not any(t in tags for t in ('بيراجع عقود', 'في إجازة'))
    assert 'من نفس بلد القانون' in tags


# ---------------------------------------------------------------- ٥) درج المراجعة: وثيقة العقد

def test_the_review_drawer_shows_the_contract_document_with_clauses_by_risk(open_page):
    page = open_page()
    _row(page, KR, 'review')
    page.wait_for_selector('#drawer .ef-verdict')
    d = _drawer(page)
    assert 'مراجعة العقد زي ما هتوصل لـ' in d and 'مراجعة عقد من خبير معتمد لدى البروفيسور' in d
    assert 'عقد توريد الأثاث.pdf' in d and 'عقد · %s صفحات' % _ar(page, 6) in d
    verdict = page.query_selector('#drawer .ef-verdict')
    assert 'يوقّع بعد تعديل البنود' in verdict.inner_text() and 'sign_after_changes' in verdict.get_attribute('class')
    clauses = page.query_selector_all('#drawer .ef-clause')
    assert [c.get_attribute('class').split()[-1] for c in clauses] == ['high', 'medium', 'low']   # مرتفع ⇒ متوسط ⇒ منخفض
    assert 'البند ٥: الغرامة' in clauses[0].inner_text() and 'خطر مرتفع' in clauses[0].inner_text()
    assert 'الصياغة المقترحة' in clauses[0].inner_text() and 'بحد أقصى ١٠٪' in clauses[0].inner_text()
    assert 'بيرد على نقطة القلق رقم ١' in clauses[0].inner_text()
    assert 'خطر متوسط' in clauses[1].inner_text() and 'خطر منخفض' in clauses[2].inner_text()
    assert 'الصياغة المقترحة' not in clauses[2].inner_text()                    # البند المنخفض من غير صياغة
    assert 'ماذا يفعل العميل الآن' in d and 'اطلب تعديل البند ٥' in d
    assert 'الخطوة الجاية' not in d                                              # دي بتاعة الأسئلة والأجوبة مش العقود
    assert page.dialogs == []


def test_the_contract_review_keeps_its_three_buttons(open_page):
    page = open_page()
    _row(page, KR, 'review')
    page.wait_for_selector('#drawer .ef-verdict')
    assert page.query_selector('#drawer [data-a="rv_ok"]') is not None
    assert page.query_selector('#drawer [data-a="rv_back"]') is not None
    assert page.query_selector('#drawer [data-a="ef_refund"]') is not None


@pytest.mark.parametrize('verdict,cls,text', [('sign_ok', 'sign_ok', 'ممكن يوقّع زي ما هو'),
                                              ('dont_sign', 'dont_sign', 'ما ينصحش بالتوقيع')])
def test_the_other_verdicts_wear_their_own_bar(open_page, verdict, cls, text):
    ef = _platform()
    ef.review[-1]['pending_opinion'].update({'verdict': verdict, 'clauses': [], 'todo': []})
    page = open_page(ef=ef)
    _row(page, KR, 'review')
    page.wait_for_selector('#drawer .ef-verdict')
    bar = page.query_selector('#drawer .ef-verdict')
    assert text in bar.inner_text() and cls in bar.get_attribute('class').split()
    assert 'من غير بنود' in _drawer(page)


def test_while_the_detail_loads_the_contract_says_so_and_never_shows_the_wrong_shape(open_page, harness):
    ef = _platform()
    page = open_page(ef=ef)
    harness.hold.add(('GET', '/api/platform-expert-files/' + KR))
    try:
        _row(page, KR, 'review')
        page.wait_for_function("() => document.querySelector('#drawer .ef-rv')")
        d = _drawer(page)
        assert '…بنجيب مراجعة العقد' in d
        assert 'الرأي مش ظاهر هنا' not in d and 'الخطوة الجاية' not in d
    finally:
        harness.hold.discard(('GET', '/api/platform-expert-files/' + KR))
        harness.release_held()
    page.wait_for_selector('#drawer .ef-verdict')


def test_a_failed_detail_says_so_for_a_contract(open_page):
    ef = _platform()
    ef.detail_fail = True
    page = open_page(ef=ef)
    _row(page, KR, 'review')
    page.wait_for_function("() => /مبني على|ما قدرناش/.test(document.getElementById('drawer').innerText)")
    assert 'ما قدرناش نجيب' in _drawer(page)
    assert page.query_selector('#drawer .ef-verdict') is None


def test_a_question_review_is_the_old_questions_and_answers(open_page):
    page = open_page()
    _row(page, fx.R1['id'], 'review')
    page.wait_for_selector('#drawer .ef-based')
    d = _drawer(page)
    assert 'الرأي زي ما هيوصل لـ' in d and 'الخطوة الجاية' in d
    assert page.query_selector('#drawer .ef-verdict') is None and page.query_selector('#drawer .ef-chips') is None


def test_the_timeline_also_shows_in_the_review_drawer(open_page):
    page = open_page()
    _row(page, KR, 'review')
    page.wait_for_selector('#drawer .ef-log')
    assert 'اتبعت بإيدك لـ' in page.inner_text('#drawer .ef-log li')


# ---------------------------------------------------------------- ٦) الموبايل

def test_mobile_has_no_horizontal_scroll_with_the_switch_and_the_contract_drawer(open_page):
    page = open_page(mobile=True)
    page.click('#rows [data-auto="off"]')
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.click('#rows [data-auto="x"]')
    _row(page, KR, 'review')
    page.wait_for_selector('#drawer .ef-verdict')
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    box = page.query_selector('#rows [data-auto]')
    assert box is None or box.bounding_box()['height'] >= 40
