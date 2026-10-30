# -*- coding: utf-8 -*-
"""«التسويق» (الجولة النهائية) — الحملات من الإعلان حتى الدفع · السوشيال ميديا · خطة النشر، ورا نفس المفتاح المقفول.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_marketing.py

⛔ صفر شبكة حقيقية: المنصة جدول في الذاكرة (`uiharness/mk_fixtures.MKPlatform`)، وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.
المنطق النقي (`V2L.mk`) وكل نصوص التبويبات بتتشغّل في node: الأرقام بعملتها · اقتراح العقل بقاعدة النضج · الجدول · البطاقات · التحقق · الرابط والكشف ·
صاحب الحملة بعد فشل مصدر الأعمال · نص الشاشة (بلا «يقوّم» ولا حروف لاتينية ولا عنوان يبدأ بـ«الذكاء»).

اللي بيثبّته:
  ١. المسارات الجديدة: أدمن بس · المفتاح مقفول ٤٠٤ بلا أي كتابة ولا نداء · `no-store` · الفاعل من التوكن · التدقيق عند النجاح بس · حدّ الحملات القديمة.
  ٢. `/api/campaigns` ما اتغيّرش.
  ٣. الملفات: خطّافات index.html · سطر app.py · الـDockerfiles الثلاثة · الأقسام · لا رابط من التسويق إلى التقارير · المفتاح مقفول ⇒ الشاشة القديمة بحروفها.
"""
import copy
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

import jwt
import pytest
from sqlalchemy import text
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Campaign, Article  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import mk_fixtures as mkfx   # noqa: E402
import v2_node               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2mk-admin@x.test'
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
TITLE_PREFIX = 'mkt-test '


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
        heads = {r: _bearer(_mkuser('v2mk-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.ef = mkfx.MKPlatform(d2=True)
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'headers': dict(headers or {})})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params, json)
        return _Resp(200, []) if out is None else _Resp(*out)

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


def _reset():
    """يمسح الحملات وجدولَي التسويق (الجدولان بيتعملوا كسولًا من جديد)."""
    for t in ('v2_campaign_owner', 'v2_marketing_meta'):
        db.session.execute(text('DROP TABLE IF EXISTS %s' % t))
    Campaign.query.delete()
    db.session.commit()


def _table_exists(name):
    return db.session.execute(text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {'n': name}).fetchone() is not None


def _camp(**kw):
    d = dict(name='حملة', platform='facebook', status='active', budget=0, spent=0, currency='EGP')
    d.update(kw)
    c = Campaign(**d)
    db.session.add(c)
    db.session.commit()
    return c.id


@pytest.fixture
def fresh(ctx):
    _reset()
    yield
    _reset()


def _own_articles():
    return Article.query.filter(Article.title.like(TITLE_PREFIX + '%'))


@pytest.fixture
def arts(ctx):
    _own_articles().delete(synchronize_session=False)
    db.session.commit()
    yield
    _own_articles().delete(synchronize_session=False)
    db.session.commit()


ROUTES = [('GET', '/api/v2/marketing/published', None), ('GET', '/api/v2/marketing/owners', None), ('POST', '/api/v2/marketing/legacy-checked', None),
          ('PUT', '/api/v2/marketing/campaigns/1/owner', {'owner_kind': 'platform'}), ('GET', '/api/v2/marketing/attribution', None)]


# ---------------------------------------------------------------- ١) المسارات

@pytest.mark.parametrize('method,path,body', ROUTES)
def test_every_new_route_is_admin_only(ctx, plat, fresh, method, path, body):
    for role in NON_ADMIN_ROLES:
        assert _call(ctx, method, path, body, role=role).status_code == 403, (path, role)
    assert _call(ctx, method, path, body, role=None).status_code == 401
    assert plat.seen == [], 'نداء للمنصة من غير أدمن'


@pytest.mark.parametrize('method,path,body', ROUTES)
def test_every_new_route_is_closed_with_zero_effects_when_the_switch_is_off(ctx, plat, fresh, monkeypatch, method, path, body):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    _camp()
    before = AuditLog.query.count()
    r = _call(ctx, method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert plat.seen == [], 'نداء للمنصة والمفتاح مقفول'
    assert not _table_exists('v2_marketing_meta') and not _table_exists('v2_campaign_owner'), 'جدول اتكتب والمفتاح مقفول'
    assert AuditLog.query.count() == before


def test_no_store_on_ok_bad_missing_and_down(ctx, plat, fresh):
    cid = _camp()
    ok = _call(ctx, 'GET', '/api/v2/marketing/owners')
    bad = _call(ctx, 'GET', '/api/v2/marketing/published?days=0')
    missing = _call(ctx, 'PUT', '/api/v2/marketing/campaigns/99999/owner', {'owner_kind': 'platform'})
    bad_owner = _call(ctx, 'PUT', '/api/v2/marketing/campaigns/%d/owner' % cid, {'owner_kind': 'robot'})
    plat.ef.forced[('GET', '/api/bridge/attribution/summary')] = (502, {'detail': 'x'})
    down = _call(ctx, 'GET', '/api/v2/marketing/attribution')
    assert (ok.status_code, bad.status_code, missing.status_code, bad_owner.status_code, down.status_code) == (200, 400, 404, 400, 502)
    for r in (ok, bad, missing, bad_owner, down):
        assert r.headers.get('Cache-Control') == 'no-store'


def _mkart(title, status, days_ago=None):
    at = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago) if days_ago is not None else None
    db.session.add(Article(title=TITLE_PREFIX + title, status=status, published_at=at))
    db.session.commit()


def test_published_window_status_order_and_drafts(ctx, plat, arts):
    base = Article.query.filter_by(status='draft').count()
    _mkart('a-new', 'published', 1)
    _mkart('b-newer', 'published', 0.2)
    _mkart('c-edge-in', 'published', 6.9)
    _mkart('d-old', 'published', 8)
    _mkart('e-draft', 'draft')
    _mkart('f-draft-with-date', 'draft', 1)
    r = _call(ctx, 'GET', '/api/v2/marketing/published?days=7')
    assert r.status_code == 200
    d = r.get_json()
    mine = [i['title'] for i in d['items'] if i['title'].startswith(TITLE_PREFIX)]
    assert mine == [TITLE_PREFIX + 'b-newer', TITLE_PREFIX + 'a-new', TITLE_PREFIX + 'c-edge-in'], mine            # الأحدث أولًا، و«٨ أيام» خارج النافذة، والمسودة بتاريخ ما تدخلش
    assert d['days'] == 7 and d['ok'] is True and d['since'].endswith('Z')
    assert d['drafts'] == base + 2
    ats = [i['published_at'] for i in d['items']]
    assert ats == sorted(ats, reverse=True) and all(a.endswith('Z') for a in ats)
    assert len(_call(ctx, 'GET', '/api/v2/marketing/published?days=31').get_json()['items']) >= 3
    assert plat.seen == [], 'المقالات محلية: لا نداء'


def test_published_is_capped_at_fifty(ctx, plat, arts):
    for i in range(55):
        _mkart('cap-%02d' % i, 'published', 0.5 + i / 1000.0)
    items = _call(ctx, 'GET', '/api/v2/marketing/published?days=7').get_json()['items']
    assert len(items) == 50


@pytest.mark.parametrize('days', ['0', '32', 'abc', '-1', '', '1.5'])
def test_published_rejects_a_bad_window(ctx, plat, arts, days):
    r = _call(ctx, 'GET', '/api/v2/marketing/published?days=' + days)
    assert r.status_code == 400 and r.get_json()['error'] == 'المدة غير صالحة'


def test_owner_put_rules_and_upsert(ctx, plat, fresh):
    cid = _camp(name='حملة أ')
    url = '/api/v2/marketing/campaigns/%d/owner' % cid
    for body in ({}, {'owner_kind': 'robot'}, {'owner_kind': None}, {'owner_kind': 'COURSE', 'owner_id': 'x'}):
        r = _call(ctx, 'PUT', url, body)
        assert r.status_code == 400 and r.get_json()['error'] == 'اختر صاحب الحملة', body
    for oid in ('', 'a b', 'a/b', 'a?b', 'a%b', 'x' * 201):
        r = _call(ctx, 'PUT', url, {'owner_kind': 'course', 'owner_id': oid, 'owner_title': 't'})
        assert r.status_code == 400 and r.get_json()['error'] == 'العمل غير صالح', oid
    assert _call(ctx, 'PUT', '/api/v2/marketing/campaigns/99999/owner', {'owner_kind': 'platform'}).status_code == 404
    n = AuditLog.query.filter_by(action='marketing.campaign_owner').count()
    r = _call(ctx, 'PUT', url, {'owner_kind': 'course', 'owner_id': 'contract-basics', 'owner_title': '  ' + 'ع' * 300 + '  ', 'by': 'attacker@evil.test'})
    assert r.status_code == 200
    item = r.get_json()['item']
    assert item['owner_kind'] == 'course' and item['owner_id'] == 'contract-basics' and len(item['owner_title']) == 200
    assert item['updated_by'] == ADMIN_EMAIL and 'attacker' not in json.dumps(r.get_json())
    rows = AuditLog.query.filter_by(action='marketing.campaign_owner').order_by(AuditLog.id.desc()).all()
    assert len(rows) == n + 1 and rows[0].actor_email == ADMIN_EMAIL and rows[0].target == 'campaign:%d' % cid
    assert json.loads(rows[0].meta_json) == {'owner_kind': 'course', 'owner_id': 'contract-basics'}
    # الفاشل ما بيتدقّقش
    assert AuditLog.query.filter_by(action='marketing.campaign_owner').count() == n + 1
    # upsert: التاني يستبدل (صف واحد)
    r = _call(ctx, 'PUT', url, {'owner_kind': 'book', 'owner_id': 'bk-1', 'owner_title': 'كتاب'})
    assert r.status_code == 200
    got = _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['items']
    assert [(i['campaign_id'], i['owner_kind'], i['owner_id'], i['owner_title']) for i in got] == [(cid, 'book', 'bk-1', 'كتاب')]
    # «البروفيسور» يمسح المعرّف والعنوان
    r = _call(ctx, 'PUT', url, {'owner_kind': 'platform', 'owner_id': 'zzz', 'owner_title': 'يتجاهل'})
    assert r.status_code == 200 and r.get_json()['item']['owner_id'] == '' and r.get_json()['item']['owner_title'] == ''
    assert plat.seen == []


def test_owners_hides_rows_of_deleted_campaigns(ctx, plat, fresh):
    a, b = _camp(name='باقية'), _camp(name='ستُحذف')
    for cid in (a, b):
        assert _call(ctx, 'PUT', '/api/v2/marketing/campaigns/%d/owner' % cid, {'owner_kind': 'platform'}).status_code == 200
    assert _call(ctx, 'DELETE', '/api/campaigns/%d' % b).status_code == 200
    items = _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['items']
    assert [i['campaign_id'] for i in items] == [a]
    assert db.session.execute(text('SELECT COUNT(*) FROM v2_campaign_owner')).scalar() == 2, 'الصف اليتيم يفضل في SQLite ويتفلتر بس'


def test_legacy_max_id_is_written_once_by_the_first_run(ctx, plat, fresh):
    ids = [_camp(name='قديمة ١', currency='USD'), _camp(name='قديمة ٢', currency='USD')]
    r = _call(ctx, 'GET', '/api/v2/marketing/owners')
    assert r.get_json()['legacy_max_id'] == max(ids)
    assert db.session.execute(text("SELECT v FROM v2_marketing_meta WHERE k='legacy_max_campaign_id'")).scalar() == str(max(ids))
    newer = _camp(name='جديدة من الشاشة الجديدة', currency='USD')                # حملة بعد أول تشغيل ما تحرّكش الحد
    assert newer > max(ids)
    assert _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['legacy_max_id'] == max(ids)
    assert _call(ctx, 'GET', '/api/v2/marketing/published').status_code == 200
    assert _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['legacy_max_id'] == max(ids)


def test_legacy_max_id_is_zero_for_an_empty_campaigns_table(ctx, plat, fresh):
    assert _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['legacy_max_id'] == 0


def test_legacy_checked_closes_the_strip_for_good_and_is_idempotent(ctx, plat, fresh):
    cid = _camp(currency='USD')
    assert _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['legacy_max_id'] == cid
    n = AuditLog.query.filter_by(action='marketing.legacy_currency_checked').count()
    assert _call(ctx, 'POST', '/api/v2/marketing/legacy-checked').get_json() == {'ok': True}
    assert _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['legacy_max_id'] == 0
    assert _call(ctx, 'POST', '/api/v2/marketing/legacy-checked').status_code == 200            # مرة تانية: بلا ضرر
    assert db.session.execute(text("SELECT COUNT(*) FROM v2_marketing_meta WHERE k='legacy_checked'")).scalar() == 1
    assert AuditLog.query.filter_by(action='marketing.legacy_currency_checked').count() >= n + 1
    assert _call(ctx, 'GET', '/api/v2/marketing/owners').get_json()['legacy_max_id'] == 0


def test_attribution_validates_the_month_and_makes_one_call(ctx, plat, fresh):
    assert _call(ctx, 'GET', '/api/v2/marketing/attribution?month=2026-13').status_code == 400
    assert _call(ctx, 'GET', '/api/v2/marketing/attribution?month=oct').status_code == 400
    assert plat.seen == []
    plat.ef.attribution = True
    r = _call(ctx, 'GET', '/api/v2/marketing/attribution?month=2026-10')
    assert r.status_code == 200 and r.headers.get('Cache-Control') == 'no-store'
    calls = plat.calls('/api/bridge/attribution')
    assert len(calls) == 1 and calls[0]['params'] == {'month': '2026-10'} and calls[0]['headers'].get('X-ELP-Metrics-Secret') == SECRET
    body = r.get_json()
    assert body['month'] == '2026-10' and [c['key'] for c in body['channels']][:2] == ['meta', 'meta'] and 'untracked' in body and body['campaigns'][0]['campaign'].startswith('c')
    # بلا شهر ⇒ الشهر الحالي
    r = _call(ctx, 'GET', '/api/v2/marketing/attribution')
    assert r.status_code == 200 and plat.calls('/api/bridge/attribution')[-1]['params']['month'] == datetime.datetime.utcnow().strftime('%Y-%m')


def test_attribution_platform_answers_pass_through(ctx, plat, fresh):
    r = _call(ctx, 'GET', '/api/v2/marketing/attribution?month=2026-10')           # المنصة بلا الجسر: ٤٠٤ كما هو
    assert r.status_code == 404 and len(plat.calls('/api/bridge/attribution')) == 1
    plat.ef.forced[('GET', '/api/bridge/attribution/summary')] = (401, {'detail': 'no'})
    assert _call(ctx, 'GET', '/api/v2/marketing/attribution?month=2026-10').status_code == 502
    plat.ef.forced[('GET', '/api/bridge/attribution/summary')] = (403, {'detail': 'no'})
    assert _call(ctx, 'GET', '/api/v2/marketing/attribution?month=2026-10').status_code == 502
    plat.ef.forced[('GET', '/api/bridge/attribution/summary')] = (200, {'ok': True, 'month': '2026-10', 'channels': [], 'untracked': None, 'campaigns': [], 'extra': 1})
    r = _call(ctx, 'GET', '/api/v2/marketing/attribution?month=2026-10')
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'month': '2026-10', 'channels': [], 'untracked': None, 'campaigns': [], 'extra': 1}


# ---------------------------------------------------------------- ٢) /api/campaigns ما اتغيّرش

def test_the_existing_campaign_api_is_unchanged(ctx, plat, fresh):
    r = _call(ctx, 'POST', '/api/campaigns', {'name': 'اختبار', 'currency': 'EGP', 'platform': 'google_ads', 'budget': 100, 'spent': 10})
    assert r.status_code == 201
    cid = r.get_json()['id']
    row = [c for c in _call(ctx, 'GET', '/api/campaigns').get_json() if c['id'] == cid][0]
    assert row['currency'] == 'EGP' and row['status'] == 'active' and row['roas'] == 0
    assert _call(ctx, 'PUT', '/api/campaigns/%d' % cid, {'status': 'completed'}).status_code == 200
    assert Campaign.query.get(cid).status == 'completed'
    assert _call(ctx, 'PUT', '/api/campaigns/%d' % cid, {'currency': 'EGP'}).status_code == 200
    assert _call(ctx, 'DELETE', '/api/campaigns/%d' % cid).status_code == 200 and Campaign.query.get(cid) is None
    # بلا عملة ⇒ دولار (فخّ الشاشة القديمة اللي الشريط يعالجه)
    r = _call(ctx, 'POST', '/api/campaigns', {'name': 'بلا عملة'})
    assert Campaign.query.get(r.get_json()['id']).currency == 'USD'
    assert plat.seen == []


# ---------------------------------------------------------------- ٣) الملفات

def test_index_html_has_the_sections_block_and_the_render_hook():
    h = _read('dashboard-cloud', 'index.html')
    block = h[h.index('<!-- v2 sections begin -->'):h.index('<!-- v2 sections end -->')]
    assert '<link rel="stylesheet" href="v2s/marketing.css">' in block and '<script src="v2s/marketing.js"></script>' in block
    keys = re.findall(r'v2s/([a-z]+)\.(?:js|css)', block)
    assert keys == sorted(keys), 'الأسطر بترتيب أبجدي بالمفتاح'
    assert h.index('<script src="v2-d3.js"></script>') < h.index('<!-- v2 sections begin -->')
    assert "if(window.V2SEC_OWNS&&V2SEC_OWNS(current))ap.classList.add('v2-bare');" in h
    hook = "if(window.V2_ON&&window.V2SEC_OWNS&&V2SEC_OWNS(current))return V2SEC_RENDER(current,v);"
    assert hook in h and h.index("return V2D3.render(current,v);") < h.index(hook) < h.index("viewSoon(v)")


def test_app_py_registers_the_routes_with_one_line_before_the_end_marker():
    a = _read('backend', 'app.py')
    line = "__import__('v2_marketing_routes').register(app, globals())   # v2s:marketing"
    assert a.count(line) == 1 and '# ---- v2 section routes end' in a
    assert a.index(line) < a.index('# ---- v2 section routes end')
    assert a.index("@app.route('/api/v2/book-requests/<request_id>', methods=['PATCH'])") < a.index(line)


def test_all_three_dockerfiles_ship_the_section_files():
    for df in ('Dockerfile', os.path.join('deploy', 'Dockerfile.coolify')):
        t = _read(df)
        assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in t and 'COPY backend/v2_*_routes.py /app/' in t, df
        assert t.index('COPY dashboard-cloud/v2/img /app/dist/v2/img') < t.index('COPY dashboard-cloud/v2s /app/dist/v2s')
    b = _read('backend', 'Dockerfile')
    assert 'COPY v2_*_routes.py ./' in b and b.index('COPY app.py .') < b.index('COPY v2_*_routes.py ./')


@needs_node
def test_sections_entry_and_every_open_section_target_exists():
    L = _node_json("console.log(JSON.stringify({sec: L.sectionByKey('marketing'), money_ads: !!L.tabByKey('money','ads'), company: (L.sectionByKey('company')||{}).tabs.map(t=>t.key),"
                   " route: [L.sectionFor('marketing'), L.routeFor('#s/marketing/plan'), L.routeFor('#marketing')]}))")
    sec = L['sec']
    assert sec['label'] == 'التسويق' and sec['desc'] == 'الحملات من الإعلان حتى الدفع، والسوشيال، وخطة النشر'
    assert [(t['key'], t['label'], t['mod']) for t in sec['tabs']] == [('campaigns', 'الحملات', 'marketing'), ('social', 'السوشيال ميديا', 'v2mk_social'), ('plan', 'خطة النشر', 'v2mk_plan')]
    assert L['route'][0]['tab'] == 'campaigns' and L['route'][1]['tab'] == 'plan' and L['route'][2]['section'] == 'marketing'
    src = _read('dashboard-cloud', 'v2s', 'marketing.js')
    assert "openSection('reports'" not in src and 'data-s="reports"' not in src, 'التقارير تروح للتسويق وما فيش رجوع'
    targets = set(re.findall(r'data-s="([a-z]+)" data-t="([a-z]*)"', src))
    assert targets == {('money', 'ads'), ('company', 'ads'), ('content', '')}
    assert L['money_ads'] is True
    if 'ads' in L['company']:
        pass                                      # بعد دمج جولة «الشركة»: التبويب لازم موجود (يُفحص عند الدمج)
    else:
        pytest.skip('تبويب «عملاء الإعلانات» في الشركة يوصل مع جولة الشركة — يلزم فحصه عند الدمج')


def test_the_old_marketing_screen_is_untouched_when_the_switch_is_off():
    h = _read('dashboard-cloud', 'index.html')
    a = h.index('function viewMarketing(v){')
    b = h.index('function createCampaignModal(edit){')
    c = h.index('// ⛔ (حُذفت: نافذة «إضافة ممول»)')
    got = hashlib.sha256(h[a:c].encode('utf-8')).hexdigest()
    old = subprocess.run(['git', 'show', '7d1aa83:dashboard-cloud/index.html'], capture_output=True, cwd=ROOT).stdout.decode('utf-8')
    oa, oc = old.index('function viewMarketing(v){'), old.index('// ⛔ (حُذفت: نافذة «إضافة ممول»)')
    assert got == hashlib.sha256(old[oa:oc].encode('utf-8')).hexdigest(), 'viewMarketing/renderMkt/drawMkt/createCampaignModal اتغيّروا'
    api_new, api_old = _read('dashboard-cloud', 'dashboard-api.js'), subprocess.run(['git', 'show', '7d1aa83:dashboard-cloud/dashboard-api.js'], capture_output=True, cwd=ROOT).stdout.decode('utf-8')
    assert api_new == api_old, 'dashboard-api.js اتغيّر'
    assert b > a


def test_the_section_files_only_use_the_local_api_and_never_the_network_directly():
    src = _read('dashboard-cloud', 'v2s', 'marketing.js')
    assert 'fetch(' not in src and 'XMLHttpRequest' not in src and 'sendBeacon' not in src
    paths = set(re.findall(r"'(/(?:campaigns|v2/[a-z/-]+)[^']*)'", src))
    assert paths == {'/campaigns', '/campaigns/', '/v2/marketing/owners', '/v2/income/by-service?month=', '/v2/ads-ledger', '/v2/marketing/attribution?month=', '/v2/marketing/published?days=7',
                     '/v2/marketing/campaigns/', '/v2/marketing/legacy-checked'}, paths
    css = _read('dashboard-cloud', 'v2s', 'marketing.css')
    plain = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    sels = re.findall(r'(?:^|[}{])\s*([^@{}]+)\{', plain)
    assert len(sels) > 40
    for sel in sels:
        for part in sel.split(','):
            p = part.strip()
            assert re.match(r'^(\.mk|\.v3m \.mk|\.v3m \.fld|\.mkm|#epModal \.modal:has\(\.mkm\)|\.mk,|\.v3m)', p) or p in ('.v3m', '.mk'), 'قاعدة خارج النطاق: ' + p
    for old in ('.kpis', '.kpi ', '.inboxwrap', '.panel', '.drawer', '.policy'):
        assert old not in src, 'صنف قديم في ملف التسويق: ' + old


# ---------------------------------------------------------------- ٤) المنطق النقي (node)

def _node_json(js):
    script = "const L=require(%s);\n%s" % (json.dumps(os.path.join(DC, 'v2-logic.js')), js)
    p = subprocess.run([v2_node.NODE, '-e', script], capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


def C(i, **kw):
    d = dict(id=i, name='حملة%d' % i, platform='facebook', status='active', currency='EGP', budget=0, spent=0, clicks=0, leads=0, conversions=0,
             revenue_attributed=0, start_date='', end_date='', target_audience='')
    d.update(kw)
    return d


def _mk(expr, rows=None):
    """يشغّل تعبير JS على `m = L.mk` و`rows = m.norm(<rows>)` ويرجّع JSON."""
    return _node_json("const m=L.mk; const rows=m.norm(%s); console.log(JSON.stringify(%s))" % (json.dumps(rows or [], ensure_ascii=False), expr))


TODAY = '2026-10-30'


@needs_node
def test_board_sums_each_currency_alone_and_never_mixes():
    raw = [C(1, spent=1000, revenue_attributed=5200, currency='EGP'), C(2, spent=300, revenue_attributed=900, currency='SAR'), C(3, spent=500, revenue_attributed=0, currency='EGP')]
    b = _mk("m.board(rows,'all',{})", raw)['numbers']
    assert b[0]['value'] == '١٬٥٠٠ جنيه' and b[0]['othersText'] == 'وبعملة أخرى: ٣٠٠ ريال' and b[0]['primary']['currency'] == 'EGP'
    assert b[1]['value'] == '٥٬٢٠٠ جنيه' and 'وبعملة أخرى: ٩٠٠ ريال' == b[1]['othersText']
    assert b[1]['note'] == 'كل جنيه رجع ٣٫٥ · منذ بداية كل حملة'            # ٥٢٠٠ ÷ ١٥٠٠ بالجنيه فقط (الريال خارجها)
    assert b[0]['note'] == 'من ٣ حملات مسجّلة · منذ بداية كل حملة'
    # لا جنيه إطلاقًا: أكبر عملة هي الأساسية
    only = [C(1, spent=100, currency='SAR'), C(2, spent=400, currency='USD')]
    n = _mk("m.board(rows,'all',{})", only)['numbers'][0]
    assert n['value'] == '٤٠٠ دولار' and n['othersText'] == 'وبعملة أخرى: ١٠٠ ريال'


@needs_node
def test_board_filter_and_zero_rows_never_show_a_zero():
    raw = [C(1, spent=700, currency='EGP'), C(2, spent=900, status='paused', currency='EGP')]
    act = _mk("m.board(rows,'active',{})", raw)['numbers']
    assert act[0]['value'] == '٧٠٠ جنيه' and act[0]['note'] == 'حملة واحدة نشطة · منذ بداية كل حملة'
    assert _mk("m.board(rows,'all',{})", raw)['numbers'][0]['value'] == '١٬٦٠٠ جنيه'
    none = _mk("m.board(rows,'active',{})", [])['numbers']
    for i in (0, 1):
        assert none[i]['value'] == 'لا حملات مسجّلة' and none[i]['na'] is True
    assert none[3]['value'] == 'غير متاح بعد' and none[3]['note'] == 'لم يُسجَّل بعد من دفع عن طريق حملة'
    for n in none:
        assert n['value'] not in ('٠', '٠ جنيه', '0')
    two = _mk("m.board(rows,'active',{})", [C(1, status='active', spent=5), C(2, status='active', spent=5)])['numbers'][0]
    assert two['note'].startswith('حملتان نشطتان')


@needs_node
def test_board_ratio_only_with_spend_and_cost_only_with_payers():
    n = _mk("m.board(rows,'all',{})", [C(1, spent=0, revenue_attributed=800)])['numbers']
    assert n[1]['value'] == '٨٠٠ جنيه' and n[1]['note'] == 'كما سُجّل في كل حملة منذ بدايتها' and 'رجع' not in n[1]['note']
    assert n[0]['value'] == 'لم يُسجَّل صرف بعد' and n[0]['na'] is True
    c = _mk("m.board(rows,'all',{})", [C(1, spent=1000, conversions=4), C(2, spent=900, conversions=0), C(3, spent=300, conversions=1, currency='SAR')])['numbers'][3]
    assert c['value'] == '٢٥٠ جنيه' and c['othersText'] == 'وبعملة أخرى: ٣٠٠ ريال' and c['note'] == 'من الحملات التي سُجّل لها من دفع، منذ بدايتها'    # ٩٠٠ بلا دافعين لا تدخل
    nopay = _mk("m.board(rows,'all',{})", [C(1, spent=1000, conversions=0)])['numbers'][3]
    assert nopay['value'] == 'غير متاح بعد' and nopay['na'] is True


@needs_node
def test_board_revenue_with_spend_but_no_revenue_says_so_instead_of_zero():
    n = _mk("m.board(rows,'all',{})", [C(1, spent=500, revenue_attributed=0, clicks=7)])['numbers'][1]
    assert n['value'] == 'لم يُسجَّل دخل بعد' and n['na'] is True and n['note'] == 'منذ بداية كل حملة'


@needs_node
def test_board_every_note_names_its_period():
    raw = [C(1, spent=1000, revenue_attributed=2000, conversions=2)]
    att = {'ok': True, 'captured_since': '2026-10-18T10:00:00Z', 'channels': [{'key': 'google', 'paid': False, 'signups': 3, 'paid_people': 1, 'totals': [{'currency': 'EGP', 'amount': 900}]}]}
    n = _mk("m.board(rows,'all',{attribution:%s,income:null})" % json.dumps(att), raw)['numbers']
    for i in (0, 1, 3):
        assert 'منذ بداية' in n[i]['note'] or 'منذ بدايتها' in n[i]['note'], n[i]['note']
    assert n[2]['note'].startswith('هذا الشهر') and 'منذ بدء التسجيل في ١٨ أكتوبر ٢٠٢٦' in n[2]['note']
    assert n[2]['value'] == '٩٠٠ جنيه' and n[2]['na'] is False


@needs_node
def test_board_number_three_needs_the_attribution_bridge_and_counts_only_unpaid_channels():
    base = [C(1, spent=10)]
    off = _mk("m.board(rows,'all',{attribution:null,income:null})", base)['numbers'][2]
    assert off['value'] == 'غير متاح بعد' and off['na'] is True and off['note'] == 'هذا الشهر: المنصة لا تسجّل بعد من أين جاء كل دافع.'
    inc = [{'currency': 'EGP', 'amount': 13500}, {'currency': 'SAR', 'amount': 300}]
    withinc = _mk("m.board(rows,'all',{attribution:null,income:%s})" % json.dumps(inc), base)['numbers'][2]
    assert withinc['note'].endswith('دخل المنصة كله هذا الشهر: ١٣٬٥٠٠ جنيه · ٣٠٠ ريال، ولا نعرف بعد كم منه جاء من إعلان.')
    att = mkfx.attribution_summary()
    on = _mk("m.board(rows,'all',{attribution:%s,income:null})" % json.dumps(att), base)['numbers'][2]
    # غير المدفوعة فقط: 1250 + 2300 + 900 + 700 = 5150 جنيه، و150 ريال. المدفوع (3400) و«بلا مصدر» (5200) خارج.
    assert on['value'] == '٥٬١٥٠ جنيه' and on['othersText'] == 'وبعملة أخرى: ١٥٠ ريال'
    bad = _mk("m.board(rows,'all',{attribution:{ok:false,channels:[]},income:null})", base)['numbers'][2]
    assert bad['na'] is True
    failed = _mk("m.board(null,'all',{})")['numbers']
    for i in (0, 1, 3):
        assert failed[i]['value'] == 'غير متاح بعد' and failed[i]['note'] == 'تعذّر جلب الحملات'


@needs_node
def test_each_number_picks_its_own_primary_currency():
    raw = [C(1, spent=900, currency='SAR', revenue_attributed=0), C(2, spent=10, currency='EGP', revenue_attributed=0), C(3, spent=0, currency='SAR', revenue_attributed=700)]
    n = _mk("m.board(rows,'all',{})", raw)['numbers']
    assert n[0]['primary']['currency'] == 'EGP'                  # فيه جنيه مصروف
    assert n[1]['primary']['currency'] == 'SAR' and n[1]['value'] == '٧٠٠ ريال'      # الدخل بالريال فقط


@needs_node
def test_legacy_usd_lists_only_old_screen_rows():
    raw = [C(1, currency='USD'), C(2, currency='SAR'), C(3, currency='EGP'), C(4, currency='USD'), C(9, currency='USD')]
    assert [r['id'] for r in _mk("m.legacyUsd(rows, 4)", raw)] == [1, 4]
    assert _mk("m.legacyUsd(rows, 0)", raw) == [] and _mk("m.legacyUsd(rows, null)", raw) == []


@needs_node
def test_brain_priority_order_and_exact_texts():
    raw = [C(1, name='أ', spent=1000, revenue_attributed=300, clicks=5, start_date='2026-09-01', budget=1500, end_date='2026-10-01'),
           C(2, name='ب', spent=800, start_date='2026-09-10', budget=1000),
           C(3, name='ج', spent=2200, revenue_attributed=3000, clicks=5, start_date='2026-09-10', budget=2000)]
    b = _mk("m.brain(rows,'%s',[])" % TODAY, raw)
    kinds = [i['kind'] for i in b['items']]
    assert kinds == ['ended', 'losing', 'no_results', 'losing', 'over_budget'] or kinds[0] == 'ended', kinds
    first = b['items'][0]
    assert first['text'] == 'حملة «أ» انتهى موعدها في ١ أكتوبر ٢٠٢٦ وما زالت «نشطة» هنا.' and first['line'] == 'أقترح تسجيلها منتهية.' and first['btn'] == 'سجّلها منتهية'
    by_kind = {i['kind'] + '_' + str(i['id']): i for i in b['items']}
    assert by_kind['losing_1']['text'] == 'حملة «أ» صُرف عليها ١٬٠٠٠ جنيه وسُجّل لها دخل ٣٠٠ جنيه: كل جنيه رجع ٠٫٣.'
    assert by_kind['no_results_2']['text'] == 'حملة «ب» صُرف عليها ٨٠٠ جنيه ولم تُسجَّل لها أي نتيجة بعد.' and by_kind['no_results_2']['btn'] == 'سجّل النتائج' and by_kind['no_results_2']['action'] == 'edit'
    assert by_kind['over_budget_3']['text'] == 'حملة «ج» صُرف عليها ٢٬٢٠٠ جنيه وميزانيتها ٢٬٠٠٠ جنيه.' and by_kind['over_budget_3']['line'] == 'راجع الميزانية أو أوقفها.'
    assert by_kind['losing_1']['action'] == 'pause' and by_kind['losing_1']['btn'] == 'أوقفها' and first['action'] == 'complete'
    # ترتيب الأولويات: منتهية ثم خاسرة ثم بلا نتائج ثم فوق الميزانية
    order = {'ended': 0, 'losing': 1, 'no_results': 2, 'over_budget': 3}
    assert [order[k] for k in kinds] == sorted(order[k] for k in kinds)


@needs_node
def test_brain_later_advances_and_every_number_in_the_text_is_the_rows_own():
    raw = [C(1, name='أ', spent=1000, revenue_attributed=300, clicks=5, start_date='2026-09-01', budget=1500, end_date='2026-10-01'),
           C(2, name='ب', spent=800, start_date='2026-09-10', budget=1000)]
    items = _mk("m.brain(rows,'%s',[])" % TODAY, raw)['items']
    assert [i['kind'] for i in items] == ['ended', 'losing', 'no_results']
    nxt = _mk("m.brain(rows,'%s',['ended_1'])" % TODAY, raw)
    assert nxt['state'] == 'items' and nxt['items'][0]['kind'] == 'losing'
    all_skipped = _mk("m.brain(rows,'%s',['ended_1','losing_1','no_results_2'])" % TODAY, raw)
    assert all_skipped['state'] == 'none' and all_skipped['items'] == [] and all_skipped['text'] == 'لا اقتراح الآن. الحملات النشطة تسير كما سُجّلت.'
    for it in items:
        row = [r for r in raw if r['id'] == it['id']][0]
        nums = set(re.findall(r'[٠-٩٬٫]+', it['text']))
        allowed = {'١٬٠٠٠', '٣٠٠', '٠٫٣', '٨٠٠', '١', '٢٠٢٦'}
        assert nums <= allowed, (it['text'], nums)


@needs_node
def test_brain_ties_larger_spend_first_and_only_active_rows():
    raw = [C(1, name='صغيرة', spent=300, start_date='2026-09-01', budget=400), C(2, name='كبيرة', spent=900, start_date='2026-09-01', budget=1000),
           C(3, name='موقوفة', status='paused', spent=9000, start_date='2026-09-01', budget=1000)]
    items = _mk("m.brain(rows,'%s',[])" % TODAY, raw)['items']
    assert [i['id'] for i in items] == [2, 1], 'الأكبر صرفًا أولًا والموقوفة بلا اقتراح'


@needs_node
def test_brain_best_only_when_nothing_else_applies_and_has_no_later():
    raw = [C(1, name='ممتازة', spent=1000, revenue_attributed=5200, clicks=5, start_date='2026-09-01', budget=3000)]
    b = _mk("m.brain(rows,'%s',[])" % TODAY, raw)
    assert b['state'] == 'items' and b['items'][0]['kind'] == 'best' and b['items'][0]['later'] is False and b['items'][0]['text'] == 'أفضل حملة الآن «ممتازة»: كل جنيه رجع ٥٫٢.'
    assert b['items'][0]['btn'] == 'افتح الحملة' and b['items'][0]['action'] == 'detail'
    both = raw + [C(2, name='خاسرة', spent=800, revenue_attributed=100, clicks=1, start_date='2026-09-01', budget=1000)]
    kinds = [i['kind'] for i in _mk("m.brain(rows,'%s',[])" % TODAY, both)['items']]
    assert kinds == ['losing'], 'best لا يظهر مع اقتراح آخر'


@needs_node
def test_brain_maturity_rule():
    young = [C(1, name='وليدة', spent=200, revenue_attributed=0, clicks=9, start_date='2026-10-29', budget=500)]
    r = _mk("m.brain(rows,'%s',[])" % TODAY, young)
    assert r['state'] == 'young' and r['items'] == [] and r['text'] == 'الحملات الجديدة ما زالت في أيامها الأولى، فلا اقتراح عليها الآن.'
    # عمرها ١٠ أيام لكن صرفت أقل من ٢٥٪ من ميزانيتها
    low = [C(1, spent=100, revenue_attributed=0, clicks=9, start_date='2026-10-20', budget=1000)]
    assert _mk("m.brain(rows,'%s',[])" % TODAY, low)['state'] == 'young'
    ok = [C(1, spent=250, revenue_attributed=0, clicks=9, start_date='2026-10-20', budget=1000)]
    assert _mk("m.brain(rows,'%s',[])" % TODAY, ok)['items'][0]['kind'] == 'losing'
    nodate = [C(1, spent=100, revenue_attributed=0, clicks=9, start_date='', budget=0)]
    assert _mk("m.brain(rows,'%s',[])" % TODAY, nodate)['items'][0]['kind'] == 'losing'
    seven = [C(1, spent=500, revenue_attributed=0, clicks=9, start_date='2026-10-23', budget=1000)]
    assert _mk("m.brain(rows,'%s',[])" % TODAY, seven)['items'][0]['kind'] == 'losing'      # ٧ أيام بالضبط = ناضجة
    six = [C(1, spent=500, revenue_attributed=0, clicks=9, start_date='2026-10-24', budget=1000)]
    assert _mk("m.brain(rows,'%s',[])" % TODAY, six)['state'] == 'young'


@needs_node
def test_brain_no_results_is_reachable_and_losing_with_zero_revenue_never_says_zero():
    nores = [C(1, name='صامتة', spent=600, start_date='2026-09-01', budget=1000)]
    it = _mk("m.brain(rows,'%s',[])" % TODAY, nores)['items']
    assert [i['kind'] for i in it] == ['no_results'], 'صفر نتائج ⇒ no_results مش losing'
    some = [C(1, name='فيها زيارات', spent=600, clicks=4, start_date='2026-09-01', budget=1000)]
    it = _mk("m.brain(rows,'%s',[])" % TODAY, some)['items'][0]
    assert it['kind'] == 'losing' and it['text'] == 'حملة «فيها زيارات» صُرف عليها ٦٠٠ جنيه ولم يُسجَّل لها دخل بعد.' and 'رجع ٠' not in it['text'] and 'رجع ٠٫٠' not in it['text']


@needs_node
def test_brain_empty_none_and_main_button():
    e = _mk("m.brain(rows,'%s',[])" % TODAY, [])
    assert e['state'] == 'empty' and e['items'][0]['text'] == 'لا حملات مسجّلة. سجّل أول حملة لأرى ما صُرف وما جاء.' and e['items'][0]['btn'] == 'حملة جديدة' and e['items'][0]['action'] == 'create'
    n = _mk("m.brain(rows,'%s',[])" % TODAY, [C(1, spent=0), C(2, status='paused', spent=50)])
    assert n['state'] == 'none' and n['text'] == 'لا اقتراح الآن. الحملات النشطة تسير كما سُجّلت.' and n['items'] == []
    mb = _node_json("console.log(JSON.stringify(['items','empty','young','none'].map(s=>L.mk.mainButton(s))))")
    assert mb == [{'main': 'brain', 'topHidden': False}, {'main': 'brain', 'topHidden': True}, {'main': 'top', 'topHidden': False}, {'main': 'top', 'topHidden': False}]


@needs_node
def test_sources_chips_needs_and_failed():
    s = _node_json("console.log(JSON.stringify(L.mk.sources({campaigns:'ready',income:'ready',ads:'ready',attribution:'closed'})))")
    assert [x['key'] for x in s['needs']] == ['attribution', 'ads_results', 'social_pages', 'site_visits'] and s['failed'] == []
    assert [x['state'] for x in s['seen']] == ['ready', 'ready', 'ready', 'off', 'off', 'off', 'off', 'off']
    ready = _node_json("console.log(JSON.stringify(L.mk.sources({campaigns:'ready',income:'ready',ads:'ready',attribution:'ready'})))")
    assert [x['key'] for x in ready['needs']] == ['ads_results', 'social_pages', 'site_visits'] and ready['seen'][3]['state'] == 'ready'
    err = _node_json("console.log(JSON.stringify(L.mk.sources({campaigns:'error',income:'error',ads:'ready',attribution:'error'})))")
    assert err['failed'] == ['campaigns', 'income', 'attribution'] and [x['state'] for x in err['seen']][:4] == ['error', 'error', 'ready', 'error']
    assert not [n for n in err['needs'] if n['key'] in ('campaigns', 'income', 'ads')], 'المصدر الموجود لو وقع مش «احتياج»'
    assert [n['key'] for n in err['needs']][0] == 'attribution'


@needs_node
def test_rows_sort_chip_organic_and_via():
    raw = [C(1, name='ب', spent=100, revenue_attributed=500, clicks=1, leads=2, conversions=1), C(2, name='أ', spent=900, revenue_attributed=2700, clicks=5, leads=7, conversions=3),
           C(3, name='ج', spent=300, status='paused', clicks=4), C(4, name='د', spent=250), C(5, name='ه', spent=0, clicks=0)]
    att = mkfx.attribution_summary({'winning': 2, 'losing': 1})
    owners = [{'campaign_id': 2, 'owner_kind': 'course', 'owner_id': 'x', 'owner_title': 'أساسيات التسويق'}, {'campaign_id': 1, 'owner_kind': 'platform'}]
    v = _mk("m.rows(rows,%s,'all',%s)" % (json.dumps(owners), json.dumps(att)), raw)
    assert [r['id'] for r in v['rows']] == [2, 4, 1, 5, 3], '(نشطة أولًا بالصرف ثم الموقوفة)'
    by = {r['id']: r for r in v['rows']}
    assert by[2]['owner'] == 'لأساسيات التسويق' and by[1]['owner'] == 'للبروفيسور' and by[4]['owner'] == 'للبروفيسور'
    assert by[4]['noResults'] is True and by[5]['noResults'] is False and by[3]['noResults'] is False        # ٣ فيها زيارات، و٥ لا صرف فيها
    assert by[2]['ratioText'] == '٣' and by[2]['ratioTone'] == 'good' and by[1]['ratioTone'] == 'good'
    assert by[4]['ratioText'] == '—' and by[5]['ratioText'] == '—'
    # عبر الرابط: من campaigns[c{id}] فقط، والأرقام المكتوبة ما تتبدّلش
    assert v['viaColumn'] is True and by[2]['via'] == {'signups': 9, 'paid': 3, 'totals': [{'currency': 'EGP', 'amount': 2100.0}]} and by[2]['viaText'] == 'سجّلوا ٩ · دفعوا ٣'
    assert by[1]['via']['signups'] == 4 and by[3]['via'] is None and by[3]['viaText'] == '—'
    assert by[2]['leads'] == '٧' and by[2]['conversions'] == '٣', 'المكتوب كما هو'
    org = v['organic']
    assert org['name'] == 'بلا إعلان' and org['sub'] == 'من المنصة · هذا الشهر · البحث والسوشيال والدعوات والدخول المباشر' and org['na'] is False
    assert org['signups'] == '٧٢' and org['paid'] == '٢١' and org['ratioText'] == 'بلا صرف'          # غير المدفوعة فقط: 20+30+8+14 و5+9+3+4
    assert org['revenueText'] == '٥٬١٥٠ جنيه · ١٥٠ ريال'
    off = _mk("m.rows(rows,null,'all',null)", raw)
    assert off['viaColumn'] is False and off['organic']['na'] is True and off['organic']['naText'] == 'غير متاح بعد — المنصة لا تسجّل بعد من أين جاء كل دافع'
    assert all(r['via'] is None and r['viaText'] == '' and r['owner'] == '' for r in off['rows'])
    active = _mk("m.rows(rows,[],'active',null)", raw)
    assert [r['id'] for r in active['rows']] == [2, 4, 1, 5]


@needs_node
def test_by_platform_shared_rows_and_missing_revenue():
    raw = [C(1, platform='facebook_instagram', spent=1000, revenue_attributed=2500, conversions=4), C(2, platform='facebook', spent=500, revenue_attributed=0, conversions=1),
           C(3, platform='tiktok', spent=300, currency='SAR'), C(4, platform='google_ads', spent=700), C(5, platform='instagram', spent=0)]
    p = _mk("m.byPlatform(rows)", raw)
    assert set(p) == {'facebook', 'instagram', 'linkedin', 'youtube', 'tiktok'}, 'جوجل مش بطاقة سوشيال'
    assert p['facebook']['n'] == 2 and p['facebook']['big'] == '١٬٥٠٠ جنيه' and p['facebook']['sharedText'] == '(مشتركة مع إنستجرام)' and p['facebook']['conversions'] == 5
    assert p['facebook']['fact'] == 'حملتان · دفعوا ٥ · كل جنيه رجع ١٫٧'
    assert p['instagram']['n'] == 2 and p['instagram']['sharedText'] == '(مشتركة مع فيسبوك)' and p['instagram']['big'] == '١٬٠٠٠ جنيه'
    assert p['tiktok']['big'] == '٣٠٠ ريال' and p['tiktok']['fact'] == 'حملة واحدة · دفعوا ٠ · لم يُسجَّل دخل بعد'
    assert p['linkedin']['big'] == 'لا حملات مسجّلة على هذه المنصة' and p['linkedin']['na'] is True and p['youtube']['n'] == 0
    only = _mk("m.byPlatform(rows)", [C(1, platform='instagram', spent=0)])
    assert only['instagram']['big'] == 'لم يُسجَّل صرف بعد' and only['instagram']['na'] is True
    mixed = _mk("m.byPlatform(rows)", [C(1, platform='linkedin', spent=100), C(2, platform='linkedin', spent=50, currency='USD')])
    assert mixed['linkedin']['big'] == '١٠٠ جنيه' and mixed['linkedin']['othersText'] == 'وبعملة أخرى: ٥٠ دولار'


@needs_node
def test_link_statement_and_validate():
    for plat_, src in (('facebook', 'facebook'), ('instagram', 'instagram'), ('facebook_instagram', 'meta'), ('google_ads', 'google'), ('linkedin', 'linkedin'), ('youtube', 'youtube'),
                       ('tiktok', 'tiktok'), ('Google Ads', 'other'), ('', 'other')):
        url = _node_json("console.log(JSON.stringify(L.mk.link(12, %s)))" % json.dumps(plat_))
        assert url == 'https://elprofessor.net/?utm_source=%s&utm_medium=paid&utm_campaign=c12' % src, plat_
    row = C(7, name='حملة الصيف', platform='google_ads', spent=1500, budget=3000, clicks=320, leads=18, conversions=0, revenue_attributed=0, start_date='2026-10-01', end_date='2026-10-20')
    stm = _mk("m.statement(rows[0],{owner_kind:'course',owner_id:'x',owner_title:'أساسيات التسويق'},'%s')" % TODAY, [row])
    assert stm.split('\n') == ['كشف حملة «حملة الصيف» — لأساسيات التسويق', 'المنصة: جوجل · من ١ أكتوبر ٢٠٢٦ إلى ٢٠ أكتوبر ٢٠٢٦', 'صُرف: ١٬٥٠٠ جنيه من ميزانية ٣٬٠٠٠ جنيه',
                                'زيارات: ٣٢٠ · سجّلوا: ١٨ · دفعوا: ٠', 'الدخل المسجّل: ٠ جنيه', 'الأرقام كما سُجّلت في لوحة البروفيسور بتاريخ ٣٠ أكتوبر ٢٠٢٦.'], '«الأصفار تبقى: قيم مسجّلة»'
    bare = _mk("m.statement(rows[0],null,'%s')" % TODAY, [C(8, name='بلا مالك', platform='', spent=0, budget=0)])
    assert bare.split('\n')[0] == 'كشف حملة «بلا مالك» — للبروفيسور' and bare.split('\n')[1] == 'بلا تاريخ', 'سطر المنصة المفقودة يُحذف'


def _validate(form, loaded=None):
    return _node_json("console.log(JSON.stringify(L.mk.validate(%s,%s)))" % (json.dumps(form, ensure_ascii=False), json.dumps(loaded)))


F = dict(name='حملة', platform='facebook', currency='EGP', status='active', start='', end='', budget='', spent='', clicks='', leads='', conversions='', revenue='', audience='',
         ownerValue='platform', ownerDisabled=False, ownerTitle='', edit=False)


@needs_node
def test_validate_rules_in_arabic():
    ok = _validate(dict(F, budget='٣٬٠٠٠', spent='١٥٠٠٫٥', clicks='٣٢٠', leads='18', conversions='٠', revenue=' ٥٠٠ '))
    assert ok['ok'] is True and ok['body'] == {'name': 'حملة', 'platform': 'facebook', 'status': 'active', 'budget': 3000, 'spent': 1500.5, 'currency': 'EGP', 'clicks': 320, 'leads': 18,
                                              'conversions': 0, 'revenue_attributed': 500, 'target_audience': '', 'impressions': 0}
    assert _validate(dict(F, name='   '))['error'] == 'اكتب اسم الحملة'
    assert _validate(dict(F, name='ن' * 256))['ok'] is False
    for field in ('budget', 'spent', 'clicks', 'revenue'):
        assert _validate(dict(F, **{field: '-5'}))['error'] == 'الأرقام لا تكون سالبة', field
    assert _validate(dict(F, spent='abc'))['ok'] is False and _validate(dict(F, clicks='1.5'))['ok'] is False
    assert _validate(dict(F, start='2026-10-10', end='2026-10-01'))['error'] == 'تاريخ النهاية قبل البدء'
    assert _validate(dict(F, start='2026-10-10', end='2026-10-10'))['ok'] is True
    assert _validate(dict(F, platform='other', platformOther='  '))['error'] == 'اكتب اسم المنصة'
    assert _validate(dict(F, platform='other', platformOther='قناة الشريك'))['body']['platform'] == 'قناة الشريك'
    assert _validate(dict(F, currency='other', currencyOther='ab'))['error'] == 'اكتب رمز العملة من ثلاثة أحرف'
    assert _validate(dict(F, currency='other', currencyOther='aed'))['body']['currency'] == 'AED'
    ed = _validate(dict(F, edit=True, start='2026-10-01'))
    assert 'impressions' not in ed['body'] and ed['body']['start_date'] == '2026-10-01' and 'end_date' not in ed['body'], 'التاريخ الفارغ لا يُرسل (لا يُمسح)'
    assert 'impressions' in ok['body']


@needs_node
def test_owner_choices_never_replace_a_stored_owner_when_the_list_is_missing():
    own = {'owner_kind': 'course', 'owner_id': 'contract-basics', 'owner_title': 'أساسيات صياغة العقود'}
    ads = [{'owner_kind': 'book', 'owner_id': 'bk-1', 'title': 'كتاب الإيجار'}, {'owner_kind': 'course', 'owner_id': 'c-2', 'title': ''}]
    j = lambda x: json.dumps(x, ensure_ascii=False)       # noqa: E731
    failed = _node_json("console.log(JSON.stringify(L.mk.ownerChoices('error',null,%s)))" % j(own))
    assert failed['disabled'] is True and [o['label'] for o in failed['options']] == ['أساسيات صياغة العقود — الحالي'] and failed['selected'] == 'course:contract-basics'
    assert failed['hint'] == 'قائمة الأعمال غير متاحة الآن، فلا يمكن تغيير صاحب الحملة'
    assert _validate(dict(F, ownerValue='course:contract-basics', ownerDisabled=True, ownerTitle='x'), own)['ownerChanged'] is False
    # قائمة مقفولة لا تُرسل أي تغيير مهما كانت القيمة اللي فيها (حماية من استبدال صامت)
    assert _validate(dict(F, ownerValue='book:bk-9', ownerDisabled=True, ownerTitle='كتاب'), own)['ownerChanged'] is False
    assert _validate(dict(F, ownerValue='platform', ownerDisabled=True), own)['ownerChanged'] is False
    plain = _node_json("console.log(JSON.stringify(L.mk.ownerChoices('closed',null,null)))")
    assert plain['disabled'] is True and [o['label'] for o in plain['options']] == ['البروفيسور نفسه']
    ready = _node_json("console.log(JSON.stringify(L.mk.ownerChoices('ready',%s,%s)))" % (j(ads), j(own)))
    labels = [o['label'] for o in ready['options']]
    assert labels == ['البروفيسور نفسه', 'كتاب الإيجار — كتاب', 'عمل بلا عنوان (c-2) — دورة', 'أساسيات صياغة العقود — الحالي'], 'المالك الحالي غير الموجود في القائمة يبقى خيارًا'
    assert ready['selected'] == 'course:contract-basics' and ready['disabled'] is False
    same = _node_json("console.log(JSON.stringify(L.mk.ownerChoices('ready',%s,%s).options.map(o=>o.label)))" % (j([{'owner_kind': 'course', 'owner_id': 'contract-basics', 'title': ''}]), j(own)))
    assert same == ['البروفيسور نفسه', 'أساسيات صياغة العقود — دورة'], 'عنوان الأرصدة فارغ ⇒ نستعمل العنوان المحفوظ مع الحملة'
    kept = _validate(dict(F, ownerValue='course:contract-basics', ownerDisabled=False), own)
    assert kept['ownerChanged'] is False
    changed = _validate(dict(F, ownerValue='book:bk-1', ownerDisabled=False, ownerTitle='كتاب الإيجار'), own)
    assert changed['ownerChanged'] is True and changed['owner'] == {'owner_kind': 'book', 'owner_id': 'bk-1', 'owner_title': 'كتاب الإيجار'}
    back = _validate(dict(F, ownerValue='platform'), own)
    assert back['ownerChanged'] is True and back['owner'] == {'owner_kind': 'platform'}
    newc = _validate(dict(F, ownerValue='platform'), None)
    assert newc['ownerChanged'] is False, 'حملة جديدة بلا مالك: لا نداء'
    assert _validate(dict(F, ownerValue='book:bk-1', ownerTitle='ك'), None)['ownerChanged'] is True
    # «أرصدة الأعمال» غائبة وحملة جديدة: القائمة مقفولة على «البروفيسور نفسه» فلا يتغيّر شيء
    off = _node_json("console.log(JSON.stringify(L.mk.ownerChoices('error',null,null,true)))")
    assert off['disabled'] is True and off['selected'] == 'platform'
    owners_off = _node_json("console.log(JSON.stringify(L.mk.ownerChoices('ready',[],%s,false)))" % j(own))
    assert owners_off['disabled'] is True and owners_off['hint'] == 'صاحب الحملة غير متاح الآن، فلا يمكن تغييره' and owners_off['selected'] == 'course:contract-basics'


# ---------------------------------------------------------------- ٥) نصوص الشاشة (node على marketing.js بلا DOM)

def _html(tab, model):
    p = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'mk_html.js')], input=json.dumps({'tab': tab, 'model': model}, ensure_ascii=False),
                       capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)['html']


def _src(**kw):
    out = {}
    for k, v in kw.items():
        out[k] = {'state': 'ready', 'data': v} if not (isinstance(v, str)) else {'state': v, 'data': None}
    return out


NOW = int(datetime.datetime(2026, 10, 30, 10, 0, 0).replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)


def _model(raw=None, **kw):
    src = {'campaigns': {'state': 'ready', 'data': raw if raw is not None else [
        C(1, name='رابحة', spent=1000, revenue_attributed=5200, clicks=5, leads=3, conversions=2, start_date='2026-09-01', budget=3000),
        C(2, name='خاسرة', spent=800, revenue_attributed=100, clicks=5, start_date='2026-09-01', budget=1000)]},
        'owners': {'state': 'ready', 'data': {'items': [], 'legacy_max_id': 0}}, 'income': {'state': 'ready', 'data': {'services': []}},
        'ads': {'state': 'ready', 'data': {'items': [{'owner_kind': 'book', 'owner_id': 'bk-1', 'title': 'كتاب', 'balance': [{'currency': 'EGP', 'amount': 100}]}]}},
        'attribution': {'state': 'closed'}, 'published': {'state': 'ready', 'data': {'items': [], 'drafts': 0}}}
    src.update(kw.pop('src', {}))
    m = {'now': NOW, 'filter': 'active', 'skipped': [], 'legacyLater': False, 'note': None, 'src': src}
    m.update(kw)
    return m


def _count(html, cls):
    return len(re.findall(r'class="[^"]*\b%s\b[^"]*"' % re.escape(cls), html))


@needs_node
def test_the_campaigns_tab_has_exactly_one_main_button_in_every_brain_state():
    items = _html('marketing', _model())
    assert _count(items, 'v3-btn1') == 1 and 'data-a="brain"' in items and 'mk-brainstrip' in items
    empty = _html('marketing', _model(raw=[]))
    assert _count(empty, 'v3-btn1') == 1 and 'data-a="new"' in empty and empty.count('data-a="new"') == 1, 'لا حملات ⇒ زرّ «حملة جديدة» في شريط العقل فقط'
    young = _html('marketing', _model(raw=[C(1, spent=100, clicks=3, start_date='2026-10-29', budget=1000)]))
    assert _count(young, 'v3-btn1') == 1 and 'mk-new v3-btn1' in young and 'data-a="brain"' not in young
    none = _html('marketing', _model(raw=[C(1, spent=0)]))
    assert _count(none, 'v3-btn1') == 1 and 'mk-new v3-btn1' in none
    down = _html('marketing', _model(src={'campaigns': {'state': 'error'}}))
    assert _count(down, 'v3-btn1') == 0 and 'disabled' in down and 'تعذّر جلب الحملات — أعد المحاولة أولًا حتى لا تتكرر حملة' in down and 'mk-brainstrip' not in down
    later = _html('marketing', _model(skipped=['losing_2']))
    assert _count(later, 'v3-btn1') == 1 and 'mk-new v3-btn2' in later or 'mk-new v3-btn1' in later


@needs_node
def test_the_campaigns_tab_html_rules():
    h = _html('marketing', _model())
    assert 'mk-links' not in h and 'mk-madar' not in h and 'اربط مدار' not in h, 'لا بطاقات روابط ولا بطاقة مدار في تبويب الحملات'
    assert h.count('data-a="how"') == 1 and 'كيف تُربط هذه المصادر؟' in h and h.count('class="mk-need"') == 4 and '<button' not in re.search(r'<ul class="mk-needlist">.*?</ul>', h, re.S).group(0)
    assert h.count('data-a="goto"') == 2 and 'data-s="money" data-t="ads"' in h and 'data-s="company" data-t="ads"' in h
    assert 'العقل يرى من' in h and 'العقل يحتاج:' in h
    for old in ('kpis', 'inboxwrap', 'class="panel', 'drawer', 'class="policy'):
        assert old not in h, old
    assert 'العقل يقترح' in h and 'لاحقًا' in h and 'اقتراح' not in re.sub('العقل يقترح', '', h), 'اقتراح واحد ⇒ بلا عدّاد'
    two = _html('marketing', _model(raw=[C(1, name='أ', spent=800, start_date='2026-09-01', budget=1000), C(2, name='ب', spent=600, clicks=3, start_date='2026-09-01', budget=1000)]))
    assert 'اقتراح ١ من ٢' in two
    assert 'غير متاح بعد' in h and 'مدار' in h
    allv = _html('marketing', _model(filter='all'))
    assert 'كل الحملات' in allv and allv.count('data-a="open"') == 6, 'الصفان ثلاث مرات: جدول سطح المكتب وجدول التابلت وبطاقات الموبايل'


@needs_node
def test_the_legacy_strip_shows_only_when_owners_say_so():
    raw = [C(1, name='قديمة', currency='USD', spent=50), C(2, name='أحدث', currency='USD', spent=60)]
    on = _html('marketing', _model(raw=raw, src={'owners': {'state': 'ready', 'data': {'items': [], 'legacy_max_id': 1}}}))
    assert 'mk-legacy' in on and 'حملة واحدة سُجّلت من الشاشة القديمة' in on and 'راجع العملة' in on
    assert 'mk-legacy' not in _html('marketing', _model(raw=raw, src={'owners': {'state': 'ready', 'data': {'items': [], 'legacy_max_id': 0}}}))
    assert 'mk-legacy' not in _html('marketing', _model(raw=raw, src={'owners': {'state': 'error'}}))
    assert 'mk-legacy' not in _html('marketing', _model(raw=raw, legacyLater=True, src={'owners': {'state': 'ready', 'data': {'items': [], 'legacy_max_id': 5}}}))


@needs_node
def test_the_organic_row_and_via_column_follow_the_attribution_state():
    off = _html('marketing', _model())
    assert 'mk-via-c' not in off and 'غير متاح بعد — المنصة لا تسجّل بعد من أين جاء كل دافع' in off and 'mk-via"' not in off
    att = mkfx.attribution_summary({'winning': 1, 'losing': 2})
    on = _html('marketing', _model(src={'attribution': {'state': 'ready', 'data': att}}))
    assert 'mk-via-c' in on and 'عبر الرابط' in on and 'من المنصة · هذا الشهر' in on and 'سجّلوا ٩ · دفعوا ٣' in on and 'بلا صرف' in on
    assert 'غير متاح بعد — المنصة لا تسجّل' not in on and 'class="mk-via"' in on and 'class="mk-viarow"' in on


@needs_node
def test_a_missing_ads_source_says_so_and_failures_are_never_empty_screens():
    h = _html('marketing', _model(src={'ads': {'state': 'error'}, 'income': {'state': 'error'}}))
    assert 'أرصدة إعلانات الأعمال: غير متاح بعد' in h and 'mk-src s-error' in h and h.count('data-a="retry"') >= 1
    d = _html('marketing', _model(src={'campaigns': {'state': 'error'}}))
    assert 'الحملات: غير متاح بعد' in d and 'تعذّر الجلب الآن، فلا تعتبر الشاشة فارغة.' in d and 'تعذّر جلب: الحملات — ما يظهر ناقص، وليس معناه أنه لا شيء' in d
    loading = _html('marketing', _model(src={'campaigns': {'state': 'loading'}}))
    assert '…جارٍ جلب الحملات' in loading and 'غير متاح بعد' in loading.replace('الحملات: غير متاح بعد', '')
    emptya = _html('marketing', _model(raw=[C(1, status='paused', spent=5)]))
    assert 'لا حملات نشطة الآن.' in emptya and 'اعرض كل الحملات' in emptya
    emptyall = _html('marketing', _model(raw=[], filter='all'))
    assert 'لا حملات مسجّلة بعد' in emptyall


@needs_node
def test_the_social_tab_has_one_button_and_no_needs_block():
    h = _html('social', _model(raw=[C(1, platform='facebook_instagram', spent=1000, revenue_attributed=2000, conversions=2), C(2, platform='tiktok', spent=300, currency='SAR')]))
    buttons = re.findall(r'<button[^>]*>', h)
    assert len(buttons) == 1 and 'data-a="madar"' in buttons[0] and 'v3-btn2' in buttons[0]
    assert 'العقل يحتاج' not in h and 'mk-need' not in h and 'v3-btn1' not in h
    assert h.count('class="mk-sc"') == 5 and 'المتابعون والوصول: غير متاح بعد' in h and h.count('المتابعون والوصول: غير متاح بعد') == 5
    assert 'mk-madar' in h and 'قريبًا' in h and 'v2/img/marketing.jpg' in h and 'ماذا سيظهر هنا؟' in h
    assert '(مشتركة مع إنستجرام)' in h and '(مشتركة مع فيسبوك)' in h
    down = _html('social', _model(src={'campaigns': {'state': 'error'}}))
    assert down.count('تعذّر جلب الحملات') >= 5 and 'غير متاح بعد' in down and len(re.findall(r'<button', down)) == 2      # «ماذا سيظهر» + «أعد المحاولة» في الشريط
    empty = _html('social', _model(raw=[]))
    assert empty.count('لا حملات مسجّلة على هذه المنصة') == 5 and 'mk-sbig na' in empty


@needs_node
def test_the_plan_tab_lists_the_published_articles_and_the_drafts_line():
    pub = {'items': [{'id': 7, 'title': 'مقال عن الإيجار', 'published_at': '2026-10-29T08:00:00Z'}, {'id': 9, 'title': 'مقال ثانٍ', 'published_at': '2026-10-27T08:00:00Z'}], 'drafts': 3}
    h = _html('plan', _model(src={'published': {'state': 'ready', 'data': pub}}))
    assert 'مقال عن الإيجار' in h and '٢٩ أكتوبر ٢٠٢٦ · منذ يوم' in h and 'https://elprofessor.net/article.html?id=7' in h and 'rel="noopener"' in h and 'target="_blank"' in h
    assert 'مسودات مقالات لم تُنشر بعد: ٣' in h and 'data-s="content"' in h and 'افتح المحتوى' in h
    assert 'خطة النشر على السوشيال' in h and 'قريبًا' in h and 'mk-madar' not in h and '<img' not in h and 'v3-btn1' not in h
    empty = _html('plan', _model(src={'published': {'state': 'ready', 'data': {'items': [], 'drafts': 0}}}))
    assert 'لم يُنشر مقال على الموقع في آخر ٧ أيام.' in empty and 'مسودات مقالات' not in empty
    down = _html('plan', _model(src={'published': {'state': 'error'}}))
    assert 'مقالات الموقع: غير متاح بعد' in down and 'data-a="retry"' in down


def _visible_text(html):
    html = re.sub(r'<(script|style)\b.*?</\1>', '', html, flags=re.S)
    html = re.sub(r'<input[^>]*>', '', html)
    return re.sub(r'<[^>]+>', ' ', html)


@needs_node
def test_copy_lint_over_the_strings_and_every_rendered_tab():
    strs = _node_json("console.log(JSON.stringify(L.mk.STR))")
    flat = []

    def walk(v):
        if isinstance(v, str):
            flat.append(v)
        elif isinstance(v, list):
            [walk(x) for x in v]
        elif isinstance(v, dict):
            [walk(x) for x in v.values()]
    walk(strs)
    extra = _node_json("console.log(JSON.stringify([L.mk.NEEDS.map(n=>[n.title,n.why,n.chip,n.how]), L.mk.PLATFORM_OPTS.map(o=>o[1]), L.mk.CURRENCY_OPTS.map(o=>o[1]), Object.values(L.mk.PLATFORM_LABEL), Object.values(L.mk.STATUS_LABEL)]))")
    walk(extra)
    for s in flat:
        assert 'يقوّم' not in s and not re.search(r'[A-Za-z]', s), s
        assert not re.match(r'^\s*(ال)?ذكاء', s) and not s.strip().startswith('AI'), s
        for bad in ('CAC', 'ROAS', 'Impressions', 'Clicks', 'API', 'utm', 'بعدين'):
            assert bad not in s, (bad, s)
    att = mkfx.attribution_summary({'winning': 1, 'losing': 2})
    pages = [_html('marketing', _model()), _html('marketing', _model(filter='all', src={'attribution': {'state': 'ready', 'data': att}})), _html('marketing', _model(raw=[])),
             _html('marketing', _model(src={'campaigns': {'state': 'error'}, 'ads': {'state': 'error'}})), _html('social', _model()), _html('plan', _model()),
             _html('plan', _model(src={'published': {'state': 'error'}}))]
    for html in pages:
        txt = _visible_text(html)
        assert 'يقوّم' not in txt
        assert not re.search(r'[A-Za-z]', txt), re.findall(r'[A-Za-z]+', txt)[:5]
        assert not re.search(r'(?<![\w@./-])(undefined|NaN|null|\[object)', txt)
        for h in re.findall(r'<h[23][^>]*>(.*?)</h[23]>', html):
            assert not re.match(r'^\s*(ال)?ذكاء', re.sub(r'<[^>]+>', '', h))
    # كل «غير متاح» ظاهرة نصها «غير متاح بعد» بالحرف
    for html in pages:
        for m in re.findall(r'غير متاح(?! بعد)', _visible_text(html)):
            raise AssertionError('«غير متاح» ناقصة')


@needs_node
def test_cards_for_the_home_round_have_the_decision_card_shape():
    def cards(model):
        p = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'mk_html.js')], input=json.dumps({'tab': 'marketing', 'cards': True, 'model': model}, ensure_ascii=False),
                           capture_output=True, text=True, timeout=60)
        assert p.returncode == 0, p.stderr[-800:]
        return json.loads(p.stdout)['cards']
    got = cards(_model())
    assert [c['kind'] for c in got] == ['mk_losing'] and got[0]['btn'] == 'أوقفها' and got[0]['open'] == 'function'
    assert got[0]['title'].startswith('حملة «خاسرة» صُرف عليها') and got[0]['line'] == 'أقترح إيقافها.'
    assert cards(_model(src={'campaigns': {'state': 'error'}})) == [] and cards(_model(raw=[])) == [], 'بلا مصدر أو بلا حملات: لا بطاقات'
    assert cards(_model(skipped=['losing_2'])) == []


@needs_node
def test_the_lam_prefix_follows_arabic_spelling():
    got = _node_json("console.log(JSON.stringify(['الإيجار','أساسيات التسويق','كتاب','Contract'].map(L.mk.lam)))")
    assert got == ['للإيجار', 'لأساسيات التسويق', 'لكتاب', 'لـContract']
