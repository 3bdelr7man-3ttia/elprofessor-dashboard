# -*- coding: utf-8 -*-
"""r27 — تعديلات من تجربة مدرّب حقيقي (2026-11-15): فحص النشر بالعربي · الشريط والشارة والأعمدة بتتحدّث مع بعض · الصورة · الأسعار · صفحة الشخص.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r27_dash_e2e.py

⛔ صفر شبكة: المنطق في node على الملفات الحقيقية، وردود المنصة جدول في الذاكرة.
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ROOT = os.path.dirname(os.path.dirname(_HERE))
NOW = 1793000000000
LATIN = re.compile(r'[A-Za-z]')


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


def _co(fn, *args):
    return v2_node.logic('v2s.courses.' + fn, *args)


# ───────────── ١. فحص النشر: لا مفتاح إنجليزي يتعرض أبدًا ─────────────
# الشكل الحقيقي لردّ جسر المنصة: {key, group, label, ok, detail} (مفيش `item`)
BRIDGE = {'course_id': 'c1', 'slug': 'x', 'sale_block_reason': '', 'all_ok': False, 'checklist': [
    {'key': 'content', 'group': 'publish', 'label': 'فيها محتوى', 'ok': True, 'detail': ''},
    {'key': 'outcomes', 'group': 'publish', 'label': 'نواتج التعلّم مذكورة', 'ok': True, 'detail': ''},
    {'key': 'intro_video', 'group': 'publish', 'label': 'فيديو تعريفي مرفوع', 'ok': False, 'detail': 'لم يُرفع فيديو'},
    {'key': 'level', 'group': 'publish', 'label': 'مستوى الدورة محدّد', 'ok': True, 'detail': ''},
    {'key': 'pricing', 'group': 'publish', 'label': 'التسعير سليم', 'ok': True, 'detail': ''},
    {'key': 'agreement', 'group': 'publish', 'label': 'صاحب الدورة وقّع الاتفاقية', 'ok': True, 'detail': ''},
]}
COURSE = {'id': 'c1', 'title': 'عقود', 'type': 'recorded_paid', 'approval_status': 'pending', 'price_amount': 480, 'price_currency': 'EGP', 'lesson_count': 9,
          'platform_owned': False, 'agreement_signed': True}


@needs_node
def test_real_bridge_shape_shows_arabic_labels_and_detail():
    f = _co('courseFacts', COURSE, {'now': NOW, 'checklist': BRIDGE})
    labels = [i['label'] for i in f['items']] + [i['pos'] for i in f['items']]
    assert not [x for x in labels if LATIN.search(x)], labels
    assert not LATIN.search(f['line']) and not LATIN.search(f['returnNote'])
    assert 'ينقصها: فيديو تعريفي مرفوع (لم يُرفع فيديو)' in f['line']
    assert f['suggestion'] == 'return' and f['missing'] == ['فيديو تعريفي مرفوع (لم يُرفع فيديو)']


@needs_node
def test_no_english_key_can_ever_render_even_with_bare_or_english_labels():
    keys = ['content', 'outcomes', 'intro_video', 'level', 'pricing', 'agreement', 'sellable', 'start_date', 'price_decision', 'zoom', 'something_new']
    for shape in ({}, {'label': 'intro_video'}, {'item': 'intro_video'}, {'label': 'Intro Video', 'detail': 'missing file'}):
        cl = {'checklist': [dict(shape, key=k, ok=False) for k in keys], 'all_ok': False, 'sale_block_reason': 'blocked_by_admin'}
        f = _co('courseFacts', COURSE, {'now': NOW, 'checklist': cl})
        everything = [i['label'] for i in f['items']] + [i['pos'] for i in f['items']] + f['missing'] + [f['line'], f['returnNote']]
        assert not [x for x in everything if LATIN.search(x)], (shape, everything)
    f = _co('courseFacts', COURSE, {'now': NOW, 'checklist': {'checklist': [{'key': 'intro_video', 'ok': False}, {'key': 'level', 'ok': False}, {'key': 'sellable', 'ok': False}], 'sale_block_reason': ''}})
    assert 'ينقصها: فيديو تعريفي، المستوى، صالحة للبيع' in f['line']


def test_other_course_surfaces_never_print_a_raw_key():
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert 'esc(i.key)' not in co and 'esc(x.key)' not in co.replace("x.key === 'eg'", '')
    assert 'typeLabel: TYPE_LABEL[c.type] || checkText(c.type)' in _read('dashboard-cloud', 'v2-logic.js')


# ───────────── ٢+٣. الشريط والشارة والأعمدة وعدّاد المدرّبين بيتحدّثوا مع بعض ─────────────
def _ok(body):
    return {'status': 200, 'body': body}


def _platform(courses, pending_items, apps):
    return {
        '/api/platform-ops-queue': _ok({'courses_pending': {'count': len(pending_items), 'titles': [x['title'] for x in pending_items], 'items': pending_items}, 'live_needs_decision': []}),
        '/api/platform-courses': _ok({'courses': courses}),
        '/api/platform-trainer-applications': _ok({'applications': apps}),
        '/api/platform-experts': _ok({'experts': []}),
        '/api/platform-schedules': _ok({'schedules': []}),
        '/api/inbox': _ok({'rows': []}),
    }


def _refresh_run(initial, later):
    proc = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'r27_refresh.js')], input=json.dumps({'initial': initial, 'later': later}, ensure_ascii=False),
                          capture_output=True, text=True, timeout=60)
    out = json.loads(proc.stdout)
    assert 'error' not in out, out.get('error')
    return out


C_BUILD = {'id': 'c9', 'slug': 'new-c', 'title': 'دورة المدرّب الجديدة', 'type': 'recorded_paid', 'approval_status': 'draft', 'is_active': False, 'lesson_count': 3,
           'price_amount': 450, 'price_currency': 'EGP', 'instructor_name': 'أ. سلمى', 'instructor_email': 's@x.test'}
C_REVIEW = dict(C_BUILD, approval_status='pending', submitted_at='2026-11-15T08:00:00+00:00')
APP = {'id': 'a1', 'status': 'pending', 'name': 'سلمى', 'email': 's@x.test', 'join_as': 'trainer', 'expertise': ['تسويق']}
ITEM = {'id': 'c9', 'slug': 'new-c', 'title': 'دورة المدرّب الجديدة', 'instructor_name': 'أ. سلمى', 'submitted_at': '2026-11-15T08:00:00+00:00'}


@needs_node
def test_strip_badge_columns_and_trainer_count_refresh_together_without_reload():
    out = _refresh_run(_platform([C_BUILD], [], [APP]), _platform([C_REVIEW], [ITEM], []))
    b, a = out['before'], out['after']
    # قبل: لا شيء مستنّي، وعدّاد المدرّبين ١
    assert b['strip_n'] == 0 and b['counts_courses'] == 0
    assert 'طلبات انضمام جديدة: ١' in b['html']
    # بعد تقديم الدورة وقبول المدرّب (والتبويب لسه مفتوح): الشريط = الشارة = العدّاد = عمود «في المراجعة» = ١، والمدرّبون ٠
    assert a['strip_n'] == 1 == a['counts_courses'] == a['tile_count'], a
    assert 'دورة المدرّب الجديدة' in a['html'] and 'القرار في «محتاج قرارك» فوق' in a['html']
    assert 'طلبات انضمام جديدة: ٠' in a['html'] and 'طلبات انضمام جديدة: ١' not in a['html']
    # تحديث صامت: المصدر ما دخلش «جارٍ التحميل» (لا وميض)
    assert out['states']['opsQueue'] == 'ready'
    for u in ('/api/platform-ops-queue', '/api/platform-courses', '/api/platform-trainer-applications?status=pending'):
        assert u in out['calls'], (u, out['calls'])


@needs_node
def test_refresh_wiring_and_throttle_are_in_the_sources():
    home = _read('dashboard-cloud', 'v2-home.js')
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    # بعد أي قرار (publish/return/accept) كل حاجة بتتحدّث مع بعض
    assert re.search(r"function reload\(\)[^\n]*V2CO\.refresh\(true, true\)", home)
    assert 'CO.refresh(true, true);' in co and 'afterCourseWrite' in co
    # الدخول للقسم + كل ٤٥ ثانية + الرجوع للتبويب
    assert 'CO.refresh(false);' in co and 'setInterval(autoRefresh, 45000)' in home and 'visibilitychange' in home
    # الشارة والشريط من نفس opsQueue، فتحديثه الصامت هو تحديثهما
    assert 'EP.refresh = function' in _read('dashboard-cloud', 'dashboard-api.js')


