# -*- coding: utf-8 -*-
"""r25 — الدورات المستنية والحيّة الواقفة بقت بطاقات قرار بزراير شغّالة في شريط «محتاج قرارك» (قسم الدورات).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r25_courses_strip.py

  ١. الطابور فيه `courses_pending.items` (معرّف كل دورة) ⇒ بطاقة قرار لكل دورة بـ«افتح وراجع» + «انشرها» + «أعِدها بملاحظات».
  ٢. دورة حيّة (`slug` موجود) ⇒ بطاقة بـ«ثبّتها» + «مدّد المهلة ٤٨ ساعة» + «ألغِها» + «افتحها».
  ٣. منصة أقدم (بلا `items` ولا `slug`) ⇒ الشكل القديم «للعلم» زي ما هو.
  ٤. ثابت الجمع: مجموع الشرائط = عدّاد «ابدأ القرارات» = مجموع المربعات.
  ٥. الأفعال بتتنفّذ فعلًا: النقر بيوصل لـ`V2CO.act` بنفس المعرّف، والورقة بتعمل نداء `/v2/courses/<id>/approve|reject` أو `/live/<slug>/decide`.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = 1793000000000
ROOT = os.path.dirname(os.path.dirname(_HERE))


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


Q = {'courses_pending': {'count': 2, 'titles': ['عقود', 'إثبات'],
                         'items': [{'id': 'c-1', 'slug': 'contracts', 'title': 'عقود', 'instructor_name': 'أ. منى', 'submitted_at': '2026-11-10T08:00:00+00:00'},
                                   {'id': 'c-2', 'slug': 'proof', 'title': 'إثبات', 'instructor_name': '', 'submitted_at': ''}]},
     'live_needs_decision': [{'slug': 'live-ip', 'title': 'ورشة الملكية', 'live_status': 'needs_decision', 'reserved_count': 2, 'quorum': 5}]}


def _split(queue):
    return v2_node.logic('v2Split', [], [], queue, {'now': NOW})


@needs_node
def test_pending_courses_and_live_become_decision_cards_with_real_buttons():
    out = _split(Q)
    cards = [c for c in out['decisions'] if c['home'] == 'courses']
    assert sorted(c['kind'] for c in cards) == ['course', 'course', 'live']
    c1 = next(c for c in cards if c['title'] == 'عقود')
    assert c1['bucket'] == 'decision' and c1['tag'] == 'دورة تنتظر الاعتماد'
    assert c1['primary'] == {'label': 'افتح وراجع', 'act': {'do': 'course_open', 'id': 'c-1'}}
    assert c1['secondary']['label'] == 'انشرها' and c1['secondary']['act'] == {'do': 'course_approve', 'id': 'c-1'}
    assert c1['edit']['label'] == 'أعِدها بملاحظات' and c1['edit']['act'] == {'do': 'course_return', 'id': 'c-1'}
    assert 'أ. منى' in c1['brain']
    lv = next(c for c in cards if c['kind'] == 'live')
    assert lv['primary']['act'] == {'do': 'live_decide', 'slug': 'live-ip', 'action': 'confirm'} and lv['primary']['label'] == 'ثبّتها'
    assert lv['secondary']['act']['action'] == 'extend' and lv['edit']['act']['action'] == 'cancel'
    assert lv['read']['act'] == {'do': 'course_open', 'slug': 'live-ip'}
    assert lv['sub'] == 'حجز ٢ من ٥'
    # مفيش «للعلم» مكرر لنفس البنود
    assert not [g for g in out['fyi']['groups'] if g['key'] in ('course', 'live')]


@needs_node
def test_older_platform_keeps_the_fyi_lines():
    out = _split({'courses_pending': {'count': 1, 'titles': ['دورة أ']}, 'live_needs_decision': [{'title': 'حيّة'}]})
    assert out['decisions'] == []
    assert {g['key'] for g in out['fyi']['groups']} == {'course', 'live'}


@needs_node
def test_strip_sum_equals_deck_count_with_the_new_cards():
    out = _split(Q)
    strip = v2_node.logic('v2Strip', out, 'courses')
    assert strip['n'] == 3 and strip['n'] == out['counts']['courses']
    assert sum(out['counts'][k] for k in out['counts'] if k != 'total') == out['counts']['total'] == len(out['decisions'])


def test_the_buttons_are_wired_to_the_course_sheets():
    home = _read('dashboard-cloud', 'v2-home.js')
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    for do in ('course_open', 'course_approve', 'course_return', 'live_decide'):
        assert "case '%s'" % do in home, do
    assert 'V2CO.act' in home and 'CO.act = function' in co
    # الأوراق الحقيقية هي اللي بتتفتح (نفس اللي في صفحة الدورة): نشر · إرجاع · قرار الحيّة
    assert 'openApprove(c.id' in co and 'openReturn(c.id)' in co and 'openLiveDecision(extra.slug || key, extra.action)' in co
    assert "'/v2/courses/' + encodeURIComponent(id) + '/approve'" in co and "'/reject'" in co and "/decide'" in co


# ───────────── سوق الخدمات: طلبات في حارة غلط ─────────────
def _mrow(**kw):
    base = {'id': 'm1', 'kind': 'public_service', 'need_kind': 'expert', 'status': 'open', 'title': 'محتاج محامي ضرائب', 'offer_count': 0,
            'created_at': '2026-11-12T08:00:00+00:00', 'visibility': 'public', 'author_kind': 'member'}
    base.update(kw)
    return base


@needs_node
def test_wrong_lane_requests_become_market_strip_cards_with_a_working_move_button():
    cards = v2_node.logic('v2sMarket.cards', [_mrow(), _mrow(id='m2', kind='request'), _mrow(id='m3', offer_count=2), _mrow(id='m4', hidden=True)], NOW)
    lane = [c for c in cards if c['primary']['act'] == 'relane']
    assert [c['id'] for c in lane] == ['m1'], 'الصح حارته مش بتتنقل · اللي عليه عروض مش بيتنقل · المخفي بره'
    out = v2_node.logic('v2Split', [], [], None, {'now': NOW, 'marketLane': lane})
    cs = [c for c in out['decisions'] if c['home'] == 'market']
    assert len(cs) == 1 and cs[0]['kind'] == 'market_lane' and cs[0]['bucket'] == 'decision'
    a = cs[0]['primary']['act']
    assert a['do'] == 'market_relane' and a['id'] == 'm1' and a['target'] == 'request' and cs[0]['primary']['label'].startswith('انقله إلى')
    assert cs[0]['read']['act'] == {'do': 'market_open', 'id': 'm1'}
    strip = v2_node.logic('v2Strip', out, 'market')
    assert strip['n'] == 1 == out['counts']['market'] == out['counts']['total']


def test_market_buttons_are_wired_to_the_relane_sheet_and_no_report_card_is_faked():
    home = _read('dashboard-cloud', 'v2-home.js')
    mk = _read('dashboard-cloud', 'v2s', 'market.js')
    assert "case 'market_relane'" in home and 'V2S_MARKET.act' in home
    assert 'M.act = function' in mk and 'openRelane(r, target' in mk
    # المنصة ما بتعرّضش بلاغات مستخدمين على طلبات السوق ⇒ ولا بطاقة «بلاغ» اتخترعت
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert 'market_report' not in logic
