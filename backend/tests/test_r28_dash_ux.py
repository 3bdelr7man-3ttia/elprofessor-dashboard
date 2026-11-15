# -*- coding: utf-8 -*-
"""r28 — تعديلات من التجربة الحيّة (2026-11-15): طريقة الدفع بالعربي · «منذ» بأسابيع وشهور وسنوات · أدوار صفحة الشخص · غلاف صفحة الدورة ·
فحص النشر الكامل · روابط مقدّم الطلب على بطاقات المدرّبين.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r28_dash_ux.py

⛔ صفر شبكة: المنطق في node على الملفات الحقيقية، وردود المنصة جدول في الذاكرة.
"""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ROOT = os.path.dirname(os.path.dirname(_HERE))
NOW = 1793000000000
HOUR = 3600e3
DAY = 24 * HOUR
LATIN = re.compile(r'[A-Za-z]')
DOT_DIGIT = re.compile(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]')


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


def _lg(fn, *args):
    return v2_node.logic(fn, *args)


def _iso(ms):
    import datetime
    return datetime.datetime.utcfromtimestamp(ms / 1000.0).strftime('%Y-%m-%dT%H:%M:%S+00:00')


# ───────────── ١. طريقة الدفع بالعربي ─────────────
CODES = {'instapay': 'إنستاباي', 'vodafone_cash': 'فودافون كاش', 'card': 'بطاقة بنكية', 'stripe': 'بطاقة بنكية',
         'paytabs': 'بطاقة بنكية', 'other': 'تحويل محلي'}


@needs_node
@pytest.mark.parametrize('code,ar', sorted(CODES.items()))
def test_method_codes_map_to_arabic(code, ar):
    assert _lg('util.payMethodAr', code) == ar
    assert _lg('util.payMethodAr', code.upper()) == ar
    assert _lg('util.payMethodAr', ' ' + code + ' ') == ar


@needs_node
def test_unknown_latin_code_never_shows_and_human_text_passes_through():
    assert _lg('util.payMethodAr', 'some_new_gateway') == 'تحويل محلي'
    assert _lg('util.payMethodAr', 'تحويل على الرقم ٠١٠٠') == 'تحويل على الرقم ٠١٠٠'
    assert _lg('util.payMethodAr', 'Vodafone-Cash') == 'فودافون كاش'
    assert _lg('util.payMethodAr', '') == '' and _lg('util.payMethodAr', None) == ''


def _manual_row(method):
    return {'apiKind': 'manual_payment', 'apiId': 'p1', 'pid': 'p1', 'who': 'منى', 'email': 'mona@x.test', 'amount': 450, 'currency': 'EGP',
            'payMethod': method, 'payWhat': 'دورة عقود', 'payRef': 'IP-77', 'ts': NOW - HOUR}


@needs_node
@pytest.mark.parametrize('code', ['instapay', 'vodafone_cash', 'card', 'stripe', 'paytabs', 'other'])
def test_no_latin_method_code_renders_on_the_decision_card_or_its_confirm_sheet(code):
    card = _lg('v2Card', _manual_row(code), {'now': NOW})
    shown = [card['brain'], card['sub']] + [f['v'] for f in card['facts']] + [card['primary']['money']['method'], card['secondary']['money']['method']
                                                                           if card.get('secondary') and card['secondary'].get('money') else '']
    assert not [x for x in shown if LATIN.search(x or '')], shown
    assert CODES[code] in card['brain'] and card['primary']['money']['method'] == CODES[code]
    assert dict((f['k'], f['v']) for f in card['facts'])['الطريقة'] == CODES[code]


@needs_node
def test_payout_method_and_stuck_receipts_are_arabic_too():
    p = {'apiKind': 'payout', 'pid': 'w1', 'who': 'هالة', 'email': 'h@x.test', 'currency': 'EGP', 'dest': 'hala@instapay', 'raw': {'amount': 600.5, 'method': 'instapay', 'created_at': _iso(NOW - HOUR)}}
    card = _lg('v2Card', p, {'now': NOW})
    assert card['primary']['money']['method'] == 'إنستاباي' and 'عبر إنستاباي' in card['brain']
    assert not LATIN.search(card['brain'])
    rows = _lg('v2Stuck', {'items': [{'order_id': 'o1', 'kind': 'course', 'amount': 450, 'currency': 'EGP', 'provider': 'instapay', 'buyer_email': 'a@x.test',
                                      'created_at': _iso(NOW - 3 * HOUR)}, {'order_id': 'o2', 'kind': 'course', 'amount': 1, 'currency': 'EGP', 'provider': 'paytabs',
                                                                           'buyer_email': 'b@x.test', 'created_at': _iso(NOW - 3 * HOUR)}]}, NOW)['rows']
    assert sorted(r['provider'] for r in rows) == ['إنستاباي', 'بطاقة بنكية']


def test_legacy_api_screens_map_the_method_too():
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'function payMethodLabel' in api
    assert 'payMethod: payMethodLabel(p.method)' in api and '"، " + payMethodLabel(p.method)' in api
    assert 'Stripe' not in api.split('var REV_METHOD_AR')[1].split('};')[0] and 'Wise' not in api.split('var REV_METHOD_AR')[1].split('};')[0]


@needs_node
def test_real_manual_payment_row_from_the_api_layer_has_an_arabic_method():
    first = v2_node._run('v2_rows.js', {'responses': {}, 'keys': ['inbox']})
    path = [p for p in first['asked'] if 'platform-manual-payments' in p][0]
    body = {'payments': [{'id': 'p9', 'user_name': 'منى', 'user_email': 'mona@x.test', 'amount': 450, 'currency': 'EGP', 'method': 'instapay', 'product_label': 'دورة',
                          'product_type': 'course', 'reference_number': 'R1', 'created_at': _iso(NOW - HOUR)}]}
    out = v2_node._run('v2_rows.js', {'responses': {path: {'status': 200, 'body': body}}, 'keys': ['inbox']})
    row = [r for r in out['inbox'] if r.get('apiKind') == 'manual_payment'][0]
    assert row['payMethod'] == 'إنستاباي' and 'instapay' not in row['note'] and 'إنستاباي' in row['note']


# ───────────── ٢. «منذ» بأيام وأسابيع وشهور وسنوات ─────────────
@needs_node
@pytest.mark.parametrize('hours,text', [
    (0.5, 'منذ ٣٠ دقيقة'), (0.01, 'الآن'), (3, 'منذ ٣ ساعات'), (48, 'منذ يومين'), (24 * 3, 'منذ ٣ أيام'), (24 * 6, 'منذ ٦ أيام'), (24 * 7, 'منذ ٧ أيام'), (24 * 12, 'منذ ١٢ يومًا'), (24 * 14, 'منذ أسبوعين'),
    (24 * 21, 'منذ ٣ أسابيع'), (24 * 29, 'منذ ٤ أسابيع'), (24 * 30, 'منذ شهر'), (24 * 60, 'منذ شهرين'), (3469, 'منذ ٤ شهور'), (24 * 144, 'منذ ٤ شهور'),
    (24 * 364, 'منذ ١٢ شهرًا'), (24 * 365, 'منذ سنة'), (24 * 800, 'منذ سنتين'), (24 * 365 * 5, 'منذ ٥ سنوات')])
def test_ago_text_switches_to_longer_units(hours, text):
    got = _lg('util.agoText', NOW - hours * HOUR, NOW)
    assert got == text, got


@needs_node
def test_the_3469_hours_receipt_reads_in_months_not_hours():
    # ١٤٤ يومًا و٩ ساعات ⇒ ٤ شهور
    got = _lg('util.agoText', NOW - 3469 * HOUR, NOW)
    assert got == 'منذ ٤ شهور', got
    rows = _lg('v2Stuck', {'items': [{'order_id': 'o1', 'kind': 'course', 'amount': 450, 'currency': 'EGP', 'provider': 'instapay', 'buyer_email': 'a@x.test',
                                      'age_hours': 3469}]}, NOW)['rows']
    assert rows[0]['ageText'] == 'منذ ٤ شهور', rows[0]['ageText']
    assert not re.search(r'[0-9٠-٩]{4}', rows[0]['ageText'])


@needs_node
def test_other_relative_helpers_share_the_same_scale():
    assert _lg('util.longSpan', 400) == 'سنة' and _lg('util.longSpan', 100) == '٣ شهور' and _lg('util.hoursSpan', 5) == '٥ ساعات'
    assert _lg('util.hoursSpan', 24 * 100) == '٣ شهور'
    assert _lg('util.durShort', 100 * DAY) == '٣ شهور'          # عدّاد البطاقات يتبع نفس السلّم
    assert _lg('util.durShort', 50 * HOUR).endswith('أيام') or _lg('util.durShort', 50 * HOUR) == 'يومان'


def test_the_notification_helper_in_the_api_layer_does_not_print_huge_hours():
    api = _read('dashboard-cloud', 'dashboard-api.js')
    seg = api.split('function relTime')[1].split('function arDate')[0]
    assert 'return arDate(iso)' in seg and 'days < 7' in seg


# ───────────── ٣. أدوار صفحة الشخص ─────────────
def _roles(approved_apps, **user):
    os.environ.setdefault('ALLOW_WEAK_SECRET_KEY', '1')
    from app import _v2_person_build
    u = dict({'email': 'a@b.co', 'full_name': 'أحمد', 'trainer_status': 'approved', 'role': 'user', 'id': 'u1'}, **user)
    S = {'users': {'users': [u]}, 'req_trainer_approved': approved_apps}
    return _v2_person_build('a@b.co', S)['roles']


def _app(join_as, **kw):
    return {'applications': [dict({'user_email': 'a@b.co', 'join_as': join_as, 'status': 'approved', 'updated_at': '2026-11-01T00:00:00+00:00'}, **kw)]}


def test_trainer_only_joiner_is_not_an_expert():
    assert _roles(_app('trainer')) == ['trainer']


def test_expert_only_and_both():
    assert _roles(_app('expert')) == ['expert']
    assert _roles(_app('both')) == ['expert', 'trainer']


def test_no_application_to_read_means_trainer_only_never_a_claimed_expert():
    assert _roles(None) == ['trainer'] and _roles({'applications': []}) == ['trainer'] and _roles(_app('')) == ['trainer']
    assert _roles(_app('nonsense')) == ['trainer']


def test_other_peoples_applications_do_not_leak_and_latest_wins():
    other = {'applications': [{'user_email': 'zz@b.co', 'join_as': 'both', 'updated_at': '2026-12-01'}]}
    assert _roles(other) == ['trainer']
    two = {'applications': [{'user_email': 'a@b.co', 'join_as': 'both', 'updated_at': '2026-01-01'}, {'user_email': 'a@b.co', 'join_as': 'trainer', 'updated_at': '2026-06-01'}]}
    assert _roles(two) == ['trainer']


def test_pending_trainer_has_no_expert_chip():
    assert _roles(None, trainer_status='pending') == ['trainer_pending']


@needs_node
def test_person_join_line_has_no_dot_beside_digits():
    resp = {'found': True, 'email': 'a@b.co', 'identity': {'name': 'أحمد', 'joined_at': '2026-11-02T10:00:00+00:00', 'invited_by': {'name': 'نادية', 'kind': 'member'}},
            'roles': ['trainer'], 'sources': {}}
    vm = _lg('v2Person', resp, NOW, 'a@b.co')
    assert 'بدعوة من نادية' in vm['joinLine'] and '·' not in vm['joinLine'], vm['joinLine']
    assert [c['label'] for c in vm['chips']] == ['مدرّب']


def test_no_source_dot_beside_digits_in_the_changed_strings():
    lg = _read('dashboard-cloud', 'v2-logic.js')
    for needle in ("'، بدعوة من '", "'، الداعي: '", "'، مدرّبون معتمدون '", "t + '، مرّ عليها أكثر من يوم'"):
        assert needle in lg, needle


# ───────────── ٤. غلاف صفحة الدورة = غلاف المنصة ─────────────
COURSE = {'id': 'c1', 'title': 'عقود', 'type': 'recorded_paid', 'approval_status': 'approved', 'is_active': True, 'price_amount': 480, 'price_currency': 'EGP', 'lesson_count': 9,
          'platform_owned': False, 'agreement_signed': True}
PLATFORM = 'https://app.elprofessor.net'


@needs_node
def test_cover_mirrors_the_platform_resolution_order():
    cv = lambda c: _lg('util.courseCover', c)
    assert cv({'thumbnail_url': 'https://cdn.x.test/a.jpg'}) == 'https://cdn.x.test/a.jpg'
    assert cv({'thumbnail_url': '/courses2/spec-marketing.jpg'}) == PLATFORM + '/courses2/spec-marketing.jpg'      # الصورة الجاهزة التي اختارها المدرّب
    assert cv({'thumbnail_url': '', 'cover': 'https://c.x.test/c.jpg'}) == 'https://c.x.test/c.jpg'
    assert cv({'image': 'https://c.x.test/i.jpg'}) == 'https://c.x.test/i.jpg'
    assert cv({'thumbnail_url': '', 'category': 'marketing'}) == PLATFORM + '/courses2/spec-marketing.jpg'
    assert cv({'category': 'criminal'}) == PLATFORM + '/courses2/world-judicial.jpg'
    assert cv({'category': 'realestate'}) == PLATFORM + '/courses2/spec-real-estate.jpg'
    assert cv({'category': 'corporate'}) == PLATFORM + '/courses2/world-legal-affairs.jpg'
    assert cv({'category': 'civil'}) == PLATFORM + '/courses2/track-courses.jpg' and cv({}) == PLATFORM + '/courses2/track-courses.jpg'
    assert cv({'thumbnail_url': 'javascript:alert(1)', 'category': 'marketing'}) == PLATFORM + '/courses2/spec-marketing.jpg'


@needs_node
def test_course_page_hero_is_never_blank_and_uses_the_platform_cover():
    m = _lg('v2s.courses.pageModel', dict(COURSE, thumbnail_url='/courses2/world-judicial.jpg'), None, None, None, None, {'now': NOW})
    assert m['hero'] == PLATFORM + '/courses2/world-judicial.jpg'
    m2 = _lg('v2s.courses.pageModel', dict(COURSE, thumbnail_url=''), None, None, None, None, {'now': NOW})
    assert m2['hero'] == PLATFORM + '/courses2/track-courses.jpg'


# ───────────── ٥. فحص النشر الكامل ─────────────
BRIDGE = {'ok': True, 'course_id': 'c1', 'slug': 'x', 'sale_block_reason': '', 'all_ok': False, 'checklist': [
    {'key': 'content', 'group': 'review', 'label': 'محتوى موجود (دروس مسجّلة أو موعد انطلاق للدورة الحية)', 'ok': True, 'detail': ''},
    {'key': 'outcomes', 'group': 'review', 'label': 'نواتج التعلم (ماذا ستتعلم) مذكورة', 'ok': True, 'detail': ''},
    {'key': 'intro_video', 'group': 'review', 'label': 'فيديو تعريفي مرفوع', 'ok': False, 'detail': ''},
    {'key': 'level', 'group': 'review', 'label': 'مستوى الدورة محدَّد', 'ok': True, 'detail': ''},
    {'key': 'pricing', 'group': 'review', 'label': 'التسعير سليم', 'ok': True, 'detail': ''},
    {'key': 'agreement', 'group': 'gate', 'label': 'توقيع المدرّب على اتفاقية التدريب', 'ok': True, 'detail': ''},
    {'key': 'sellable', 'group': 'sale', 'label': 'الدورة صالحة للبيع الآن', 'ok': False, 'detail': 'Course is not approved yet'},
]}


@needs_node
def test_full_bridge_list_is_restored_in_arabic_even_when_a_detail_is_latin():
    f = _lg('v2s.courses.courseFacts', COURSE, {'now': NOW, 'checklist': BRIDGE})
    keys = [i['key'] for i in f['items']]
    for k in ('content', 'outcomes', 'intro_video', 'level', 'price', 'agreement', 'sellable'):
        assert k in keys, (k, keys)
    by = dict((i['key'], i) for i in f['items'])
    assert by['outcomes']['ok'] is True and by['outcomes']['pos'].startswith('نواتج التعلم')
    assert by['intro_video']['ok'] is False and by['sellable']['ok'] is False
    # التفصيل اللاتيني يسقط وحده، والبند نفسه يبقى بنصه العربي
    assert by['sellable']['label'] == 'الدورة صالحة للبيع الآن'
    shown = [i['label'] for i in f['items']] + [i['pos'] for i in f['items']] + [f['line'], f['returnNote']]
    assert not [x for x in shown if LATIN.search(x)], shown
    assert len(f['items']) >= 7


def test_the_checklist_is_requested_for_every_non_archived_course_page():
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert "if (C.stateOf(c) !== 'archived') load('checklist:' + id);" in co
    assert "if (C.stateOf(c) === 'review') load('checklist:' + id);" not in co


# ───────────── ٦. روابط مقدّم الطلب على بطاقات المدرّبين ─────────────
APP = {'id': 'a1', 'user_name': 'سمر', 'user_email': 'samar@x.test', 'status': 'cancelled', 'join_as': 'trainer', 'created_at': _iso(NOW - 2 * DAY),
       'cancelled_at': _iso(NOW - DAY), 'intro_video_url': 'https://youtu.be/abc', 'cv_url': 'https://x.test/cv.pdf', 'linkedin_url': 'https://linkedin.com/in/samar',
       'contact_phone': '+971500000000', 'expertise': ['عقود']}


@needs_node
def test_app_tickets_carry_the_same_links_and_phone_as_the_decision_card():
    t = _lg('v2s.courses.appTickets', [APP], {'now': NOW})[0]
    assert t['linkList'] == [{'label': 'فيديو الشرح', 'url': 'https://youtu.be/abc'}, {'label': 'السيرة الذاتية', 'url': 'https://x.test/cv.pdf'},
                             {'label': 'لينكدإن', 'url': 'https://linkedin.com/in/samar'}]
    assert t['contact'] == {'label': 'رقم التواصل', 'value': '+971500000000'}
    bad = _lg('v2s.courses.appTickets', [dict(APP, intro_video_url='javascript:alert(1)', cv_url='http://x.test/cv', linkedin_url='data:text/html,x', contact_phone='')], {'now': NOW})[0]
    assert bad['linkList'] == [] and bad['contact'] is None


def test_trainer_ticket_renderers_show_links_and_phone():
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert 'function appLinksHtml' in co and 'target="_blank" rel="noopener noreferrer"' in co
    assert "appChipsHtml(a) + appLinksHtml(a)" in co and "+ appLinksHtml(a) + '</div>' + appVideoActs(a)" in co
    assert '<bdi dir="ltr">' in co.split('function appLinksHtml')[1].split('function appVideoActs')[0]
    assert '.v2co-alinks' in _read('dashboard-cloud', 'v2s', 'courses.css')


# ───────────── عام: لا نقطة وسط جنب رقم في نصوص هذه الجولة ─────────────
def test_new_visible_strings_have_no_latin_digits_or_dot_beside_digits():
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    for new in ('فحص النشر الكامل', 'روابط مقدّم الطلب', 'فيديو الشرح'):
        seg = new
        assert not DOT_DIGIT.search(seg)
    assert not re.search(r"label: '[^']*[0-9]", _read('dashboard-cloud', 'v2-logic.js').split('function appLinkList')[1].split('function appTickets')[0])
    assert 'v2co-alink' in co
