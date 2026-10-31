# -*- coding: utf-8 -*-
"""«اسألني على تليجرام» في شاشة العقل: منطق الصفوف وورقة التأكيد (node) + ربط المفتاح في `v2s/brain.js` (ثابت).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_telegram_ui.py
"""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
NOW = 1793354400000
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')


def _p(pid, kind='draft', **kw):
    d = {'id': pid, 'section': 'people', 'kind': kind, 'label': 'عنوان الصف', 'sentence': 'جملة.', 'lock_reason': 'قفل.',
         'may_run_alone': kind != 'draft', 'mode': 'ask', 'updated_at': None, 'updated_by': ''}
    d.update(kw)
    return d


def _rows(*items):
    r = v2_node.logic('v2sBrainSwitches', {'switches': list(items), 'writer': 'main', 'brain_today': {'used': 1, 'cap': 60}}, NOW)
    return {x['id']: x for x in r['rows']}


@needs_node
def test_rows_expose_the_telegram_toggle_only_when_the_server_declares_it():
    rows = _rows(
        _p('file_review', telegram=True, telegram_ok=True, telegram_can_toggle=True),
        _p('market_match', telegram=False, telegram_ok=False, telegram_can_toggle=True),
        _p('opinion', kind='opinion', mode='alone', telegram=False, telegram_ok=False, telegram_can_toggle=False),
        _p('old_server'))                                     # خادم قديم بلا الحقول ⇒ لا مفتاح
    assert (rows['file_review']['tgToggle'], rows['file_review']['telegram'], rows['file_review']['tgOk']) == (True, True, True)
    assert (rows['market_match']['tgToggle'], rows['market_match']['telegram'], rows['market_match']['tgOk']) == (True, False, False)
    assert rows['opinion']['tgToggle'] is False and rows['opinion']['telegram'] is None
    assert rows['old_server']['tgToggle'] is False and rows['old_server']['telegram'] is None
    assert _rows(_p('x', telegram='yes', telegram_can_toggle=True))['x']['tgToggle'] is False, 'قيمة غير منطقية لا تُعرض'


@needs_node
def test_telegram_confirm_sheet_texts():
    rows = _rows(_p('file_review', telegram=False, telegram_ok=True, telegram_can_toggle=True),
                 _p('market_match', telegram=False, telegram_ok=False, telegram_can_toggle=True))
    s = lambda i, on: v2_node.logic('v2sBrainTelegramSheet', rows[i], on)
    on_ok, on_link, off = s('file_review', True), s('market_match', True), s('file_review', False)
    assert on_ok['go'] == 'نعم، اسألني' and 'تعتمده أو ترفضه من هناك' in on_ok['lead']
    assert 'الرابط فقط' in on_link['lead'] and 'تعتمده' not in on_link['lead'], 'لا وعد باعتماد من تليجرام لمنتج لا يسمح به'
    assert off['go'] == 'نعم، أوقفه' and 'لا يرسل' in off['lead']
    for x in (on_ok, on_link, off):
        assert x['title'] and not re.search(r'[A-Za-z]', x['lead'] + x['go'])


def test_brain_js_wires_the_toggle_to_the_switches_route_with_confirmation():
    js = open(os.path.join(ROOT, 'dashboard-cloud', 'v2s', 'brain.js'), encoding='utf-8').read()
    assert 'data-a="tg"' in js and 'role="switch"' in js and "a === 'tg'" in js
    assert "body: { telegram: on, confirmed: true }" in js and "method: 'PUT'" in js
    assert 'L.v2sBrainTelegramSheet' in js
