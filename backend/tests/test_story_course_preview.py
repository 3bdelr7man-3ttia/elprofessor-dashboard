# -*- coding: utf-8 -*-
"""طلب المؤسس (2026-10-15): «عايزين معاينة من الداش بورد».

Run:  cd backend && python3 -m pytest -q tests/test_story_course_preview.py

الدورة التفاعلية («قصة») دروسها في ملف الدورة مش في المنهج، فالكارت كان بيقول «· درس» و«لا محاضرات
ولا دروس بعد» لدورة فيها ٣٩ درس، ومن غير أي طريق للمعاينة. ما يثبّته الملف ده:
  ١. الجسر بيبعت `story: {units, lessons, minutes}` والكارت بيعرضه بدل العدّاد الفاضي.
  ٢. زرار «معاينة» بيفتح ‎app.elprofessor.net/?page=admincourses&preview=<slug>‎ في تاب جديد —
     المنصة بتفتح المعاينة على طول (AdminCourses.jsx · previewSlugFromSearch).
  ٣. الزرار للدورات التفاعلية بس، و«المنهج والمحاضرات» ما بيظهرش لها (ملهاش منهج قديم).
  ٤. «story-seed» ما يظهرش كاسم تقني في الشاشة.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_REPO, 'dashboard-cloud', 'index.html')


def _idx():
    return open(INDEX, encoding='utf-8').read()


def _fn(src, name):
    m = re.search(r'function ' + name + r'\(c\)\{.*?\}\n', src)
    assert m, name
    return m.group(0)


@pytest.mark.skipif(shutil.which('node') is None, reason='node غير موجود')
def test_story_helpers_behave():
    src = _idx()
    js = _fn(src, 'pcStory') + _fn(src, 'pcPreviewUrl') + r"""
const out = {
  story: pcStory({story: {units: 7, lessons: 39, minutes: 153}}),
  none: pcStory({story: null}),
  empty: pcStory({story: {units: 0, lessons: 0, minutes: 0}}),
  missing: pcStory({}),
  url: pcPreviewUrl({slug: 'marketing-basics'}),
};
console.log(JSON.stringify(out));
"""
    r = subprocess.run(['node', '-e', js], capture_output=True, text=True, timeout=20)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out['story'] == {'units': 7, 'lessons': 39, 'minutes': 153}
    assert out['none'] is None and out['empty'] is None and out['missing'] is None
    assert out['url'] == 'https://app.elprofessor.net/?page=admincourses&preview=marketing-basics'


def test_drawer_shows_preview_and_story_counts():
    src = _idx()
    assert 'href="${esc(pcPreviewUrl(c))}" target="_blank" rel="noopener"' in src
    assert '${svg(\'book\')}معاينة</a>' in src
    assert '${sty&&c.slug?' in src                              # للدورات التفاعلية بس
    assert 'درس · ${money(sty.units)} أجزاء · حوالي ${money(sty.minutes)} دقيقة' in src
    # الدورة التفاعلية ملهاش منهج قديم: لا زرار «المنهج والمحاضرات» ولا تحميل للفيديوهات.
    assert "${sty?'':`<button class=\"btn btn-human\" data-a=\"pcvideo\"" in src
    assert 'if(window.EP&&c.id&&!sty){EP.loadCourseVideos' in src
    # عدّاد الصفّ في القائمة بيعدّ دروس الدورة التفاعلية.
    assert 'var lessons=pcStory(c)?pcStory(c).lessons:(c.lesson_count||0);' in src


def test_no_technical_source_name_on_screen():
    src = _idx()
    assert "'story-seed':'دورة تفاعلية'" in src
