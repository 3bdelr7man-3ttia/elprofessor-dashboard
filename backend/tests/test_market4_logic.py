# -*- coding: utf-8 -*-
"""منطق «السوق v4» في الداشبورد (v2s/market4.js، الجزء النقي) + جدول النسب بسلّم السوق (v2-logic.js) — بيتشغّل في node بلا شبكة وبلا DOM.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_market4_logic.py

اللي بيثبّته:
  ١. مدى الأسعار: أعداد صحيحة (لاتينية وهندية وبفواصل) · زوج كامل أو لا شيء · الأدنى < الأعلى · تحذير فوق ثلاثة أضعاف (لا يمنع) · الفارغ تمامًا ≠ المسح · الفروق قبل ⇒ بعد.
  ٢. اقتراحات «أخرى»: نموذج الاعتماد (النوع والتخصص والنطاق، وفي كلٍّ «أخرى» ⇒ فارغ للمنصة) · الرفض بلا حقول زيادة.
  ٣. صفوف القوائم (اقتراحات · كتالوج · مكاتب · طلبات مفتوحة): المصدر الفاشل null لا صفر · الثابت لا يُعدَّل · الروابط https بس · التجريبي وعروض المدرّبين خارج المفتوحة.
  ٤. بلاد القيد: معرّف الملف من رابط المنصة بنمط صارم · بلد الطلب مسبقًا · ISO-2 نظيف بلا تكرار وحتى ١٢ · «أخرى» موجودة في القائمة.
  ٥. جدول النسب: سلّم السوق يظهر بسبع عملات · الأرضية ٢٥ والحدود تزيد وآخر درجة بلا سقف · الفروق والسجل · سجل قديم بلا سوق ما يكتبش «لا شيء ⇒».
  ٦. النصوص: أرقام هندية و«·» ما تلاصق رقمًا · لا «يقوّم» ولا مصطلحات تقنية.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
NODE = shutil.which('node')
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
NOW = 1793361600000          # 2026-10-30T12:00:00Z
H = 3600e3


def _iso(hours_ago):
    import datetime
    return datetime.datetime.fromtimestamp((NOW - hours_ago * H) / 1000.0, datetime.timezone.utc).isoformat()


def _run(fn, args, of):
    p = subprocess.run([NODE, os.path.join(_HERE, 'uiharness', 'm4_apply.js')], input=json.dumps({'fn': fn, 'args': list(args), 'of': of}, ensure_ascii=False),
                       capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    if p.returncode != 0:
        raise RuntimeError('node failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def M(fn, *args):
    return _run(fn, args, 'M')


def L(fn, *args):
    return _run(fn, args, 'L')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _texts(o, out=None):
    out = [] if out is None else out
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            _texts(v, out)
    elif isinstance(o, list):
        for v in o:
            _texts(v, out)
    return out


def _clean_copy(*objs):
    """«·» ما تلاصق رقمًا · لا أرقام لاتينية في النص الظاهر (باستثناء الإيميلات والمعرّفات) · لا كلمات ممنوعة."""
    for t in [x for o in objs for x in _texts(o)]:
        if '@' in t or re.match(r'^[A-Za-z0-9_.:/?#=&%+-]+$', t):
            continue
        assert not re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', t), t
        assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', t), t
        assert not re.search(r'\bAPI\b|JSON|undefined|NaN|null|\[object', t), t
        assert not re.search(r'[0-9]', t), 'رقم لاتيني ظاهر: ' + t


# ---------------------------------------------------------------- ١) مدى الأسعار

@needs_node
def test_the_anchor_check_accepts_whole_numbers_in_any_digits_with_separators():
    r = M('anchorCheck', {'EGP': {'min': '٢٥٠٠', 'max': '6,000'}, 'SAR': {'min': '400', 'max': '١٬١٠٠'}, 'USD': {'min': ' 80 ', 'max': '220'}})
    assert r['ok'] is True and r['empty'] is False and r['errors'] == {}
    assert r['payload'] == {'EGP': [2500, 6000], 'SAR': [400, 1100], 'USD': [80, 220]}


@needs_node
@pytest.mark.parametrize('mn,mx,msg', [
    ('1.5', '9', 'بلا كسور'), ('abc', '9', 'بلا كسور'), ('-5', '9', 'بلا كسور'), ('5', '9.5', 'بلا كسور'), ('1٢x3', '900', 'بلا كسور'), ('12345678901', '99999999999', 'بلا كسور'),
    ('5', '', 'معًا'), ('', '5', 'معًا'), ('500', '500', 'أقل من الأعلى'), ('900', '100', 'أقل من الأعلى')])
def test_the_anchor_check_refuses_with_a_plain_sentence(mn, mx, msg):
    r = M('anchorCheck', {'EGP': {'min': mn, 'max': mx}})
    assert r['ok'] is False and msg in r['errors']['EGP'] and r['payload'] == {}


@needs_node
def test_more_than_three_times_warns_but_never_blocks_and_exactly_three_does_not_warn():
    r = M('anchorCheck', {'EGP': {'min': '100', 'max': '300'}, 'SAR': {'min': '100', 'max': '301'}, 'USD': {'min': '1', 'max': '1000'}})
    assert r['ok'] is True and r['payload']['SAR'] == [100, 301]
    assert 'EGP' not in r['warns'] and 'ثلاثة أضعاف' in r['warns']['SAR'] and 'USD' in r['warns']


@needs_node
def test_all_empty_is_not_a_save_it_asks_for_the_clear_button_and_one_bad_currency_blocks_the_rest():
    r = M('anchorCheck', {})
    assert r['ok'] is False and r['empty'] is True and 'امسح المدى' in r['error']
    r = M('anchorCheck', {'EGP': {'min': '1', 'max': '9'}, 'KWD': {'min': '9', 'max': '1'}})
    assert r['ok'] is False and r['empty'] is False and list(r['errors']) == ['KWD'] and 'صحّح' in r['error']
    r = M('anchorCheck', {'GBP': {'min': '1', 'max': '9'}})
    assert r['empty'] is True, 'عملة غير معروفة تتجاهل'


@needs_node
def test_inputs_come_back_in_arabic_digits_and_the_diff_names_each_changed_currency():
    inp = M('anchorInputs', {'EGP': [2500, 6000]})
    assert inp['EGP'] == {'min': '٢٥٠٠', 'max': '٦٠٠٠'} and inp['SAR'] == {'min': '', 'max': ''} and list(inp) == ['EGP', 'SAR', 'AED', 'QAR', 'KWD', 'OMR', 'USD']
    d = M('anchorDiff', {'EGP': [2500, 6000], 'SAR': [400, 1100]}, {'EGP': [3000, 6000], 'USD': [80, 220]})
    got = {x['label']: (x['from'], x['to']) for x in d}
    assert got == {'جنيه مصري': ('٢٬٥٠٠ إلى ٦٬٠٠٠ جنيه', '٣٬٠٠٠ إلى ٦٬٠٠٠ جنيه'), 'ريال سعودي': ('٤٠٠ إلى ١٬١٠٠ ريال سعودي', 'بلا مدى'),
                   'دولار أمريكي': ('بلا مدى', '٨٠ إلى ٢٢٠ دولار')}, got
    assert M('anchorDiff', {'EGP': [1, 2]}, {'EGP': [1, 2]}) == []
    assert [x['to'] for x in M('anchorDiff', {'EGP': [1, 2]}, None)] == ['بلا مدى']
    _clean_copy(d)


@needs_node
def test_anchor_errors_from_the_platform_pass_with_arabic_digits_and_have_safe_fallbacks():
    assert M('anchorError', 422, {'error': 'EGP: الأدنى لازم يكون أقل من الأعلى 5'}).endswith('٥')
    assert 'مالهاش مدى' in M('anchorError', 409, {'error': 'الخدمة دي مالهاش مدى سعر'})
    assert M('anchorError', 404, {}) == 'هذه الخدمة لم تعد في القائمة'
    assert M('anchorError', 502, {'error': 'x', 'no_reply': True}) == 'x'
    assert M('anchorError', 500, {}) == 'تعذّر حفظ المدى، حاول مرة أخرى'
    assert M('catalogQuery', {'noRange': True, 'q': ' عقد '}) == '/v2/market/catalog?no_range=1&q=%D8%B9%D9%82%D8%AF'
    assert M('catalogQuery', {}) == '/v2/market/catalog'


# ---------------------------------------------------------------- ٢) اقتراحات «أخرى»

@needs_node
def test_the_approve_form_builds_empty_values_for_other_so_the_platform_chooses_its_defaults():
    ok = M('suggestionDecision', {'decision': 'approve', 'type': 'memo', 'specialty': 'civil', 'scopeMode': 'note'})
    assert ok == {'ok': True, 'body': {'decision': 'approve', 'service_type': 'memo', 'specialty': 'civil', 'scope': ''}}
    other = M('suggestionDecision', {'decision': 'approve', 'type': 'other', 'specialty': 'other', 'scopeMode': 'other', 'scope': '  نطاق كتبته  '})
    assert other['body'] == {'decision': 'approve', 'service_type': '', 'specialty': '', 'scope': 'نطاق كتبته'}
    assert M('suggestionDecision', {'decision': 'reject', 'type': 'memo'}) == {'ok': True, 'body': {'decision': 'reject'}}


@needs_node
@pytest.mark.parametrize('form,msg', [
    ({'decision': 'approve', 'specialty': 'civil'}, 'نوع الخدمة'), ({'decision': 'approve', 'type': 'memo'}, 'التخصص'),
    ({'decision': 'approve', 'type': 'nope', 'specialty': 'civil'}, 'غير معروف'), ({'decision': 'approve', 'type': 'memo', 'specialty': 'nope'}, 'غير معروف'),
    ({'decision': 'approve', 'type': 'memo', 'specialty': 'civil', 'scopeMode': 'other', 'scope': '  '}, 'اكتب النطاق'),
    ({'decision': 'approve', 'type': 'memo', 'specialty': 'civil', 'scopeMode': 'other', 'scope': 'x' * 601}, 'طويل'), ({'decision': 'x'}, 'اعتماد أو رفض'), (None, 'اعتماد أو رفض')])
def test_the_approve_form_refuses_in_plain_arabic(form, msg):
    r = M('suggestionDecision', form)
    assert r['ok'] is False and msg in r['error']


@needs_node
def test_every_picker_has_other_and_the_lists_match_the_platform():
    types = [t[0] for t in M('SERVICE_TYPES')]
    assert len(types) == 12 and 'written_opinion' in types
    specs = [t[0] for t in M('SPECIALTIES')]
    assert len(specs) == 14 and 'general' not in specs and 'corporate' not in specs, 'عام ⇒ «أخرى»، وتجاري/شركات مكرّرة بتسمية واحدة'
    countries = M('COUNTRIES')
    assert countries[-1] == ['XX', 'أخرى'] and len(countries) == 19 and M('OTHER') == 'other'
    assert M('typeLabel', 'zzz') == 'أخرى' and M('specialtyLabel', 'zzz') == 'أخرى' and M('countryLabel', 'XX') == 'أخرى' and M('countryLabel', 'sa') == 'السعودية'


@needs_node
def test_the_suggestions_view_counts_what_waits_and_never_invents_zero():
    resp = {'items': [{'id': 'a', 'name': 'ترجمة', 'note': 'ن', 'user_email': 'u@x.test', 'status': 'pending', 'created_at': _iso(5)},
                      {'id': 'b', 'name': '', 'status': 'approved', 'created_slug': 'svc-1', 'decided_by': 'f@x.test', 'created_at': _iso(50)},
                      {'id': '', 'name': 'بلا معرّف'}, 'junk'], 'pending': 1, 'total': 2}
    v = M('suggestions', resp, NOW)
    assert [r['id'] for r in v['rows']] == ['a', 'b'] and v['pending'] == 1 and v['countText'] == 'اقتراح واحد ينتظر'
    assert v['rows'][0]['open'] is True and v['rows'][0]['when'] == 'منذ ٥ ساعات' and v['rows'][1]['name'] == 'اقتراح بلا اسم' and v['rows'][1]['statusText'] == 'اعتُمد'
    assert M('suggestions', None, NOW) is None and M('suggestions', {'items': 'x'}, NOW) is None, 'مصدر فاشل ⇒ null'
    assert M('suggestions', {'items': [], 'pending': 0}, NOW)['countText'] == 'لا اقتراحات تنتظر'
    assert M('suggestions', {'items': [{'id': 'a', 'name': 'x', 'status': 'pending'}] * 3}, NOW)['countText'] == '٣ اقتراحات تنتظر', 'العدّ من الصفوف لو المنصة ما بعتتش pending'
    _clean_copy(v)
    assert M('decideDone', 'reject', {}) == 'رُفض الاقتراح، وأُبلغ صاحبه'
    assert 'لم يُسجَّل طلب تقديمها' in M('decideDone', 'approve', {'claimed': False}) and 'سجّلنا طلب تقديمها' in M('decideDone', 'approve', {'claimed': True})
    assert M('decideError', 409, {'error': 'اتقرّر في الاقتراح ده قبل كده'}) == 'اتقرّر في الاقتراح ده قبل كده' and 'سبق أن اتُّخذ قرار' in M('decideError', 409, {})
    assert M('decideError', 500, {}) == 'تعذّر تنفيذ القرار، حاول مرة أخرى'


# ---------------------------------------------------------------- ٣) القوائم

@needs_node
def test_the_catalog_view_marks_fixed_items_as_not_editable_and_writes_the_range_in_plain_words():
    resp = {'items': [
        {'slug': 'a', 'name': 'مراجعة عقد', 'service_type': 'contract_review', 'specialty': 'commercial', 'specialty_label': 'تجاري وشركات', 'pricing_mode': 'quote',
         'licensed': False, 'anchor_range': {'EGP': [2500, 6000], 'SAR': [400, 1100], 'GBP': [1, 2], 'USD': ['x', 5]}},
        {'slug': 'b', 'name': 'بحث', 'service_type': 'legal_research', 'specialty': 'general', 'pricing_mode': 'quote', 'licensed': True, 'anchor_range': None},
        {'slug': 'c', 'name': 'رأي ثابت', 'service_type': 'written_opinion', 'specialty': 'family', 'pricing_mode': 'fixed', 'anchor_range': None}, {'slug': ''}],
        'total': 3, 'no_range_count': 1, 'currencies': ['EGP', 'SAR', 'BAD']}
    v = M('catalog', resp)
    a, b, c = v['rows']
    assert a['text'] == '٢٬٥٠٠ إلى ٦٬٠٠٠ جنيه، وعملة أخرى' and a['hasRange'] and a['canEdit'] and sorted(a['range']) == ['EGP', 'SAR']
    assert b['text'] == 'بلا مدى' and b['canEdit'] and b['licensed'] and b['specialty'] == 'أخرى'
    assert c['text'] == 'سعر ثابت' and c['canEdit'] is False and c['fixed'] is True
    assert v['noRangeCount'] == 1 and v['noRangeText'] == 'خدمة واحدة بلا مدى' and v['currencies'] == ['EGP', 'SAR'] and v['total'] == 3
    assert M('catalog', None) is None and M('catalog', {'items': {}}) is None
    assert M('catalog', {'items': [], 'no_range_count': 0})['noRangeText'] == 'كل الخدمات لها مدى'
    assert M('catalog', {'items': []})['noRangeText'] == '', 'بلا رقم من المنصة ⇒ لا جملة'
    _clean_copy(v)


@needs_node
def test_the_orgs_view_gives_the_registration_link_member_count_and_who_can_be_verified():
    resp = {'items': [
        {'id': 'o1', 'name': 'مكتب النور', 'city': 'القاهرة', 'country': 'EG', 'founded_year': 2011, 'status': 'pending', 'created_at': _iso(30),
         'commercial_reg': {'url': 'https://f.test/r.pdf', 'verified_by': '', 'verified_at': ''},
         'members': [{'email': 'a@x.test', 'role': 'admin', 'verified_lawyer': True}, {'email': 'b@x.test', 'role': 'lawyer', 'verified_lawyer': False}], 'badge': False},
        {'id': 'o2', 'name': 'بلا سجل', 'status': 'pending', 'commercial_reg': None, 'members': []},
        {'id': 'o3', 'name': 'موثّق', 'status': 'pending', 'commercial_reg': {'url': 'https://f.test/x', 'verified_at': _iso(1), 'verified_by': 'f'}, 'members': [{'email': 'z', 'role': 'admin'}]},
        {'id': 'o4', 'name': 'موقوف', 'status': 'suspended', 'commercial_reg': {'url': 'https://f.test/y', 'verified_at': ''}, 'members': []},
        {'id': 'o5', 'name': 'رابط خطر', 'status': 'pending', 'commercial_reg': {'url': 'javascript:alert(1)'}, 'members': []}]}
    v = M('orgs', resp, NOW)
    o1, o2, o3, o4, o5 = v['rows']
    assert o1['regUrl'] == 'https://f.test/r.pdf' and o1['members'] == 2 and o1['membersText'] == 'عضوان' and o1['canVerify'] is True and o1['place'] == 'القاهرة، مصر' and o1['founded'] == '٢٠١١'
    assert o1['lawyers'] == 1 and o1['statusText'] == 'ينتظر التوثيق'
    assert o2['regUrl'] == '' and o2['canVerify'] is False and o2['blockedText'] == 'لم يرفع سجله التجاري بعد' and o2['membersText'] == 'بلا أعضاء'
    assert o3['canVerify'] is False and o3['regVerified'] is True and o3['blockedText'] == 'سُجّل توثيق السجل'
    assert o4['canVerify'] is False and o4['blockedText'] == 'المكتب موقوف' and o4['statusText'] == 'موقوف'
    assert o5['regUrl'] == '' and o5['canVerify'] is False, 'javascript: ما يبقاش رابطًا'
    assert v['countText'] == '٥ مكاتب تنتظر' and M('orgs', None, NOW) is None
    assert 'لم يرفع' in M('verifyError', 422, {'error': 'المكتب لم يرفع سجله التجاري بعد'}) and M('verifyDone', {'already': True}) == 'كان السجل موثّقًا من قبل'
    assert M('verifyDone', {'already': False}) == 'تم توثيق السجل، والمكتب مفعّل'
    _clean_copy(v)


@needs_node
def test_open_requests_read_service_country_offers_and_attachment_opens():
    rows = [
        {'id': 'r1', 'title': 'مراجعة عقد شراكة', 'kind': 'request', 'status': 'open', 'service_slug': 'contract-review', 'service_name': 'مراجعة عقد تجاري', 'applicable_country': 'EG',
         'offer_count': 3, 'attachment_count': 2, 'attachment_access_count': 5, 'created_at': _iso(2)},
        {'id': 'r2', 'title': 'طلب قديم', 'kind': 'request', 'status': 'open', 'service_slug': '', 'service_name': '', 'applicable_country': '', 'offer_count': 0, 'attachment_count': 0,
         'attachment_access_count': 0, 'created_at': _iso(80)},
        {'id': 'r3', 'title': 'عرض مدرّب', 'kind': 'training_offer', 'status': 'open'}, {'id': 'r4', 'title': 'تجريبي', 'is_test': True, 'status': 'open'},
        {'id': 'r5', 'title': 'مغلق', 'status': 'closed'}, {'id': 'r6', 'title': 'قديم', 'status': 'open', 'service_slug': 'x', 'applicable_country': 'ZZ', 'offer_count': 1,
                                                          'attachment_count': 1, 'attachment_access_count': 0, 'created_at': _iso(300)}]
    v = M('openRequests', {'items': rows, 'total': 6}, NOW)
    assert [r['id'] for r in v['rows']] == ['r1', 'r2', 'r6'], 'الأحدث أولًا؛ لا عروض مدرّبين ولا تجريبي ولا مغلق'
    r1, r2, r6 = v['rows']
    assert (r1['service'], r1['country'], r1['offersText'], r1['filesText']) == ('مراجعة عقد تجاري', 'مصر', '٣ عروض', 'مرفقان، فُتح ٥ مرات')
    assert (r2['service'], r2['country'], r2['offersText'], r2['filesText']) == ('', '', 'بلا عروض', 'بلا مرفقات')
    assert r6['service'] == 'x' and r6['country'] == 'أخرى' and r6['filesText'] == 'مرفق واحد، لم يُفتح بعد'
    assert v['countText'] == '٣ طلبات مفتوحة' and M('openRequests', None, NOW) is None
    assert M('openRequests', {'items': []}, NOW)['countText'] == 'لا طلبات مفتوحة'
    _clean_copy(v)


# ---------------------------------------------------------------- ٤) الترخيص عند القبول

@needs_node
def test_the_licence_file_id_comes_only_from_a_platform_licence_link():
    ok = 'https://api.elprofessor.net/api/bridge/market/licence-files/lf-3c9a41d2-7b05-4e88-a1f0'
    assert M('licenceFileId', ok) == 'lf-3c9a41d2-7b05-4e88-a1f0' and M('licenceFileId', ok + '?x=1') == 'lf-3c9a41d2-7b05-4e88-a1f0'
    for bad in ('', None, 'https://evil.test/file.png', ok + '/../../x', 'https://api.x/api/bridge/market/licence-files/short', ok + ' extra', 'javascript:alert(1)',
                'https://x.test/api/bridge/market/licence-files/' + 'a' * 70):
        assert M('licenceFileId', bad) == '', bad


@needs_node
def test_the_licence_block_prefills_the_country_and_never_trusts_a_free_text_code():
    o = M('licenceOf', {'licence_country': 'sa', 'licence': 'https://api.elprofessor.net/api/bridge/market/licence-files/lf-3c9a41d2-7b05-4e88-a1f0', 'bar_number': '١٢٣٤٥'})
    assert o == {'country': 'SA', 'countryName': '', 'fileId': 'lf-3c9a41d2-7b05-4e88-a1f0', 'bar': '١٢٣٤٥'}
    assert M('licenceOf', {'licence_country': 'XX', 'licence_country_name': ' قبرص '})['countryName'] == 'قبرص'
    assert M('licenceOf', {'licence_country': 'Saudi'})['country'] == '' and M('licenceOf', None) == {'country': '', 'countryName': '', 'fileId': '', 'bar': ''}
    line = M('licenceLine', {'licence': {'country': 'SA', 'bar': '12345'}})
    assert line == 'بلد القيد المكتوب في الطلب: السعودية، رقم القيد: ١٢٣٤٥'
    assert M('licenceLine', {'licence': {'country': 'XX', 'countryName': 'قبرص', 'bar': ''}}) == 'بلد القيد المكتوب في الطلب: قبرص' and M('licenceLine', {}) == ''
    _clean_copy(line)


@needs_node
def test_the_countries_sent_with_an_approval_are_clean_unique_and_capped():
    assert M('licensedCountries', ['sa', 'EG', 'SA', ' xx ', 'bad', 'S1', 5, None]) == {'ok': True, 'list': ['SA', 'EG', 'XX']}
    assert M('licensedCountries', []) == {'ok': True, 'list': []} and M('licensedCountries', None) == {'ok': True, 'list': []}
    big = [a + b for a in 'ABCDEFG' for b in 'XY'][:13]
    assert M('licensedCountries', big)['ok'] is False
    assert [c['code'] for c in M('countryOptions')][:4] == ['EG', 'SA', 'AE', 'QA']
    assert M('fileError', 404) == 'ملف الترخيص غير موجود' and M('fileError', 0) == 'تعذّر جلب ملف الترخيص، حاول مرة أخرى'


# ---------------------------------------------------------------- ٥) جدول النسب: سلّم السوق

MARKET = {'ladder_by_currency': {
    'EGP': [{'max': 10000, 'platform_pct': 35}, {'max': 30000, 'platform_pct': 30}, {'max': None, 'platform_pct': 25}],
    'SAR': [{'max': 750, 'platform_pct': 35}, {'max': 2250, 'platform_pct': 30}, {'max': None, 'platform_pct': 25}],
    'KWD': [{'max': 60, 'platform_pct': 35}, {'max': 180, 'platform_pct': 30}, {'max': None, 'platform_pct': 25}]}}


def _shares(**over):
    t = {'version': 7, 'books': {'normal': {'owner': 60, 'platform': 40}, 'ads': {'owner': 65, 'platform': 35}},
         'courses': {'base': 35, 'code_max': 50, 'ads_max_bonus': 25, 'owner_cap': 65},
         'cases': {'ladder': [{'max_egp': 10000, 'platform_pct': 35}, {'max_egp': 30000, 'platform_pct': 30}, {'max_egp': None, 'platform_pct': 25}]},
         'case_floor': 25, 'platform_floor': 35, 'affiliate': {'rate': 10, 'split': 'pro_rata', 'floor_measured': 'before_affiliate'}, 'market': json.loads(json.dumps(MARKET))}
    t.update(over)
    return t


@needs_node
def test_the_shares_view_shows_the_market_ladder_per_currency_in_plain_arabic():
    v = L('v2SharesView', {'shares': _shares()})
    assert [m['cur'] for m in v['market']] == ['EGP', 'SAR', 'KWD'] and v['marketFloor'] == 25 and v['marketFloorText'] == 'نصيب المنصة في السوق لا ينزل عن ٢٥٪'
    egp = v['market'][0]
    assert [t['upTo'] for t in egp['tiers']] == ['أقل من ١٠٬٠٠٠', 'من ١٠٬٠٠٠ إلى ٣٠٬٠٠٠', 'أكثر من ٣٠٬٠٠٠']
    assert [t['platformText'] for t in egp['tiers']] == ['٣٥٪', '٣٠٪', '٢٥٪'] and egp['name'] == 'جنيه مصري'
    assert 'لا ينزل عن ٣٥٪' in v['floorText'] and '٢٥٪' in v['floorText'], 'نص الأرضية القديم ثابت'
    assert L('v2SharesView', {'shares': _shares(market=None)})['market'] is None, 'منصة قديمة بلا سوق ⇒ القسم يختفي'
    _clean_copy(v['market'], v['marketFloorText'])


@needs_node
def test_a_market_edit_sends_only_the_changed_currency_and_keeps_the_rest():
    t = _shares()
    r = L('v2SharesChanges', t, {'market': {'EGP': [{'max': '١٢٠٠٠', 'pct': '35'}, {'max': '30000', 'pct': '28'}, {'pct': '25'}], 'SAR': [{'max': '750', 'pct': '35'}, {'max': '2250', 'pct': '30'}, {'pct': '25'}]}})
    assert r['ok'] is True
    assert r['changes'] == {'market': {'ladder_by_currency': {'EGP': [{'max': 12000, 'platform_pct': 35}, {'max': 30000, 'platform_pct': 28}, {'max': None, 'platform_pct': 25}]}}}
    assert r['after']['market']['ladder_by_currency']['SAR'] == MARKET['ladder_by_currency']['SAR'] and r['after']['market']['ladder_by_currency']['EGP'][0]['max'] == 12000
    d = L('v2SharesDiff', t, r['after'])
    got = {x['label']: (x['from'], x['to']) for x in d['lines']}
    assert got == {'السوق، جنيه مصري، الدرجة ١': ('أقل من ١٠٬٠٠٠، المنصة ٣٥٪', 'أقل من ١٢٬٠٠٠، المنصة ٣٥٪'),
                   'السوق، جنيه مصري، الدرجة ٢': ('من ١٠٬٠٠٠ إلى ٣٠٬٠٠٠، المنصة ٣٠٪', 'من ١٢٬٠٠٠ إلى ٣٠٬٠٠٠، المنصة ٢٨٪')}, got
    same = L('v2SharesChanges', t, {'market': {'EGP': [{'max': '10000', 'pct': '35'}, {'max': '30000', 'pct': '30'}, {'pct': '25'}]}})
    assert same['ok'] is False and same['unchanged'] is True


@needs_node
@pytest.mark.parametrize('inp,msg', [
    ({'EGP': [{'pct': '24'}]}, 'لا ينزل عن ٢٥٪'), ({'EGP': [{'pct': '101'}]}, 'بين ٠ و١٠٠'), ({'EGP': [{'pct': 'x'}]}, 'بين ٠ و١٠٠'), ({'EGP': [{}, {}, {'pct': '10'}]}, 'لا ينزل عن'),
    ({'EGP': [{'max': '0'}]}, 'أكبر من صفر'), ({'EGP': [{'max': 'abc'}]}, 'أكبر من صفر'), ({'EGP': [{'max': '30000'}, {'max': '10000'}]}, 'لازم تزيد'),
    ({'EGP': [{'max': '40000'}, {'max': '30000'}]}, 'لازم تزيد')])
def test_the_market_edit_checks_shape_floor_and_order_in_the_screen_too(inp, msg):
    r = L('v2SharesChanges', _shares(), {'market': inp})
    assert r['ok'] is False and msg in r['error'], r
    assert 'unchanged' not in r


@needs_node
def test_the_history_writes_market_lines_only_when_both_sides_have_the_ladder():
    before = _shares()
    after = json.loads(json.dumps(before))
    after['market']['ladder_by_currency']['SAR'][1]['platform_pct'] = 28
    hist = L('v2SharesHistory', {'history': [{'by': 'f@x.test', 'at': _iso(1), 'before': before, 'after': after}]}, NOW)
    assert hist[0]['lines'] == [{'label': 'السوق، ريال سعودي، الدرجة ٢', 'from': 'من ٧٥٠ إلى ٢٬٢٥٠، المنصة ٣٠٪', 'to': 'من ٧٥٠ إلى ٢٬٢٥٠، المنصة ٢٨٪'}]
    old = _shares()
    old.pop('market')
    h2 = L('v2SharesHistory', {'history': [{'by': 'f@x.test', 'at': _iso(1), 'before': old, 'after': before}]}, NOW)
    assert h2[0]['lines'] == [], 'قبل دخول السوق للجدول: لا «لا شيء ⇒ المنصة ٣٥٪» لسطور ما اتغيّرتش'
    _clean_copy(hist)


# ---------------------------------------------------------------- ٦) التبويب وبطاقة القبول

@needs_node
def test_the_tab_sits_last_in_the_market_section_and_licensed_join_cards_open_the_sheet():
    mk = [s for s in L('SECTIONS') if s['key'] == 'market'][0]
    assert mk['tabs'][-1]['key'] == 'manage' and mk['tabs'][-1]['label'] == 'إدارة السوق' and mk['tabs'][-1]['mod'] == 'v2s_market_v4'
    assert L('routeFor', '#s/market/manage', {})['tab'] == 'manage'
    row = {'apiKind': 'join', 'apiId': 'jr', 'who': 'أ. هبة', 'from': 'محامٍ معتمد', 'serviceLabel': 'مرافعة', 'licensed': True, 'licenceMissing': False, 'attachments': [], 'note': 'ن'}
    card = L('v2Card', row, {'now': NOW})
    assert card['primary']['label'] == 'افتح وراجع' and card['primary']['act']['do'] == 'open' and 'بلد القيد' in card['reason']
    plain = L('v2Card', dict(row, licensed=False), {'now': NOW})
    assert plain['primary']['label'] == 'اقبل' and plain['primary']['act'] == {'do': 'decide', 'action': 'approve'}
    missing = L('v2Card', dict(row, licenceMissing=True), {'now': NOW})
    assert missing['primary']['label'] == 'افتح وراجع'


# ---------------------------------------------------------------- ٧) الملفات والقواعد

def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_files_ship_and_stay_inside_their_own_rules():
    js = _read('dashboard-cloud', 'v2s', 'market4.js')
    css = _read('dashboard-cloud', 'v2s', 'market4.css')
    html = _read('dashboard-cloud', 'index.html')
    m = re.search(r'<!-- v2 sections begin -->(.*?)<!-- v2 sections end -->', html, re.S)
    assert '<link rel="stylesheet" href="v2s/market4.css">' in m.group(1) and m.group(1).count('<script src="v2s/market4.js"></script>') == 1
    assert m.group(1).index('v2s/market.js') < m.group(1).index('v2s/market4.js') < m.group(1).index('v2s/marketing.js'), 'بعد market.js وقبل marketing.js (ترتيب أبجدي)'
    assert html.index('v2-logic.js') < html.index('v2s/market4.js'), 'المنطق يتحمّل قبل'
    code = _strip(js)
    assert not re.search(r'\bfetch\(|XMLHttpRequest|api\.elprofessor|bridge/', code.replace('/bridge/market/licence-files/', '')), 'لا شبكة غير EP.api'
    assert not re.search(r'\b(alert|confirm|prompt)\s*\(', code), 'لا نوافذ المتصفح'
    assert 'localStorage' not in code and 'sessionStorage' not in code
    assert len(re.findall(r'confirmed(?::| =) true', code)) >= 4 and 'ep-b1' in code and 'ep-b2' in code
    for sel in re.findall(r'(?m)^([^@\s/}{][^{]*)\{', re.sub(r'/\*.*?\*/', '', css, flags=re.S)):
        for part in sel.split(','):
            part = part.strip()
            assert part == '' or '.m4-' in part or '.v2s-m4' in part or part.startswith(('0%', '100%', 'from', 'to')), part
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in _read(df), df


def test_visible_copy_has_no_banned_words_and_no_dot_next_to_a_digit():
    js = _read('dashboard-cloud', 'v2s', 'market4.js')
    strings = ' '.join(re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", _strip(js)))
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings), 'كلمة ممنوعة'
    for word in ('API', 'JSON', 'endpoint', 'token', 'bridge', 'استرداد'):
        assert word not in strings, word
    assert not re.search(r"<h[1-4][^>]*>\s*(الذكاء|AI)", js)
    assert not re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', strings)
    assert "['XX', 'أخرى']" in js and "<option value=\"other\">أخرى</option>" in js
