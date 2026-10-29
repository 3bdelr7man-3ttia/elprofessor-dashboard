# -*- coding: utf-8 -*-
"""«ملف للخبير» الجولة ١٤ في الداشبورد — مراجعة العقود + التخصص + التوزيع التلقائي فوق جسر المنصة
(SPEC-R14-CONTRACT-ASSIGN §٤).

Run:  cd backend && python3 -m pytest -q tests/test_expert_files_r14_dashboard.py

⛔ المنصة متزيّفة بالكامل (`EFPlatform(r14=True)` من `uiharness/ef_fixtures.py`): أي عنوان برّه `https://platform.test`
بيتسجّل ويوقع الاختبار. الجسر الجديد بيتبني على المنصة بالتوازي، فالداشبورد بيقرا حقوله بحذر (مفاتيح معروفة بأنواعها بس).

اللي بيثبّته:
  ١. البروكسي `GET/PUT /api/platform-expert-files/settings` (مفتاح التوزيع التلقائي): أدمن بس (الباقي ٤٠٣ من غير نداء)،
     القفل بتأكيد الشاشة، `by` من التوكن، نداء واحد ولا إعادة محاولة، السجل بعد النجاح، ورسايل المنصة بتعدّي زي ما هي.
  ٢. القوايم بتعدّي بالحرف بالحقول الجديدة (`assign_log` · `declined[].reason_code` · المرشّحين بترتيب المنصة).
  ٣. التفاصيل بتشيل النوع وصفحات العقد والتخصص ووثيقة العقد (الحكم والبنود) بمفاتيح معروفة بأنواعها بس.
  ٤. الملفات القديمة (من غير الحقول دي) بتتصرف زي ما كانت بالحرف.
"""
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uiharness'))
import ef_fixtures as fx  # noqa: E402
from test_expert_files_dashboard import (  # noqa: F401  (الأدوات والـfixtures المشتركة)
    ctx, Platform, _audits, _fresh_audits, PLATFORM, SECRET, ADMIN, NON_ADMIN_ROLES)

K1, K2, K3, KR = fx.K1['id'], fx.K2['id'], fx.K3['id'], fx.KR['id']
SETTINGS = '/api/platform-expert-files/settings'
BRIDGE_SETTINGS = '/api/bridge/expert-files/settings'


class PlatformR14(Platform):
    def __init__(self):
        super().__init__()
        self.ef = fx.EFPlatform(r8=True, r14=True)


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = PlatformR14()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _req(ctx, method, path, body=None, role='admin'):
    c = ctx['client']
    h = ctx['heads'][role] if role else {}
    if method == 'GET':
        return c.get(path, headers=h)
    return c.open(path, method=method, headers=h, json=body if body is not None else {})


def _detail(ctx, fid):
    r = _req(ctx, 'GET', '/api/platform-expert-files/' + fid)
    assert r.status_code == 200, r.get_json()
    return r.get_json(), r.get_data(as_text=True)


# ---------------------------------------------------------------- ١) مفتاح التوزيع التلقائي: الصلاحية

@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
@pytest.mark.parametrize('method', ['GET', 'PUT'])
def test_settings_is_admin_only_and_never_reaches_the_platform(ctx, plat, role, method):
    r = _req(ctx, method, SETTINGS, {'auto_assign': True}, role=role)
    assert r.status_code == 403
    assert plat.seen == []


@pytest.mark.parametrize('method', ['GET', 'PUT'])
def test_settings_without_a_token_is_401(ctx, plat, method):
    r = _req(ctx, method, SETTINGS, {'auto_assign': True}, role=None)
    assert r.status_code == 401 and plat.seen == []


def test_settings_is_not_mistaken_for_a_file_id(ctx, plat):
    """`/settings` مسار ثابت: مش ملف اسمه settings (القراية بتروح لجسر الإعداد مش جسر الملف)."""
    _req(ctx, 'GET', SETTINGS)
    assert [c['url'] for c in plat.seen] == [PLATFORM + BRIDGE_SETTINGS]


# ---------------------------------------------------------------- ٢) القراية

def test_read_returns_enabled_and_the_flag(ctx, plat):
    r = _req(ctx, 'GET', SETTINGS)
    assert r.status_code == 200 and r.get_json() == {'enabled': True, 'auto_assign': True}
    call = plat.seen[0]
    assert call['method'] == 'GET' and call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    plat.ef.auto_assign = False
    assert _req(ctx, 'GET', SETTINGS).get_json() == {'enabled': True, 'auto_assign': False}


@pytest.mark.parametrize('weird', ['true', 1, None, [], {'x': 1}])
def test_a_non_boolean_flag_is_unknown_not_guessed(ctx, plat, weird):
    plat.forced[('GET', BRIDGE_SETTINGS)] = (200, {'auto_assign': weird})
    assert _req(ctx, 'GET', SETTINGS).get_json() == {'enabled': True, 'auto_assign': None}


def test_a_platform_before_round_14_is_not_a_failure(ctx, plat):
    plat.ef.settings_enabled = False
    r = _req(ctx, 'GET', SETTINGS)
    assert r.status_code == 200 and r.get_json() == {'enabled': False, 'auto_assign': None}


def test_read_errors_pass_on_in_arabic(ctx, plat):
    plat.forced[('GET', BRIDGE_SETTINGS)] = (500, {'detail': 'Database not available'})
    r = _req(ctx, 'GET', SETTINGS)
    assert r.status_code == 500 and r.get_json() == {'error': 'المنصة مش متاحة دلوقتي — جرّب بعد شوية'}


# ---------------------------------------------------------------- ٣) الكتابة: التحقق المحلي

@pytest.mark.parametrize('bad', [None, 'true', 'false', 1, 0, [], {}])
def test_put_needs_a_real_boolean(ctx, plat, bad):
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': bad, 'confirmed': True})
    assert r.status_code == 400
    assert r.get_json() == {'error': 'اختار: التوزيع التلقائي شغّال ولا مقفول'}
    assert plat.seen == []


@pytest.mark.parametrize('confirmed', [None, False, 'true', 1, 'yes'])
def test_closing_it_needs_the_screen_confirmation(ctx, plat, confirmed):
    body = {'auto_assign': False}
    if confirmed is not None:
        body['confirmed'] = confirmed
    r = _req(ctx, 'PUT', SETTINGS, body)
    assert r.status_code == 400 and r.get_json() == {'error': 'لازم تأكّد الأول من الشاشة'}
    assert plat.seen == [] and plat.ef.auto_assign is True


def test_opening_it_needs_no_confirmation(ctx, plat):
    plat.ef.auto_assign = False
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': True})
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'auto_assign': True}
    assert plat.ef.auto_assign is True


# ---------------------------------------------------------------- ٤) الكتابة: الفعل نفسه

def test_close_forwards_exactly_the_flag_and_the_admin_email(ctx, plat):
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': False, 'confirmed': True, 'by': 'someone@else.test',
                                    'expert_email': 'x@x.test'})
    assert r.status_code == 200, r.get_json()
    assert len(plat.seen) == 1                                          # نداء واحد
    call = plat.seen[0]
    assert call['method'] == 'PUT' and call['url'] == PLATFORM + BRIDGE_SETTINGS
    assert call['json'] == {'auto_assign': False, 'by': ADMIN}          # ⛔ ولا حاجة تانية من المتصفح
    assert call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert r.get_json() == {'ok': True, 'auto_assign': False}
    assert plat.ef.auto_assign is False


def test_the_reply_uses_what_the_platform_says_not_what_was_asked(ctx, plat):
    plat.forced[('PUT', BRIDGE_SETTINGS)] = (200, {'auto_assign': True})
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': False, 'confirmed': True})
    assert r.get_json() == {'ok': True, 'auto_assign': True}


def test_audit_records_the_new_value_once(ctx, plat):
    _req(ctx, 'PUT', SETTINGS, {'auto_assign': False, 'confirmed': True})
    _req(ctx, 'PUT', SETTINGS, {'auto_assign': True})
    rows = _audits('expert_file.auto_assign', 'settings')
    assert [(a, m) for a, _t, m in rows] == [(ADMIN, {'auto_assign': False}), (ADMIN, {'auto_assign': True})]


@pytest.mark.parametrize('status,detail', [(409, 'الإعداد اتغيّر — حدّث الصفحة'), (422, 'قيمة غلط'),
                                           (403, 'مش مسموح')])
def test_platform_refusals_pass_verbatim_and_are_not_audited(ctx, plat, status, detail):
    plat.forced[('PUT', BRIDGE_SETTINGS)] = (status, {'detail': detail})
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': False, 'confirmed': True})
    assert r.status_code == status and r.get_json() == {'error': detail}
    assert _audits('expert_file.auto_assign') == []


@pytest.mark.parametrize('forced', [(502, {'detail': 'bad gateway'}), (503, {'detail': 'x'}), (500, {}),
                                    ConnectionError('boom')])
def test_a_lost_reply_is_said_logged_and_never_retried(ctx, plat, forced):
    plat.forced[('PUT', BRIDGE_SETTINGS)] = forced
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': False, 'confirmed': True})
    assert r.status_code == 502
    assert r.get_json()['no_reply'] is True and 'ما وصلناش رد' in r.get_json()['error']
    assert len(plat.seen) == 1                                          # ولا إعادة محاولة
    (_a, _t, meta), = _audits('expert_file.no_reply', 'settings')
    assert meta == {'attempt': 'auto_assign', 'action': 'off'}
    assert _audits('expert_file.auto_assign') == []


def test_bridge_not_published_yet_says_so_in_arabic(ctx, plat):
    plat.ef.settings_enabled = False
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': True})
    assert r.status_code == 404
    assert r.get_json() == {'error': 'ملفات «ملف للخبير» مش واصلة للداشبورد لسه'}


def test_without_the_secret_nothing_is_sent(ctx, plat, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    r = _req(ctx, 'PUT', SETTINGS, {'auto_assign': True})
    assert r.status_code == 503 and plat.seen == []


# ---------------------------------------------------------------- ٥) القوايم: الحقول الجديدة بالحرف

def _list(ctx, status):
    r = _req(ctx, 'GET', '/api/platform-expert-files?status=' + status)
    assert r.status_code == 200
    return r.get_json()


def test_waiting_list_carries_the_round_14_fields_verbatim(ctx, plat):
    rows = {f['id']: f for f in _list(ctx, 'waiting')['files']}
    assert {K1, K2, K3} <= set(rows)
    k2 = rows[K2]
    assert k2['assign_log'] == fx.K2['assign_log'] and [e['by'] for e in k2['assign_log']] == ['auto', 'auto']
    assert [e['reason'] for e in k2['assign_log']] == ['paid', 'declined']
    assert k2['declined'][0]['reason_code'] == 'not_my_field'
    assert rows[K3]['no_candidate_alerted_at'] == fx.K3['no_candidate_alerted_at']
    assert rows[K3]['candidates'] == []
    assert (rows[K1]['kind'], rows[K1]['contract_pages'], rows[K1]['specialty']) == ('contract', 8, 'real_estate')


def test_candidates_keep_the_platforms_order_and_carry_specialties(ctx, plat):
    k1 = next(f for f in _list(ctx, 'waiting')['files'] if f['id'] == K1)
    assert [c['email'] for c in k1['candidates']] == ['hala@experts.test', 'nada@experts.test', 'karim@experts.test']
    hala, nada, karim = k1['candidates']
    assert hala['reviews_contracts'] is True and hala['specialties'] == ['real_estate', 'civil']
    assert nada['specialty_other'] == 'عقود التأمين' and nada['reviews_contracts'] is False
    assert karim['available'] is False and hala['available'] is True


def test_a_contract_file_is_in_the_review_lane(ctx, plat):
    rows = _list(ctx, 'review')['files']
    assert KR in [f['id'] for f in rows]


def test_old_rows_have_no_round_14_keys_and_come_through_unchanged(ctx, plat):
    f1 = next(f for f in _list(ctx, 'waiting')['files'] if f['id'] == fx.F1['id'])
    assert f1 == fx.F1                                                  # ملف قديم بالحرف
    for key in ('kind', 'assign_log', 'specialty', 'no_candidate_alerted_at'):
        assert key not in f1


# ---------------------------------------------------------------- ٦) التفاصيل: النوع والتخصص ووثيقة العقد

def test_a_contract_review_detail_carries_kind_pages_name_specialty_and_the_document(ctx, plat):
    body, _raw = _detail(ctx, KR)
    assert (body['kind'], body['contract_pages'], body['contract_name']) == ('contract', 6, 'عقد توريد الأثاث.pdf')
    assert (body['specialty'], body['specialty_other']) == ('civil', None)
    c = body['contract']
    assert sorted(c) == ['clauses', 'todo', 'verdict']
    assert c['verdict'] == 'sign_after_changes'
    assert [x['risk'] for x in c['clauses']] == ['low', 'high', 'medium']        # ترتيب المنصة — الدرج هو اللي بيرتّبها
    high = c['clauses'][1]
    assert sorted(high) == ['answers', 'ref', 'risk', 'suggestion', 'why']
    assert high['ref'] == 'البند ٥: الغرامة' and high['answers'] == [1]
    assert high['suggestion'].startswith('تُحتسب غرامة التأخير')
    assert c['clauses'][0]['suggestion'] is None and c['clauses'][0]['answers'] == []
    assert c['todo'] == fx.KR_OPINION['todo']


def test_the_contract_keeps_known_keys_only_and_drops_client_data(ctx, plat):
    row = plat.ef.review[-1]
    assert row['id'] == KR
    row['pending_opinion']['clauses'][0]['client_email'] = 'leak@clients.test'
    row['pending_opinion']['clauses'][0]['payment_id'] = 'pay-secret'
    row['pending_opinion']['internal_note'] = 'ملاحظة داخلية'
    row['pending_opinion']['todo'] = ['خطوة', {'phone': '+201000000000'}, 5]
    body, raw = _detail(ctx, KR)
    for leak in ('leak@clients.test', 'pay-secret', '+201000000000'):
        assert leak not in body['contract'].__repr__(), leak
    assert body['contract']['todo'] == ['خطوة']
    assert sorted(body['contract']['clauses'][0]) == ['answers', 'ref', 'risk', 'suggestion', 'why']


@pytest.mark.parametrize('verdict', [None, '', 'sign', 'DONT_SIGN', 5, ['sign_ok']])
def test_a_bogus_verdict_means_no_document(ctx, plat, verdict):
    plat.ef.review[-1]['pending_opinion']['verdict'] = verdict
    body, _raw = _detail(ctx, KR)
    assert body['contract'] is None


def test_wrong_types_in_clauses_are_dropped_not_passed_on(ctx, plat):
    po = plat.ef.review[-1]['pending_opinion']
    po['clauses'] = [None, 4, 'x', {'ref': ['a'], 'why': 5}, {'ref': 'البند ١', 'risk': 'critical', 'why': 'سبب',
                                                              'suggestion': 9, 'answers': ['a', True, -1, 2, 3.0]}]
    body, _raw = _detail(ctx, KR)
    (only,) = body['contract']['clauses']
    assert only == {'ref': 'البند ١', 'risk': None, 'why': 'سبب', 'suggestion': None, 'answers': [2, 3]}


def test_clauses_are_capped_at_fifteen_and_texts_are_trimmed(ctx, plat):
    po = plat.ef.review[-1]['pending_opinion']
    po['clauses'] = [{'ref': 'بند %d' % k, 'risk': 'low', 'why': 'س' * 2000, 'suggestion': 'ص' * 3000, 'answers': []}
                     for k in range(40)]
    c = _detail(ctx, KR)[0]['contract']
    assert len(c['clauses']) == 15
    assert len(c['clauses'][0]['why']) == 800 and len(c['clauses'][0]['suggestion']) == 1200


def test_a_sign_ok_verdict_may_have_no_clauses(ctx, plat):
    po = plat.ef.review[-1]['pending_opinion']
    po.update({'verdict': 'sign_ok', 'clauses': [], 'todo': []})
    c = _detail(ctx, KR)[0]['contract']
    assert c == {'verdict': 'sign_ok', 'clauses': [], 'todo': []}


@pytest.mark.parametrize('key', ['items', 'points'])
def test_the_clause_list_name_is_read_from_the_known_aliases(ctx, plat, key):
    po = plat.ef.review[-1]['pending_opinion']
    po[key] = po.pop('clauses')
    c = _detail(ctx, KR)[0]['contract']
    assert len(c['clauses']) == 3


def test_the_document_may_be_nested_under_contract(ctx, plat):
    po = plat.ef.review[-1]['pending_opinion']
    nested = {'verdict': po.pop('verdict'), 'clauses': po.pop('clauses'), 'todo': po.pop('todo')}
    po['contract'] = nested
    c = _detail(ctx, KR)[0]['contract']
    assert c['verdict'] == 'sign_after_changes' and len(c['clauses']) == 3


def test_the_approved_opinion_is_a_fallback_source(ctx, plat):
    full = plat.ef._detail(plat.ef.review[-1])
    full['opinion'] = {'verdict': 'dont_sign', 'clauses': [{'ref': 'البند ١', 'risk': 'high', 'why': 'سبب كافي'}],
                       'todo': []}
    full['pending_opinion'] = None
    plat.forced[('GET', '/api/bridge/expert-files/' + KR)] = (200, full)
    assert _detail(ctx, KR)[0]['contract']['verdict'] == 'dont_sign'


def test_specialty_other_carries_its_text_only_for_other(ctx, plat):
    row = plat.ef.waiting[0]
    row['specialty'], row['specialty_other'] = 'other', '  قانون بحري  '
    body, _raw = _detail(ctx, row['id'])
    assert (body['specialty'], body['specialty_other']) == ('other', 'قانون بحري')
    row['specialty'] = 'civil'
    body, _raw = _detail(ctx, row['id'])
    assert (body['specialty'], body['specialty_other']) == ('civil', None)


@pytest.mark.parametrize('bad', ['astrology', '', 5, None, ['civil'], 'OTHER'])
def test_an_unknown_specialty_is_dropped(ctx, plat, bad):
    row = plat.ef.waiting[0]
    row['specialty'], row['specialty_other'] = bad, 'x'
    body, _raw = _detail(ctx, row['id'])
    assert body['specialty'] is None and body['specialty_other'] is None


@pytest.mark.parametrize('bad,expected', [(True, None), ('8', None), (0, None), (-3, None), (9999, None), (8.0, 8),
                                          (12, 12), (None, None)])
def test_contract_pages_is_a_sane_positive_number_or_nothing(ctx, plat, bad, expected):
    row = plat.ef.waiting[0]
    row['contract_pages'] = bad
    body, _raw = _detail(ctx, row['id'])
    assert body['contract_pages'] == expected


@pytest.mark.parametrize('kind', ['', 'CONTRACT', 5, None, 'case', ['contract']])
def test_an_unknown_kind_is_a_plain_question(ctx, plat, kind):
    row = plat.ef.waiting[0]
    row['kind'] = kind
    assert _detail(ctx, row['id'])[0]['kind'] == 'question'


def test_the_contract_name_comes_from_the_marked_document_only(ctx, plat):
    full = plat.ef._detail(plat.ef.review[-1])
    full['docs'] = [{'id': 'd0', 'name': 'مستند تاني.pdf'}, {'id': 'd1', 'name': 'العقد.pdf', 'is_contract': True}]
    plat.forced[('GET', '/api/bridge/expert-files/' + KR)] = (200, full)
    assert _detail(ctx, KR)[0]['contract_name'] == 'العقد.pdf'
    full['docs'] = [{'id': 'd0', 'name': 'مستند تاني.pdf'}]
    assert _detail(ctx, KR)[0]['contract_name'] is None


def test_the_old_files_detail_has_no_contract_no_specialty_and_is_a_question(ctx, plat):
    body, _raw = _detail(ctx, fx.F1['id'])
    assert body['kind'] == 'question' and body['contract'] is None
    assert (body['contract_pages'], body['contract_name'], body['specialty'], body['specialty_other']) == (None,) * 4


def test_detail_never_carries_the_assign_log_or_client_data(ctx, plat):
    """سجل التوزيع بيتقري من صفّ القايمة — التفاصيل مش بتعدّيه، ولا إيميل الخبير ولا العميل."""
    body, raw = _detail(ctx, KR)
    assert 'assign_log' not in body
    for leak in ('@clients.test', 'rana@experts.test', 'payment_id', 'pay-'):
        assert leak not in raw, leak


# ---------------------------------------------------------------- ٧) قايمة التخصصات

def test_the_specialty_list_matches_the_platform_spec_when_it_is_next_to_the_repo():
    import app as appmod
    spec = '/Users/abdelrhman/Documents/Playground/elprofessor-wt-r8/docs/expert-files/SPEC-R14-CONTRACT-ASSIGN.md'
    if not os.path.isfile(spec):
        pytest.skip('مواصفة المنصة مش جنب الريبو')
    with open(spec, encoding='utf-8') as fh:
        text = fh.read()
    block = text[text.index('SPECIALTIES = {'):]
    block = block[:block.index('}\n')]
    pairs = dict(re.findall(r'"(\w+)": "([^"]+)"', block))
    assert pairs == appmod._EF_SPECIALTIES
    assert tuple(pairs) == fx.SPECIALTY_KEYS
