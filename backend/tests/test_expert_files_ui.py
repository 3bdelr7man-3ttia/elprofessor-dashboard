# -*- coding: utf-8 -*-
"""«ملف للخبير» في المتصفح — السلوك نفسه (الجولة ٦ · SPEC §١٠-ج).

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

    def _open(role='admin', ef=None, hash_='#inbox', wait_ready=True):
        harness.ef = ef or fx.EFPlatform()
        try:
            br = pw.chromium.launch(args=['--single-process'])
        except Exception as exc:              # متصفح مش متنزّل
            pytest.skip('chromium غير متاح لـplaywright: %s' % exc)
        browsers.append(br)
        ctx = harness.context(br, role, {'width': 1440, 'height': 900})
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
    for label in ('ملف مستني خبير', 'خبير اعتذر — الملف مستني خبير تاني', 'ملف ما اتستلمش من ١٢ ساعة', 'رأي متأخر'):
        assert label in texts, label
    assert '⚠️ البلد مختلف' in texts and '⚠️ الرقم مش واضح' in texts and '⏳ فاضل أقل من ١٢ ساعة' in texts
    page.click('#filters .chip[data-f="t:disputes"]')
    d = page.inner_text('#rows')
    assert d.count(fx.D1['title']) == 1                           # D1′ من قايمة الاستشارات ما اتكررش
    assert fx.D2['title'] in d and fx.D3['title'] in d
    chips = page.inner_text('#filters')
    assert 'ملفات للخبير (٥)' in chips and 'نزاعات (٣)' in chips


def test_queue_chips_use_the_platform_numbers_and_land_on_their_chip(open_page):
    page = open_page()
    panel = page.inner_text('section.panel >> nth=0')
    for label in ('ملفات مستنية خبير', 'آراء متأخرة', 'ملفات فيها «عندي مشكلة»', 'ملفات اتدفعت وما وصلتش للتوزيع',
                  'للعلم:', '📁 4 ملف مستني خبير'):
        assert label in panel, label
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
    assert 'EGP' in body
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
    assert refunds[0][3] == {'note': ''}                           # المنصة خدت الملاحظة بس
    assert 'ملفات للخبير (٤)' in page.inner_text('#filters')        # الصفّ اختفى والشريحة قلّت


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


def test_feature_off_is_quiet_and_the_alert_is_printed(open_page):
    page = open_page(ef=fx.EFPlatform(enabled=False, cons_enabled=False, off_open_total=2))
    assert page.evaluate("() => (window.INBOX_FAILED||[]).length") == 0
    assert page.evaluate("() => INBOX.filter(r => r.apiKind==='expert_file' || r.apiKind==='dispute').length") == 0
    assert '2 ملف مدفوع والميزة مقفولة' in page.inner_text('section.panel >> nth=0')


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


def test_zero_real_requests(harness):
    """آخر اختبار في الملف: كل اللي اتقفل في المتصفح خطوط جوجل بس، وجوه العملية ولا عنوان اتمنع."""
    assert harness.unexpected_blocked() == []
