# -*- coding: utf-8 -*-
"""«القاموس» — مسارات الإدارة والفيد العام (docs/v2/glossary/SPEC.md، القسم الخلفي).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_glossary_routes.py

⛔ صفر شبكة حقيقية: جسر المنصة بديل في الذاكرة (`FakeBridge`) وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
`_prerender_push_async` متبدّلة بدالة تسجّل السبب (ولا SFTP ولا توليد).

اللي بيثبّته:
  ١. الأدوار والمفتاح والتأكيد والحقول المسموحة · ٢. القائمة: بحث ومجال («أخرى») وحالة وعدّادات · ٣. الإنشاء والتعديل بالفرق وتجميد الرابط ·
  ٤. ختم «راجعه» ومسحه عند التعديل الجوهري (إعداد مفعّل ومعطّل) · ٥. النشر يتطلب مراجعة · ٦. الحذف · ٧. الاستيراد: معاينة ثم تأكيد ·
  ٨. الفيد العام: منشور فقط وبلا حقول خاصة · ٩. النقاش المرتبط عبر الجسر البديل · ١٠. طلب التوليد ينادى وفشله لا يُسقط الحفظ · ١١. التسجيل في app.py وDockerfile.
الجولة الثانية (قرار المؤسس ٢٠٢٦-١١-٠١): ١٢. الحالات مسودة ⇒ تحت التأكيد ⇒ مؤكّد والشرط الافتراضي مغلق · ١٣. الاستمارة العامة (فخّ الحقل الخفي · الحدّ · التحقق ·
  ٤٠٤ لمصطلح غير منشور · مراجعة معلّقة واحدة لكل بريد ومصطلح · لا IP ولا متصفح) · ١٤. صندوق «مراجعات القاموس»: اعتمد (يختم) · اعتمد اقتراحًا · ارفض ·
  تحذير تغيّر المصطلح · ١٥. التنبيه: لا سطر تليجرام، وصف واحد في جرس الإشعارات.
"""
import copy
import datetime
import json
import os
import re

import jwt
import pytest
from werkzeug.security import generate_password_hash

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog, GlossaryTerm, Setting, ExpertReviewSubmission  # noqa: E402
import v2_glossary_routes as gr  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(_HERE)
ROOT = os.path.dirname(BACKEND)

PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
TID = 'c0ffee00-1111-4222-8333-444455556666'
TID2 = 'deadbeef-1111-4222-8333-444455556666'
BASE = '/api/v2/content/glossary'


# ——————————————————————————————————————————————— أدوات

def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
             linked_to_name='', preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


def _term(slug='force-majeure', ar='القوة القاهرة', en='force majeure', area='contracts', status='draft', reviewed=False,
          published=False, **kw):
    t = GlossaryTerm(slug=slug, ar=ar, en=en, fr=kw.pop('fr', 'force majeure'), area=area, definition_ar=kw.pop('definition_ar', 'حدث خارج عن إرادة الطرفين يعفي من التنفيذ.'),
                     example_en=kw.pop('example_en', 'The Seller is not liable for force majeure.'),
                     example_ar=kw.pop('example_ar', 'لا يسأل البائع عن القوة القاهرة.'), false_friend_note_ar=kw.pop('false_friend_note_ar', None),
                     countries_note_ar=kw.pop('countries_note_ar', None), related=json.dumps(kw.pop('related', []), ensure_ascii=False),
                     status=status, source='manual', saha_topic_id=kw.pop('saha_topic_id', None),
                     published_at=datetime.datetime(2026, 10, 1) if (published or status == 'published') else None,
                     created_at=datetime.datetime(2026, 9, 1), updated_at=datetime.datetime(2026, 9, 1))
    if status == 'published':                           # اختصار الاختبارات: منشور ⇒ مؤكَّد لو عليه ختم وإلا تحت التأكيد
        t.status = 'confirmed' if reviewed else 'under_review'
    if reviewed:
        t.reviewed_by_name, t.reviewed_by_role, t.reviewed_at = 'أ. هبة الجندي', 'محامية', datetime.datetime(2026, 10, 2)
    assert not kw, kw
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def ctx():
    with flask_app.app_context():
        db.create_all()
        GlossaryTerm.query.delete()
        ExpertReviewSubmission.query.delete()
        Setting.query.filter_by(key=gr.SETTING_KEY).delete()
        AuditLog.query.filter(AuditLog.action.like('glossary%')).delete(synchronize_session=False)
        db.session.commit()
        heads = {r: _bearer(_mkuser('glos-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('glos-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}
        GlossaryTerm.query.delete()
        ExpertReviewSubmission.query.delete()
        Setting.query.filter_by(key=gr.SETTING_KEY).delete()
        db.session.commit()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


class FakeBridge(object):
    """جسر المنصة بديل في الذاكرة: قراءة `/api/bridge/topics` فقط (المصطلح لا يُنشئ نقاشًا)."""

    def __init__(self):
        self.topics = [
            {'id': TID, 'title': 'متى تُعفي القوة القاهرة؟', 'status': 'published', 'question': 'q'},
            {'id': TID2, 'title': 'مسودة', 'status': 'draft'},
            {'id': 'aaaaaaaa-0000-4000-8000-000000000001', 'title': 'مفتوح', 'status': 'open'},
            {'id': 'bad id', 'title': 'معرّف سيئ', 'status': 'published'},
        ]
        self.seen = []
        self.blocked = []
        self.mode = 'ok'            # ok | lost | down403 | junk

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        self.seen.append({'method': method.upper(), 'url': url, 'json': copy.deepcopy(json), 'headers': dict(headers or {})})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        path = url[len(PLATFORM):]
        if path == '/api/bridge/topics' and method.upper() == 'GET':
            if self.mode == 'lost':
                return _Resp(504, {'detail': 'timeout'})
            if self.mode == 'down403':
                return _Resp(403, {'detail': 'no'})
            if self.mode == 'junk':
                return _Resp(200, {'oops': 1})
            return _Resp(200, copy.deepcopy(self.topics))
        return _Resp(404, {'detail': 'no route'})


@pytest.fixture
def plat(monkeypatch):
    p = FakeBridge()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    p.pushes = []
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': p.pushes.append(reason) or {'state': 'started'})
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def call(ctx, method, path, body=None, role='admin', confirmed=True):
    kw = {'headers': ctx['heads'][role] if role else {}}
    if body is not None or method in ('POST', 'PUT', 'DELETE'):
        b = dict(body or {})
        if confirmed and 'confirmed' not in b:
            b['confirmed'] = True
        kw['json'] = b
    return ctx['client'].open(BASE + path, method=method, **kw)


def fresh(tid):
    db.session.expire_all()
    return db.session.get(GlossaryTerm, tid)


def audits(prefix='glossary'):
    return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email)
            for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%')).order_by(AuditLog.id).all()]


def set_require(ctx, v):
    r = call(ctx, 'PUT', '/settings', {'require_review': v})
    assert r.status_code == 200, r.get_json()


# ——————————————————————————————————————————————— ١) الأدوار والمفتاح والتأكيد

ROUTES = [
    ('GET', ''), ('GET', '/1'), ('POST', ''), ('PUT', '/1'), ('DELETE', '/1'), ('POST', '/1/publish'), ('POST', '/1/unpublish'),
    ('POST', '/1/review'), ('POST', '/1/unreview'), ('POST', '/seed/preview'), ('POST', '/seed/import'), ('GET', '/topics'),
    ('POST', '/1/attach-topic'), ('POST', '/1/detach-topic'), ('GET', '/settings'), ('PUT', '/settings'),
    ('GET', '/reviews'), ('POST', '/reviews/1/approve'), ('POST', '/reviews/1/reject'),
]


@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_only_admin_every_route(ctx, plat, role):
    t = _term()
    for m, p in ROUTES:
        r = call(ctx, m, p.replace('/1', '/%d' % t.id), role=role)
        assert r.status_code == 403, (role, m, p, r.status_code)
    assert plat.seen == [] and GlossaryTerm.query.count() == 1 and audits() == []


def test_no_token_is_401(ctx, plat):
    for m, p in ROUTES:
        assert call(ctx, m, p, role=None).status_code == 401, (m, p)
    assert plat.seen == []


def test_closed_flag_is_404_no_side_effect_no_call(ctx, plat, monkeypatch):
    t = _term(reviewed=True)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    for m, p in ROUTES:
        r = call(ctx, m, p.replace('/1', '/%d' % t.id), {'ar': 'x'} if m == 'PUT' else None)
        assert r.status_code == 404, (m, p, r.status_code)
        assert r.headers['Cache-Control'] == 'no-store'
    assert plat.seen == [] and plat.pushes == [] and audits() == []
    assert fresh(t.id).ar == 'القوة القاهرة' and GlossaryTerm.query.count() == 1


WRITES = [('POST', ''), ('PUT', '/{id}'), ('DELETE', '/{id}'), ('POST', '/{id}/publish'), ('POST', '/{id}/unpublish'),
          ('POST', '/{id}/review'), ('POST', '/{id}/unreview'), ('POST', '/seed/import'), ('POST', '/{id}/attach-topic'),
          ('POST', '/{id}/detach-topic'), ('PUT', '/settings'), ('POST', '/reviews/{id}/approve'), ('POST', '/reviews/{id}/reject')]


@pytest.mark.parametrize('bad', [{}, {'confirmed': False}, {'confirmed': 'true'}, {'confirmed': 1}, {'confirmed': None}])
def test_every_write_needs_confirmed_true_exactly(ctx, plat, bad):
    t = _term(reviewed=True)
    for m, p in WRITES:
        r = ctx['client'].open(BASE + p.format(id=t.id), method=m, headers=ctx['heads']['admin'],
                               json=dict(bad, reviewer_name='س س', reviewer_role='محامٍ', ar='تعديل', en='x', definition_ar='y', source='seed',
                                         saha_topic_id=TID, require_review=False))
        assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR, (m, p, r.status_code)
    assert plat.seen == [] and plat.pushes == [] and audits() == []
    assert GlossaryTerm.query.count() == 1 and fresh(t.id).ar == 'القوة القاهرة' and fresh(t.id).reviewed_at


def test_reads_and_preview_need_no_confirmation(ctx, plat):
    _term()
    assert call(ctx, 'GET', '', confirmed=False).status_code == 200
    r = call(ctx, 'POST', '/seed/preview', {'source': 'seed'}, confirmed=False)
    assert r.status_code == 200 and r.get_json()['new_count'] == 79 and r.get_json()['skip_existing'] == 1   # force-majeure موجود في الأساسي
    assert GlossaryTerm.query.count() == 1 and audits() == []


def test_confirmed_is_never_stored_and_by_comes_from_token(ctx, plat):
    r = call(ctx, 'POST', '', {'ar': 'العقد', 'en': 'contract', 'definition_ar': 'اتفاق.', 'area': 'contracts', 'by': 'hacker@x.test',
                                'created_by': 'hacker@x.test', 'confirmed': True})
    assert r.status_code == 200
    item = r.get_json()['item']
    assert 'confirmed' not in item and 'by' not in item and 'hacker' not in json.dumps(item)
    a = audits('glossary.create')
    assert len(a) == 1 and a[0][3] == 'glos-admin@x.test' and 'hacker' not in json.dumps(a[0][2])


# ——————————————————————————————————————————————— ٢) القائمة

def _many():
    _term('consideration', 'المقابل (العوض)', 'consideration', 'contracts', fr='contrepartie', definition_ar='شيء ذو قيمة يقدّمه كل طرف.')
    _term('plaintiff', 'المدّعي', 'plaintiff', 'litigation', status='published', reviewed=True, fr='demandeur')
    _term('arbitrator', 'المحكّم', 'arbitrator', 'arbitration', fr='arbitre')
    _term('misc-thing', 'أمر آخر', 'other thing', 'other', fr=None)
    _term('shell-co', 'شركة الأموال', 'shell company', 'corporate', fr='société écran', definition_ar='شركة بلا نشاط فعلي.')


def test_list_search_across_languages_and_definition(ctx, plat):
    _many()
    got = lambda q: sorted(i['slug'] for i in call(ctx, 'GET', '?q=' + q).get_json()['items'])
    assert got('plaint') == ['plaintiff']                  # إنجليزي جزئي
    assert got('PLAINTIFF') == ['plaintiff']               # غير حساس للحالة
    assert got('المحكّم') == ['arbitrator']                # عربي
    assert got('contrepartie') == ['consideration']        # فرنسي
    assert got('بلا نشاط') == ['shell-co']                 # من التعريف
    assert got('%') == [] and got('_') == []               # محارف LIKE لا تعمل كبدائل
    assert len(got('')) == 5


def test_list_area_filter_includes_other_and_validates(ctx, plat):
    _many()
    r = call(ctx, 'GET', '?area=other').get_json()
    assert [i['slug'] for i in r['items']] == ['misc-thing'] and r['total'] == 1
    assert [i['slug'] for i in call(ctx, 'GET', '?area=litigation').get_json()['items']] == ['plaintiff']
    assert call(ctx, 'GET', '?area=nonsense').status_code == 400
    assert {a['code'] for a in r['areas']} == {'contracts', 'litigation', 'corporate', 'general', 'arbitration', 'criminal', 'ip', 'labor', 'family', 'other'}
    assert dict((a['code'], a['label']) for a in r['areas'])['other'] == 'أخرى'


def test_list_status_review_filters_and_counts(ctx, plat):
    _many()
    r = call(ctx, 'GET', '?status=published').get_json()
    assert [i['slug'] for i in r['items']] == ['plaintiff']
    assert [i['slug'] for i in call(ctx, 'GET', '?status=confirmed').get_json()['items']] == ['plaintiff']
    assert call(ctx, 'GET', '?status=under_review').get_json()['items'] == []
    assert len(call(ctx, 'GET', '?status=draft').get_json()['items']) == 4
    assert [i['slug'] for i in call(ctx, 'GET', '?review=reviewed').get_json()['items']] == ['plaintiff']
    assert len(call(ctx, 'GET', '?review=unreviewed').get_json()['items']) == 4
    c = r['counts']
    assert (c['all'], c['draft'], c['published'], c['reviewed'], c['unreviewed']) == (5, 4, 1, 1, 4)
    assert (c['under_review'], c['confirmed'], c['reviews_pending']) == (0, 1, 0)
    assert c['by_area']['other'] == 1 and c['by_area']['contracts'] == 1 and c['published_unreviewed'] == 0
    assert call(ctx, 'GET', '?status=zzz').status_code == 400 and call(ctx, 'GET', '?limit=abc').status_code == 400
    assert r['require_review'] is False and 'definition_ar' in r['substantive_fields']
    assert len(call(ctx, 'GET', '?limit=2&offset=1').get_json()['items']) == 2


def test_get_one_and_missing(ctx, plat):
    t = _term(reviewed=True)
    it = call(ctx, 'GET', '/%d' % t.id).get_json()['item']
    assert it['slug'] == 'force-majeure' and it['reviewed'] is True and it['slug_frozen'] is False and it['reviewed_by_name'] == 'أ. هبة الجندي'
    assert call(ctx, 'GET', '/99999').status_code == 404


# ——————————————————————————————————————————————— ٣) الإنشاء والتعديل وتجميد الرابط

def _new(**kw):
    b = {'ar': 'العقد', 'en': 'contract', 'definition_ar': 'اتفاق بين طرفين.', 'area': 'contracts'}
    b.update(kw)
    return b


def test_create_derives_slug_validates_and_is_draft(ctx, plat):
    r = call(ctx, 'POST', '', _new(en='Force Majeure!', fr='force majeure', related=['a-b', 'a-b', 'c'], status='published',
                                    reviewed_by_name='x', saha_topic_id=TID, source='seed'))
    it = r.get_json()['item']
    assert r.status_code == 200 and it['slug'] == 'force-majeure' and it['status'] == 'draft' and it['source'] == 'manual'
    assert it['related'] == ['a-b', 'c'] and it['reviewed'] is False and it['saha_topic_id'] is None and it['published_at'] is None
    assert plat.pushes == []                                     # مسودة جديدة لا تمسّ صفحة منشورة
    assert call(ctx, 'POST', '', _new(slug='force-majeure')).status_code == 409       # الرابط فريد
    for bad in ({'ar': ''}, {'en': ''}, {'definition_ar': '   '}, {'area': 'tax'}, {'area': None}, {'slug': 'Bad Slug'}, {'slug': '-x'},
                {'related': ['Bad Slug']}, {'related': 'x'}, {'definition_ar': 'انظر https://x.test'}, {'example_en': 'see www.x.test'},
                {'ar': 'س' * 301}, {'fr': 5}):
        assert call(ctx, 'POST', '', _new(**dict({'slug': 'ok-slug'}, **bad))).status_code == 400, bad
    assert GlossaryTerm.query.count() == 1


def test_create_requires_a_slug_source(ctx, plat):
    assert call(ctx, 'POST', '', _new(en='العقد')).status_code == 400          # لا slug ولا إنجليزي ASCII يُشتقّ منه
    assert call(ctx, 'POST', '', _new(en='contract', slug='')).get_json()['item']['slug'] == 'contract'


def test_update_diff_only_and_whitelist(ctx, plat):
    t = _term()
    r = call(ctx, 'PUT', '/%d' % t.id, {'ar': 'القوة القاهرة', 'en': 'force majeure', 'status': 'published', 'reviewed_by_name': 'x',
                                         'reviewed_at': '2026-01-01', 'saha_topic_id': TID, 'source': 'seed', 'published_at': '2026-01-01',
                                         'created_at': '2000-01-01', 'id': 999})
    assert r.status_code == 200 and r.get_json()['changed'] == []                  # لا فرق ⇒ لا تغيير
    f = fresh(t.id)
    assert (f.status, f.reviewed_by_name, f.saha_topic_id, f.source, f.published_at, f.id) == ('draft', None, None, 'manual', None, t.id)
    assert audits('glossary.update') == [] and plat.pushes == []
    r = call(ctx, 'PUT', '/%d' % t.id, {'fr': '', 'example_ar': 'مثال جديد', 'related': ['x-y'], 'area': 'other'})
    assert sorted(r.get_json()['changed']) == ['area', 'example_ar', 'fr', 'related']
    f = fresh(t.id)
    assert f.fr is None and f.area == 'other' and json.loads(f.related) == ['x-y']
    a = audits('glossary.update')
    assert len(a) == 1 and sorted(a[0][2]['fields']) == ['area', 'example_ar', 'fr', 'related']
    assert call(ctx, 'PUT', '/%d' % t.id, {'ar': ''}).status_code == 400
    assert call(ctx, 'PUT', '/%d' % t.id, {'area': 'tax'}).status_code == 400
    assert call(ctx, 'PUT', '/99999', {'ar': 'x'}).status_code == 404


def test_slug_editable_before_first_publish_then_frozen_even_after_unpublish(ctx, plat):
    t = _term(reviewed=True)
    u = _term('other-term', 'آخر', 'other term')
    assert call(ctx, 'PUT', '/%d' % t.id, {'slug': 'other-term'}).status_code == 409           # فريد
    assert call(ctx, 'PUT', '/%d' % t.id, {'slug': 'force-majeure-clause'}).status_code == 200
    assert fresh(t.id).slug == 'force-majeure-clause'
    assert call(ctx, 'POST', '/%d/publish' % t.id).status_code == 200
    r = call(ctx, 'PUT', '/%d' % t.id, {'slug': 'renamed'})
    assert r.status_code == 409 and r.get_json()['error'] == gr.SLUG_FROZEN_AR and fresh(t.id).slug == 'force-majeure-clause'
    assert call(ctx, 'PUT', '/%d' % t.id, {'slug': 'force-majeure-clause', 'related': ['x-y']}).status_code == 200   # نفس الرابط مقبول
    assert call(ctx, 'POST', '/%d/unpublish' % t.id).status_code == 200
    assert call(ctx, 'PUT', '/%d' % t.id, {'slug': 'renamed'}).status_code == 409            # التجميد لا يزول بإلغاء النشر
    assert fresh(u.id).slug == 'other-term'


# ——————————————————————————————————————————————— ٤) ختم «راجعه»

def test_review_stamp_server_time_and_audit_by_token(ctx, plat):
    t = _term()
    before = datetime.datetime.utcnow()
    r = call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': '  أ. هبة   الجندي ', 'reviewer_role': 'محامية', 'by': 'evil@x.test',
                                                 'reviewed_at': '2000-01-01T00:00:00', 'reviewer_email': 'e@x.test'})
    assert r.status_code == 200
    f = fresh(t.id)
    assert f.reviewed_by_name == 'أ. هبة الجندي' and f.reviewed_by_role == 'محامية' and f.reviewed_at >= before
    assert 'evil' not in json.dumps(r.get_json()) and 'e@x.test' not in json.dumps(r.get_json())
    a = audits('glossary.review')
    assert len(a) == 1 and a[0][3] == 'glos-admin@x.test' and a[0][2]['reviewer_name'] == 'أ. هبة الجندي'
    assert plat.pushes == [] and f.status == 'draft' and f.reviewer_name_public is False   # مسودة ⇒ لا توليد، وتبقى مسودة
    # إعادة الختم تستبدل المراجع
    assert call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'أستاذة قانون'}).status_code == 200
    assert fresh(t.id).reviewed_by_name == 'د. سارة' and audits('glossary.review')[-1][2]['restamp'] is True


@pytest.mark.parametrize('body', [{}, {'reviewer_name': 'س'}, {'reviewer_name': 'سعد', 'reviewer_role': ''}, {'reviewer_name': 'سعد', 'reviewer_role': 'ص'},
                                  {'reviewer_name': 'x@y.test', 'reviewer_role': 'محام'}, {'reviewer_name': 'سعد', 'reviewer_role': 'https://x.test'},
                                  {'reviewer_name': 'ش' * 121, 'reviewer_role': 'محام'}, {'reviewer_name': 5, 'reviewer_role': 'محام'}])
def test_review_needs_name_and_role(ctx, plat, body):
    t = _term()
    r = call(ctx, 'POST', '/%d/review' % t.id, body)
    assert r.status_code == 400 and fresh(t.id).reviewed_at is None and audits('glossary.review') == []


def test_unreview_clears_stamp(ctx, plat):
    t = _term(reviewed=True)
    r = call(ctx, 'POST', '/%d/unreview' % t.id)
    assert r.status_code == 200 and r.get_json()['unpublished'] is False
    f = fresh(t.id)
    assert (f.reviewed_by_name, f.reviewed_by_role, f.reviewed_at) == (None, None, None)
    assert call(ctx, 'POST', '/%d/unreview' % t.id).status_code == 409


@pytest.mark.parametrize('field', list(gr.SUBSTANTIVE))
def test_substantive_edit_clears_stamp(ctx, plat, field):
    t = _term(reviewed=True, false_friend_note_ar='ملاحظة', countries_note_ar='بلد')
    r = call(ctx, 'PUT', '/%d' % t.id, {field: 'قيمة جديدة' if field not in ('en', 'fr', 'example_en') else 'new value'})
    assert r.status_code == 200 and r.get_json()['review_cleared'] is True, r.get_json()
    f = fresh(t.id)
    assert (f.reviewed_by_name, f.reviewed_by_role, f.reviewed_at) == (None, None, None)
    assert audits('glossary.update')[-1][2]['review_cleared'] is True


@pytest.mark.parametrize('field,val', [('area', 'other'), ('related', ['x-y']), ('slug', 'new-slug')])
def test_non_substantive_edit_keeps_stamp(ctx, plat, field, val):
    t = _term(reviewed=True)
    assert call(ctx, 'PUT', '/%d' % t.id, {field: val}).status_code == 200
    assert fresh(t.id).reviewed_by_name == 'أ. هبة الجندي'


def test_edit_of_unreviewed_term_does_not_pretend_to_clear(ctx, plat):
    t = _term()
    assert call(ctx, 'PUT', '/%d' % t.id, {'ar': 'جديد'}).get_json()['review_cleared'] is False


# ——————————————————————————————————————————————— ٥) الحالات: مسودة ⇒ تحت التأكيد ⇒ مؤكّد (الشرط مغلق افتراضيًّا)

def test_publish_without_stamp_is_under_review_by_default(ctx, plat):
    t = _term()
    r = call(ctx, 'POST', '/%d/publish' % t.id)
    j = r.get_json()['item']
    assert r.status_code == 200 and j['status'] == 'under_review' and j['published'] is True and j['reviewed'] is False
    assert fresh(t.id).published_at is not None and plat.pushes == ['glossary:%d' % t.id]
    assert audits('glossary.publish')[0][2] == {'slug': 'force-majeure', 'reviewed': False, 'state': 'under_review'}


def test_publish_refused_without_stamp_only_while_required(ctx, plat):
    set_require(ctx, True)
    t = _term()
    r = call(ctx, 'POST', '/%d/publish' % t.id)
    assert r.status_code == 409 and r.get_json()['error'] == 'يُنشر بعد أن يراجعه خبير' and r.get_json()['needs_review'] is True
    f = fresh(t.id)
    assert f.status == 'draft' and f.published_at is None and plat.pushes == [] and audits('glossary.publish') == []
    call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'محامية'})
    assert call(ctx, 'POST', '/%d/publish' % t.id).get_json()['item']['status'] == 'confirmed'


def test_publish_after_review_is_confirmed_and_first_date_never_changes(ctx, plat):
    t = _term(reviewed=True)
    r = call(ctx, 'POST', '/%d/publish' % t.id)
    assert r.status_code == 200 and r.get_json()['item']['status'] == 'confirmed'
    first = fresh(t.id).published_at
    assert first is not None and plat.pushes == ['glossary:%d' % t.id]
    assert call(ctx, 'POST', '/%d/publish' % t.id).status_code == 409                    # منشور بالفعل
    assert call(ctx, 'POST', '/%d/unpublish' % t.id).status_code == 200
    assert plat.pushes[-1] == 'glossary:%d' % t.id and fresh(t.id).status == 'draft'
    assert fresh(t.id).reviewed_at is not None                                             # إلغاء النشر لا يمسح الختم
    assert call(ctx, 'POST', '/%d/unpublish' % t.id).status_code == 409
    assert call(ctx, 'POST', '/%d/publish' % t.id).status_code == 200
    assert fresh(t.id).published_at == first and fresh(t.id).status == 'confirmed'
    assert [a[0] for a in audits()] == ['glossary.publish', 'glossary.unpublish', 'glossary.publish']


def test_stamping_a_published_term_confirms_it_and_a_draft_stays_draft(ctx, plat):
    t = _term(status='published')
    assert t.status == 'under_review'
    r = call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'محامية', 'reviewer_name_public': True})
    assert r.status_code == 200 and r.get_json()['item']['status'] == 'confirmed' and r.get_json()['item']['reviewer_name_public'] is True
    assert plat.pushes == ['glossary:%d' % t.id] and audits('glossary.review')[0][2]['name_public'] is True
    d = _term('other-draft', 'آخر', 'other draft')
    j = call(ctx, 'POST', '/%d/review' % d.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'محامية'}).get_json()['item']
    assert j['status'] == 'draft' and j['reviewer_name_public'] is False and len(plat.pushes) == 1


@pytest.mark.parametrize('bad', ['yes', 1, 'true', None])
def test_review_name_consent_must_be_a_real_boolean(ctx, plat, bad):
    t = _term()
    r = call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'محامية', 'reviewer_name_public': bad})
    assert r.status_code == 400 and fresh(t.id).reviewed_at is None


def test_confirmed_term_substantive_edit_goes_back_to_under_review_and_stays_visible(ctx, plat):
    t = _term(status='published', reviewed=True)
    t.reviewer_name_public = True
    db.session.commit()
    j = call(ctx, 'PUT', '/%d' % t.id, {'definition_ar': 'تعريف مُعدَّل'}).get_json()
    assert j['review_cleared'] is True and j['unpublished'] is False and j['item']['status'] == 'under_review'
    f = fresh(t.id)
    assert f.reviewed_at is None and f.reviewer_name_public is False and f.published_at is not None
    assert plat.pushes == ['glossary:%d' % t.id]
    row = ctx['client'].get('/api/content/glossary').get_json()['terms']
    assert [x['slug'] for x in row] == ['force-majeure'] and row[0]['review_state'] == 'under_review' and row[0]['reviewed_by_name'] is None


def test_published_term_non_substantive_edit_keeps_state_and_requests_prerender(ctx, plat):
    t = _term(status='published', reviewed=True)
    assert call(ctx, 'PUT', '/%d' % t.id, {'related': ['x-y']}).status_code == 200
    f = fresh(t.id)
    assert f.status == 'confirmed' and f.reviewed_at is not None and plat.pushes == ['glossary:%d' % t.id]


def test_under_review_edit_stays_under_review(ctx, plat):
    t = _term(status='published')
    j = call(ctx, 'PUT', '/%d' % t.id, {'ar': 'القوة القاهرة (معدّل)'}).get_json()
    assert j['review_cleared'] is False and j['item']['status'] == 'under_review'


def test_unreview_of_confirmed_goes_to_under_review(ctx, plat):
    t = _term(status='published', reviewed=True)
    r = call(ctx, 'POST', '/%d/unreview' % t.id)
    assert r.get_json()['unpublished'] is False and r.get_json()['item']['status'] == 'under_review'
    f = fresh(t.id)
    assert f.reviewed_at is None and f.reviewer_name_public is False and plat.pushes == ['glossary:%d' % t.id]


def test_required_mode_substantive_edit_of_confirmed_goes_to_draft(ctx, plat):
    set_require(ctx, True)
    t = _term(status='published', reviewed=True)
    j = call(ctx, 'PUT', '/%d' % t.id, {'definition_ar': 'تعريف مُعدَّل'}).get_json()
    assert j['review_cleared'] is True and j['unpublished'] is True and j['item']['status'] == 'draft'
    f = fresh(t.id)
    assert f.status == 'draft' and f.reviewed_at is None and f.published_at is not None
    assert plat.pushes == ['glossary:%d' % t.id]                                           # الصفحة تسقط عند التوليد التالي
    assert call(ctx, 'POST', '/%d/publish' % t.id).status_code == 409                    # لا نشر قبل مراجعة جديدة
    assert call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'محامية'}).status_code == 200
    assert call(ctx, 'POST', '/%d/publish' % t.id).status_code == 200


def test_required_mode_unreview_of_published_goes_to_draft(ctx, plat):
    set_require(ctx, True)
    t = _term(status='published', reviewed=True)
    r = call(ctx, 'POST', '/%d/unreview' % t.id)
    assert r.get_json()['unpublished'] is True
    f = fresh(t.id)
    assert f.status == 'draft' and f.reviewed_at is None and plat.pushes == ['glossary:%d' % t.id]


def test_review_of_published_term_requests_prerender(ctx, plat):
    t = _term(status='published', reviewed=True)
    assert call(ctx, 'POST', '/%d/review' % t.id, {'reviewer_name': 'د. سارة', 'reviewer_role': 'محامية'}).status_code == 200
    assert plat.pushes == ['glossary:%d' % t.id]


# ——————————————————————————————————————————————— الإعداد (الافتراضي مغلق)

def test_setting_default_off_and_toggle_with_confirmation(ctx, plat):
    assert call(ctx, 'GET', '/settings').get_json()['require_review'] is False
    assert call(ctx, 'PUT', '/settings', {'require_review': 'no'}).status_code == 400
    assert call(ctx, 'PUT', '/settings', {}).status_code == 400
    r = call(ctx, 'PUT', '/settings', {'require_review': True})
    assert r.status_code == 200 and r.get_json()['require_review'] is True
    assert Setting.query.get(gr.SETTING_KEY).value == '1'
    assert call(ctx, 'GET', '/settings').get_json()['require_review'] is True
    assert [a[0] for a in audits('glossary.setting')] == ['glossary.setting']
    call(ctx, 'PUT', '/settings', {'require_review': True})                                # لا تغيير ⇒ لا سطر تدقيق جديد
    assert len(audits('glossary.setting')) == 1
    set_require(ctx, False)
    assert Setting.query.get(gr.SETTING_KEY).value == '0' and call(ctx, 'GET', '').get_json()['require_review'] is False


def test_turning_setting_on_reports_but_does_not_unpublish(ctx, plat):
    t = _term(status='published')
    r = call(ctx, 'PUT', '/settings', {'require_review': True})
    j = r.get_json()
    assert j['published_unreviewed'] == 1 and j['under_review'] == 1 and fresh(t.id).status == 'under_review'
    assert plat.pushes == []


def test_setting_garbage_value_in_store_means_off(ctx, plat):
    assert Setting.query.get(gr.SETTING_KEY) is None
    db.session.add(Setting(key=gr.SETTING_KEY, value='whatever'))
    db.session.commit()
    assert call(ctx, 'GET', '/settings').get_json()['require_review'] is False
    Setting.query.get(gr.SETTING_KEY).value = 'yes'
    db.session.commit()
    assert call(ctx, 'GET', '/settings').get_json()['require_review'] is True


def test_generic_settings_route_cannot_write_the_review_setting(ctx, plat):
    r = ctx['client'].put('/api/settings', headers=ctx['heads']['admin'], json={gr.SETTING_KEY: '1', 'other_key_x': 'v'})
    assert r.status_code == 400 and Setting.query.get(gr.SETTING_KEY) is None and Setting.query.get('other_key_x') is None
    assert ctx['client'].put('/api/settings', headers=ctx['heads']['admin'], json={'other_key_x': 'v'}).status_code == 200
    Setting.query.filter_by(key='other_key_x').delete()
    db.session.commit()


# ——————————————————————————————————————————————— ٦) الحذف

def test_delete_only_never_published_drafts(ctx, plat):
    d = _term('draft-one', 'مسودة', 'draft one')
    assert call(ctx, 'DELETE', '/%d' % d.id).status_code == 200 and fresh(d.id) is None
    assert audits('glossary.delete')[0][2] == {'slug': 'draft-one'}
    p = _term('pub-one', 'منشور', 'pub one', status='published', reviewed=True)
    assert call(ctx, 'DELETE', '/%d' % p.id).status_code == 409
    assert call(ctx, 'POST', '/%d/unpublish' % p.id).status_code == 200
    r = call(ctx, 'DELETE', '/%d' % p.id)
    assert r.status_code == 409 and fresh(p.id) is not None                                  # نُشر قبل ذلك ⇒ لا حذف
    assert call(ctx, 'DELETE', '/99999').status_code == 404


# ——————————————————————————————————————————————— ٧) الاستيراد

def test_builtin_sources_are_shipped_and_valid():
    seed, c1 = gr.load_source('seed'), gr.load_source('course1')
    assert len(seed) == 80 and len(c1) == 31
    for rows in (seed, c1):
        for i, raw in enumerate(rows):
            f, probs = gr.clean_row(raw, i)
            assert not probs, (raw.get('id'), probs)
    assert len({r['id'] for r in seed + c1}) == 111                                          # لا تعارض بين المصدرين
    assert gr.load_source('seed', base='/nonexistent') is None


def test_preview_is_read_only_and_counts(ctx, plat):
    _term('consideration', 'المقابل', 'consideration')
    r = call(ctx, 'POST', '/seed/preview', {'source': 'seed'}, confirmed=False)
    j = r.get_json()
    assert r.status_code == 200 and (j['total'], j['new_count'], j['skip_existing'], j['invalid_count']) == (80, 79, 1, 0)
    assert len(j['sample']) == 8 and j['sample'][0]['area_label']
    assert GlossaryTerm.query.count() == 1 and audits() == [] and plat.pushes == []
    assert call(ctx, 'POST', '/seed/preview', {'source': 'course1'}).get_json()['new_count'] == 31
    assert call(ctx, 'POST', '/seed/preview', {'source': 'nope'}).status_code == 400
    assert call(ctx, 'POST', '/seed/preview', {}).status_code == 400


def test_import_seed_creates_drafts_skips_existing_and_never_overwrites(ctx, plat):
    _term('consideration', 'نص محلي', 'consideration', definition_ar='تعريف كتبه الأدمن')
    r = call(ctx, 'POST', '/seed/import', {'source': 'seed'})
    j = r.get_json()
    assert r.status_code == 200 and j['imported'] == 79 and j['skip_existing'] == 1 and j['invalid_count'] == 0
    assert GlossaryTerm.query.count() == 80
    mine = GlossaryTerm.query.filter_by(slug='consideration').one()
    assert mine.ar == 'نص محلي' and mine.definition_ar == 'تعريف كتبه الأدمن' and mine.source == 'manual'
    rows = GlossaryTerm.query.filter(GlossaryTerm.slug != 'consideration').all()
    assert {t.status for t in rows} == {'draft'} and {t.source for t in rows} == {'seed'}
    assert all(t.reviewed_at is None and t.published_at is None and t.saha_topic_id is None for t in rows)
    a = audits('glossary.seed_import')
    assert len(a) == 1 and a[0][2] == {'source': 'seed', 'imported': 79, 'skipped_existing': 1, 'skipped_duplicate': 0, 'invalid': 0}
    assert plat.pushes == []
    r = call(ctx, 'POST', '/seed/import', {'source': 'seed'}).get_json()                    # مرّة ثانية ⇒ كله يُتخطّى
    assert r['imported'] == 0 and r['skip_existing'] == 80 and GlossaryTerm.query.count() == 80


def test_import_keeps_related_even_if_target_absent_and_course1_source(ctx, plat):
    call(ctx, 'POST', '/seed/import', {'source': 'seed'})
    t = GlossaryTerm.query.filter_by(slug='consideration').one()
    assert json.loads(t.related) == ['offer-acceptance', 'void-voidable', 'good-faith', 'legal-personality']
    j = call(ctx, 'POST', '/seed/import', {'source': 'course1'}).get_json()
    assert j['imported'] == 31 and GlossaryTerm.query.filter_by(source='course1').count() == 31
    h = GlossaryTerm.query.filter_by(slug='hereby').one()
    assert h.status == 'draft' and h.fr is None and h.reviewed_at is None


def test_import_upload_validates_every_row(ctx, plat):
    good = {'id': 'good-one', 'ar': 'صالح', 'en': 'good', 'area': 'general', 'definition_ar': 'تعريف.', 'related': ['not-yet-imported'], 'status': 'published',
            'reviewed_by_name': 'x'}
    rows = [good,
            {'id': 'no-ar', 'en': 'x', 'area': 'general', 'definition_ar': 'ت'},
            {'id': 'no-def', 'ar': 'س', 'en': 'x', 'area': 'general'},
            {'id': 'bad-area', 'ar': 'س', 'en': 'x', 'area': 'tax', 'definition_ar': 'ت'},
            {'id': 'has-url', 'ar': 'س', 'en': 'x', 'area': 'general', 'definition_ar': 'انظر https://x.test'},
            {'id': 'Bad_ID', 'ar': 'س', 'en': 'x', 'area': 'general', 'definition_ar': 'ت'},
            {'id': 'bad-rel', 'ar': 'س', 'en': 'x', 'area': 'general', 'definition_ar': 'ت', 'related': ['Bad Rel']},
            'not a dict',
            dict(good),                                                                      # مكرّر داخل الملف
            {'ar': 'بلا معرّف', 'en': 'Derived Slug', 'area': 'other', 'definition_ar': 'ت'}]   # الرابط يُشتقّ من الإنجليزي
    p = call(ctx, 'POST', '/seed/preview', {'source': 'upload', 'payload': {'items': rows}}).get_json()
    assert (p['total'], p['new_count'], p['invalid_count'], p['skip_duplicate_in_file']) == (10, 2, 7, 1)
    assert {x['row'] for x in p['problems']} == {2, 3, 4, 5, 6, 7, 8}
    j = call(ctx, 'POST', '/seed/import', {'source': 'upload', 'payload': {'items': rows}}).get_json()
    assert j['imported'] == 2
    g = GlossaryTerm.query.filter_by(slug='good-one').one()
    assert g.status == 'draft' and g.reviewed_by_name is None and g.source == 'upload' and json.loads(g.related) == ['not-yet-imported']
    assert GlossaryTerm.query.filter_by(slug='derived-slug').one().area == 'other'
    assert GlossaryTerm.query.count() == 2
    # شكل الرفع: قائمة مباشرة أيضًا؛ وشكل غير صالح ⇒ ٤٠٠
    assert call(ctx, 'POST', '/seed/preview', {'source': 'upload', 'payload': [good]}).get_json()['skip_existing'] == 1
    assert call(ctx, 'POST', '/seed/preview', {'source': 'upload', 'payload': {'x': 1}}).status_code == 400
    assert call(ctx, 'POST', '/seed/preview', {'source': 'upload'}).status_code == 400
    big = [dict(good, id='g%d' % i) for i in range(501)]
    assert call(ctx, 'POST', '/seed/preview', {'source': 'upload', 'payload': big}).status_code == 400


def test_seed_import_does_not_write_when_source_file_missing(ctx, plat, monkeypatch):
    monkeypatch.setattr(gr, 'load_source', lambda name, base=None: None)
    assert call(ctx, 'POST', '/seed/import', {'source': 'seed'}).status_code == 400
    assert GlossaryTerm.query.count() == 0 and audits() == []


# ——————————————————————————————————————————————— ٨) الفيد العام

def test_feed_public_published_only_and_public_fields_only(ctx, plat):
    _term('plain-draft', 'مسودة', 'plain draft')
    _term('reviewed-draft', 'مراجَعة', 'reviewed draft', reviewed=True)
    a = _term('contract-law', 'قانون العقود', 'contract law', status='published', reviewed=True, related=['plaintiff', 'plain-draft', 'ghost', 'contract-law'],
              countries_note_ar='يختلف بين الدول', saha_topic_id=TID)
    a.reviewer_name_public = True
    db.session.commit()
    _term('plaintiff', 'المدّعي', 'plaintiff', 'litigation', status='published', fr=None)
    c = ctx['client']
    r = c.get('/api/content/glossary')                                                       # بلا توكن
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store' and r.headers['Pragma'] == 'no-cache'
    j = r.get_json()
    assert j['source'] == 'dashboard' and [t['slug'] for t in j['terms']] == ['contract-law', 'plaintiff']
    assert 'plain-draft' not in json.dumps(j) and 'reviewed-draft' not in json.dumps(j)
    row = j['terms'][0]
    assert set(row) == {'id', 'slug', 'ar', 'en', 'fr', 'area', 'area_label', 'definition_ar', 'example_en', 'example_ar', 'false_friend_note_ar',
                        'countries_note_ar', 'related', 'review_state', 'reviewed_by_name', 'reviewed_by_role', 'reviewed_at', 'saha_topic_id',
                        'published_at', 'updated_at'}
    assert row['related'] == [{'slug': 'plaintiff', 'ar': 'المدّعي', 'en': 'plaintiff'}]     # القريب المنشور فقط، لا نفسه ولا مسودة ولا غائب
    assert row['saha_topic_id'] == TID and row['reviewed_by_name'] == 'أ. هبة الجندي' and row['reviewed_by_role'] == 'محامية'
    assert row['review_state'] == 'confirmed' and row['reviewed_at'] is not None
    assert row['countries_note_ar'] == 'يختلف بين الدول' and row['area_label'] == 'عقود'
    body = r.get_data(as_text=True)
    for private in ('x.test', 'glos-', 'status', 'created_at', 'reviewed_by_email', 'slug_frozen'):
        assert private not in body, private
    assert j['terms'][1]['fr'] is None and j['terms'][1]['reviewed_by_name'] is None and j['terms'][1]['reviewed_at'] is None
    assert j['terms'][1]['review_state'] == 'under_review'
    assert {x['code'] for x in j['areas']} >= {'other', 'contracts'}
    assert a.id == row['id']


def test_feed_hides_country_note_and_reviewer_when_not_confirmed(ctx, plat):
    _term('unrev', 'غير مراجَع', 'unrev', status='published', countries_note_ar='ملاحظة دول')
    row = ctx['client'].get('/api/content/glossary').get_json()['terms'][0]
    assert row['review_state'] == 'under_review'
    assert row['countries_note_ar'] is None and row['reviewed_by_name'] is None and row['reviewed_at'] is None


def test_feed_confirmed_without_name_consent_hides_name_and_role_only(ctx, plat):
    _term('anon', 'مجهول', 'anon', status='published', reviewed=True, countries_note_ar='ملاحظة دول')
    row = ctx['client'].get('/api/content/glossary').get_json()['terms'][0]
    assert row['review_state'] == 'confirmed' and row['reviewed_at'] is not None and row['countries_note_ar'] == 'ملاحظة دول'
    assert row['reviewed_by_name'] is None and row['reviewed_by_role'] is None
    assert 'هبة' not in json.dumps(row, ensure_ascii=False) and 'محامية' not in json.dumps(row, ensure_ascii=False)


def test_feed_inconsistent_row_is_treated_as_under_review(ctx, plat):
    t = _term('odd-state', 'شاذ', 'odd state', status='published', reviewed=True, countries_note_ar='ملاحظة')
    t.status = 'under_review'                       # ختم موجود لكن الحالة تحت التأكيد: لا نعرض اسمًا ولا ملاحظة
    t.reviewer_name_public = True
    db.session.commit()
    row = ctx['client'].get('/api/content/glossary').get_json()['terms'][0]
    assert row['review_state'] == 'under_review' and row['reviewed_by_name'] is None and row['countries_note_ar'] is None and row['reviewed_at'] is None


def test_feed_drops_invalid_topic_id_and_pending_drop_after_edit(ctx, plat):
    t = _term('odd', 'غريب', 'odd', status='published', reviewed=True, saha_topic_id='bad id!')
    assert ctx['client'].get('/api/content/glossary').get_json()['terms'][0]['saha_topic_id'] is None
    set_require(ctx, True)
    call(ctx, 'PUT', '/%d' % t.id, {'en': 'odd term'})                                       # جوهري والشرط مفعّل ⇒ مسودة ⇒ يخرج من الفيد
    assert ctx['client'].get('/api/content/glossary').get_json()['terms'] == []


def test_feed_empty_and_cors_header(ctx, plat):
    r = ctx['client'].get('/api/content/glossary', headers={'Origin': 'https://elprofessor.net'})
    assert r.get_json()['terms'] == [] and r.headers.get('Access-Control-Allow-Origin') == 'https://elprofessor.net'
    a = ctx['client'].get('/api/content/articles', headers={'Origin': 'https://elprofessor.net'})
    assert a.headers.get('Access-Control-Allow-Origin') == r.headers.get('Access-Control-Allow-Origin') and a.headers['Cache-Control'] == r.headers['Cache-Control']


def test_feed_payload_is_exposed_for_the_generator(ctx, plat):
    _term('pub', 'منشور', 'pub', status='published', reviewed=True)
    assert [t['slug'] for t in appmod._glossary_feed_payload()['terms']] == ['pub']


# ——————————————————————————————————————————————— ٩) نقاش الساحة (جسر بديل)

def test_topics_picker_published_only_with_valid_ids(ctx, plat):
    r = call(ctx, 'GET', '/topics')
    j = r.get_json()
    assert r.status_code == 200 and [t['id'] for t in j['topics']] == [TID, 'aaaaaaaa-0000-4000-8000-000000000001']
    assert set(j['topics'][0]) == {'id', 'title', 'status'}                                   # بلا السؤال ولا حقول المنصة الأخرى
    assert [c['method'] for c in plat.seen] == ['GET'] and plat.seen[0]['url'] == PLATFORM + '/api/bridge/topics'
    assert plat.seen[0]['headers'].get('X-ELP-Metrics-Secret') == SECRET


@pytest.mark.parametrize('mode,code', [('lost', 502), ('down403', 502), ('junk', 502)])
def test_topics_picker_failures(ctx, plat, mode, code):
    plat.mode = mode
    r = call(ctx, 'GET', '/topics')
    assert r.status_code == code
    if mode == 'lost':
        assert r.get_json()['no_reply'] is True and audits('glossary.no_reply')


def test_attach_and_detach_topic(ctx, plat):
    t = _term(status='published', reviewed=True)
    r = call(ctx, 'POST', '/%d/attach-topic' % t.id, {'saha_topic_id': TID})
    assert r.status_code == 200 and r.get_json()['url'] == 'https://app.elprofessor.net/?page=saha&topic=' + TID
    assert fresh(t.id).saha_topic_id == TID and plat.pushes == ['glossary:%d' % t.id]
    assert [c['method'] for c in plat.seen] == ['GET']                                         # قراءة فقط، لا إنشاء نقاش
    assert audits('glossary.topic_attach')[0][2] == {'topic_id': TID}
    assert call(ctx, 'POST', '/%d/attach-topic' % t.id, {'saha_topic_id': 'aaaaaaaa-0000-4000-8000-000000000001'}).status_code == 409   # فصل أولًا
    assert call(ctx, 'POST', '/%d/detach-topic' % t.id).status_code == 200
    assert fresh(t.id).saha_topic_id is None and plat.pushes[-1] == 'glossary:%d' % t.id
    assert call(ctx, 'POST', '/%d/detach-topic' % t.id).status_code == 409
    assert [a[0] for a in audits()] == ['glossary.topic_attach', 'glossary.topic_detach']
    assert [c['method'] for c in plat.seen if c['method'] != 'GET'] == []


def test_attach_refuses_unknown_draft_or_malformed_topic(ctx, plat):
    t = _term()
    for tid, code in ((TID2, 409), ('ffffffff-0000-4000-8000-000000000000', 409), ('bad id', 400), ('short', 400), (None, 400), (5, 400)):
        r = call(ctx, 'POST', '/%d/attach-topic' % t.id, {'saha_topic_id': tid})
        assert r.status_code == code, (tid, r.status_code)
    assert fresh(t.id).saha_topic_id is None and audits('glossary.topic_attach') == [] and plat.pushes == []


def test_attach_bridge_down_saves_nothing(ctx, plat):
    t = _term(status='published', reviewed=True)
    plat.mode = 'lost'
    r = call(ctx, 'POST', '/%d/attach-topic' % t.id, {'saha_topic_id': TID})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert fresh(t.id).saha_topic_id is None and plat.pushes == []


def test_attach_to_draft_does_not_request_prerender(ctx, plat):
    t = _term()
    assert call(ctx, 'POST', '/%d/attach-topic' % t.id, {'saha_topic_id': TID}).status_code == 200
    assert plat.pushes == []


def test_topic_not_settable_through_generic_update(ctx, plat):
    t = _term()
    call(ctx, 'PUT', '/%d' % t.id, {'saha_topic_id': TID, 'ar': 'اسم جديد'})
    assert fresh(t.id).saha_topic_id is None


# ——————————————————————————————————————————————— ١٠) طلب التوليد لا يُسقط الحفظ

def test_prerender_failure_never_fails_the_save(ctx, plat, monkeypatch):
    def boom(reason=''):
        raise RuntimeError('sftp down')
    monkeypatch.setattr(appmod, '_prerender_push_async', boom)
    t = _term(reviewed=True)
    assert call(ctx, 'POST', '/%d/publish' % t.id).status_code == 200 and fresh(t.id).status == 'confirmed'
    assert call(ctx, 'PUT', '/%d' % t.id, {'related': ['x-y']}).status_code == 200
    assert call(ctx, 'POST', '/%d/attach-topic' % t.id, {'saha_topic_id': TID}).status_code == 200
    assert call(ctx, 'POST', '/%d/unpublish' % t.id).status_code == 200 and fresh(t.id).status == 'draft'


def test_every_publish_affecting_change_requests_one_run(ctx, plat):
    set_require(ctx, True)
    t = _term(reviewed=True)
    call(ctx, 'POST', '/%d/publish' % t.id)                                                   # 1
    call(ctx, 'PUT', '/%d' % t.id, {'example_ar': 'مثال'})                                    # 2 (جوهري ⇒ مسودة)
    assert fresh(t.id).status == 'draft'
    assert len(plat.pushes) == 2 and set(plat.pushes) == {'glossary:%d' % t.id}
    call(ctx, 'PUT', '/%d' % t.id, {'example_ar': 'مثال آخر'})                                 # مسودة ⇒ لا طلب
    call(ctx, 'POST', '/seed/import', {'source': 'course1'})                                   # مسودات ⇒ لا طلب
    assert len(plat.pushes) == 2


# ——————————————————————————————————————————————— ١١) التسجيل والشحن

def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
        return fh.read()


def test_registered_guarded_in_app_and_docker_ships_it():
    app_src = _read('backend', 'app.py')
    i = app_src.index('import v2_glossary_routes')
    assert "logger.exception('v2 glossary routes not loaded')" in app_src[i:i + 300]
    assert app_src.rindex('try:', 0, i) > app_src.rindex('\n\n', 0, i) - 400
    assert app_src.index('# ---- v2 section routes begin') < i < app_src.index('# ---- v2 section routes end')
    d = _read('Dockerfile')
    assert 'COPY backend/v2_glossary_routes.py /app/v2_glossary_routes.py' in d
    assert 'backend/data/glossary_seed.json' in d and 'backend/data/glossary_course1.json' in d and '/app/data/' in d
    assert os.path.isfile(os.path.join(BACKEND, 'data', 'glossary_seed.json')) and os.path.isfile(os.path.join(BACKEND, 'data', 'glossary_course1.json'))


def test_module_does_not_import_app_and_model_is_created_at_boot():
    src = _read('backend', 'v2_glossary_routes.py')
    assert not re.search(r'^\s*(import app\b|from app import)', src, re.M)
    with flask_app.app_context():
        assert 'glossary_terms' in db.inspect(db.engine).get_table_names()
        cols = {c['name'] for c in db.inspect(db.engine).get_columns('glossary_terms')}
    assert cols >= {'id', 'slug', 'ar', 'en', 'fr', 'area', 'definition_ar', 'example_en', 'example_ar', 'false_friend_note_ar', 'countries_note_ar',
                    'related', 'status', 'reviewed_by_name', 'reviewed_by_role', 'reviewed_at', 'reviewer_name_public', 'saha_topic_id', 'source',
                    'created_at', 'updated_at', 'published_at'}


def test_no_real_network_in_module():
    src = _read('backend', 'v2_glossary_routes.py')
    assert 'requests' not in src and 'urllib' not in src and 'http://' not in src.replace('https?://', '')


def test_pure_helpers():
    assert gr.slugify('Force Majeure!') == 'force-majeure' and gr.slugify('العقد') == '' and gr.slugify('9abc') == ''
    assert gr.SLUG_RE.match('a') and gr.SLUG_RE.match('a-b-1') and not gr.SLUG_RE.match('a-') and not gr.SLUG_RE.match('A') and not gr.SLUG_RE.match('a' * 65)
    assert gr.clean_related(None) == ([], None) and gr.clean_related(['a-b', 'a-b'])[0] == ['a-b']


# ——————————————————————————————————————————————— ١٢) الاستمارة العامة POST /api/public/expert-reviews

PUB = '/api/public/expert-reviews'


@pytest.fixture
def pubctx(ctx, plat):
    appmod._RATE_BUCKETS.clear()
    yield dict(ctx, plat=plat)
    appmod._RATE_BUCKETS.clear()


def _sub(**kw):
    b = {'kind': 'glossary_term', 'ref': 'force-majeure', 'name': 'سارة أحمد', 'email': 'Sara@Example.test', 'specialty': 'law_practice',
         'verdict': 'confirm', 'show_name': True, 'website': ''}
    b.update(kw)
    return {k: v for k, v in b.items() if v is not ...}


def post_pub(ctx, body, ip='203.0.113.7', headers=None):
    h = {'X-Forwarded-For': ip}
    h.update(headers or {})
    return ctx['client'].post(PUB, json=body, headers=h)


def test_public_submission_is_stored_with_snapshots_and_no_auth(pubctx):
    t = _term(status='published')
    r = post_pub(pubctx, _sub())
    assert r.status_code == 201 and r.get_json() == {'ok': True}
    assert r.headers['Cache-Control'] == 'no-store'
    row = ExpertReviewSubmission.query.one()
    assert (row.kind, row.ref, row.ref_title, row.name, row.email, row.specialty, row.verdict, row.show_name, row.status) == \
        ('glossary_term', 'force-majeure', 'القوة القاهرة', 'سارة أحمد', 'sara@example.test', 'law_practice', 'confirm', True, 'pending')
    assert row.term_updated_at == t.updated_at and row.decided_at is None and row.decided_by is None and row.created_at is not None
    assert audits() == []                                                                  # الاستمارة العامة لا تكتب في سجل الأدمن


def test_public_submission_never_stores_ip_or_agent(pubctx):
    cols = {c['name'] for c in db.inspect(db.engine).get_columns('expert_review_submissions')}
    assert cols == {'id', 'kind', 'ref', 'ref_title', 'term_updated_at', 'name', 'email', 'specialty', 'specialty_other', 'verdict', 'text',
                    'show_name', 'status', 'created_at', 'decided_at', 'decided_by', 'admin_note'}
    assert not [c for c in cols if re.search(r'ip|agent|addr|host|ua$', c)]
    _term(status='published')
    post_pub(pubctx, _sub(text='ملاحظة'), ip='198.51.100.44', headers={'User-Agent': 'UniqueAgentXYZ/9.9', 'Referer': 'https://elprofessor.net/glossary/x'})
    blob = json.dumps([[getattr(r, c.name) for c in r.__table__.columns] for r in ExpertReviewSubmission.query.all()], default=str, ensure_ascii=False)
    for needle in ('198.51.100.44', '127.0.0.1', 'UniqueAgentXYZ', 'Referer', 'elprofessor.net/glossary'):
        assert needle not in blob, needle
    assert any('198.51.100.44' in k for k in appmod._RATE_BUCKETS)                          # العنوان مفتاح دلو في الذاكرة فقط، لا في أي جدول


def test_public_honeypot_fakes_success_and_stores_nothing(pubctx):
    _term(status='published')
    r = post_pub(pubctx, _sub(website='http://spam.test'))
    assert r.status_code == 201 and r.get_json() == {'ok': True} and ExpertReviewSubmission.query.count() == 0
    r = post_pub(pubctx, {'website': 'x'})                                                  # حمولة ناقصة + فخ ⇒ نفس النجاح الوهمي
    assert r.status_code == 201 and ExpertReviewSubmission.query.count() == 0


def test_public_honeypot_burns_a_strict_slot(pubctx):
    _term(status='published')
    for _ in range(gr.STRICT_LIMIT):
        assert post_pub(pubctx, _sub(website='bot')).status_code == 201
    r = post_pub(pubctx, _sub(email='real@example.test'))
    assert r.status_code == 429 and r.get_json() == {'error': 'rate_limited', 'detail': 'محاولات كثيرة، جرّب بعد قليل'}
    assert ExpertReviewSubmission.query.count() == 0


def test_public_strict_rate_limit_is_per_ip_and_invalid_attempts_do_not_burn_it(pubctx):
    _term(status='published')
    for _ in range(10):
        assert post_pub(pubctx, _sub(name='')).status_code == 400                           # أخطاء بريئة لا تستهلك الحصة
    for i in range(gr.STRICT_LIMIT):
        assert post_pub(pubctx, _sub(email='u%d@example.test' % i)).status_code == 201
    r = post_pub(pubctx, _sub(email='late@example.test'))
    assert r.status_code == 429 and r.get_json()['error'] == 'rate_limited'
    assert post_pub(pubctx, _sub(email='other@example.test'), ip='203.0.113.99').status_code == 201      # عنوان آخر
    assert ExpertReviewSubmission.query.count() == gr.STRICT_LIMIT + 1


def test_public_loose_rate_limit_applies_before_anything_else(pubctx):
    for _ in range(gr.LOOSE_LIMIT):
        assert post_pub(pubctx, {}).status_code == 400
    r = post_pub(pubctx, {'website': 'bot'})
    assert r.status_code == 429 and r.get_json()['error'] == 'rate_limited'


def test_public_forged_forwarded_for_uses_the_rightmost_address(pubctx):
    _term(status='published')
    for i in range(gr.STRICT_LIMIT):
        assert post_pub(pubctx, _sub(email='f%d@example.test' % i), ip='1.1.1.%d, 203.0.113.50' % i).status_code == 201
    assert post_pub(pubctx, _sub(email='g@example.test'), ip='9.9.9.9, 203.0.113.50').status_code == 429


@pytest.mark.parametrize('patch,needle', [
    ({'kind': 'book'}, 'نوع'), ({'kind': None}, 'نوع'), ({'ref': ''}, 'العنصر'), ({'ref': 'Bad Slug'}, 'العنصر'), ({'ref': 5}, 'العنصر'),
    ({'name': 'س'}, 'اسمك'), ({'name': 'x@y.test'}, 'اسمك'), ({'name': 'http://x.test'}, 'اسمك'), ({'name': 'ش' * 81}, 'اسمك'), ({'name': 7}, 'اسمك'),
    ({'email': 'nope'}, 'بريد'), ({'email': 'a@b'}, 'بريد'), ({'email': 'a b@c.test'}, 'بريد'), ({'email': 'x' * 250 + '@c.test'}, 'بريد'), ({'email': ...}, 'بريد'),
    ({'specialty': 'plumber'}, 'تخصص'), ({'specialty': ...}, 'تخصص'),
    ({'specialty': 'other'}, 'تخصصك'), ({'specialty': 'other', 'specialty_other': 'ص'}, 'تخصصك'), ({'specialty': 'other', 'specialty_other': 'ص' * 81}, 'تخصصك'),
    ({'verdict': 'maybe'}, 'اختر'), ({'verdict': ...}, 'اختر'),
    ({'verdict': 'suggest'}, 'التعديل'), ({'verdict': 'suggest', 'text': '   '}, 'التعديل'), ({'verdict': 'suggest', 'text': 'ط' * 2001}, 'أطول'),
    ({'text': 'ط' * 1001}, 'أطول'), ({'text': 5}, 'النص'),
    ({'show_name': 'yes'}, 'اسمك'), ({'show_name': 1}, 'اسمك'),
])
def test_public_validation_rejects_with_arabic_detail(pubctx, patch, needle):
    _term(status='published')
    r = post_pub(pubctx, _sub(**patch))
    j = r.get_json()
    assert r.status_code == 400 and j['error'] == 'invalid' and needle in j['detail'] and re.search('[؀-ۿ]', j['detail']), (patch, j)
    assert ExpertReviewSubmission.query.count() == 0


def test_public_body_that_is_not_an_object_is_400_not_500(pubctx):
    for raw in ('[]', '"x"', 'not json', ''):
        r = pubctx['client'].post(PUB, data=raw, content_type='application/json', headers={'X-Forwarded-For': '203.0.113.8'})
        assert r.status_code == 400 and r.get_json()['error'] == 'invalid', raw


def test_public_boundary_values_are_accepted(pubctx):
    _term(status='published')
    assert post_pub(pubctx, _sub(name='سع', email='a@b.co', specialty='other', specialty_other='خبير تحكيم', verdict='suggest', text='ط' * 2000)).status_code == 201
    row = ExpertReviewSubmission.query.one()
    assert row.specialty_other == 'خبير تحكيم' and len(row.text) == 2000
    assert post_pub(pubctx, _sub(email='b@b.co', text='ط' * 1000)).status_code == 201


def test_public_specialty_other_is_dropped_unless_other_and_text_is_optional_for_confirm(pubctx):
    _term(status='published')
    assert post_pub(pubctx, _sub(specialty='judiciary', specialty_other='ignored text')).status_code == 201
    row = ExpertReviewSubmission.query.one()
    assert row.specialty_other is None and row.text is None


@pytest.mark.parametrize('state', ['draft', 'missing'])
def test_public_unknown_or_unpublished_term_is_404_and_burns_nothing(pubctx, state):
    if state == 'draft':
        _term()
    r = post_pub(pubctx, _sub())
    assert r.status_code == 404 and ExpertReviewSubmission.query.count() == 0
    for i in range(gr.STRICT_LIMIT):                                                        # الـ٤٠٤ لا يستهلك الحصة الصارمة
        post_pub(pubctx, _sub())
    _term('real-one', 'حقيقي', 'real one', status='published')
    assert post_pub(pubctx, _sub(ref='real-one')).status_code == 201


def test_public_under_review_and_confirmed_terms_both_accept(pubctx):
    _term('a-term', 'أ', 'a term', status='published')
    _term('b-term', 'ب', 'b term', status='published', reviewed=True)
    assert post_pub(pubctx, _sub(ref='a-term')).status_code == 201 and post_pub(pubctx, _sub(ref='b-term')).status_code == 201


def test_public_one_pending_per_email_kind_ref_a_repeat_updates_it(pubctx):
    t = _term(status='published')
    post_pub(pubctx, _sub(verdict='confirm'))
    first = ExpertReviewSubmission.query.one()
    t.updated_at = datetime.datetime(2026, 10, 20)
    db.session.commit()
    r = post_pub(pubctx, _sub(email='  SARA@example.test ', verdict='suggest', text='الأصح كذا', name='سارة  أحمد', show_name=False,
                              specialty='other', specialty_other='محكّمة'))
    assert r.status_code == 201
    db.session.expire_all()
    row = ExpertReviewSubmission.query.one()
    assert row.id == first.id and row.verdict == 'suggest' and row.text == 'الأصح كذا' and row.name == 'سارة أحمد' and row.show_name is False
    assert row.specialty_other == 'محكّمة' and row.term_updated_at == datetime.datetime(2026, 10, 20) and row.status == 'pending'
    post_pub(pubctx, _sub(email='other@example.test'))
    _term('second', 'ثان', 'second', status='published')
    post_pub(pubctx, _sub(ref='second'))
    assert ExpertReviewSubmission.query.count() == 3                                        # بريد آخر، ومصطلح آخر: صفوف مستقلة


def test_public_repeat_after_a_decision_creates_a_new_pending_row(pubctx):
    _term(status='published')
    post_pub(pubctx, _sub())
    row = ExpertReviewSubmission.query.one()
    row.status = 'rejected'
    db.session.commit()
    post_pub(pubctx, _sub())
    assert sorted(r.status for r in ExpertReviewSubmission.query.all()) == ['pending', 'rejected']


def test_public_course_and_track_kinds_are_accepted_with_free_ref(pubctx):
    for kind, ref in (('course', 'legal-english-101'), ('track', 'track-7')):
        r = post_pub(pubctx, _sub(kind=kind, ref=ref, ref_title='عنوان الدورة'))
        assert r.status_code == 201, r.get_json()
    rows = {r.kind: r for r in ExpertReviewSubmission.query.all()}
    assert rows['course'].ref == 'legal-english-101' and rows['course'].ref_title == 'عنوان الدورة' and rows['course'].term_updated_at is None
    assert post_pub(pubctx, _sub(kind='course', ref='bad ref!')).status_code == 400
    # عقد الجلسة الأساسية: slug بحروف صغيرة وأرقام وشرطة حتى ٨٠، والـ٤٠٤ لـglossary_term وحده
    for bad in ('track_7', 'Course-1', 'a.b', '-lead', 'trail-', 'x' * 81):
        assert post_pub(pubctx, _sub(kind='track', ref=bad)).status_code == 400, bad
    assert post_pub(pubctx, _sub(kind='course', ref='x' * 80, email='edge@example.test')).status_code == 201
    assert post_pub(pubctx, _sub(kind='course', ref='never-seen-here', email='n@example.test')).status_code == 201
    assert post_pub(pubctx, _sub(kind='glossary_term', ref='UPPER')).status_code == 400


def test_public_cors_matches_the_contact_route(pubctx):
    _term(status='published')
    o = {'Origin': 'https://elprofessor.net'}
    pre = pubctx['client'].open(PUB, method='OPTIONS', headers=dict(o, **{'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'}))
    msg = pubctx['client'].open('/api/messages', method='OPTIONS', headers=dict(o, **{'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'content-type'}))
    assert pre.status_code == msg.status_code and pre.headers.get('Access-Control-Allow-Origin') == 'https://elprofessor.net'
    assert pre.headers.get('Access-Control-Allow-Origin') == msg.headers.get('Access-Control-Allow-Origin')
    assert 'POST' in pre.headers.get('Access-Control-Allow-Methods', '') and 'content-type' in pre.headers.get('Access-Control-Allow-Headers', '').lower()
    r = post_pub(pubctx, _sub(), headers=o)
    assert r.status_code == 201 and r.headers.get('Access-Control-Allow-Origin') == 'https://elprofessor.net'
    evil = post_pub(pubctx, _sub(email='e@example.test'), headers={'Origin': 'https://evil.test'})
    assert evil.headers.get('Access-Control-Allow-Origin') is None


def test_public_endpoint_needs_no_flag_and_ignores_dash_flag(pubctx, monkeypatch):
    _term(status='published')
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')                                          # الاستمارة عامة: لا تتبع مفتاح الأدمن الجديد
    assert post_pub(pubctx, _sub()).status_code == 201


# ——————————————————————————————————————————————— ١٣) صندوق «مراجعات القاموس» (أدمن)

def _submit(ctx, **kw):
    r = post_pub(ctx, _sub(**kw), ip=kw.pop('ip', None) or '203.0.113.%d' % (ExpertReviewSubmission.query.count() + 20))
    assert r.status_code == 201, r.get_json()
    return ExpertReviewSubmission.query.order_by(ExpertReviewSubmission.id.desc()).first()


def test_reviews_list_filters_counts_and_term_context(pubctx):
    t = _term(status='published')
    a = _submit(pubctx)
    b = _submit(pubctx, email='b@example.test', verdict='suggest', text='اقتراح')
    c = _submit(pubctx, kind='course', ref='legal-english-101', email='c@example.test', ref_title='دورة')
    b.status = 'rejected'
    db.session.commit()
    j = call(pubctx, 'GET', '/reviews').get_json()
    assert [i['id'] for i in j['items']] == [c.id, a.id] and j['counts'] == {'pending': 2, 'approved': 0, 'rejected': 1, 'all': 3}
    assert {s['code'] for s in j['specialties']} >= {'other', 'law_practice'} and dict((s['code'], s['label']) for s in j['specialties'])['other'] == 'أخرى'
    row = [i for i in j['items'] if i['id'] == a.id][0]
    assert row['email'] == 'sara@example.test' and row['specialty_text'] == 'محاماة' and row['term']['id'] == t.id and row['term_changed'] is False
    assert row['term']['definition_ar'] and [i for i in j['items'] if i['id'] == c.id][0]['term'] is None
    assert [i['id'] for i in call(pubctx, 'GET', '/reviews?status=rejected').get_json()['items']] == [b.id]
    assert [i['id'] for i in call(pubctx, 'GET', '/reviews?kind=course').get_json()['items']] == [c.id]
    assert len(call(pubctx, 'GET', '/reviews?status=all').get_json()['items']) == 3
    assert call(pubctx, 'GET', '/reviews?status=zzz').status_code == 400 and call(pubctx, 'GET', '/reviews?kind=zzz').status_code == 400
    assert call(pubctx, 'GET', '').get_json()['counts']['reviews_pending'] == 2
    assert 'تعديل' not in json.dumps(j['counts'])


def test_reviews_list_flags_a_term_that_changed_since_the_submission(pubctx):
    t = _term(status='published')
    _submit(pubctx)
    call(pubctx, 'PUT', '/%d' % t.id, {'definition_ar': 'تعريف جديد'})
    item = call(pubctx, 'GET', '/reviews').get_json()['items'][0]
    assert item['term_changed'] is True and item['term']['definition_ar'] == 'تعريف جديد'


def test_approve_confirm_stamps_a_published_term_as_confirmed(pubctx):
    t = _term(status='published')
    s = _submit(pubctx, specialty='other', specialty_other='خبيرة تحكيم', show_name=True)
    r = call(pubctx, 'POST', '/reviews/%d/approve' % s.id, {'admin_note': 'ملاحظة خاصة', 'by': 'evil@x.test'})
    j = r.get_json()
    assert r.status_code == 200 and j['ok'] and j['stamped'] is True and j['open_term_id'] is None and j['term']['status'] == 'confirmed'
    f = fresh(t.id)
    assert (f.status, f.reviewed_by_name, f.reviewed_by_role, f.reviewer_name_public) == ('confirmed', 'سارة أحمد', 'خبيرة تحكيم', True) and f.reviewed_at
    db.session.expire_all()
    s = db.session.get(ExpertReviewSubmission, s.id)
    assert (s.status, s.decided_by, s.admin_note) == ('approved', 'glos-admin@x.test', 'ملاحظة خاصة') and s.decided_at
    assert pubctx['plat'].pushes == ['glossary:%d' % t.id]
    a = audits('glossary.review_approve')
    assert len(a) == 1 and a[0][3] == 'glos-admin@x.test' and a[0][2]['stamped'] is True and a[0][2]['state'] == 'confirmed'
    assert 'sara@example.test' not in json.dumps(a, ensure_ascii=False) and 'evil' not in json.dumps(a)
    row = ctx_feed(pubctx)[0]
    assert row['review_state'] == 'confirmed' and row['reviewed_by_name'] == 'سارة أحمد' and row['reviewed_by_role'] == 'خبيرة تحكيم'


def ctx_feed(ctx):
    return ctx['client'].get('/api/content/glossary').get_json()['terms']


def test_approve_confirm_without_name_consent_keeps_the_name_private(pubctx):
    _term(status='published')
    s = _submit(pubctx, show_name=False)
    call(pubctx, 'POST', '/reviews/%d/approve' % s.id)
    row = ctx_feed(pubctx)[0]
    assert row['review_state'] == 'confirmed' and row['reviewed_by_name'] is None and row['reviewed_by_role'] is None


def test_approve_confirm_on_a_draft_stamps_but_keeps_it_a_draft(pubctx):
    t = _term(status='published')
    s = _submit(pubctx)
    call(pubctx, 'POST', '/%d/unpublish' % t.id)
    j = call(pubctx, 'POST', '/reviews/%d/approve' % s.id).get_json()
    assert j['term']['status'] == 'draft' and j['term']['reviewed'] is True and ctx_feed(pubctx) == []
    assert call(pubctx, 'POST', '/%d/publish' % t.id).get_json()['item']['status'] == 'confirmed'


def test_approve_a_suggestion_marks_it_and_leaves_the_term_untouched(pubctx):
    t = _term(status='published')
    s = _submit(pubctx, verdict='suggest', text='الأصح: القوة القاهرة العامة')
    j = call(pubctx, 'POST', '/reviews/%d/approve' % s.id).get_json()
    assert j['stamped'] is False and j['open_term_id'] == t.id and j['item']['status'] == 'approved'
    f = fresh(t.id)
    assert f.status == 'under_review' and f.reviewed_at is None and f.definition_ar.startswith('حدث خارج')
    assert audits('glossary.review_approve')[0][2]['stamped'] is False and pubctx['plat'].pushes == []


def test_approve_course_and_track_marks_done_without_any_stamp(pubctx):
    t = _term(status='published')
    s = _submit(pubctx, kind='course', ref='legal-english-101', email='c@example.test')
    j = call(pubctx, 'POST', '/reviews/%d/approve' % s.id).get_json()
    assert j['stamped'] is False and j['term'] is None and j['item']['status'] == 'approved'
    assert fresh(t.id).reviewed_at is None


def test_approve_warns_nothing_but_still_works_when_the_term_changed(pubctx):
    t = _term(status='published')
    s = _submit(pubctx)
    call(pubctx, 'PUT', '/%d' % t.id, {'definition_ar': 'نص مختلف تمامًا'})
    j = call(pubctx, 'POST', '/reviews/%d/approve' % s.id).get_json()
    assert j['ok'] is True and j['item']['term_changed'] is True and j['term']['status'] == 'confirmed'


def test_reject_with_and_without_note_and_double_decision_is_409(pubctx):
    t = _term(status='published')
    s = _submit(pubctx)
    r = call(pubctx, 'POST', '/reviews/%d/reject' % s.id, {'admin_note': 'خارج النطاق'})
    assert r.status_code == 200 and r.get_json()['item']['status'] == 'rejected' and r.get_json()['item']['admin_note'] == 'خارج النطاق'
    assert fresh(t.id).reviewed_at is None and audits('glossary.review_reject')[0][2] == {'kind': 'glossary_term', 'ref': 'force-majeure', 'verdict': 'confirm'}
    assert call(pubctx, 'POST', '/reviews/%d/reject' % s.id).status_code == 409
    assert call(pubctx, 'POST', '/reviews/%d/approve' % s.id).status_code == 409
    s2 = _submit(pubctx, email='z@example.test')
    assert call(pubctx, 'POST', '/reviews/%d/reject' % s2.id).get_json()['item']['admin_note'] == ''


def test_review_decisions_validate_and_404(pubctx):
    _term(status='published')
    s = _submit(pubctx)
    assert call(pubctx, 'POST', '/reviews/99999/approve').status_code == 404 and call(pubctx, 'POST', '/reviews/99999/reject').status_code == 404
    assert call(pubctx, 'POST', '/reviews/%d/reject' % s.id, {'admin_note': 'ن' * 501}).status_code == 400
    assert call(pubctx, 'POST', '/reviews/%d/reject' % s.id, {'admin_note': 5}).status_code == 400
    assert ExpertReviewSubmission.query.get(s.id).status == 'pending' and audits('glossary.review_') == []


def test_review_decisions_need_confirmed_true(pubctx):
    _term(status='published')
    s = _submit(pubctx)
    for kind in ('approve', 'reject'):
        r = call(pubctx, 'POST', '/reviews/%d/%s' % (s.id, kind), {'confirmed': 'yes'}, confirmed=False)
        assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR
    assert ExpertReviewSubmission.query.get(s.id).status == 'pending' and audits() == []


# ——————————————————————————————————————————————— ١٤) التنبيه: لا تليجرام، وصف واحد في الجرس

def test_no_telegram_line_is_sent_for_a_new_submission(pubctx, monkeypatch):
    sent = []
    for name in ('_telegram_send', 'send_telegram'):
        monkeypatch.setattr(appmod, name, lambda *a, **k: sent.append(a), raising=False)
    _term(status='published')
    assert post_pub(pubctx, _sub()).status_code == 201
    assert sent == [] and pubctx['plat'].seen == []
    src = open(os.path.join(BACKEND, 'v2_glossary_routes.py'), encoding='utf-8').read()
    assert 'telegram' not in src.lower() and '/api/bridge/brain' not in src


def test_notifications_bell_gets_one_aggregated_row_only_while_reviews_pend(pubctx, monkeypatch):
    monkeypatch.setattr(appmod, '_bridge_get', lambda *a, **k: {})                           # الجسر خارج هذا الاختبار
    _term(status='published')
    c, h = pubctx['client'], pubctx['heads']['admin']
    base = c.get('/api/notifications', headers=h).get_json()
    assert not [i for i in base['items'] if i['kind'] == 'glossary_review']
    s1 = _submit(pubctx)
    _submit(pubctx, email='b@example.test')
    j = c.get('/api/notifications', headers=h).get_json()
    rows = [i for i in j['items'] if i['kind'] == 'glossary_review']
    assert len(rows) == 1 and rows[0]['unread'] is True and rows[0]['detail'] == 'مراجعتان من متخصصين'
    assert 'sara' not in json.dumps(rows, ensure_ascii=False).lower()                        # لا بريد ولا اسم في الجرس
    call(pubctx, 'POST', '/reviews/%d/reject' % s1.id)
    assert [i for i in c.get('/api/notifications', headers=h).get_json()['items'] if i['kind'] == 'glossary_review'][0]['detail'] == 'مراجعة واحدة من متخصص'


# ——————————————————————————————————————————————— ١٥) جولة المراجعة: اتجاه النص · التكرار · الرابط المحجوز · الجمع

BIDI = '\u202e\u2066\u200f\u200e\u2069\u202a\u202c'


def test_bidi_controls_are_stripped_from_every_visitor_text(pubctx):
    _term(status='published')
    r = post_pub(pubctx, _sub(name='\u202eسارة\u2066 أحمد\u2069', specialty='other', specialty_other='م\u200fحكّمة\u202d', verdict='suggest',
                              text='الأصح\u202e كذا\u200f'))
    assert r.status_code == 201
    row = ExpertReviewSubmission.query.one()
    assert row.name == 'سارة أحمد' and row.specialty_other == 'محكّمة' and row.text == 'الأصح كذا'
    assert not any(c in (row.name + row.specialty_other + row.text) for c in BIDI)
    # اسم كله محارف اتجاه ⇒ بعد الحذف أقل من حرفين ⇒ مرفوض
    assert post_pub(pubctx, _sub(name='\u202e\u202e\u202eس', email='x@example.test')).status_code == 400


def test_bidi_controls_are_stripped_from_the_stamp_and_never_reach_the_feed(pubctx):
    t = _term(status='published')
    r = call(pubctx, 'POST', '/%d/review' % t.id, {'reviewer_name': '\u202eأ. هبة\u2066 الجندي', 'reviewer_role': 'م\u200eحامية\u202e', 'reviewer_name_public': True})
    assert r.status_code == 200
    f = fresh(t.id)
    assert f.reviewed_by_name == 'أ. هبة الجندي' and f.reviewed_by_role == 'محامية'
    row = ctx_feed(pubctx)[0]
    assert not any(c in json.dumps(row, ensure_ascii=False) for c in BIDI)
    assert call(pubctx, 'POST', '/%d/review' % t.id, {'reviewer_name': '\u202e\u202e\u2066', 'reviewer_role': 'محامية'}).status_code == 400


def test_a_repeat_with_the_same_name_updates_but_another_name_cannot_replace_it(pubctx):
    _term(status='published')
    post_pub(pubctx, _sub(name='سارة أحمد', verdict='confirm', show_name=False))
    first = ExpertReviewSubmission.query.one()
    # نفس البريد باسم مختلف من IP آخر: لا يستبدل الصف الأول ولا يغيّر اسمه ولا اختياره
    assert post_pub(pubctx, _sub(name='منتحل', verdict='suggest', text='نص مزوّر', show_name=True), ip='198.51.100.9').status_code == 201
    db.session.expire_all()
    rows = ExpertReviewSubmission.query.order_by(ExpertReviewSubmission.id).all()
    assert len(rows) == 2 and rows[0].id == first.id
    assert (rows[0].name, rows[0].verdict, rows[0].text, rows[0].show_name) == ('سارة أحمد', 'confirm', None, False)
    assert (rows[1].name, rows[1].verdict, rows[1].status) == ('منتحل', 'suggest', 'pending')
    # الاسم نفسه (بمسافات وحالة مختلفة) يحدّث صفه فقط
    post_pub(pubctx, _sub(name='  سارة   أحمد ', verdict='suggest', text='تعديلي', show_name=True), ip='198.51.100.10')
    db.session.expire_all()
    rows = ExpertReviewSubmission.query.order_by(ExpertReviewSubmission.id).all()
    assert len(rows) == 2 and rows[0].text == 'تعديلي' and rows[0].show_name is True and rows[1].name == 'منتحل' and rows[1].text == 'نص مزوّر'


def test_pending_rows_per_email_and_ref_are_capped(pubctx):
    _term(status='published')
    for i in range(gr.PENDING_PER_REF + 2):
        assert post_pub(pubctx, _sub(name='اسم رقم %s' % 'أبجدهوز'[i]), ip='198.51.100.%d' % (30 + i)).status_code == 201
    assert ExpertReviewSubmission.query.count() == gr.PENDING_PER_REF


def test_reserved_slug_index_is_refused_everywhere(ctx, plat):
    r = call(ctx, 'POST', '', _new(slug='index'))
    assert r.status_code == 400 and gr.RESERVED_SLUG_AR in json.dumps(r.get_json(), ensure_ascii=False)
    assert GlossaryTerm.query.count() == 0
    # الاشتقاق من الإنجليزي لا ينتج الاسم المحجوز
    assert gr.slugify('Index') == 'index-term' and gr.slugify('index') != 'index'
    r = call(ctx, 'POST', '', _new(en='Index'))
    assert r.status_code == 200 and r.get_json()['item']['slug'] == 'index-term'
    # تعديل رابط مسودة إلى المحجوز
    t = _term('ok-slug')
    assert call(ctx, 'PUT', '/%d' % t.id, {'slug': 'index'}).status_code == 400 and fresh(t.id).slug == 'ok-slug'
    # استيراد صف رابطه المحجوز يُرفض ضمن الأخطاء
    j = call(ctx, 'POST', '/seed/import', {'source': 'upload', 'payload': {'items': [{'id': 'index', 'ar': 'أ', 'en': 'a', 'definition_ar': 'د', 'area': 'general'}]}}).get_json()
    assert not GlossaryTerm.query.filter_by(slug='index').count() and j.get('created', j.get('new_count', 0)) == 0


def test_a_legacy_row_with_the_reserved_slug_cannot_be_published(ctx, plat):
    t = _term('legacy-x')
    t.slug = 'index'
    db.session.commit()
    r = call(ctx, 'POST', '/%d/publish' % t.id)
    assert r.status_code == 409 and fresh(t.id).status == 'draft' and plat.pushes == []


def test_a_submission_for_the_reserved_ref_is_invalid(pubctx):
    assert post_pub(pubctx, _sub(ref='index')).status_code == 400


def test_ar_count_matches_the_dashboard_plural_helper():
    f = ['مراجعة واحدة', 'مراجعتان', 'مراجعات', 'مراجعةً']
    assert [gr.ar_count(n, f) for n in (1, 2, 3, 10, 11, 25)] == ['مراجعة واحدة', 'مراجعتان', '٣ مراجعات', '١٠ مراجعات', '١١ مراجعةً', '٢٥ مراجعةً']
