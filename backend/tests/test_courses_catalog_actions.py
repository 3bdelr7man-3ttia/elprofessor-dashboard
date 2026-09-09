# -*- coding: utf-8 -*-
"""قرار المؤسس (2026-09-10): «حذف/أرشفة» في الكتالوج · ونهاية «المزامنة مع الأكاديمية».

Run:  cd backend && python3 -m pytest -q tests/test_courses_catalog_actions.py

ما يثبّته هذا الملف:
  ١. `DELETE /api/platform-courses/<id>` بلا معاملات = **أرشفة** (لا `hard` يسافر للمنصّة)،
     ومع `?hard=1` = **حذف نهائي** (`hard=true` في المعاملات) — الفعلان لا يختلطان.
  ٢. رفض المنصّة (٤٠٩ لدورةٍ عليها اشتراك) يعبر **بحاله**: نفس الكود ونفس النصّ العربي، لا
     «تعذّر تنفيذ العملية» عامّة تخفي السبب والبديل.
  ٣. السرّ المشترك في الترويسة ولا يتسرّب للمتصفّح.
  ٤. من يقرأ: أدمن/موظّف فقط — بقيّة الأدوار ٤٠٣.
  ٥. الفعلان يُسجَّلان في دفتر التدقيق بفعلين مختلفين (`course.delete` ≠ `course.archive`)،
     ولا يُسجَّل شيء عند الرفض.
  ٦. مسارا الأكاديمية **اختفيا** (٤٠٤/٤٠٥)، ولا مستهلك لهما في الواجهة.

⛔ صفر لمسٍ للإنتاج: `requests.request` مُعترَض، ولا نداء شبكة واحد.
"""
import datetime
import os
import re

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_HERE))
INDEX = os.path.join(_REPO, 'dashboard-cloud', 'index.html')
APIJS = os.path.join(_REPO, 'dashboard-cloud', 'dashboard-api.js')
APPPY = os.path.join(_REPO, 'backend', 'app.py')

ARCHIVED = {'ok': True, 'archived': True,
            'course': {'id': 'c-1', 'slug': 'rec-x', 'title': 'العقود',
                       'is_active': False, 'archived_at': '2026-09-10T09:00:00+00:00'}}
DELETED = {'ok': True, 'deleted': True,
           'course': {'id': 'c-2', 'slug': 'draft-x', 'title': 'مسودّة'}}
BLOCKED_AR = ('مش هينفع تحذف الدورة دي نهائيًّا: عليها 4 اشتراك و1 عملية دفع. '
              'استعمل «أرشفة» — تختفي من الكتالوج ويفضل سجلّ المشتركين ودفعاتهم كما هو.')


class _FakeResp:
    def __init__(self, payload, status=200):
        self._p = payload
        self.status_code = status
        self.content = b'x'
        self.text = ''

    def json(self):
        return self._p


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
                 name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
                 preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = u.dashboard_role = role
    u.is_active = True
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id,
                      'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        roles = ['admin', 'employee', 'trainer', 'investor', 'viewer', 'pending']
        heads = {r: _bearer(_mkuser('cat-%s@x.test' % r, r)) for r in roles}
        yield {'heads': heads, 'client': flask_app.test_client()}


@pytest.fixture
def bridge(monkeypatch):
    """يعترض ما يرسله `_platform_proxy` ويردّ ما نقرّره لكل حالة."""
    seen = []
    box = {'resp': _FakeResp(ARCHIVED)}

    def _fake(method, url, params=None, json=None, headers=None, timeout=None):
        seen.append({'method': method, 'url': url, 'params': params, 'headers': headers or {}})
        return box['resp']

    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', 'test-metrics-secret')
    monkeypatch.setattr(appmod.requests, 'request', _fake)
    return {'seen': seen, 'box': box}


# ---------------------------------------------------------------- ١) فعلان لا فعل

def test_archive_is_the_default_and_never_sends_hard(ctx, bridge):
    r = ctx['client'].delete('/api/platform-courses/c-1', headers=ctx['heads']['admin'])
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.get_json() == ARCHIVED
    call = bridge['seen'][-1]
    assert call['method'] == 'DELETE' and call['url'].endswith('/api/bridge/courses/c-1')
    assert call['params'] is None      # بلا `hard` ⇒ المنصّة تؤرشف


def test_hard_flag_travels_to_the_platform(ctx, bridge):
    bridge['box']['resp'] = _FakeResp(DELETED)
    r = ctx['client'].delete('/api/platform-courses/c-2?hard=1', headers=ctx['heads']['admin'])
    assert r.status_code == 200
    assert r.get_json()['deleted'] is True
    assert bridge['seen'][-1]['params'] == {'hard': 'true'}


@pytest.mark.parametrize('qs', ['?hard=0', '?hard=false', '?hard=', ''])
def test_anything_but_an_explicit_yes_is_an_archive(ctx, bridge, qs):
    """⛔ محوٌ لا رجعة فيه لا يُشتقّ من معاملٍ غامض: كل ما ليس «نعم» صريحة = أرشفة."""
    ctx['client'].delete('/api/platform-courses/c-1' + qs, headers=ctx['heads']['admin'])
    assert bridge['seen'][-1]['params'] is None


# ---------------------------------------------------------------- ٢) الرفض يعبر بحاله

def test_platform_409_passes_through_verbatim(ctx, bridge):
    bridge['box']['resp'] = _FakeResp({'detail': BLOCKED_AR}, status=409)
    r = ctx['client'].delete('/api/platform-courses/c-1?hard=1', headers=ctx['heads']['admin'])
    assert r.status_code == 409
    assert r.get_json()['error'] == BLOCKED_AR       # حرفيًّا — فيه السبب والبديل
    assert 'أرشفة' in r.get_json()['error']


def test_a_refused_delete_writes_no_audit_row(ctx, bridge):
    """سجلٌّ يقول «حُذفت» عن دورةٍ لم تُحذف أسوأ من لا سجلّ."""
    bridge['box']['resp'] = _FakeResp({'detail': BLOCKED_AR}, status=409)
    with flask_app.app_context():
        before = AuditLog.query.filter_by(action='course.delete', target='c-9').count()
    ctx['client'].delete('/api/platform-courses/c-9?hard=1', headers=ctx['heads']['admin'])
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='course.delete', target='c-9').count() == before


def test_the_two_actions_are_two_audit_actions(ctx, bridge):
    ctx['client'].delete('/api/platform-courses/c-77', headers=ctx['heads']['admin'])
    bridge['box']['resp'] = _FakeResp(DELETED)
    ctx['client'].delete('/api/platform-courses/c-88?hard=1', headers=ctx['heads']['admin'])
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='course.archive', target='c-77').count() == 1
        assert AuditLog.query.filter_by(action='course.delete', target='c-88').count() == 1


# ---------------------------------------------------------------- ٣) السرّ · ٤) من يقرأ

def test_secret_in_the_header_and_never_in_the_response(ctx, bridge):
    r = ctx['client'].delete('/api/platform-courses/c-1', headers=ctx['heads']['admin'])
    assert bridge['seen'][-1]['headers'].get('X-ELP-Metrics-Secret') == 'test-metrics-secret'
    assert 'test-metrics-secret' not in r.get_data(as_text=True)


@pytest.mark.parametrize('role', ['trainer', 'investor', 'viewer', 'pending'])
def test_only_staff_may_remove_a_catalog_course(ctx, bridge, role):
    r = ctx['client'].delete('/api/platform-courses/c-1?hard=1', headers=ctx['heads'][role])
    assert r.status_code == 403


def test_employee_may_remove(ctx, bridge):
    r = ctx['client'].delete('/api/platform-courses/c-1', headers=ctx['heads']['employee'])
    assert r.status_code == 200


# ---------------------------------------------------------------- ٦) الأكاديمية اختفت

@pytest.mark.parametrize('path', ['/api/courses/sync-lms', '/api/courses/create-lms'])
def test_the_academy_routes_are_gone(ctx, path):
    """المسار المحذوف لا يردّ ٢٠٠ ولا ٥٠٣ «لم يُضبط الربط» — هو ببساطة غير موجود."""
    r = ctx['client'].post(path, json={}, headers=ctx['heads']['admin'])
    assert r.status_code in (404, 405), r.status_code


def test_no_academy_route_is_registered_anywhere_in_the_url_map():
    rules = {str(r) for r in flask_app.url_map.iter_rules()}
    assert not [u for u in rules if 'lms' in u.lower()], sorted(u for u in rules if 'lms' in u.lower())


def test_the_dashboard_has_no_academy_consumer_left():
    """⛔ المسح البرمجي هو الحارس: لا زرّ ولا نداء ولا تبويب باسم الأكاديمية."""
    idx = open(INDEX, encoding='utf-8').read()
    js = open(APIJS, encoding='utf-8').read()
    for needle in ('syncCoursesLms', 'createLmsCourse', 'sync-lms', 'create-lms'):
        assert needle not in idx, needle
        assert needle not in js, needle
    assert 'مزامنة من الأكاديمية' not in idx
    assert 'مزامنة مع الأكاديمية' not in idx
    assert 'الأكاديمية' not in idx      # لا تبويب ولا زرّ ولا نصّ بهذا الاسم


def test_the_flask_app_no_longer_calls_any_platform_lms_course_endpoint():
    src = open(APPPY, encoding='utf-8').read()
    # ما بقي من `lms` في الخادم: أعمدة SQLite (بيانات) + تعليقُ الشاهد + مسار الدخول
    # الموحّد `/api/lms/sso/verify` (راوتر SSO حيّ، ليس من رواتر الدورات المركونة).
    calls = [m for m in re.findall(r'/api/bridge/lms-[a-z-]+', src)]
    assert calls == [], calls


def test_the_lms_columns_stay_as_data_with_no_ui_reader():
    """الأعمدة تبقى (تاريخٌ لا يُمحى) — لكن لا واجهة تقرؤها.

    ⛔ المسحُ يشمل **طبقة البيانات في المتصفّح** أيضًا: حقلٌ مُهاجَرٌ في نموذج العرض
    (`lms_synced: !!c.lms_synced`) لا يرسمه أحد = حقلٌ ميّتٌ يوهم القارئ أن للأكاديمية بقيّة."""
    src = open(APPPY, encoding='utf-8').read()
    assert 'lms_id = db.Column' in src and 'lms_synced = db.Column' in src
    idx = open(INDEX, encoding='utf-8').read()
    js = open(APIJS, encoding='utf-8').read()
    for col in ('lms_synced', 'lms_sales_count', 'lms_revenue', 'lms_instructor_email'):
        assert col not in idx, col
        assert col not in js, col


# ---------------------------------------------------------------- الواجهة موصولة فعلًا

def test_the_catalog_rows_carry_both_actions_and_the_modal():
    idx = open(INDEX, encoding='utf-8').read()
    assert 'function pcCanHardDelete(' in idx
    assert 'function pcRemoveModal(' in idx
    assert 'EP.removePlatformCourse' in idx      # المودال ينادي الطبقة فعلًا
    assert "data-pc-act=\"hard\"" in idx and "data-pc-act=\"archive\"" in idx
    assert '.pcDel' in idx                        # الزرّ مربوطٌ بمستمع، لا مرسومٌ وحسب
    assert 'مؤرشفة — مخفية' in idx    # الشارة تتغيّر بعد الأرشفة
    js = open(APIJS, encoding='utf-8').read()
    assert 'EP.removePlatformCourse = function' in js
    assert '"?hard=1"' in js


def test_the_demand_tab_stays_in_the_courses_screen():
    """قرار المؤسس: «الطلب على الدورات» يفضل هنا — طلبات الشات والسوق تظهر في مكانها."""
    idx = open(INDEX, encoding='utf-8').read()
    assert 'data-t="demand">الطلب على الدورات' in idx
    assert 'function renderCourseDemand(' in idx


# ------------------------------------------- الأرشفةُ تُمحى بالنشر · والردُّ هو الحَكَم

def test_the_audit_row_follows_the_platform_reply_not_our_intent(ctx, bridge):
    """لو اللوحة نزلت قبل المنصّة: منصّةٌ أقدم تتجاهل `hard` وتؤرشف وترجّع ٢٠٠ بلا `deleted` —
    فالسطر المكتوب لازم يكون «أرشفة»، وإلا وثّقنا حذفًا لدورةٍ لسه في القاعدة."""
    bridge['box']['resp'] = _FakeResp(ARCHIVED)          # ردُّ منصّةٍ قديمة على `?hard=1`
    ctx['client'].delete('/api/platform-courses/c-old?hard=1', headers=ctx['heads']['admin'])
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='course.delete', target='c-old').count() == 0
        assert AuditLog.query.filter_by(action='course.archive', target='c-old').count() == 1


def test_the_toast_follows_the_reply_too(ctx=None):
    """نفس القاعدة في المتصفّح: التوست يقرأ `r.deleted` لا المتغيّر المحلّي `hard`."""
    js = open(APIJS, encoding='utf-8').read()
    assert '(r && r.deleted) ? "اتحذفت الدورة نهائيًّا من المنصة ✓"' in js
    assert 'note(hard ? "اتحذفت' not in js


def test_the_action_cell_uses_the_same_condition_as_the_badge():
    """⛔ `archived_at` وحده كان يقفل الصفّ: دورةٌ حيّةٌ عليها طابعٌ قديم تظهر «منشورة» في
    الشارة و«مؤرشفة» في خليّة الفعل — بلا زرِّ أرشفةٍ ولا حذفٍ إلى الأبد."""
    idx = open(INDEX, encoding='utf-8').read()
    assert "var act=(c.archived_at&&!c.is_active)?" in idx
    assert "var act=c.archived_at?" not in idx
    # نفسُ شرط الشارة بالحرف
    assert "if(!c.is_active&&c.archived_at)return['s-late','مؤرشفة — مخفية']" in idx


def test_the_state_page_no_longer_advertises_the_deleted_routes():
    """ورقةُ حالةٍ تكذب أخطر من ورقةٍ ناقصة: المساران اتشالوا فلا يُذكران كـ«يُعاد توجيهه»."""
    state = open(os.path.join(_REPO, 'dashboard-cloud', 'Dashboard-State.html'),
                 encoding='utf-8').read()
    assert '/api/courses/sync-lms' not in state
    assert 'يُعاد توجيهه' not in state
    assert 'قرار المؤسس 2026-09-10' in state
