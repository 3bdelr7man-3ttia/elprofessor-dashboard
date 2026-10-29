# -*- coding: utf-8 -*-
"""«ملف للخبير» الجولة ١٣ في المتصفح — المستعجل وعرض سعر القضية في الدرج (SPEC-R13 §٥ · docs/EXPERT-FILES-DASHBOARD-SPEC.md §١٩).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_r13_ui.py

نفس الأداة (`uiharness/ef_route_harness.py`): الواجهة من الديسك على أصل وهمي، `/api/*` جوه العملية، والمنصة جدول في الذاكرة
(`EFPlatform(r13=True)`). ⛔ ولا نافذة متصفح (`alert`/`confirm`/`prompt`) في أي اختبار — لو ظهرت نافذة الاختبار يقع.
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
CS1, CS2, X1, X2, X3 = fx.CS1['id'], fx.CS2['id'], fx.X1['id'], fx.X2['id'], fx.X3['id']
RES_PATH = '/api/bridge/expert-files/%s/case/milestones/%d/resolve'


@pytest.fixture(scope='module')
def harness():
    h = Harness(fx.EFPlatform(r13=True))
    yield h
    h.uninstall()


@pytest.fixture(scope='module')
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture
def open_page(pw, harness):
    browsers = []

    def _open(role='admin', ef=None, hash_='#inbox', mobile=False):
        harness.ef = ef or fx.EFPlatform(r13=True)
        try:
            br = pw.chromium.launch(args=['--single-process'])
        except Exception as exc:
            pytest.skip('chromium غير متاح لـplaywright: %s' % exc)
        browsers.append(br)
        ctx = harness.context(br, role, {'width': 390, 'height': 844} if mobile else {'width': 1440, 'height': 900}, mobile)
        page = ctx.new_page()
        page.dialogs = []
        page.on('dialog', lambda d: (page.dialogs.append(d.message), d.dismiss()))      # ⛔ أي نافذة = فشل (بنتأكد تحت)
        page.goto(DASH + '/' + hash_, wait_until='domcontentloaded')
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
    page.click('#rows .row[data-i="%d"]' % idx)


def _ar(page, n):
    return page.evaluate("n => Number(n).toLocaleString('ar-EG')", n)


def _drawer(page):
    return page.inner_text('#drawer')


def _case_ready(page):
    page.wait_for_selector('#drawer .ef-case', timeout=15000)


def _resolve_calls(harness):
    return [c for c in harness.platform_calls if c[0] == 'POST' and '/case/milestones/' in c[1]]


# ---------------------------------------------------------------- الصفوف والفلاتر

def test_urgent_rows_wear_the_badge_and_the_fallen_back_one_says_so(open_page):
    page = open_page()
    page.click('#filters .chip[data-f="t:files"]')
    rows = page.inner_text('#rows')
    assert fx.X1['title'] in rows and fx.X2['title'] in rows and fx.X3['title'] in rows
    assert 'ملف مستعجل مستني خبير' in rows                                    # X1: العنوان على الصفّ
    badges = page.evaluate("() => INBOX.filter(r => r.apiKind === 'expert_file')"
                           ".map(r => [r.apiId, (r.badges || []).map(b => b.t)])")
    got = dict((k, v) for k, v in badges)
    assert '⚡ مستعجل' in got[X1] and '⚡ مستعجل' in got[X3]
    assert 'اتحوّل لعادي' in got[X2] and '⚡ مستعجل' not in got[X2]
    assert all('⚡ مستعجل' not in v for k, v in got.items() if k not in (X1, X3))


def test_urgent_waiting_file_is_a_real_item_not_a_for_your_info_line(open_page):
    """ملف اتبعت لخبير جوه الـ١٢ ساعة بيبقى «للعلم» — المستعجل المستني ما ينفعش (ميعاده ٦ ساعات)."""
    ef = fx.EFPlatform(r13=True)
    ef.waiting = [fx.sent_inside_12h(f) if f['id'] == X1 else f for f in ef.waiting]
    page = open_page(ef=ef)
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).fyi", X1) is False
    assert page.evaluate("id => INBOX.find(r => r.apiId === id).slaWarn", X1) is True


def test_the_two_new_filters_count_and_filter_the_rows(open_page):
    page = open_page()
    chips = page.inner_text('#filters')
    assert '⚡ مستعجل (%s)' % _ar(page, 2) in chips
    assert 'قضايا فيها ملاحظة (%s)' % _ar(page, 1) in chips
    page.click('#filters .chip[data-f="urgent"]')
    rows = page.inner_text('#rows')
    assert fx.X1['title'] in rows and fx.X3['title'] in rows
    assert fx.X2['title'] not in rows and fx.F1['title'] not in rows and fx.CS1['title'] not in rows
    page.click('#filters .chip[data-f="case"]')
    rows = page.inner_text('#rows')
    assert fx.CS1['title'] in rows and 'ملاحظة من العميل على مرحلة من قضية' in rows
    assert fx.X1['title'] not in rows and fx.F1['title'] not in rows
    # الصفّ بيورّي مرحلته ومبلغها (الدفعة الأولى ٧٥٠٠) وللخبير ٥٦٢٥
    assert _ar(page, 7500) in rows and _ar(page, 5625) in rows and 'الدفعة الأولى: بدء العمل' in rows


def test_without_any_round_13_data_there_are_no_new_filters(open_page):
    page = open_page(ef=fx.EFPlatform(r8=True))
    chips = page.inner_text('#filters')
    assert 'مستعجل' not in chips and 'قضايا فيها ملاحظة' not in chips


def test_a_platform_before_round_13_does_not_make_a_failure_strip(open_page):
    """منصة ما تعرفش `case_disputed` بترد ٤٢٢ — مش عطل ولا «تعذّر جلب»."""
    ef = fx.EFPlatform(r8=True)
    real = ef.handle

    def handle(method, path, params=None, body=None):
        if path == '/api/bridge/expert-files' and (params or {}).get('status') in ('case_disputed', 'urgent', 'case_open'):
            return 422, {'detail': [{'loc': ['query', 'status'], 'msg': 'bad'}]}
        return real(method, path, params, body)

    ef.handle = handle
    page = open_page(ef=ef)
    assert 'تعذّر جلب' not in page.inner_text('#view')
    assert page.evaluate("() => INBOX.some(r => r.efLane === 'case_disputed')") is False


# ---------------------------------------------------------------- درج المستعجل

def test_the_urgent_waiting_drawer_says_when_to_start_and_when_the_opinion_is_due(open_page):
    page = open_page()
    _row(page, X1)
    page.wait_for_selector('#drawer .ef-urgent')
    box = page.inner_text('#drawer .ef-urgent')
    assert '⚡ مستعجل · الرأي خلال ٢٤ ساعة' in box
    assert 'ابدأ قبل' in box and 'الرأي قبل' in box
    assert 'يتحوّل عادي ويرجع الفرق لمحفظة العميل لوحده' in box
    assert 'كان مستعجل' not in box
    assert page.dialogs == []


def test_the_started_urgent_drawer_has_no_start_by_warning(open_page):
    page = open_page()
    _row(page, X3)
    page.wait_for_selector('#drawer .ef-urgent')
    box = page.inner_text('#drawer .ef-urgent')
    assert 'الخبير بدأ' in box and 'الرأي قبل' in box and 'ابدأ قبل' not in box
    assert 'يتحوّل عادي' not in box


def test_the_fallen_back_drawer_says_it_became_normal_and_what_came_back(open_page):
    page = open_page()
    _row(page, X2)
    page.wait_for_selector('#drawer .ef-urgent.fell')
    box = page.inner_text('#drawer .ef-urgent')
    assert 'كان مستعجل واتحوّل عادي' in box
    assert _ar(page, 300) in box and 'ج' in box
    assert 'لمحفظة العميل' in box


def test_a_normal_file_drawer_has_neither_card(open_page):
    page = open_page()
    _row(page, fx.F1['id'])
    page.wait_for_selector('#drawer .dh')
    assert page.query_selector('#drawer .ef-urgent') is None and page.query_selector('#drawer .ef-case') is None


def test_the_review_drawer_shows_the_urgent_card_next_to_the_voice_player(open_page):
    ef = fx.EFPlatform(r8=True, r13=True)
    for f in ef.review:
        if f['id'] == fx.R1['id']:
            f['speed'] = 'urgent'
            f['urgent'] = fx.urgent_view('started', start_h=-3.0, due_h=20.0, started_h=-4.0)
    page = open_page(ef=ef)
    _row(page, fx.R1['id'])
    page.wait_for_selector('#drawer .ef-voice')
    page.wait_for_selector('#drawer .ef-urgent')
    order = page.evaluate("() => { const d = document.getElementById('drawer');"
                          " return d.innerHTML.indexOf('ef-urgent') < d.innerHTML.indexOf('ef-voice'); }")
    assert order is True
    assert page.is_enabled('#drawer [data-a="rv_ok"]')                         # المراجعة نفسها ما اتأثرتش


def test_the_dispute_drawer_shows_the_urgent_card_too(open_page):
    ef = fx.EFPlatform(r13=True)
    ef.disputed[0]['speed'] = 'urgent'
    ef.disputed[0]['urgent'] = fx.urgent_view('started', start_h=-30.0, due_h=-6.0, started_h=-29.0)
    page = open_page(ef=ef)
    _row(page, fx.D1['id'])
    page.wait_for_selector('#drawer .ef-urgent')
    assert 'الرأي قبل' in page.inner_text('#drawer .ef-urgent')


# ---------------------------------------------------------------- درج القضية

def test_the_case_drawer_shows_the_quote_and_every_milestone_with_the_money_split(open_page, harness):
    harness.platform_calls.clear()
    page = open_page()
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    box = _drawer(page)
    assert 'عرض سعر' in box and 'العميل قبل العرض' in box
    assert _ar(page, 15000) in box and 'دفعتان: ٥٠٪ الآن و٥٠٪ عند رفع الدعوى' in box
    assert 'رفع الدعوى وحضور الجلسات' in box and 'الاستئناف ومصاريف الخبراء' in box and '٦ أشهر تقريبًا' in box
    ms = page.query_selector_all('#drawer .ef-ms')
    assert len(ms) == 2
    first, second = [m.inner_text() for m in ms]
    assert 'الدفعة الأولى: بدء العمل' in first and 'العميل عنده ملاحظة · مستني حسمك' in first
    for label, n in (('يدفع العميل', 7500), ('للخبير', 5625), ('للمنصة', 1875)):
        assert label in first and _ar(page, n) in first, label
    assert '٢٥٪' in first                                                     # نسبة المنصة بتبان للمؤسس
    assert 'جهّزت صحيفة الدعوى' in first and 'الخبير ما رفعش الدعوى' in first
    assert 'الدفعة الثانية: عند رفع الدعوى' in second and 'لسه ما اتفتحتش للدفع' in second
    assert page.query_selector('#drawer .ef-ms[data-ms="2"] [data-cs]') is None  # الأزرار للمرحلة اللي فيها ملاحظة بس
    assert [c[1] for c in harness.platform_calls if c[0] == 'GET' and c[1] == '/api/bridge/expert-files/' + CS1]
    assert page.dialogs == []


def test_a_sent_quote_shows_the_clients_question_and_the_missing_reply(open_page, harness):
    ef = fx.EFPlatform(r13=True)
    cs1 = next(f for f in ef.case_files if f['id'] == CS1)
    cs1['case'] = fx.copy.deepcopy(next(f for f in ef.case_files if f['id'] == CS2)['case'])
    cs1['case']['milestones'][0]['status'] = 'disputed'                       # عشان الصفّ يفضل في فلتر الملاحظات
    page = open_page(ef=ef)
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    box = _drawer(page)
    assert 'أُرسل العرض · بانتظار رد العميل' in box
    assert 'دفعة واحدة' in box and 'هل الأتعاب بتشمل الخبير الهندسي؟' in box
    assert 'رد الخبير' in box and 'لسه ما ردّش' in box


def test_the_quote_texts_are_shown_as_text_not_as_html(open_page):
    ef = fx.EFPlatform(r13=True)
    cs1 = ef.case_files[0]
    cs1['case']['quote']['includes'] = '<img src=x onerror="window.__pwn=1"> شامل'
    cs1['case']['milestones'][0]['problem'] = '<b id="pwn">كبير</b>'
    page = open_page(ef=ef)
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    assert page.evaluate("() => window.__pwn") is None
    assert page.query_selector('#drawer #pwn') is None and page.query_selector('#drawer .ef-quote img') is None
    assert '<img src=x' in page.inner_text('#drawer .ef-quote')


def test_the_row_works_even_when_the_list_row_carries_no_case(open_page):
    ef = fx.EFPlatform(r13=True)
    real = ef.handle

    def handle(method, path, params=None, body=None):
        code, out = real(method, path, params, body)
        if path == '/api/bridge/expert-files' and (params or {}).get('status') == 'case_disputed':
            out = dict(out, files=[{k: v for k, v in f.items() if k != 'case'} for f in out['files']])
        return code, out

    ef.handle = handle
    page = open_page(ef=ef)
    page.click('#filters .chip[data-f="case"]')
    assert fx.CS1['title'] in page.inner_text('#rows')
    _row(page, CS1, 'case_disputed')
    _case_ready(page)                                                         # الدرج بيجيب القضية من التفاصيل
    assert len(page.query_selector_all('#drawer .ef-ms')) == 2


def test_a_failed_detail_says_so_and_does_not_offer_the_buttons(open_page):
    ef = fx.EFPlatform(r13=True)
    ef.detail_fail = False
    real = ef.handle

    def handle(method, path, params=None, body=None):
        if method == 'GET' and path == '/api/bridge/expert-files/' + CS1:
            return 500, {'detail': 'boom'}
        code, out = real(method, path, params, body)
        if path == '/api/bridge/expert-files' and (params or {}).get('status') == 'case_disputed':
            out = dict(out, files=[{k: v for k, v in f.items() if k != 'case'} for f in out['files']])
        return code, out

    ef.handle = handle
    page = open_page(ef=ef)
    _row(page, CS1, 'case_disputed')
    page.wait_for_function("() => /ما قدرناش نجيب القضية دلوقتي/.test(document.getElementById('drawer').innerText)", timeout=15000)
    assert page.query_selector('#drawer [data-cs]') is None


def test_the_resolve_buttons_wait_for_the_detail_numbers(open_page):
    """سطر القايمة (`case_row_bridge`) فيه المبلغ بس ⇒ لحد ما تفاصيل الملف توصل (أجر الخبير ونصيب المنصة وملاحظة العميل)
    ما فيش زراري حسم؛ ولما توصل بتظهر. ومحاولة حسم بأرقام ناقصة (`go`) ما بتبعتش حاجة."""
    page = open_page()
    out = page.evaluate("""() => {
      const i = {apiId: 'x1', ef: {}};
      const thin = {n: 1, label: 'المرحلة الأولى', amount: 7500, status: 'disputed'};
      const full = Object.assign({}, thin, {expert_amount: 5625, platform_fee: 1875, problem: 'لم تُنجز'});
      const mk = m => { const d = document.createElement('div'); d.innerHTML = efMsHtml(i, m, 'EGP'); return d; };
      const a = mk(thin), b = mk(full);
      return {thinBtns: a.querySelectorAll('[data-cs]').length, thinText: a.innerText,
              fullBtns: b.querySelectorAll('[data-cs]').length, ready: [efMsReady(thin), efMsReady(full)]};
    }""")
    assert out['thinBtns'] == 0 and 'بنجيب الأرقام' in out['thinText']
    assert out['fullBtns'] == 2 and out['ready'] == [False, True]
    assert page.dialogs == []


# ---------------------------------------------------------------- الحسم بتأكيد جوه الدرج

def test_release_asks_inside_the_drawer_first_and_sends_nothing_before_the_confirm(open_page, harness):
    harness.platform_calls.clear()
    page = open_page()
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="rel"]')
    page.wait_for_selector('#drawer .ef-conf')
    box = page.inner_text('#drawer .ef-conf')
    assert 'هتحوّل' in box and _ar(page, 5625) in box and fx.CS1['expert_email'] and 'ندى' in box
    assert _ar(page, 1875) in box and 'للمنصة' in box
    assert 'ما ينفعش ترجع فيها' in box
    assert 'حوّل' in page.inner_text('#drawer [data-cs="go"]') and _ar(page, 5625) in page.inner_text('#drawer [data-cs="go"]')
    assert _resolve_calls(harness) == []                                       # ولا نداء قبل التأكيد
    assert page.query_selector('#epModal') is None                              # مش نافذة — جوه الدرج
    assert page.dialogs == []
    page.click('#drawer [data-cs="x"]')                                        # رجوع
    assert page.query_selector('#drawer .ef-conf') is None
    assert page.query_selector('#drawer [data-cs="rel"]') and page.query_selector('#drawer [data-cs="ref"]')
    assert _resolve_calls(harness) == []


def test_release_confirmed_sends_one_call_and_the_row_leaves_the_inbox(open_page, harness):
    harness.platform_calls.clear()
    page = open_page()
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="rel"]')
    page.fill('#drawer #cs_note', 'الشغل اتسلّم')
    page.click('#drawer [data-cs="go"]')
    page.wait_for_function("() => !INBOX.some(r => r.efLane === 'case_disputed')", timeout=15000)
    calls = _resolve_calls(harness)
    assert len(calls) == 1
    method, path, _params, body = calls[0]
    assert path == RES_PATH % (CS1, 1)
    assert body == {'action': 'release', 'note': 'الشغل اتسلّم', 'by': 'admin@local.test'}
    assert harness.ef.case_files[0]['case']['milestones'][0]['status'] == 'released'
    assert page.query_selector('#filters .chip[data-f="case"]') is None
    assert page.dialogs == []


def test_refund_asks_with_the_whole_amount_and_goes_to_the_wallet(open_page, harness):
    harness.platform_calls.clear()
    page = open_page()
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="ref"]')
    page.wait_for_selector('#drawer .ef-conf')
    box = page.inner_text('#drawer .ef-conf')
    assert 'هترجّع' in box and _ar(page, 7500) in box and 'لمحفظة' in box and 'دعاء' in box
    assert 'بوابة' not in box and 'فيزا' not in box                             # الرد دايمًا رصيد في المحفظة
    page.click('#drawer [data-cs="go"]')
    page.wait_for_function("() => !INBOX.some(r => r.efLane === 'case_disputed')", timeout=15000)
    (call,) = _resolve_calls(harness)
    assert call[3]['action'] == 'refund' and call[1] == RES_PATH % (CS1, 1)
    assert harness.ef.case_files[0]['case']['milestones'][0]['status'] == 'refunded'
    # كل النداءات الكتابية للمنصة: مسار الحسم ده بس (مفيش دفع ولا بوابة)
    writes = [c[1] for c in harness.platform_calls if c[0] == 'POST']
    assert writes == [RES_PATH % (CS1, 1)]


def test_a_second_milestone_in_dispute_keeps_the_drawer_open_on_the_other_one(open_page, harness):
    ef = fx.EFPlatform(r13=True)
    ef.case_files[0]['case']['milestones'][1]['status'] = 'disputed'
    page = open_page(ef=ef)
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    assert len(page.query_selector_all('#drawer [data-cs="rel"]')) == 2
    page.click('#drawer .ef-ms[data-ms="1"] [data-cs="rel"]')
    page.click('#drawer [data-cs="go"]')
    page.wait_for_function("() => { const d = document.querySelector('#drawer .ef-ms[data-ms=\"1\"]');"
                           " return d && /اتحوّلت للخبير/.test(d.innerText); }", timeout=15000)
    assert page.query_selector('#drawer .ef-ms[data-ms="2"] [data-cs="rel"]')    # التانية لسه مستنية قرارك
    assert page.query_selector('#drawer .ef-ms[data-ms="1"] [data-cs]') is None


def test_two_fast_clicks_send_one_call(open_page, harness):
    harness.platform_calls.clear()
    page = open_page()
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="rel"]')
    harness.hold.add(('POST', '/api/platform-expert-files/%s/case/milestones/1/resolve' % CS1))
    page.click('#drawer [data-cs="go"]')
    page.wait_for_function("() => document.querySelector('#drawer [data-cs=\"go\"]') && "
                           "document.querySelector('#drawer [data-cs=\"go\"]').disabled", timeout=15000)
    assert page.is_disabled('#drawer [data-cs="x"]')                            # الرجوع كمان مقفول وهو بيتحوّل
    assert 'بيتحوّل…' in page.inner_text('#drawer [data-cs="go"]')
    page.evaluate("() => document.querySelector('#drawer [data-cs=\"go\"]').click()")   # ضغطة تانية بالقوة
    harness.hold.clear()
    harness.release_held()
    page.wait_for_function("() => !INBOX.some(r => r.efLane === 'case_disputed')", timeout=15000)
    assert len(_resolve_calls(harness)) == 1


def test_a_refusal_from_the_platform_is_said_in_the_drawer_and_locks_the_button(open_page, harness):
    ef = fx.EFPlatform(r13=True)
    real = ef.handle

    def handle(method, path, params=None, body=None):
        if method == 'POST' and path.endswith('/resolve') and '/case/milestones/' in path:
            return 409, {'detail': fx.E_CASE_RELEASE_MANUAL}
        return real(method, path, params, body)

    ef.handle = handle
    page = open_page(ef=ef)
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="rel"]')
    page.click('#drawer [data-cs="go"]')
    page.wait_for_function("() => /مفيش تحويل للخبير من هنا/.test(document.querySelector('#drawer .ef-conf-err').innerText)",
                           timeout=15000)
    assert page.is_disabled('#drawer [data-cs="go"]')                           # رفض نهائي ⇒ الضغطة التانية هتترفض بنفس الكلام
    assert page.is_enabled('#drawer [data-cs="x"]')
    assert page.dialogs == []


def test_a_lost_reply_says_so_and_does_not_let_the_founder_click_again(open_page, harness):
    ef = fx.EFPlatform(r13=True)
    real = ef.handle

    def handle(method, path, params=None, body=None):
        if method == 'POST' and '/case/milestones/' in path:
            return 502, {'detail': 'bad gateway'}
        return real(method, path, params, body)

    ef.handle = handle
    harness.platform_calls.clear()
    page = open_page(ef=ef)
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="ref"]')
    page.click('#drawer [data-cs="go"]')
    page.wait_for_function("() => /ما وصلناش رد/.test(document.getElementById('drawer').innerText)", timeout=15000)
    assert page.is_disabled('#drawer [data-cs="go"]')
    assert len(_resolve_calls(harness)) == 1                                    # ولا إعادة محاولة


def test_opening_another_row_forgets_the_open_confirmation(open_page):
    page = open_page()
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    page.click('#drawer [data-cs="rel"]')
    page.wait_for_selector('#drawer .ef-conf')
    _row(page, X1)
    page.wait_for_selector('#drawer .ef-urgent')
    assert page.query_selector('#drawer .ef-conf') is None
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    assert page.query_selector('#drawer .ef-conf') is None and page.query_selector('#drawer [data-cs="rel"]')


def test_the_case_drawer_on_a_phone_has_no_sideways_scroll_and_big_touch_targets(open_page):
    page = open_page(mobile=True)
    page.click('#filters .chip[data-f="case"]')
    _row(page, CS1, 'case_disputed')
    _case_ready(page)
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1") is True
    page.click('#drawer [data-cs="rel"]')
    page.wait_for_selector('#drawer .ef-conf')
    h = page.evaluate("() => [...document.querySelectorAll('#drawer .ef-conf .btn')].map(b => b.getBoundingClientRect().height)")
    assert h and all(x >= 44 for x in h)
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1") is True


def test_the_audit_log_names_the_new_action_in_arabic(open_page):
    page = open_page()
    assert page.evaluate("() => AUDIT_LABEL['expert_file.case_resolve']") == 'حسم ملاحظة على مرحلة من قضية'


def test_zero_real_requests_at_the_very_end(harness):
    assert harness.unexpected_blocked() == []
