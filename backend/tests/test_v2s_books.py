# -*- coding: utf-8 -*-
"""«الكتب والأعمال» (قسم «الكتب»، تبويبها الأخير) على الهيكل الجديد، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_books.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/v2s_books_fixtures.BooksPlatform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.
المنطق النقي (الحالة · الممرّات · نص المبيعات · سطور العقل · الفرق قبل ⇒ بعد · البحث) بيتشغّل في node على v2-logic.js.

اللي بيثبّته:
  ١. المسارين الجديدين (pytest): أدمن بس · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` · قايمة بيضا للحقول (لا نص خاص ولا رابط ملف) · حالة المراجعة
     محصورة · ٤٠٤ بتعدّي · ٤٠١/٤٠٣ من المنصة ⇒ ٥٠٢ · التسجيل في app.py سطر واحد قبل العلامة · البحث عن `_platform_proxy` وقت الطلب.
  ٢. المنطق (node): كل حالة وممرّ · ترتيب الممرّات · المصدر الفاشل «غير متاح بعد» لا صفر · حقول المنصة الجديدة تغلب قوائم المراجعة ·
     نص المبيعات بالعربية · سطور العقل ب١–ب٧ بأساسها بالظبط وأولويتها · الفرق قبل ⇒ بعد · إضافة كتاب · رابط المجلد · البحث.
  ٣. الملفات: الأوسمة في index.html · السجلّ `V2SX` · الغلاف مقفول ⇒ لا أثر · لا حفظ في المتصفح · لا نص ممنوع · الأهداف في الـCSS.
"""
import copy
import datetime
import json
import os
import re
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2s_books_fixtures as bfx   # noqa: E402
import v2_node                     # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2books-admin@x.test'
L = v2_node.logic


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------- أدوات

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
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'),
             name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
    db.session.add(u)
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)},
                     flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('v2books-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من `BooksPlatform`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self, **kw):
        self.ef = bfx.BooksPlatform(**kw)
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}),
                          'headers': dict(headers or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        if out is None:
            return _Resp(200, [])
        return _Resp(*out)

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]


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


def _call(ctx, method, path, body=None, role='admin'):
    kw = {'headers': ctx['heads'][role] if role else {}}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


REVIEW = '/api/v2/books/review?status=pending_review'
STORE = '/api/v2/books/store'
ROUTES = [('/api/v2/books/review?status=pending_review', '/api/bridge/knowledge/review'),
          ('/api/v2/books/review?status=rejected', '/api/bridge/knowledge/review'),
          (STORE, '/api/bridge/books/works')]


# ---------------------------------------------------------------- ١) المسارين

@pytest.mark.parametrize('path,_pp', ROUTES)
def test_the_new_routes_are_admin_only(ctx, plat, path, _pp):
    for role in NON_ADMIN_ROLES:
        r = _call(ctx, 'GET', path, role=role)
        assert r.status_code == 403, (role, r.status_code)
    assert _call(ctx, 'GET', path, role=None).status_code == 401
    assert plat.seen == [], 'الرفض لازم يسبق أي نداء للمنصة'


@pytest.mark.parametrize('path,_pp', ROUTES)
def test_the_new_routes_are_closed_when_the_switch_is_off(ctx, plat, monkeypatch, path, _pp):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, 'GET', path)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == []


@pytest.mark.parametrize('path,pp', ROUTES)
def test_reads_pass_through_with_the_secret_and_no_store(ctx, plat, path, pp):
    r = _call(ctx, 'GET', path)
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    c = plat.calls(pp)[-1]
    assert c['method'] == 'GET' and c['headers'].get('X-ELP-Metrics-Secret') == SECRET
    assert len(plat.calls()) == 1, 'نداء واحد بلا إعادة محاولة'


def test_review_status_is_one_of_two_and_checked_before_any_call(ctx, plat):
    for bad in ('', 'published', 'all', 'pending_review;x', 'PENDING_REVIEW'):
        r = _call(ctx, 'GET', '/api/v2/books/review?status=' + bad)
        assert r.status_code == 400 and r.get_json() == {'error': 'حالة غير معروفة'}, bad
        assert r.headers.get('Cache-Control') == 'no-store'
    assert _call(ctx, 'GET', '/api/v2/books/review').status_code == 400
    assert plat.seen == []
    _call(ctx, 'GET', '/api/v2/books/review?status=rejected')
    assert plat.calls('/api/bridge/knowledge/review')[-1]['params'] == {'status': 'rejected'}


def test_review_never_returns_the_private_text_or_the_file_link(ctx, plat):
    plat.ef.items[0]['file_path'] = '/srv/private/a.pdf'
    r = _call(ctx, 'GET', REVIEW)
    body = r.get_json()
    assert body['count'] == 3 and len(body['items']) == 3
    raw = r.get_data(as_text=True)
    for leak in ('material_text', 'file_url', 'file_path', 'pricing', 'owns_it', bfx.SECRET_TEXT, 'files.example.test', '/srv/private'):
        assert leak not in raw, leak
    for it in body['items']:
        assert set(it) <= set(['id', 'slug', 'title', 'type', 'owner_email', 'owner_name', 'rights', 'is_active', 'status', 'created_at', 'updated_at',
                               'review_note', 'total_acquired', 'has_file']), set(it)
    by = {i['id']: i for i in body['items']}
    assert by['kn-1']['has_file'] is True and by['kn-2']['has_file'] is False


def test_has_file_is_false_for_a_blank_link(ctx, plat):
    plat.ef.items[0]['file_url'] = '   \n '
    plat.ef.items[1]['file_url'] = None
    by = {i['id']: i for i in _call(ctx, 'GET', REVIEW).get_json()['items']}
    assert by['kn-1']['has_file'] is False and by['kn-2']['has_file'] is False and by['kn-3']['has_file'] is True


def test_store_is_a_whitelist_of_the_platform_row(ctx, plat):
    plat.ef.store[0]['buyer_emails'] = ['secret@buyer.test']
    plat.ef.store[0]['by_version']['hidden'] = 9
    r = _call(ctx, 'GET', STORE)
    body = r.get_json()
    assert body['count'] == 4 and 'secret@buyer.test' not in r.get_data(as_text=True)
    first = body['items'][0]
    assert set(first) <= set(['slug', 'title', 'source', 'type', 'owner_email', 'owner_name', 'catalog_id', 'offer_id', 'plan', 'plan_label', 'owner_pct',
                              'platform_pct', 'paid_owners', 'owners_total', 'by_version', 'last_sold_at']), set(first)
    assert first['by_version'] == {'read': 3, 'pdf': 2} and first['paid_owners'] == 5


def test_store_404_passes_through_as_404_so_the_screen_says_not_available_yet(ctx, plat):
    plat.ef.works_bridge = False
    r = _call(ctx, 'GET', STORE)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert set(r.get_json()) == {'error'}


@pytest.mark.parametrize('status', [401, 403])
@pytest.mark.parametrize('path,pp', [(REVIEW, '/api/bridge/knowledge/review'), (STORE, '/api/bridge/books/works')])
def test_a_platform_401_or_403_never_logs_the_admin_out(ctx, plat, path, pp, status):
    plat.ef.forced[('GET', pp)] = (status, {'detail': 'secret rejected'})
    r = _call(ctx, 'GET', path)
    assert r.status_code == 502 and r.get_json() == {'error': 'تعذّر الاتصال بالمنصة'} and r.headers.get('Cache-Control') == 'no-store'


def test_a_platform_error_is_its_status_and_only_an_error_message(ctx, plat):
    plat.ef.forced[('GET', '/api/bridge/books/works')] = (500, {'detail': 'boom', 'trace': 'SECRET-TRACE'})
    r = _call(ctx, 'GET', STORE)
    assert r.status_code == 500 and set(r.get_json()) == {'error'} and 'SECRET-TRACE' not in r.get_data(as_text=True)
    assert r.headers.get('Cache-Control') == 'no-store'
    plat.ef.forced[('GET', '/api/bridge/knowledge/review')] = (200, {'unexpected': True})
    r2 = _call(ctx, 'GET', REVIEW)
    assert r2.status_code == 502 and set(r2.get_json()) == {'error'}, 'شكل غير مفهوم ⇒ خطأ لا قايمة فاضية'


def test_registration_is_one_line_before_the_marker():
    # يخصّ هذا القسم وحده: سطره موجود مرة واحدة وقبل علامة نهاية المسارات. بعد دمج الأقسام سيجاوره سطر كل قسم آخر، ولا يهمّه ذلك.
    src = _read('backend', 'app.py')
    marker = '# ---- v2 section routes end'
    line = "__import__('v2_books_routes').register(app, globals())"
    assert src.count(marker) >= 1 and src.count(line) == 1
    assert src.index(line) < src.index(marker)
    assert src.index(marker) < src.index("@app.route('/api/platform-pnl'")
    assert src.index("def v2_book_request_patch") < src.index(line)
    block = src[src.index(line):src.index(marker)]
    assert all(ln.strip() == '' or 'v2_' in ln and 'register' in ln and '(app' in ln or ln.lstrip().startswith('#') for ln in block.split('\n')), \
        'بين سطر الكتب والعلامة سطور تسجيل أقسام أخرى فقط'


def test_the_proxy_is_looked_up_at_request_time_not_at_registration(ctx, plat, monkeypatch):
    import app as appmod
    seen = []

    def fake(method, path, params=None, json_body=None, timeout=12):
        seen.append((method, path, params))
        return appmod.jsonify({'items': []})
    monkeypatch.setattr(appmod, '_platform_proxy', fake)
    r = _call(ctx, 'GET', REVIEW)
    assert r.status_code == 200 and r.get_json() == {'items': [], 'count': 0}
    assert seen == [('GET', '/api/bridge/knowledge/review', {'status': 'pending_review'})]
    assert plat.seen == []


def test_the_existing_write_routes_the_screen_calls_still_behave(ctx, plat):
    ef = plat.ef
    r = _call(ctx, 'PUT', '/api/platform-knowledge/kn-4', {'title': 'عنوان جديد', 'price_egp': 275.5, 'bid_enabled': True, 'junk': 'x'})
    assert r.status_code == 200
    sent = plat.calls('/api/bridge/knowledge/kn-4')[-1]['json']
    assert sent == {'title': 'عنوان جديد', 'price_egp': 275.5, 'bid_enabled': True}
    assert ef.items[3]['pricing']['eg']['amount'] == 275.5
    assert _call(ctx, 'PUT', '/api/platform-knowledge/kn-4', {}).status_code == 400
    r = _call(ctx, 'POST', '/api/platform-knowledge/kn-1/decide', {'decision': 'approve', 'admin_note': ''})
    assert r.status_code == 200 and ef.items[0]['status'] == 'published'
    assert plat.calls('/api/bridge/knowledge/kn-1/decide')[-1]['json'] == {'decision': 'approve', 'note': ''}
    assert _call(ctx, 'POST', '/api/platform-knowledge/kn-1/decide', {'decision': 'approve'}).status_code == 409
    assert _call(ctx, 'POST', '/api/platform-knowledge/kn-2/decide', {'decision': 'approve'}).status_code == 422
    assert _call(ctx, 'POST', '/api/platform-knowledge/kn-2/decide', {'decision': 'later'}).status_code == 400
    r = _call(ctx, 'POST', '/api/platform-books', {'title': 'دليل', 'file_url': 'https://x.test/a.pdf', 'price': 90, 'currency': 'USD', 'is_active': True, 'junk': 1})
    assert r.status_code == 200
    assert plat.calls('/api/bridge/books')[-1]['json'] == {'title': 'دليل', 'author': '', 'description': '', 'price': 90.0, 'currency': 'USD',
                                                           'file_url': 'https://x.test/a.pdf', 'cover_url': '', 'is_active': True}
    r = _call(ctx, 'POST', '/api/platform-library/ingest-folder', {'folder_id': '1AbCdEfGhIjKl', 'category': 'law', 'max_files': 40})
    assert r.status_code == 200 and r.get_json()['ingested'] == 5
    assert plat.calls('/api/bridge/library/ingest-drive-folder')[-1]['json'] == {'folder_id': '1AbCdEfGhIjKl', 'category': 'law', 'country': 'egypt', 'max_files': 40}


# ---------------------------------------------------------------- ٢) المنطق (node)

NOW_MS = int(bfx.d3fx.fx._NOW.timestamp() * 1000)
HOUR = 3600e3
DAY = 24 * HOUR


def _get(ef, path, params=None):
    status, body = ef.handle('GET', path, params or {}, {})
    assert status == 200, (path, status)
    return body


def _src(p1=True, **over):
    """ردود المصادر كما تصل الواجهة: قوائم المراجعة بعد القايمة البيضا في المسار الجديد."""
    ef = bfx.BooksPlatform(p1=p1)
    import v2_books_routes as vb

    def review(status):
        rows = _get(ef, '/api/bridge/knowledge/review', {'status': status})['items']
        items = [vb._review_item(r) for r in rows]
        return {'items': items, 'count': len(items)}
    src = {'knowledge': _get(ef, '/api/bridge/knowledge'), 'revPending': review('pending_review'), 'revRejected': review('rejected'),
           'prices': _get(ef, '/api/bridge/prices/book'), 'offers': _get(ef, '/api/bridge/book-offers', {'status': 'all'}),
           'store': {'items': _get(ef, '/api/bridge/books/works')['items'], 'count': 4}}
    src.update(over)
    return src


def W(src=None, now=NOW_MS, **kw):
    return L('v2kWorks', src if src is not None else _src(**kw), now)


def _rowmap(res):
    return {r['key']: r for r in res['rows']}


@needs_node
def test_each_work_gets_its_status_lane_and_the_lanes_are_in_the_fixed_order():
    res = W()
    by = _rowmap(res)
    assert res['lanes']['review'] == ['kn:kn-2', 'kn:kn-1', 'kn:kn-3'], 'الأقدم أولًا'
    assert res['lanes']['noprice'] == ['st:bk-new']
    assert res['lanes']['hiddenSold'] == ['kn:kn-7'], 'المخفي الذي بيع منه ممرّ لوحده لا «مخفي»'
    assert 'kn:kn-7' not in res['lanes']['hidden'] and set(res['lanes']['hidden']) == {'kn:kn-8', 'st:bk-hidden'}
    assert res['lanes']['live'][0] == 'kn:kn-6', 'الأكثر مبيعًا أولًا (٣١ نسخة مجانية)'
    assert res['lanes']['live'][1:3] == ['kn:kn-4', 'st:bk-tenant-guide']
    assert res['lanes']['rejected'] == ['of:off-12', 'kn:kn-9'], 'الأحدث قرارًا أولًا (العرض قبل يومين، والعمل قبل ثلاثة)'
    assert res['lanes']['unknown'] == []
    assert res['counts'] == {k: len(v) for k, v in res['lanes'].items()}
    assert by['kn:kn-1']['statusText'] == 'في المراجعة' and by['kn:kn-4']['statusText'] == 'ظاهر للناس' and by['kn:kn-8']['statusText'] == 'مخفي'
    assert by['st:bk-new']['statusText'] == 'بلا سعر' and by['kn:kn-9']['statusText'] == 'مرفوض'
    assert res['partial'] == {k: False for k in res['partial']} and res['failed'] == [] and res['storeClosed'] is False


@needs_node
def test_offers_in_review_draft_and_live_are_never_rows_and_rejected_offers_are():
    res = W()
    keys = [r['key'] for r in res['rows']]
    assert not [k for k in keys if k.startswith('of:') and k != 'of:off-12']
    assert res['offersWaiting'] == 2, 'عدّاد عروض «مراجعة العروض» بس'
    off = _rowmap(res)['of:off-12']
    assert off['kind'] == 'offer' and off['reviewNote'] == 'الموضوع خارج تخصص المنصة' and off['priceText'] == '٢٠٠ جنيه' and off['salesText'] == ''
    assert off['agreementText'] == 'النشر على المنصة: صاحب العمل ٦٠٪ · المنصة ٤٠٪'
    assert len(keys) == len(set(keys))


@needs_node
def test_a_store_book_takes_its_owner_from_the_store_and_falls_back_to_the_live_offer():
    by = _rowmap(W())
    assert by['st:bk-tenant-guide']['ownerName'] == 'أ. نادية فؤاد' and by['st:bk-tenant-guide']['catalogId'] == 'bk-tenant-guide'
    assert by['st:bk-startup-law']['agreementText'] == 'كتاب من البروفيسور' and by['st:bk-startup-law']['ownerName'] == 'البروفيسور'
    assert by['st:bk-tenant-guide']['agreementText'] == 'النشر مع إعلانات على حسابك: صاحب العمل ٦٥٪ · المنصة ٣٥٪'
    closed = _rowmap(W(store='closed'))
    assert closed['st:bk-tenant-guide']['ownerName'] == 'أ. نادية فؤاد', 'الجسر غير مبني ⇒ من العرض الحي'
    assert closed['st:bk-tenant-guide']['agreementText'] == 'النشر مع إعلانات على حسابك: صاحب العمل ٦٥٪ · المنصة ٣٥٪'
    assert closed['st:bk-hidden']['ownerNA'] is True and closed['st:bk-hidden']['ownerName'] == '', 'لا مصدر ⇒ «غير متاح بعد» لا «البروفيسور»'
    assert closed['st:bk-labor']['catalogId'] == 'bk-labor'


@needs_node
def test_a_failed_source_is_never_a_zero_and_never_an_empty_list():
    res = W(_src(store=None))
    assert res['failed'] == ['بيانات المتجر']
    for k in ('st:bk-tenant-guide', 'st:bk-startup-law', 'st:bk-labor', 'st:bk-hidden', 'st:bk-new'):
        r = _rowmap(res)[k]
        assert r['salesText'] == 'المبيعات: غير متاح بعد' and r['sold'] is None and r['salesNA'] is True and r['salesSub'] == ''
    res = W(_src(p1=False, revPending=None))
    by = _rowmap(res)
    assert res['partial']['review'] is True and 'حالة المراجعة' in res['failed']
    assert by['kn:kn-1']['status'] == 'unknown' and by['kn:kn-1']['statusText'] == 'الحالة: غير متاح بعد' and by['kn:kn-1']['lane'] == 'unknown'
    assert by['kn:kn-9']['status'] == 'rejected', 'ما وصلت قائمته يُعرف من الأخرى'
    assert by['kn:kn-4']['status'] == 'unknown'
    assert res['partial']['live'] is True and res['partial']['hiddenSold'] is True and res['partial']['rejected'] is False
    res = W(_src(offers=None))
    assert res['offersWaiting'] is None and res['failed'] == ['عروض الكتب'] and res['partial']['rejected'] is True
    assert 'of:off-12' not in _rowmap(res)
    res = W(_src(knowledge=None))
    assert res['failed'] == ['أعمال السوق'] and res['partial']['review'] is True
    assert 'kn:kn-1' in _rowmap(res), 'عمل ينتظر قرارًا يبقى ظاهرًا من قايمة المراجعة'
    assert W(_src(knowledge=None, prices=None, offers=None)) is None
    assert W(_src(knowledge=None, prices='closed', offers='closed')) is None, 'لا شيء وصل ولا المتجر مفتوح'
    r = W(_src(prices='closed', offers='closed', store='closed'))
    assert r['storeClosed'] is True and r['failed'] == [] and not [x for x in r['rows'] if x['kind'] != 'market'] and r['offersWaiting'] is None


@needs_node
def test_the_platforms_new_fields_win_over_the_review_lists_when_they_disagree():
    src = _src(p1=True)
    src['revPending'] = {'items': [], 'count': 0}
    src['revRejected'] = {'items': [{'id': 'kn-4'}], 'count': 1}
    res = W(src)
    by = _rowmap(res)
    assert by['kn:kn-1']['status'] == 'review' and by['kn:kn-4']['status'] == 'live', 'حالة المنصة هي الحكم'
    assert by['kn:kn-1']['createdAt'] is not None and by['kn:kn-1']['hasFile'] is True and by['kn:kn-2']['hasFile'] is False
    src = _src(p1=True, revPending=None, revRejected=None)
    r = W(src)
    assert r['failed'] == [] and r['partial']['review'] is False, 'مع الحقول الجديدة لا نحتاج قوائم المراجعة أصلًا'


@needs_node
def test_without_the_new_fields_a_work_for_sale_has_no_agreement_and_no_split_claim():
    by = _rowmap(W(_src(p1=False)))
    r = by['kn:kn-4']
    assert r['agreementText'] == 'غير متاح بعد' and r['legacySplit'] is None and r['platformPct'] is None and r['brain'] is None
    assert by['kn:kn-6']['agreementText'] == 'مجاني، لا بيع فيه'
    assert by['kn:kn-1']['createdAt'] is not None and by['kn:kn-1']['status'] == 'review', 'المراجعة تعطي التاريخ والملف'
    assert by['kn:kn-4']['createdAt'] is None and by['kn:kn-4']['createdText'] == '' and by['kn:kn-4']['hasFile'] is None
    p1 = _rowmap(W(_src(p1=True)))['kn:kn-4']
    assert p1['legacySplit'] is True and p1['platformPct'] == 20
    assert p1['agreementText'] == 'صاحب العمل ٨٠٪ · المنصة ٢٠٪ — النسبة القديمة، إلى أن يُنقل إلى قائمة الأسعار الموحّدة'
    assert p1['priceText'] == '٢٥٠ جنيه' and _rowmap(W())['kn:kn-6']['priceText'] == 'مجاني للجميع'


@needs_node
def test_sales_wording_is_arabic_plural_and_a_real_zero_is_a_sentence():
    def sale(n, rights='owned_for_sale'):
        src = _src()
        k = src['knowledge']['items'][3]
        k['rights'], k['total_acquired'] = rights, n
        return _rowmap(W(src))['kn:kn-4']['salesText']
    assert [sale(n) for n in (0, 1, 2, 3, 11, 100)] == ['لم تُبع منه نسخة بعد', 'بيعت منه نسخة واحدة', 'بيعت منه نسختان', 'بيعت منه ٣ نسخ', 'بيعت منه ١١ نسخة', 'بيعت منه ١٠٠ نسخة']
    assert [sale(n, 'public_domain_feed') for n in (0, 1, 2, 3, 11)] == ['لم يأخذه أحد بعد', 'نسخة واحدة مجانية', 'نسختان مجانيتان', '٣ نسخ مجانية', '١١ نسخة مجانية']
    assert not re.search(r'[0-9]', ' '.join(sale(n) for n in (0, 1, 2, 7, 100)))

    def store(paid, bv):
        src = _src()
        src['store']['items'][0].update({'paid_owners': paid, 'by_version': bv})
        r = _rowmap(W(src))['st:bk-tenant-guide']
        return r['salesText'], r['salesSub']
    assert store(5, {'read': 3, 'pdf': 2}) == ('بيعت منه ٥ نسخ', 'منها ٣ نسخ للقراءة على المنصة ونسختان للتحميل')
    assert store(4, {'read': 1, 'pdf': 3}) == ('بيعت منه ٤ نسخ', 'منها نسخة واحدة للقراءة على المنصة و٣ نسخ للتحميل')
    assert store(3, {'read': 3, 'pdf': 0}) == ('بيعت منه ٣ نسخ', 'منها ٣ نسخ للقراءة على المنصة ولا نسخة للتحميل')
    assert store(2, {'read': 0, 'pdf': 2}) == ('بيعت منه نسختان', 'منها نسختان للتحميل ولا نسخة للقراءة على المنصة')
    assert store(0, {'read': 0, 'pdf': 0}) == ('لم تُبع منه نسخة بعد', '') and store(1, None)[1] == ''
    for t in store(5, {'read': 3, 'pdf': 2}):
        assert 'PDF' not in t and not re.search(r'[0-9]', t)


@needs_node
def test_brain_lines_fire_on_their_exact_basis_and_not_without_it():
    def line(row, now=NOW_MS):
        r = L('v2kBrainLine', row, now)
        return r and (r['id'], r['text'], r['action'])
    base = {'kind': 'market', 'status': 'review', 'forSale': True, 'hasFile': True, 'sold': 0, 'createdAt': NOW_MS - 30 * HOUR, 'legacySplit': None, 'platformPct': None}
    assert line(dict(base, hasFile=False)) == ('B1', 'لا يوجد ملف مرفق، والمنصة لا تنشر عملًا للبيع بلا ملف.', 'reject')
    assert line(dict(base, hasFile=None))[0] == 'B2', 'الملف مجهول ⇒ لا ادّعاء بأنه ناقص'
    assert line(dict(base, forSale=False, hasFile=False))[0] == 'B2', 'عمل مجاني بلا ملف لا يمسّه سطر الملف'
    assert line(dict(base)) == ('B2', 'ينتظر المراجعة منذ يوم.', 'approve')
    assert line(dict(base, createdAt=None)) is None
    b5 = dict(base, status='hidden', sold=4)
    assert line(b5) == ('B5', 'مخفي الآن. بيعت منه ٤ نسخ، ولا يستطيع أصحابها تحميلها ما دام مخفيًا.', 'show')
    assert line(dict(b5, sold=0)) is None and line(dict(b5, forSale=False)) is None
    assert line({'kind': 'store', 'status': 'noprice'}) == ('B3', 'لا سعر لهذا الكتاب بعد، فهو غير معروض للبيع.', 'price')
    assert line({'kind': 'store', 'status': 'hidden'}) == ('B4', 'له أسعار، لكنه مخفي عن الناس.', 'price')
    assert line({'kind': 'store', 'status': 'live'}) is None
    live = dict(base, status='live', sold=3, legacySplit=True, platformPct=20)
    assert line(live) == ('B7', 'يُباع بالنسبة القديمة (المنصة ٢٠٪، أقل من الحد ٣٥٪) إلى أن يُنقل إلى قائمة الأسعار الموحّدة.', None)
    assert line(dict(live, platformPct=35)) is None and line(dict(live, platformPct=36)) is None
    assert line(dict(live, legacySplit=None)) is None and line(dict(live, legacySplit=False)) is None and line(dict(live, platformPct=None)) is None
    assert line(dict(live, status='hidden', sold=0)) is not None and line(dict(live, status='hidden', sold=0))[0] == 'B7'
    b6 = dict(base, status='live', sold=0)
    assert line(dict(b6, createdAt=NOW_MS - 29 * DAY)) is None
    assert line(dict(b6, createdAt=NOW_MS - 30 * DAY)) == ('B6', 'لم تُبع منه نسخة منذ أُضيف قبل ٣٠ يومًا.', None)
    assert line(dict(b6, createdAt=None)) is None and line(dict(b6, sold=1, createdAt=NOW_MS - 90 * DAY)) is None and line(dict(b6, sold=None, createdAt=NOW_MS - 90 * DAY)) is None
    # الأولوية: ب١ > ب٥ > ب٣ > ب٤ > ب٢ > ب٧ > ب٦
    assert line(dict(base, status='live', sold=0, legacySplit=True, platformPct=20, createdAt=NOW_MS - 90 * DAY))[0] == 'B7'
    assert line(dict(base, hasFile=False, status='review', legacySplit=True, platformPct=20))[0] == 'B1'
    res = W()
    by = _rowmap(res)
    assert by['kn:kn-2']['brain']['id'] == 'B1' and by['kn:kn-1']['brain']['id'] == 'B2' and by['kn:kn-7']['brain']['id'] == 'B5'
    assert by['st:bk-new']['brain']['id'] == 'B3' and by['st:bk-hidden']['brain']['id'] == 'B4' and by['kn:kn-4']['brain']['id'] == 'B7'
    assert by['kn:kn-5']['brain']['id'] == 'B7', 'ب٧ قبل ب٦'
    assert by['kn:kn-6']['brain'] is None and by['kn:kn-9']['brain'] is None


@needs_node
def test_brain_summary_counts_market_works_only_and_has_one_action():
    res = W()
    s = L('v2kBrainSummary', res)
    assert s['text'] == 'في انتظار مراجعتك: ٣ أعمال من السوق · بلا سعر: كتاب واحد · مخفي وبيعت منه نسخ: عمل واحد'
    assert s['action'] == {'label': 'ابدأ المراجعة', 'lane': 'review'}, 'العرضان في «مراجعة العروض» لا يُعدّان هنا'
    no_review = _src()
    no_review['knowledge']['items'] = [k for k in no_review['knowledge']['items'] if k['status'] != 'pending_review']
    no_review['revPending'] = {'items': [], 'count': 0}
    s = L('v2kBrainSummary', W(no_review))
    assert s['action'] == {'label': 'اعرض الكتب بلا سعر', 'lane': 'noprice'} and s['text'].startswith('بلا سعر: كتاب واحد')
    quiet = _src()
    quiet['knowledge']['items'] = [k for k in quiet['knowledge']['items'] if k['status'] == 'published' and k['id'] not in ('kn-7',)]
    quiet['prices']['items'] = [p for p in quiet['prices']['items'] if p['id'] != 'bk-new']
    quiet['revPending'] = {'items': [], 'count': 0}
    s = L('v2kBrainSummary', W(quiet))
    assert s == {'text': 'لا شيء ينتظرك في الكتب والأعمال الآن.', 'action': None}
    s = L('v2kBrainSummary', W(_src(p1=False, revPending=None)))
    assert s['text'].endswith(' — وبعض المصادر لم تصل، فقد يكون العدد أكبر') and s['action']['lane'] == 'noprice'
    s = L('v2kBrainSummary', W(_src(prices=None)))
    assert s['text'].endswith('فقد يكون العدد أكبر')


@needs_node
def test_the_summary_other_sections_read_never_invents_an_unknown():
    s = L('v2kSummary', W())
    assert s == {'review': 3, 'noprice': 1, 'hiddenSold': 1, 'legacySplit': 6, 'offersWaiting': 2, 'partial': False}
    s = L('v2kSummary', W(_src(p1=False)))
    assert s['legacySplit'] is None, 'ما نعرفش النسبة ⇒ لا رقم'
    s = L('v2kSummary', W(_src(p1=False, revPending=None)))
    assert s['review'] is None and s['hiddenSold'] is None and s['partial'] is True
    assert L('v2kSummary', None)['review'] is None


@needs_node
def test_search_is_arabic_normalised_over_title_and_owner_and_drops_empty_lanes():
    assert L('v2kKey', 'إِدارةُ المَدرسةِ ١٢٣') == 'اداره المدرسه 123'
    assert L('v2kKey', 'أ إ آ ا ة ه ى ي') == 'ا ا ا ا ه ه ي ي' and L('v2kKey', '۱۲٣') == '123'
    assert L('v2kKey', None) == '' and L('v2kKey', '  \n ') == ''
    res = W()
    lanes = L('v2kSearch', res, 'دليل')
    assert set(lanes) == {'review', 'noprice', 'hiddenSold', 'live'}, 'ممرّ بلا تطابق يسقط'
    assert lanes['review'] == ['kn:kn-1'] and 'st:bk-tenant-guide' in lanes['live']
    assert list(L('v2kSearch', res, 'اداره')) == ['live'] or L('v2kSearch', res, 'اداره') == {}
    assert L('v2kSearch', res, 'كريم') == {'review': ['kn:kn-2']}, 'اسم صاحب العمل'
    assert L('v2kSearch', res, 'نادية')['live'] == ['st:bk-tenant-guide']
    assert L('v2kSearch', res, 'zzz-none') == {} and L('v2kSearch', res, '') == res['lanes'] and L('v2kSearch', res, '   ') == res['lanes']
    assert L('v2kSearch', res, 'الشركات') != {} and L('v2kSearch', res, 'الشركه') == L('v2kSearch', res, 'الشركة'), 'ة = ه'


@needs_node
def test_edit_diff_shows_only_what_changes_and_sends_only_what_changed():
    row = _rowmap(W())['kn:kn-4']
    base = {'title': row['title'], 'priceText': '250', 'bid': False}
    d = L('v2kEditDiff', row, base)
    assert d['ok'] and d['changed'] is False and d['lines'] == [] and d['body'] == {}
    d = L('v2kEditDiff', row, dict(base, title='عنوان جديد'))
    assert d['changed'] and d['body'] == {'title': 'عنوان جديد'} and d['lines'] == [{'label': 'العنوان', 'from': row['title'], 'to': 'عنوان جديد'}]
    d = L('v2kEditDiff', row, dict(base, priceText='١٥٠٫٥'))
    assert d['body'] == {'price_egp': 150.5} and d['lines'] == [{'label': 'السعر', 'from': '٢٥٠ جنيه', 'to': '١٥٠٫٥ جنيه'}]
    d = L('v2kEditDiff', row, dict(base, bid=True))
    assert d['body'] == {'bid_enabled': True} and d['lines'] == [{'label': '«اعرض سعرك»', 'from': 'غير مفعّل', 'to': 'مفعّل'}]
    d = L('v2kEditDiff', row, {'title': '  عنوان  ', 'priceText': '300', 'bid': True})
    assert d['body'] == {'title': 'عنوان', 'price_egp': 300, 'bid_enabled': True} and len(d['lines']) == 3
    for bad in ('abc', '', '12.345', '-5', '١٢،٥٠'):
        r = L('v2kEditDiff', row, dict(base, priceText=bad))
        assert r['ok'] is False and 'السعر' in r['error'], bad
    assert L('v2kEditDiff', row, dict(base, priceText='0'))['ok'] is False
    assert L('v2kEditDiff', row, dict(base, title='  '))['error'] == 'اكتب عنوان العمل'
    free = _rowmap(W())['kn:kn-6']
    d = L('v2kEditDiff', free, {'title': 'عنوان آخر', 'priceText': 'abc', 'bid': True})
    assert d['ok'] and d['body'] == {'title': 'عنوان آخر'}, 'العمل المجاني بلا سعر ولا «اعرض سعرك»'


@needs_node
def test_a_for_sale_work_with_an_unknown_price_can_still_change_its_title_and_bid():
    row = dict(_rowmap(W())['kn:kn-4'], priceAmount=None, priceText='غير متاح بعد')
    assert row['forSale'] is True
    d = L('v2kEditDiff', row, {'title': 'عنوان جديد', 'priceText': '', 'bid': True})
    assert d['ok'] and d['body'] == {'title': 'عنوان جديد', 'bid_enabled': True} and [x['label'] for x in d['lines']] == ['العنوان', '«اعرض سعرك»']
    d = L('v2kEditDiff', row, {'title': row['title'], 'priceText': '', 'bid': bool(row['bid'])})
    assert d['ok'] and d['changed'] is False
    d = L('v2kEditDiff', row, {'title': row['title'], 'priceText': '120', 'bid': bool(row['bid'])})
    assert d['body'] == {'price_egp': 120} and d['lines'][0]['from'] == 'غير متاح بعد'
    for bad in ('abc', '0', '-3'):
        assert L('v2kEditDiff', row, {'title': row['title'], 'priceText': bad, 'bid': False})['ok'] is False, bad


@needs_node
def test_a_decimal_amount_uses_the_arabic_decimal_mark_never_a_latin_comma():
    row = _rowmap(W())['kn:kn-4']
    d = L('v2kEditDiff', row, {'title': row['title'], 'priceText': '299.5', 'bid': bool(row['bid'])})
    to = d['lines'][0]['to']
    assert '\u066b' in to and ',' not in to and '.' not in to, to


@needs_node
def test_add_book_builds_exactly_the_eight_fields_the_endpoint_takes():
    ok = {'title': ' دليل ', 'author': ' أ ', 'description': 'وصف', 'priceText': '١٢٠', 'currency': 'USD', 'fileUrl': 'https://x.test/a.pdf', 'coverUrl': '', 'active': True}
    r = L('v2kAddBook', ok)
    assert r['ok'] and r['body'] == {'title': 'دليل', 'author': 'أ', 'description': 'وصف', 'price': 120, 'currency': 'USD', 'file_url': 'https://x.test/a.pdf', 'cover_url': '', 'is_active': True}
    assert L('v2kAddBook', dict(ok, priceText=''))['body']['price'] == 0 and L('v2kAddBook', dict(ok, priceText='٠'))['body']['price'] == 0
    assert L('v2kAddBook', dict(ok, currency='SAR'))['body']['currency'] == 'EGP' and L('v2kAddBook', dict(ok, active=False))['body']['is_active'] is False
    assert L('v2kAddBook', dict(ok, title=' '))['error'] == 'اكتب عنوان الكتاب'
    for bad in ('', 'http://x.test/a.pdf', 'ftp://x', 'x.test/a.pdf', 'https://', 'https://a b'):
        r = L('v2kAddBook', dict(ok, fileUrl=bad))
        assert r['ok'] is False and 'يبدأ بـ' in r['error'] and 'https://' in r['error'], bad
    assert L('v2kAddBook', dict(ok, priceText='abc'))['ok'] is False and L('v2kAddBook', dict(ok, coverUrl='http://c.test/c.jpg'))['ok'] is False
    assert L('v2kAddBook', dict(ok, coverUrl='https://c.test/c.jpg'))['body']['cover_url'] == 'https://c.test/c.jpg'
    long = L('v2kAddBook', dict(ok, title='ع' * 400, description='و' * 3000))['body']
    assert len(long['title']) == 300 and len(long['description']) == 2000


@needs_node
def test_a_drive_folder_id_comes_from_a_link_or_a_bare_id_and_never_from_garbage():
    fid = '1AbCdEfGhIjKlMnOp'
    for text in ('https://drive.google.com/drive/folders/%s' % fid, 'https://drive.google.com/drive/folders/%s?usp=sharing' % fid,
                 'https://drive.google.com/drive/u/0/folders/%s?hl=ar' % fid, 'https://drive.google.com/open?id=%s' % fid, '  %s  ' % fid):
        assert L('v2kFolderId', text) == fid, text
    for bad in ('', 'مجلد', 'short', 'https://example.com/x', 'a b c d e f g h i j k', None):
        assert L('v2kFolderId', bad) == '', bad


@needs_node
def test_the_hide_warning_is_only_for_a_work_for_sale_that_was_sold():
    by = _rowmap(W())
    assert L('v2kHideWarning', by['kn:kn-4']) == 'بيعت منه ١٢ نسخة، ومن اشتراه لا يستطيع تحميله ما دام مخفيًا.'
    assert L('v2kHideWarning', by['kn:kn-5']) == '' and L('v2kHideWarning', by['kn:kn-6']) == '' and L('v2kHideWarning', by['st:bk-labor']) == ''


@needs_node
def test_every_visible_string_the_helpers_return_is_plain_arabic():
    texts = []
    for p1 in (True, False):
        for res in (W(_src(p1=p1)), W(_src(p1=p1, store=None, revPending=None)), W(_src(offers=None))):
            for r in res['rows']:
                texts += [r['title'], r['typeText'], r['statusText'], r['salesText'], r['salesSub'], r['agreementText'], r['priceText'], r['createdText'], r['reviewNote']]
                texts += [(r['brain'] or {}).get('text', '')]
            texts += res['failed'] + [L('v2kBrainSummary', res)['text']]
    for row in _rowmap(W()).values():
        texts += [(L('v2kBrainLine', dict(row, status=s, hasFile=h, sold=n, createdAt=NOW_MS - 40 * DAY), NOW_MS) or {}).get('text', '')
                  for s in ('review', 'hidden', 'live', 'noprice') for h in (True, False) for n in (0, 1, 7)]
    banned = ['يقوّم', 'يقوم بتقييم', 'API', 'ID', 'RAG', 'OCR', 'PDF', 'Folder', 'bridge', 'null', 'undefined', 'NaN', 'الذكاء الاصطناعي', 'طابور', 'JSON']
    for t in texts:
        for bad in banned:
            assert bad not in t, (bad, t)
        assert not re.match(r'^\s*(ذكاء|الذكاء|AI)\b', t), t
        if t.startswith('مكتبة') or not t:
            continue
        assert not re.search(r'[0-9]', t), t


# ---------------------------------------------------------------- ٣) الملفات والأقسام

DC = os.path.join(ROOT, 'dashboard-cloud')


def _strip_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_files_are_wired_in_the_sections_block_and_shipped():
    html = _read('dashboard-cloud', 'index.html')
    begin, end = '<!-- v2 sections begin -->', '<!-- v2 sections end -->'
    assert html.count(begin) == 1 and html.count(end) == 1
    block = html[html.index(begin):html.index(end)]
    assert '<link rel="stylesheet" href="v2s/books.css">' in block and '<script src="v2s/books.js"></script>' in block
    assert html.index('v2-d2.js') < html.index('v2-d3.js') < html.index(begin) < html.index(end), 'بعد الدمج: كتلة الأقسام بعد v2-d3 (كل الأقسام في كتلة واحدة)'
    refs = re.findall(r'(?:href|src)="(v2s/[^"]+)"', block)
    assert refs.count('v2s/books.css') == 1 and refs.count('v2s/books.js') == 1, refs
    assert refs.index('v2s/books.css') < refs.index('v2s/books.js'), 'الأنماط قبل السكربت'
    keys = [re.match(r'v2s/([a-z0-9_-]+)\.', r).group(1) for r in refs]
    assert keys == sorted(keys), 'الكتلة مرتّبة أبجديًا بمفتاح القسم'
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        txt = _read(df)
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in txt and 'COPY backend/v2_books_routes.py /app/v2_books_routes.py' in txt, df   # بعد الدمج: سطر صريح لكل قسم (لا نمط عام)
        assert txt.index('COPY backend/app.py /app/app.py') < txt.index('COPY backend/v2_books_routes.py /app/v2_books_routes.py')
    for f in ('v2s/books.js', 'v2s/books.css'):
        assert os.path.getsize(os.path.join(DC, f)) > 5000
    assert re.search(r'v2s/\[a-z0-9_-\]\+\\\.js', _read('backend', 'tests', 'test_xss_hardening.py')), 'قايمة السكربتات المسموحة تقبل v2s/<مفتاح>.js'


def test_the_dispatch_line_is_there_once_right_after_the_d3_line_and_the_old_screen_stays():
    html = _read('dashboard-cloud', 'index.html')
    d3 = "  if(window.V2_ON&&window.V2D3&&V2D3.owns(current))return V2D3.render(current,v);\n"
    # بعد الدمج: خطّاف واحد موحّد (V2SEC.owner) بعد سطر D3 مباشرة (بعد سطر تعليقه)، والكتب مسجَّلة فيه بمفتاحها
    assert html.count(d3) == 1 and html.count('const _s=V2SEC.owner(current)') == 1
    assert html.index(d3) < html.index('const _s=V2SEC.owner(current)') < html.index('if(MODULES_LOOKUP[current]&&MODULES_LOOKUP[current].soon)')
    assert '.books = { owns: function (m) { return R.owns(m); }' in _read('dashboard-cloud', 'v2s', 'books.js')
    assert 'function viewKnowledge(v){' in html and 'function addBookModal(){' in html and 'function knowledgeEditModal(k){' in html, 'مسار المفتاح المقفول'
    mods = html[html.index('const MODULES={'):html.index('// موديولات الأدوار غير-الأدمن')]
    assert 'v2s' not in mods and 'V2SX' not in mods


@needs_node
def test_the_books_section_tabs_are_unchanged_and_the_description_is_the_new_text():
    secs = {s['key']: s for s in L('SECTIONS')}
    books = secs['books']
    assert [(t['key'], t['label'], t['mod']) for t in books['tabs']] == [('offers', 'مراجعة العروض', 'v2b_offers'), ('requests', 'طلبات القرّاء', 'v2b_requests'),
                                                                        ('books', 'الكتب والأعمال', 'knowledge')]
    assert books['desc'] == 'كل كتاب وعمل، وعروض تنتظر المراجعة، وطلبات القرّاء' and books['img'] == 'books'
    assert not [t for t in books['tabs'] if 'كل السجلات' in t['label']], 'لا «كل السجلات»: كل ما في الشاشة القديمة له بيت جديد'
    land = L('sectionFor', 'knowledge', {})
    assert (land['section'], land['tab']) == ('books', 'books')


def _node_registry(shell_on):
    """يحمّل v2s/books.js في node بنافذة مزيّفة ويرجّع نتيجة `V2SX.owns('knowledge')`."""
    import subprocess
    script = """
const fs=require('fs'),path=require('path');
const L=require(%s);
global.window=global; global.V2L=L; global.document={getElementById:()=>null,querySelector:()=>null,querySelectorAll:()=>[],body:{contains:()=>false}};
global.addEventListener=()=>{}; global.setInterval=()=>0; global.history={}; global.location={hash:''};
global.V2SHELL=%s;
eval(fs.readFileSync(%s,'utf8'));
const R=window.V2SX, m=R.mods.knowledge;
process.stdout.write(JSON.stringify({owns:R.owns('knowledge'), other:R.owns('home'), kinds:[typeof m.summary, typeof m.library, typeof m.render, typeof m.owns], sum:m.summary()}));
""" % (json.dumps(os.path.join(DC, 'v2-logic.js')), 'undefined' if shell_on is None else json.dumps({'on': shell_on}), json.dumps(os.path.join(DC, 'v2s', 'books.js')))
    out = subprocess.run([v2_node.NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-1500:]
    return json.loads(out.stdout)


@needs_node
def test_the_registry_owns_the_knowledge_module_only_under_the_new_shell():
    on, off, none = _node_registry(True), _node_registry(False), _node_registry(None)
    assert on['owns'] is True and off['owns'] is False and none['owns'] is False, 'الغلاف مقفول ⇒ الشاشة القديمة'
    assert on['other'] is False
    assert on['kinds'] == ['function', 'function', 'function', 'function']
    assert on['sum']['review'] is None and on['sum']['partial'] is True, 'قبل أي جلب: لا أرقام مخترعة'


JS = _read('dashboard-cloud', 'v2s', 'books.js')
CODE = _strip_comments(JS)


def test_nothing_is_persisted_in_the_browser():
    for bad in ('localStorage', 'sessionStorage', 'indexedDB', 'document.cookie'):
        assert bad not in CODE, bad


def test_every_write_goes_through_one_of_the_four_existing_endpoints_and_money_is_never_touched():
    assert 'fetch(' not in CODE and 'XMLHttpRequest' not in CODE and 'E.post(' not in CODE
    methods = sorted(re.findall(r"method: '(\w+)'", CODE))
    assert methods == ['POST', 'POST', 'POST', 'PUT', 'PUT'], methods
    targets = [re.sub(r"\s+", ' ', t) for t in re.findall(r"api\(('/platform-[^']*'[^,]*)", CODE)]
    assert sorted(set(t.split("'")[1] for t in targets)) == ['/platform-books', '/platform-knowledge/', '/platform-library/ingest-folder'], targets
    reads = set(re.findall(r"PATHS = \{(.*?)\};", CODE, re.S)[0].split("'")[1::2])
    assert reads <= set(['/platform-knowledge', '/v2/books/review?status=pending_review', '/v2/books/review?status=rejected', '/v2/prices/book', '/v2/book-offers?status=all',
                         '/v2/books/store', '/v2/ads-ledger']), reads
    assert 'DELETE' not in CODE, '«حذف» اندمج في «أخفِ عن الناس»'
    for money in ('openMoney', 'confirmed: true', '/refund', '/settle', 'wallet', 'payout'):
        assert money not in CODE, money


def test_visible_strings_in_the_screen_are_plain_arabic_without_ai_headlines():
    banned = ['يقوّم', 'يقوم بتقييم', 'API', 'RAG', 'OCR', 'PDF', 'Folder', 'bridge', 'null', 'undefined', 'NaN', 'الذكاء الاصطناعي', 'طابور', 'JSON', 'endpoint', 'بروف']
    for m in re.finditer(r"'((?:[^'\\\n]|\\.)*[؀-ۿ](?:[^'\\\n]|\\.)*)'", CODE):
        t = m.group(1)
        for bad in banned:
            assert bad not in t, (bad, t)
        assert not re.match(r'^\s*(ذكاء|الذكاء|AI)\b', t), t
        assert not re.search(r'[0-9]', re.sub(r'<[^>]*(?:>|$)', '', t)), t
    for w in ('ملفاته', 'دوراته', 'فلوسه', 'راسله', 'عليه نزاع'):
        assert not re.search(r'(?<![؀-ۿ])%s(?![؀-ۿ])' % w, CODE), w


def test_the_only_images_on_the_tab_are_the_books_photo_and_the_brain_avatar():
    imgs = set(re.findall(r"img\('([a-z-]+)'\)", CODE))
    assert imgs == {'brain-avatar', 'books'}, imgs
    assert not re.search(r'<img[^>]+src="(?!\' \+ img|v2/img)', CODE)
    assert 'cover' not in CODE.replace('cover_url', '').replace('coverUrl', '').replace('bk_acv', '').replace('رابط صورة الغلاف', ''), 'لا أغلفة'
    for name in ('books.jpg', 'brain-avatar.jpg'):
        assert os.path.getsize(os.path.join(DC, 'v2', 'img', name)) > 1000


def test_every_failed_source_has_a_visible_not_available_path():
    assert 'تعذّر جلب: ' in CODE and 'function warnStrip(' in CODE
    assert 'الكتب والأعمال: غير متاح بعد' in CODE and 'تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.' in CODE and 'data-a="retry"' in CODE
    assert 'لم يصل ما نعرضه بعد' in CODE, 'مصدر واقع ولا صفوف ≠ «لا أعمال بعد»'
    assert 'أعمال السوق التي تنتظر المراجعة: ' in CODE, 'ممرّ المراجعة لا يدّعي «لا شيء» والمصدر واقع'


def test_the_screen_never_redraws_under_an_open_sheet_and_the_dock_hides_with_it():
    assert "document.getElementById('epModal')" in CODE and 'S.dirty' in CODE
    assert 'function dockHide(' in CODE and CODE.count('dockHide(') >= 4


CSS = _read('dashboard-cloud', 'v2s', 'books.css')


def test_css_is_scoped_under_the_books_roots_only():
    bare = re.sub(r'/\*.*?\*/', '', CSS, flags=re.S)
    for sel in re.findall(r'([^{}]+)\{', bare):
        sel = sel.strip()
        if sel.startswith('@') or re.match(r'^[\d.]+%|^from$|^to$', sel):
            continue
        for part in sel.split(','):
            assert part.strip().startswith(('.v2s-books', '.v2s-bm', '#epModal', 'body:has(#epModal) .v2s-books')), part


def test_touch_targets_and_the_mobile_dock_rules_are_in_the_css():
    mob = CSS[CSS.index('@media(max-width:760px)'):]
    assert re.search(r'\.bk-search\{[^}]*min-height:52px', mob) and re.search(r'\.bk-fold\{[^}]*min-height:52px', mob)
    assert re.search(r'\.bk-search\{[^}]*min-height:48px[^}]*font-size:16px', CSS)
    assert 'padding-bottom:calc(76px + env(safe-area-inset-bottom))' in mob and 'env(safe-area-inset-bottom)' in mob
    assert re.search(r'\.bk-dock\{[^}]*position:fixed[^}]*z-index:60', mob)
    assert 'body:has(#epModal) .v2s-books .bk-dock{display:none}' in CSS
    assert re.search(r'\.bk-tgrid\{[^}]*grid-template-columns:repeat\(3', CSS) and re.search(r'@media\(max-width:1179px\)\{[^@]*\.bk-tgrid\{grid-template-columns:repeat\(2', CSS)
    assert 'prefers-reduced-motion' in CSS
    assert not re.search(r'#(?:1[bB]2|0[fF]3)', CSS.replace('#0F5A37', '')), 'لا كحلي (مش لون الهوية)'
    for tok in ('#9E2B4E',):
        assert tok in CSS


def test_the_docs_status_file_lists_the_founder_decisions():
    st = _read('docs', 'v2', 'final', 'STATUS-books.md')
    for need in ('قرارات تحتاج المؤسس', 'D-1', 'D-8', 'مكتبة المراجع', 'العقل'):
        assert need in st, need


def test_no_test_hook_or_time_override_ships_in_the_screen():
    assert 'V2SX_BOOKS' not in CODE and 'nowOverride' not in CODE and '_tick' not in CODE and '_state' not in CODE
    assert 'function now() { return Date.now(); }' in CODE


def test_the_list_draws_once_the_three_deciding_sources_settle_and_a_slow_source_times_out():
    assert "var CORE = ['knowledge', 'prices', 'offers'];" in CODE and 'CORE.every(settled)' in CODE and 'LIST.every(settled)' not in CODE
    assert 'LATE_MS = 8000' in CODE and "s.state = 'error'" in CODE, 'مصدر متأخر ينقلب «غير متاح بعد» بعد ٨ ثوانٍ'
    assert '…جارٍ جلب بقية البيانات' in CODE and 'res.failed = res.failed.filter(' in CODE, 'ما لم يصل بعد ليس «تعذّر»'


def test_the_periodic_timers_stop_when_the_tab_is_left_and_restart_on_render():
    assert 'setInterval' in CODE and 'S.poll' not in CODE, 'لا استطلاع كل نصف ثانية'
    assert 'function stopTimers()' in CODE and 'clearInterval(S.minute)' in CODE and "addEventListener('hashchange', S.hashFn)" in CODE
    assert 'startTimers();' in CODE[CODE.index('function render(v) {'):CODE.index('function leftTab()')]


def test_the_owner_link_is_a_44px_target_on_every_width_and_the_edge_fixes_are_in_the_css():
    assert re.search(r'\.bk-item \.v3-person\{[^}]*min-height:44px', CSS)
    assert not re.search(r'\.bk-row \.v3-person\{[^}]*padding:6px', CSS)
    mob = CSS[CSS.index('@media(max-width:760px)'):]
    assert re.search(r'\.bk-addrow \.v3-btn2,[^{]*\.v3-empty \.v3-btn1,[^{]*\.v3-empty \.v3-btn2\{width:100%\}', mob), 'كل الأزرار بعرض الشاشة في الموبايل'
    assert re.search(r'#epModal \.v2s-bm \.fld label\{color:#21262E\}', CSS), 'عناوين الخانات بحبر لا رمادي بارد'
    assert re.search(r'#epModal \.v2s-bm \.fld input,[^{]*\{border-color:#E9E1D6\}', CSS)
