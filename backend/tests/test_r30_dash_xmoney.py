# -*- coding: utf-8 -*-
"""R30 — فلوس ملفات الخبراء بعد اختبار الرحلة الكاملة الحيّ (2026-11-16/17).

Run:  cd backend && python3 -m pytest -q -p no:cacheprovider tests/test_r30_dash_xmoney.py

اللي بيثبّته:
  ١. «اعكس الملف وارجع الفلوس»: أدمن بس · المفتاح · تأكيد صريح · سبب · نوع شغل مقفول على «يسألك» في الخادم · `by` من التوكن ·
     تدقيق بعد النجاح بس · رد ضاع = «ما وصلناش رد» · نداء واحد لكل ضغطة.
  ٢. «محجوز حتى يُسلَّم العمل» من الضمان الحقيقي على المنصة (`/api/v2/money/held`) لكل عملة، و«دخل» بيقول إنه يُحسب يوم الدفع.
  ٣. «صافي البروفيسور» بيحسب ملف الخبير لما حدث البيع يشيل الأنصبة.
  ٤. «اعتُمد اليوم» بيعدّ الرأي اللي اتعتمد النهارده من حارة `recent` (كان صفر دايمًا لأن الرأي بيطلع من كل الحارات بعد الاعتماد).
  ٥. ورقة الملف و«أُغلقت مؤخرًا» والزرار في الدرج القديم — نصوص عربية بسيطة.

⛔ صفر شبكة: المنصة ردود في الذاكرة، والمنطق في node على الملفات الحقيقية.
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

import app as appmod  # noqa: E402
from app import app as flask_app, db, User, AuditLog, Revenue  # noqa: E402
from brain2 import levels  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node  # noqa: E402

needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = os.environ.get('METRICS_SECRET', 'test-metrics-secret')
ADMIN_EMAIL = 'r30-admin@x.test'
NON_ADMIN = ['employee', 'trainer', 'investor', 'viewer', 'pending']
NOW = 1794916800000          # 2026-11-17T12:00:00Z
TODAY = '2026-11-17T09:30:00+00:00'
YESTERDAY = '2026-11-16T09:30:00+00:00'
LATIN = re.compile(r'[A-Za-z]')
FID = '6194bc68-ea88-4d2c-b7cd-3a3b15a41b29'
REVERSE = '/api/v2/expert-files/%s/reverse' % FID
PREVIEW = '/api/v2/expert-files/%s/reverse-preview' % FID
HELD = '/api/v2/money/held'
DONE = {'ok': True, 'already': False, 'file_id': FID, 'consultation_id': 'c-1', 'payment_id': 'pay-1', 'status': 'refunded', 'reversed': True,
        'file_no': 1007, 'amount': 500.0, 'currency': 'EGP', 'money_back': 'outside_platform', 'clawback': 'clawed_back', 'uncovered': 0.0,
        'expert': {'email': 'afandy.ai2026@x.test', 'amount': 300.0, 'currency': 'EGP', 'outcome': 'clawed_back', 'uncovered': 0.0}}


def _read(*p):
    with open(os.path.join(ROOT, *p), encoding='utf-8') as fh:
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
    if not u:
        u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role,
                 linked_to_name='', preferred_currency='AUTO', is_active=True)
        db.session.add(u)
    u.role = role
    u.dashboard_role = role
    u.is_active = True
    db.session.commit()
    return u


def _bearer(user):
    tok = jwt.encode({'user_id': user.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, flask_app.config['SECRET_KEY'], algorithm='HS256')
    return {'Authorization': 'Bearer ' + tok}


@pytest.fixture(scope='module')
def ctx():
    with flask_app.app_context():
        db.create_all()
        heads = {r: _bearer(_mkuser('r30-%s@x.test' % r, r)) for r in NON_ADMIN}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """المنصة: جدول ردود بالمسار. أي عنوان برّه المنصة الوهمية بيوقّع الاختبار."""

    def __init__(self):
        self.replies = {}
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'json': copy.deepcopy(json), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        rep = self.replies.get((method.upper(), url[len(PLATFORM):]))
        if rep is None:
            return _Resp(404, {'detail': 'Not Found'})
        if rep == 'boom':
            raise RuntimeError('timeout')
        return _Resp(*rep)


@pytest.fixture
def plat(monkeypatch):
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == []


def _call(ctx, method, path, body=None, who='admin'):
    heads = {} if who is None else ctx['heads'][who]
    return ctx['client'].open(path, method=method, headers=heads, json=body) if body is not None else ctx['client'].open(path, method=method, headers=heads)


# ═══════════════════════════════════════════ ١) «اعكس الملف وارجع الفلوس»
@pytest.mark.parametrize('method,path,body', [('GET', PREVIEW, None), ('POST', REVERSE, {'reason': 'س', 'confirmed': True}), ('GET', HELD, None)])
def test_admin_only_and_flag_closed(ctx, plat, monkeypatch, method, path, body):
    for role in NON_ADMIN:
        assert _call(ctx, method, path, body, who=role).status_code == 403
    assert _call(ctx, method, path, body, who=None).status_code == 401
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = _call(ctx, method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == []


def test_reverse_needs_confirm_and_reason_before_any_call(ctx, plat):
    assert _call(ctx, 'POST', REVERSE, {'reason': 'سبب'}).status_code == 400
    assert _call(ctx, 'POST', REVERSE, {'reason': 'سبب', 'confirmed': 'true'}).status_code == 400
    r = _call(ctx, 'POST', REVERSE, {'reason': '   ', 'confirmed': True})
    assert r.status_code == 400 and r.get_json()['error'] == 'سبب العكس مطلوب'
    assert _call(ctx, 'POST', '/api/v2/expert-files/a%20b/reverse', {'reason': 'س', 'confirmed': True}).status_code == 404
    assert plat.seen == []


def test_reverse_sends_a_whitelisted_body_with_by_from_the_token_and_audits_on_success(ctx, plat):
    plat.replies[('POST', '/api/bridge/expert-files/%s/reverse' % FID)] = (200, DONE)
    r = _call(ctx, 'POST', REVERSE, {'reason': 'تجربة الرحلة الكاملة', 'confirmed': True, 'by': 'someone@else', 'amount': 1, 'to_wallet': True})
    assert r.status_code == 200 and r.get_json()['status'] == 'refunded' and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen[-1]['json'] == {'reason': 'تجربة الرحلة الكاملة', 'confirmed': True, 'by': ADMIN_EMAIL}
    with flask_app.app_context():
        a = AuditLog.query.filter_by(action='expert_file.reverse', target=FID).order_by(AuditLog.id.desc()).first()
        meta = json.loads(a.meta_json)
        assert a.actor_email == ADMIN_EMAIL
        assert meta['expert_amount'] == 300.0 and meta['expert_currency'] == 'EGP' and meta['amount'] == 500.0 and meta['reason'] == 'تجربة الرحلة الكاملة'
    # «اتعكس قبل كده» من المنصة ⇒ رد عادي ولا تدقيق تاني
    plat.replies[('POST', '/api/bridge/expert-files/%s/reverse' % FID)] = (200, dict(DONE, already=True))
    _call(ctx, 'POST', REVERSE, {'reason': 'مرة تانية', 'confirmed': True})
    with flask_app.app_context():
        assert AuditLog.query.filter_by(action='expert_file.reverse', target=FID).count() == 1


def test_platform_refusal_passes_through_and_lost_reply_is_no_reply(ctx, plat):
    moved = 'يُعكس من هنا الملف المغلق الذي حُوّل أجر خبيره فقط'
    key = ('POST', '/api/bridge/expert-files/%s/reverse' % FID)
    plat.replies[key] = (409, {'detail': moved})
    r = _call(ctx, 'POST', REVERSE, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 409 and r.get_json()['error'] == moved
    plat.replies[key] = 'boom'
    r = _call(ctx, 'POST', REVERSE, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    plat.replies[key] = (200, {'ok': True, 'status': 'refunded'})        # ٢٠٠ من غير «reversed» ⇒ مش «اتعكس»
    r = _call(ctx, 'POST', REVERSE, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 502 and r.get_json()['no_reply'] is True
    assert len([c for c in plat.seen if c['method'] == 'POST']) == 3, 'نداء واحد لكل ضغطة ولا إعادة محاولة'


def test_reverse_is_a_money_type_locked_to_ask_on_the_server(ctx, plat, monkeypatch):
    wt = levels.get_type('expert_file_reverse')
    assert wt and wt.lock == 'money' and wt.reversible is False and wt.levels == ('ask',) and wt.default == 'ask'
    assert levels.check_level(wt, 'alone')[1] == 409 and levels.check_level(wt, 'suggest')[1] == 400
    assert not levels.eligible(wt)
    monkeypatch.setattr(levels, 'level_of', lambda ns, w: 'alone')
    r = _call(ctx, 'POST', REVERSE, {'reason': 'س', 'confirmed': True})
    assert r.status_code == 409 and plat.seen == []
    monkeypatch.undo()
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r2 = ctx['client'].put('/api/v2/brain/levels/expert_file_reverse', json={'level': 'alone'}, headers=ctx['heads']['admin'])
    assert r2.status_code == 409


def test_preview_held_and_the_recent_lane_are_thin_reads(ctx, plat):
    plat.replies[('GET', '/api/bridge/expert-files/%s/reverse-preview' % FID)] = (200, {'ok': True, 'reversible': True})
    plat.replies[('GET', '/api/bridge/escrow/held')] = (200, {'ok': True, 'totals': [], 'count': 0})
    plat.replies[('GET', '/api/bridge/expert-files')] = (200, {'status': 'recent', 'files': [], 'count': 0, 'total': 0})
    assert _call(ctx, 'GET', PREVIEW).get_json() == {'ok': True, 'reversible': True}
    assert _call(ctx, 'GET', HELD).get_json() == {'ok': True, 'totals': [], 'count': 0}
    r = _call(ctx, 'GET', '/api/platform-expert-files?status=recent')
    assert r.status_code == 200 and plat.seen[-1]['params'] == {'status': 'recent'}, 'الحارة الجديدة بتعدّي (مش بترجع «waiting»)'
    plat.replies[('GET', '/api/bridge/escrow/held')] = (401, {'detail': 'unauthorized'})
    assert _call(ctx, 'GET', HELD).status_code == 502, 'رفض السرّ مش خروج الأدمن'


# ═══════════════════════════════════════════ ٢) «محجوز» و«دخل» و«صافي البروفيسور»
HELD_RESP = {'ok': True, 'count': 2, 'totals': [{'currency': 'EGP', 'amount': 500, 'expert_share': 300, 'platform_share': 200, 'expert_files': 500, 'count': 1},
                                                {'currency': 'SAR', 'amount': 250, 'expert_share': 200, 'platform_share': 50, 'expert_files': 0, 'count': 1}]}
SALE = {'date': '2026-11-16', 'source': 'consultation', 'amount_egp': 500, 'amount_usd': 0, 'seller_share': 300, 'platform_share': 200, 'share_currency': 'EGP'}


@needs_node
def test_held_comes_from_the_platform_escrow_per_currency():
    b = v2_node.logic('v2MoneyBoard', {'revenues': [SALE], 'escrow': [], 'payouts': [], 'held': HELD_RESP}, 'month', NOW)
    n = {x['key']: x for x in b['numbers']}
    assert n['held']['na'] is False and n['held']['text'] == '٥٠٠ ج و٢٥٠ ر.س' and n['held']['count'] == 2, 'كل عملة لوحدها ولا جمع'
    assert 'داخلة في «دخل» يوم دفعها' in n['held']['note']
    assert 'يُحسب يوم الدفع' in n['income']['note'] and n['income']['text'] == '٥٠٠ ج'
    # فشل الجسر ⇒ «غير متاح بعد» بالسبب (مش صفر)
    n2 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': [], 'held': None}, 'month', NOW)['numbers']}
    assert n2['held']['na'] is True and n2['held']['why'] == 'تعذّر جلب أموال الضمان من المنصة'
    # لسه بيتحمّل ⇒ مرآة الداشبورد القديمة زي الأول
    n3 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [{'status': 'held', 'amount': 70, 'currency': 'EGP'}], 'payouts': []}, 'month', NOW)['numbers']}
    assert n3['held']['text'] == '٧٠ ج'
    # المحجوز صفر فعلًا ⇒ «٠» مش «غير متاح»
    n4 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [], 'escrow': [], 'payouts': [], 'held': {'ok': True, 'totals': [], 'count': 0}}, 'month', NOW)['numbers']}
    assert n4['held']['na'] is False and n4['held']['text'] == '٠'
    for x in list(n.values()) + list(n2.values()):
        assert not LATIN.search(x['note']) and not LATIN.search(x['text']) and not LATIN.search(x.get('why') or '')


@needs_node
def test_net_counts_the_expert_file_when_the_sale_carries_shares(ctx, monkeypatch):
    monkeypatch.setattr(appmod, 'METRICS_SECRET', SECRET, raising=False)
    r = ctx['client'].post('/api/metrics/finance-event', json={'payment_id': 'r30-sale-1', 'amount': 500, 'currency': 'EGP', 'kind': 'consultation',
                                                              'seller_share': 300, 'platform_share': 200, 'share_currency': 'EGP'},
                           headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200
    r2 = ctx['client'].post('/api/metrics/finance-event', json={'payment_id': 'r30-sale-1', 'amount': -500, 'currency': 'EGP', 'kind': 'consultation',
                                                               'event': 'refund', 'refund_of': 'r30-sale-1', 'full_refund': True,
                                                               'seller_share': -300, 'platform_share': -200, 'share_currency': 'EGP'},
                            headers={'X-ELP-Metrics-Secret': SECRET})
    assert r2.status_code == 200
    with flask_app.app_context():
        sale = Revenue.query.filter_by(payment_id='r30-sale-1').first()
        back = Revenue.query.filter_by(payment_id='refund:r30-sale-1').first()
        assert (sale.seller_share, sale.platform_share, sale.source) == (300, 200, 'consultation')
        assert (back.seller_share, back.platform_share, back.amount_egp) == (-300, -200, -500)
    n = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': [SALE], 'escrow': [], 'payouts': []}, 'month', NOW)['numbers']}
    assert n['net']['text'] == '٢٠٠ ج' and 'بلا تفصيل للنصيب' not in n['net']['note']
    both = [SALE, dict(SALE, amount_egp=-500, seller_share=-300, platform_share=-200)]
    n2 = {x['key']: x for x in v2_node.logic('v2MoneyBoard', {'revenues': both, 'escrow': [], 'payouts': []}, 'month', NOW)['numbers']}
    assert n2['net']['text'] == '٠ ج' and n2['income']['text'] == '٠', 'العكس بيرجّع الدخل والصافي'


# ═══════════════════════════════════════════ ٣) «اعتُمد اليوم»
def _recent(fid, status='delivered', **kw):
    f = {'id': fid, 'title': 'فاتورة تصميم لم تُدفع', 'status': status, 'amount': 500, 'currency': 'EGP', 'expert_amount': 300,
         'expert_name': 'خبير', 'client_first_name': 'منى', 'file_no': 1007, 'delivered_at': TODAY}
    f.update(kw)
    return {'apiKind': 'expert_file', 'apiId': fid, 'efLane': 'recent', 'ef': f, 'fyi': True, 'needsAttention': False, 'out': 'رأي اعتُمد', 'who': 'منى'}


@needs_node
def test_approved_today_counts_from_the_recent_lane_only_for_today():
    rows = [_recent('a'), _recent('b', review={'approved_at': TODAY, 'submitted_at': YESTERDAY}),
            _recent('c', delivered_at=YESTERDAY), _recent('d', status='closed', delivered_at=YESTERDAY, closed_at=TODAY),
            _recent('e', status='refunded', refund_reason='reversed', delivered_at=TODAY)]
    T = v2_node.logic('v2Tickets', rows, {'now': NOW})
    assert T['counts']['done'] == 2 and T['counts']['review'] == 0 and T['counts']['late'] == 0 and T['counts']['with'] == 0
    assert {t['row']['ef']['id'] for t in T['cols']['done']} == {'a', 'b'}
    assert all(t['strip']['label'] == 'اعتُمد اليوم' for t in T['cols']['done'])


@needs_node
def test_file_sheet_says_what_happened_in_plain_arabic():
    f = {'id': 'x', 'title': 'فاتورة', 'status': 'closed', 'amount': 500, 'currency': 'EGP', 'expert_amount': 300, 'expert_name': 'خبير',
         'client_first_name': 'منى', 'file_no': 1007, 'delivered_at': YESTERDAY, 'closed_at': TODAY, 'closed_by': 'client_ok'}
    vm = v2_node.logic('v2FileSheet', f)
    rows = {r['k']: r['v'] for r in vm['rows']}
    assert vm['canReverse'] is True and vm['reversed'] is False
    assert rows['رقم الملف'] == '١٠٠٧' and rows['المبلغ'] == '٥٠٠ ج' and rows['أجر الخبير'] == '٣٠٠ ج'
    assert rows['الإغلاق'] == '١٧ نوفمبر ٢٠٢٦، بتأكيد صاحب الطلب' and rows['الحالة'] == 'مغلق'
    rv = v2_node.logic('v2FileSheet', dict(f, status='refunded', refund_reason='reversed', refunded_at=TODAY,
                                            reversal={'reason': 'تجربة الرحلة الكاملة', 'at': TODAY, 'money_back': 'outside_platform'}))
    rrows = {r['k']: r['v'] for r in rv['rows']}
    assert rv['canReverse'] is False and rv['reversed'] is True and rrows['الحالة'] == 'عُكس وأُعيد المبلغ' and rrows['سبب العكس'] == 'تجربة الرحلة الكاملة'
    for t in [r['k'] for r in vm['rows'] + rv['rows']] + [r['v'] for r in vm['rows'] + rv['rows'] if r['k'] != 'سبب العكس'] + [vm['note'], rv['note']]:
        assert not LATIN.search(t), t
        assert not re.search(r'·\s*[٠-٩]|[٠-٩]\s*·', t), t


# ═══════════════════════════════════════════ ٤) الواجهة: الورقة بمرحلتين والأماكن اللي بتفتحها
def test_reverse_sheet_is_two_steps_and_says_exactly_what_happens():
    d3 = _read('dashboard-cloud', 'v2-d3.js')
    for s in ('اعكس الملف وارجع الفلوس', 'يدويًا خارج المنصة', 'ولا يُضاف شيء إلى محفظة صاحب الطلب على المنصة', 'يُخصم أجر الخبير',
              'تتحمّل المنصة المبلغ', 'ينقص الدخل في «الفلوس» بمقدار', 'ولا تُرسل رسائل بريد', 'راجع العكس', 'تأكيد أخير: عكس الملف لا يُتراجع عنه.',
              'أكّد العكس', "'/v2/expert-files/' + encodeURIComponent(fileId)", "body: { reason: reason, confirmed: true }", 'D3.openReverse = openReverse',
              "held: function () { return '/v2/money/held'; }"):
        assert s in d3, s
    d2 = _read('dashboard-cloud', 'v2-d2.js')
    assert 'data-a="fsheet"' in d2 and 'V2D3.openReverse(' in d2 and 'أُغلقت مؤخرًا' in d2 and "t.row.efLane === 'recent'" in d2
    idx = _read('dashboard-cloud', 'index.html')
    assert "data-a=\"ef_reverse\"" in idx and 'V2D3.openReverse(f.id||i.apiId,efRefreshInbox)' in idx
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert '/platform-expert-files?status=recent' in api and 'EP.data.efRecent' in api
    assert 'COPY backend/v2_expert_money_routes.py /app/v2_expert_money_routes.py' in _read('Dockerfile')


def test_recent_rows_never_enter_the_inbox():
    api = _read('dashboard-cloud', 'dashboard-api.js')
    block = api[api.index('jobs.push(get("/platform-expert-files?status=recent")'):]
    block = block[:block.index('}));') + 4]
    assert 'realRows' not in block, 'حارة «recent» مش بنود قرار — برّه الوارد'
