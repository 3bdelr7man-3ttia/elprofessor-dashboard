# -*- coding: utf-8 -*-
"""R16 بطاقة «آخر تشغيل للعقل» في الواجهة: منطق نقي (`V2L.v2sBrainRunCard`) + فحوص ثابتة على v2s/brain.js.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_run_status_ui.py
"""
import os
import re
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
NOW = 1793361600000          # 2026-10-30T12:00:00Z


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _sw(**over):
    d = {'switches': [], 'writer': 'main', 'brain_today': {'used': 2, 'cap': 60},
         'autorun': {'on': True, 'next_at': '2026-10-30T18:00:00Z', 'hours': [9, 20]}, 'writes_on': True}
    d.update(over)
    return v2_node.logic('v2sBrainSwitches', d, NOW)


def card(run_resp, sw):
    return v2_node.logic('v2sBrainRunCard', run_resp, sw, NOW)


REPORT = {'state': 'partial', 'trigger_text': 'تلقائيًا', 'headline': 'عمل العقل وكتب كتابتين، وتعذّر جزء.',
          'done': ['«مسودات الرد على الرسائل»: كتب اقتراحين تنتظر قرارك.'],
          'failed': ['«مراجعة الدورة قبل النشر»: تعذّرت قراءة بياناته من المنصة الآن.'], 'fix': ''}


@needs_node
def test_card_shows_the_server_lines_as_is_and_the_button():
    c = card({'run': {'started_at': '2026-10-30T09:00:00Z', 'finished_at': '2026-10-30T09:01:00Z', 'active': False, 'report': REPORT}}, _sw())
    assert c['known'] is True and c['state'] == 'partial' and c['tone'] == 'warn'
    assert c['when'] == 'آخر تشغيل: منذ ٢ ساعات، تلقائيًا' or c['when'].startswith('آخر تشغيل: منذ ')
    assert c['done'] == REPORT['done'] and c['failed'] == REPORT['failed'] and c['headline'] == REPORT['headline']
    assert c['canRun'] is True and c['reason'] == ''
    assert c['auto'].startswith('التشغيل التلقائي القادم: ') and 'الساعة' in c['auto']


@needs_node
def test_card_before_any_run_and_unknown_source():
    c = card({'run': None}, _sw())
    assert c['when'] == 'لم يعمل العقل بعد' and 'شغّل الآن' in c['headline'] and c['canRun'] is True
    u = card(None, _sw())
    assert u['known'] is False and u['when'] == 'غير متاح بعد' and u['failed'] == [], 'مصدر لم يصل ⇒ لا جملة مخترعة'


@needs_node
def test_missing_key_is_named_with_its_place_even_before_a_run():
    fix = {'text': 'لا يوجد مفتاح موديل يكتب به العقل، فلم يُكتب شيء.', 'where': 'من قسم «العقل» افتح تبويب «المساعدون»…'}
    c = card({'run': None}, _sw(writer=None, writer_fix=fix))
    assert c['canRun'] is False and c['reason'] == 'لا كاتب مفعّل الآن'
    assert c['failed'] == [fix['text']] and c['where'] == fix['where'] and c['tone'] == 'bad'
    # التقرير نفسه ذكر المكان ⇒ لا تكرار
    rep = dict(REPORT, state='failed', failed=[fix['text']], fix=fix['where'], done=[])
    c2 = card({'run': {'started_at': '2026-10-30T11:00:00Z', 'finished_at': '2026-10-30T11:00:05Z', 'report': rep}}, _sw(writer=None, writer_fix=fix))
    assert c2['fix'] == fix['where'] and c2['where'] == ''


@needs_node
def test_running_and_server_writes_off():
    c = card({'run': {'started_at': '2026-10-30T11:58:00Z', 'finished_at': None, 'active': True,
                      'report': {'state': 'running', 'headline': 'العقل يعمل الآن.', 'done': [], 'failed': [], 'fix': ''}}}, _sw())
    assert c['state'] == 'running' and c['canRun'] is False and c['tone'] == 'run'
    off = card({'run': None}, _sw(writes_on=False))
    assert off['canRun'] is False and off['reason'] == 'كتابة العقل موقوفة من إعداد الخادم'
    stopped = card({'run': None}, _sw(autorun={'on': False, 'next_at': None}))
    assert stopped['auto'] == 'التشغيل التلقائي متوقّف'


def test_brain_js_renders_the_card_with_run_now():
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    assert 'function runCard()' in js and "L.v2sBrainRunCard(" in js
    assert "+ runCard() + seg +" in js, 'البطاقة فوق القواعد والسجل'
    assert "data-a=\"runnow\"" in js and "'شغّل الآن'" in js and 'آخر تشغيل للعقل' in js
    assert "a === 'gokeys'" in js and "openSection('brain', 'helpers')" in js
    assert "a === 'retry-run'" in js


def test_new_ui_strings_follow_the_copy_rules():
    js = _read('dashboard-cloud', 'v2s', 'brain.js')
    start, end = js.index('function runCard()'), js.index('function drawRules(v)')
    logic = _read('dashboard-cloud', 'v2-logic.js')
    ls, le = logic.index('function brStrList('), logic.index('// قرصا المساعدين الجديدان.')
    for chunk, latin in ((js[start:end], False), (logic[ls:le], True)):
        arabic = re.findall(r"'([^'\n]*[\u0600-\u06FF][^'\n]*)'", chunk)
        assert arabic
        for s in arabic:
            assert 'يقوّم' not in s and 'استشار' not in s and '·' not in s and not s.startswith('الذكاء'), s
            if latin:      # الجمل النقية (بلا وسوم HTML) بلا حروف لاتينية
                assert not re.search(r'[A-Za-z]', s), s
