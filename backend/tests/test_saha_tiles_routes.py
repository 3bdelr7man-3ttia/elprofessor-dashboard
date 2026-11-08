# -*- coding: utf-8 -*-
"""مسارات «الساحة» و«الديوان» و«الفرص» في الداشبورد (docs/v2/saha-tiles/SPEC.md). جسور المنصة بديل في الذاكرة.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_saha_tiles_routes.py

⛔ صفر شبكة حقيقية وصفر نداء حقيقي (ولا موديل ذكاء): المنصة في الذاكرة (`FakePlatform`)، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.

اللي بيثبّته:
  ١. أدمن بس في كل المسارات · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` · السرّ يطلع مع كل نداء.
  ٢. كل كتابة تطلب `confirmed:true` بالظبط (قبل أي نداء) ولا تُرسَل · `by` من التوكن وحده · قايمة بيضا للمرسَل وللردود.
  ٣. التحقق قبل أي نداء: https بس (الرابط الرسمي · الصورة · الغلاف · رابط الدورة) · أنواع وتواريخ وأسطر الشروط · اللجنة ثلاثة · الفائزون.
  ٤. الاستيراد: تجربة (`dry_run=true`) بلا تأكيد وبلا كتابة، ثم الحقيقي بتأكيد · جسم فاضي = ملف المنصة · ملف مرفوع يتفحص شكله.
  ٥. رد ضايع ⇒ ٥٠٢ و`no_reply` وبلا إعادة محاولة وبلا تدقيق نجاح · نصوص المنصة العربية (٤٠٤ ٤٠٩ ٤٢٢) تعدّي بنفس الكود · مصدر غاب ⇒ `bridge_missing`.
  ٦. التذكير الدوري: سرّ الجسر أولًا (٤٠١) ثم المفتاح (٤٠٤) · المنصة مقفولة ⇒ `enabled:false` والشاشة «التذكير مقفول» · تدقيق عند الإرسال أو الخطأ فقط.
  ٧. التقرير: القيم الغايبة تفضل null (مش صفر).
"""
import copy
import datetime
import json
import os

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Setting  # noqa: E402

PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2saha-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
BAD_JS = 'javascript:alert(1)'


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else b''
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


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


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2saha-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


# ------------------------------------------------------------------ منصة بديلة في الذاكرة
def _job(i, kind='grant', review='pending', **kw):
    row = {'id': 'job-%d' % i, 'title': 'منحة %d' % i, 'title_en': '', 'employer': 'جهة', 'place': '', 'company': 'جهة', 'location': '', 'country': 'GB',
           'employment_type': '', 'specialty': '', 'body': '', 'source_url': 'https://x.org/%d' % i, 'source_label': '', 'posted_at': '',
           'expires_at': '', 'expired': False, 'logo_initial': 'ج', 'status': 'open', 'opp_status': 'draft', 'created_at': '2026-11-01T00:00:00Z',
           'updated_at': '', 'kind': kind, 'provider': 'جهة', 'language': 'en', 'funding': 'full', 'eligibility_ar': ['خريج قانون'], 'covers_ar': 'رسوم',
           'deadline': '2026-12-08', 'deadline_text': '', 'days_left': 30, 'official_url': 'https://x.org/%d' % i, 'source_name': 'x.org',
           'verified_at': '2026-10-30', 'image': '', 'featured': False, 'review_status': review, 'reject_reason': '', 'submitted_by': 'm@x.test',
           'note': '', 'decided_at': '', 'seed_id': '', 'poster_email': 'secret-poster@x.test', 'internal_flag': 'x'}
    row.update(kw)
    return row


class FakePlatform(object):
    def __init__(self):
        self.news = [{'id': 'n-1', 'title': 'خبر', 'summary': 's', 'body': 'b', 'source_name': 'مصدر', 'source_url': 'https://s.test/1', 'extra_sources': [],
                      'country': 'EG', 'specialty': '', 'target_audience': 'عام', 'status': 'draft', 'is_published': False, 'created_at': 'x',
                      'published_at': '', 'category': 'أخرى', 'featured': False, 'cover_url': BAD_JS, 'related_product': None, 'topic_id': None,
                      'secret_field': 'leak'},
                     {'id': 'n-2', 'title': 'خبر منشور', 'status': 'published', 'source_url': BAD_JS}]
        self.topics = [{'id': 'tp-1', 'title': 'نقاش', 'status': 'open', 'source': 'human', 'opinions_count': 2, 'expert_opinions_count': 1,
                        'created_at': 'x', 'author_email': 'leak@x.test', 'ai_answer': 'leak'}]
        self.opinions = [{'id': 'op-1', 'topic_id': 'tp-1', 'topic_title': 'نقاش', 'author_email': 'a@x.test', 'body': 'رأي', 'status': 'pending',
                          'is_expert': False, 'author_kind': 'member', 'kind': 'opinion', 'created_at': 'x', 'edited': False, 'side': 'a',
                          'ai_moderation': {'x': 1}}]
        self.jobs = [_job(1), _job(2, kind='training', review='draft'), _job(3, kind='job', review='published', image=BAD_JS)]
        self.settings = {'prep_course_url': 'https://courses.test/prep', 'updated_at': 'x'}
        self.challenges = [{'id': 'CH_1', 'slug': 'c1', 'title': 'تحدٍّ', 'brief': '', 'kind_allowed': ['story'], 'word_cap': 500,
                            'opens_at': '2026-11-01T00:00:00+00:00', 'closes_at': '2026-11-20T00:00:00+00:00', 'results_at': '', 'status': 'closed',
                            'prizes': [{'type': 'certificate', 'label': '', 'ref': ''}], 'jury': [{'name': 'أ', 'title': ''}], 'sponsor': None,
                            'cover_url': '', 'created_by': 'dashboard', 'created_at': 'x', 'updated_at': 'x', 'winners': [], 'awards': [],
                            'entries_count': 3}]
        self.works = [{'id': 'CR_1', 'slug': 'w1', 'title': 'عمل', 'kind': 'story', 'creator_email': 'w@x.test', 'creator_name': 'كاتب',
                       'status': 'pending_review', 'media': {'provider': 'youtube', 'video_id': 'abc', 'hash': 'h'}, 'media_url': BAD_JS,
                       'cover_url': 'https://i.test/c.png', 'body': 'نص', 'comments_locked': False, 'featured': False, 'internal': 'x'},
                      {'id': 'CR_2', 'slug': 'w2', 'title': 'منشور', 'kind': 'film', 'status': 'published'}]
        self.comments = [{'id': 'cm-1', 'work_id': 'CR_2', 'work_title': 'منشور', 'user_email': 'u@x.test', 'display_name': 'قارئ', 'body': 'تعليق',
                          'status': 'visible', 'created_at': 'x', 'ip': '1.2.3.4'}]
        self.report = {'window_days': 30, 'visitors': None, 'legal_open_share': None, 'signups': None, 'share_card_clicks': 0, 'return_7d': None,
                       'entries_per_challenge': [{'challenge_id': 'CH_1', 'slug': 'c1', 'title': 'تحدٍّ', 'entries': 3, 'x': 1}],
                       'works_acceptance': {'submitted': 4, 'accepted': 3, 'ratio': 0.75}, 'generated_at': 'x', 'extra': 'leak'}
        self.reminders_enabled = False
        self.reminder_stats = {'opportunities': 2, 'sent': 5, 'skipped_already': 1, 'skipped_toggle_off': 0, 'errors': 0}
        self.forced = {}
        self.backfills = []
        self.down = set()
        self.missing = set()

    def handle(self, method, path, params, body):
        key = (method, path)
        if key in self.forced:
            return self.forced[key]
        if path in self.down:
            return 503, {'detail': 'x'}
        if path in self.missing:
            return 404, {'detail': 'Not Found'}
        if method == 'GET' and path == '/api/bridge/news':
            rows = [n for n in self.news if not params.get('status') or n.get('status') == params['status']]
            return 200, {'news': rows, 'count': len(rows)}
        if method == 'PUT' and path.startswith('/api/bridge/news/'):
            n = [x for x in self.news if x['id'] == path.rsplit('/', 1)[1]]
            if not n:
                return 404, {'detail': 'News item not found'}
            n[0].update({k: v for k, v in body.items() if k != 'by'})
            return 200, n[0]
        if method == 'POST' and path == '/api/bridge/news/run':
            return 200, {'ok': True, 'ran_at': 'now', 'total_created': 2, 'total_held_for_review': 1, 'total_skipped_not_legal': 4,
                         'per_country': [{'country': 'EG', 'fetched': 9, 'created': 2, 'errors': 0, 'held_for_review': 1, 'skipped_not_legal': 4, 'x': 1}]}
        if method == 'GET' and path == '/api/bridge/topics':
            return 200, [t for t in self.topics if not params.get('status') or t['status'] == params['status']]
        if method == 'POST' and path.startswith('/api/bridge/topics/') and path.rsplit('/', 1)[1] in ('hide', 'restore'):
            _, _, _, _, tid, act = path.split('/')
            t = [x for x in self.topics if x['id'] == tid]
            if not t:
                return 404, {'detail': 'Topic not found'}
            t[0]['legal_gate'] = {'ok': act == 'restore', 'by': 'human', 'reason': 'human:' + act, 'themes': ['x'], 'secret': 1}
            return 200, t[0]
        if method == 'POST' and path == '/api/bridge/legal-gate/backfill':
            self.backfills.append(dict(body))
            applied = body.get('apply') is True
            hidden = [{'id': 'n-9', 'title': 'خبر رياضي', 'reason': 'off-theme', 'status': 'published', 'x': 1}]
            return 200, {'ok': True, 'dry_run': not applied, 'applied': applied, 'archive': False, 'version': 'lg1',
                         'collections': {'news': {'scanned': 5, 'would_hide': 1, 'would_pass': 4, 'changed': 1, 'skipped_human': 0,
                                                  'skipped_linked': 0, 'stamped': 5 if applied else 0, 'archived': 0, 'hidden': hidden, 'leak': 'x'},
                                         'topics': {'scanned': 2, 'would_hide': 0, 'would_pass': 2, 'hidden': []},
                                         'articles': {'error': 'read_failed'}, 'users': {'scanned': 9}}}
        if method == 'GET' and path == '/api/bridge/opinions':
            rows = [o for o in self.opinions if (params.get('status') in (None, 'all') or o['status'] == params['status'])
                    and (not params.get('topic_id') or o['topic_id'] == params['topic_id'])]
            return 200, rows
        if method == 'POST' and path.startswith('/api/bridge/opinions/'):
            _, _, _, _, oid, act = path.split('/')
            o = [x for x in self.opinions if x['id'] == oid]
            if not o:
                return 404, {'detail': 'Opinion not found'}
            o[0]['status'] = 'rejected' if act == 'reject' else 'approved'
            return 200, o[0]
        if method == 'GET' and path == '/api/bridge/jobs':
            rows = [j for j in self.jobs if (not params.get('review_status') or j['review_status'] == params['review_status'])
                    and (not params.get('kind') or params['kind'] == 'all' or j['kind'] == params['kind'] or (params['kind'] == 'grants' and j['kind'] in ('grant', 'fellowship')))]
            return 200, {'jobs': rows, 'count': len(rows)}
        if method == 'GET' and path.startswith('/api/bridge/jobs/'):
            j = [x for x in self.jobs if x['id'] == path.rsplit('/', 1)[1]]
            return (200, j[0]) if j else (404, {'detail': 'Job not found'})
        if method == 'POST' and path == '/api/bridge/jobs':
            row = _job(len(self.jobs) + 1, kind=body.get('kind', 'job'), review='published' if body.get('publish') else 'draft', title=body['title'])
            self.jobs.append(row)
            return 200, row
        if method == 'PUT' and path.startswith('/api/bridge/jobs/'):
            j = [x for x in self.jobs if x['id'] == path.rsplit('/', 1)[1]]
            if not j:
                return 404, {'detail': 'Job not found'}
            j[0].update({k: v for k, v in body.items() if k not in ('by', 'publish')})
            return 200, j[0]
        if method == 'DELETE' and path.startswith('/api/bridge/jobs/'):
            j = [x for x in self.jobs if x['id'] == path.rsplit('/', 1)[1]]
            if j and j[0]['kind'] == 'job':
                return 409, {'detail': 'الوظائف تُقفل ولا تُحذف'}
            return 200, {'ok': True, 'deleted': path.rsplit('/', 1)[1]}
        if method == 'POST' and path.endswith('/decide') and path.startswith('/api/bridge/jobs/'):
            j = [x for x in self.jobs if x['id'] == path.split('/')[4]]
            if not j:
                return 404, {'detail': 'Job not found'}
            if body['decision'] == 'approve' and not j[0]['official_url']:
                return 422, {'detail': 'أكمل عنوان الإعلان قبل النشر'}
            j[0]['review_status'] = 'published' if body['decision'] == 'approve' else 'rejected'
            return 200, j[0]
        if path == '/api/bridge/opportunities/settings':
            if method == 'GET':
                return 200, self.settings
            self.settings = {'prep_course_url': body['prep_course_url'], 'updated_at': 'now'}
            return 200, self.settings
        if method == 'POST' and path == '/api/bridge/opportunities/import-seed':
            dry = params.get('dry_run') == 'true'
            return 200, {'created': 34, 'filled': 1, 'skipped_unverified': 4, 'unchanged': 2, 'warnings': ['id: تحذير'], 'dry': dry, 'extra': 'x'}
        if method == 'POST' and path == '/api/bridge/opportunities/run-reminders':
            if not self.reminders_enabled:
                return 200, {'enabled': False, 'opportunities': 0, 'sent': 0, 'skipped_already': 0, 'skipped_toggle_off': 0, 'errors': 0}
            return 200, dict(self.reminder_stats, enabled=True)
        if method == 'GET' and path == '/api/bridge/creative':
            rows = [w for w in self.works if w['status'] == params.get('status')]
            return 200, {'items': rows, 'count': len(rows)}
        if method == 'POST' and path == '/api/bridge/creative':
            row = {'id': 'CR_9', 'slug': 'up', 'title': body['title'], 'kind': body['kind'], 'status': 'published', 'featured': bool(body.get('featured'))}
            self.works.append(row)
            return 200, row
        if method == 'POST' and path.endswith('/decide') and path.startswith('/api/bridge/creative/'):
            w = [x for x in self.works if x['id'] == path.split('/')[4]]
            if not w:
                return 404, {'detail': 'العمل غير موجود'}
            w[0]['status'] = 'published' if body['decision'] == 'approve' else 'rejected'
            return 200, w[0]
        if method == 'PUT' and path.startswith('/api/bridge/creative/'):
            w = [x for x in self.works if x['id'] == path.rsplit('/', 1)[1]]
            if not w:
                return 404, {'detail': 'العمل غير موجود'}
            if body.get('status') == 'hidden' and w[0]['status'] != 'published':
                return 409, {'detail': 'الإخفاء للأعمال المنشورة فقط'}
            w[0].update({k: v for k, v in body.items() if k != 'by'})
            return 200, w[0]
        if method == 'GET' and path == '/api/bridge/diwan/comments':
            return 200, {'items': [c for c in self.comments if c['status'] == params.get('status')], 'count': 1}
        if method == 'POST' and path.startswith('/api/bridge/diwan/comments/'):
            c = [x for x in self.comments if x['id'] == path.split('/')[5]]
            if not c:
                return 404, {'detail': 'التعليق غير موجود'}
            c[0]['status'] = 'hidden'
            return 200, {'ok': True, 'comment': c[0]}
        if method == 'GET' and path == '/api/bridge/diwan/challenges':
            rows = [c for c in self.challenges if not params.get('status') or c['status'] == params['status']]
            return 200, {'items': rows, 'count': len(rows)}
        if method == 'POST' and path == '/api/bridge/diwan/challenges':
            row = dict(self.challenges[0], id='CH_new', title=body['title'], status=body.get('status', 'draft'))
            return 200, row
        if method == 'PUT' and path.startswith('/api/bridge/diwan/challenges/'):
            if path.endswith('CH_res'):
                return 409, {'detail': 'أُعلنت النتائج، لا تعديل غير الغلاف والوصف'}
            return 200, dict(self.challenges[0], **{k: v for k, v in body.items() if k != 'by'})
        if method == 'POST' and path.endswith('/winners'):
            return 200, {'ok': True, 'already': False, 'challenge': dict(self.challenges[0], status='results'),
                         'certificates': [{'place': w['place'], 'work_id': w['work_id'], 'code': 'C%d' % w['place'], 'z': 1} for w in body['winners']], 'emails_sent': 3}
        if method == 'GET' and path == '/api/bridge/diwan/report':
            return 200, self.report
        return 404, {'detail': 'Not Found'}


class Plat(object):
    def __init__(self):
        self.ef = FakePlatform()
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'headers': dict(headers or {}),
                          'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        return _Resp(*self.ef.handle(method.upper(), url[len(PLATFORM):], params or {}, json or {}))

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]

    def writes(self):
        return [c for c in self.seen if c['method'] != 'GET']


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    with flask_app.app_context():
        row = db.session.get(Setting, 'v2saha_reminders_last')
        if row:
            db.session.delete(row)
            db.session.commit()
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _call(ctx, method, path, body=None, role='admin', headers=None):
    h = dict(ctx['heads'][role]) if role else {}
    h.update(headers or {})
    kw = {'headers': h}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


def _audits(prefix):
    with flask_app.app_context():
        return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email) for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%')).order_by(AuditLog.id).all()]


S = '/api/v2/saha'
D = '/api/v2/diwan'
READS = [S + '/news', S + '/topics', S + '/opinions', S + '/opportunities', S + '/opportunities/job-1', S + '/settings', S + '/reminders',
         D + '/works', D + '/comments', D + '/challenges', D + '/report']
C = {'confirmed': True}
WORK_UP = {'title': 'فيلم', 'kind': 'film', 'ai_assisted': False, 'media_url': 'https://youtu.be/abc', 'confirmed': True}
OPP_NEW = {'kind': 'grant', 'publish': False, 'title': 'منحة جديدة', 'official_url': 'https://grant.org/apply', 'confirmed': True}
CH_NEW = {'title': 'تحدٍّ جديد', 'opens_at': '2026-12-01T00:00:00Z', 'closes_at': '2026-12-20T00:00:00Z', 'confirmed': True}
WRITES = [('PUT', S + '/news/n-1', {'status': 'published', 'confirmed': True}),
          ('POST', S + '/news/run', dict(C)),
          ('POST', S + '/opinions/op-1/hide', dict(C)),
          ('POST', S + '/opinions/op-1/restore', dict(C)),
          ('POST', S + '/topics/tp-1/hide', dict(C)),
          ('POST', S + '/topics/tp-1/restore', dict(C)),
          ('POST', S + '/legal-gate/apply', {'confirmed': True, 'ids': ['n-9']}),
          ('POST', S + '/opportunities', OPP_NEW),
          ('PUT', S + '/opportunities/job-1', {'featured': True, 'confirmed': True}),
          ('DELETE', S + '/opportunities/job-1', dict(C)),
          ('POST', S + '/opportunities/job-1/decide', {'decision': 'approve', 'confirmed': True}),
          ('PUT', S + '/settings', {'prep_course_url': 'https://courses.test/p', 'confirmed': True}),
          ('POST', S + '/opportunities/seed/import', dict(C)),
          ('POST', S + '/reminders/run', dict(C)),
          ('POST', D + '/works', WORK_UP),
          ('POST', D + '/works/CR_1/decide', {'decision': 'approve', 'confirmed': True}),
          ('PUT', D + '/works/CR_2', {'featured': True, 'confirmed': True}),
          ('POST', D + '/comments/cm-1/hide', dict(C)),
          ('POST', D + '/challenges', CH_NEW),
          ('PUT', D + '/challenges/CH_1', {'brief': 'وصف', 'confirmed': True}),
          ('POST', D + '/challenges/CH_1/winners', {'winners': [{'place': 1, 'work_id': 'CR_2', 'jury_line': 'أفضل'}], 'confirmed': True})]
ADMIN_ONLY = READS + [S + '/opportunities/seed/preview']


# ---------------------------------------------------------------- ١) الأدوار والمفتاح و no-store

@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_every_route_is_admin_only(ctx, plat, role):
    for path in READS:
        assert _call(ctx, 'GET', path, role=role).status_code == 403, (role, path)
    for m, path, body in WRITES + [('POST', S + '/opportunities/seed/preview', {}), ('POST', S + '/legal-gate/check', {})]:
        assert _call(ctx, m, path, body, role=role).status_code == 403, (role, m, path)
    for path in READS:
        assert _call(ctx, 'GET', path, role=None).status_code == 401
    for m, path, body in WRITES:
        assert _call(ctx, m, path, body, role=None).status_code == 401
    assert plat.seen == []


def test_every_route_is_closed_when_the_switch_is_off_with_no_platform_call(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    for path in READS:
        assert _call(ctx, 'GET', path).status_code == 404, path
    for m, path, body in WRITES + [('POST', S + '/opportunities/seed/preview', {}), ('POST', S + '/legal-gate/check', {})]:
        assert _call(ctx, m, path, body).status_code == 404, path
    assert _call(ctx, 'POST', S + '/reminders/cron', None, role=None, headers={'X-ELP-Metrics-Secret': SECRET}).status_code == 404
    assert plat.seen == []


def test_every_reply_is_no_store_and_the_secret_goes_out(ctx, plat):
    rs = [_call(ctx, 'GET', p) for p in READS] + [_call(ctx, m, p, b) for m, p, b in WRITES] + [_call(ctx, 'GET', S + '/news?status=zzz')]
    assert all(r.headers.get('Cache-Control') == 'no-store' for r in rs), [r.status_code for r in rs if r.headers.get('Cache-Control') != 'no-store']
    assert plat.seen and all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)


@pytest.mark.parametrize('method,path,body', WRITES)
def test_a_write_needs_an_exact_true_confirmation_before_any_call(ctx, plat, method, path, body):
    for bad in (None, False, 'true', 1, 'yes'):
        b = dict(body)
        if bad is None:
            b.pop('confirmed')
        else:
            b['confirmed'] = bad
        r = _call(ctx, method, path, b)
        assert r.status_code == 400 and CONFIRM_AR in r.get_json()['error'], (bad, r.get_json())
    assert plat.writes() == []


@pytest.mark.parametrize('method,path,body', WRITES)
def test_a_write_sends_by_from_the_token_and_never_the_confirmation(ctx, plat, method, path, body):
    r = _call(ctx, method, path, dict(body, by='attacker@evil.test', injected='x'))
    assert r.status_code == 200, r.get_json()
    w = plat.writes()
    assert len(w) == 1, 'نداء واحد بلا إعادة محاولة'
    sent = w[0]['json']
    if path.endswith('seed/import'):
        assert sent is None                                      # جسم فاضي = ملف المنصة
    else:
        assert sent['by'] == ADMIN_EMAIL and 'confirmed' not in sent and 'injected' not in sent, sent
    assert not any(a[3] != ADMIN_EMAIL for a in _audits('saha.') + _audits('diwan.') if a[1] != 'reminders')


# ---------------------------------------------------------------- ٢) الأخبار

def test_news_list_forwards_a_clean_status_and_whitelists_fields_and_links(ctx, plat):
    d = _call(ctx, 'GET', S + '/news').get_json()
    assert plat.calls('/api/bridge/news')[0]['params'] == {'status': 'draft'}
    assert [n['id'] for n in d['items']] == ['n-1'] and 'secret_field' not in d['items'][0]
    assert d['items'][0]['cover_url'] == ''                      # javascript: لا يوصل الشاشة
    assert d['total'] == 1 and d['status'] == 'draft'
    d = _call(ctx, 'GET', S + '/news?status=all').get_json()
    assert 'status' not in plat.calls('/api/bridge/news')[-1]['params'] and len(d['items']) == 2 and d['items'][1]['source_url'] == ''
    _call(ctx, 'GET', S + '/news?status=%3Bdrop')
    assert plat.calls('/api/bridge/news')[-1]['params'] == {'status': 'draft'}


def test_news_approve_sends_the_status_only_and_is_audited_by_name(ctx, plat):
    r = _call(ctx, 'PUT', S + '/news/n-1', {'status': 'published', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['status'] == 'published' and 'secret_field' not in r.get_json()
    assert plat.writes()[0]['json'] == {'status': 'published', 'by': ADMIN_EMAIL}
    a = _audits('saha.news_approve')[-1]
    assert a[1] == 'n-1' and a[2] == {'fields': ['status']}
    _call(ctx, 'PUT', S + '/news/n-1', {'status': 'draft', 'confirmed': True})
    assert _audits('saha.news_unpublish')[-1][1] == 'n-1'
    _call(ctx, 'PUT', S + '/news/n-1', {'category': 'أخرى', 'featured': True, 'cover_url': 'https://c.test/a.png', 'confirmed': True})
    assert _audits('saha.news_edit')[-1][2] == {'fields': ['category', 'cover_url', 'featured']}


@pytest.mark.parametrize('body', [{}, {'status': 'archived'}, {'category': 'سياسة'}, {'cover_url': 'http://c.test/a.png'}, {'cover_url': BAD_JS},
                                  {'featured': 'yes'}, {'related_product': {'kind': 'film', 'slug': 'x'}}, {'related_product': 'x'}, {'title': ''}, {'title': 'x' * 301}])
def test_news_edit_is_validated_before_any_call(ctx, plat, body):
    r = _call(ctx, 'PUT', S + '/news/n-1', dict(body, confirmed=True))
    assert r.status_code == 422 and r.get_json()['error'], body
    assert plat.writes() == []


def test_news_cover_and_related_product_can_be_cleared(ctx, plat):
    r = _call(ctx, 'PUT', S + '/news/n-1', {'cover_url': '', 'related_product': None, 'confirmed': True})
    assert r.status_code == 200
    assert plat.writes()[0]['json'] == {'cover_url': '', 'related_product': None, 'by': ADMIN_EMAIL}


def test_news_run_sends_only_the_known_options(ctx, plat):
    r = _call(ctx, 'POST', S + '/news/run', {'per_country_limit': 2, 'countries': ['eg', 'SA', 'eg'], 'derive_topics': False, 'x': 1, 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['total_created'] == 2 and r.get_json()['per_country'] == [{'country': 'EG', 'fetched': 9, 'created': 2, 'errors': 0,
                                                                                                  'held_for_review': 1, 'skipped_not_legal': 4}]
    assert plat.writes()[0]['json'] == {'per_country_limit': 2, 'countries': ['EG', 'SA'], 'derive_topics': False, 'by': ADMIN_EMAIL}
    assert plat.writes()[0]['timeout'] >= 100
    assert _audits('saha.news_run')[-1][2] == {'total_created': 2, 'countries': 1, 'held_for_review': 1}
    for bad in ({'per_country_limit': 0}, {'per_country_limit': 9}, {'per_country_limit': '3'}, {'countries': ['EGY']}, {'countries': 'EG'}, {'derive_topics': 'no'}):
        n = len(plat.writes())
        assert _call(ctx, 'POST', S + '/news/run', dict(bad, confirmed=True)).status_code == 422, bad
        assert len(plat.writes()) == n


# ---------------------------------------------------------------- ٣) النقاشات والآراء

def test_topics_and_opinions_are_whitelisted_and_filtered(ctx, plat):
    t = _call(ctx, 'GET', S + '/topics').get_json()
    assert plat.calls('/api/bridge/topics')[0]['params'] == {'status': 'open'}
    assert t['items'][0] == {'id': 'tp-1', 'title': 'نقاش', 'status': 'open', 'source': 'human', 'opinions_count': 2, 'expert_opinions_count': 1, 'created_at': 'x',
                             'legal': None}
    o = _call(ctx, 'GET', S + '/opinions?topic_id=tp-1&status=all').get_json()
    assert plat.calls('/api/bridge/opinions')[0]['params'] == {'status': 'all', 'topic_id': 'tp-1'}
    assert len(o['items']) == 1 and 'ai_moderation' not in o['items'][0] and o['items'][0]['side'] == 'a'
    assert _call(ctx, 'GET', S + '/opinions?topic_id=a%20b').status_code == 400
    _call(ctx, 'GET', S + '/opinions')
    assert plat.calls('/api/bridge/opinions')[-1]['params'] == {'status': 'pending'}


def test_hide_is_a_reject_on_the_platform_and_restore_an_approve(ctx, plat):
    r = _call(ctx, 'POST', S + '/opinions/op-1/hide', dict(C))
    assert r.status_code == 200 and r.get_json()['status'] == 'rejected'
    assert plat.writes()[0]['path'] == '/api/bridge/opinions/op-1/reject' and plat.writes()[0]['json'] == {'by': ADMIN_EMAIL}
    assert _audits('saha.opinion_hide')[-1][1] == 'op-1'
    _call(ctx, 'POST', S + '/opinions/op-1/restore', dict(C))
    assert plat.writes()[-1]['path'] == '/api/bridge/opinions/op-1/approve' and _audits('saha.opinion_restore')[-1][1] == 'op-1'


def test_topic_hide_and_restore_are_human_stamps_on_the_platform(ctx, plat):
    r = _call(ctx, 'POST', S + '/topics/tp-1/hide', dict(C))
    assert r.status_code == 200 and r.get_json()['legal'] == {'ok': False, 'by': 'human', 'reason': 'human:hide'}
    assert 'author_email' not in r.get_json() and 'ai_answer' not in r.get_json()
    assert plat.writes()[0]['path'] == '/api/bridge/topics/tp-1/hide' and plat.writes()[0]['json'] == {'by': ADMIN_EMAIL}
    assert _audits('saha.topic_hide')[-1][1:3] == ('tp-1', {'hidden': True})
    r = _call(ctx, 'POST', S + '/topics/tp-1/restore', dict(C))
    assert r.get_json()['legal']['ok'] is True and _audits('saha.topic_restore')[-1][2] == {'hidden': False}
    assert _call(ctx, 'POST', S + '/topics/nope/hide', dict(C)).status_code == 404
    assert _call(ctx, 'POST', S + '/topics/a%20b/hide', dict(C)).status_code == 400
    t = _call(ctx, 'GET', S + '/topics').get_json()['items'][0]
    assert t['legal'] == {'ok': True, 'by': 'human', 'reason': 'human:restore'}       # بلا الثيمات ولا أي حقل زيادة


def test_legal_gate_check_is_a_dry_run_without_confirmation_or_audit(ctx, plat):
    r = _call(ctx, 'POST', S + '/legal-gate/check', {})
    assert r.status_code == 200
    d = r.get_json()
    assert d['dry_run'] is True and d['applied'] is False
    assert plat.ef.backfills == [{'apply': False}]                                     # ولا `by` ولا تأكيد ولا archive
    news = d['collections']['news']
    assert news['would_hide'] == 1 and news['hidden'] == [{'id': 'n-9', 'title': 'خبر رياضي', 'reason': 'off-theme', 'status': 'published'}]
    assert 'leak' not in news and d['collections']['articles']['scanned'] == 0 and 'users' not in d['collections']
    assert d['collections']['topics']['stamped'] == 0
    assert _audits('saha.legal_gate_check') == []


def test_legal_gate_apply_needs_confirmation_and_never_archives(ctx, plat):
    assert _call(ctx, 'POST', S + '/legal-gate/apply', {'ids': ['n-9']}).status_code == 400 and plat.ef.backfills == []
    r = _call(ctx, 'POST', S + '/legal-gate/apply', {'confirmed': True, 'archive': True, 'apply': False, 'ids': ['n-9', 'n-9']})
    assert r.status_code == 200 and r.get_json()['applied'] is True
    # الجسم قايمة بيضا: لا archive، والمختار بس (بلا تكرار)
    assert plat.ef.backfills == [{'apply': True, 'ids': ['n-9'], 'by': ADMIN_EMAIL}]
    assert _audits('saha.legal_gate_apply')[-1][2] == {'news': 1, 'topics': 0, 'articles': 0, 'picked': 1}


def test_legal_gate_apply_hides_only_what_was_ticked(ctx, plat):
    for bad in ({'confirmed': True}, {'confirmed': True, 'ids': []}, {'confirmed': True, 'ids': 'n-9'},
                {'confirmed': True, 'ids': ['a b']}, {'confirmed': True, 'ids': [1]}, {'confirmed': True, 'ids': ['x'] * 901}):
        r = _call(ctx, 'POST', S + '/legal-gate/apply', bad)
        assert r.status_code == 400, bad
    assert plat.ef.backfills == []
    assert 'اختر' in _call(ctx, 'POST', S + '/legal-gate/apply', {'confirmed': True}).get_json()['error']


def test_hidden_topics_list_covers_every_status(ctx, plat):
    plat.ef.topics.append({'id': 'tp-h', 'title': 'نقاش منشور مخفي', 'status': 'published', 'source': 'news', 'created_at': 'y',
                           'legal_gate': {'ok': False, 'by': 'rule', 'reason': 'off-theme'}})
    t = _call(ctx, 'GET', S + '/topics?status=all&hidden=1').get_json()
    assert plat.calls('/api/bridge/topics')[-1]['params'] in (None, {})
    assert [x['id'] for x in t['items']] == ['tp-h'] and t['hidden_only'] is True and t['total'] == 1


def test_news_run_reports_the_items_held_for_review(ctx, plat):
    r = _call(ctx, 'POST', S + '/news/run', dict(C)).get_json()
    assert r['total_held_for_review'] == 1 and 'x' not in r['per_country'][0]
    assert r['per_country'][0]['held_for_review'] == 1 and r['per_country'][0]['skipped_not_legal'] == 4


# ---------------------------------------------------------------- ٤) الفرص

def test_opportunity_queue_forwards_review_status_and_kind_and_whitelists(ctx, plat):
    d = _call(ctx, 'GET', S + '/opportunities').get_json()
    assert plat.calls('/api/bridge/jobs')[0]['params'] == {'review_status': 'pending'}
    row = d['items'][0]
    assert 'poster_email' not in row and 'internal_flag' not in row and row['official_url'] == 'https://x.org/1' and row['eligibility_ar'] == ['خريج قانون']
    d = _call(ctx, 'GET', S + '/opportunities?review_status=all&kind=grants&featured=true').get_json()
    assert plat.calls('/api/bridge/jobs')[-1]['params'] == {'kind': 'grants', 'featured': 'true'}
    assert [i['id'] for i in d['items']] == ['job-1']
    d = _call(ctx, 'GET', S + '/opportunities?review_status=published&kind=job').get_json()
    assert d['items'][0]['image'] == ''                                       # صورة javascript: اتشالت
    _call(ctx, 'GET', S + '/opportunities?review_status=%3B&kind=zzz&featured=maybe')
    assert plat.calls('/api/bridge/jobs')[-1]['params'] == {'review_status': 'pending'}


def test_one_opportunity_distinguishes_missing_item_from_missing_bridge(ctx, plat):
    assert _call(ctx, 'GET', S + '/opportunities/job-1').get_json()['id'] == 'job-1'
    r = _call(ctx, 'GET', S + '/opportunities/job-nope')
    assert r.status_code == 404 and 'bridge_missing' not in r.get_json() and r.get_json()['error'] == 'Job not found'
    plat.ef.missing.add('/api/bridge/jobs')
    r = _call(ctx, 'GET', S + '/opportunities')
    assert r.status_code == 404 and r.get_json()['bridge_missing'] is True
    plat.ef.down.add('/api/bridge/news')
    assert _call(ctx, 'GET', S + '/news').status_code == 503


def test_create_sends_every_known_field_and_nothing_else(ctx, plat):
    body = {'kind': 'fellowship', 'publish': True, 'title': ' زمالة ', 'provider': 'الجهة', 'country': 'gb', 'language': 'en', 'funding': 'partial',
            'eligibility_ar': ['  أول  ', '', 'ثان'], 'covers_ar': 'رسوم وسكن', 'deadline': '2026-12-08', 'deadline_text': 'يناير عادةً',
            'official_url': 'https://f.org/a', 'source_name': 'f.org', 'image': 'https://f.org/i.png', 'featured': True, 'verified_at': '2026-10-30',
            'title_en': 'Fellowship', 'poster_email': 'x@evil.test', 'review_status': 'published', 'seed_id': 's', 'confirmed': True}
    r = _call(ctx, 'POST', S + '/opportunities', body)
    assert r.status_code == 200 and r.get_json()['review_status'] == 'published'
    sent = plat.writes()[0]['json']
    assert sent == {'kind': 'fellowship', 'publish': True, 'title': 'زمالة', 'provider': 'الجهة', 'country': 'GB', 'language': 'en', 'funding': 'partial',
                    'eligibility_ar': ['أول', 'ثان'], 'covers_ar': 'رسوم وسكن', 'deadline': '2026-12-08', 'deadline_text': 'يناير عادةً',
                    'official_url': 'https://f.org/a', 'source_name': 'f.org', 'image': 'https://f.org/i.png', 'featured': True,
                    'verified_at': '2026-10-30', 'title_en': 'Fellowship', 'by': ADMIN_EMAIL}
    a = _audits('saha.opportunity_create')[-1]
    assert a[2] == {'kind': 'fellowship', 'publish': True} and a[1].startswith('job-')


@pytest.mark.parametrize('patch,why', [
    ({'kind': None}, 'النوع صريح'), ({'kind': 'film'}, 'نوع غريب'), ({'publish': None}, 'النشر صريح'), ({'publish': 'true'}, 'النشر منطقي'),
    ({'title': 'ab'}, 'عنوان قصير'), ({'official_url': 'http://x.org/a'}, 'http مرفوض'), ({'official_url': BAD_JS}, 'javascript'),
    ({'official_url': 'https://x.org/a b'}, 'مسافة'), ({'official_url': ''}, 'رابط ناقص'), ({'image': 'http://x.org/i.png'}, 'صورة http'),
    ({'image': 'data:image/png;base64,AAAA'}, 'صورة data'), ({'language': 'de'}, 'لغة'), ({'funding': 'free'}, 'تمويل'),
    ({'eligibility_ar': ['س'] * 9}, 'تسعة أسطر'), ({'eligibility_ar': ['س' * 161]}, 'سطر طويل'), ({'eligibility_ar': 'نص'}, 'ليست قائمة'),
    ({'covers_ar': 'س' * 301}, 'يغطي طويل'), ({'deadline': '2026-02-30'}, 'تاريخ غير موجود'), ({'deadline': '12/08/2026'}, 'صيغة'),
    ({'deadline_text': 'س' * 81}, 'نص الموعد'), ({'source_name': 'س' * 81}, 'اسم المصدر'), ({'country': 'مصر'}, 'بلد بالاسم'), ({'country': 'EGY'}, 'ثلاثة'),
    ({'featured': 1}, 'منطقي'), ({'expires_in_days': 0}, 'مدة'),
])
def test_create_is_validated_before_any_call(ctx, plat, patch, why):
    body = dict(OPP_NEW)
    body.update(patch)
    for k in [k for k, v in patch.items() if v is None]:
        body.pop(k)
    r = _call(ctx, 'POST', S + '/opportunities', body)
    assert r.status_code == 422 and r.get_json()['error'], why
    assert plat.writes() == []


def test_country_accepts_online_various_and_empty(ctx, plat):
    for c, want in (('online', 'online'), ('VARIOUS', 'various'), ('', ''), ('eg', 'EG')):
        assert _call(ctx, 'PUT', S + '/opportunities/job-1', {'country': c, 'confirmed': True}).status_code == 200
        assert plat.writes()[-1]['json']['country'] == want


def test_update_sends_only_given_fields_clears_with_empty_and_ignores_nulls(ctx, plat):
    r = _call(ctx, 'PUT', S + '/opportunities/job-1', {'deadline': '', 'image': '', 'eligibility_ar': [], 'featured': None, 'title': None, 'publish': True, 'confirmed': True})
    assert r.status_code == 200
    assert plat.writes()[0]['json'] == {'publish': True, 'deadline': '', 'image': '', 'eligibility_ar': [], 'by': ADMIN_EMAIL}
    assert _audits('saha.opportunity_publish')[-1][1] == 'job-1'
    _call(ctx, 'PUT', S + '/opportunities/job-1', {'publish': False, 'confirmed': True})
    assert _audits('saha.opportunity_unpublish')[-1][1] == 'job-1'
    _call(ctx, 'PUT', S + '/opportunities/job-1', {'featured': True, 'image': 'https://i.test/a.png', 'confirmed': True})
    assert _audits('saha.opportunity_edit')[-1][2] == {'fields': ['featured', 'image']}
    n = len(plat.writes())
    r = _call(ctx, 'PUT', S + '/opportunities/job-1', {'title': None, 'confirmed': True})
    assert r.status_code == 422 and len(plat.writes()) == n


def test_decide_sends_a_reason_only_with_a_rejection(ctx, plat):
    assert _call(ctx, 'POST', S + '/opportunities/job-1/decide', {'decision': 'approve', 'reason': 'x', 'confirmed': True}).status_code == 200
    assert plat.writes()[-1]['json'] == {'decision': 'approve', 'by': ADMIN_EMAIL}
    assert _call(ctx, 'POST', S + '/opportunities/job-1/decide', {'decision': 'reject', 'reason': ' ناقصة ', 'confirmed': True}).status_code == 200
    assert plat.writes()[-1]['json'] == {'decision': 'reject', 'reason': 'ناقصة', 'by': ADMIN_EMAIL}
    assert _audits('saha.opportunity_reject')[-1][2] == {'decision': 'reject', 'has_reason': True}
    n = len(plat.writes())
    for bad in ({'decision': 'maybe'}, {}, {'decision': 'reject', 'reason': 'س' * 141}):
        assert _call(ctx, 'POST', S + '/opportunities/job-1/decide', dict(bad, confirmed=True)).status_code == 422
    assert len(plat.writes()) == n


def test_platform_texts_pass_through_with_their_codes_and_only_success_is_audited(ctx, plat):
    n0 = len(_audits('saha.'))
    r = _call(ctx, 'POST', S + '/opportunities/job-nope/decide', {'decision': 'approve', 'confirmed': True})
    assert r.status_code == 404 and r.get_json()['error'] == 'Job not found'
    r = _call(ctx, 'DELETE', S + '/opportunities/job-3', dict(C))
    assert r.status_code == 409 and 'تُقفل' in r.get_json()['error']
    plat.ef.jobs[0]['official_url'] = ''
    r = _call(ctx, 'POST', S + '/opportunities/job-1/decide', {'decision': 'approve', 'confirmed': True})
    assert r.status_code == 422 and 'أكمل عنوان' in r.get_json()['error']
    assert _call(ctx, 'PUT', D + '/works/CR_1', {'status': 'hidden', 'confirmed': True}).status_code == 409
    assert len(_audits('saha.')) == n0 and _audits('diwan.work_hide') == []


def test_delete_goes_to_the_platform_with_by_and_is_audited(ctx, plat):
    r = _call(ctx, 'DELETE', S + '/opportunities/job-1', dict(C))
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'deleted': 'job-1'}
    assert plat.writes()[0]['method'] == 'DELETE' and plat.writes()[0]['json'] == {'by': ADMIN_EMAIL}
    assert _audits('saha.opportunity_delete')[-1][1] == 'job-1'


def test_ids_with_unsafe_characters_never_reach_the_platform(ctx, plat):
    for path in (S + '/opportunities/a%20b/decide', S + '/news/a%23b', S + '/opinions/a%3Fb/hide', D + '/works/a%25b'):
        assert _call(ctx, 'POST' if 'decide' in path or 'hide' in path else 'PUT', path, {'decision': 'approve', 'featured': True, 'title': 'xxx', 'confirmed': True}).status_code in (400, 404), path
    assert plat.writes() == []


# ---------------------------------------------------------------- ٥) الإعداد · رابط دورة التحضير

def test_prep_course_url_is_https_only_and_empty_clears(ctx, plat):
    assert _call(ctx, 'GET', S + '/settings').get_json() == {'prep_course_url': 'https://courses.test/prep', 'updated_at': 'x'}
    for bad in ('http://c.test/p', BAD_JS, 'ftp://c.test', 'https://c.test/a b', 'x' * 2100, 5):
        assert _call(ctx, 'PUT', S + '/settings', {'prep_course_url': bad, 'confirmed': True}).status_code == 422, bad
    assert _call(ctx, 'PUT', S + '/settings', {'confirmed': True}).status_code == 422
    assert plat.writes() == []
    r = _call(ctx, 'PUT', S + '/settings', {'prep_course_url': ' https://c.test/p ', 'confirmed': True})
    assert r.status_code == 200 and plat.writes()[0]['json'] == {'prep_course_url': 'https://c.test/p', 'by': ADMIN_EMAIL}
    assert _audits('saha.opportunity_settings')[-1][2] == {'cleared': False}
    r = _call(ctx, 'PUT', S + '/settings', {'prep_course_url': '', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['prep_course_url'] == '' and _audits('saha.opportunity_settings')[-1][2] == {'cleared': True}


# ---------------------------------------------------------------- ٦) الاستيراد: تجربة ثم تأكيد

def test_seed_preview_is_a_dry_run_with_no_confirmation_no_by_and_no_audit(ctx, plat):
    n0 = len(_audits('saha.seed'))
    r = _call(ctx, 'POST', S + '/opportunities/seed/preview', {})
    assert r.status_code == 200
    assert r.get_json() == {'created': 34, 'filled': 1, 'skipped_unverified': 4, 'unchanged': 2, 'warnings': ['id: تحذير'], 'dry_run': True}
    c = plat.calls('/api/bridge/opportunities/import-seed')
    assert len(c) == 1 and c[0]['params'] == {'dry_run': 'true'} and c[0]['json'] is None
    assert len(_audits('saha.seed')) == n0


def test_seed_import_needs_confirmation_then_runs_for_real_without_dry_run(ctx, plat):
    assert _call(ctx, 'POST', S + '/opportunities/seed/import', {}).status_code == 400
    assert plat.seen == []
    r = _call(ctx, 'POST', S + '/opportunities/seed/import', dict(C))
    assert r.status_code == 200 and r.get_json()['dry_run'] is False and r.get_json()['created'] == 34
    c = plat.calls('/api/bridge/opportunities/import-seed')
    assert len(c) == 1 and c[0]['params'] == {} and c[0]['json'] is None
    a = _audits('saha.seed_import')[-1]
    assert a[2] == {'created': 34, 'filled': 1, 'skipped_unverified': 4, 'unchanged': 2, 'warnings': 1, 'own_file': False} and a[3] == ADMIN_EMAIL


def test_an_uploaded_seed_passes_through_unchanged_after_a_shape_check(ctx, plat):
    seed = {'meta': {'v': 1}, 'items': [{'id': 'a', 'type': 'grant', 'verified': True, 'title_ar': 'منحة'}], 'notes': ['x']}
    assert _call(ctx, 'POST', S + '/opportunities/seed/preview', {'seed': seed}).status_code == 200
    assert plat.calls('/api/bridge/opportunities/import-seed')[0]['json'] == seed          # بلا `by` ولا `confirmed`
    assert _call(ctx, 'POST', S + '/opportunities/seed/import', {'seed': seed, 'confirmed': True}).status_code == 200
    assert plat.calls('/api/bridge/opportunities/import-seed')[1]['json'] == seed and _audits('saha.seed_import')[-1][2]['own_file'] is True


@pytest.mark.parametrize('seed', [[], 'x', {}, {'items': 'x'}, {'items': [1]}, {'items': [{}] * 501}, {'items': [{'t': 'س' * 3000000}]}])
def test_a_bad_seed_shape_is_refused_before_any_call(ctx, plat, seed):
    for path, extra in ((S + '/opportunities/seed/preview', {}), (S + '/opportunities/seed/import', dict(C))):
        r = _call(ctx, 'POST', path, dict(extra, seed=seed))
        assert r.status_code == 422 and r.get_json()['error'], (path, seed if not isinstance(seed, dict) else '')
    assert plat.seen == []


def test_seed_replies_drop_unknown_fields_and_cap_warnings(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/opportunities/import-seed')] = (200, {'created': 1, 'warnings': ['w'] * 300 + [5, {'x': 1}], 'zzz': 1})
    d = _call(ctx, 'POST', S + '/opportunities/seed/preview', {}).get_json()
    assert set(d) == {'created', 'filled', 'skipped_unverified', 'unchanged', 'warnings', 'dry_run'} and len(d['warnings']) == 200


# ---------------------------------------------------------------- ٧) الرد الضايع

LOST = [(('POST', '/api/bridge/news/run'), 'POST', S + '/news/run', dict(C), 'saha.news_run'),
        (('PUT', '/api/bridge/jobs/job-1'), 'PUT', S + '/opportunities/job-1', {'featured': True, 'confirmed': True}, 'saha.opportunity_edit'),
        (('POST', '/api/bridge/opportunities/import-seed'), 'POST', S + '/opportunities/seed/import', dict(C), 'saha.seed_import'),
        (('POST', '/api/bridge/diwan/challenges/CH_1/winners'), 'POST', D + '/challenges/CH_1/winners',
         {'winners': [{'place': 1, 'work_id': 'CR_2'}], 'confirmed': True}, 'diwan.challenge_winners'),
        (('POST', '/api/bridge/opportunities/run-reminders'), 'POST', S + '/reminders/run', dict(C), 'saha.reminders_run_now')]


@pytest.mark.parametrize('key,method,path,body,action', LOST)
@pytest.mark.parametrize('status', [500, 502, 503, 504])
def test_a_lost_reply_says_no_reply_and_is_audited_as_an_attempt_not_as_done(ctx, plat, key, method, path, body, action, status):
    plat.ef.forced[key] = (status, {'detail': 'x'})
    n0 = len(_audits(action))
    r = _call(ctx, method, path, body)
    assert r.status_code == 502 and r.get_json() == {'error': NO_REPLY_AR, 'no_reply': True}
    assert len(_audits(action)) == n0
    area = action.split('.')[0]
    assert _audits(area + '.no_reply')[-1][2] == {'attempt': action}
    assert len(plat.writes()) == 1, 'بلا إعادة محاولة'


def test_a_platform_4xx_is_not_a_lost_reply(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/news/run')] = (409, {'detail': 'شغّال بالفعل'})
    r = _call(ctx, 'POST', S + '/news/run', dict(C))
    assert r.status_code == 409 and r.get_json() == {'error': 'شغّال بالفعل'}


def test_the_platform_refusing_the_shared_secret_is_masked_as_a_bridge_failure(ctx, plat):
    plat.ef.forced[('GET', '/api/bridge/news')] = (401, {'detail': 'x'})
    r = _call(ctx, 'GET', S + '/news')
    assert r.status_code == 502, 'لا ٤٠١ يخرّج الأدمن إلى شاشة الدخول'


# ---------------------------------------------------------------- ٨) التذكير الدوري

CRON = S + '/reminders/cron'
SEC = {'X-ELP-Metrics-Secret': SECRET}


def test_cron_is_guarded_by_the_shared_secret_before_anything(ctx, plat):
    assert _call(ctx, 'POST', CRON, {}, role=None).status_code == 401
    assert _call(ctx, 'POST', CRON, {}, role=None, headers={'X-ELP-Metrics-Secret': 'wrong'}).status_code == 401
    assert _call(ctx, 'POST', CRON, {}, role=None, headers={'X-ELP-Metrics-Secret': 'سر-غير-لاتيني'}).status_code == 401
    assert _call(ctx, 'POST', CRON, {}, role='admin').status_code == 401, 'توكن الأدمن لا يكفي'
    assert plat.seen == []


def test_cron_needs_no_confirmation_and_calls_the_bridge_once_with_by_cron(ctx, plat):
    plat.ef.reminders_enabled = True
    r = _call(ctx, 'POST', CRON, None, role=None, headers=SEC)
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    d = r.get_json()
    assert d['enabled'] is True and d['locked'] is False and d['sent'] == 5 and d['ok'] is True
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/opportunities/run-reminders' and w[0]['json'] == {'by': 'cron'}
    a = _audits('saha.reminders_cron')[-1]
    assert a[2] == {'opportunities': 2, 'sent': 5, 'skipped_already': 1, 'skipped_toggle_off': 0, 'errors': 0} and a[3] == 'cron'


def test_cron_while_the_platform_flag_is_off_is_inert_and_the_tile_says_locked(ctx, plat):
    n0 = len(_audits('saha.reminders'))
    st = _call(ctx, 'GET', S + '/reminders').get_json()
    assert st == {'last': None, 'enabled': None, 'locked': False}, 'قبل أول تشغيل: لا نعرف'
    assert plat.seen == [], 'قراءة الحالة لا تنادي المنصة (النداء نفسه يرسل)'
    r = _call(ctx, 'POST', CRON, None, role=None, headers=SEC)
    assert r.status_code == 200
    d = r.get_json()
    assert d['enabled'] is False and d['locked'] is True and d['sent'] == 0 and d['opportunities'] == 0 and d['errors'] == 0
    st = _call(ctx, 'GET', S + '/reminders').get_json()
    assert st['enabled'] is False and st['locked'] is True and st['last']['ok'] is True and st['last']['trigger'] == 'cron' and st['last']['at'].endswith('Z')
    assert len(_audits('saha.reminders')) == n0, 'ساعة بلا إرسال لا تكتب تدقيقًا'
    assert len(plat.writes()) == 1


def test_cron_audits_errors_even_when_nothing_was_sent(ctx, plat):
    plat.ef.reminders_enabled = True
    plat.ef.reminder_stats = {'opportunities': 1, 'sent': 0, 'skipped_already': 0, 'skipped_toggle_off': 0, 'errors': 2}
    n0 = len(_audits('saha.reminders_cron'))
    _call(ctx, 'POST', CRON, None, role=None, headers=SEC)
    assert len(_audits('saha.reminders_cron')) == n0 + 1
    plat.ef.reminder_stats = {'opportunities': 1, 'sent': 0, 'skipped_already': 3, 'skipped_toggle_off': 0, 'errors': 0}
    _call(ctx, 'POST', CRON, None, role=None, headers=SEC)
    assert len(_audits('saha.reminders_cron')) == n0 + 1


def test_cron_failure_is_a_visible_error_and_status_remembers_it(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/opportunities/run-reminders')] = (504, {'detail': 'x'})
    r = _call(ctx, 'POST', CRON, None, role=None, headers=SEC)
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    st = _call(ctx, 'GET', S + '/reminders').get_json()
    assert st['last']['ok'] is False and st['last']['no_reply'] is True and st['enabled'] is None and st['locked'] is False
    plat.ef.forced[('POST', '/api/bridge/opportunities/run-reminders')] = (404, {'detail': 'Not Found'})
    assert _call(ctx, 'POST', CRON, None, role=None, headers=SEC).status_code == 404
    # رفض المنصة ليس ضياع رد: الشاشة تفرّق بينهما في نص الفشل
    st = _call(ctx, 'GET', S + '/reminders').get_json()
    assert st['last']['ok'] is False and st['last']['no_reply'] is False
    assert len(plat.writes()) == 2


def test_run_now_shows_enabled_false_when_the_platform_has_reminders_off(ctx, plat):
    r = _call(ctx, 'POST', S + '/reminders/run', dict(C))
    assert r.status_code == 200 and r.get_json()['enabled'] is False and r.get_json()['locked'] is True
    assert plat.writes()[0]['json'] == {'by': ADMIN_EMAIL}
    assert _audits('saha.reminders_run_now')[-1][2]['enabled'] is False
    assert _call(ctx, 'GET', S + '/reminders').get_json()['last']['trigger'] == 'manual'
    plat.ef.reminders_enabled = True
    d = _call(ctx, 'POST', S + '/reminders/run', dict(C)).get_json()
    assert d['enabled'] is True and d['locked'] is False and d['sent'] == 5
    assert _call(ctx, 'GET', S + '/reminders').get_json()['locked'] is False


def test_a_reply_without_the_enabled_flag_counts_as_locked_never_as_sending(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/opportunities/run-reminders')] = (200, {'sent': 9})
    d = _call(ctx, 'POST', CRON, None, role=None, headers=SEC).get_json()
    assert d['enabled'] is False and d['locked'] is True


# ---------------------------------------------------------------- ٩) الديوان · الأعمال

def test_works_list_filters_by_status_and_challenge_and_whitelists(ctx, plat):
    d = _call(ctx, 'GET', D + '/works').get_json()
    assert plat.calls('/api/bridge/creative')[0]['params'] == {'status': 'pending_review'}
    w = d['items'][0]
    assert 'internal' not in w and w['media'] == {'provider': 'youtube', 'video_id': 'abc'} and w['media_url'] == '' and w['cover_url'] == 'https://i.test/c.png'
    assert w['creator_email'] == 'w@x.test'
    _call(ctx, 'GET', D + '/works?status=hidden&challenge_id=CH_1')
    assert plat.calls('/api/bridge/creative')[-1]['params'] == {'status': 'hidden', 'challenge_id': 'CH_1'}
    _call(ctx, 'GET', D + '/works?status=zzz')
    assert plat.calls('/api/bridge/creative')[-1]['params'] == {'status': 'pending_review'}
    assert _call(ctx, 'GET', D + '/works?challenge_id=a%20b').status_code == 400


def test_work_decision_sends_reason_and_note_only_with_a_rejection(ctx, plat):
    assert _call(ctx, 'POST', D + '/works/CR_1/decide', {'decision': 'approve', 'reason': 'x', 'note': 'y', 'confirmed': True}).status_code == 200
    assert plat.writes()[-1]['json'] == {'decision': 'approve', 'by': ADMIN_EMAIL}
    r = _call(ctx, 'POST', D + '/works/CR_1/decide', {'decision': 'reject', 'reason': 'غير مناسب', 'note': 'ملاحظة', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['status'] == 'rejected'
    assert plat.writes()[-1]['json'] == {'decision': 'reject', 'reason': 'غير مناسب', 'note': 'ملاحظة', 'by': ADMIN_EMAIL}
    assert _audits('diwan.work_reject')[-1][2] == {'decision': 'reject', 'has_reason': True}
    for bad in ({'decision': 'x'}, {'decision': 'reject', 'reason': 'س' * 141}, {'decision': 'reject', 'note': 'س' * 1001}):
        n = len(plat.writes())
        assert _call(ctx, 'POST', D + '/works/CR_1/decide', dict(bad, confirmed=True)).status_code == 422
        assert len(plat.writes()) == n


@pytest.mark.parametrize('patch,action', [({'featured': True}, 'diwan.work_feature'), ({'featured': False}, 'diwan.work_unfeature'),
                                          ({'featured_until': '2026-12-01'}, 'diwan.work_feature'), ({'featured_until': ''}, 'diwan.work_unfeature'),
                                          ({'status': 'hidden'}, 'diwan.work_hide'), ({'status': 'published'}, 'diwan.work_show'),
                                          ({'comments_locked': True}, 'diwan.work_comments_lock'), ({'comments_locked': False}, 'diwan.work_comments_unlock')])
def test_work_control_is_audited_by_what_it_did(ctx, plat, patch, action):
    plat.ef.works[1]['status'] = 'published'
    r = _call(ctx, 'PUT', D + '/works/CR_2', dict(patch, confirmed=True, creator_email='x@evil.test'))
    assert r.status_code == 200, r.get_json()
    assert plat.writes()[0]['json'] == dict(patch, by=ADMIN_EMAIL)
    assert _audits(action)[-1][1] == 'CR_2'


@pytest.mark.parametrize('patch', [{}, {'status': 'rejected'}, {'featured': 'yes'}, {'comments_locked': 1}, {'featured_until': 'غدًا'}, {'featured_until': '2026-13-01'}])
def test_work_control_is_validated_before_any_call(ctx, plat, patch):
    assert _call(ctx, 'PUT', D + '/works/CR_2', dict(patch, confirmed=True)).status_code == 422
    assert plat.writes() == []


def test_staff_upload_needs_the_ai_disclosure_and_sends_known_fields_only(ctx, plat):
    body = {'title': ' فيلم قصير ', 'kind': 'film', 'ai_assisted': True, 'creator_name': 'الفريق', 'media_url': 'https://youtu.be/abc', 'about': 'كلمة',
            'cover_url': 'https://i.test/c.png', 'duration_minutes': 6, 'featured': True, 'featured_until': '2026-12-01T00:00:00Z', 'status': 'hidden',
            'creator_email': 'x@evil.test', 'confirmed': True}
    r = _call(ctx, 'POST', D + '/works', body)
    assert r.status_code == 200 and r.get_json()['id'] == 'CR_9'
    assert plat.writes()[0]['json'] == {'title': 'فيلم قصير', 'kind': 'film', 'ai_assisted': True, 'creator_name': 'الفريق', 'media_url': 'https://youtu.be/abc',
                                        'about': 'كلمة', 'cover_url': 'https://i.test/c.png', 'duration_minutes': 6, 'featured': True,
                                        'featured_until': '2026-12-01T00:00:00Z', 'by': ADMIN_EMAIL}
    assert _audits('diwan.work_upload')[-1][2] == {'kind': 'film', 'featured': True}
    base = dict(WORK_UP)
    for patch in ({'ai_assisted': None}, {'ai_assisted': 'no'}, {'kind': 'song'}, {'kind': None}, {'title': ''}, {'cover_url': 'http://i.test/c.png'},
                  {'media_url': BAD_JS}, {'duration_minutes': 0}, {'duration_minutes': 601}, {'about': 'س' * 601}, {'body': 'س' * 20001}):
        b = dict(base)
        b.update(patch)
        for k in [k for k, v in patch.items() if v is None]:
            b.pop(k)
        n = len(plat.writes())
        assert _call(ctx, 'POST', D + '/works', b).status_code == 422, patch
        assert len(plat.writes()) == n


# ---------------------------------------------------------------- ١٠) الديوان · التعليقات والتحديات والتقرير

def test_comments_list_and_hide(ctx, plat):
    d = _call(ctx, 'GET', D + '/comments?work_id=CR_2').get_json()
    assert plat.calls('/api/bridge/diwan/comments')[0]['params'] == {'status': 'visible', 'work_id': 'CR_2'}
    assert 'ip' not in d['items'][0] and d['items'][0]['user_email'] == 'u@x.test'
    r = _call(ctx, 'POST', D + '/comments/cm-1/hide', dict(C))
    assert r.status_code == 200 and r.get_json()['comment']['status'] == 'hidden' and 'ip' not in r.get_json()['comment']
    assert plat.writes()[0]['json'] == {'by': ADMIN_EMAIL} and _audits('diwan.comment_hide')[-1][1] == 'cm-1'
    assert _call(ctx, 'POST', D + '/comments/cm-nope/hide', dict(C)).status_code == 404


def test_challenge_create_sends_a_clean_whitelisted_body(ctx, plat):
    body = {'title': ' تحدّي القصة ', 'brief': 'اكتب', 'kind_allowed': ['story', 'poem', 'story'], 'word_cap': 500,
            'opens_at': '2026-12-01T00:00:00Z', 'closes_at': '2026-12-20', 'results_at': '2026-12-25T10:00:00+02:00', 'status': 'open',
            'prizes': [{'type': 'certificate', 'label': 'شهادة', 'ref': '', 'place': 1, 'x': 1}], 'jury': [{'name': 'أ', 'title': 'قاضٍ'}, {'name': 'ب'}, {'name': 'ج', 'title': ''}],
            'sponsor': {'name': 'راعٍ', 'logo_url': 'https://s.test/l.png'}, 'cover_url': 'https://s.test/c.png', 'created_by': 'x', 'confirmed': True}
    r = _call(ctx, 'POST', D + '/challenges', body)
    assert r.status_code == 200 and r.get_json()['id'] == 'CH_new' and 'created_by' not in r.get_json()
    assert plat.writes()[0]['json'] == {'title': 'تحدّي القصة', 'brief': 'اكتب', 'kind_allowed': ['story', 'poem'], 'word_cap': 500,
                                        'opens_at': '2026-12-01T00:00:00Z', 'closes_at': '2026-12-20', 'results_at': '2026-12-25T10:00:00+02:00', 'status': 'open',
                                        'prizes': [{'type': 'certificate', 'label': 'شهادة', 'ref': '', 'place': 1}],
                                        'jury': [{'name': 'أ', 'title': 'قاضٍ'}, {'name': 'ب', 'title': ''}, {'name': 'ج', 'title': ''}],
                                        'sponsor': {'name': 'راعٍ', 'logo_url': 'https://s.test/l.png'}, 'cover_url': 'https://s.test/c.png', 'by': ADMIN_EMAIL}
    assert _audits('diwan.challenge_create')[-1][2] == {'status': 'open'}


@pytest.mark.parametrize('patch,why', [
    ({'title': ''}, 'عنوان'), ({'title': 'س' * 121}, 'عنوان طويل'), ({'brief': 'س' * 601}, 'وصف طويل'), ({'kind_allowed': []}, 'بلا نوع'),
    ({'kind_allowed': ['video']}, 'نوع قديم'), ({'word_cap': 0}, 'سقف'), ({'word_cap': 'x'}, 'سقف نص'), ({'closes_at': '2026-11-30T00:00:00Z'}, 'إغلاق قبل البدء'),
    ({'closes_at': '2026-12-01T00:00:00Z'}, 'إغلاق = بدء'), ({'opens_at': 'غدًا'}, 'تاريخ'), ({'status': 'closed'}, 'حالة إنشاء'),
    ({'status': 'open', 'jury': [{'name': 'أ'}]}, 'فتح بلجنة ناقصة'), ({'jury': [{'name': 'أ'}] * 7}, 'سبعة محكّمين'), ({'jury': [{'name': ''}]}, 'محكّم بلا اسم'),
    ({'prizes': [{'type': 'cash'}]}, 'جائزة غريبة'), ({'prizes': [{'type': 'book', 'place': 4}]}, 'مركز'), ({'prizes': [{'type': 'book'}] * 7}, 'سبع جوائز'),
    ({'sponsor': {'name': 'ر', 'logo_url': 'http://s.test/l.png'}}, 'شعار http'), ({'sponsor': 'x'}, 'راعٍ'), ({'cover_url': BAD_JS}, 'غلاف'),
])
def test_challenge_is_validated_before_any_call(ctx, plat, patch, why):
    body = dict(CH_NEW)
    body.update(patch)
    assert _call(ctx, 'POST', D + '/challenges', body).status_code == 422, why
    assert plat.writes() == []


def test_challenge_update_sends_only_given_fields_and_can_clear_the_cap_and_sponsor(ctx, plat):
    r = _call(ctx, 'PUT', D + '/challenges/CH_1', {'word_cap': None, 'sponsor': None, 'status': 'closed', 'confirmed': True})
    assert r.status_code == 200
    assert plat.writes()[0]['json'] == {'word_cap': None, 'sponsor': None, 'status': 'closed', 'by': ADMIN_EMAIL}
    assert _audits('diwan.challenge_edit')[-1][2] == {'fields': ['sponsor', 'status', 'word_cap'], 'status': 'closed'}
    for bad in ({}, {'status': 'results'}, {'status': 'x'}):
        n = len(plat.writes())
        assert _call(ctx, 'PUT', D + '/challenges/CH_1', dict(bad, confirmed=True)).status_code == 422
        assert len(plat.writes()) == n
    r = _call(ctx, 'PUT', D + '/challenges/CH_res', {'title': 'جديد', 'confirmed': True})
    assert r.status_code == 409 and 'أُعلنت النتائج' in r.get_json()['error']


def test_challenges_list_filters_and_hides_internal_fields(ctx, plat):
    d = _call(ctx, 'GET', D + '/challenges?status=closed').get_json()
    assert plat.calls('/api/bridge/diwan/challenges')[0]['params'] == {'status': 'closed'}
    assert d['items'][0]['entries_count'] == 3 and 'created_by' not in d['items'][0]
    _call(ctx, 'GET', D + '/challenges')
    assert plat.calls('/api/bridge/diwan/challenges')[-1]['params'] == {}


def test_winners_are_checked_then_sent_sorted_and_the_certificates_come_back(ctx, plat):
    body = {'winners': [{'place': 2, 'work_id': 'CR_2', 'jury_line': ' جيد '}, {'place': 1, 'work_id': 'CR_1', 'x': 1}], 'confirmed': True}
    r = _call(ctx, 'POST', D + '/challenges/CH_1/winners', body)
    d = r.get_json()
    assert r.status_code == 200 and d['emails_sent'] == 3 and d['already'] is False and d['challenge']['status'] == 'results'
    assert d['certificates'] == [{'place': 1, 'work_id': 'CR_1', 'code': 'C1'}, {'place': 2, 'work_id': 'CR_2', 'code': 'C2'}]
    assert plat.writes()[0]['json'] == {'winners': [{'place': 1, 'work_id': 'CR_1', 'jury_line': ''}, {'place': 2, 'work_id': 'CR_2', 'jury_line': 'جيد'}], 'by': ADMIN_EMAIL}
    assert _audits('diwan.challenge_winners')[-1][2] == {'winners': 2, 'certificates': 2, 'emails_sent': 3, 'already': False}
    assert all(set(c) == {'place', 'work_id', 'code'} for c in d['certificates'])


@pytest.mark.parametrize('winners', [[], 'x', [{'place': 1, 'work_id': 'CR_1'}] * 2, [{'place': 1, 'work_id': 'a'}, {'place': 2, 'work_id': 'a'}],
                                      [{'place': i, 'work_id': 'w%d' % i} for i in (1, 2, 3, 4)], [{'place': 4, 'work_id': 'a'}], [{'place': 0, 'work_id': 'a'}],
                                      [{'place': 1, 'work_id': ''}], [{'place': 1, 'work_id': 'a b'}], [{'place': '1', 'work_id': 'a'}],
                                      [{'place': 1, 'work_id': 'a', 'jury_line': 'س' * 141}], ['x']])
def test_bad_winners_never_reach_the_platform(ctx, plat, winners):
    assert _call(ctx, 'POST', D + '/challenges/CH_1/winners', {'winners': winners, 'confirmed': True}).status_code == 422
    assert plat.writes() == []


def test_the_report_keeps_missing_numbers_null_and_real_zeros_zero(ctx, plat):
    d = _call(ctx, 'GET', D + '/report?days=7').get_json()
    assert plat.calls('/api/bridge/diwan/report')[0]['params'] == {'days': 7}
    assert d['visitors'] is None and d['signups'] is None and d['return_7d'] is None and d['legal_open_share'] is None
    assert d['share_card_clicks'] == 0 and d['works_acceptance'] == {'submitted': 4, 'accepted': 3, 'ratio': 0.75} and 'extra' not in d
    assert d['entries_per_challenge'] == [{'challenge_id': 'CH_1', 'slug': 'c1', 'title': 'تحدٍّ', 'entries': 3}]
    plat.ef.report = {'visitors': True, 'signups': 'x', 'works_acceptance': 'x', 'entries_per_challenge': 'x'}
    d = _call(ctx, 'GET', D + '/report').get_json()
    assert d['visitors'] is None and d['signups'] is None and d['works_acceptance'] is None and d['entries_per_challenge'] is None and d['window_days'] is None
    assert plat.calls('/api/bridge/diwan/report')[-1]['params'] == {'days': 30}
    for bad in ('0', '366', 'x', '-1'):
        _call(ctx, 'GET', D + '/report?days=' + bad)
        assert plat.calls('/api/bridge/diwan/report')[-1]['params'] == {'days': 30}


def test_the_report_bridge_missing_is_not_zero(ctx, plat):
    plat.ef.missing.add('/api/bridge/diwan/report')
    r = _call(ctx, 'GET', D + '/report')
    assert r.status_code == 404 and r.get_json()['bridge_missing'] is True


def test_validation_messages_use_arabic_indic_digits_and_no_dot_beside_a_digit(ctx, plat):
    import re
    cases = [(S + '/opportunities', dict(OPP_NEW, title='ab')), (S + '/opportunities', dict(OPP_NEW, covers_ar='س' * 301)),
             (S + '/opportunities', dict(OPP_NEW, eligibility_ar=['س'] * 9)), (S + '/opportunities', dict(OPP_NEW, expires_in_days=0)),
             (D + '/challenges', dict(CH_NEW, word_cap=0)), (D + '/challenges', dict(CH_NEW, title='س' * 121)), (S + '/news/run', {'per_country_limit': 99, 'confirmed': True})]
    for path, body in cases:
        msg = _call(ctx, 'POST', path, body).get_json()['error']
        assert not re.search(r'[0-9]', msg) and not re.search(r'[٠-٩]\s*·|·\s*[٠-٩]', msg) and re.search(r'[٠-٩]', msg), msg
    assert plat.writes() == []


# ---------------------------------------------------------------- ١١) لا ذكاء ولا ملفات ممنوعة

def test_no_model_call_and_no_forbidden_files_in_the_module():
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(os.path.dirname(here), 'v2_saha_routes.py'), encoding='utf-8').read()
    for word in ('anthropic', 'deepseek', 'openai', 'brain2', 'prerender', 'generate_chat_reply', 'requests.'):
        assert word not in src.replace('prerender.py` ولا', ''), word
