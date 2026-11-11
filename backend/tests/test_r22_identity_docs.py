# -*- coding: utf-8 -*-
"""R22 — «هوية محفوظة» في الداشبورد: المؤسس يراجع وثيقة هوية الخبير ويحسم (وثّق / محتاج مستند أوضح).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r22_identity_docs.py

⛔ صفر شبكة حقيقية وصفر نداء حقيقي: المنصة دالة في الذاكرة تسجّل النداءات، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار
(وده كمان بيمسك أي نداء من الداشبورد لنفسه: gunicorn بعامل واحد).
  ١. المسارات الثلاثة (قايمة · ملف · قرار): أدمن بس · السرّ يطلع مع كل نداء · قايمة بيضا بالحقول · `no-store` · النوع من البايتات ·
     «محتاج مستند أوضح» بلا سبب ⇒ ٤٠٠ قبل أي نداء · رفض المنصة (٤٠٩) يعدّي كما هو · تدقيق عند النجاح بس.
  ٢. صفوف الوارد (dashboard-api.js جوه node:vm): التذكرة «توثيق هوية — الصفة» · الموثَّق ما يظهرش · غياب الجسر (٤٠٤) لا يوسم الوارد «فشل».
  ٣. القرار (EP.decideInboxItem): وثّق ⇒ verify · محتاج مستند أوضح ⇒ needs_another بسببه · بلا سبب ⇒ لا نداء أصلًا.
  ٤. الدرج (v2s/identity_docs.js): الزرّان والوثيقة · السبب مطلوب قبل أي قرار · الفشل يفتح الأزرار ويكتب السبب.
  ٥. النصوص: فصحى بسيطة، بلا «استشار»، ولا «·» جنب رقم.
"""
import datetime
import json
import os
import re
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
FILE_ID = 'idf-3c9a41d27b05'
USER_ID = 'u-expert-1'
PNG = b'\x89PNG\r\n\x1a\n' + b'0' * 40
ITEM = {'user_id': USER_ID, 'email': 'expert@example.test', 'name': 'أحمد علي', 'title': 'محامٍ بالنقض', 'status': 'pending',
        'submitted_at': '2026-11-11T08:00:00+00:00', 'note': '', 'verified_at': None, 'file_id': FILE_ID, 'id_number': '29801011234567'}


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        if isinstance(payload, tuple):
            self.content = payload[0]
            self.headers = {'Content-Type': payload[1]}
        elif isinstance(payload, str):
            self.content = payload.encode('utf-8')
            self.headers = {'Content-Type': 'text/html'}
        else:
            self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.headers = {'Content-Type': 'application/json'}

    def json(self):
        if not isinstance(self._p, (dict, list)):
            raise ValueError('not json')
        return self._p


def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role,
                 dashboard_role=role, linked_to_name='', preferred_currency='AUTO', is_active=True)
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
        heads = {r: _bearer(_mkuser('r22-%s@x.test' % r, r)) for r in ('admin', 'employee', 'viewer', 'investor', 'trainer')}
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.seen = []
        self.blocked = []
        self.reply = {}           # {path-suffix: (status, payload)} لتجربة رفض المنصة أو غيابها

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):], 'json': json, 'params': params, 'headers': headers})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        for suffix, rep in self.reply.items():
            if url.endswith(suffix):
                return _Resp(*rep)
        if '/identity-docs/files/' in url:
            return _Resp(200, (PNG, 'image/png'))
        if url.endswith('/decide'):
            body = json or {}
            return _Resp(200, {'ok': True, 'status': 'verified' if body.get('decision') == 'verify' else 'needs_another'})
        return _Resp(200, {'items': [dict(ITEM), dict(ITEM, user_id='u-2', status='verified')], 'total': 2})

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setattr(appmod.requests, 'get', lambda url, params=None, headers=None, timeout=None: p('GET', url, params=params, headers=headers, timeout=timeout))
    yield p
    assert p.blocked == [], p.blocked


def _call(ctx, method, path, body=None, who='admin'):
    return ctx['client'].open(path, method=method, headers={} if who is None else ctx['heads'][who], json=body)


def _audits(action):
    return AuditLog.query.filter_by(action=action).count()


LIST = '/api/platform-identity-docs'
FILE = '/api/platform-identity-docs/files/' + FILE_ID
DECIDE = '/api/platform-identity-docs/' + USER_ID + '/decide'


# ——————————————————————————————————————————————————————— ١. المسارات
@pytest.mark.parametrize('method,path', [('GET', LIST), ('GET', FILE), ('POST', DECIDE)])
def test_every_route_is_admin_only_and_makes_no_platform_call_otherwise(ctx, plat, method, path):
    body = {'decision': 'verify'} if method == 'POST' else None
    for who in ('employee', 'viewer', 'investor', 'trainer'):
        assert _call(ctx, method, path, body, who).status_code == 403, who
    assert _call(ctx, method, path, body, None).status_code == 401
    assert plat.seen == [], 'من غير الأدمن ما يوصلش شيء للمنصة'


def test_list_forwards_the_secret_whitelists_fields_and_is_no_store(ctx, plat):
    r = _call(ctx, 'GET', LIST)
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    call = plat.seen[-1]
    assert call['method'] == 'GET' and call['path'] == '/api/bridge/identity-docs' and call['params'] == {'status': 'pending'}
    assert call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    body = r.get_json()
    assert body['total'] == 2 and len(body['items']) == 2
    assert all('id_number' not in it for it in body['items']), 'حقل خارج القايمة البيضا ما يعدّيش'
    assert body['items'][0]['name'] == 'أحمد علي' and body['items'][0]['title'] == 'محامٍ بالنقض' and body['items'][0]['file_id'] == FILE_ID


def test_list_status_all_passes_and_junk_falls_back_to_pending(ctx, plat):
    _call(ctx, 'GET', LIST + '?status=all')
    assert plat.seen[-1]['params'] == {'status': 'all'}
    _call(ctx, 'GET', LIST + '?status=%27%3Bdrop')
    assert plat.seen[-1]['params'] == {'status': 'pending'}


def test_list_when_the_bridge_is_missing_or_answers_garbage(ctx, plat):
    plat.reply['/api/bridge/identity-docs'] = (404, {'detail': 'Not Found'})
    r = _call(ctx, 'GET', LIST)
    assert r.status_code == 404 and isinstance(r.get_json()['error'], str)
    plat.reply['/api/bridge/identity-docs'] = (200, {'items': 'oops'})
    assert _call(ctx, 'GET', LIST).status_code == 502
    plat.reply['/api/bridge/identity-docs'] = (200, '<html>proxy error</html>')
    assert _call(ctx, 'GET', LIST).status_code == 502
    plat.reply['/api/bridge/identity-docs'] = (200, [])
    r = _call(ctx, 'GET', LIST)
    assert r.status_code == 200 and r.get_json() == {'items': [], 'total': 0}, 'قايمة فاضية صريحة = لا وثائق'


def test_file_streams_the_bytes_with_safe_headers_and_audits(ctx, plat):
    n0 = _audits('identity_doc.file_view')
    r = _call(ctx, 'GET', FILE)
    assert r.status_code == 200 and r.mimetype == 'image/png' and r.data == PNG
    h = r.headers
    assert h['Cache-Control'] == 'no-store' and h['X-Content-Type-Options'] == 'nosniff' and h['Content-Security-Policy'] == "default-src 'none'; sandbox"
    c = plat.seen[-1]
    assert c['path'] == '/api/bridge/identity-docs/files/' + FILE_ID and c['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert _audits('identity_doc.file_view') == n0 + 1


def test_file_type_comes_from_the_bytes_not_from_the_header(ctx, plat):
    plat.reply['/files/' + FILE_ID] = (200, (b'<html><script>alert(1)</script></html>', 'image/png'))
    r = _call(ctx, 'GET', FILE)
    assert r.status_code == 422 and r.mimetype == 'application/json'
    for ok, kind in ((b'%PDF-1.4\n%x', 'application/pdf'), (b'\xff\xd8\xff\xe0abc', 'image/jpeg'), (b'RIFF\x00\x00\x00\x00WEBPVP8 ', 'image/webp')):
        plat.reply['/files/' + FILE_ID] = (200, (ok, 'text/plain'))
        r = _call(ctx, 'GET', FILE)
        assert r.status_code == 200 and r.mimetype == kind, kind
    plat.reply['/files/' + FILE_ID] = (200, (b'', 'image/png'))
    assert _call(ctx, 'GET', FILE).status_code == 422


def test_file_missing_down_and_bad_ids_never_reach_the_platform(ctx, plat):
    plat.reply['/files/' + FILE_ID] = (404, {'detail': 'x'})
    assert _call(ctx, 'GET', FILE).status_code == 404
    plat.reply['/files/' + FILE_ID] = (503, {'detail': 'x'})
    assert _call(ctx, 'GET', FILE).status_code == 502
    n = len(plat.seen)
    for bad in ('a', 'x' * 80, 'a b c d e f g h', 'a..b..c..d..e', 'a.b.c.d.e.f.g.h'):
        assert _call(ctx, 'GET', '/api/platform-identity-docs/files/' + bad).status_code in (400, 404), bad
    assert len(plat.seen) == n


def test_decide_verify_sends_the_exact_body_and_is_audited(ctx, plat):
    n0 = _audits('identity_doc.verify')
    r = _call(ctx, 'POST', DECIDE, {'decision': 'verify', 'extra': 'x', 'note': ''})
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'status': 'verified'}
    c = plat.seen[-1]
    assert c['method'] == 'POST' and c['path'] == '/api/bridge/identity-docs/%s/decide' % USER_ID
    assert c['json'] == {'decision': 'verify', 'note': ''}, 'جسم من قايمة بيضا، لا حقل زيادة'
    assert c['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert _audits('identity_doc.verify') == n0 + 1


def test_decide_needs_another_requires_a_real_reason_before_any_call(ctx, plat):
    for body in ({'decision': 'needs_another'}, {'decision': 'needs_another', 'note': ''}, {'decision': 'needs_another', 'note': '    '},
                 {'decision': 'needs_another', 'note': 'لا'}, {'decision': 'needs_another', 'note': 'abcd'}):
        r = _call(ctx, 'POST', DECIDE, body)
        assert r.status_code == 400 and 'سبب' in r.get_json()['error'], body
    assert plat.seen == [], 'بلا سبب ⇒ ولا نداء للمنصة'
    n0 = _audits('identity_doc.needs_another')
    r = _call(ctx, 'POST', DECIDE, {'decision': 'needs_another', 'note': '  الصورة غير واضحة، ارفع صورة أوضح  '})
    assert r.status_code == 200 and r.get_json()['status'] == 'needs_another'
    assert plat.seen[-1]['json'] == {'decision': 'needs_another', 'note': 'الصورة غير واضحة، ارفع صورة أوضح'}
    assert _audits('identity_doc.needs_another') == n0 + 1


def test_decide_rejects_unknown_decisions_and_bodiless_posts_with_a_sentence(ctx, plat):
    assert _call(ctx, 'POST', DECIDE, {'decision': 'approve'}).status_code == 400
    r = ctx['client'].post(DECIDE, headers=ctx['heads']['admin'])      # بلا جسم: جملة لا صفحة ٤١٥
    assert r.status_code == 400 and r.get_json()['error']
    assert _call(ctx, 'POST', '/api/platform-identity-docs/bad%20id/decide', {'decision': 'verify'}).status_code in (400, 404)
    assert plat.seen == []


def test_decide_platform_refusal_passes_through_and_is_not_audited(ctx, plat):
    plat.reply['/decide'] = (409, {'detail': 'لا توجد وثيقة محفوظة لهذا الخبير'})
    n0 = _audits('identity_doc.verify')
    r = _call(ctx, 'POST', DECIDE, {'decision': 'verify'})
    assert r.status_code == 409 and r.get_json()['error'] == 'لا توجد وثيقة محفوظة لهذا الخبير'
    assert _audits('identity_doc.verify') == n0


def test_secret_not_configured_means_no_call_at_all(ctx, plat, monkeypatch):
    import app as appmod
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', '')
    assert _call(ctx, 'GET', LIST).status_code == 503
    assert _call(ctx, 'GET', FILE).status_code == 503
    assert _call(ctx, 'POST', DECIDE, {'decision': 'verify'}).status_code == 503
    assert plat.seen == []


# ——————————————————————————————————————————————————————— ٢. صفوف الوارد (node)
def _rows(identity_reply, extra=None):
    responses = {'/api/platform-identity-docs?status=pending': identity_reply}
    responses.update(extra or {})
    return v2_node._run('v2_rows.js', {'responses': responses, 'keys': ['inbox']})


@needs_node
def test_the_inbox_gets_one_ticket_per_pending_document_titled_with_the_public_title():
    out = _rows({'status': 200, 'body': {'items': [ITEM, dict(ITEM, user_id='u-2', status='verified'), dict(ITEM, user_id='u-3', status='needs_another'),
                                                   dict(ITEM, user_id='u-4', title='')], 'total': 4}})
    rows = [r for r in out['inbox'] if r.get('apiKind') == 'identity_doc']
    assert [r['apiId'] for r in rows] == [USER_ID, 'u-4'], 'المعروض بانتظار القرار فقط'
    r = rows[0]
    assert r['out'] == 'توثيق هوية — محامٍ بالنقض' and rows[1]['out'] == 'توثيق هوية — خبير'
    assert r['who'] == 'أحمد علي' and r['email'] == 'expert@example.test' and r['idTitle'] == 'محامٍ بالنقض' and r['idFileId'] == FILE_ID
    assert r['approveLabel'] == 'وثّق الهوية' and r['canReject'] is True and r['rejectNeedsReason'] is True and r['ref'] == 'IDD-' + USER_ID
    assert '29801011234567' not in json.dumps(r, ensure_ascii=False), 'رقم الهوية ما يوصلش للشاشة'
    assert 'توثيق الهوية' not in out['failed']


@needs_node
def test_a_missing_bridge_does_not_mark_the_inbox_failed_but_a_broken_one_does():
    for status in (404, 403):
        out = _rows({'status': status, 'body': {'error': 'x'}})
        assert 'توثيق الهوية' not in out['failed'] and not [r for r in out['inbox'] if r.get('apiKind') == 'identity_doc']
    out = _rows({'status': 502, 'body': {'error': 'تعذر الاتصال بالمنصة'}})
    assert 'توثيق الهوية' in out['failed'], 'عطل حقيقي لازم يتعلن، مش «لا وارد»'


@needs_node
def test_the_decision_card_is_a_person_card_that_opens_the_page_of_the_item():
    row = {'apiKind': 'identity_doc', 'apiId': USER_ID, 'ref': 'IDD-' + USER_ID, 'who': 'أحمد علي', 'idTitle': 'محامٍ بالنقض', 'email': 'expert@example.test',
           'personEmail': 'expert@example.test', 'ts': 1793000000000}
    card = v2_node.logic('v2Card', row, {'now': 1793003600000})
    assert card['kind'] == 'identity_doc' and card['tag'] == 'توثيق هوية' and card['title'] == 'أحمد علي' and card['sub'] == 'محامٍ بالنقض'
    assert card['primary']['label'] == 'راجع الوثيقة' and card['primary']['act'] == {'do': 'open'}, 'ولا قرار بضغطة من البطاقة: الوثيقة تُرى أولًا'
    assert card['secondary'] is None
    assert v2_node.logic('v2bFacts', card, 1793003600000) is None, 'لا يُرسل الاسم ولا الوثيقة لأي رأي آلي'


# ——————————————————————————————————————————————————————— ٣. القرار (node)
ROW = {'apiKind': 'identity_doc', 'apiId': USER_ID, 'who': 'أحمد علي'}


@needs_node
def test_verify_posts_the_decision_with_the_exact_body():
    out = v2_node.decide(ROW, 'approve', {'status': 200, 'body': {'ok': True, 'status': 'verified'}})
    assert out['result']['ok'] is True
    c = out['calls'][0]
    assert c['url'].endswith('/platform-identity-docs/' + USER_ID + '/decide') and c['body'] == {'decision': 'verify', 'note': ''}


@needs_node
def test_needs_another_without_a_reason_never_calls_the_server_and_with_one_sends_it():
    for why in ('', '   ', 'لا', 'abcd'):
        out = v2_node.decide(ROW, 'reject', {'status': 200, 'body': {}}, reason=why)
        assert out['calls'] == [] and out['result']['ok'] is False and 'سبب' in out['result']['error'], why
    out = v2_node.decide(ROW, 'reject', {'status': 200, 'body': {'ok': True}}, reason='  الصورة مقطوعة من الأعلى  ')
    assert out['result']['ok'] is True and out['calls'][0]['body'] == {'decision': 'needs_another', 'note': 'الصورة مقطوعة من الأعلى'}


@needs_node
def test_a_refusal_from_the_platform_comes_back_as_a_final_sentence_not_a_retry():
    out = v2_node.decide(ROW, 'approve', {'status': 409, 'body': {'error': 'لا توجد وثيقة محفوظة لهذا الخبير'}})
    assert out['result']['ok'] is False and out['result']['final'] is True and 'وثيقة' in out['result']['error']
    assert len(out['calls']) == 1


# ——————————————————————————————————————————————————————— ٤. الدرج (node)
def _idd(payload):
    return v2_node._run('idd_apply.js', payload)


DOC_ROW = {'out': 'توثيق هوية — محامٍ بالنقض', 'idName': 'أحمد علي', 'idTitle': 'محامٍ بالنقض', 'email': 'expert@example.test', 'idFileId': FILE_ID,
           'whenLabel': 'قُدِّم 2026-11-11، منذ 3 ساعات'}


@needs_node
def test_the_drawer_shows_who_what_when_and_the_two_decisions_with_the_view_button():
    out = _idd({'mode': 'logic', 'row': DOC_ROW, 'texts': ['', 'abcd', 'الصورة غير واضحة']})
    html = out['html']
    for needle in ('توثيق هوية — محامٍ بالنقض', 'أحمد علي', 'محامٍ بالنقض', 'expert@example.test', 'عرض الوثيقة', 'وثّق الهوية', 'محتاج مستند أوضح',
                   'data-idd-reason', 'يراه المؤسس وحده'):
        assert needle in html, needle
    assert '٢٠٢٦-١١-١١' in html and '2026' not in html, 'الأرقام هندية كباقي الداشبورد'
    assert [c['ok'] for c in out['checks']] == [False, False, True]
    assert out['fileErr'][0] == 'الوثيقة غير متاحة' and out['fileErr'][1] == 'تعذّر عرض هذا الملف'


@needs_node
def test_the_drawer_without_a_file_has_no_view_button_and_says_why():
    out = _idd({'mode': 'logic', 'row': dict(DOC_ROW, idFileId='')})
    assert 'iddView' not in out['html'] and 'لا ملف مرفوع' in out['html']
    out = _idd({'mode': 'logic', 'row': dict(DOC_ROW, idFileId='../../etc/passwd')})
    assert 'iddView' not in out['html'], 'معرّف ملف غريب ما يتحوّلش لزرّ'


@needs_node
def test_needs_another_is_refused_in_the_drawer_until_a_reason_is_written():
    out = _idd({'mode': 'wire', 'row': DOC_ROW, 'steps': [{'click': 'no', 'reason': ''}, {'click': 'no', 'reason': 'لا'}, {'click': 'no', 'reason': 'الصورة غير واضحة'}]})
    assert out['decides'] == [['reject', 'الصورة غير واضحة']], 'قرار واحد فقط، وبسببه'
    assert out['msgs'][0] == 'اكتب سبب طلب مستند آخر بوضوح — يقرؤه الخبير كما تكتبه' and out['msgs'][1] == out['msgs'][0]
    assert out['msgs'][2] == 'طُلب من الخبير مستند أوضح.'


@needs_node
def test_verify_sends_no_reason_and_a_failure_unlocks_the_buttons_with_the_reason():
    out = _idd({'mode': 'wire', 'row': DOC_ROW, 'steps': [{'click': 'ok', 'reason': 'ملاحظة كتبها ثم عدل عنها', 'reply': {'ok': False, 'error': 'لا توجد وثيقة محفوظة لهذا الخبير'}}]})
    assert out['decides'] == [['approve', '']] and out['msgs'] == ['لا توجد وثيقة محفوظة لهذا الخبير']
    assert out['disabled'] == {'ok': False, 'no': False}
    out = _idd({'mode': 'wire', 'row': DOC_ROW, 'steps': [{'click': 'ok'}]})
    assert out['msgs'] == ['وُثّقت الهوية.'] and out['disabled'] == {'ok': True, 'no': True}, 'بعد النجاح الأزرار تفضل مقفولة (لا قرار مرتين)'


@needs_node
def test_the_view_button_fetches_the_document_through_the_dashboard_route_only():
    out = _idd({'mode': 'wire', 'row': DOC_ROW, 'steps': [{'click': 'view', 'blob': {'type': 'text/html'}}]})
    assert out['api'] == ['/platform-identity-docs/files/' + FILE_ID]


# ——————————————————————————————————————————————————————— ٥. التوصيل والنصوص
def _strip(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_drawer_is_wired_into_the_inbox_and_the_script_loads_before_the_page_code():
    html = _read('dashboard-cloud', 'index.html')
    assert html.count('<script src="v2s/identity_docs.js"></script>') == 1
    assert html.index('v2s/identity_docs.js') < html.index('<script src="v2s/market.js">'), 'قبل كود الصفحة الداخلي'
    assert "if(i.apiKind==='identity_doc'&&window.V2S_IDENTITY){drawIdentityDoc(el,i);return;}" in html
    assert html.count('function drawIdentityDoc(el,i)') == 1
    js = _read('dashboard-cloud', 'v2s', 'identity_docs.js')
    assert 'data-a=' not in _strip(js), 'الحلقة العامة للدرج تكتب فوق data-a'


def test_the_backend_never_calls_itself_and_has_only_the_three_routes():
    src = _read('backend', 'app.py')
    i = src.index('# R22 — «هوية محفوظة»')
    j = src.index("@app.route('/api/platform-pending-topics'")
    block = src[i:j]
    assert block.count('@app.route(') == 3 and block.count("@roles_required('admin')") == 3 and block.count('@token_required') == 3
    assert 'localhost' not in block and '127.0.0.1' not in block and 'test_client' not in block
    assert block.count('requests.request(') == 1, 'ملف الوثيقة: نداء واحد بلا إعادة محاولة'


def test_visible_copy_is_plain_arabic_without_the_banned_words_or_dot_next_to_digits():
    texts = [_read('dashboard-cloud', 'v2s', 'identity_docs.js')]
    api = _read('dashboard-cloud', 'dashboard-api.js')
    texts.append(api[api.index('R22 — «هوية محفوظة»: وثيقة هوية خبير بانتظار'):api.index('R1 — دفعات محلية')])
    texts.append(api[api.index('R22 — قرار وثيقة الهوية'):api.index('case "trainer":  path')])
    logic = _read('dashboard-cloud', 'v2-logic.js')
    texts.append(logic[logic.index("case 'identity_doc': {"):logic.index("case 'pending_user': {\n        var flags")])
    texts.append(_read('backend', 'app.py').split('# R22 — «هوية محفوظة»')[1].split("@app.route('/api/platform-pending-topics'")[0])
    for t in texts:
        assert 'استشار' not in t
        assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', t), 'لا «·» جنب رقم'
