# -*- coding: utf-8 -*-
"""«سعر خاص لكل دليل» (2026-11-02): بروكسي الحذف «ارجع للسعر العام» + مرور حقول القائمة الجديدة + منطق الشاشة (node) + الملفات.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2_item_prices.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/item_prices_fixtures.ItemPricesPlatform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.

اللي بيثبّته:
  ١. DELETE `/api/v2/prices/book/<id>`: أدمن بس · المفتاح مقفول ⇒ ٤٠٤ بلا نداء · `no-store` · `confirmed:true` بالظبط · `by` من التوكن ·
     قايمة بيضا للحقول · النوع كتاب بس · رفض المنصة (٤٠٩/٤٢٢) بيعدّي · الرد الضايع ⇒ «ما وصلناش رد» بلا تدقيق ناجح · التدقيق `prices.reset_to_general` عند النجاح بس.
  ٢. حقول القائمة الجديدة (`group` · `has_own` · `uses_general`) بتعدّي كما هي، وتعديل دليل بيمرّ بنفس PUT الكتب (`prices.update`).
  ٣. المنطق (node): الصفوف بالمجموعات · الفلتر والبحث · أقل سعر فعلي للدليل الذي يأخذ العام · فرق «قبل ⇒ بعد» للرجوع · الأدلّة بره متوسط الكتب وبره صفوف متجر «الكتب».
  ٤. الملفات: الواجهة بتنادي DELETE بجسم مؤكَّد ولا تبعت `by`.
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

from app import app as flask_app, db, User, AuditLog  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import item_prices_fixtures as ipfx   # noqa: E402
import v2_node                        # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ADMIN_EMAIL = 'v2ip-admin@x.test'
GUIDE = '/api/v2/prices/book/guide-rent'
GUIDE_PP = '/api/bridge/prices/book/guide-rent'
DEL_BODY = {'confirmed': True, 'note': 'نرجع للعام', 'rev': 1}


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
        heads = {r: _bearer(_mkuser('v2ip-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self, **kw):
        self.ef = ipfx.ItemPricesPlatform(d2=True, **kw)
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

    def calls(self, path_prefix='', method=None):
        return [c for c in self.seen if c['path'].startswith(path_prefix) and (method is None or c['method'] == method)]


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
    heads = ctx['heads'][role] if role else {}
    kw = {'headers': heads}
    if body is not None:
        kw['json'] = body
    return ctx['client'].open(path, method=method, **kw)


def _audits(action):
    return AuditLog.query.filter_by(action=action).order_by(AuditLog.id.desc()).all()


# ---------------------------------------------------------------- ١) بروكسي الحذف

def test_reset_to_general_is_admin_only(ctx, plat):
    for role in NON_ADMIN_ROLES:
        assert _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY), role=role).status_code == 403, role
    assert _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY), role=None).status_code == 401
    assert plat.seen == [], 'نداء للمنصة من غير أدمن'


def test_reset_to_general_is_closed_when_the_switch_is_off(ctx, plat, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY))
    assert r.status_code == 404 and plat.seen == [] and r.headers.get('Cache-Control') == 'no-store'


def test_reset_needs_confirmed_true_exactly(ctx, plat):
    for bad in (None, False, 'true', 1, 'yes'):
        b = dict(DEL_BODY)
        if bad is None:
            b.pop('confirmed')
        else:
            b['confirmed'] = bad
        r = _call(ctx, 'DELETE', GUIDE, b)
        assert r.status_code == 400 and r.headers.get('Cache-Control') == 'no-store', bad
    assert _call(ctx, 'DELETE', GUIDE).status_code == 400          # بلا جسم أصلًا
    assert plat.seen == [], 'نداء للمنصة من غير تأكيد صريح'


def test_reset_by_comes_from_the_token_and_the_body_is_a_whitelist(ctx, plat):
    b = {'confirmed': True, 'rev': 1, 'note': 'ن' * 900, 'by': 'attacker@evil.test', 'evil': 1, 'versions': {'read': {}}, 'role': 'root'}
    r = _call(ctx, 'DELETE', GUIDE, b)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    calls = plat.calls(GUIDE_PP, 'DELETE')
    assert len(calls) == 1, 'نداء واحد ولا إعادة محاولة'
    sent = calls[0]['json']
    assert set(sent) <= {'confirmed', 'note', 'rev', 'by'} and sent['confirmed'] is True and sent['by'] == ADMIN_EMAIL
    assert len(sent['note']) == 300 and 'attacker' not in json.dumps(sent) and 'evil' not in sent
    assert calls[0]['headers'].get('X-ELP-Metrics-Secret') == SECRET
    assert r.headers.get('Cache-Control') == 'no-store'


def test_reset_rev_is_forwarded_only_when_it_is_a_whole_number(ctx, plat):
    for bad in ('1', True, 1.5, [1], None):
        plat.ef.guide_docs.setdefault('guide-rent', dict(ipfx.GUIDE_OWN['guide-rent'], title='دليل عقد الإيجار السكني', rev=1))
        _call(ctx, 'DELETE', GUIDE, {'confirmed': True, 'rev': bad})
        sent = plat.calls(GUIDE_PP, 'DELETE')[-1]['json']
        assert 'rev' not in sent, bad
    plat.ef.guide_docs['guide-rent'] = dict(ipfx.GUIDE_OWN['guide-rent'], title='x', rev=1)
    _call(ctx, 'DELETE', GUIDE, {'confirmed': True, 'rev': 1.0})
    assert plat.calls(GUIDE_PP, 'DELETE')[-1]['json']['rev'] == 1


def test_reset_is_validated_by_kind_and_id_before_any_call(ctx, plat):
    assert _call(ctx, 'DELETE', '/api/v2/prices/course/contract-basics', dict(DEL_BODY)).status_code == 404
    assert _call(ctx, 'DELETE', '/api/v2/prices/movie/x', dict(DEL_BODY)).status_code == 404
    assert _call(ctx, 'DELETE', '/api/v2/prices/book/a%20b', dict(DEL_BODY)).status_code == 404
    assert _call(ctx, 'DELETE', '/api/v2/prices/book/x%3Fy', dict(DEL_BODY)).status_code == 404
    assert plat.seen == []


def test_reset_success_removes_the_own_price_and_is_audited_once(ctx, plat):
    before = db.session.query(AuditLog).count()
    r = _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY))
    assert r.status_code == 200 and r.get_json()['removed'] is True
    rows = _audits('prices.reset_to_general')
    assert rows[0].actor_email == ADMIN_EMAIL and rows[0].target == 'book:guide-rent'
    assert json.loads(rows[0].meta_json) == {'kind': 'book', 'rev': 1}
    assert db.session.query(AuditLog).count() == before + 1
    lst = _call(ctx, 'GET', '/api/v2/prices/book').get_json()
    row = [i for i in lst['items'] if i['id'] == 'guide-rent'][0]
    assert row['has_own'] is False and row['uses_general'] is True
    log = [x for x in plat.ef.price_log if x['op'] == 'removed']
    assert log and log[0]['old_versions']['read']['eg'] == 120.0 and log[0]['by'] == ADMIN_EMAIL


def test_the_platforms_refusals_pass_through_and_are_not_audited(ctx, plat):
    n = len(_audits('prices.reset_to_general'))
    r = _call(ctx, 'DELETE', '/api/v2/prices/book/bk-tenant-guide', dict(DEL_BODY))        # كتاب ⇒ ٤٠٩
    assert r.status_code == 409 and 'للأدلّة' in r.get_json()['error']
    r = _call(ctx, 'DELETE', '/api/v2/prices/book/_guides', dict(DEL_BODY))                # السعر العام نفسه ⇒ ٤٠٩
    assert r.status_code == 409
    r = _call(ctx, 'DELETE', '/api/v2/prices/book/guide-sole', {'confirmed': True})        # يأخذ العام أصلًا ⇒ ٤٠٩
    assert r.status_code == 409 and 'السعر العام' in r.get_json()['error']
    r = _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY, rev=77))                                 # نسخة قديمة ⇒ ٤٠٩
    assert r.status_code == 409 and 'اتعدّلت من مكان تاني' in r.get_json()['error']
    assert 'guide-rent' in plat.ef.guide_docs, 'الرفض ما يمسّش الوثيقة'
    assert len(_audits('prices.reset_to_general')) == n


def test_a_lost_reply_is_no_reply_not_a_refusal(ctx, plat):
    n_ok, n_nr = len(_audits('prices.reset_to_general')), len(_audits('prices.no_reply'))
    for status in (500, 502, 503, 504):
        plat.ef.forced[('DELETE', GUIDE_PP)] = (status, {'detail': 'x'})
        r = _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY))
        assert r.status_code == 502 and r.get_json().get('no_reply') is True, status
        assert r.headers.get('Cache-Control') == 'no-store'
    assert len(_audits('prices.reset_to_general')) == n_ok
    assert len(_audits('prices.no_reply')) == n_nr + 4
    plat.ef.forced[('DELETE', GUIDE_PP)] = (422, {'detail': 'لازم تأكيد التعديل الأول'})
    r = _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY))
    assert r.status_code == 422 and 'no_reply' not in r.get_json()


def test_the_shared_key_rejection_is_a_bad_link_not_a_logout(ctx, plat):
    plat.ef.forced[('DELETE', GUIDE_PP)] = (401, {'detail': 'no'})
    r = _call(ctx, 'DELETE', GUIDE, dict(DEL_BODY))
    assert r.status_code == 502


# ---------------------------------------------------------------- ٢) القائمة والتعديل

def test_the_new_list_fields_pass_through_untouched(ctx, plat):
    r = _call(ctx, 'GET', '/api/v2/prices/book')
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    items = r.get_json()['items']
    by_group = {}
    for it in items:
        by_group.setdefault(it['group'], []).append(it)
    assert set(by_group) == {'book', 'guides_general', 'guide'} and len(by_group['guides_general']) == 1 and len(by_group['guide']) == 5
    assert by_group['guides_general'][0]['id'] == '_guides' and by_group['guides_general'][0]['title'] == 'السعر العام للأدلّة'
    g = {i['id']: i for i in by_group['guide']}
    assert g['guide-rent']['has_own'] is True and g['guide-rent']['uses_general'] is False
    assert g['guide-sole']['has_own'] is False and g['guide-sole']['uses_general'] is True
    assert g['guide-heirs']['visible'] is False and g['guide-sole']['visible'] is True
    assert plat.calls('/api/bridge/prices', 'GET')[-1]['path'] == '/api/bridge/prices/book'


def test_editing_a_guide_goes_through_the_same_put_and_audit_as_a_book(ctx, plat):
    n = len(_audits('prices.update'))
    b = {'versions': {'read': {'eg': {'amount': 130, 'currency': 'EGP'}, 'default': {'amount': 8, 'currency': 'USD'}}, 'pdf': {}},
         'visible': True, 'confirmed': True, 'rev': 0, 'title': 'دليل تأسيس شركة فردية', 'by': 'attacker@evil.test'}
    r = _call(ctx, 'PUT', '/api/v2/prices/book/guide-sole', b)
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    sent = plat.calls('/api/bridge/prices/book/guide-sole', 'PUT')[-1]['json']
    assert sent['by'] == ADMIN_EMAIL and sent['confirmed'] is True
    assert len(_audits('prices.update')) == n + 1 and _audits('prices.update')[0].target == 'book:guide-sole'
    row = [i for i in _call(ctx, 'GET', '/api/v2/prices/book').get_json()['items'] if i['id'] == 'guide-sole'][0]
    assert row['has_own'] is True and row['min_price']['eg']['amount'] == 130
    # الرفض لا يترك وثيقة ولا تدقيق
    k = len(_audits('prices.update'))
    r = _call(ctx, 'PUT', '/api/v2/prices/book/guide-labor', dict(b, visible=True, versions={'read': {'eg': {'amount': 5, 'currency': 'EGP'}}, 'pdf': {}}, rev=0))
    assert r.status_code == 422 and 'باقي البلاد' in r.get_json()['error']
    assert len(_audits('prices.update')) == k


def test_the_general_row_is_edited_like_any_book(ctx, plat):
    got = _call(ctx, 'GET', '/api/v2/prices/book/_guides').get_json()
    assert got['prices']['title'] == 'السعر العام للأدلّة' and got['prices']['versions']['read']['eg']['amount'] == 99
    b = {'versions': {'read': {'eg': {'amount': 110, 'currency': 'EGP'}, 'default': {'amount': 6, 'currency': 'USD'}}, 'pdf': {}}, 'visible': True, 'confirmed': True, 'rev': got['prices']['rev']}
    assert _call(ctx, 'PUT', '/api/v2/prices/book/_guides', b).status_code == 200
    assert plat.ef.general['versions']['read']['eg'] == 110.0


def test_a_guide_without_its_own_price_returns_an_empty_form(ctx, plat):
    got = _call(ctx, 'GET', '/api/v2/prices/book/guide-labor').get_json()
    assert got['prices']['rev'] == 0 and got['prices']['versions'] == {} and got['prices']['title'] == 'دليل عقد العمل للموظف'


# ---------------------------------------------------------------- ٣) المنطق (node)

def L(fn, *args):
    return v2_node.logic(fn, *args)


def _list_resp(**kw):
    return ipfx.ItemPricesPlatform(d2=True, **kw)._list()


@needs_node
def test_rows_carry_group_and_ownership_and_legacy_rows_stay_books():
    res = L('v2Prices', _list_resp())
    g = {r['id']: r for r in res['rows']}
    assert g['bk-tenant-guide']['group'] == 'book' and g['_guides']['group'] == 'guides_general'
    assert g['guide-rent']['group'] == 'guide' and g['guide-rent']['hasOwn'] is True and g['guide-rent']['usesGeneral'] is False
    assert g['guide-sole']['hasOwn'] is False and g['guide-sole']['usesGeneral'] is True
    assert g['_guides']['title'] == 'السعر العام للأدلّة'
    legacy = {'ok': True, 'countries': ipfx.COUNTRIES, 'currencies': ipfx.CURRENCIES,
              'items': [{'id': 'b1', 'title': 'كتاب', 'visible': True, 'has_prices': True, 'min_price': {'eg': {'amount': 150, 'currency': 'EGP'}}}]}
    row = L('v2Prices', legacy)['rows'][0]
    assert row['group'] == 'book' and row['hasOwn'] is False and row['usesGeneral'] is False
    assert L('v2PricesView', L('v2Prices', legacy), {'group': 'all', 'q': ''})['showTools'] is False


@needs_node
def test_a_guide_that_takes_the_general_price_shows_the_general_minimum():
    for eff in (True, False):
        res = L('v2Prices', _list_resp(guide_min_effective=eff))
        g = {r['id']: r for r in res['rows']}
        assert g['guide-sole']['minText'] == g['_guides']['minText'] == 'مصر: ٩٩ جنيه، السعودية: ٢٥ ريال، باقي البلاد: ٥ دولار', eff
        assert g['guide-rent']['minText'].startswith('مصر: ١٢٠ جنيه'), 'السعر الخاص ما يتغطّاش بالعام'
        assert g['guide-sole']['badge'] == 'يأخذ السعر العام' and g['guide-rent']['badge'] == 'سعر خاص'


@needs_node
def test_no_price_line_joins_countries_with_a_middle_dot():
    for r in L('v2Prices', _list_resp())['rows']:
        assert ' · ' not in r['minText'], r['minText']


@needs_node
def test_the_view_groups_filters_and_searches():
    res = L('v2Prices', _list_resp())
    v = L('v2PricesView', res, {'group': 'all', 'q': ''})
    assert v['showTools'] is True and [s['key'] for s in v['sections']] == ['book', 'general', 'guide']
    assert v['counts'] == {'all': 10, 'book': 4, 'guide': 5}      # الشريحة بتعدّ الأدلّة وحدها (٥) زي القسم تحتها، والعام صفّ لوحده
    assert v['counts']['guide'] == len(v['sections'][2]['rows'])
    assert [len(s['rows']) for s in v['sections']] == [4, 1, 5]
    only_books = L('v2PricesView', res, {'group': 'book', 'q': ''})
    assert [s['key'] for s in only_books['sections']] == ['book']
    only_guides = L('v2PricesView', res, {'group': 'guide', 'q': ''})
    assert [s['key'] for s in only_guides['sections']] == ['general', 'guide'] and len(only_guides['sections'][1]['rows']) == 5
    s = L('v2PricesView', res, {'group': 'all', 'q': 'مواريث'})
    assert [r['id'] for sec in s['sections'] for r in sec['rows']] == ['guide-heirs']
    s = L('v2PricesView', res, {'group': 'all', 'q': 'عقد الايجار'})
    assert [r['id'] for sec in s['sections'] for r in sec['rows']] == ['guide-rent'], 'البحث يتجاهل الهمزة'
    none = L('v2PricesView', res, {'group': 'all', 'q': 'غير موجود أبدًا'})
    assert none['empty'] is True and none['sections'] == []
    both = L('v2PricesView', res, {'group': 'book', 'q': 'مواريث'})
    assert both['empty'] is True


@needs_node
def test_reset_diff_lists_every_cell_that_changes_and_always_says_the_price_kind_changes():
    own = L('v2PriceForm', _own_detail('guide-rent'))
    gen = L('v2PriceForm', _own_detail('_guides'))
    d = L('v2PriceResetDiff', own, gen)
    assert d['changed'] is True and d['lines'][0] == {'label': 'نوع السعر', 'from': 'سعر خاص', 'to': 'السعر العام'}
    labels = [x['label'] for x in d['lines']]
    # الدليل والسعر العام قراءة بس (المنصة ترفض PDF عليهما)، فما فيش سطر PDF أصلًا
    assert 'القراءة على المنصة · مصر' in labels and not any('PDF' in x for x in labels)
    eg = [x for x in d['lines'] if x['label'] == 'القراءة على المنصة · مصر'][0]
    assert eg['from'] == '١٢٠ جنيه' and eg['to'] == '٩٩ جنيه'
    d2 = L('v2PriceResetDiff', own, None)
    assert d2['changed'] is True and len(d2['lines']) == 1


def _own_detail(item_id):
    p = ipfx.ItemPricesPlatform(d2=True)
    status, body = p._prices('GET', 'book', item_id, {})
    assert status == 200
    return body


@needs_node
def test_guides_stay_out_of_the_books_average_and_the_books_store_rows():
    pr = _list_resp()
    avg_all = L('v2BookAverage', pr, 'eg')
    only_books = dict(pr, items=[i for i in pr['items'] if i['group'] == 'book'])
    assert avg_all == L('v2BookAverage', only_books, 'eg') and avg_all['n'] == 3
    works = L('v2kWorks', {'knowledge': {'items': []}, 'prices': pr}, 1)
    keys = json.dumps(works, ensure_ascii=False)
    assert 'st:guide-' not in keys, 'أدلّة المتجر لا تُضاف كأعمال إلى «الكتب»'
    assert 'st:bk-tenant-guide' in keys


# ---------------------------------------------------------------- ٤) الملفات

def _strip_comments(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_the_screen_calls_delete_with_a_confirmed_body_and_never_sends_by():
    js = _strip_comments(_read('dashboard-cloud', 'v2-d3.js'))
    i = js.index("method: 'DELETE'")
    call = js[max(0, i - 200):i + 260]
    assert 'confirmed: true' in call and 'by:' not in call
    assert 'ارجع للسعر العام' in js and 'يأخذ السعر العام' in js and 'سعر خاص' in js
    assert 'localStorage.setItem(\'v3_price' not in js, 'الفلتر والبحث في الذاكرة فقط'


def test_the_delete_route_is_the_only_new_write_and_has_the_new_audit_name():
    src = _strip_comments(_read('backend', 'app.py'))
    i = src.index("@app.route('/api/v2/prices/<kind>/<item_id>', methods=['DELETE'])")
    block = src[i:i + 1800]
    assert '@roles_required(\'admin\')' in block and '_v2_confirmed(body)' in block and "'prices.reset_to_general'" in block
    assert block.count('_v2_write(') == 1 and "_actor_email" not in block, 'by يوضع في _v2_write من التوكن'


# ═══ الدليل القصير (المنصة 2026-11-09): أقصر من حد البيع ⇒ بلا سعر ويُقرأ كاملًا ═══════════════

@needs_node
def test_a_short_guide_is_marked_and_never_borrows_the_general_minimum():
    resp = _list_resp()
    for it in resp['items']:
        if it['id'] == 'guide-sole':
            it.update({'source': 'short', 'uses_general': False, 'min_price': {}, 'words': 1200})
    g = {r['id']: r for r in L('v2Prices', resp)['rows']}
    assert g['guide-sole']['short'] is True and g['guide-sole']['badge'] == 'دليل قصير'
    assert g['guide-sole']['minText'] == 'يُقرأ كاملًا بلا سعر'
    assert g['guide-rent']['short'] is False and g['guide-rent']['badge'] == 'سعر خاص'


@needs_node
def test_a_short_source_on_a_book_row_changes_nothing():
    resp = _list_resp()
    for it in resp['items']:
        if it['id'] == 'bk-tenant-guide':
            it['source'] = 'short'
    g = {r['id']: r for r in L('v2Prices', resp)['rows']}
    assert g['bk-tenant-guide']['short'] is False and g['bk-tenant-guide']['badge'] == ''


def test_the_short_guide_form_says_it_reads_in_full_and_starts_visible():
    js = open(os.path.join(ROOT, 'dashboard-cloud', 'v2-d3.js'), encoding='utf-8').read()
    assert 'هذا الدليل أقصر من حد البيع، فيُقرأ كاملًا بلا سعر' in js
    assert "if (isShort && !row.hasOwn) form.visible = true;" in js
    assert '.v3-own.short{' in open(os.path.join(ROOT, 'dashboard-cloud', 'v2-d3.css'), encoding='utf-8').read()


@needs_node
def test_the_guides_section_counts_how_many_are_above_and_below_the_minimum():
    resp = _list_resp()
    resp['guides_min_words'] = 4000
    for it in resp['items']:
        if it['id'] == 'guide-sole':
            it.update({'source': 'short', 'uses_general': False, 'words': 1200})
        elif it['id'] == 'guide-rent':
            it['words'] = 5200
    res = L('v2Prices', resp)
    assert res['minWords'] == 4000
    view = L('v2PricesView', res, {'group': 'all', 'q': 'لا يطابق شيئًا'})
    assert view['size'] == {'minWords': 4000, 'above': 1, 'below': 1}, 'العدد من كل الأدلّة لا من البحث'
    old = _list_resp()
    old.pop('guides_min_words', None)
    assert L('v2PricesView', L('v2Prices', old), {'group': 'all', 'q': ''})['size'] is None


def test_the_size_line_says_the_minimum_in_words_and_pages():
    js = open(os.path.join(ROOT, 'dashboard-cloud', 'v2-d3.js'), encoding='utf-8').read()
    assert "'حد البيع ' + U.ar(z.minWords) + ' كلمة (نحو '" in js
    assert 'وتحت الحد ويُقرأ كاملًا بلا سعر: ' in js


# ═══ «الأسعار المبدئية» (المؤسس 2026-11-09): زر واحد للأدلّة العام وكتبنا، وكتب الخبراء والمجاني مستثناة ═══

def _starter_resp(**kw):
    return ipfx.ItemPricesPlatform(d2=True, sellers={'bk-tenant-guide': 'seed', 'bk-startup-law': 'ours', 'bk-labor': 'expert', 'bk-new': 'free'}, **kw)._list()


@needs_node
def test_the_starter_targets_the_general_guides_price_and_our_books_only():
    st = L('v2StarterPrices', L('v2Prices', _starter_resp()))
    ids = [t['id'] for t in st['targets']]
    assert ids == ['_guides', 'bk-tenant-guide', 'bk-startup-law']
    assert st['books'] == 2 and st['general'] == 1 and st['skipped'] == {'expert': 1, 'free': 1} and st['offer'] is True
    g, b = st['targets'][0], st['targets'][1]
    assert g['versions'] == {'read': {'eg': {'amount': 149, 'currency': 'EGP'}, 'default': {'amount': 5, 'currency': 'USD'}}}
    assert b['versions'] == {'read': {'eg': {'amount': 299, 'currency': 'EGP'}, 'default': {'amount': 10, 'currency': 'USD'}},
                             'pdf': {'eg': {'amount': 369, 'currency': 'EGP'}, 'default': {'amount': 12, 'currency': 'USD'}}}
    assert b['to'] == 'مصر: ٢٩٩ جنيه، باقي البلاد: ١٠ دولار'


@needs_node
def test_the_starter_pdf_is_dearer_by_about_a_fifth_and_no_gulf_price_is_invented():
    st = L('v2StarterPrices', L('v2Prices', _starter_resp()))
    for t in st['targets']:
        for row in t['versions'].values():
            assert set(row) == {'eg', 'default'}
    b = st['targets'][1]['versions']
    for c in ('eg', 'default'):
        assert 1.2 <= b['pdf'][c]['amount'] / b['read'][c]['amount'] <= 1.25


@needs_node
def test_once_applied_the_starter_says_so_and_offers_nothing():
    resp = _starter_resp()
    for it in resp['items']:
        if it['id'] == '_guides':
            it.update({'visible': True, 'min_price': {'eg': {'amount': 149, 'currency': 'EGP'}, 'default': {'amount': 5, 'currency': 'USD'}}})
        if it['id'] in ('bk-tenant-guide', 'bk-startup-law'):
            it.update({'visible': True, 'min_price': {'eg': {'amount': 299, 'currency': 'EGP'}, 'default': {'amount': 10, 'currency': 'USD'}}})
    st = L('v2StarterPrices', L('v2Prices', resp))
    assert st['targets'] == [] and st['applied'] is True and st['offer'] is False and st['done'] == 3


@needs_node
def test_a_platform_that_does_not_say_who_sells_a_book_gets_no_book_prices():
    st = L('v2StarterPrices', L('v2Prices', _list_resp()))
    assert [t['id'] for t in st['targets']] == ['_guides']


def test_the_starter_button_writes_only_after_the_confirm_and_says_what_stays():
    js = open(os.path.join(ROOT, 'dashboard-cloud', 'v2-d3.js'), encoding='utf-8').read()
    assert 'طبّق الأسعار المبدئية' in js and "id=\"v3_sgo\">أكّد التطبيق" in js
    assert "go.onclick = function () {" in js.split('function openStarter')[1].split('function priceBlock')[0]
    assert 'كتب الخبراء لا تتغير' in js and 'الأسعار المبدئية مطبّقة' in js
