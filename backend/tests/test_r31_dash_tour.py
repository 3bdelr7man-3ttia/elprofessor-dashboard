# -*- coding: utf-8 -*-
"""r31 — ملاحظات جولة المؤسس الحيّة على اللوحة (2026-11-17، شاشة ١٣٥٢×٧٠٠).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r31_dash_tour.py

اللي بيثبّته:
  ١. نافذة التأكيد («تُرسل الرأي إلى صاحب الطلب؟» · «رجّعه للخبير» · «رجّع الفلوس» · «اعكس الملف وارجع الفلوس» · «ابعته لـ…»)
     فوق أي درج مفتوح (درج «اقرأ وقرّر» · ورقة القائمة · درج اللوحة) — كانت بتتفتح وراه فنصّها متغطّي، وأول ضغطة على زرارها
     كانت بتقع على ستارة الدرج فتقفله بدل ما تنفّذ. والتنبيه القصير فوق النافذة والدرج.
  ٢. صفحة الشخص: «التقييم: ٥ من تقييم واحد» مع ملفاته كخبير (تحت ملخّص الملفات) — مش جوه «الدورات» بعد «لا دورات بعد» —
     ولغير الخبير ما يظهرش خالص.
  ٣. «اعكس الملف وارجع الفلوس» بعد النجاح: تنبيه قصير زي باقي أفعال الفلوس (بيدخل الجرس كمان)، والقوايم بتتجاب من جديد.

⛔ صفر شبكة: ملفات الواجهة نفسها + المنطق النقي في node.
"""
import copy
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ROOT = os.path.dirname(os.path.dirname(_HERE))
NOW = 1794916800000          # 2026-11-17T12:00:00Z
EM = 'expert@x.test'


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


def _z(css, selector):
    """أول `z-index` في قاعدة المحدِّد ده بالظبط."""
    m = re.search(re.escape(selector) + r'\{[^}]*?z-index:(\d+)', css)
    assert m, selector
    return int(m.group(1))


# ═══════════════════════════════════════════ ١) نافذة التأكيد فوق الأدراج
def test_confirm_dialog_sits_above_every_drawer_and_the_toast_above_it():
    idx = _read('dashboard-cloud', 'index.html')
    home = _read('dashboard-cloud', 'v2s', 'home.css')
    strip = _read('dashboard-cloud', 'v2-strip.css')
    shell = _read('dashboard-cloud', 'v2-shell.css')
    modal_v2 = _z(home, 'body:has(> .app.v2-shell) #epModal')
    modal_base = _z(idx, '.scrim')
    drawers = {'درج «اقرأ وقرّر»': _z(strip, '.v2rd'), 'ورقة القائمة': _z(shell, '.v2-sheet'),
               'درج اللوحة': _z(home, '  .app.v2-shell .v2h-dw'), 'جرس التنبيهات': _z(home, 'body:has(> .app.v2-shell) .v2h-bell')}
    for name, z in drawers.items():
        assert modal_v2 > z, (name, z, modal_v2)
        assert modal_base > z, (name, z, modal_base)
    toasts = _z(idx, '.toasts')
    assert toasts > modal_v2 and toasts > modal_base and toasts > max(drawers.values())


def test_confirm_buttons_stay_visible_on_a_short_screen():
    """١٣٥٢×٧٠٠: الأزرار كانت تحت حافة النافذة والضغطة على الجزء المخفي بتقفلها — دلوقتي ثابتة في آخرها (والموبايل زي ما هو)."""
    home = _read('dashboard-cloud', 'v2s', 'home.css')
    rule = re.search(r'body:has\(> \.app\.v2-shell\) #epModal \.modal \.mb>\.acts\{([^}]*)\}', home)
    assert rule and 'position:sticky' in rule.group(1) and 'bottom:0' in rule.group(1) and 'background:#fff' in rule.group(1)
    mob = home[home.index(rule.group(0)) + len(rule.group(0)):]
    assert re.search(r'@media\(max-width:760px\)\{\s*body:has\(> \.app\.v2-shell\) #epModal \.modal \.mb>\.acts\{position:static', mob)


def test_every_confirm_opened_from_the_file_drawer_uses_the_one_modal():
    """«اعتمده» و«رجّعه للخبير» و«رجّع الفلوس» و«ابعته لـ…» و«اعكس الملف» كلها بتفتح `openModal` (#epModal) — فرفع طبقتها بيحلّها كلها."""
    idx = _read('dashboard-cloud', 'index.html')
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    for fn in ('function efReviewApproveModal', 'function efReviewReturnModal', 'function efRefundModal', 'function efLegacyModal'):
        body = idx[idx.index(fn):]
        body = body[:body.index('\n}\n')]
        assert 'moneyConfirmModal(' in body, fn
    mcm = idx[idx.index('function moneyConfirmModal'):]
    assert mcm[:mcm.index('\n}\n')].count('openModal(') == 1
    pick = idx[idx.index('function expertPickModal'):]
    assert 'openModal(' in pick[:pick.index('\n}\n')]
    sheet = d3[d3.index('  function openSheet(title, html) {'):]
    assert 'window.openModal(' in sheet[:sheet.index('\n  }\n')]
    assert "s.id='epModal'" in idx


# ═══════════════════════════════════════════ ٢) تقييم الخبير مع ملفاته
def _resp(roles, courses_count=0, rating=(5, 1)):
    return {'email': EM, 'found': True, 'roles': roles,
            'sources': {k: 'ok' for k in ('users', 'invites', 'experts', 'courses', 'files', 'payouts_pending', 'payouts_paid', 'pending', 'enrollments')},
            'identity': {'name': 'أ. خبير', 'trainer_status': 'approved', 'is_active': True, 'joined_at': '2026-10-01T10:00:00Z',
                         'last_login_at': None, 'photo': None, 'country': None, 'invited_by': None},
            'expert': {'files_count': 2, 'partial': False, 'latest': []},
            'trainer': {'status': 'approved', 'courses_count': courses_count, 'students_count': 0, 'rating_avg': rating[0], 'rating_count': rating[1],
                        'courses': []},
            'money': None, 'learner': None, 'books': None, 'log': [], 'log_partial': False}


@needs_node
def test_expert_rating_sits_with_the_files_not_in_courses():
    vm = v2_node.logic('v2Person', _resp(['expert', 'trainer']), NOW, EM)
    files, courses = vm['cards'][0], vm['cards'][1]
    assert files['rating'] == 'التقييم: ٥ من تقييم واحد' and files['summary'] == 'ملفان'
    assert courses['summary'] == 'لا دورات بعد', courses
    assert 'التقييم' not in str(courses) and 'rating' not in courses
    # خبير بس (مش مدرّب) ولا تقييم له ⇒ ولا سطر
    vm = v2_node.logic('v2Person', _resp(['expert'], rating=(None, 0)), NOW, EM)
    assert 'rating' not in vm['cards'][0]


@needs_node
def test_no_rating_for_someone_who_is_not_an_expert():
    for roles in (['trainer'], ['trainer', 'learner'], ['member']):
        vm = v2_node.logic('v2Person', _resp(roles, courses_count=2), NOW, EM)
        assert all('rating' not in c for c in vm['cards']), roles
        assert 'التقييم' not in str(vm['cards']), roles
        assert vm['cards'][1]['summary'].startswith('دورتان')


@needs_node
def test_rating_still_shows_when_the_files_source_failed():
    resp = _resp(['expert'])
    resp['expert'] = None
    files = v2_node.logic('v2Person', resp, NOW, EM)['cards'][0]
    assert files['na'] is True and files['rating'] == 'التقييم: ٥ من تقييم واحد'


def test_person_card_draws_the_rating_under_the_files_summary():
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    pc = d2[d2.index('  function personCard(c) {'):]
    pc = pc[:pc.index('\n  }\n')]
    assert "c.rating ? '<p class=\"v2d-sum v2d-rate\">' + esc(c.rating)" in pc
    assert "esc(c.summary || '') + '</p>' + rate" in pc and "esc(c.text) + '</p>' + rate" in pc
    assert '.v2d-rate{' in _read('dashboard-cloud', 'v2-d2.css')
    logic = _read('dashboard-cloud', 'v2-logic.js')
    vp = logic[logic.index('  function v2Person('):]
    vp = vp[:vp.index('\n  }\n')]
    assert vp.count("'التقييم: '") == 1 and "c1.rating = 'التقييم: '" in vp and "indexOf('expert')" in vp


# ═══════════════════════════════════════════ ٣) بعد «اعكس الملف وارجع الفلوس»
def test_reverse_success_shows_a_short_toast_from_anywhere_and_lists_reload():
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    rv = d3[d3.index('  function openReverse(fileId, onDone) {'):]
    done = rv[rv.index('function done(res)'):]
    done = done[:done.index('\n          }\n')]
    assert '(window.notify || window.toast || function () {})(reverseToastText(p, res || {}))' in done
    assert 'D3.owns(' not in done, 'التنبيه بيظهر من أي مكان اتفتحت منه الورقة'
    assert 'refreshMoneyViews();' in done and 'onDone(res || {})' in done
    fn = d3[d3.index('  function reverseToastText(p, res) {'):]
    fn = fn[:fn.index('\n  }\n')]
    for s in ("'عُكس الملف'", "' رقم ' + U.ar(p.file_no)", "'، ويُعاد '", "' يدويًا'", "'، ولم يُخصم أجر الخبير'"):
        assert s in fn, s
    assert '·' not in fn and '✓' not in fn, 'علامة الصح أيقونة في التنبيه نفسه'
    idx = _read('dashboard-cloud', 'index.html')
    assert "V2D3.openReverse(f.id||i.apiId,()=>{EP.reload('opsQueue',efRefreshInbox);EP.reload('inbox',efRefreshInbox);})" in idx
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    assert "V2D3.openReverse(f.id, function () { refreshAll(function () { redraw(); }); })" in d2
    assert "var E = ep(), keys = ['opsQueue', 'inbox', 'walletPayouts']" in d2      # «أُغلقت مؤخرًا» بتيجي مع «inbox»
