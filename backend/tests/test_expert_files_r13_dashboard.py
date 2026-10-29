# -*- coding: utf-8 -*-
"""«ملف للخبير» الجولة ١٣ في الداشبورد — المستعجل وعرض سعر القضية فوق جسر المنصة (SPEC-R13 §٥ ·
docs/EXPERT-FILES-DASHBOARD-SPEC.md §١٩).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_r13_dashboard.py

⛔ المنصة متزيّفة بالكامل (نفس أداة `test_expert_files_dashboard.py`، بس `EFPlatform(r13=True)`): أي عنوان برّه
`https://platform.test` بيتسجّل ويوقع الاختبار. ولا رد على بوابة الدفع هنا: الرد دايمًا رصيد في محفظة العميل على المنصة.

اللي بيثبّته:
  ١. البروكسي الجديد `POST /api/platform-expert-files/<id>/case/milestones/<n>/resolve`: أدمن بس (الباقي ٤٠٣ من غير نداء)،
     تحقق محلي قبل أي نداء (معرّف · رقم المرحلة ١/٢ · الاتجاه · تأكيد الشاشة)، جسم النداء بالحرف (`action` + `note` + `by`)،
     نداء واحد ولا إعادة محاولة، السجل بعد النجاح بأرقام المرحلة، ورسايل المنصة بتعدّي زي ما هي.
  ٢. الفلاتر الجديدة (`urgent` · `case_disputed` · `case_open`) بتتبعت للمنصة، والقايمة بتعدّي بالحرف.
  ٣. التفاصيل بتشيل `speed` و`urgent` و`case` بمفاتيح معروفة بأنواعها بس — ولا بيانات العميل (إيميل · رقم دفع) بتعدّي معاهم.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uiharness'))
import ef_fixtures as fx  # noqa: E402
from test_expert_files_dashboard import (  # noqa: F401  (الأدوات والـfixtures المشتركة)
    ctx, Platform, _call, _audits, _fresh_audits, PLATFORM, SECRET, ADMIN, NON_ADMIN_ROLES, _Resp)

CS1, CS2, X1, X2, X3 = fx.CS1['id'], fx.CS2['id'], fx.X1['id'], fx.X2['id'], fx.X3['id']
RES = '/api/platform-expert-files/%s/case/milestones/%d/resolve'
BRIDGE_RES = '/api/bridge/expert-files/%s/case/milestones/%d/resolve'


class PlatformR13(Platform):
    def __init__(self):
        super().__init__()
        self.ef = fx.EFPlatform(r13=True)


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = PlatformR13()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


# ---------------------------------------------------------------- ١) الصلاحية والتحقق المحلي

@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_case_resolve_is_admin_only_and_never_reaches_the_platform(ctx, plat, role):
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True}, role=role)
    assert r.status_code == 403
    assert plat.seen == []


def test_case_resolve_without_a_token_is_401(ctx, plat):
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True}, role=None)
    assert r.status_code == 401 and plat.seen == []


@pytest.mark.parametrize('bad', ['a b', 'x' * 65, 'a.b', 'a%24b'])
def test_case_resolve_validates_the_file_id_first(ctx, plat, bad):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/case/milestones/1/resolve' % bad,
              {'action': 'release', 'confirmed': True})
    assert r.status_code == 404
    assert plat.seen == []


@pytest.mark.parametrize('n', ['0', '3', 'x', '01', '-1', '1.0'])
def test_case_resolve_only_knows_milestones_one_and_two(ctx, plat, n):
    r = _call(ctx, 'POST', '/api/platform-expert-files/%s/case/milestones/%s/resolve' % (CS1, n),
              {'action': 'release', 'confirmed': True})
    assert r.status_code == 404
    assert r.get_json() == {'error': 'المرحلة دي مش موجودة'}
    assert plat.seen == []


@pytest.mark.parametrize('action', [None, '', 'approve', 'RELEASE', 'void', 1, ['release']])
def test_case_resolve_validates_the_direction_locally(ctx, plat, action):
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': action, 'confirmed': True})
    assert r.status_code == 400
    assert r.get_json() == {'error': 'اختار: للخبير ولا للعميل'}
    assert plat.seen == []


@pytest.mark.parametrize('confirmed', [None, False, 'true', 1, 'yes'])
def test_case_resolve_needs_the_screen_confirmation(ctx, plat, confirmed):
    body = {'action': 'refund'}
    if confirmed is not None:
        body['confirmed'] = confirmed
    r = _call(ctx, 'POST', RES % (CS1, 1), body)
    assert r.status_code == 400
    assert r.get_json() == {'error': 'لازم تأكّد الأول من الشاشة'}
    assert plat.seen == []


# ---------------------------------------------------------------- ٢) الفعل نفسه

def test_release_forwards_exactly_action_note_and_the_admin_email(ctx, plat):
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True, 'note': 'الشغل اتسلّم فعلًا',
                                            'by': 'someone@else.test', 'amount': 1, 'expert_email': 'x@x.test'})
    assert r.status_code == 200, r.get_json()
    assert len(plat.seen) == 1                                       # نداء واحد
    call = plat.seen[0]
    assert call['method'] == 'POST' and call['url'] == PLATFORM + BRIDGE_RES % (CS1, 1)
    assert call['json'] == {'action': 'release', 'note': 'الشغل اتسلّم فعلًا', 'by': ADMIN}   # ⛔ ولا مبلغ ولا إيميل من المتصفح
    assert call['timeout'] >= 25
    assert call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert r.get_json() == {'ok': True, 'status': 'closed', 'milestone': {'n': 1, 'status': 'released'}}


def test_refund_goes_to_the_clients_wallet_and_says_refunded(ctx, plat):
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'refund', 'confirmed': True})
    assert r.status_code == 200, r.get_json()
    assert plat.seen[0]['json'] == {'action': 'refund', 'note': '', 'by': ADMIN}
    assert r.get_json()['milestone'] == {'n': 1, 'status': 'refunded'}
    # ⛔ مفيش أي نداء لبوابة دفع: كل اللي اتطلب مسار واحد على جسر المنصة.
    assert [c['url'] for c in plat.seen] == [PLATFORM + BRIDGE_RES % (CS1, 1)]


@pytest.mark.parametrize('action,status', [('release', 'released'), ('refund', 'refunded')])
def test_audit_records_the_milestone_numbers_not_the_files(ctx, plat, action, status):
    note = 'ملاحظة ' + action
    _call(ctx, 'POST', RES % (CS1, 1), {'action': action, 'confirmed': True, 'note': note})
    (actor, target, meta), = _audits('expert_file.case_resolve', CS1)
    assert actor == ADMIN and target == CS1
    assert meta['action'] == action and meta['note'] == note and meta['milestone'] == 1
    assert meta['milestone_label'] == 'الدفعة الأولى: بدء العمل' and meta['milestone_status'] == status
    # أرقام المرحلة (٧٥٠٠ ⇒ ٥٦٢٥ للخبير و١٨٧٥ للمنصة) مش أرقام الملف (٥٠٠ / ٣٠٠)
    assert (meta['amount'], meta['expert_amount'], meta['platform_fee']) == (7500, 5625, 1875)
    assert meta['milestone_consultation'] == 'cm-cs1-1'
    assert meta['title'] == fx.CS1['title']


def test_the_browser_reply_carries_ok_status_and_the_milestone_only(ctx, plat):
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True})
    raw = r.get_data(as_text=True)
    assert sorted(r.get_json()) == ['milestone', 'ok', 'status']
    for leak in ('client_email', 'payment', 'pay-', 'cm-cs1', '@clients.test', 'الخبير ما رفعش'):
        assert leak not in raw, leak


def test_second_click_reaches_the_platform_guard_once_more_and_is_audited_once(ctx, plat):
    _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True})
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True})
    assert r.status_code == 409
    assert r.get_json() == {'error': fx.E_CASE_NOT_DISPUTED}
    assert len(plat.seen) == 2
    assert len(_audits('expert_file.case_resolve', CS1)) == 1


def test_the_milestone_that_is_not_disputed_is_refused_by_the_platform_in_its_words(ctx, plat):
    r = _call(ctx, 'POST', RES % (CS1, 2), {'action': 'refund', 'confirmed': True})      # المرحلة ٢ لسه ما اتفتحتش
    assert r.status_code == 409 and r.get_json() == {'error': fx.E_CASE_NOT_DISPUTED}
    assert _audits('expert_file.case_resolve') == []


@pytest.mark.parametrize('status,detail', [
    (409, 'العميل خد فلوس المرحلة دي قبل كده، فمفيش تحويل للخبير من هنا'),
    (409, 'الملف اتغيّر — حدّث الصفحة'), (404, 'الملف ده مش موجود'), (422, 'اختار: للخبير ولا للعميل')])
def test_platform_refusals_pass_verbatim_and_are_not_audited(ctx, plat, status, detail):
    plat.forced[('POST', BRIDGE_RES % (CS1, 1))] = (status, {'detail': detail})
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True})
    assert r.status_code == status and r.get_json() == {'error': detail}
    assert _audits('expert_file.case_resolve') == []


@pytest.mark.parametrize('forced', [(502, {'detail': 'bad gateway'}), (503, {'detail': 'x'}), (500, {}),
                                    ConnectionError('boom')])
def test_a_lost_reply_is_said_logged_and_never_retried(ctx, plat, forced):
    plat.forced[('POST', BRIDGE_RES % (CS1, 1))] = forced
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'refund', 'confirmed': True})
    assert r.status_code == 502
    assert r.get_json()['no_reply'] is True and 'ما وصلناش رد' in r.get_json()['error']
    assert len(plat.seen) == 1                                       # ولا إعادة محاولة
    (_a, _t, meta), = _audits('expert_file.no_reply', CS1)
    assert meta == {'attempt': 'case_resolve', 'action': 'refund'}
    assert _audits('expert_file.case_resolve') == []


def test_bridge_not_published_yet_says_so_in_arabic(ctx, plat):
    plat.ef.deployed = False
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True})
    assert r.status_code == 404
    assert r.get_json() == {'error': 'ملفات «ملف للخبير» مش واصلة للداشبورد لسه'}


def test_without_the_secret_nothing_is_sent(ctx, plat, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    r = _call(ctx, 'POST', RES % (CS1, 1), {'action': 'release', 'confirmed': True})
    assert r.status_code == 503 and plat.seen == []


# ---------------------------------------------------------------- ٣) القوايم والفلاتر

@pytest.mark.parametrize('s_', ['urgent', 'case_disputed', 'case_open'])
def test_the_new_list_filters_are_forwarded(ctx, plat, s_):
    r = _call(ctx, 'GET', '/api/platform-expert-files?status=' + s_)
    assert r.status_code == 200
    assert plat.seen[-1]['params'] == {'status': s_}
    assert r.get_json()['status'] == s_ and r.get_json()['enabled'] is True


def test_case_disputed_list_is_verbatim_plus_enabled(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=case_disputed').get_json()
    assert body.pop('enabled') is True
    assert body == fx.list_payload('case_disputed', [fx.CS1])


def test_urgent_list_has_the_urgent_files_with_their_speed(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=urgent').get_json()
    assert sorted(f['id'] for f in body['files']) == sorted([X1, X3])
    assert all(f['speed'] == 'urgent' for f in body['files'])


def test_case_open_holds_the_quote_sent_and_the_unfinished_milestones(ctx, plat):
    body = _call(ctx, 'GET', '/api/platform-expert-files?status=case_open').get_json()
    assert sorted(f['id'] for f in body['files']) == sorted([CS1, CS2])


def test_a_platform_before_round_13_refuses_the_new_filter_in_its_own_words(ctx, plat):
    plat.forced[('GET', '/api/bridge/expert-files')] = (422, {'detail': [{'loc': ['query', 'status'], 'msg': 'bad'}]})
    r = _call(ctx, 'GET', '/api/platform-expert-files?status=case_disputed')
    assert r.status_code == 422                                      # الواجهة بتسكت عن ٤٢٢ للحارة دي (مش عطل)


def test_an_unknown_filter_still_falls_back_to_waiting(ctx, plat):
    _call(ctx, 'GET', '/api/platform-expert-files?status=case_everything')
    assert plat.seen[-1]['params'] == {'status': 'waiting'}


# ---------------------------------------------------------------- ٤) التفاصيل

def _detail(ctx, fid):
    r = _call(ctx, 'GET', '/api/platform-expert-files/' + fid)
    assert r.status_code == 200, r.get_json()
    return r.get_json(), r.get_data(as_text=True)


def test_an_urgent_file_detail_carries_speed_and_the_urgent_card(ctx, plat):
    body, _raw = _detail(ctx, X1)
    assert body['speed'] == 'urgent' and body['case'] is None
    assert sorted(body['urgent']) == ['due_at', 'fell_back_at', 'refunded', 'start_by', 'started_at', 'state']
    assert body['urgent']['state'] == 'waiting' and body['urgent']['refunded'] is None
    assert body['urgent']['start_by'] == fx.X1['urgent']['start_by'] and body['urgent']['due_at'] == fx.X1['urgent']['due_at']


def test_a_fallen_back_file_says_what_was_refunded(ctx, plat):
    body, _raw = _detail(ctx, X2)
    assert body['speed'] == 'normal'
    assert body['urgent']['state'] == 'fell_back' and body['urgent']['refunded'] == 300
    assert body['urgent']['fell_back_at'] == fx.X2['urgent']['fell_back_at']


def test_a_case_detail_carries_the_quote_and_every_milestone_with_the_split(ctx, plat):
    body, _raw = _detail(ctx, CS1)
    case = body['case']
    assert sorted(case) == ['milestones', 'quote', 'quotes']
    q = case['quote']
    assert (q['fee'], q['plan'], q['status'], q['second_label']) == (15000, 'two', 'accepted', 'عند رفع الدعوى')
    assert q['includes'] and q['excludes'] and q['duration'] == '٦ أشهر تقريبًا' and q['question'] is None
    m1, m2 = case['milestones']
    assert (m1['n'], m1['status'], m1['amount'], m1['expert_amount'], m1['platform_fee']) == (1, 'disputed', 7500, 5625, 1875)
    assert m1['problem'] == 'الخبير ما رفعش الدعوى زي ما اتفقنا، والتاريخ اتأخر.'
    assert m1['done_note'] and m1['consultation_id'] == 'cm-cs1-1' and m1['auto'] is False
    assert (m2['n'], m2['status'], m2['amount']) == (2, 'due', 7500)
    assert m2['consultation_id'] is None and m2['problem'] is None


def test_a_sent_quote_carries_the_clients_question_and_the_waiting_reply(ctx, plat):
    body, _raw = _detail(ctx, CS2)
    q = body['case']['quote']
    assert q['status'] == 'sent' and q['plan'] == 'one'
    assert q['question']['text'] == 'هل الأتعاب بتشمل الخبير الهندسي؟' and q['question']['answer'] is None


def test_the_case_keeps_known_keys_only_and_drops_client_data(ctx, plat):
    row = plat.ef.case_files[0]
    row['client_email'] = 'leak@clients.test'
    row['case']['payment_id'] = 'pay-secret'
    row['case']['quote']['client_phone'] = '+201000000000'
    row['case']['quote']['question'] = {'text': 'سؤال', 'asked_at': None, 'answer': None, 'answered_at': None,
                                        'asked_by': 'leak@clients.test'}
    row['case']['milestones'][0]['payment_id'] = 'pay-secret'
    row['case']['milestones'][0]['client_email'] = 'leak@clients.test'
    body, raw = _detail(ctx, CS1)
    for leak in ('leak@clients.test', 'pay-secret', '+201000000000', 'client_phone', 'payment_id'):
        assert leak not in raw, leak
    assert sorted(body['case']['milestones'][0]) == [
        'amount', 'auto', 'auto_release_at', 'confirmed_at', 'consultation_id', 'disputed_at', 'done_at', 'done_note',
        'expert_amount', 'label', 'n', 'paid_at', 'platform_fee', 'problem', 'released_at', 'status']
    assert sorted(body['case']['quote']) == [
        'accepted_at', 'currency', 'duration', 'excludes', 'fee', 'includes', 'n', 'plan', 'question', 'rejected_at',
        'second_label', 'sent_at', 'status']
    assert sorted(body['case']['quote']['question']) == ['answer', 'answered_at', 'asked_at', 'text']


@pytest.mark.parametrize('case', ['x', 5, [], {'milestones': 'x', 'quote': 'x', 'quotes': 3},
                                  {'milestones': [None, 4, 'a'], 'quote': None, 'quotes': [None]}])
def test_a_malformed_case_never_reaches_the_browser_as_is(ctx, plat, case):
    plat.ef.case_files[0]['case'] = case
    body, _raw = _detail(ctx, CS1)
    if isinstance(case, dict):
        assert body['case'] == {'quote': None, 'quotes': [], 'milestones': []}
    else:
        assert body['case'] is None


def test_unknown_statuses_and_wrong_types_are_dropped_not_passed_on(ctx, plat):
    c = plat.ef.case_files[0]['case']
    c['quote']['status'] = 'hacked'
    c['quote']['plan'] = 'three'
    c['quote']['fee'] = '15000'                                     # نص مش رقم
    c['milestones'][0]['status'] = '<script>'
    c['milestones'][0]['amount'] = True                             # bool مش رقم
    body, _raw = _detail(ctx, CS1)
    q, m1 = body['case']['quote'], body['case']['milestones'][0]
    assert q['status'] is None and q['plan'] is None and q['fee'] is None
    assert m1['status'] is None and m1['amount'] is None


def test_a_bogus_urgent_state_or_speed_is_neutralised(ctx, plat):
    plat.ef.waiting[0]['speed'] = 'turbo'
    plat.ef.waiting[0]['urgent'] = {'state': 'on_fire', 'refunded': 'x', 'start_by': 5, 'client_email': 'leak@x.test'}
    body, raw = _detail(ctx, plat.ef.waiting[0]['id'])
    assert body['speed'] == 'normal'
    assert body['urgent'] == {'start_by': None, 'due_at': None, 'state': None, 'refunded': None,
                              'fell_back_at': None, 'started_at': None}
    assert 'leak@x.test' not in raw


def test_the_old_round_files_keep_their_detail_shape_with_normal_speed(ctx, plat):
    body, _raw = _detail(ctx, fx.F1['id'])
    assert body['speed'] == 'normal' and body['urgent'] is None and body['case'] is None


def test_the_urgent_deadline_field_is_a_different_thing_and_is_not_touched(ctx, plat):
    """`urgent_deadline` = ميعاد جلسة المحكمة بتاع العميل — مش من مفاتيح التفاصيل ولا بيتحوّل لـ`speed`."""
    plat.ef.waiting[0]['urgent_deadline'] = '2026-11-02'
    body, _raw = _detail(ctx, plat.ef.waiting[0]['id'])
    assert 'urgent_deadline' not in body and body['speed'] == 'normal'
