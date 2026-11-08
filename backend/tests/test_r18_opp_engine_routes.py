# -*- coding: utf-8 -*-
"""R18 — «محرّك الفرص» في الداشبورد (الساحة): مسارات `/api/v2/saha/engine/*` فوق جسور المنصة (عقد R18). المنصة بديل في الذاكرة.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r18_opp_engine_routes.py

⛔ صفر شبكة حقيقية وصفر نداء مدفوع: أي عنوان برّه `https://platform.test` يوقّع الاختبار، ولا بريد حقيقي (send-test هنا بديل).

اللي بيثبّته:
  ١. أدمن بس · المفتاح مقفول ٤٠٤ بلا نداء · `no-store` · السرّ مع كل نداء.
  ٢. كل كتابة (المفتاح · المواعيد · المصدر · المصادر الأولى · شغّل الآن · إيميل الأسبوع · رسالة التجربة) تطلب `confirmed:true` بالظبط قبل أي نداء،
     والجسم بالعقد بالظبط (لا `by` ولا `confirmed` ولا حقل زيادة) · نداء واحد بلا إعادة · تدقيق عند النجاح بلا البريد.
  ٣. المواعيد: «٧» و«٧، ١٩» بالأرقام الهندية تتطبَّع، وغير ٠..٢٣ يترفض قبل أي نداء.
  ٤. المصدر: PUT يبعت الصف كاملًا (المحدِّد والملاحظات ما تضيعش) بالحقل المتغيّر بس · مصدر مش موجود ⇒ ٤٠٤ بلا كتابة.
  ٥. القراءات بقايمة بيضا (رابط javascript: ⇒ '' · الغايب null مش صفر) · جسر غايب ⇒ `bridge_missing` · رد ضايع على كتابة ⇒ ٥٠٢ و`no_reply`.
  ٦. المعاينة بلا تأكيد وبلا تدقيق وبلا كتابة · البريد يتحقق قبل أي نداء.
  ٧. النشر/الرفض من «للمراجعة» = مسار القرار الموجود (`jobs/<id>/decide`).
"""
import copy
import datetime
import json

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
ADMIN_EMAIL = 'r18eng-admin@x.test'
NON_ADMIN = ['employee', 'trainer', 'investor', 'viewer', 'pending']
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
E = '/api/v2/saha/engine'
B = '/api/bridge/opportunities'


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
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
                 linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = u.dashboard_role = role
    u.is_active = True
    db.session.commit()
    return u


def _bearer(u):
    tok = jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('r18eng-%s@x.test' % r, r)) for r in NON_ADMIN}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}
        # سطور السجل من الملف ده تتمسح (ملفات تانية بتفحص إن كل سطور `saha.*` من أدمنها هي)
        AuditLog.query.filter(AuditLog.actor_email == ADMIN_EMAIL).delete()
        db.session.commit()


class FakeEngine(object):
    def __init__(self):
        self.autorun = {'enabled': False, 'source': 'default', 'hours': '7', 'running': False, 'secret_x': 'leak',
                        'last_result': {'ok': True, 'ran_at': '2026-11-08T05:00:00Z', 'fetched': 20, 'new': 6, 'published': 2, 'drafts': 4, 'filled': 1,
                                        'expired': 0, 'skipped': {'not-legal': 9, 'source-error': 1, 'item-error': 2}, 'gate': 'rule'}}
        self.sources = [{'id': 'eu-grants', 'name': 'منح أوروبية', 'kind': 'html', 'url': 'https://eu.test/grants', 'item': {'item_xpath': '//li', 'title_xpath': './/a'},
                         'kind_default': 'grant', 'country': 'various', 'trusted': False, 'enabled': True, 'max_items': 15, 'notes': 'ملاحظة الفريق',
                         'evidence': {'x': 1}, 'last_run': {'at': '2026-11-08T05:00:00Z', 'ok': True, 'fetched': 9, 'new': 3, 'published': 0, 'drafts': 3, 'error': ''}},
                        {'id': 'bad', 'name': 'سيئ', 'kind': 'rss', 'url': 'javascript:alert(1)', 'trusted': True, 'enabled': False}]
        self.review = [{'id': 'job-9', 'title': 'منحة جديدة', 'kind': 'grant', 'provider': 'جهة', 'deadline': '2026-12-01', 'source_id': 'eu-grants',
                        'tracks': ['intl'], 'possible_duplicate_of': 'job-2', 'legal_reason': 'weak-legal-signal', 'created_at': '2026-11-08T05:01:00Z',
                        'poster_email': 'leak@x.test'}]
        self.summary = {'drafts_waiting': 4, 'possible_duplicates': 1, 'published_24h': 2, 'autorun': {'enabled': False, 'source': 'default'},
                        'last_run': {'at': '2026-11-08T05:00:00Z', 'fetched': 20, 'published': 2, 'drafts': 4, 'skipped': 12, 'errors': 3},
                        'digest': {'enabled': False, 'last_sent_at': None, 'last_count': 0}}
        self.digest = {'enabled': False, 'day': 'sun', 'hour': 10, 'last_sent_at': None, 'last_count': 0}
        self.down, self.missing, self.forced = set(), set(), {}

    def handle(self, method, path, params, body):
        if (method, path) in self.forced:
            return self.forced[(method, path)]
        if path in self.down:
            return 503, {'detail': 'x'}
        if path in self.missing:
            return 404, {'detail': 'Not Found'}
        if path == B + '/autorun':
            if method == 'PUT':
                self.autorun.update({'enabled': body['enabled'], 'source': 'settings'})
                if 'hours' in body:
                    self.autorun['hours'] = body['hours']
            return 200, self.autorun
        if path == B + '/sources' and method == 'GET':
            return 200, {'sources': self.sources, 'count': len(self.sources)}
        if path.startswith(B + '/sources/') and method == 'PUT':
            sid = path.rsplit('/', 1)[1]
            row = [s for s in self.sources if s['id'] == sid][0]
            row.update(body)
            return 200, row
        if path == B + '/sources/import-seed':
            return 200, {'created': 5, 'kept': 1, 'errors': ['x: bad']}
        if path == B + '/run':
            return 200, {'ok': True, 'ran_at': '2026-11-08T12:00:00Z', 'fetched': 11, 'new': 4, 'published': 1, 'drafts': 3, 'filled': 0, 'expired': 2,
                         'skipped': {'not-legal': 5, 'source-error': 1}, 'sources': [{'id': 'eu-grants', 'error': 'boom'}]}
        if path == B + '/summary':
            return 200, self.summary
        if path == B + '/review':
            return 200, {'items': self.review}
        if path == B + '/digest':
            if method == 'PUT':
                self.digest['enabled'] = body['enabled']
            return 200, self.digest
        if path == B + '/digest/preview':
            # شكل `opp_digest.preview` الحقيقي: رمز المسار + اسمه العربي + السبب + هل هتتبعت
            return 200, {'subject': 'فرص الأسبوع في مسارك', 'html': '<p>مرحبًا</p><script>x</script>', 'count': 3, 'track': 'intl-law',
                         'track_title': 'القانون الدولي', 'reason': '', 'will_send': True, 'x': 1}
        if path == B + '/digest/send-test':
            return 200, {'sent': True, 'reason': '', 'track': 'intl-law', 'count': 3}
        if path.startswith('/api/bridge/jobs/') and path.endswith('/decide'):
            return 200, {'id': path.split('/')[4], 'title': 'منحة جديدة', 'review_status': 'published' if body['decision'] == 'approve' else 'rejected'}
        return 404, {'detail': 'Not Found'}


class Plat(object):
    def __init__(self):
        self.ef = FakeEngine()
        self.seen, self.blocked = [], []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'headers': dict(headers or {}),
                          'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        return _Resp(*self.ef.handle(method.upper(), url[len(PLATFORM):], params or {}, json or {}))

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
    yield p
    assert p.blocked == [], p.blocked


def _call(ctx, method, path, body=None, role='admin'):
    kw = {'headers': dict(ctx['heads'][role]) if role else {}}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


def _audits(prefix):
    with flask_app.app_context():
        return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email)
                for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%')).order_by(AuditLog.id).all()]


READS = [E + '/autorun', E + '/sources', E + '/summary', E + '/review', E + '/digest']
C = {'confirmed': True}
WRITES = [('PUT', E + '/autorun', {'enabled': True, 'confirmed': True}, {'enabled': True}),
          ('PUT', E + '/autorun', {'enabled': False, 'hours': '٧، ١٩', 'confirmed': True}, {'enabled': False, 'hours': '7,19'}),
          ('PUT', E + '/sources/eu-grants', {'trusted': True, 'confirmed': True}, None),
          ('POST', E + '/sources/import-seed', dict(C), None),
          ('POST', E + '/run', dict(C), {}),
          ('PUT', E + '/digest', {'enabled': True, 'confirmed': True}, {'enabled': True}),
          ('POST', E + '/digest/send-test', {'email': 'Me@Example.test', 'confirmed': True}, {'email': 'me@example.test'})]


# ---------------------------------------------------------------- ١) الأدوار والمفتاح

@pytest.mark.parametrize('role', NON_ADMIN)
def test_every_engine_route_is_admin_only(ctx, plat, role):
    for p in READS:
        assert _call(ctx, 'GET', p, role=role).status_code == 403, (role, p)
    for m, p, body, _ in WRITES + [('POST', E + '/digest/preview', {'email': 'a@b.test'}, None)]:
        assert _call(ctx, m, p, body, role=role).status_code == 403, (role, p)
        assert _call(ctx, m, p, body, role=None).status_code == 401
    assert plat.seen == []


def test_switch_off_means_404_with_no_platform_call(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    for p in READS:
        assert _call(ctx, 'GET', p).status_code == 404
    for m, p, body, _ in WRITES:
        assert _call(ctx, m, p, body).status_code == 404
    assert plat.seen == []


def test_no_store_and_the_secret_goes_out(ctx, plat):
    rs = [_call(ctx, 'GET', p) for p in READS] + [_call(ctx, m, p, b) for m, p, b, _ in WRITES]
    assert all(r.headers.get('Cache-Control') == 'no-store' for r in rs)
    assert all(r.status_code == 200 for r in rs), [(r.status_code, r.get_json()) for r in rs if r.status_code != 200]
    assert plat.seen and all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)


# ---------------------------------------------------------------- ٢) الكتابات: تأكيد صريح · الجسم بالعقد · تدقيق

@pytest.mark.parametrize('method,path,body,sent', WRITES)
def test_a_write_needs_exact_true_confirmation_before_any_call(ctx, plat, method, path, body, sent):
    for bad in (None, False, 'true', 1):
        b = dict(body)
        if bad is None:
            b.pop('confirmed')
        else:
            b['confirmed'] = bad
        r = _call(ctx, method, path, b)
        assert r.status_code == 400 and CONFIRM_AR in r.get_json()['error']
    assert plat.writes() == []


@pytest.mark.parametrize('method,path,body,sent', WRITES)
def test_a_write_sends_the_contract_body_once_and_is_audited(ctx, plat, method, path, body, sent):
    n0 = len(_audits('saha.engine'))
    r = _call(ctx, method, path, dict(body, by='attacker@evil.test', injected='x'))
    assert r.status_code == 200, r.get_json()
    w = plat.writes()
    assert len(w) == 1, 'نداء كتابة واحد بلا إعادة'
    if sent is not None:
        assert w[0]['json'] == sent, w[0]['json']
    js = w[0]['json'] or {}
    assert 'by' not in js and 'confirmed' not in js and 'injected' not in js
    au = _audits('saha.engine')
    assert len(au) == n0 + 1 and au[-1][3] == ADMIN_EMAIL
    assert 'example.test' not in json.dumps(au[-1], ensure_ascii=False), 'لا بريد في السجل'


def test_autorun_switch_reads_back_source_and_hours(ctx, plat):
    d = _call(ctx, 'GET', E + '/autorun').get_json()
    assert d['enabled'] is False and d['source'] == 'default' and d['hours'] == '7' and 'secret_x' not in d
    assert d['last_result']['errors'] == 3 and d['last_result']['skipped'] == 9 and d['last_result']['at'] == '2026-11-08T05:00:00Z'
    d = _call(ctx, 'PUT', E + '/autorun', {'enabled': True, 'confirmed': True}).get_json()
    assert d['enabled'] is True and d['source'] == 'settings'
    assert _audits('saha.engine_autorun_on')[-1][2] == {'enabled': True, 'hours': '', 'source': 'settings'}
    plat.ef.autorun['hours'] = [19, 7, 7, 99]                     # المنصة الحالية ترجّع قائمة
    assert _call(ctx, 'GET', E + '/autorun').get_json()['hours'] == '7,19'


@pytest.mark.parametrize('hours', ['24', '7,25', 'x', '', '1,2,3,4,5,6,7', '-1', '٧.٥'])
def test_bad_hours_are_refused_before_any_call(ctx, plat, hours):
    r = _call(ctx, 'PUT', E + '/autorun', {'enabled': True, 'hours': hours, 'confirmed': True})
    assert r.status_code == 422 and 'ساعة' in r.get_json()['error']
    assert plat.writes() == []


def test_autorun_needs_a_real_boolean(ctx, plat):
    for v in ('true', 1, None):
        r = _call(ctx, 'PUT', E + '/autorun', {'enabled': v, 'confirmed': True})
        assert r.status_code == 422
    assert plat.writes() == []


# ---------------------------------------------------------------- ٣) المصادر

def test_sources_are_whitelisted_with_host_and_safe_links(ctx, plat):
    d = _call(ctx, 'GET', E + '/sources').get_json()
    a, b = d['items']
    assert a['host'] == 'eu.test' and a['url'] == 'https://eu.test/grants' and 'evidence' not in a and 'notes' not in a and 'item' not in a
    assert a['last_run'] == {'fetched': 9, 'new': 3, 'published': 0, 'drafts': 3, 'at': '2026-11-08T05:00:00Z', 'ok': True}
    assert b['url'] == '' and b['host'] == '' and b['last_run'] is None and b['trusted'] is True and b['enabled'] is False


def test_source_put_sends_the_full_row_with_only_the_changed_field(ctx, plat):
    r = _call(ctx, 'PUT', E + '/sources/eu-grants', {'trusted': True, 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['trusted'] is True
    sent = plat.writes()[0]['json']
    assert sent == {'name': 'منح أوروبية', 'kind': 'html', 'url': 'https://eu.test/grants', 'item': {'item_xpath': '//li', 'title_xpath': './/a'},
                    'kind_default': 'grant', 'country': 'various', 'trusted': True, 'enabled': True, 'max_items': 15, 'notes': 'ملاحظة الفريق'}
    assert _audits('saha.engine_source')[-1][1:3] == ('eu-grants', {'trusted': True})


def test_source_put_validates_before_any_write(ctx, plat):
    assert _call(ctx, 'PUT', E + '/sources/eu-grants', {'confirmed': True}).status_code == 422
    assert _call(ctx, 'PUT', E + '/sources/eu-grants', {'enabled': 'yes', 'confirmed': True}).status_code == 422
    assert _call(ctx, 'PUT', E + '/sources/EU%20X', {'enabled': True, 'confirmed': True}).status_code == 400
    r = _call(ctx, 'PUT', E + '/sources/ghost', {'enabled': True, 'confirmed': True})
    assert r.status_code == 404 and 'المصدر' in r.get_json()['error']
    assert plat.writes() == []


def test_sources_seed_reports_counts_only(ctx, plat):
    d = _call(ctx, 'POST', E + '/sources/import-seed', dict(C)).get_json()
    assert d == {'created': 5, 'kept': 1, 'errors': 1}


# ---------------------------------------------------------------- ٤) شغّل الآن · الملخص · المراجعة

def test_run_now_counts_errors_from_the_skips(ctx, plat):
    d = _call(ctx, 'POST', E + '/run', dict(C)).get_json()
    assert d['fetched'] == 11 and d['published'] == 1 and d['drafts'] == 3 and d['errors'] == 1 and d['failed'] is False and d['busy'] is False
    assert plat.writes()[0]['timeout'] == 110


def test_run_now_busy_and_failed_are_told_apart(ctx, plat):
    plat.ef.forced[('POST', B + '/run')] = (200, {'ok': False, 'busy': True})
    d = _call(ctx, 'POST', E + '/run', dict(C)).get_json()
    assert d['busy'] is True and d['failed'] is False
    plat.ef.forced[('POST', B + '/run')] = (200, {'ok': False, 'error': 'db-unavailable'})
    d = _call(ctx, 'POST', E + '/run', dict(C)).get_json()
    assert d['failed'] is True and 'error' not in d


def test_lost_reply_on_a_write_is_no_reply_not_refused(ctx, plat):
    plat.ef.down.add(B + '/run')
    r = _call(ctx, 'POST', E + '/run', dict(C))
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert len(plat.writes()) == 1
    assert _audits('saha.no_reply')[-1][2] == {'attempt': 'saha.engine_run'}


def test_summary_keeps_missing_numbers_null(ctx, plat):
    d = _call(ctx, 'GET', E + '/summary').get_json()
    assert d['drafts_waiting'] == 4 and d['held_news_24h'] is None and d['last_run']['errors'] == 3 and d['autorun'] == {'enabled': False, 'source': 'default'}
    assert d['digest'] == {'enabled': False, 'day': '', 'hour': None, 'last_sent_at': None, 'last_count': 0}


def test_review_is_whitelisted_and_limited(ctx, plat):
    d = _call(ctx, 'GET', E + '/review?limit=999').get_json()
    assert [c['params'] for c in plat.seen if c['path'] == B + '/review'][-1] == {'limit': 50}
    row = d['items'][0]
    assert row == {'id': 'job-9', 'title': 'منحة جديدة', 'kind': 'grant', 'provider': 'جهة', 'deadline': '2026-12-01', 'source_id': 'eu-grants', 'tracks': ['intl'],
                   'possible_duplicate_of': 'job-2', 'legal_reason': 'weak-legal-signal', 'created_at': '2026-11-08T05:01:00Z'}
    _call(ctx, 'GET', E + '/review?limit=20')
    assert [c['params'] for c in plat.seen if c['path'] == B + '/review'][-1] == {'limit': 20}


def test_missing_bridge_reads_as_not_available_yet(ctx, plat):
    for path in (B + '/summary', B + '/review', B + '/digest', B + '/autorun', B + '/sources'):
        plat.ef.missing.add(path)
    for p in READS:
        r = _call(ctx, 'GET', p)
        assert r.status_code == 404 and r.get_json().get('bridge_missing') is True, p


def test_publish_and_reject_from_review_use_the_existing_decide_route(ctx, plat):
    r = _call(ctx, 'POST', '/api/v2/saha/opportunities/job-9/decide', {'decision': 'approve', 'confirmed': True})
    assert r.status_code == 200 and plat.writes()[-1]['path'] == '/api/bridge/jobs/job-9/decide'
    r = _call(ctx, 'POST', '/api/v2/saha/opportunities/job-9/decide', {'decision': 'reject', 'reason': 'مكررة', 'confirmed': True})
    assert r.status_code == 200 and plat.writes()[-1]['json']['reason'] == 'مكررة'


# ---------------------------------------------------------------- ٥) إيميل الأسبوع

def test_digest_read_and_switch(ctx, plat):
    d = _call(ctx, 'GET', E + '/digest').get_json()
    assert d == {'enabled': False, 'day': 'sun', 'hour': 10, 'last_sent_at': None, 'last_count': 0}
    d = _call(ctx, 'PUT', E + '/digest', {'enabled': True, 'confirmed': True}).get_json()
    assert d['enabled'] is True and _audits('saha.engine_digest_on')[-1][2] == {'enabled': True}


def test_preview_is_a_dry_read_with_no_confirmation_and_no_audit(ctx, plat):
    n0 = len(_audits('saha.'))
    r = _call(ctx, 'POST', E + '/digest/preview', {'email': ' Member@X.test '})
    d = r.get_json()
    assert r.status_code == 200 and d['subject'] == 'فرص الأسبوع في مسارك' and d['count'] == 3 and d['track_title'] == 'القانون الدولي' and 'x' not in d
    assert d['reason'] == '' and d['will_send'] is True
    assert d['html'] == '<p>مرحبًا</p>' and 'script' not in d['html'].lower()
    assert plat.writes() == [] and [c['params'] for c in plat.seen if c['path'] == B + '/digest/preview'] == [{'email': 'member@x.test'}]
    assert len(_audits('saha.')) == n0


@pytest.mark.parametrize('email', ['', 'x', 'a@b', 'a b@c.test', '<a@b.test>', None, 5])
def test_bad_email_is_refused_before_any_call(ctx, plat, email):
    assert _call(ctx, 'POST', E + '/digest/preview', {'email': email}).status_code == 422
    assert _call(ctx, 'POST', E + '/digest/send-test', {'email': email, 'confirmed': True}).status_code == 422
    assert plat.seen == []


def test_send_test_reports_sent_and_reason(ctx, plat):
    plat.ef.forced[('POST', B + '/digest/send-test')] = (200, {'sent': False, 'reason': 'no-brevo-key'})
    d = _call(ctx, 'POST', E + '/digest/send-test', {'email': 'a@b.test', 'confirmed': True}).get_json()
    assert d == {'sent': False, 'reason': 'no-brevo-key'}
    assert _audits('saha.engine_digest_test')[-1][2] == {'sent': False}


# ---------------------------------------------------------------- جولة التصليح

@pytest.mark.parametrize('reply,want', [
    ({'sent': False, 'reason': 'brevo-rejected', 'track': 'x', 'count': 2}, {'sent': False, 'reason': 'brevo-rejected'}),
    ({'sent': False, 'reason': 'bad-email'}, {'sent': False, 'reason': 'bad-email'}),
    ({'sent': False, 'reason': 'no-items'}, {'sent': False, 'reason': 'no-items'}),
    ({'sent': False, 'reason': 'unsubscribed'}, {'sent': False, 'reason': 'unsubscribed'}),
    ({'sent': True, 'reason': 'sample-track', 'track': 'eg-x', 'count': 4}, {'sent': True, 'reason': 'sample-track'}),
    ({'sent': False, 'reason': 'Brevo said <b>key sk-123</b>'}, {'sent': False, 'reason': ''})])
def test_send_test_passes_only_the_platform_reason_codes(ctx, plat, reply, want):
    plat.ef.forced[('POST', B + '/digest/send-test')] = (200, reply)
    assert _call(ctx, 'POST', E + '/digest/send-test', {'email': 'a@b.test', 'confirmed': True}).get_json() == want


@pytest.mark.parametrize('reply', [
    {'subject': 'فرص الأسبوع في مسارك', 'html': '', 'count': 0, 'track': '', 'reason': 'no-user', 'will_send': False},
    {'subject': 'فرص الأسبوع في مسارك', 'html': '<p>x</p>', 'count': 2, 'track': 'eg-public-prosecution', 'track_title': 'النيابة العامة',
     'reason': 'unsubscribed', 'will_send': False}])
def test_preview_passes_reason_will_send_and_the_arabic_track_name(ctx, plat, reply):
    plat.ef.forced[('GET', B + '/digest/preview')] = (200, reply)
    d = _call(ctx, 'POST', E + '/digest/preview', {'email': 'a@b.test'}).get_json()
    assert d['reason'] == reply['reason'] and d['will_send'] is False and d['track_title'] == reply.get('track_title', '')


def test_preview_drops_an_unknown_reason(ctx, plat):
    plat.ef.forced[('GET', B + '/digest/preview')] = (200, {'subject': 's', 'html': '', 'reason': '<img src=x>', 'will_send': 'no'})
    d = _call(ctx, 'POST', E + '/digest/preview', {'email': 'a@b.test'}).get_json()
    assert d['reason'] == '' and d['will_send'] is None and d['track_title'] == ''


def test_run_errors_count_like_the_platform_summary(ctx, plat):
    """نفس عدّ `opp_engine._ERROR_KEYS` (مصدر وقع · عنصر وقع · robots) + ١ للخطأ العام — فالشاشة وتليجرام يقولوا نفس الرقم."""
    from v2_saha_routes import view_run
    v = view_run({'skipped': {'robots': 2, 'source-error': 1, 'not-legal': 4}})
    assert v['errors'] == 3 and v['skipped'] == 4
    v = view_run({'skipped': {'item-error': 1}, 'error': 'db-unavailable', 'ok': False})
    assert v['errors'] == 2 and v['skipped'] == 0
    assert view_run({'skipped': {}, 'error': ''})['errors'] == 0


def test_hours_only_change_reads_the_switch_fresh_before_sending(ctx, plat):
    """الشاشة كانت فاكرة المفتاح مقفول، وأدمن تاني شغّله: تغيير المواعيد ما يرجّعوش مقفول."""
    plat.ef.autorun.update({'enabled': True, 'source': 'settings'})
    n0 = len(_audits('saha.engine_autorun_hours'))
    r = _call(ctx, 'PUT', E + '/autorun', {'hours': '٧، ١٩', 'confirmed': True})
    assert r.status_code == 200, r.get_json()
    w = plat.writes()
    assert len(w) == 1 and w[0]['json'] == {'enabled': True, 'hours': '7,19'}
    gets = [c for c in plat.seen if c['method'] == 'GET' and c['path'] == B + '/autorun']
    assert len(gets) == 1 and plat.seen.index(gets[0]) < plat.seen.index(w[0]), 'القراءة الطازة قبل الإرسال'
    au = _audits('saha.engine_autorun_hours')
    assert len(au) == n0 + 1 and au[-1][2]['enabled'] is True and au[-1][2]['hours'] == '7,19'


def test_hours_only_change_sends_nothing_when_the_fresh_read_fails(ctx, plat):
    plat.ef.forced[('GET', B + '/autorun')] = (503, {'detail': 'x'})
    r = _call(ctx, 'PUT', E + '/autorun', {'hours': '9', 'confirmed': True})
    assert r.status_code >= 500 and plat.writes() == []
    plat.ef.forced[('GET', B + '/autorun')] = (200, {'enabled': 'yes'})
    r = _call(ctx, 'PUT', E + '/autorun', {'hours': '9', 'confirmed': True})
    assert r.status_code == 502 and plat.writes() == []


def test_hours_only_needs_a_valid_hour_and_no_hours_needs_a_boolean(ctx, plat):
    assert _call(ctx, 'PUT', E + '/autorun', {'hours': '25', 'confirmed': True}).status_code == 422
    assert _call(ctx, 'PUT', E + '/autorun', {'confirmed': True}).status_code == 422
    assert plat.seen == []
