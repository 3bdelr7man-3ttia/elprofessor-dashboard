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


# ───────────── ٤. صورة غلاف الدورة: المسار النسبي يتحلّ على عنوان المنصة ─────────────
@needs_node
def test_relative_cover_resolves_against_the_platform_and_unsafe_ones_fall_back_to_the_letter():
    f = lambda u: v2_node.logic('util.platformAsset', u)
    assert f('/covers/law-1.jpg') == 'https://app.elprofessor.net/covers/law-1.jpg'
    assert f('covers/law-1.jpg') == 'https://app.elprofessor.net/covers/law-1.jpg'
    assert f('./covers/law-1.jpg') == 'https://app.elprofessor.net/covers/law-1.jpg'
    assert f('https://cdn.example.test/a.png') == 'https://cdn.example.test/a.png'
    assert f('//cdn.example.test/a.png') == 'https://cdn.example.test/a.png'
    for bad in ('', None, '   ', 'javascript:alert(1)', 'data:image/png;base64,AAAA', 'http://x.test/a.png', 'a b.png'):
        assert f(bad) == '', bad
    m = _co('pageModel', dict(COURSE, thumbnail_url='/covers/law-1.jpg'), None, None, None, None, {'now': NOW})
    assert m['hero'] == 'https://app.elprofessor.net/covers/law-1.jpg'
    assert _co('pageModel', dict(COURSE, thumbnail_url=''), None, None, None, None, {'now': NOW})['hero'] == ''


@needs_node
def test_the_editor_accepts_a_preset_relative_cover_but_not_a_plain_http_one():
    ci = lambda u: v2_node.logic('courses2.coverIssue', u)
    assert ci('/covers/law-1.jpg') == '' and ci('https://x.test/a.png') == '' and ci('') == ''
    assert ci('http://x.test/a.png') and ci('//x.test/a.png') and ci('javascript:x')


def test_cover_surfaces_use_the_resolver_and_a_broken_hero_falls_back():
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert 'U.platformAsset(c.thumbnail_url)' in co and "classList.contains('v2co-himg')" in co and "t.src = img('courses')" in co


# ───────────── ٥. ورقة «انشر الدورة»: نفس ملخّص أسعار صفحة الدورة ─────────────
@needs_node
def test_publish_sheet_price_row_matches_the_course_page_summary():
    prices = {'eg': 450, 'sa': 99, 'default': 25}
    line = v2_node.logic('util.coursePricesLine', dict(COURSE, prices=prices))
    assert line == 'السعودية ٩٩ ر.س، باقي البلاد ٢٥ دولار'
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert "' — بره مصر: ' + U.coursePricesLine(c)" in co
    # صفحة الدورة نفسها بتستعمل نفس الدالة
    assert _co('pageModel', dict(COURSE, prices=prices), None, None, None, None, {'now': NOW})['tiles']['priceOthers'] == line


# ───────────── ٦. صفحة الشخص: بلد التسجيل · روابط ورقم مقدّم الطلب · رابط «اطّلع» حقيقي ─────────────
HALA = 'trainer.new@example.test'


def _built(**S):
    import app as appmod
    base = {k: None for k in ('users', 'invites', 'experts', 'courses', 'files', 'payouts_pending', 'payouts_paid', 'pending', 'enrollments', 'req_signups', 'req_trainer')}
    user = {'email': HALA, 'full_name': 'سلمى', 'id': 'u1', 'created_at': '2026-11-14T00:00:00Z', 'is_active': True, 'role': 'user'}
    base.update(users={'users': [user]}, pending={'users': []}, invites=[])
    base.update(S)
    return appmod._v2_person_build(HALA, base)


def test_person_country_falls_back_to_the_signup_country(ctx=None):
    out = _built(req_signups={'signups': [{'email': HALA, 'user_id': 'u1', 'country': 'EG', 'created_at': '2026-11-14T00:00:00Z'}]})
    assert out['identity']['country'] == 'EG'
    assert _built(req_signups={'signups': [{'email': 'other@example.test', 'country': 'SA'}]})['identity']['country'] is None
    # بلد الحساب نفسه (لو موجود) يسبق بلد التسجيل
    u = {'email': HALA, 'full_name': 'سلمى', 'id': 'u1', 'is_active': True, 'country': 'AE'}
    assert _built(users={'users': [u]}, req_signups={'signups': [{'email': HALA, 'country': 'EG'}]})['identity']['country'] == 'AE'


@needs_node
def test_person_page_shows_the_country_with_flag_and_name():
    resp = {'email': HALA, 'found': True, 'sources': {}, 'roles': [], 'identity': {'name': 'سلمى', 'country': 'EG', 'is_active': True}, 'log': [], 'requests': []}
    assert v2_node.logic('v2Person', resp, NOW, HALA)['countryText'] == '\U0001F1EA\U0001F1EC مصر'
    resp['identity']['country'] = None
    assert v2_node.logic('v2Person', resp, NOW, HALA)['countryText'] == 'غير متاح بعد'
    resp['identity']['country'] = 'مصر'
    assert v2_node.logic('v2Person', resp, NOW, HALA)['countryText'] == 'مصر'


def test_person_requests_carry_cv_video_and_phone_only_over_https():
    app_row = {'id': 'a1', 'user_email': HALA, 'user_name': 'سلمى', 'created_at': '2026-11-14T10:00:00Z', 'join_as': 'trainer', 'headline': 'محامية',
               'cv_url': 'https://files.example.test/cv.pdf', 'intro_video_url': 'javascript:alert(1)', 'contact_phone': '+201001112223'}
    out = _built(req_trainer={'applications': [app_row]})
    tr = [r for r in out['requests'] if r['kind'] == 'trainer'][0] if 'requests' in out else None
    if tr is None:      # الطلبات بتتجمّع في `_v2_person_requests` منفصلة عن `_v2_person_build`
        import app as appmod
        tr = [r for r in appmod._v2_person_requests(HALA, {'req_trainer': {'applications': [app_row]}})[0] if r['kind'] == 'trainer'][0]
    assert tr['cv_url'] == 'https://files.example.test/cv.pdf' and tr['intro_video_url'] == '' and tr['contact_phone'] == '+201001112223'


@needs_node
def test_trainer_card_shows_links_phone_and_a_real_person_link():
    row = {'apiKind': 'trainer', 'apiId': 'a1', 'who': 'سلمى', 'personEmail': HALA, 'ref': 'TRN-a1', 'trJoin': 'trainer', 'trHeadline': 'محامية', 'canReject': True,
           'trVideo': 'https://youtu.be/abc', 'trCv': 'https://files.example.test/cv.pdf', 'trLi': 'https://linkedin.com/in/salma', 'trPhone': '+201001112223'}
    c = v2_node.logic('v2Card', row, {'now': NOW})
    assert [(x['label'], x['url']) for x in c['links']] == [('فيديو الشرح', 'https://youtu.be/abc'), ('السيرة الذاتية', 'https://files.example.test/cv.pdf'), ('لينكدإن', 'https://linkedin.com/in/salma')]
    assert c['contact'] == {'label': 'رقم التواصل', 'value': '+201001112223'}
    assert c['read'] == {'label': 'اطّلع على الطلب كاملًا', 'act': {'do': 'person', 'email': HALA}} and not c.get('reason')
    # غياب الحقول ⇒ لا شيء (لا رابط ميّت ولا سطر فاضي)
    bare = v2_node.logic('v2Card', dict(row, trVideo='', trCv='', trLi='', trPhone=''), {'now': NOW})
    assert bare['links'] == [] and bare['contact'] is None
    # رابط غير آمن ⇒ يُسقَط
    evil = v2_node.logic('v2Card', dict(row, trVideo='javascript:alert(1)', trCv='http://x.test/cv', trLi='http://linkedin.com/in/x'), {'now': NOW})
    assert evil['links'] == []
    # بلا بريد ⇒ لا نص-يشبه-رابط
    nomail = v2_node.logic('v2Card', dict(row, personEmail='', email=''), {'now': NOW})
    assert not nomail.get('read') and not nomail.get('reason')


def test_strip_renders_links_in_a_new_tab_and_the_phone():
    s = _read('dashboard-cloud', 'v2-strip.js')
    assert 'target="_blank" rel="noopener noreferrer">\' + esc(x.label)' in s and 'contactHtml(c' in s


# ───────────── ٧. رسالة نجاح القبول ─────────────
def test_accept_toast_has_no_emoji_or_tick():
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert '"اعتُمد الطلب" : "رُفض الطلب"' in api and 'تم الاعتماد ✓' not in api
    html = _read('dashboard-cloud', 'index.html')
    assert "toast((window.V2SHELL&&window.V2SHELL.on?'':'📩 ')+msg)" in html
