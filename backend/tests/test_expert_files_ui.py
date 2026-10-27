# -*- coding: utf-8 -*-
"""«ملف للخبير» في المتصفح — السلوك نفسه (الجولة ٦ · SPEC §١٠-ج، ومتحدّثة للجولة ٧ · §١٥).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_ui.py

⛔ من غير ولا منفذ ولا سيرفر: الأداة (`uiharness/ef_route_harness.py`) بتخدم `dashboard-cloud/` من الديسك على
أصل وهمي (`https://dash.test`) وبتنفّذ `/api/*` جوه العملية بـ`app.test_client()`، والمنصة جدول في الذاكرة.
أي أصل تاني بيتقفل ويتسجّل — والاختبار الأخير بيتأكد إن مفيش ولا طلب حقيقي.
Chromium بيشتغل `--single-process` (جوه صندوق الأوامر العادي بيموت) — سياق واحد لكل متصفح.
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


@pytest.fixture(scope='module')
def harness():
    h = Harness(fx.EFPlatform())
    yield h
    h.uninstall()


@pytest.fixture(scope='module')
def pw():
    with sync_playwright() as p:
        yield p


@pytest.fixture
def open_page(pw, harness):
    browsers = []

    def _open(role='admin', ef=None, hash_='#inbox', wait_ready=True, mobile=False):
        harness.ef = ef or fx.EFPlatform()
        try:
            br = pw.chromium.launch(args=['--single-process'])
        except Exception as exc:              # متصفح مش متنزّل
            pytest.skip('chromium غير متاح لـplaywright: %s' % exc)
        browsers.append(br)
        ctx = harness.context(br, role, {'width': 390, 'height': 844} if mobile else {'width': 1440, 'height': 900},
                              mobile)
        page = ctx.new_page()
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


def _row(page, rid):
    idx = page.evaluate("id => INBOX.findIndex(r => r.apiId === id)", rid)
    assert idx >= 0, rid
    page.click('#rows .row[data-i="%d"]' % idx)


def test_rows_render_in_their_chips_and_a_file_dispute_is_listed_once(open_page):
    page = open_page()
    page.click('#filters .chip[data-f="t:files"]')
    texts = page.inner_text('#rows')
    for f in (fx.F1, fx.F2, fx.F3, fx.F4, fx.F5):
        assert f['title'] in texts, f['title']
    for label in ('ملف مستني خبير', 'خبير اعتذر — الملف مستني خبير تاني', 'ملف ما اتستلمش من ١٢ ساعة', 'رأي متأخر',
                  'فلوس ملف ما رجعتش لوحدها', 'أجر خبير ما اتحوّلش لوحده', 'اتدفع وما وصلش لقايمة التوزيع'):
        assert label in texts, label
    assert '⚠️ البلد مختلف' in texts and '⚠️ الرقم مش واضح' in texts and '⏳ فاضل أقل من ١٢ ساعة' in texts
    page.click('#filters .chip[data-f="t:disputes"]')
    d = page.inner_text('#rows')
    assert d.count(fx.D1['title']) == 1                           # D1′ من قايمة الاستشارات ما اتكررش
    assert fx.D2['title'] in d and fx.D3['title'] in d
    chips = page.inner_text('#filters')
    # ٥ مستنية + متأخر + «أجر ما اتحوّلش» (فلتر blocked بس) + ٢ «اتدفع وما وصلش» · F7 مرة واحدة مع إنه في حارتين
    assert 'ملفات للخبير (٩)' in chips and 'نزاعات (٣)' in chips and 'محتاج تدخّلك (٤)' in chips
    assert page.evaluate("id => INBOX.filter(r => r.apiId === id).length", fx.F7['id']) == 1


def test_queue_chips_use_the_platform_numbers_and_land_on_their_chip(open_page):
    page = open_page()
    panel = page.inner_text('section.panel >> nth=0')
    for label in ('ملفات مستنية توزيعك', 'ملفات ما اتستلمتش من ١٢ ساعة', 'آراء متأخرة', 'ملفات فيها «عندي مشكلة»',
                  'نزاعات على استشارات', 'ملفات فلوسها واقفة', 'ملفات اتدفعت وما وصلتش للتوزيع',
                  'للعلم: ١ ملف اتبعت لخبير ولسه ما اتستلمش · ٣ ملف مستني الدفع'):
        assert label in panel, label
    # سطر تنبيه ليه عدّاد ظاهر فوقه ما يتكررش (كان نفس الرقم مرتين) · ولا «راجعه من الداشبورد» ولا «لا شاشة له»
    for gone in ('📁', '⏰', 'رأي متأخر', 'ملف فيه ملاحظة مستنية قرارك', 'راجعه من الداشبورد', 'لا شاشة له بعد',
                 'ملفات لسه ما اتستلمتش', 'نزاع على استشارة مستني قرارك', 'ملف فلوسه ما اتحرّكتش لوحدها'):
        assert gone not in panel, gone
    q = page.evaluate("() => EP.data.opsQueue")
    chips = {k: page.inner_text('.opsq[data-k="%s"] b' % k) for k in
             ('expert_files_awaiting_assignment', 'expert_files_assign_overdue', 'consultation_disputes',
              'expert_files_blocked', 'expert_files_unactivated')}
    assert chips == {'expert_files_awaiting_assignment': '٤', 'expert_files_assign_overdue': '١',
                     'consultation_disputes': '٢', 'expert_files_blocked': '٢', 'expert_files_unactivated': '٢'}, chips
    assert q['expert_files_waiting'] == 5                          # الرقم المجمّع لسه جاي بس ما بقاش شريحة
    page.click('.opsq[data-k="expert_files_disputed"]')
    page.wait_for_timeout(200)
    assert page.evaluate("() => activeFilter") == 't:disputes'


def test_refund_window_names_amount_currency_and_client_before_any_post(open_page, harness):
    page = open_page()
    before = len(harness.dash_calls)
    _row(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    body = page.inner_text('#epModal')
    assert '٥٠٠ ج' in body and 'ياسمين' in body and fx.F3['title'] in body and 'أ. هالة سمير' in body
    assert 'جنيه مصري' in body and 'EGP' not in body                  # العملة بالكلام مش بالكود
    assert 'ومش هيتحوّل أجر لـأ. هالة سمير' in body                    # من غير «مش هياخد» بصيغة المذكّر
    assert page.inner_text('#mc_go') == 'رجّع ٥٠٠ ج'
    posts = [c for c in harness.dash_calls[before:] if c[0] == 'POST']
    assert posts == []                                             # التأكيد قبل أي فعل


def test_double_click_on_refund_sends_one_request(open_page, harness):
    page = open_page()
    path = '/api/platform-expert-files/%s/refund' % fx.F3['id']
    _row(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    harness.hold.add(('POST', path))
    try:
        page.locator('#mc_go').dblclick()
        page.wait_for_timeout(300)
        assert page.inner_text('#mc_go') == 'بيرجع…'
        assert page.is_disabled('#mc_go')
        page.evaluate("() => { const b = document.getElementById('mc_go'); b.click(); b.click(); }")
        page.mouse.click(5, 5)                                     # ضغطة برّه النافذة ما تقفلهاش وهي شغّالة
        assert page.query_selector('#epModal') is not None
    finally:
        harness.hold.discard(('POST', path))
    assert sum(1 for c in harness.dash_calls if c == ('POST', path)) == 1
    harness.release_held()
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.wait_for_function("id => EP.state.inbox==='ready' && !INBOX.some(r => r.apiId === id)",
                           arg=fx.F3['id'], timeout=15000)
    refunds = [c for c in harness.ef.calls if c[0] == 'POST' and c[1].endswith(fx.F3['id'] + '/refund')]
    assert len(refunds) == 1
    assert refunds[0][3] == {'note': '', 'by': 'admin@local.test'}   # الملاحظة + إيميل الأدمن بس
    assert 'ملفات للخبير (٨)' in page.inner_text('#filters')        # الصفّ اختفى والشريحة قلّت


def test_pick_expert_excludes_the_current_one_and_assigns(open_page, harness):
    page = open_page()
    _row(page, fx.F3['id'])                                        # متوزّع على هالة وما استلمش
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    names = page.inner_text('#epModal')
    assert 'أ. هالة سمير' not in names.split('الطرف التاني')[1].split('ملاحظة')[0]
    assert 'محمود السيد' in names                                   # الطرف التاني قدّام المؤسس
    assert page.is_disabled('#ep_go')
    page.click('#epModal .ef-cand >> nth=0')
    assert page.inner_text('#ep_go').startswith('ابعته لـ')
    page.click('#ep_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    sent = [c for c in harness.ef.calls if c[0] == 'POST' and c[1].endswith(fx.F3['id'] + '/assign')]
    assert len(sent) == 1 and sent[0][3]['expert_email'] != 'hala@experts.test'


def test_platform_refusal_shows_inside_the_window_and_the_button_comes_back(open_page, harness):
    page = open_page()
    _row(page, fx.D3['id'])                                        # «للعميل» مقفول: الفلوس رجعت يدوي
    assert page.is_disabled('#drawer [data-a="dsp_ref"]')
    harness.ef.cons = [c for c in harness.ef.cons if c['id'] != fx.D2['id']] + [dict(fx.D2, manual_refund_settled_at='x')]
    page.evaluate("() => { selected=null; }")
    _row(page, fx.D2['id'])                                        # الصفّ لسه بالنسخة القديمة (من غير العلامة)
    page.click('#drawer [data-a="dsp_ref"]')
    page.wait_for_selector('#mc_go')
    page.click('#mc_go')
    page.wait_for_selector('#epModal .ef-err', timeout=15000)
    assert 'الفلوس دي رجعت للعميل يدوي قبل كده' in page.inner_text('#epModal .ef-err')
    assert page.is_enabled('#mc_go')


def test_both_opinions_side_by_side_and_no_official_choice(open_page):
    page = open_page()
    _row(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    drawer = page.inner_text('#drawer')
    assert 'الرأي الأصلي' in drawer and 'تعديل الخبير' in drawer
    assert 'القرار هنا على الفلوس بس' in drawer
    page.click('#drawer [data-a="dsp_cmp"]')
    page.wait_for_selector('#epModal .cmp2')
    modal = page.inner_text('#epModal')
    assert fx.D1_OPINION['answers'][1]['text'][:30] in modal and fx.D1_REVISION['answers'][1]['text'][:30] in modal
    assert page.query_selector('#epModal [data-a]') is None         # قراية بس — ولا زرار حسم


def test_employee_never_asks_for_files_and_sees_no_failure(open_page, harness):
    before = len(harness.dash_calls)
    page = open_page(role='employee', hash_='#courses', wait_ready=False)
    page.wait_for_function("() => window.EP && EP.authed", timeout=30000)
    page.evaluate("() => EP.reload('inbox')")
    page.wait_for_function("() => EP.state.inbox==='ready'", timeout=30000)
    calls = [c for c in harness.dash_calls[before:] if 'expert-files' in c[1] or 'consultation-disputes' in c[1]]
    assert calls == []
    assert page.evaluate("() => (window.INBOX_FAILED||[]).length") == 0


def test_bridge_not_on_the_platform_yet_is_quiet(open_page):
    """الإنتاج قبل نشر الفروع: الجسر ٤٠٤ والطابور من غير مفاتيح الملفات ⇒ ولا صفوف ولا «تعذّر» ولا سطر مقفول."""
    page = open_page(ef=fx.EFPlatform(deployed=False, cons_enabled=False))
    assert page.evaluate("() => (window.INBOX_FAILED||[]).length") == 0
    assert page.evaluate("() => INBOX.filter(r => r.apiKind==='expert_file' || r.apiKind==='dispute').length") == 0
    assert page.evaluate("() => EP.data.efServiceOpen") is None
    assert 'مقفولة للناس' not in page.inner_text('body')


def test_service_closed_rows_still_show_with_the_line_and_refund_works(open_page, harness):
    """الجولة ٧ (ب١/ج٥): الخدمة مقفولة للناس والجسر شغّال بالسرّ — الصفوف المفتوحة لسه ظاهرة، وسطر بيقول إنها
    مقفولة، ومن غير «ابعته لـ…»، و«رجّع الفلوس» شغّال."""
    page = open_page(ef=fx.EFPlatform(service_open=False))
    assert page.evaluate("() => EP.data.efServiceOpen") is False
    page.click('#filters .chip[data-f="t:files"]')
    line = page.inner_text('#rows .ef-off-line')
    assert 'مقفولة للناس دلوقتي' in line and 'ما ينفعش تبعتها لخبير' in line
    assert fx.F1['title'] in page.inner_text('#rows')
    idx = page.evaluate("id => INBOX.findIndex(r => r.apiId === id)", fx.F1['id'])
    assert 'الخدمة مقفولة' in page.inner_text('#rows .row[data-i="%d"]' % idx)   # مش «مستني توزيعك»
    panel = page.inner_text('section.panel >> nth=0')
    assert 'ملف مفتوح وخدمة «ملف للخبير» مقفولة للناس دلوقتي' in panel and 'افتح المفتاح' not in panel
    _row(page, fx.F1['id'])
    assert page.query_selector('#drawer [data-a="ef_pick"]') is None
    assert 'ما ينفعش تبعته لخبير' in page.inner_text('#drawer')
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    assert [c for c in harness.ef.calls if c[0] == 'POST' and c[1].endswith(fx.F1['id'] + '/refund')]


def test_bridge_text_is_escaped_everywhere(open_page):
    evil = '<img src=x onerror="window.__pwned=1">'
    ef = fx.EFPlatform()
    for f in ef.waiting + ef.disputed:
        f['title'] = evil
        f['counterparty_name'] = evil
        f['client_first_name'] = evil
        for c in f['candidates']:
            c['name'] = evil
    ef.disputed[0]['dispute']['note'] = evil
    page = open_page(ef=ef)
    _row(page, fx.F1['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#ep_x')
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    page.click('#mc_x')
    _row(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    page.click('#drawer [data-a="dsp_cmp"]')
    page.wait_for_selector('#epModal .cmp2')
    page.wait_for_timeout(300)
    assert page.evaluate("() => window.__pwned") is None
    assert page.evaluate("() => document.querySelectorAll('img[src=\"x\"]').length") == 0


def _files_order(page):
    return page.evaluate("() => [...document.querySelectorAll('#rows .row')].map(r => INBOX[+r.dataset.i].apiId)")


def test_assigned_file_inside_its_12_hours_is_fyi_not_an_inbox_item(open_page, harness):
    """ملف اتبعت لخبير ولسه في مهلته مش بند: برّه العدّ والشرايح وشارة القايمة — سطر «للعلم» بس."""
    page = open_page()
    nav0 = page.evaluate("() => navInboxCount()")
    _row(page, fx.F1['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    page.click('#ep_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.wait_for_function("id => EP.state.inbox==='ready' && INBOX.some(r => r.apiId === id && r.fyi)",
                           arg=fx.F1['id'], timeout=15000)
    page.wait_for_timeout(200)
    assert page.evaluate("() => navInboxCount()") == nav0 - 1          # شارة «الوارد» نزلت
    chips = page.inner_text('#filters')
    assert 'ملفات للخبير (٨)' in chips
    page.click('#filters .chip[data-f="t:files"]')
    assert fx.F1['title'] not in page.inner_text('#rows .row >> nth=0')
    assert fx.F1['id'] not in _files_order(page)
    line = page.inner_text('#rows .ef-fyi-line')
    assert 'للعلم: ١ ملف اتبعت لخبير' in line
    page.click('#rows .ef-fyi-line [data-a="ef_fyi"]')                 # «اعرضهم» ⇒ يتفتح ويتشاف
    assert _files_order(page) == [fx.F1['id']]
    assert 'مستني الخبير يستلم' in page.inner_text('#rows')


def test_overdue_assignment_says_it_needs_a_new_expert(open_page):
    page = open_page()
    page.click('#filters .chip[data-f="t:files"]')
    idx = page.evaluate("id => INBOX.findIndex(r => r.apiId === id)", fx.F3['id'])
    row = page.inner_text('#rows .row[data-i="%d"]' % idx)
    assert 'محتاج تبعته لحد تاني' in row and 'مستني الخبير يستلم' not in row


def test_rows_are_sorted_most_urgent_first(open_page):
    page = open_page()
    page.click('#filters .chip[data-f="t:files"]')
    # محتاج تدخّلك (الأقدم وقوفًا) ⇐ متأخر ⇐ قرب الـ٤٨ (٥ ساعات) ⇐ ما اتستلمش من ١٢ ساعة ⇐ الباقي بالساعات
    assert _files_order(page) == [fx.U2['consultation_id'], fx.F7['id'], fx.F6['id'], fx.U1['consultation_id'],
                                  fx.F5['id'], fx.F2['id'], fx.F3['id'], fx.F4['id'], fx.F1['id']]
    page.click('#filters .chip[data-f="t:disputes"]')
    assert _files_order(page) == [fx.D3['id'], fx.D2['id'], fx.D1['id']]   # النزاعات من الأقدم
    page.click('#filters .chip[data-f="t:files"]')
    assert 'فاضل ٥ ساعات وفلوسه ترجع لوحدها' in page.inner_text('#rows')


def test_pick_window_shows_each_candidates_load(open_page):
    page = open_page()
    _row(page, fx.F1['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    hala = page.inner_text('#epModal .ef-cand >> nth=0')
    assert 'أ. هالة سمير' in hala and '⚠️ ١ ملف تاني اتبعت وما اتستلمش من ١٢ ساعة' in hala
    page.click('#ep_x')
    _row(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    body = page.inner_text('#epModal')
    sami = page.evaluate("() => [...document.querySelectorAll('#epModal .ef-cand')].map(c => c.innerText)"
                         ".filter(t => t.includes('م. سامي فؤاد'))[0] || ''")
    assert '⚠️ ١ رأي متأخر' in sami                                    # متأخر في «عقد توريد»
    assert 'رأي متأخر' not in hala


def test_release_after_a_manual_refund_says_the_platform_pays(open_page):
    page = open_page()
    _row(page, fx.D3['id'])
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    body = page.inner_text('#epModal')
    assert 'خالد خد ٢٥٠ ج يدوي قبل كده' in body and 'المنصة هتدفع ١٥٠ ج' in body
    for bad in ('الباقي', 'مش هياخد', 'مش هترجع'):
        assert bad not in body, bad
    assert page.inner_text('#mc_go') == 'حوّل ١٥٠ ج لـد. ندى حسن'


def test_release_without_an_expert_share_names_the_full_amount_and_the_blind_spot(open_page):
    ef = fx.EFPlatform()
    for c in ef.cons:
        if c['id'] == fx.D2['id']:
            # استشارة اتموّلت قبل العمولة: المنصة بتبعت اللي هيتحوّل فعلًا (المبلغ كله)
            c.update({'expert_amount': None, 'platform_fee': None, 'release_amount': 750})
    page = open_page(ef=ef)
    _row(page, fx.D2['id'])
    assert 'بتحسم من غير ما تشوفه' in page.inner_text('#drawer')
    assert 'شوفها من المنصة' not in page.inner_text('#drawer')
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    body = page.inner_text('#epModal')
    assert 'هيتحوّل المبلغ كله ٧٥٠ ج' in body and 'نصيب' not in body
    assert 'إنت بتحسم من غير ما تشوف الشغل اللي اتسلّم' in body
    assert page.inner_text('#mc_go') == 'حوّل ٧٥٠ ج لـأ. عمرو الشريف'


def test_verify_dispute_on_the_platform_address_names_the_payee_the_platform_sent(open_page):
    """الجولة ٧ (ب٦/ج١): مين هيقبض من المنصة (`payee_name`) — مش تخمين «الاحتمالين» زي الجولة ٦."""
    ef = fx.EFPlatform()
    for c in ef.cons:
        if c['id'] == fx.D3['id']:
            c.update({'expert_email': 'admin@platform.test', 'expert_name': 'حساب المنصة',
                      'manual_refund_settled_at': '', 'verified_by_email': 'nada@experts.test',
                      'payee_email': 'nada@experts.test', 'payee_name': 'د. ندى حسن', 'release_amount': 150})
    page = open_page(ef=ef)
    _row(page, fx.D3['id'])
    drawer = page.inner_text('#drawer')
    assert '١٥٠ ج لـد. ندى حسن' in drawer and 'nada@experts.test' not in drawer
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    body = page.inner_text('#epModal')
    assert 'محفظة د. ندى حسن' in body and 'حساب المنصة' not in body and 'اللي وثّق) — إلا لو' not in body
    assert page.inner_text('#mc_go') == 'حوّل ١٥٠ ج لـد. ندى حسن'


def test_dispute_drawer_refetches_on_every_open_and_never_caches_a_failure(open_page, harness):
    ef = fx.EFPlatform()
    ef.d1_revision = None                                              # الخبير لسه ما عدّلش
    page = open_page(ef=ef)
    _row(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    assert 'الخبير ما عدّلش لسه' in page.inner_text('#drawer')
    ef.d1_revision = fx.D1_REVISION                                    # بعت تعديله بعدها
    page.click('#drawer [data-a="dsp_close"]')
    _row(page, fx.D1['id'])
    page.wait_for_function("() => /الحضانة للأم لحد ١٥ سنة/.test(document.getElementById('drawer').innerText)",
                           timeout=15000)
    page.click('#drawer [data-a="dsp_cmp"]')
    page.wait_for_selector('#epModal .cmp2')
    assert fx.D1_REVISION['answers'][1]['text'][:30] in page.inner_text('#epModal')
    page.click('#cmp_x')
    ef.detail_fail = True                                              # قراية واحدة تقع
    page.click('#drawer [data-a="dsp_close"]')
    _row(page, fx.D1['id'])
    page.wait_for_selector('#drawer .ef-err', timeout=15000)
    page.click('#drawer [data-a="dsp_close"]')
    _row(page, fx.D1['id'])                                            # الفتحة الجاية بتجرّب تاني
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)


def test_lost_connection_on_refund_is_arabic_and_keeps_the_button_locked(open_page, harness):
    page = open_page()
    _row(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    page.route('**/api/platform-expert-files/*/refund', lambda r: r.abort())   # النت قطع
    page.click('#mc_go')
    page.wait_for_selector('#epModal .ef-err', timeout=15000)
    err = page.inner_text('#epModal .ef-err')
    assert 'ما وصلناش رد' in err
    assert page.is_disabled('#mc_go') and page.inner_text('#mc_go') == 'حدّث الأول وشوف حصل إيه'
    for bad in ('Failed to fetch', 'Load failed', 'HTTP', 'unauthorized'):
        assert bad not in page.inner_text('body'), bad


def test_audit_lines_name_the_file_and_the_amount(open_page):
    page = open_page()
    _row(page, fx.F4['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    page.click('#ep_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.evaluate("() => auditModal()")
    page.wait_for_selector('#auditRows .au-ef', timeout=15000)
    txt = page.inner_text('#epModal')
    assert 'سجلّ العمليات' in txt and 'Audit Log' not in txt
    assert '«%s» · ٥٠٠ ج · لـأ. هالة سمير' % fx.F4['title'] in txt
    assert fx.F4['id'] not in txt                                      # مش الرقم الداخلي


def test_mobile_queue_chip_lands_on_the_rows_and_touch_targets_are_44(open_page):
    page = open_page(mobile=True)
    page.evaluate("() => document.querySelector('.opsq[data-k=\"expert_files_awaiting_assignment\"]').scrollIntoView({block:'center'})")
    page.click('.opsq[data-k="expert_files_awaiting_assignment"]')
    page.wait_for_timeout(300)
    top = page.evaluate("() => document.getElementById('filters').getBoundingClientRect().top")
    assert 0 <= top < 844 * 0.4, top                                   # الشرايح والصفوف قدّام العين
    assert page.evaluate("() => activeFilter") == 't:files'
    hs = page.evaluate("() => [...document.querySelectorAll('#filters .chip')].map(c => c.getBoundingClientRect().height)")
    assert hs and min(hs) >= 44, hs
    _row(page, fx.F3['id'])
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    box = page.evaluate("() => { const r = document.querySelector('#epModal .mh button').getBoundingClientRect(); return [r.width, r.height]; }")
    assert box[0] >= 44 and box[1] >= 44, box


def test_hours_are_counted_the_arabic_way(open_page):
    page = open_page()
    got = page.evaluate("() => [0.5, 1.2, 2.5, 5.2, 10.9, 11, 41.5].map(h => EP.EF.efHours(h))")
    assert got == ['أقل من ساعة', 'ساعة', 'ساعتين', '٥ ساعات', '١٠ ساعات', '١١ ساعة', '٤١ ساعة']


# ---------------------------------------------------------------- الجولة ٧ (ج١–ج٥)

def test_unactivated_rows_say_why_and_refund_once_through_the_confirm_window(open_page, harness):
    """ج٢: «اتدفعت وما وصلتش» بقت صفوف بفعل «رجّع الفلوس» بنفس التأكيد — مرة واحدة حتى لو اتداس مرتين."""
    page = open_page()
    page.click('#filters .chip[data-f="attn"]')
    rows = page.inner_text('#rows')
    assert 'مش لاقيين الملف بتاع الفلوس دي' in rows and 'الملف لسه «مستني الدفع» مع إن الفلوس وصلت' in rows
    cid = fx.U1['consultation_id']
    _row(page, cid)
    drawer = page.inner_text('#drawer')
    assert fx.U1['title'] in drawer and 'مها' in drawer and 'محتاج تدخّلك' in drawer
    assert page.query_selector('#drawer [data-a="ef_pick"]') is None        # الفعل الوحيد «رجّع الفلوس»
    page.click('#drawer [data-a="ef_refund"]')
    page.wait_for_selector('#mc_go')
    body = page.inner_text('#epModal')
    assert '٥٠٠ ج' in body and 'محفظة مها' in body and 'جنيه مصري' in body
    assert page.inner_text('#mc_go') == 'رجّع ٥٠٠ ج'
    path = '/api/platform-expert-files/unactivated/%s/refund' % cid
    harness.hold.add(('POST', path))
    try:
        page.locator('#mc_go').dblclick()
        page.wait_for_timeout(300)
        assert page.is_disabled('#mc_go') and page.inner_text('#mc_go') == 'بيرجع…'
    finally:
        harness.hold.discard(('POST', path))
    assert sum(1 for c in harness.dash_calls if c == ('POST', path)) == 1
    harness.release_held()
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.wait_for_function("id => EP.state.inbox==='ready' && !INBOX.some(r => r.apiId === id)", arg=cid, timeout=15000)
    sent = [c for c in harness.ef.calls if c[0] == 'POST' and c[1].endswith('/unactivated/%s/refund' % cid)]
    assert len(sent) == 1 and sent[0][3] == {'note': '', 'by': 'admin@local.test'}


def test_needs_attention_badge_names_the_platform_reason_on_the_row_and_the_drawer(open_page):
    """ج٤: أختام التوقّف = شارة «محتاج تدخّلك» على الصفّ بسبب المنصة، وسطر لكل ختم في الدرج."""
    page = open_page()
    page.click('#filters .chip[data-f="attn"]')
    idx = page.evaluate("id => INBOX.findIndex(r => r.apiId === id)", fx.F6['id'])
    badge = page.locator('#rows .row[data-i="%d"] .ef-b' % idx).first
    assert badge.inner_text() == 'محتاج تدخّلك'
    assert badge.get_attribute('title') == fx.BLOCK_LABELS['release_blocked_at']
    row = page.inner_text('#rows .row[data-i="%d"]' % idx)
    assert fx.BLOCK_LABELS['release_blocked_at'] in row                  # السبب ظاهر على الصفّ مش في التلميح بس
    assert 'فلوسه واقفة' in row and row.count('محتاج تدخّلك') == 1        # مش نفس الكلمة مرتين
    _row(page, fx.F6['id'])
    drawer = page.inner_text('#drawer')
    assert fx.BLOCK_LABELS['release_blocked_at'] in drawer and 'رقم ١٠٣٧' in drawer
    assert 'مفيش زرار هنا يحوّلها للخبير لسه' in drawer
    assert page.query_selector('#drawer [data-a="ef_refund"]') is None   # بعد التسليم الرجوع مش من هنا
    _row(page, fx.F7['id'])                                              # قبل الاستلام: الرجوع موجود
    assert fx.BLOCK_LABELS['refund_blocked_at'] in page.inner_text('#drawer')
    assert page.query_selector('#drawer [data-a="ef_refund"]') is not None


def test_stuck_and_unactivated_counters_land_on_the_attention_chip(open_page):
    page = open_page()
    for key in ('expert_files_blocked', 'expert_files_unactivated'):
        page.click('.opsq[data-k="%s"]' % key)
        page.wait_for_timeout(200)
        assert page.evaluate("() => activeFilter") == 'attn', key
    assert sorted(page.evaluate("() => [...document.querySelectorAll('#rows .row')].map(r => INBOX[+r.dataset.i].apiId)")) == \
        sorted([fx.U2['consultation_id'], fx.F7['id'], fx.F6['id'], fx.U1['consultation_id']])


def test_regular_consultation_disputes_have_their_own_counter(open_page):
    """ج٣: نزاعات الاستشارات العادية ليها عدّاد (من غير نزاع الملف — ده ليه عدّاده)، وبيفتح «نزاعات»."""
    page = open_page()
    assert page.inner_text('.opsq[data-k="consultation_disputes"]').startswith('٢')
    page.click('.opsq[data-k="consultation_disputes"]')
    page.wait_for_timeout(200)
    assert page.evaluate("() => activeFilter") == 't:disputes'


def test_a_file_dispute_with_no_one_to_pay_cannot_be_released(open_page):
    """`release_amount` فاضي من المنصة (الفلوس لسه على بريدها) ⇒ «للخبير» مقفول بسبب، مش نافذة بمبلغ مخمّن."""
    ef = fx.EFPlatform()
    ef.disputed[0]['release_amount'] = None
    page = open_page(ef=ef)
    _row(page, fx.D1['id'])
    assert page.is_disabled('#drawer [data-a="dsp_rel"]')
    assert 'مفيش حد ياخد أجر' in page.inner_text('#drawer')


def test_file_dispute_drawer_reads_the_reason_and_number_from_the_platform(open_page):
    page = open_page()
    _row(page, fx.D1['id'])
    page.wait_for_selector('#drawer [data-a="dsp_cmp"]', timeout=15000)
    drawer = page.inner_text('#drawer')
    assert 'الرأي ما ردّش على سؤالي' in drawer and 'رقم ١٠٤٢' in drawer and '٣٠٠ ج لـد. ندى حسن' in drawer
    page.click('#drawer [data-a="dsp_rel"]')
    page.wait_for_selector('#mc_go')
    assert page.inner_text('#mc_go') == 'حوّل ٣٠٠ ج لـد. ندى حسن'


def test_every_write_reaches_the_platform_with_the_admins_email(open_page, harness):
    """ج١: كل فعل بيوصل المنصة ومعاه `by` = إيميل الأدمن اللي داخل (من الخادم، مش المتصفح)."""
    page = open_page()
    _row(page, fx.F4['id'])
    page.click('#drawer [data-a="ef_pick"]')
    page.wait_for_selector('#epModal .ef-cand')
    page.click('#epModal .ef-cand >> nth=0')
    page.click('#ep_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    page.wait_for_function("() => EP.state.inbox==='ready'", timeout=15000)
    _row(page, fx.D2['id'])
    page.click('#drawer [data-a="dsp_ref"]')
    page.wait_for_selector('#mc_go')
    page.click('#mc_go')
    page.wait_for_selector('#epModal', state='detached', timeout=15000)
    writes = [c for c in harness.ef.calls if c[0] == 'POST']
    assert len(writes) == 2 and all(c[3].get('by') == 'admin@local.test' for c in writes), writes
    page.evaluate("() => auditModal()")
    page.wait_for_selector('#auditRows .au-ef', timeout=15000)
    assert 'admin@local.test' in page.inner_text('#auditRows')


def test_zero_real_requests(harness):
    """آخر اختبار في الملف: كل اللي اتقفل في المتصفح خطوط جوجل بس، وجوه العملية ولا عنوان اتمنع."""
    assert harness.unexpected_blocked() == []
