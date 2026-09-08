# -*- coding: utf-8 -*-
"""F-134/ب — دورة الإدارة تحمل مالكها قبل ما تتنشر (قرار المؤسس 2026-09-08).

الداشبورد ينشئ الدورة ويعكسها على المنصّة (`POST /api/bridge/courses`). لو راحت بلا
`instructor_email` تولد على المنصّة **بلا مالك**: المدرّب لا يفتح مسوّدتها ولا يضيف حلقاتها
ولا يشوف دفعتها (الملكية بالبريد وحده — F-134). فالشرط هنا: بريد صالح، أو قرار صريح
«دورة من المنصّة نفسها» (`platform_owned`).

المُثبَّت أدناه:
  ١) `POST /api/courses` بلا بريد وبلا العلَم ⇒ ٤٠٠ بالعربي الأبيض، ولا صفَّ يُكتب؛
  ٢) تمرّ بالبريد وحده، وتمرّ بالعلَم وحده — والبريد يسافر للمنصّة مقصوصًا بحروف صغيرة؛
  ٣) اسمٌ في خانة البريد ليس بريدًا (الفخّ الحقيقي في الفورم)؛
  ٤) نفس الشرط على «انشر على المنصّة» المتأخّر وعلى توليد Titch؛
  ٥) وحارس «مكتوبٌ ولا طريقَ له»: الفورم نفسه يبعت الحقلين فعلًا.

Run:  cd backend && python3 -m pytest -q tests/test_f134b_course_owner_required.py
"""
import datetime
import json
import os
import shutil
import subprocess

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, Course, User  # noqa: E402

DASH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'dashboard-cloud')
MSG = 'اكتب بريد المدرّب صاحب الدورة — أو علّم «دورة من المنصّة»'


def _bearer(user):
    tok = jwt.encode({'user_id': user.id,
                      'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture()
def ctx(monkeypatch):
    with flask_app.app_context():
        db.create_all()
        user = User.query.filter_by(email='f135-admin@x.test').first()
        if not user:
            user = User(email='f135-admin@x.test',
                        password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
                        name='أدمن', role='admin', dashboard_role='admin',
                        linked_to_name='', preferred_currency='AUTO', is_active=True)
            db.session.add(user)
            db.session.commit()
        sent = []

        # ⛔ لا شبكة من الطقم: نمسك المرآة نفسها ونقرأ ما كانت هترسله للمنصّة.
        def fake_mirror(course, owner=None):
            sent.append({'course': course, 'owner': dict(owner or {})})
            return {'id': 'CRS_TEST', 'slug': 'test-slug'}

        monkeypatch.setattr('app._platform_create_course', fake_mirror)
        yield {'client': flask_app.test_client(), 'head': _bearer(user), 'sent': sent}


def _create(ctx, **body):
    payload = {'title': 'دورة الإدارة', 'trainer_name': 'أ. منى', 'price_egp': 500}
    payload.update(body)
    return ctx['client'].post('/api/courses', json=payload, headers=ctx['head'])


# ═════════════════════════════════════ ١) بلا مالك = مرفوضة، ولا صفَّ يُكتب
def test_create_without_an_owner_is_refused_in_plain_arabic(ctx):
    before = Course.query.count()
    r = _create(ctx, title='دورة يتيمة')
    assert r.status_code == 400, r.get_data(as_text=True)[:300]
    assert r.get_json()['error'] == MSG
    assert Course.query.count() == before, 'الصفّ اتكتب رغم الرفض'
    assert ctx['sent'] == [], 'اتبعت للمنصّة رغم الرفض'


@pytest.mark.parametrize('bad', ['', '   ', 'أ. منى', 'mona', 'mona@', 'mona@ex'])
def test_a_name_in_the_email_box_is_not_an_owner(ctx, bad):
    r = _create(ctx, instructor_email=bad)
    assert r.status_code == 400 and r.get_json()['error'] == MSG


# ═════════════════════════════════════ ٢) تمرّ بالبريد، أو بقرار «دورة من المنصّة»
def test_create_with_a_trainer_email_passes_and_travels_lowercased(ctx):
    r = _create(ctx, instructor_email='  Mona@Example.COM  ')
    assert r.status_code == 201, r.get_data(as_text=True)[:300]
    assert r.get_json()['platform_published'] is True
    owner = ctx['sent'][-1]['owner']
    assert owner['instructor_email'] == 'mona@example.com'
    assert owner['platform_owned'] is False


def test_create_with_the_platform_owned_flag_passes_with_no_email(ctx):
    r = _create(ctx, platform_owned=True, instructor_email='')
    assert r.status_code == 201
    owner = ctx['sent'][-1]['owner']
    assert owner['platform_owned'] is True and owner['instructor_email'] == ''


def test_the_flag_wins_over_a_leftover_email_so_the_two_never_travel_together(ctx):
    """الخانة تتقفل وتتفضّى في الواجهة؛ ولو وصل الاتنين، العلَم هو القرار."""
    r = _create(ctx, platform_owned=True, instructor_email='mona@example.com')
    assert r.status_code == 201
    assert ctx['sent'][-1]['owner'] == {'platform_owned': True, 'instructor_email': ''}


# ═════════════════════════════════════ ٣) نفس الشرط على النشر المتأخّر والتوليد
def test_publishing_an_existing_course_later_needs_the_same_owner(ctx):
    r = _create(ctx, title='دورة دفترية', publish_to_platform=False)
    assert r.status_code == 201
    course_id = r.get_json()['id']
    late = ctx['client'].post('/api/courses/%d/publish-platform' % course_id,
                              json={}, headers=ctx['head'])
    assert late.status_code == 400 and late.get_json()['error'] == MSG
    ok = ctx['client'].post('/api/courses/%d/publish-platform' % course_id,
                            json={'instructor_email': 'Mona@Ex.com'}, headers=ctx['head'])
    assert ok.status_code == 200 and ctx['sent'][-1]['owner']['instructor_email'] == 'mona@ex.com'


def test_titch_generation_is_refused_without_an_owner_before_any_ai_call(ctx):
    """التوليد إنشاءُ دورة كذلك — والرفض هنا يوفّر نداء ذكاءٍ كان هيتحرق ثم يُرفض على المنصّة."""
    r = ctx['client'].post('/api/platform-courses/generate',
                           json={'title': 'دورة العقود', 'material': 'نص'}, headers=ctx['head'])
    assert r.status_code == 400 and r.get_json()['error'] == MSG


# ═════════════════════════════════════ ٤) مكتوبٌ ولا طريقَ له؟ الفورم يبعت الحقلين فعلًا
def _read(name):
    with open(os.path.join(DASH, name), encoding='utf-8') as fh:
        return fh.read()


def test_the_course_form_actually_sends_the_owner_fields():
    html = _read('index.html')
    assert 'id="m_email"' in html and 'id="m_plat"' in html, 'الخانة/العلَم مش في الفورم'
    assert 'بريد المدرّب صاحب الدورة' in html and 'دورة من المنصّة نفسها' in html
    # الإرسال نفسه — في نداء الإنشاء وفي نداء التوليد (مش مجرّد تعريف خانة).
    assert html.count('instructor_email:own.instructor_email,platform_owned:own.platform_owned') == 2


def test_the_api_layer_refuses_an_ownerless_course_call():
    js = _read('dashboard-api.js')
    assert 'courseOwnerDeclared' in js
    # createCourse + generateCourse + publishCourseToPlatform — كل باب يخلق دورة على المنصّة.
    assert js.count('if (!courseOwnerDeclared(') == 3


def test_the_publish_button_opens_the_owner_modal_instead_of_calling_blind():
    """زرّ «انشر على المنصة» كان بيبعت `{}` والخادم بيردّ ٤٠٠ ⇒ طريق مسدود دائم.

    الحارس هنا على المسار كله: الزرّان يفتحان المودال، والمودال هو الوحيد الذي ينادي
    `EP.publishCourseToPlatform` — ومعه المالك."""
    html = _read('index.html')
    assert 'function publishCoursePlatformModal(' in html
    assert html.count('publishCoursePlatformModal(') == 3   # التعريف + زرّ الجدول + زرّ المعاينة
    # النداء الوحيد للـAPI يمرّ من المودال ومعه المالك المقروء من نفس الخانة والعلَم.
    assert html.count('EP.publishCourseToPlatform(') == 1
    assert 'EP.publishCourseToPlatform(c.cid,own,after)' in html
    # وبلوك الملكية مشترك: تعريف + استعمالان (الإنشاء والنشر) — سؤال واحد بشكل واحد.
    assert 'function courseOwnerBlockHtml(' in html and 'function bindCourseOwner(' in html
    assert html.count('courseOwnerBlockHtml()') == 3
    assert html.count('bindCourseOwner(s)') == 2 + 1   # الاستعمالان + التعريف
    # «مطلوب» ظاهرة في الليبل، والبلوك معنون «ملكية الدورة».
    assert '(مطلوب)' in html and 'ملكية الدورة' in html


@pytest.mark.skipif(shutil.which('node') is None, reason='node مطلوب لتشغيل ملف الواجهة كما يُشحن')
def test_node_harness_the_publish_call_actually_carries_the_owner(tmp_path):
    """تشغيل `dashboard-api.js` كما يُشحن: بلا مالك = لا نداء شبكة أصلًا؛ ومعه = الحقلان في الجسم."""
    api_js = os.path.join(DASH, 'dashboard-api.js')
    harness = """
const fs = require('fs');
const calls = [], toasts = [];
global.localStorage = { getItem: () => 'tok', setItem: () => {}, removeItem: () => {} };
global.fetch = (url, opts) => { calls.push({url, body: JSON.parse(opts.body || '{}')});
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ok: true}) }); };
global.window = global;
// readyState='loading' يمنع `EP.start` من الانطلاق، فنقيس النداء المقصود وحده.
global.document = { readyState: 'loading', addEventListener: () => {} };
global.toast = (m) => toasts.push(m);
global.notify = (m) => toasts.push(m);
eval(fs.readFileSync(%r, 'utf8'));
const EP = global.window.EP;
EP.reload = (k, after) => { if (after) after(); };
EP.publishCourseToPlatform(7, {}, () => {});
EP.publishCourseToPlatform(9, {instructor_email: 'mona@ex.com', platform_owned: false}, () => {});
EP.publishCourseToPlatform(11, {instructor_email: '', platform_owned: true}, () => {});
setTimeout(() => console.log(JSON.stringify({calls, toasts})), 30);
""" % api_js
    script = tmp_path / 'publish.js'
    script.write_text(harness, encoding='utf-8')
    proc = subprocess.run([shutil.which('node'), str(script)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    urls = [c['url'] for c in out['calls']]
    # النداء الأول (بلا مالك) ما خرجش من المتصفح أصلًا، والرسالة عربية بيضاء.
    assert not any('/courses/7/publish-platform' in u for u in urls), urls
    assert MSG in out['toasts']
    # والنداءان الشرعيان خرجا ومعهما الحقلان بالحرف.
    by_url = {c['url']: c['body'] for c in out['calls']}
    nine = next(b for u, b in by_url.items() if u.endswith('/courses/9/publish-platform'))
    assert nine == {'instructor_email': 'mona@ex.com', 'platform_owned': False}
    eleven = next(b for u, b in by_url.items() if u.endswith('/courses/11/publish-platform'))
    assert eleven == {'instructor_email': '', 'platform_owned': True}


def test_a_failed_mirror_is_announced_not_swallowed():
    """الخادم بيرجّع 201 ومعاها `platform_published:false` لو النشر فشل — الواجهة لازم تقولها."""
    js = _read('dashboard-api.js')
    assert 'r.platform_published === false' in js
    assert 'النشر على المنصة فشل' in js
