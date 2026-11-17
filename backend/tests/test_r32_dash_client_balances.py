# -*- coding: utf-8 -*-
"""R32 — «أرصدة العملاء» لوحدها في «الفلوس ⇐ نظرة» (قرار المؤسس 2026-11-17 «افصل طبعا دي عن دي… ارصده العملاء»).

Run:  cd backend && python3 -m pytest -q -p no:cacheprovider tests/test_r32_dash_client_balances.py

اللي بيثبّته:
  ١. «مستحق للخبراء والمدرّبين» من `totals` بس (أرباح)، و«أرصدة العملاء» رقم خامس من `clients` — كل عملة لوحدها.
  ٢. «صافي البروفيسور» ما بيتغيّرش بأرصدة العملاء (من نصيب المنصة في كل بيعة بس).
  ٣. منصة قبل R32 (رد من غير `clients`) أو فشل المحافظ ⇒ «غير متاح بعد» بالسبب، مش صفر.
  ٤. القايمة القصيرة: الاسم + المبلغ بعملته + ليه («ملف رقم ١٢») — أرقام عربية بس، ومفيش «·» جنب رقم.
  ٥. الواجهة: الزرار «مين هم؟» بينزل للقايمة، والاسم بيفتح صفحة الشخص.
⛔ صفر شبكة: المنطق في node:vm، والبروكسي نفسه ما اتغيّرش (بيعدّي رد المنصة كما هو).
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
NOW = 1794787200000          # 2026-11-15T00:00:00Z
LATIN = re.compile(r'[A-Za-z0-9]')

OWED = {'ok': True, 'people': 2, 'payouts_pending_count': 1,
        'totals': [{'currency': 'EGP', 'amount': 890, 'on_hold': 90, 'withdrawable': 700, 'payouts_pending': 100, 'people': 2}],
        'clients': {'people': 2, 'more': 0,
                    'totals': [{'currency': 'EGP', 'amount': 750, 'in_wallet': 750, 'payouts_pending': 0, 'people': 1},
                               {'currency': 'SAR', 'amount': 40, 'in_wallet': 40, 'payouts_pending': 0, 'people': 1}],
                    'list': [{'email': 'client@example.com', 'name': 'عميل الملف', 'currency': 'EGP', 'amount': 750,
                              'items': [{'why': 'استرداد مبلغ ملف للخبير', 'amount': 750, 'at': '2026-11-14T00:00:00+00:00', 'file_no': 12}]},
                             {'email': 'both@example.com', 'name': '', 'currency': 'SAR', 'amount': 40,
                              'items': [{'why': 'استرداد 50٪ — إلغاء متأخر', 'amount': 40, 'at': '2026-11-13T00:00:00+00:00'}]}]}}


def _board(src):
    return {x['key']: x for x in v2_node.logic('v2MoneyBoard', dict({'revenues': [], 'escrow': [], 'payouts': []}, **src), 'month', NOW)['numbers']}


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


@needs_node
def test_owed_is_earnings_only_and_clients_is_its_own_number():
    n = _board({'owed': OWED})
    assert n['owed']['text'] == '٨٩٠ ج' and n['owed']['count'] == 2
    c = n['clients']
    assert c['label'] == 'أرصدة العملاء' and c['na'] is False and c['text'] == '٧٥٠ ج و٤٠ ر.س' and c['count'] == 2
    assert c['lines'] == ['٧٥٠ ج', '٤٠ ر.س'], 'كل عملة لوحدها'
    assert 'ليست مستحقة لخبير' in c['note'] and not LATIN.search(c['note'] + c['text'])


@needs_node
def test_net_does_not_move_with_client_balances():
    sale = [{'date': '2026-11-10', 'source': 'course', 'amount_egp': 450, 'amount_usd': 0, 'platform_share': 292.5, 'currency': 'EGP'}]
    with_clients = _board({'revenues': sale, 'owed': OWED})['net']
    no_clients = _board({'revenues': sale, 'owed': dict(OWED, clients={'people': 0, 'totals': [], 'list': []})})['net']
    assert with_clients['text'] == no_clients['text'] == '٢٩٢٫٥٠ ج'


@needs_node
def test_old_platform_or_failure_says_not_available_not_zero():
    old = _board({'owed': {'ok': True, 'people': 1, 'totals': OWED['totals']}})['clients']
    assert old['na'] is True and old['text'] == 'غير متاح بعد' and old['why'] == 'لم تصل أرصدة العملاء من المنصة بعد'
    failed = _board({'owed': None})['clients']
    assert failed['na'] is True and failed['why'] == 'تعذّر جلب المحافظ'
    loading = _board({})['clients']
    assert loading['na'] is True and loading['why'] == 'يُجلب الآن'
    zero = _board({'owed': dict(OWED, clients={'people': 0, 'totals': [], 'list': []})})['clients']
    assert zero['na'] is False and zero['text'] == '٠'


@needs_node
def test_usd_line_names_client_balances_separately():
    b = v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': [], 'owed': OWED, 'rates': {'rates': {'EGP': 50, 'SAR': 4}, 'date': '2026-11-15'}}, 'month', NOW)
    assert 'مستحق ١٨ دولار' in b['usdLine']['text'] and 'أرصدة العملاء ٢٥ دولار' in b['usdLine']['text']


@needs_node
def test_client_rows_name_amount_and_why_in_arabic_digits():
    r = v2_node.logic('v2ClientRows', OWED, NOW)
    assert r['more'] == 0 and len(r['rows']) == 2
    a, b = r['rows']
    assert a['name'] == 'عميل الملف' and a['email'] == 'client@example.com' and a['amountText'] == '٧٥٠ ج'
    assert a['why'] == 'استرداد مبلغ ملف للخبير، ملف رقم ١٢' and a['when'].startswith('منذ ')
    assert b['name'] == 'both@example.com' and b['amountText'] == '٤٠ ر.س' and b['why'] == 'استرداد ٥٠٪ — إلغاء متأخر'
    for x in r['rows']:
        assert '·' not in x['why'] and not re.search(r'[0-9]', x['why'] + x['amountText'])
    assert v2_node.logic('v2ClientRows', {'ok': True, 'totals': []}, NOW) is None
    assert v2_node.logic('v2ClientBalances', None) is None


def test_ui_wires_the_tile_to_the_list_and_people_pages():
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    assert 'data-a="clients"' in d3 and "q('#v3-clients', v)" in d3 and 'clientsSection(t)' in d3
    assert 'personLink(r.name, r.email)' in d3, 'الاسم بيفتح صفحة الشخص (نفس رابط الناس)'
    css = _read('dashboard-cloud', 'v2-d3.css')
    assert 'repeat(5,minmax(0,1fr))' in css and '.v3-num.k-clients' in css
