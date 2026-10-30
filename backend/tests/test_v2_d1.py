# -*- coding: utf-8 -*-
"""اللوحة الجديدة (D1) ورا مفتاح مقفول — الخادم + الملفات + المنطق النقي.

Run:  cd backend && python3 -B -m pytest -q tests/test_v2_d1.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/v2_fixtures.V2Platform` فوق `EFPlatform` وأشكال `fake_platform.py`)،
وأي عنوان برّه `https://platform.test` بيتسجّل ويوقع الاختبار. المنطق النقي بيتشغّل في node (مدخلات JSON، مفيش DOM).

اللي بيثبّته:
  ١. `GET /api/v2/config`: افتراضه مقفول · `true`/`1` (أي حالة حروف) بيفتح · غير الأدمن ٤٠٣ · من غير توكن ٤٠١.
  ٢. `POST /api/platform-wallet-payouts/<id>/settle|reject`: أدمن بس · `confirmed:true` ومرجع/سبب لازمين وبحدّهم ·
     المسار والجسم للمنصة بالحرف (`reference` / `reason`) · نداء واحد · السجل بالفاعل والمبلغ من رد المنصة ·
     أخطاء المنصة بالعربي · رد ضاع ⇒ «ما وصلناش رد» من غير إعادة محاولة.
  ٣. الـDockerfile بالملفات الجديدة + صور المربّعات موجودة + `serve_frontend` بيخدم مسارات متداخلة.
  ٤. المفتاح مقفول = `index.html` بنفس القائمة (اللوحة بتتدخل وقت الإقلاع بس).
  ٥. المنطق (node): الترتيب · عدّادات المربّعات من الطابور · «تعذّر» مش صفر · جملة المراجعة في تحويل الأرباح ·
     المراجعة/النزاع/الدورة/الكتاب من غير اعتماد بضغطة · نص عربي من غير «AI/ذكاء» في بداية عنوان.
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
import v2_fixtures as v2fx   # noqa: E402
import v2_node               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')


# ---------------------------------------------------------------- أدوات

class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload).encode() if payload is not None else b''
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
        heads = {r: _bearer(_mkuser('v2-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser('v2-admin@x.test', 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    """`requests.request` البديل: يسجّل كل نداء ويرد من `V2Platform`. أي عنوان برّه المنصة المزيّفة ⇒ ممنوع."""

    def __init__(self):
        self.ef = v2fx.V2Platform()
        self.seen = []
        self.blocked = []
        self.raise_exc = None

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method, 'url': url, 'params': params, 'json': copy.deepcopy(json),
                          'headers': dict(headers or {}), 'timeout': timeout})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        if self.raise_exc is not None:
            raise self.raise_exc
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        if out is None:
            return _Resp(200, [])
        return _Resp(*out)


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    yield p
    assert p.blocked == [], 'طلب لسيرفر حقيقي: %r' % p.blocked


def _call(ctx, method, path, body=None, role='admin'):
    c = ctx['client']
    h = ctx['heads'][role] if role else {}
    if method == 'GET':
        return c.get(path, headers=h)
    return c.post(path, headers=h, json=body if body is not None else {})


def _audits(action, target=None):
    with flask_app.app_context():
        q = AuditLog.query.filter(AuditLog.action == action)
        if target is not None:
            q = q.filter(AuditLog.target == target)
        return [(r.actor_email, r.target, json.loads(r.meta_json) if r.meta_json else None)
                for r in q.order_by(AuditLog.id).all()]


@pytest.fixture(autouse=True)
def _fresh_audits():
    with flask_app.app_context():
        AuditLog.query.filter(AuditLog.action.like('wallet_payout.%')).delete(synchronize_session=False)
        db.session.commit()
    yield


# ---------------------------------------------------------------- ١) مفتاح اللوحة

def test_config_defaults_to_off(ctx, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    r = _call(ctx, 'GET', '/api/v2/config')
    assert r.status_code == 200 and r.get_json() == {'enabled': False}


@pytest.mark.parametrize('val,expected', [
    ('true', True), ('TRUE', True), ('True', True), ('1', True), (' true ', True), (' 1 ', True),
    ('', False), ('0', False), ('false', False), ('no', False), ('yes', False), ('on', False), ('2', False)])
def test_config_reads_the_env_at_request_time(ctx, monkeypatch, val, expected):
    monkeypatch.setenv('DASH_V2_ENABLED', val)
    r = _call(ctx, 'GET', '/api/v2/config')
    assert r.status_code == 200 and r.get_json() == {'enabled': expected}


@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_config_is_admin_only_even_when_on(ctx, monkeypatch, role):
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    r = _call(ctx, 'GET', '/api/v2/config', role=role)
    assert r.status_code == 403
    assert 'enabled' not in (r.get_json() or {})


def test_config_without_a_token_is_401(ctx, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    assert _call(ctx, 'GET', '/api/v2/config', role=None).status_code == 401


# ---------------------------------------------------------------- ٢) سحوبات الأرباح: سجّل / ارفض

SETTLE = '/api/platform-wallet-payouts/po-1/settle'
REJECT = '/api/platform-wallet-payouts/po-1/reject'
BRIDGE_SETTLE = PLATFORM + '/api/bridge/wallet-payouts/po-1/settle'
BRIDGE_REJECT = PLATFORM + '/api/bridge/wallet-payouts/po-1/reject'


@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
@pytest.mark.parametrize('path', [SETTLE, REJECT])
def test_payout_writes_are_admin_only_and_never_reach_the_platform(ctx, plat, role, path):
    r = _call(ctx, 'POST', path, {'reference': 'x', 'reason': 'x', 'confirmed': True}, role=role)
    assert r.status_code == 403 and plat.seen == []


@pytest.mark.parametrize('path', [SETTLE, REJECT])
def test_payout_writes_without_a_token_are_401(ctx, plat, path):
    assert _call(ctx, 'POST', path, {'confirmed': True}, role=None).status_code == 401 and plat.seen == []


@pytest.mark.parametrize('path,field', [(SETTLE, 'reference'), (REJECT, 'reason')])
@pytest.mark.parametrize('confirmed', [None, False, 'true', 1, 'yes'])
def test_payout_writes_need_the_confirmation_flag(ctx, plat, path, field, confirmed):
    body = {field: 'IP-1'}
    if confirmed is not None:
        body['confirmed'] = confirmed
    r = _call(ctx, 'POST', path, body)
    assert r.status_code == 400 and 'تأكّد' in r.get_json()['error'] and plat.seen == []


@pytest.mark.parametrize('bad', [None, '', '   ', 5, ['x'], {'a': 1}])
def test_settle_needs_a_real_reference(ctx, plat, bad):
    r = _call(ctx, 'POST', SETTLE, {'reference': bad, 'confirmed': True})
    assert r.status_code == 400 and 'مرجع' in r.get_json()['error'] and plat.seen == []


def test_settle_reference_limit_is_120(ctx, plat):
    r = _call(ctx, 'POST', SETTLE, {'reference': 'x' * 121, 'confirmed': True})
    assert r.status_code == 400 and plat.seen == []
    r = _call(ctx, 'POST', SETTLE, {'reference': 'x' * 120, 'confirmed': True})
    assert r.status_code == 200 and len(plat.seen) == 1


@pytest.mark.parametrize('bad', [None, '', '   ', 5, ['x']])
def test_reject_needs_a_reason(ctx, plat, bad):
    r = _call(ctx, 'POST', REJECT, {'reason': bad, 'confirmed': True})
    assert r.status_code == 400 and 'سبب' in r.get_json()['error'] and plat.seen == []


def test_reject_reason_limit_is_500(ctx, plat):
    assert _call(ctx, 'POST', REJECT, {'reason': 'س' * 501, 'confirmed': True}).status_code == 400 and plat.seen == []
    assert _call(ctx, 'POST', REJECT, {'reason': 'س' * 500, 'confirmed': True}).status_code == 200


def test_settle_proxies_to_the_platform_exactly(ctx, plat):
    r = _call(ctx, 'POST', SETTLE, {'reference': '  IP-99120 ', 'confirmed': True, 'by': 'evil@x.test', 'amount': 1})
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] is True and body['payout']['status'] == 'paid'
    assert len(plat.seen) == 1, 'نداء واحد ولا إعادة محاولة'
    call = plat.seen[0]
    assert call['method'] == 'POST' and call['url'] == BRIDGE_SETTLE
    assert call['json'] == {'reference': 'IP-99120'}, 'المبلغ والفاعل مش بيتبعتوا من المتصفح'
    assert call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert plat.ef.settled[0]['reference'] == 'IP-99120'


def test_reject_proxies_to_the_platform_exactly(ctx, plat):
    r = _call(ctx, 'POST', REJECT, {'reason': ' الحساب غير مطابق ', 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['payout']['status'] == 'rejected'
    call = plat.seen[0]
    assert call['url'] == BRIDGE_REJECT and call['json'] == {'reason': 'الحساب غير مطابق'}
    assert len(plat.seen) == 1


def test_settle_writes_the_audit_with_the_actor_and_the_platform_amount(ctx, plat):
    _call(ctx, 'POST', SETTLE, {'reference': 'IP-1', 'confirmed': True})
    rows = _audits('wallet_payout.settle', 'po-1')
    assert len(rows) == 1
    actor, target, meta = rows[0]
    assert actor == 'v2-admin@x.test', 'الفاعل من التوكن'
    assert meta['amount'] == 1200.0 and meta['currency'] == 'EGP' and meta['reference'] == 'IP-1'


def test_reject_writes_the_audit(ctx, plat):
    _call(ctx, 'POST', REJECT, {'reason': 'سبب', 'confirmed': True})
    actor, target, meta = _audits('wallet_payout.reject', 'po-1')[0]
    assert actor == 'v2-admin@x.test' and meta['reason'] == 'سبب' and meta['amount'] == 1200.0


def test_a_payout_already_decided_passes_the_platforms_arabic_message_and_writes_no_audit(ctx, plat):
    assert _call(ctx, 'POST', SETTLE, {'reference': 'A', 'confirmed': True}).status_code == 200
    r = _call(ctx, 'POST', SETTLE, {'reference': 'B', 'confirmed': True})
    assert r.status_code == 409 and r.get_json() == {'error': 'طلب السحب محسوم بالفعل (paid)'}
    assert len(_audits('wallet_payout.settle', 'po-1')) == 1


def test_unknown_payout_is_the_platforms_404_in_arabic(ctx, plat):
    r = _call(ctx, 'POST', '/api/platform-wallet-payouts/po-999/settle', {'reference': 'A', 'confirmed': True})
    assert r.status_code == 404 and r.get_json() == {'error': 'طلب السحب غير موجود'}
    assert _audits('wallet_payout.settle', 'po-999') == []


@pytest.mark.parametrize('weird', ['a%20b', 'x.y', 'a%3Fb'])
def test_a_malformed_id_never_reaches_the_platform(ctx, plat, weird):
    r = _call(ctx, 'POST', '/api/platform-wallet-payouts/%s/settle' % weird, {'reference': 'A', 'confirmed': True})
    assert r.status_code == 404 and plat.seen == []


def test_english_platform_errors_are_translated(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/wallet-payouts/po-1/settle')] = (503, {'detail': 'Database not available'})
    r = _call(ctx, 'POST', SETTLE, {'reference': 'A', 'confirmed': True})
    out = r.get_json()
    assert not re.search(r'[A-Za-z]{4,}', out['error']), out
    assert len(plat.seen) == 1, 'ولا إعادة محاولة'


def test_a_lost_reply_is_no_reply_not_a_rejection_and_is_logged(ctx, plat):
    plat.raise_exc = RuntimeError('timeout')
    plat.raise_exc = __import__('requests').exceptions.ConnectionError('down')
    r = _call(ctx, 'POST', SETTLE, {'reference': 'A', 'confirmed': True})
    out = r.get_json()
    assert r.status_code == 502 and out['no_reply'] is True and 'ما وصلناش رد' in out['error']
    assert len(plat.seen) == 1
    assert _audits('wallet_payout.no_reply', 'po-1')[0][2] == {'attempt': 'settle'}
    assert _audits('wallet_payout.settle', 'po-1') == []


def test_a_recorded_reject_with_a_failed_recredit_keeps_the_platforms_instruction(ctx, plat):
    msg = 'سُجّل الرفض لكن تعذّر إرجاع المبلغ للمحفظة — أعد تنفيذ الرفض نفسه لإكمال الإرجاع.'
    plat.ef.forced[('POST', '/api/bridge/wallet-payouts/po-1/reject')] = (500, {'detail': msg})
    r = _call(ctx, 'POST', REJECT, {'reason': 'سبب', 'confirmed': True})
    assert r.status_code == 500 and r.get_json() == {'error': msg}
    assert len(_audits('wallet_payout.reject_incomplete', 'po-1')) == 1


def test_the_read_list_is_untouched(ctx, plat):
    r = _call(ctx, 'GET', '/api/platform-wallet-payouts')
    assert r.status_code == 200 and r.get_json()['count'] == 2
    assert plat.seen[0]['params'] == {'status': 'pending'}


# ---------------------------------------------------------------- ٣) الملفات والنشر

def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


@pytest.mark.parametrize('dockerfile', ['Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')])
def test_dockerfiles_ship_the_new_files(dockerfile):
    txt = _read(dockerfile)
    for f in ('dashboard-cloud/v2-logic.js', 'dashboard-cloud/v2-home.js', 'dashboard-cloud/v2-home.css'):
        assert f in txt, (dockerfile, f)
    assert 'COPY dashboard-cloud/v2/img /app/dist/v2/img' in txt
    assert 'dashboard-cloud/index.html dashboard-cloud/dashboard-api.js dashboard-cloud/site-content.js' in txt


def test_every_tile_image_and_the_avatar_exist():
    for name in ('files', 'disputes', 'courses', 'market', 'books', 'people', 'money', 'content', 'marketing',
                 'reports', 'brain', 'company', 'brain-avatar'):
        p = os.path.join(DC, 'v2', 'img', name + '.jpg')
        assert os.path.isfile(p) and os.path.getsize(p) > 1000, name


def test_the_frontend_route_serves_nested_files(tmp_path, monkeypatch):
    import app as appmod
    dist = tmp_path / 'dist'
    (dist / 'v2' / 'img').mkdir(parents=True)
    (dist / 'index.html').write_text('<html>INDEX</html>', encoding='utf-8')
    (dist / 'v2' / 'img' / 'files.jpg').write_bytes(b'\xff\xd8\xffJPEGDATA')
    (dist / 'v2-home.js').write_text('/*js*/', encoding='utf-8')
    monkeypatch.setattr(appmod, '__file__', str(tmp_path / 'app.py'))
    c = flask_app.test_client()
    r = c.get('/v2/img/files.jpg')
    assert r.status_code == 200 and r.data == b'\xff\xd8\xffJPEGDATA' and r.mimetype == 'image/jpeg'
    assert c.get('/v2-home.js').data == b'/*js*/'
    assert b'INDEX' in c.get('/v2/img/nope.jpg').data            # غير موجود ⇒ index (سلوك SPA القديم)
    r = c.get('/v2/img/../../app.py')
    assert b'INDEX' in r.data or r.status_code in (400, 404)     # مفيش خروج من المجلد


# ---------------------------------------------------------------- ٤) المفتاح مقفول = نفس الصفحة

def test_the_closed_switch_leaves_the_menu_declaration_untouched():
    html = _read('dashboard-cloud', 'index.html')
    body = html[html.index('const MODULES={'):html.index('const CO_PINNED=')]
    assert 'home:' not in body, 'اللوحة بتتدخل وقت الإقلاع لما المفتاح يفتح — مش في الإعلان'
    assert 'window.V2_ON=false;' in html
    assert "EP.api('/v2/config')" in html
    assert 'v2-logic.js' in html and 'v2-home.js' in html and 'v2-home.css' in html
    # الإقلاع: السؤال قبل renderNav، وفشله/تأخيره/٤٠٣ = مقفول.
    boot = html[html.index('window.EP_BOOT=function(){'):html.index('function epBootCore(){')]
    assert "EP.role==='admin'" in boot and 'v2LoadFlag(epBootCore)' in boot
    flag = html[html.index('function v2LoadFlag'):html.index('window.EP_BOOT=function(){')]
    assert 'fin(false)' in flag and 'setTimeout' in flag and 'r.enabled===true' in flag
    assert "if(current==='home'&&window.V2_ON&&window.V2)return V2.render(v);" in html


# ---------------------------------------------------------------- ٥) المنطق (node)

NOW = 1793361600000          # 2026-10-30T12:00:00Z
H = 3600e3


def _iso(hours_ago):
    return datetime.datetime.fromtimestamp((NOW - hours_ago * H) / 1000.0, datetime.timezone.utc).isoformat()


QUEUE = {
    'expert_files_late': 1, 'expert_files_assign_overdue': 2, 'expert_files_in_review': 3, 'expert_files_awaiting_assignment': 4,
    'expert_files_blocked': 5, 'expert_files_disputed': 1, 'expert_files_case_disputed': 2, 'consultation_disputes': 3,
    'consultations_legacy': 4, 'manual_refunds_pending': 5, 'expert_files_unactivated': 6,
    'courses_pending': {'count': 2, 'titles': ['أ', 'ب']}, 'trainer_applications_pending': {'count': 3},
    'live_needs_decision': [{'title': 'ورشة'}],
    'wallet_payouts_pending': {'count': 4, 'total_amount': 9}, 'manual_payments_pending': {'count': 1},
    'stuck_card_payments': {'count': 2}, 'course_split_pending': {'count': 3},
    'topics_drafts': 311, 'testimonials_pending': 4, 'founding_leads_new': {'count': 9},
    'alerts': ['⏰ تنبيه أول', '⚠️ تنبيه ثانٍ'], 'heartbeats': {'tick_last': _iso(1), 'backup_last': None},
}


def _tiles(queue, **extras):
    ex = {'inbox': [], 'inboxFailed': [], 'pendingVisitors': 0, 'invitesAwaiting': 0, 'market': 0, 'now': NOW}
    ex.update(extras)
    return {t['key']: t for t in v2_node.logic('v2Tiles', queue, ex)}


@needs_node
def test_there_are_twelve_tiles_in_the_approved_order_with_their_images():
    t = v2_node.logic('v2Tiles', QUEUE, {'inbox': [], 'now': NOW})
    assert [x['key'] for x in t] == ['files', 'disputes', 'courses', 'market', 'books', 'people', 'money', 'content',
                                      'marketing', 'reports', 'brain', 'company']
    assert [x['img'] for x in t] == [x['key'] for x in t]
    assert [x['label'] for x in t][:3] == ['ملفات الخبراء', 'النزاعات والاستردادات', 'الدورات والمدرّبون']


@needs_node
def test_tile_counts_come_straight_from_the_queue():
    t = _tiles(QUEUE, market=7, pendingVisitors=2, invitesAwaiting=3,
               inbox=[{'apiKind': 'book', 'ref': 'K1'}, {'apiKind': 'book', 'ref': 'K2'}, {'apiKind': 'join', 'ref': 'J1'}])
    # الملفات: متأخر (١+٢) + تنتظر مراجعتك ٣ + تنتظر توزيع ٤ + فلوس واقفة ٥
    assert t['files']['count'] == 15 and t['files']['hot'] is True
    assert t['files']['next'] == '٣ متأخر · ٣ تنتظر مراجعتك · ٤ تنتظر خبيرًا · ٥ فلوسها واقفة'
    # النزاعات: ملفات ١ + قضايا ٢ + استشارات ٣ + قديمة ٤ + استرداد ٥ + دفع بلا ملف ٦
    assert t['disputes']['count'] == 21 and t['disputes']['hot'] is True
    assert t['courses']['count'] == 2 + 3 + 1 and t['courses']['dest'] == 'courses'
    assert t['market']['count'] == 7
    assert t['books']['count'] == 2 and t['books']['dest'] == 'knowledge'
    # الناس: زوّار ٢ + دعوات ٣ + انضمام ١ + خبراء مؤسسون ٩
    assert t['people']['count'] == 15 and t['people']['partial'] is False and t['people']['dest'] == 'invites'
    # الفلوس: تحويلات ٤ + إيصالات ١ + عالقة ٢ + اقتسام ٣ — الأحمر لما فيه عالق
    assert t['money']['count'] == 10 and t['money']['hot'] is True and t['money']['dest'] == 'finance'
    assert t['content']['count'] == 315 and t['content']['dest'] == 'topics'
    for k, dest in (('marketing', 'marketing'), ('reports', 'analysis'), ('company', 'investment')):
        assert t[k]['count'] is None and t[k]['failed'] is False and t[k]['dest'] == dest


@needs_node
def test_hot_means_the_first_part_is_positive_only():
    q = dict(QUEUE, expert_files_late=0, expert_files_assign_overdue=0, expert_files_disputed=0, expert_files_case_disputed=0,
             consultation_disputes=0, stuck_card_payments={'count': 0})
    t = _tiles(q)
    assert t['files']['hot'] is False and t['files']['count'] == 12
    assert t['disputes']['hot'] is False and t['disputes']['count'] == 15
    assert t['money']['hot'] is False


@needs_node
def test_a_zero_count_has_no_circle_and_a_one_part_line_stays_plain():
    t = _tiles({'alerts': [], 'heartbeats': {}})
    for k in ('files', 'disputes', 'courses', 'money', 'content'):
        assert t[k]['count'] == 0 and t[k]['failed'] is False and t[k]['hot'] is False
    assert t['files']['next'] == 'كل شيء يسير في موعده'


@needs_node
def test_a_failed_loader_is_unknown_not_zero():
    t = _tiles(None, inbox=None, pendingVisitors=None, invitesAwaiting=None, market=None)
    for k in ('files', 'disputes', 'courses', 'money', 'content', 'books', 'people', 'market', 'brain'):
        assert t[k]['failed'] is True and t[k]['count'] is None, k
        assert t[k]['next'] == 'تعذّر الجلب', k
        assert t[k]['hot'] is False


@needs_node
def test_a_missing_market_bridge_hides_the_number_without_calling_it_a_failure():
    t = _tiles(QUEUE, market=None)
    assert t['market']['failed'] is True
    t = v2_node.logic('v2Tiles', QUEUE, {'inbox': [], 'inboxFailed': [], 'pendingVisitors': 0, 'invitesAwaiting': 0, 'now': NOW})
    m = {x['key']: x for x in t}['market']
    assert m['count'] is None and m['failed'] is False


@needs_node
def test_books_fail_when_their_queue_failed_even_if_the_inbox_arrived():
    t = _tiles(QUEUE, inbox=[], inboxFailed=['سوق المعرفة'])
    assert t['books']['failed'] is True and t['books']['count'] is None
    assert t['files']['failed'] is False


@needs_node
def test_people_total_is_marked_partial_when_one_source_is_missing():
    t = _tiles(QUEUE, pendingVisitors=None, invitesAwaiting=2, inbox=[])
    assert t['people']['partial'] is True and t['people']['failed'] is False
    assert t['people']['count'] == 2 + 0 + 9               # المعروف بس — ومعلَن إنه ناقص
    assert 'ناقص' in t['people']['next']
    t = _tiles(None, pendingVisitors=None, invitesAwaiting=None, inbox=None)
    assert t['people']['failed'] is True


BRAIN_ROW = {'apiKind': 'expert_file', 'efLane': 'waiting', 'ef': {
    'id': 'f1', 'title': 'ملف اختبار', 'status': 'assigned', 'candidates': [{'email': 'n@x', 'name': 'د. ندى'}],
    'assign_log': [
        {'at': '2026-10-30T03:00:00+00:00', 'to': 'n@x', 'by': 'auto', 'reason': 'paid', 'why': 'نفس بلد القانون'},
        {'at': '2026-10-30T09:00:00+00:00', 'to': 'h@x', 'by': 'auto', 'reason': 'declined', 'why': ''},
        {'at': '2026-10-30T08:00:00+00:00', 'to': 'n@x', 'by': 'founder', 'reason': 'manual', 'why': ''},
        {'at': '2026-10-29T22:00:00+00:00', 'to': 'n@x', 'by': 'auto', 'reason': 'paid', 'why': ''}]}}


@needs_node
def test_the_brain_tile_counts_only_todays_automatic_assignments():
    t = _tiles(QUEUE, inbox=[BRAIN_ROW, BRAIN_ROW])               # نفس الملف مرتين ⇒ ما يتعدّش مرتين
    assert t['brain']['count'] == 2 and t['brain']['internal'] is True
    assert t['brain']['next'] == 'وزّع ملفين وحده اليوم'
    log = v2_node.logic('v2BrainLog', [BRAIN_ROW], NOW)
    assert [e['who'] for e in log] == ['h@x', 'د. ندى'], 'الأحدث أولًا، والاسم من المرشّحين'
    assert all('اعكس' not in json.dumps(e, ensure_ascii=False) for e in log)
    assert _tiles(QUEUE, inbox=[])['brain']['next'] == 'لم يوزّع شيئًا اليوم'


# —— البطاقات والترتيب (من صفوف الوارد الحقيقية)

@pytest.fixture(scope='module')
def real(ctx):
    """صفوف الوارد الحقيقية: dashboard-api.js جوه node على ردود الداشبورد نفسه فوق المنصة المزيّفة."""
    if not v2_node.NODE:
        pytest.skip('needs node')
    import app as appmod
    mp = pytest.MonkeyPatch()
    p = Plat()
    mp.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    mp.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    mp.setattr(appmod.requests, 'request', p)
    # طلبات المدرّبين بتنادي `requests.get` مباشرةً (مش `_platform_proxy`) ⇒ نفس المنصة المزيّفة.
    mp.setattr(appmod.requests, 'get', lambda url, **kw: p('GET', url, params=kw.get('params'), json=None,
                                                          headers=kw.get('headers'), timeout=kw.get('timeout')))
    try:
        out = v2_node.real_rows(ctx['client'], ctx['heads']['admin'])
    finally:
        mp.undo()
    assert p.blocked == []
    return out


def _decisions(real, **opts):
    o = {'now': NOW, 'inboxFailed': real['failed']}
    o.update(opts)
    payouts = real['data']['walletPayouts']['rows']
    return v2_node.logic('v2Decisions', [r for r in real['inbox'] if not r.get('fyi')], payouts, real['data']['opsQueue'], o)


@needs_node
def test_the_real_pipeline_loads_every_source(real):
    assert real['failed'] == [], real['failed']
    assert all(real['state'][k] == 'ready' for k in ('opsQueue', 'inbox', 'walletPayouts', 'invites', 'pendingUsers', 'market'))
    kinds = {r.get('apiKind') for r in real['inbox']}
    assert {'expert_file', 'dispute', 'manual_payment', 'trainer', 'pending_user', 'founding', 'join', 'book', 'topic',
            'lead', 'legacy'} <= kinds


RANK_ORDER = [  # الترتيب المعتمد: ملفات عاجلة/عادية ⇐ نزاعات ⇐ استردادات ⇐ تحويلات ⇐ إيصالات ⇐ آراء ⇐ مدرّبون/انضمام ⇐ زوّار ⇐ مؤسسون ⇐ محتوى ⇐ رسائل
    ('file_late', 'file_attention'), ('file_waiting',), ('dispute',), ('unactivated', 'legacy'), ('payout',),
    ('manual_payment',), ('review',), ('trainer', 'join'), ('pending_user',), ('founding',),
    ('book', 'topic', 'program', 'creative', 'verify', 'course', 'live'), ('lead', 'message', 'open_message', 'other')]


@needs_node
def test_decisions_follow_the_approved_order(real):
    cards = _decisions(real)
    assert len(cards) > 15
    pos = {}
    for i, grp in enumerate(RANK_ORDER):
        for k in grp:
            pos[k] = i
    seq = [pos[c['kind']] for c in cards]
    # الملف العادي المنتظر ممكن يتقدّم لمجموعة العاجل لو ميعاده فات — كل واحد يبقى في مجموعته أو اللي قبلها بس
    groups = [c['group'] for c in cards]
    assert groups == sorted(groups), 'المجموعات مرتّبة تصاعديًّا'
    kinds_in_order = []
    for c in cards:
        if c['kind'] not in kinds_in_order:
            kinds_in_order.append(c['kind'])
    # كل نوع بيظهر مرة واحدة ككتلة (مفيش نوع متقطّع)
    assert [c['kind'] for c in cards] == [k for k in (c['kind'] for c in cards)]
    last = -1
    for c in cards:
        grp = pos[c['kind']]
        assert grp >= last - 1 or c['kind'] == 'file_waiting', (c['kind'], seq)
        last = max(last, grp)
    first = cards[0]
    assert first['kind'] in ('file_late', 'file_attention', 'file_waiting')
    assert first['group'] == 10, 'أول بطاقة عاجلة'


@needs_node
def test_the_known_kinds_come_in_the_approved_relative_order(real):
    cards = _decisions(real)
    first_at = {}
    for i, c in enumerate(cards):
        first_at.setdefault(c['kind'], i)
    seq = ['dispute', 'unactivated', 'payout', 'manual_payment', 'review', 'trainer', 'pending_user', 'founding', 'book', 'lead']
    present = [k for k in seq if k in first_at]
    assert present == ['dispute', 'unactivated', 'payout', 'manual_payment', 'review', 'trainer', 'pending_user', 'founding', 'book', 'lead']
    assert [first_at[k] for k in present] == sorted(first_at[k] for k in present)
    assert first_at['legacy'] > first_at['dispute'] and first_at['legacy'] < first_at['payout']
    assert first_at['join'] > first_at['review'] and first_at['join'] < first_at['pending_user']


@needs_node
def test_within_a_group_the_oldest_comes_first(real):
    cards = _decisions(real)
    by_group = {}
    for c in cards:
        by_group.setdefault(c['group'], []).append(c)
    checked = 0
    for g, lst in by_group.items():
        stamps = [c['ts'] for c in lst if c['ts'] is not None]
        assert stamps == sorted(stamps), (g, [(c['kind'], c['ts']) for c in lst])
        # المجهول (null) بعد المعروف
        flags = [c['ts'] is None for c in lst]
        assert flags == sorted(flags), g
        checked += len(stamps)
    assert checked > 10


@needs_node
def test_oldest_first_on_a_hand_built_group():
    mk = lambda i, h: {'apiKind': 'expert_file', 'apiId': i, 'efLane': 'waiting', 'ref': i, 'who': 'م',
                       'ef': {'id': i, 'title': 't' + i, 'status': 'awaiting_assignment', 'hours_left': 5,
                              'paid_at': _iso(h), 'candidates': []}}
    cards = v2_node.logic('v2Decisions', [mk('a', 2), mk('b', 30), mk('c', 10)], [], None, {'now': NOW, 'inboxFailed': []})
    assert [c['title'] for c in cards] == ['tb', 'tc', 'ta']


@needs_node
def test_card_ids_are_unique_and_every_card_has_an_action(real):
    cards = _decisions(real)
    ids = [c['id'] for c in cards]
    assert len(ids) == len(set(ids))
    for c in cards:
        assert c['primary'] and c['primary']['label'] and c['primary']['act']['do'], c['kind']
        assert c['tag'] and c['title'] and c['brain'], c['kind']
        assert c['img'] in {'files', 'disputes', 'courses', 'market', 'books', 'people', 'money', 'content'}, c['kind']


READ_FIRST = ('review', 'dispute', 'unactivated', 'legacy', 'book', 'program', 'topic', 'creative', 'verify', 'course', 'live',
              'file_attention')
DECIDING = ('send', 'decide', 'resolve', 'payout_settle', 'pay_confirm', 'payout_reject', 'pay_reject')


@needs_node
def test_things_that_need_reading_are_never_a_one_click_approve(real):
    cards = _decisions(real)
    seen = set()
    for c in cards:
        if c['kind'] in READ_FIRST:
            seen.add(c['kind'])
            assert c['primary']['act']['do'] in ('open', 'goto'), c['kind']
            assert 'افتح' in c['primary']['label'], c['kind']
            assert c['secondary'] is None or c['secondary']['act']['do'] in ('open', 'goto'), c['kind']
    assert {'review', 'dispute', 'unactivated', 'legacy', 'book', 'topic', 'course', 'live'} <= seen
    labels = {c['kind']: c['primary']['label'] for c in cards if c['kind'] in ('review', 'dispute')}
    assert labels['review'] == 'افتح وراجع' and labels['dispute'] == 'افتح النزاع'


@needs_node
def test_a_suspicious_visitor_and_an_unlicensed_applicant_are_opened_not_approved(real):
    cards = _decisions(real)
    visitors = [c for c in cards if c['kind'] == 'pending_user']
    assert visitors
    flagged = [c for c in visitors if c['warn']]
    plain = [c for c in visitors if not c['warn']]
    assert flagged and all(c['primary']['act']['do'] == 'open' for c in flagged)
    assert plain and all(c['primary']['act'] == {'do': 'decide', 'action': 'approve'} for c in plain)
    row = {'apiKind': 'join', 'apiId': 'j', 'ref': 'JR-j', 'who': 'م', 'licenceMissing': True, 'licensed': True, 'note': 'x'}
    c = v2_node.logic('v2Card', row, {'now': NOW})
    assert c['primary']['act']['do'] == 'open' and c['warn']


@needs_node
def test_money_buttons_carry_the_amount_currency_and_name_for_the_confirmation(real):
    cards = _decisions(real)
    pay = [c for c in cards if c['kind'] == 'payout']
    man = [c for c in cards if c['kind'] == 'manual_payment']
    assert len(pay) == 2 and len(man) == 2
    for c in pay + man:
        m = c['primary']['money']
        assert m['amount'] and m['currency'] and m['curName'] and m['name'], c['kind']
        assert c['secondary']['money'] == m
    assert [c['row']['pid'] for c in pay] == ['po-2', 'po-1'], 'الأقدم أولًا (٣٠ ساعة قبل ٩)'
    assert pay[1]['primary']['act'] == {'do': 'payout_settle', 'id': 'po-1'}
    assert pay[1]['secondary']['act'] == {'do': 'payout_reject', 'id': 'po-1'}
    assert pay[1]['primary']['label'] == 'سجّل التحويل' and pay[1]['secondary']['label'] == 'ارفض'
    assert man[0]['primary']['label'] == 'أكّد الدفع' and man[0]['primary']['act']['do'] == 'pay_confirm'
    sar = [c for c in pay if c['primary']['money']['currency'] == 'SAR'][0]
    assert sar['primary']['money']['curName'] == 'ريال' and 'الصرف' in sar['warn']
    assert any(c['link'] and c['link']['url'].startswith('https://') for c in man)


PAYOUT = {'kind': 'payout', 'pid': 'po-9', 'who': 'د. هالة', 'email': 'hala@example.test', 'amount': 1200, 'currency': 'EGP',
          'dest': 'hala@instapay', 'status': 'pending', 'fx_alert': False, 'raw': {'method': 'إنستاباي', 'created_at': _iso(5)}}
DISPUTE_ROW = {'apiKind': 'dispute', 'dsrc': 'file', 'apiId': 'd1', 'ref': 'DSP-1', 'who': 'منى',
               'ef': {'id': 'd1', 'title': 'عقد', 'expert_email': 'hala@example.test', 'dispute': {'at': _iso(3)}}}


def _payout_card(rows, failed):
    out = v2_node.logic('v2Decisions', rows, [PAYOUT], None, {'now': NOW, 'inboxFailed': failed})
    return [c for c in out if c['kind'] == 'payout'][0]


@needs_node
def test_the_payout_review_sentence_appears_only_when_it_was_really_checked():
    c = _payout_card([], [])
    assert 'روجعت مع النزاعات والاستردادات' in c['reason'] and c['warn'] == ''
    # الفحص ماقدرش (الوارد وقع / طابور النزاعات تعذّر / مفيش بيان بالأعطال) ⇒ الجملة تتشال
    for failed in (None, ['نزاعات الملفات'], ['نزاعات الاستشارات'], ['قضايا فيها ملاحظة']):
        c = _payout_card([], failed)
        assert c['reason'] == '', failed
    out = v2_node.logic('v2Decisions', None, [PAYOUT], None, {'now': NOW, 'inboxFailed': []})
    assert [x for x in out if x['kind'] == 'payout'][0]['reason'] == ''
    # نزاع مفتوح على نفس الشخص ⇒ الجملة تتشال وبيتحذّر
    c = _payout_card([DISPUTE_ROW], [])
    assert 'روجعت' not in c['reason'] and 'نزاع مفتوح' in c['warn']


@needs_node
def test_a_file_card_suggests_the_auto_pick_with_a_plain_reason():
    row = {'apiKind': 'expert_file', 'apiId': 'f', 'efLane': 'waiting', 'ref': 'EF-f', 'who': 'منى', 'amountLabel': '٧٥٠ جنيه',
           'ef': {'id': 'f', 'title': 'مراجعة عقد', 'status': 'awaiting_assignment', 'kind': 'contract', 'hours_left': 40, 'paid_at': _iso(2),
                  'candidates': [{'email': 'a@x', 'name': 'أ. أولى', 'auto_pick': False, 'declined': True},
                                 {'email': 'b@x', 'name': 'أ. ثانية', 'auto_pick': True, 'same_specialty': True, 'same_country': True,
                                  'reviews_contracts': True, 'load': 2}]}}
    c = v2_node.logic('v2Card', row, {'now': NOW})
    assert c['kind'] == 'file_waiting' and c['tag'] == 'ملف ينتظر خبيرًا'
    assert c['brain'] == 'أقترح أ. ثانية'
    assert c['reason'] == 'يراجع العقود · نفس التخصص · نفس بلد القانون · لديه ملفان مفتوحان'
    assert c['primary'] == {'label': 'أرسله إلى أ. ثانية', 'act': {'do': 'send', 'email': 'b@x', 'name': 'أ. ثانية'}}
    assert c['secondary']['label'] == 'افتح الملف'
    # مفيش مرشّح مؤهّل ⇒ «لا يوجد خبير متاح» وزرّ الفتح
    row['ef']['candidates'] = [{'email': 'a@x', 'name': 'أ', 'auto_pick': False, 'eligible': False}]
    c = v2_node.logic('v2Card', row, {'now': NOW})
    assert c['brain'] == 'لا يوجد خبير متاح' and c['primary']['act']['do'] == 'open' and c['primary']['label'] == 'افتح الملف'


@needs_node
def test_a_late_file_suggests_moving_it_and_says_how_late():
    row = {'apiKind': 'expert_file', 'apiId': 'f', 'efLane': 'late', 'ref': 'EF-f', 'who': 'منى',
           'ef': {'id': 'f', 'title': 'رأي', 'status': 'writing', 'expert_name': 'أ. بطيء', 'writing_due_at': _iso(5),
                  'candidates': [{'email': 'n@x', 'name': 'د. ندى', 'auto_pick': True, 'load': 0, 'same_country': True}]}}
    c = v2_node.logic('v2Card', row, {'now': NOW})
    assert c['kind'] == 'file_late' and c['tag'] == 'ملف متأخر' and c['group'] == 10
    assert c['brain'] == 'متأخر ٥ ساعات عند أ. بطيء. أقترح نقله إلى د. ندى'
    assert c['primary']['label'] == 'انقله إلى د. ندى' and c['primary']['act']['do'] == 'send'
    assert 'ليس لديه ملفات مفتوحة' in c['reason']


@needs_node
def test_visible_text_is_plain_arabic_with_no_ai_headline(real):
    cards = _decisions(real)
    tiles = v2_node.logic('v2Tiles', real['data']['opsQueue'], {'inbox': real['inbox'], 'inboxFailed': [], 'pendingVisitors': 1,
                                                              'invitesAwaiting': 1, 'market': 1, 'now': NOW})
    texts = []
    for c in cards:
        texts += [c['tag'], c['title'], c['brain'], c['reason'], c['primary']['label'], (c['secondary'] or {}).get('label', '')]
    for t in tiles:
        texts += [t['label'], t['next']]
    head = re.compile(r'^\s*(AI|A\.I|ذكاء|الذكاء|ذكي)')
    for s in texts:
        assert not head.search(s or ''), s
        for bad in ('undefined', 'NaN', '[object', 'null'):
            assert bad not in (s or ''), (bad, s)
        # مفيش مصطلح تقني ظاهر
        assert not re.search(r'\b(API|JSON|webhook|token|endpoint|bridge)\b', s or '', re.I), s
    for c in cards:
        assert not head.search(c['tag'] + ' ' + c['title']), c['title']


@needs_node
def test_health_lists_the_alerts_and_the_heartbeats():
    h = v2_node.logic('v2Health', QUEUE, NOW)
    assert h['ok'] is False and h['failed'] is False and h['alerts'] == ['⏰ تنبيه أول', '⚠️ تنبيه ثانٍ']
    assert [b['label'] for b in h['heartbeats']] == ['الفحص الدوري', 'النسخ الاحتياطي']
    assert h['heartbeats'][0]['ago'] == 'منذ ساعة' and h['heartbeats'][1]['ago'] == 'لم تعمل بعد'
    assert v2_node.logic('v2Health', {'alerts': [], 'heartbeats': {}}, NOW)['ok'] is True
    assert v2_node.logic('v2Health', None, NOW) == {'ok': False, 'failed': True, 'alerts': [], 'heartbeats': []}


@needs_node
def test_next_is_the_first_card_or_null(real):
    cards = _decisions(real)
    assert v2_node.logic('v2Next', cards)['id'] == cards[0]['id']
    assert v2_node.logic('v2Next', []) is None
    line = v2_node.logic('v2NextLine', cards[0])
    assert cards[0]['tag'] in line and cards[0]['title'] in line


@needs_node
def test_nothing_waiting_yields_no_cards():
    assert v2_node.logic('v2Decisions', [], [], {'alerts': []}, {'now': NOW, 'inboxFailed': []}) == []
    assert v2_node.logic('v2Decisions', None, None, None, {'now': NOW}) == []


@needs_node
def test_other_rows_get_their_plain_cards(real):
    cards = {c['kind']: c for c in _decisions(real)}
    assert cards['trainer']['primary']['label'] == 'اقبله' and cards['trainer']['secondary']['label'] == 'افتح الطلب'
    assert cards['founding']['primary']['label'] == 'تواصلت معه'
    assert cards['lead']['primary'] == {'label': 'تم', 'act': {'do': 'resolve'}}
    assert cards['pending_user']['tag'] == 'زائر ينتظر الفتح'
    assert cards['join']['primary']['label'] in ('اقبل', 'افتح وراجع')
    assert cards['review']['tag'] == 'أول رأي لخبير جديد'
    assert cards['dispute']['tag'] in ('نزاع', 'ملاحظة على قضية')
    assert cards['unactivated']['tag'] == 'دفع بلا ملف'
    assert 'منذ' in cards['payout']['ageText'] or cards['payout']['ageText'] == ''


@needs_node
def test_the_suggestion_is_never_the_expert_who_already_has_the_file():
    row = {'apiKind': 'expert_file', 'apiId': 'f', 'efLane': 'late', 'ref': 'EF-f', 'who': 'منى',
           'ef': {'id': 'f', 'title': 'رأي', 'status': 'writing', 'expert_name': 'أ. بطيء', 'expert_email': 'slow@x',
                  'writing_due_at': _iso(5),
                  'candidates': [{'email': 'slow@x', 'name': 'أ. بطيء', 'auto_pick': True}]}}
    c = v2_node.logic('v2Card', row, {'now': NOW})
    assert c['primary']['act']['do'] == 'open' and 'لا يوجد خبير آخر متاح' in c['brain']


@needs_node
def test_a_dispute_card_reads_gender_neutral():
    c = v2_node.logic('v2Card', DISPUTE_ROW, {'now': NOW})
    assert c['brain'].startswith('اعتراض من منى على «عقد»')
    assert c['primary'] == {'label': 'افتح النزاع', 'act': {'do': 'open'}}
