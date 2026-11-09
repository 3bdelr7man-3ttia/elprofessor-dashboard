# -*- coding: utf-8 -*-
"""مسارات «كتبنا وأدلّتنا» `/api/v2/books/ours/*` و`/api/v2/books/guide-codes` (docs/v2/books-ours/SPEC.md §أ ب د).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_books_ours_routes.py

⛔ صفر شبكة حقيقية وصفر نداء ذكاء حقيقي: المنصة في الذاكرة (`uiharness/books_ours_fixtures.OursPlatform`)، و`ai_call` بديل في الذاكرة،
وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.

اللي بيثبّته:
  ١. أدمن بس · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` على كل رد.
  ٢. كل كتابة تطلب `confirmed:true` بالظبط، و`by` من التوكن وحده، وقايمة بيضا للحقول. ⛔ ولا سعر من أي مسار هنا.
  ٣. رفع الملف: PDF بس (الامتداد وأول `%PDF-`) قبل أي نداء للمنصة · السقف ٤١٣ · الرد الضايع ⇒ ٥٠٢ + `no_reply` بنداء واحد.
  ٤. نص `detail` العربي من المنصة بيوصل بنفس الكود (٤٠٩ «ارفع ملف الـPDF الأول» · ٤٢٢ · ٤١٣).
  ٥. تدقيق عند النجاح بس، والفاعل من التوكن.
  ٦. مسودة العقل: نداء كاتب واحد · بتتحفظ بلا أي نداء للمنصة · السقوف اليومية · فحوص الصدق · الكاتب الاحتياطي.
  ٧. الـPDF: يطلع (لو weasyprint موجودة) · غيابها ⇒ رسالة عربية واضحة · الرفع بنفس مسار الرفع وبتأكيد.
"""
import copy
import datetime
import io
import json
import os
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import books_ours_fixtures as bof   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2bo-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
PDF = b'%PDF-1.4\n%stub\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
IDEM = 'bo-0123456789abcdef0123456789abcdef'
B = '/api/v2/books/ours'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


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
        heads = {r: _bearer(_mkuser('v2bo-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.ef = bof.OursPlatform()
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        path = url[len(PLATFORM):]
        body = copy.deepcopy(json)
        if files:
            name, content = files['file'][0], files['file'][1]
            body = dict(data or {}, __file__={'name': name, 'size': len(content), 'head': content[:8].decode('latin-1'), 'ctype': files['file'][2]})
        self.seen.append({'method': method.upper(), 'url': url, 'path': path, 'params': dict(params or {}), 'json': body, 'timeout': timeout, 'data': data})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        if body is not None and files:
            wire = dict(data or {})
            wire['confirmed'] = wire.get('confirmed') == 'true'
            wire['__file__'] = body['__file__']
            body = wire
        out = self.ef.handle(method, path, params, body)
        return _Resp(*(out if out is not None else (200, [])))

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
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _call(ctx, method, path, body=None, who='admin', **kw):
    heads = {} if who is None else ctx['heads'][who]
    if body is not None:
        return ctx['client'].open(path, method=method, headers=heads, json=body, **kw)
    return ctx['client'].open(path, method=method, headers=heads, **kw)


def _upload(ctx, slug='ours-startup-law', name='x.pdf', data=PDF, confirmed='true', who='admin', field='file'):
    form = {}
    if confirmed is not None:
        form['confirmed'] = confirmed
    if data is not None:
        form[field] = (io.BytesIO(data), name)
    return ctx['client'].post('%s/%s/file' % (B, slug), headers=ctx['heads'][who] if who else {}, data=form, content_type='multipart/form-data')


def _audits(prefix):
    return [a for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%')).all()]


# (method, path, body, needs_confirmed)
ROUTES = [
    ('GET', B, None, False),
    ('POST', B, {'title': 'كتاب', 'about': 'نبذة', 'type': 'book', 'idem_key': IDEM}, True),
    ('PUT', B + '/ours-startup-law', {'title': 'عنوان جديد'}, True),
    ('PUT', B + '/ours-startup-law/status', {'live': True}, True),
    ('GET', '/api/v2/books/guide-codes', None, False),
    ('PUT', '/api/v2/books/guide-codes', {'codes': [{'code': 'abc-1', 'note': 'x', 'max_uses': 5, 'active': True}]}, True),
    ('GET', B + '/ours-startup-law/brain/draft', None, False),
    ('POST', B + '/ours-startup-law/brain/draft', {'instruction': 'اكتب'}, False),
    ('PUT', B + '/ours-startup-law/brain/draft', {'title': 'ع', 'chapters': [{'title': 'ف', 'body': 'ن'}]}, False),
    ('POST', B + '/ours-startup-law/brain/pdf', {}, True),
]


# ---------------------------------------------------------------- ١ · الحرّاس
@pytest.mark.parametrize('method,path,body,_c', ROUTES)
def test_admin_only_and_closed_key_and_no_store(ctx, plat, monkeypatch, method, path, body, _c):
    for who in NON_ADMIN_ROLES:
        assert _call(ctx, method, path, body or ({} if method != 'GET' else None), who=who).status_code == 403, who
    assert _call(ctx, method, path, body or ({} if method != 'GET' else None), who=None).status_code == 401
    assert plat.seen == []
    r = _call(ctx, method, path, dict(body or {}, confirmed=True) if method != 'GET' else None)
    assert r.headers.get('Cache-Control') == 'no-store' or r.status_code in (200, 202, 400, 409, 429, 503)
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    plat.seen.clear()
    r = _call(ctx, method, path, dict(body or {}, confirmed=True) if method != 'GET' else None)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store' and plat.seen == []


def test_upload_guards_admin_key(ctx, plat, monkeypatch):
    for who in NON_ADMIN_ROLES:
        assert _upload(ctx, who=who).status_code == 403
    assert _upload(ctx, who=None).status_code == 401
    assert plat.seen == []
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    assert _upload(ctx).status_code == 404 and plat.seen == []


def test_bad_slug_rejected_before_any_call(ctx, plat):
    for path, m, body in ((B + '/a%20b', 'PUT', {'title': 'x', 'confirmed': True}), (B + '/a%20b/status', 'PUT', {'live': True, 'confirmed': True}),
                          (B + '/a%20b/brain/draft', 'POST', {'instruction': 'x'})):
        assert _call(ctx, m, path, body).status_code == 400, path
    assert _upload(ctx, slug='a%20b').status_code == 400
    assert plat.seen == []


# ---------------------------------------------------------------- ٢ · التأكيد والقايمة البيضا وشيل السعر
@pytest.mark.parametrize('method,path,body,needs', [r for r in ROUTES if r[3]])
def test_every_write_needs_exact_confirmed(ctx, plat, method, path, body, needs):
    for bad in (None, False, 'true', 1, 'yes', 0):
        b = dict(body)
        if bad is not None:
            b['confirmed'] = bad
        r = _call(ctx, method, path, b)
        assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR, (path, bad)
    assert plat.seen == []


def test_upload_needs_confirmed_field(ctx, plat):
    for bad in (None, 'false', '1', 'True', ''):
        r = _upload(ctx, confirmed=bad)
        assert r.status_code == 400 and r.get_json()['error'] == CONFIRM_AR, bad
    assert plat.seen == []


def test_create_whitelist_by_from_token_and_no_money(ctx, plat):
    r = _call(ctx, 'POST', B, {'title': ' دليل جديد ', 'about': 'نبذة', 'type': 'guide', 'idem_key': IDEM, 'confirmed': True, 'by': 'evil@x.test',
                              'price': 99, 'price_eg': 5, 'pricing': {'eg': 1}, 'versions': {'pdf': {'eg': 10}}, 'visible': True, 'is_free': True,
                              'owner_pct': 90, 'platform_pct': 10, 'status': 'live', 'slug': 'hijack', 'file': {'x': 1}})
    assert r.status_code == 200 and r.get_json()['ok'] is True
    w = plat.writes()
    assert len(w) == 1 and w[0]['method'] == 'POST' and w[0]['path'] == '/api/bridge/books/ours'
    assert w[0]['json'] == {'title': 'دليل جديد', 'about': 'نبذة', 'type': 'guide', 'idem_key': IDEM, 'confirmed': True, 'by': ADMIN_EMAIL}
    assert [a for a in _audits('book_ours.create') if a.target == IDEM]


def test_create_validation_and_other_type_exists(ctx, plat):
    assert _call(ctx, 'POST', B, {'title': '', 'type': 'book', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', B, {'title': 'ع' * 161, 'type': 'book', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', B, {'title': 'عنوان', 'type': 'novel', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', B, {'title': 'عنوان', 'about': 'ن' * 2001, 'type': 'book', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', B, {'title': 'عنوان', 'type': 'book', 'idem_key': 'قصير', 'confirmed': True}).status_code == 400
    assert plat.seen == []
    for t in ('book', 'guide', 'research', 'other'):
        assert _call(ctx, 'POST', B, {'title': 'ع ' + t, 'type': t, 'confirmed': True}).status_code == 200
    assert [w['json']['type'] for w in plat.writes()] == ['book', 'guide', 'research', 'other']


def test_update_whitelist(ctx, plat):
    r = _call(ctx, 'PUT', B + '/ours-startup-law', {'title': 'عنوان معدّل', 'about': 'نبذة', 'type': 'research', 'confirmed': True, 'by': 'evil@x.test',
                                                    'price': 5, 'versions': {}, 'status': 'live', 'file': {}})
    assert r.status_code == 200
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/books/ours/ours-startup-law'
    assert w[0]['json'] == {'title': 'عنوان معدّل', 'about': 'نبذة', 'type': 'research', 'confirmed': True, 'by': ADMIN_EMAIL}
    assert _call(ctx, 'PUT', B + '/ours-startup-law', {'price': 5, 'confirmed': True}).get_json()['error'] == 'لا يوجد تغيير'
    assert _call(ctx, 'PUT', B + '/ours-startup-law', {'type': 'zzz', 'confirmed': True}).status_code == 400
    assert len(plat.writes()) == 1


def test_no_price_route_under_books_ours():
    rules = [r.rule for r in flask_app.url_map.iter_rules() if r.rule.startswith('/api/v2/books/ours') or r.rule.startswith('/api/v2/books/guide-codes')]
    assert rules and not [r for r in rules if 'price' in r.lower()], rules
    src = _read('backend', 'v2_books_ours_routes.py')
    assert "/api/bridge/prices" not in src


def test_list_whitelist_and_draft_flag(ctx, plat):
    plat.ef.ours[0]['secret_path'] = '/private/x'
    plat.ef.ours[0]['file']['url'] = 'https://files.example.test/secret.pdf'
    r = _call(ctx, 'GET', B)
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    d = r.get_json()
    assert [x['slug'] for x in d['books']] == [b['slug'] for b in bof.seed_books()] and 'other' in d['types']
    blob = json.dumps(d, ensure_ascii=False)
    assert 'secret' not in blob and 'files.example' not in blob
    assert set(d['books'][0]['file']) <= set(['name', 'size', 'pages', 'uploaded', 'uploaded_at'])
    assert d['books'][2]['file'] is None
    assert [c['method'] for c in plat.seen] == ['GET'] and plat.seen[0]['path'] == '/api/bridge/books/ours' and plat.writes() == []


def test_list_failed_source_is_502_not_empty(ctx, plat):
    plat.ef.down.add('/api/bridge/books/ours')
    r = _call(ctx, 'GET', B)
    assert r.status_code == 502 and 'books' not in r.get_json()
    plat.ef.down.clear()
    plat.ef.forced[('GET', '/api/bridge/books/ours')] = (401, {'detail': 'x'})
    assert _call(ctx, 'GET', B).status_code == 502          # رفض السرّ ما يخرجش الأدمن من جلسته


# ---------------------------------------------------------------- ٣ · الرفع
def test_upload_valid_pdf_goes_with_by_and_confirmed(ctx, plat):
    before = len(_audits('book_ours.file'))
    r = _upload(ctx, name='كتاب البحث.pdf')
    assert r.status_code == 200 and r.get_json()['book']['file']['uploaded'] is True
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/books/ours/ours-startup-law/file'
    assert w[0]['data'] == {'by': ADMIN_EMAIL, 'confirmed': 'true'}
    assert w[0]['json']['__file__']['head'].startswith('%PDF-') and w[0]['json']['__file__']['ctype'] == 'application/pdf'
    assert w[0]['timeout'] >= 60
    rows = _audits('book_ours.file')
    assert len(rows) == before + 1 and rows[-1].actor_email == ADMIN_EMAIL and json.loads(rows[-1].meta_json)['size'] == len(PDF)


@pytest.mark.parametrize('name,data', [('notes.txt', PDF), ('book.docx', PDF), ('book', PDF), ('fake.pdf', b'<html>not a pdf</html>'),
                                       ('fake.pdf', b'GIF89a%PDF-'), ('empty.pdf', b''), ('x.pdf.exe', PDF)])
def test_upload_rejects_anything_not_pdf_before_the_platform(ctx, plat, name, data):
    r = _upload(ctx, name=name, data=data)
    assert r.status_code == 400 and r.get_json()['error'], (name, r.get_json())
    assert plat.seen == []


def test_upload_missing_file_and_wrong_field(ctx, plat):
    assert _upload(ctx, data=None).status_code == 400
    assert _upload(ctx, field='doc').status_code == 400
    assert plat.seen == []


def test_upload_size_cap_413_before_the_platform(ctx, plat, monkeypatch):
    monkeypatch.setenv('BOOKS_UPLOAD_MAX_MB', '1')
    big = PDF + b'0' * (2 * 1024 * 1024)
    r = _upload(ctx, data=big)
    assert r.status_code == 413 and 'أكبر' in r.get_json()['error'] and plat.seen == []
    ok = PDF + b'0' * (900 * 1024)
    assert _upload(ctx, data=ok).status_code == 200


def test_upload_platform_413_passes_through(ctx, plat):
    plat.ef.max_upload = 10
    r = _upload(ctx)
    assert r.status_code == 413 and r.get_json()['error'] == bof.TOO_BIG_AR


def test_upload_lost_reply_is_no_reply_502_single_call(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/books/ours/ours-startup-law/file')] = (504, {'detail': 'timeout'})
    n = len(_audits('book_ours.file'))
    r = _upload(ctx)
    assert r.status_code == 502 and r.get_json() == {'error': NO_REPLY_AR, 'no_reply': True}
    assert len(plat.writes()) == 1 and len(_audits('book_ours.file')) == n
    assert _audits('book_ours.no_reply')


# ---------------------------------------------------------------- ٤ · الحالة والأكواد وردود المنصة
def test_status_needs_pdf_409_arabic_passes_and_no_audit(ctx, plat):
    n = len(_audits('book_ours.status'))
    r = _call(ctx, 'PUT', B + '/ours-arbitration/status', {'live': True, 'confirmed': True})
    assert r.status_code == 409 and r.get_json()['error'] == bof.NEED_PDF_FIRST_AR
    assert len(_audits('book_ours.status')) == n
    r = _call(ctx, 'PUT', B + '/ours-startup-law/status', {'live': True, 'confirmed': True, 'price': 4, 'by': 'evil@x.test'})
    assert r.status_code == 200
    assert plat.writes()[-1]['json'] == {'live': True, 'confirmed': True, 'by': ADMIN_EMAIL}
    assert len(_audits('book_ours.status')) == n + 1
    assert _call(ctx, 'PUT', B + '/ours-startup-law/status', {'live': 'yes', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'PUT', B + '/ours-startup-law/status', {'confirmed': True}).status_code == 400


def test_platform_rejections_pass_with_same_code(ctx, plat):
    plat.ef.forced[('PUT', '/api/bridge/books/ours/ours-startup-law')] = (422, {'detail': {'error': 'x', 'message': 'عنوان مكرر'}})
    r = _call(ctx, 'PUT', B + '/ours-startup-law', {'title': 'عنوان', 'confirmed': True})
    assert r.status_code == 422 and r.get_json()['error'] == 'عنوان مكرر'
    r = _call(ctx, 'PUT', B + '/nope/status', {'live': False, 'confirmed': True})
    assert r.status_code == 404 and r.get_json()['error'] == 'هذا الكتاب غير موجود'
    plat.ef.forced[('PUT', '/api/bridge/books/ours/ours-startup-law/status')] = (403, {'detail': 'no'})
    r = _call(ctx, 'PUT', B + '/ours-startup-law/status', {'live': False, 'confirmed': True})
    assert r.status_code == 502       # رفض السرّ = عطل ربط مش جلسة منتهية


@pytest.mark.parametrize('code', [500, 502, 503, 504])
def test_lost_reply_on_every_write_is_no_reply(ctx, plat, code):
    for method, path, body in (('POST', B, {'title': 'ع', 'type': 'book'}), ('PUT', B + '/ours-startup-law', {'title': 'ع'}),
                               ('PUT', B + '/ours-startup-law/status', {'live': False}), ('PUT', '/api/v2/books/guide-codes', {'codes': []})):
        plat.ef.forced[(method, path.replace('/api/v2/books/ours', '/api/bridge/books/ours').replace('/api/v2/books/guide-codes', '/api/bridge/guides/codes'))] = (code, {'detail': 'x'})
        n = len(plat.writes())
        r = _call(ctx, method, path, dict(body, confirmed=True))
        assert r.status_code == 502 and r.get_json() == {'error': NO_REPLY_AR, 'no_reply': True}, (path, code)
        assert len(plat.writes()) == n + 1


def test_guide_codes_read_whitelist_and_write(ctx, plat):
    d = _call(ctx, 'GET', '/api/v2/books/guide-codes').get_json()
    assert [c['code'] for c in d['codes']] == ['spring-26', 'partner-gift', 'old-launch'] and d['version'] == 3
    assert set(d['codes'][0]) == {'code', 'note', 'max_uses', 'active', 'uses'}
    rows = [{'code': ' Spring-26 ', 'note': 'حملة', 'max_uses': 60, 'active': True, 'uses': 999, 'secret': 'x'}, {'code': 'new_code', 'active': False}]
    r = _call(ctx, 'PUT', '/api/v2/books/guide-codes', {'codes': rows, 'confirmed': True, 'by': 'evil@x.test'})
    assert r.status_code == 200
    w = plat.writes()
    assert w[-1]['json'] == {'codes': [{'code': 'spring-26', 'note': 'حملة', 'max_uses': 60, 'active': True},
                                       {'code': 'new_code', 'note': '', 'max_uses': None, 'active': False}], 'confirmed': True, 'by': ADMIN_EMAIL}
    assert json.loads(_audits('guide_codes.update')[-1].meta_json) == {'count': 2, 'active': 1}


@pytest.mark.parametrize('rows', [[{'code': 'ab'}], [{'code': 'a' * 41}], [{'code': 'سلام-123'}], [{'code': 'abc def'}], [{'code': 'abc'}, {'code': 'ABC'}],
                                  [{'code': 'abc', 'max_uses': 0}], [{'code': 'abc', 'max_uses': True}], [{'code': 'abc', 'max_uses': '5'}],
                                  [{'code': 'abc', 'active': 'yes'}], ['abc'], 'abc', [{'code': 'c%03d' % i} for i in range(201)]])
def test_guide_codes_validation_before_any_call(ctx, plat, rows):
    r = _call(ctx, 'PUT', '/api/v2/books/guide-codes', {'codes': rows, 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error']
    assert plat.seen == []


# ---------------------------------------------------------------- ٥ · مسودة العقل
GOOD = {'title': 'دليل البداية في عقود الإيجار',
        'about': 'دليل مبسّط يشرح خطوات كتابة عقد الإيجار وما يجب الانتباه إليه.',
        'chapters': [{'title': 'لماذا نكتب العقد', 'body': 'العقد المكتوب يحفظ حق الطرفين.\n\nيبدأ الاتفاق بفهم ما يريده كل طرف.'},
                     {'title': 'بنود لا تُنسى', 'body': 'مدة الإيجار وقيمته وموعد الدفع وطريقة التسليم.'}]}


class Writer(object):
    def __init__(self, reply=None, kind=None):
        self.calls = []
        self.reply = reply
        self.kind = kind

    def __call__(self, system, user, purpose='ai'):
        self.calls.append({'system': system, 'user': user, 'purpose': purpose})
        if self.kind:
            e = Exception('x')
            e.kind = self.kind
            raise e
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply if self.reply is not None else GOOD, ensure_ascii=False)


@pytest.fixture
def brain(monkeypatch, plat):
    import app as appmod
    w = Writer()
    monkeypatch.setattr(appmod, 'ai_call', w)
    monkeypatch.setattr(appmod, 'ai_writer_state', lambda: {'writer': 'main', 'label': None, 'source': 'db'})
    monkeypatch.setattr(appmod, 'ai_daily_usage_state', lambda: {'remaining': 100})
    monkeypatch.setitem(flask_app.config, 'BRAIN_INLINE', True)
    monkeypatch.delenv('DASH_BRAIN_WRITE', raising=False)
    monkeypatch.delenv('DASH_BRAIN_DAY_CAP', raising=False)
    return w


def _day_calls():
    from brain2 import engine
    return engine.brain_today(db)


def test_brain_draft_saved_one_writer_call_no_platform_call(ctx, plat, brain):
    n0 = _day_calls()
    r = _call(ctx, 'POST', B + '/ours-draft-a/brain/draft', {'instruction': 'اكتب دليلًا عن عقود الإيجار', 'outline': ['لماذا نكتب العقد', 'بنود لا تُنسى']})
    assert r.status_code == 202 and r.get_json()['status'] == 'ready' and r.get_json()['draft']['title'] == GOOD['title']
    assert len(brain.calls) == 1 and brain.calls[0]['purpose'] == 'books_ours.draft'
    assert 'عقود الإيجار' in brain.calls[0]['user'] and 'لماذا نكتب العقد' in brain.calls[0]['user']
    assert plat.seen == [] and plat.writes() == []
    assert _day_calls() == n0 + 1
    g = _call(ctx, 'GET', B + '/ours-draft-a/brain/draft').get_json()
    assert g['status'] == 'ready' and g['writer'] == 'main' and g['draft']['chapters'][1]['title'] == 'بنود لا تُنسى' and g['instruction'].startswith('اكتب دليلًا')
    assert plat.seen == []
    assert json.loads(_audits('book_ours.brain_draft')[-1].meta_json) == {'chapters': 2, 'writer': 'main', 'review_marks': 0}


def test_brain_draft_rules_are_in_the_prompt(ctx, plat, brain):
    _call(ctx, 'POST', B + '/ours-draft-rules/brain/draft', {'instruction': 'اكتب'})
    s = brain.calls[0]['system']
    for must in ('فصحى بسيطة', 'محايدة', 'دولي', 'لا تذكر مصدرًا', 'JSON', '«الذكاء»'):
        assert must in s, must
    assert 'يقوّم' not in s and 'يقوم' not in s


def test_brain_draft_backup_writer_is_recorded(ctx, plat, brain, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, 'ai_writer_state', lambda: {'writer': 'backup', 'label': None, 'source': 'env'})
    _call(ctx, 'POST', B + '/ours-draft-b/brain/draft', {'instruction': 'اكتب'})
    assert _call(ctx, 'GET', B + '/ours-draft-b/brain/draft').get_json()['writer'] == 'backup'


def test_brain_draft_validation_and_gates(ctx, plat, brain, monkeypatch):
    assert _call(ctx, 'POST', B + '/ours-draft-c/brain/draft', {'instruction': '  '}).status_code == 400
    assert _call(ctx, 'POST', B + '/ours-draft-c/brain/draft', {'instruction': 'ن' * 2001}).status_code == 400
    monkeypatch.setenv('DASH_BRAIN_WRITE', '0')
    r = _call(ctx, 'POST', B + '/ours-draft-c/brain/draft', {'instruction': 'اكتب'})
    assert r.status_code == 409 and r.get_json()['error'] == 'كتابة العقل متوقّفة الآن'
    monkeypatch.delenv('DASH_BRAIN_WRITE')
    import app as appmod
    monkeypatch.setattr(appmod, 'ai_writer_state', lambda: {'writer': None, 'label': None, 'source': None})
    monkeypatch.setattr(appmod, 'ai_provider_in_use', lambda: None)
    r = _call(ctx, 'POST', B + '/ours-draft-c/brain/draft', {'instruction': 'اكتب'})
    assert r.status_code == 503 and r.get_json()['error'] == 'لا يوجد كاتب متاح الآن'
    assert brain.calls == [] and plat.seen == []


def test_brain_draft_respects_daily_caps(ctx, plat, brain, monkeypatch):
    monkeypatch.setenv('DASH_BRAIN_DAY_CAP', '0')
    r = _call(ctx, 'POST', B + '/ours-draft-d/brain/draft', {'instruction': 'اكتب'})
    assert r.status_code == 429 and 'حدّه' in r.get_json()['error'] and brain.calls == []
    monkeypatch.delenv('DASH_BRAIN_DAY_CAP')
    import app as appmod
    monkeypatch.setattr(appmod, 'ai_daily_usage_state', lambda: {'remaining': 3})
    r = _call(ctx, 'POST', B + '/ours-draft-d/brain/draft', {'instruction': 'اكتب'})
    assert r.status_code == 429 and brain.calls == []


@pytest.mark.parametrize('reply,why', [
    ({'title': 'عنوان', 'about': '', 'chapters': [{'title': 'ف', 'body': 'كيف يُقَوِّم القاضي الأدلة'}]}, 'يقوّم'),
    ({'title': 'الذكاء الاصطناعي في العقود', 'about': '', 'chapters': [{'title': 'ف', 'body': 'نص'}]}, 'عنوان يبدأ بالذكاء'),
    ({'title': 'عنوان', 'about': '', 'chapters': []}, 'بلا فصول'),
    ({'title': '', 'about': '', 'chapters': [{'title': 'ف', 'body': 'نص'}]}, 'بلا عنوان'),
    ({'title': 'عنوان', 'chapters': [{'title': 'ف', 'body': ''}]}, 'فصل بلا نص'),
    ('ليس JSON أبدًا', 'نص عادي'),
    ({'title': 'عنوان', 'chapters': [{'title': 'ف', 'body': 'ن'}] * 13}, 'أكثر من ١٢ فصلًا'),
])
def test_brain_draft_invalid_output_is_never_saved(ctx, plat, brain, reply, why):
    slug = 'ours-bad-%d' % abs(hash(why))
    brain.reply = reply
    r = _call(ctx, 'POST', B + '/%s/brain/draft' % slug, {'instruction': 'اكتب دليلًا قصيرًا'})
    assert r.status_code == 202 and len(brain.calls) == 1, why
    v = _call(ctx, 'GET', B + '/%s/brain/draft' % slug).get_json()
    assert v['status'] == 'failed' and v['draft'] is None and v['error'], why
    assert plat.seen == []


def test_brain_draft_numbers_and_latin_are_marked_not_rejected(ctx, plat, brain):
    brain.reply = {'title': 'شرح قانون العمل', 'about': 'يتناول العقود.',
                   'chapters': [{'title': 'عقد العمل', 'body': 'تنص المادة ٧٠ من القانون على حقوق العامل، وصدر في سنة 2003، وهو مثل Labor Law.'},
                                {'title': 'الإجازات', 'body': 'المادة ٧٠ أيضًا، ثم المادة ٤٨ من القانون.'}]}
    r = _call(ctx, 'POST', B + '/ours-marks/brain/draft', {'instruction': 'اكتب شرحًا لقانون العمل'})
    assert r.status_code == 202
    v = _call(ctx, 'GET', B + '/ours-marks/brain/draft').get_json()
    assert v['status'] == 'ready' and v['draft']['title'] == 'شرح قانون العمل' and 'review_marks' not in v['draft']
    got = sorted((m['chapter_index'], m['token']) for m in v['review_marks'])
    assert got == [(0, '2003'), (0, 'Labor'), (0, 'Law'), (0, '٧٠'), (1, '٤٨'), (1, '٧٠')], got
    assert json.loads(_audits('book_ours.brain_draft')[-1].meta_json)['review_marks'] == 6
    assert plat.seen == []


def test_brain_draft_tokens_from_the_instruction_are_not_marked(ctx, plat, brain):
    brain.reply = {'title': 'دليل في ٣ خطوات', 'about': '', 'chapters': [{'title': 'الخطوة', 'body': 'اتبع الخطوات ٣ بترتيب. راجع Law في الملحق.'}]}
    _call(ctx, 'POST', B + '/ours-draft-n/brain/draft', {'instruction': 'اكتب دليلًا في 3 خطوات'})
    v = _call(ctx, 'GET', B + '/ours-draft-n/brain/draft').get_json()
    assert v['status'] == 'ready' and [m['token'] for m in v['review_marks']] == ['Law'], v['review_marks']


def test_review_marks_follow_the_founders_edits(ctx, plat, brain):
    brain.reply = {'title': 'عنوان', 'about': '', 'chapters': [{'title': 'ف', 'body': 'المادة ٧٠ والمادة ٤٨'}, {'title': 'فصل ثانٍ', 'body': 'نص'}]}
    _call(ctx, 'POST', B + '/ours-edit-marks/brain/draft', {'instruction': 'اكتب'})
    d = _call(ctx, 'GET', B + '/ours-edit-marks/brain/draft').get_json()
    assert len(d['review_marks']) == 2
    d['draft']['chapters'][0]['body'] = 'المادة ٧٠ فقط'
    d['draft']['chapters'][1]['body'] = 'ونُقلت المادة ٤٨ هنا'
    saved = _call(ctx, 'PUT', B + '/ours-edit-marks/brain/draft', d['draft']).get_json()
    assert sorted((m['chapter_index'], m['token']) for m in saved['review_marks']) == [(0, '٧٠'), (1, '٤٨')]
    saved['draft']['chapters'][0]['body'] = 'بلا أرقام'
    again = _call(ctx, 'PUT', B + '/ours-edit-marks/brain/draft', saved['draft']).get_json()
    assert [(m['chapter_index'], m['token']) for m in again['review_marks']] == [(1, '٤٨')]


def test_banned_word_and_ai_headline_still_reject_hard(ctx, plat, brain):
    brain.reply = {'title': 'عنوان', 'about': '', 'chapters': [{'title': 'ف', 'body': 'المادة ٧٠ وكيف يُقَوِّم القاضي'}]}
    _call(ctx, 'POST', B + '/ours-hard-a/brain/draft', {'instruction': 'اكتب'})
    assert _call(ctx, 'GET', B + '/ours-hard-a/brain/draft').get_json()['status'] == 'failed'
    brain.reply = {'title': 'الذكاء في العقود', 'about': '', 'chapters': [{'title': 'ف', 'body': 'نص ٧٠'}]}
    _call(ctx, 'POST', B + '/ours-hard-b/brain/draft', {'instruction': 'اكتب'})
    assert _call(ctx, 'GET', B + '/ours-hard-b/brain/draft').get_json()['status'] == 'failed'


@pytest.mark.parametrize('kind,msg', [('cap', 'وصل العقل'), ('no_key', 'لا يوجد كاتب'), (None, 'تعذّرت الكتابة')])
def test_brain_draft_writer_failure_keeps_old_draft(ctx, plat, brain, kind, msg):
    slug = 'ours-keep-%s' % kind
    _call(ctx, 'POST', B + '/%s/brain/draft' % slug, {'instruction': 'اكتب'})
    assert _call(ctx, 'GET', B + '/%s/brain/draft' % slug).get_json()['status'] == 'ready'
    brain.kind = kind or 'error'
    _call(ctx, 'POST', B + '/%s/brain/draft' % slug, {'instruction': 'اكتب مرة ثانية'})
    v = _call(ctx, 'GET', B + '/%s/brain/draft' % slug).get_json()
    assert v['status'] == 'failed' and msg in v['error'] and v['draft']['title'] == GOOD['title']
    assert plat.seen == []


def test_brain_draft_busy_returns_409(ctx, plat, brain, monkeypatch):
    from brain2 import engine
    monkeypatch.setattr(engine, 'submit', lambda ns, key, fn: {'queued': True})      # الخيط الخلفي لم يخلّص بعد
    r = _call(ctx, 'POST', B + '/ours-busy/brain/draft', {'instruction': 'اكتب'})
    assert r.status_code == 202 and r.get_json()['status'] == 'writing' and brain.calls == []
    r = _call(ctx, 'POST', B + '/ours-busy/brain/draft', {'instruction': 'اكتب'})
    assert r.status_code == 409 and r.get_json()['error'] == 'العقل يكتب الآن. جرّب بعد قليل'
    row = None
    import v2_books_ours_routes  # noqa: F401
    from sqlalchemy import text
    db.session.execute(text("UPDATE v2_books_ours_drafts SET updated_at = :t WHERE slug = 'ours-busy'"), {'t': datetime.datetime.utcnow() - datetime.timedelta(minutes=30)})
    db.session.commit()
    assert _call(ctx, 'GET', B + '/ours-busy/brain/draft').get_json()['status'] == 'failed'      # عالقة قديمة ⇒ فشل مش «يكتب» للأبد
    assert row is None


def test_brain_draft_edit_by_founder_saves_locally(ctx, plat, brain):
    edited = {'title': 'عنوان بيد المؤسس 7', 'about': 'نبذة', 'chapters': [{'title': 'فصل', 'body': 'نص يحتوي 123 رقمًا'}]}
    r = _call(ctx, 'PUT', B + '/ours-edit/brain/draft', edited)
    assert r.status_code == 200 and r.get_json()['status'] == 'ready' and r.get_json()['draft']['chapters'][0]['body'].endswith('رقمًا')
    assert brain.calls == [] and plat.seen == []
    assert _call(ctx, 'PUT', B + '/ours-edit/brain/draft', {'title': '', 'chapters': []}).status_code == 400
    assert _call(ctx, 'PUT', B + '/ours-edit/brain/draft', {'title': 'ع', 'chapters': [{'title': 'ف', 'body': 'قال يُقَوِّم'}]}).status_code == 400
    assert _call(ctx, 'GET', B + '/ours-edit/brain/draft').get_json()['draft']['title'] == 'عنوان بيد المؤسس 7'


def test_brain_draft_none_when_never_written(ctx, plat):
    v = _call(ctx, 'GET', B + '/ours-never/brain/draft').get_json()
    assert v == {'status': 'none', 'draft': None, 'review_marks': []}


# ---------------------------------------------------------------- ٦ · الـPDF
def _seed_draft(ctx, slug):
    r = _call(ctx, 'PUT', B + '/%s/brain/draft' % slug, GOOD)
    assert r.status_code == 200


def test_pdf_needs_a_saved_draft(ctx, plat, brain):
    r = _call(ctx, 'POST', B + '/ours-nodraft/brain/pdf', {'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'] == 'اكتب المسودة أولًا' and plat.seen == []


def test_pdf_uploads_through_the_file_route_with_confirmed(ctx, plat, brain, monkeypatch):
    import v2_books_ours_routes as m
    seen = {}

    def fake(draft, fonts_dir=None):
        seen['draft'] = draft
        return PDF
    monkeypatch.setattr(m, 'render_pdf', fake)
    _seed_draft(ctx, 'ours-startup-law')
    r = _call(ctx, 'POST', B + '/ours-startup-law/brain/pdf', {'confirmed': True, 'by': 'evil@x.test'})
    assert r.status_code == 200 and r.get_json()['book']['file']['uploaded'] is True
    assert seen['draft']['title'] == GOOD['title']
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/books/ours/ours-startup-law/file' and w[0]['data'] == {'by': ADMIN_EMAIL, 'confirmed': 'true'}
    assert w[0]['json']['__file__']['name'].endswith('.pdf') and w[0]['json']['__file__']['head'].startswith('%PDF-')
    assert brain.calls == []
    assert json.loads(_audits('book_ours.file')[-1].meta_json)['source'] == 'brain'
    assert _call(ctx, 'GET', B + '/ours-startup-law/brain/draft').get_json()['pdf_at']


def test_pdf_without_confirmed_never_renders_or_uploads(ctx, plat, monkeypatch):
    import v2_books_ours_routes as m
    monkeypatch.setattr(m, 'render_pdf', lambda *a, **k: (_ for _ in ()).throw(AssertionError('rendered')))
    _seed_draft(ctx, 'ours-startup-law')
    assert _call(ctx, 'POST', B + '/ours-startup-law/brain/pdf', {}).status_code == 400
    assert plat.seen == []


def test_pdf_library_missing_is_a_clear_arabic_error(ctx, plat, monkeypatch):
    import v2_books_ours_routes as m

    def boom(*a, **k):
        raise RuntimeError('missing')
    monkeypatch.setattr(m, 'render_pdf', boom)
    _seed_draft(ctx, 'ours-startup-law')
    r = _call(ctx, 'POST', B + '/ours-startup-law/brain/pdf', {'confirmed': True})
    assert r.status_code == 503 and r.get_json()['error'] == 'إنشاء ملف PDF غير متاح على الخادم الآن' and plat.seen == []
    monkeypatch.setattr(m, 'render_pdf', lambda *a, **k: (_ for _ in ()).throw(ValueError('layout')))
    r = _call(ctx, 'POST', B + '/ours-startup-law/brain/pdf', {'confirmed': True})
    assert r.status_code == 500 and r.get_json()['error'] == 'تعذّر إنشاء ملف PDF الآن' and plat.seen == []


def test_render_pdf_without_weasyprint_raises_missing(monkeypatch):
    import builtins
    import v2_books_ours_routes as m
    real = builtins.__import__

    def deny(name, *a, **k):
        if name.startswith('weasyprint'):
            raise ImportError('no weasyprint')
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, '__import__', deny)
    with pytest.raises(RuntimeError, match='missing'):
        m.render_pdf(GOOD)


def _weasy_or_skip():
    try:
        import weasyprint   # noqa: F401
    except Exception as exc:   # noqa: BLE001  (غير موجودة، أو مكتبات النظام تحتها غير موجودة)
        pytest.skip('weasyprint غير متاحة في هذه البيئة: %s' % type(exc).__name__)


def test_real_pdf_comes_out_rtl_with_cover_toc_and_chapters():
    _weasy_or_skip()
    from weasyprint import HTML
    import v2_books_ours_routes as m
    data = m.render_pdf(GOOD)
    assert data.startswith(b'%PDF-') and len(data) > 8000
    doc = HTML(string=m.build_book_html(GOOD), base_url=m.HERE).render()
    assert len(doc.pages) >= 4                      # غلاف + فهرس + فصلان


# ---------------------------------------------------------------- ٧ · قالب الـPDF (نقي)
def test_book_html_has_brand_cover_toc_and_escapes():
    import v2_books_ours_routes as m
    draft = {'title': 'كتاب <script>alert(1)</script>', 'about': 'نبذة\n\nفقرة ثانية',
             'chapters': [{'title': 'فصل أول', 'body': 'أ\n\nب<b>'}, {'title': 'فصل ثانٍ', 'body': 'ج'}]}
    h = m.build_book_html(draft)
    assert 'dir="rtl"' in h and 'lang="ar"' in h and '#FBFAF7' in h and '#21262E' in h and '#9E2B4E' in h
    assert '<script>' not in h and '&lt;script&gt;' in h and '<b>' not in h
    assert h.count('class="ch"') == 2 and h.count('href="#c') == 2 and 'الفهرس' in h and 'البروفيسور' in h
    assert 'الفصل الأول' in h and 'الفصل الثاني' in h
    assert h.count('<p>') >= 5
    for f in ('Cairo-Regular.ttf', 'Cairo-Bold.ttf'):
        assert f in h and os.path.isfile(os.path.join(m.FONTS_DIR, f))
    assert os.path.isfile(os.path.join(m.FONTS_DIR, 'OFL-Cairo.txt'))


def test_validate_draft_is_pure_and_trims():
    from brain2 import engine
    import v2_books_ours_routes as m
    ok, why = m.validate_draft({'title': '  عنوان  ', 'about': None, 'chapters': [{'title': ' ف ', 'body': 'نص\r\n\r\n\r\n\r\nنص'}]}, engine, 'x')
    assert why is None and ok['title'] == 'عنوان' and ok['about'] == '' and ok['chapters'][0]['body'] == 'نص\n\nنص'
    assert m.validate_draft(None, engine)[1] == 'shape' and m.validate_draft({'title': 'ع', 'chapters': 'x'}, engine)[1] == 'shape'


# ---------------------------------------------------------------- ٨ · الملفات والتسجيل
def test_registered_guarded_in_app_and_docker_ships_it():
    app_src = _read('backend', 'app.py')
    i = app_src.index('import v2_books_ours_routes')
    assert app_src.rindex('try:', 0, i) > app_src.rindex('\n\n', 0, i) - 400 and "logger.exception('v2 books ours routes not loaded')" in app_src
    assert app_src.index('# ---- v2 section routes begin') < i < app_src.index('# ---- v2 section routes end')
    root = _read('Dockerfile')
    assert 'COPY backend/v2_books_ours_routes.py' in root and 'COPY backend/assets/fonts /app/assets/fonts' in root
    for lib in ('libpango-1.0-0', 'libpangoft2-1.0-0', 'libharfbuzz-subset0'):
        assert lib in root and lib in _read('backend', 'Dockerfile')
    assert 'COPY assets ./assets' in _read('backend', 'Dockerfile')
    assert 'weasyprint==' in _read('backend', 'requirements.txt')


def test_weasyprint_is_imported_lazily_only():
    src = _read('backend', 'v2_books_ours_routes.py')
    top = src.split('def register')[0]
    for line in top.splitlines():
        if line.startswith(('import ', 'from ')):
            assert 'weasyprint' not in line, line
    assert src.count('import HTML') == 1 and '    try:\n        from weasyprint import HTML' in src


def test_public_domain_author_and_free_pass_through_validated(ctx, plat):
    """كتب الملك العام (المؤسس 2026-11-09): اسم المؤلف الحقيقي و«مجاني» يعبران للمنصة بعد الفحص، و`is_free` يظل محذوفًا."""
    r = _call(ctx, 'POST', B, {'title': 'المحاماة', 'type': 'book', 'author': '  أحمد فتحي   زغلول ', 'free': True, 'is_free': True, 'confirmed': True})
    assert r.status_code == 200
    assert plat.writes()[-1]['json'] == {'title': 'المحاماة', 'about': '', 'type': 'book', 'author': 'أحمد فتحي زغلول', 'free': True,
                                         'confirmed': True, 'by': ADMIN_EMAIL}
    n = len(plat.writes())
    assert _call(ctx, 'POST', B, {'title': 'عنوان', 'type': 'book', 'author': 'م' * 201, 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', B, {'title': 'عنوان', 'type': 'book', 'free': 'yes', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'PUT', B + '/ours-startup-law', {'author': 5, 'confirmed': True}).status_code == 400
    assert len(plat.writes()) == n
    r = _call(ctx, 'PUT', B + '/ours-startup-law', {'author': '', 'free': False, 'confirmed': True})
    assert r.status_code == 200 and plat.writes()[-1]['json'] == {'author': '', 'free': False, 'confirmed': True, 'by': ADMIN_EMAIL}


def test_the_ours_sheets_carry_author_and_free():
    js = _read('dashboard-cloud', 'v2s', 'books.js')
    assert js.count("authorFields(") == 3 and "id=\"ou_au\"" in js and "id=\"ou_fr\"" in js
    assert js.count("free: !!q('#ou_fr', s).checked") == 2
    assert 'مجاني للجميع: كتاب قديم صار ملكًا عامًا، فلا سعر له.' in js
