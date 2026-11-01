# -*- coding: utf-8 -*-
"""مسارات «الأدوات / الاستوديو» في الداشبورد (docs/v2/tools/SPEC.md): نظرة اليوم · مفتاح الإيقاف · الأدوات (تشغيل وسعر ومعاينة) · الأماكن (رفع وتعديل وإظهار وحذف) ·
الإعدادات · العيّنات · التقرير · كنس الاحتفاظ. الجسور على المنصة بديل في الذاكرة.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_tools_routes.py

⛔ صفر شبكة حقيقية وصفر نداء حقيقي (لا إنتاج ولا Higgsfield ولا OpenAI ولا Stripe): المنصة في الذاكرة (`uiharness/tools_fixtures.ToolsPlatform`)،
وأي عنوان برّه `https://platform.test` بيوقّع الاختبار.

اللي بيثبّته:
  ١. أدمن بس (أي دور تاني ٤٠٣) · المفتاح مقفول ٤٠٤ بلا أي نداء · `no-store` على كل رد · السرّ يطلع مع كل نداء.
  ٢. كل كتابة تطلب `confirmed:true` بالظبط (قبل أي نداء) · `by` من التوكن وحده · قايمة بيضا للحقول والردود · تدقيق عند النجاح بس.
  ٣. تعديل الأداة: قراءة ثم دمج ثم كتابة، و`base_updated_at` القديم ⇒ ٤٠٩ بلا كتابة · حارس السعر قبل النداء · تشغيل أداة بلا أماكن مرفوض.
  ٤. المعاينة تجريبية دايمًا (`real:false`)، و`real:true` من الداشبورد مرفوضة بلا نداء.
  ٥. الصورة المرفوعة: النوع من البايتات (لا HTML متنكّر) وتحت ٣ ميجا، والمكان الجديد يتربط بالأداة (نداءان) أو يتعلّم «لم يُربط» لو الربط فشل.
  ٦. حذف مكان: التصميمات المربوطة بشاشات المنصة ما تتحذفش، وآخر أماكن أداة شغّالة كمان.
  ٧. الإعدادات: التحقق قبل النداء (السقف ≤ الحدّ الأقصى ≤ ٥٠، المضاعِف، الأعداد، العملات) · `kill` و`blocked_terms` من غير هذا المسار.
  ٨. رد ضايع على كتابة ⇒ ٥٠٢ و`no_reply` بلا سطر تدقيق نجاح · قراءة غابت ⇒ `bridge_missing`.
  ٩. الكنس بالسرّ وحده (حتى والمفتاح مقفول)، وأرقامه بقايمة بيضا، والتدقيق لما يتمسح شيء بس.
"""
import base64
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
import tools_fixtures as tfx   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NON_ADMIN_ROLES = ['employee', 'trainer', 'investor', 'viewer', 'pending']
ADMIN_EMAIL = 'v2tl-admin@x.test'
CONFIRM_AR = 'لازم تأكّد الأول من الشاشة'
NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 64
JPG = b'\xff\xd8\xff\xe0' + b'\x00' * 64
HTML = b'<html><script>alert(1)</script></html>'


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
        heads = {r: _bearer(_mkuser('v2tl-%s@x.test' % r, r)) for r in NON_ADMIN_ROLES}
        heads['admin'] = _bearer(_mkuser(ADMIN_EMAIL, 'admin'))
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.ef = tfx.ToolsPlatform()
        self.seen = []
        self.blocked = []

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None, data=None, files=None):
        body = copy_json(json)
        if files:       # رفع multipart: الجسم المسجَّل = حقول النموذج + وصف الملف (زي ef_route_harness)
            fk = next(iter(files))
            name, content = files[fk][0], files[fk][1]
            body = dict(data or {}, __file__={'name': name, 'size': len(content), 'head': content[:8].decode('latin-1')})
        elif data is not None:
            body = dict(data)
        self.seen.append({'method': method.upper(), 'url': url, 'path': url[len(PLATFORM):], 'params': dict(params or {}), 'headers': dict(headers or {}),
                          'json': body, 'timeout': timeout, 'multipart': bool(files)})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        out = self.ef.handle(method, url[len(PLATFORM):], params or {}, body or {})
        return _Resp(*(out if out is not None else (200, [])))

    def calls(self, prefix=''):
        return [c for c in self.seen if c['path'].startswith(prefix)]

    def writes(self):
        return [c for c in self.seen if c['method'] != 'GET']


def copy_json(j):
    import copy
    return copy.deepcopy(j)


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


def _call(ctx, method, path, body=None, role='admin', **kw):
    k = {'headers': ctx['heads'][role] if role else {}}
    if body is not None:
        k['json'] = body
    k.update(kw)
    return ctx['client'].open(path, method=method, **k)


def _audits(prefix):
    with flask_app.app_context():
        return [(a.action, a.target, json.loads(a.meta_json or 'null'), a.actor_email) for a in AuditLog.query.filter(AuditLog.action.like(prefix + '%')).order_by(AuditLog.id).all()]


def _clear_audits():
    with flask_app.app_context():
        AuditLog.query.filter(AuditLog.action.like('tools.%')).delete(synchronize_session=False)
        db.session.commit()


T = '/api/v2/tools'
READS = [T + '/overview', T + '/recipes', T + '/settings', T + '/samples', T + '/report']
WRITES = [('POST', T + '/kill', {'kill': True, 'confirmed': True}),
          ('POST', T + '/recipes/headshot/enable', {'enabled': False, 'base_updated_at': 'x', 'confirmed': True}),
          ('PUT', T + '/recipes/headshot', {'est_cost_usd': 0.2, 'base_updated_at': 'x', 'confirmed': True}),
          ('POST', T + '/recipes/headshot/test-render', {}),
          ('PUT', T + '/styles/hs_plain', {'title_ar': 'بسيطة', 'confirmed': True}),
          ('POST', T + '/styles/hs_plain/visible', {'visible': False, 'base_updated_at': 'x', 'confirmed': True}),
          ('DELETE', T + '/styles/hs_plain', {'confirmed': True}),
          ('PUT', T + '/settings', {'changes': {'per_user_daily': 8}, 'confirmed': True}),
          ('POST', T + '/samples/ou-a1b2c3d4', {'action': 'ok', 'confirmed': True})]


def _recipe(plat, rid):
    return plat.ef._recipe(rid)


def _fresh(ctx, plat, rid='headshot'):
    d = _call(ctx, 'GET', T + '/recipes').get_json()
    return next(r for r in d['recipes'] if r['id'] == rid)


def _style_form(**over):
    f = {'id': 'st_a1b2c3d4', 'recipe_id': 'headshot', 'title_ar': 'غرفة اجتماعات', 'place_prompt': 'a quiet meeting room with soft light', 'sort': '5',
         'judge_ok': 'true', 'confirmed': 'true', 'preview': (io.BytesIO(PNG), 'room.png')}
    f.update(over)
    return {k: v for k, v in f.items() if v is not None}


def _post_style(ctx, **over):
    return ctx['client'].post(T + '/styles', data=_style_form(**over), headers=ctx['heads']['admin'], content_type='multipart/form-data')


# ---------------------------------------------------------------- ١) الأدوار والمفتاح و no-store

@pytest.mark.parametrize('role', NON_ADMIN_ROLES)
def test_every_route_is_admin_only(ctx, plat, role):
    for path in READS:
        assert _call(ctx, 'GET', path, role=role).status_code == 403, (role, path)
    for m, path, body in WRITES:
        assert _call(ctx, m, path, body, role=role).status_code == 403, (role, path)
    assert ctx['client'].post(T + '/styles', data=_style_form(), headers=ctx['heads'][role], content_type='multipart/form-data').status_code == 403
    for path in READS:
        assert _call(ctx, 'GET', path, role=None).status_code == 401
    assert plat.seen == []


def test_every_route_is_closed_when_the_switch_is_off_with_no_platform_call(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    for path in READS:
        assert _call(ctx, 'GET', path).status_code == 404, path
    for m, path, body in WRITES:
        assert _call(ctx, m, path, body).status_code == 404, path
    assert _post_style(ctx).status_code == 404
    assert plat.seen == []


def test_every_reply_is_no_store_and_the_secret_goes_out(ctx, plat):
    rs = [_call(ctx, 'GET', p) for p in READS] + [_call(ctx, m, p, b) for m, p, b in WRITES] + [_post_style(ctx)]
    assert all(r.headers.get('Cache-Control') == 'no-store' for r in rs), [r.headers.get('Cache-Control') for r in rs]
    assert plat.seen and all(c['headers'].get('X-ELP-Metrics-Secret') == SECRET for c in plat.seen)


# ---------------------------------------------------------------- ٢) نظرة اليوم ومفتاح الإيقاف

def test_overview_merges_the_platform_state_with_todays_report_and_whitelists(ctx, plat, monkeypatch):
    import v2_tools_routes as vt
    monkeypatch.setattr(vt, 'utc_today', lambda: datetime.date(2026, 11, 1))
    plat.ef.tools_flags = {'tools_enabled': False, 'provider': 'mock', 'topup_enabled': False, 'secret_key': 'sk-live'}
    d = _call(ctx, 'GET', T + '/overview').get_json()
    assert d['flags'] == {'tools_enabled': False, 'provider': 'mock', 'topup_enabled': False}
    assert d['today'] == {'cap_usd': 10.0, 'spent_usd': 2.4, 'remaining_usd': 7.6, 'kill': False, 'paused': False, 'reason': None}
    assert d['jobs'] == {'count': 43, 'succeeded': 41, 'failures': 2} and d['day'] == '2026-11-01'
    assert d['ffmpeg'] is True and d['raqm'] is True
    assert 'secret_key' not in json.dumps(d)
    rep = plat.calls('/api/bridge/tools/report')[0]
    assert rep['params'] == {'from': '2026-11-01', 'to': '2026-11-01'}


def test_overview_survives_a_failed_report_and_says_so(ctx, plat):
    plat.ef.down.add('/api/bridge/tools/report')
    r = _call(ctx, 'GET', T + '/overview')
    assert r.status_code == 200 and r.get_json()['jobs'] is None


def test_a_bridge_the_platform_does_not_have_yet_says_bridge_missing(ctx, plat):
    plat.ef.tools_missing = True
    for path in READS:
        r = _call(ctx, 'GET', path)
        assert r.status_code == 404 and r.get_json().get('bridge_missing') is True, path


def test_overview_paused_by_the_cap_is_reported(ctx, plat):
    plat.ef.tools_spent = 9.95
    d = _call(ctx, 'GET', T + '/overview').get_json()
    assert d['today']['paused'] is True and d['today']['reason'] == 'cap'


def test_kill_needs_the_exact_confirmation_and_a_boolean_before_any_call(ctx, plat):
    for body, code in (({'kill': True}, 400), ({'kill': True, 'confirmed': 'true'}, 400), ({'kill': True, 'confirmed': 1}, 400),
                       ({'kill': 'yes', 'confirmed': True}, 400), ({'confirmed': True}, 400)):
        r = _call(ctx, 'POST', T + '/kill', body)
        assert r.status_code == code, body
    assert _call(ctx, 'POST', T + '/kill', {'kill': True}).get_json()['error'] == CONFIRM_AR
    assert plat.seen == []


def test_kill_and_resume_write_one_settings_call_with_by_from_the_token_and_audit(ctx, plat):
    _clear_audits()
    r = _call(ctx, 'POST', T + '/kill', {'kill': True, 'confirmed': True, 'by': 'evil@x.test'})
    assert r.status_code == 200 and r.get_json() == {'kill': True}
    w = plat.writes()
    assert len(w) == 1 and w[0]['method'] == 'PUT' and w[0]['path'] == '/api/bridge/tools/settings'
    assert w[0]['json'] == {'settings': {'kill': True}, 'by': ADMIN_EMAIL}
    assert plat.ef.tools_settings['kill'] is True
    assert _call(ctx, 'GET', T + '/overview').get_json()['today']['reason'] == 'kill'
    r2 = _call(ctx, 'POST', T + '/kill', {'kill': False, 'confirmed': True})
    assert r2.get_json() == {'kill': False} and plat.ef.tools_settings['kill'] is False
    assert [a[0] for a in _audits('tools.')] == ['tools.kill', 'tools.resume']


def test_a_lost_reply_on_kill_is_no_reply_not_rejected(ctx, plat):
    _clear_audits()
    plat.ef.forced[('PUT', '/api/bridge/tools/settings')] = (504, {'detail': 'gateway timeout'})
    r = _call(ctx, 'POST', T + '/kill', {'kill': True, 'confirmed': True})
    assert r.status_code == 502 and r.get_json() == {'error': NO_REPLY_AR, 'no_reply': True}
    assert [a[0] for a in _audits('tools.')] == ['tools.no_reply']


# ---------------------------------------------------------------- ٣) الأدوات (الوصفات)

def test_recipes_list_whitelists_fields_and_hides_prompts(ctx, plat):
    plat.ef.tools_recipes[0]['secret_note'] = 'x'
    d = _call(ctx, 'GET', T + '/recipes').get_json()
    assert [r['id'] for r in d['recipes']] == ['headshot', 'linkedin', 'post', 'card', 'trend_video']
    h = d['recipes'][0]
    assert h['enabled'] is True and h['price']['EGP'] == 20 and h['free_rule'] == 'once_per_verified_account' and h['est_cost_usd'] == 0.12
    assert h['styles'] == ['hs_office', 'hs_library', 'hs_entrance', 'hs_plain'] and h['sizes'] == ['4x5', 'square']
    blob = json.dumps(d)
    assert 'prompt_template' not in blob and 'secret_note' not in blob and 'model_params' not in blob
    assert d['groups'] == ['photo', 'social', 'video_cards']
    assert all(s['preview_data'].startswith('data:image/jpeg;base64,') for s in d['styles'] if s['id'].startswith('hs_'))
    assert all(set(s) <= {'id', 'recipe_id', 'title_ar', 'place_prompt', 'judge_ok', 'uses_provider', 'hidden', 'kind', 'sort', 'enabled', 'preview_asset_id', 'updated_at', 'updated_by', 'preview_data'} for s in d['styles'])


def test_a_preview_that_is_not_an_image_data_url_never_reaches_the_screen(ctx, plat):
    plat.ef.tools_styles[0]['preview_data'] = 'javascript:alert(1)'
    plat.ef.tools_styles[1]['preview_data'] = 'data:text/html;base64,PHNjcmlwdD4='
    d = _call(ctx, 'GET', T + '/recipes').get_json()
    by = {s['id']: s for s in d['styles']}
    assert by['hs_office']['preview_data'] == '' and by['hs_library']['preview_data'] == ''


def test_enable_needs_the_confirmation_and_a_boolean(ctx, plat):
    base = _fresh(ctx, plat, 'linkedin')['updated_at']
    n = len(plat.seen)
    assert _call(ctx, 'POST', T + '/recipes/linkedin/enable', {'enabled': True, 'base_updated_at': base}).status_code == 400
    assert _call(ctx, 'POST', T + '/recipes/linkedin/enable', {'enabled': 'on', 'base_updated_at': base, 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', T + '/recipes/Bad Id/enable', {'enabled': True, 'base_updated_at': base, 'confirmed': True}).status_code in (400, 404)
    assert len(plat.seen) == n and plat.writes() == []


def test_enable_a_recipe_sends_the_whole_recipe_back_with_only_that_switch_changed(ctx, plat):
    _clear_audits()
    base = _fresh(ctx, plat, 'linkedin')['updated_at']
    before = json.loads(json.dumps(_recipe(plat, 'linkedin')))
    r = _call(ctx, 'POST', T + '/recipes/linkedin/enable', {'enabled': True, 'base_updated_at': base, 'confirmed': True, 'by': 'evil@x.test'})
    assert r.status_code == 200 and r.get_json()['recipe']['enabled'] is True
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/tools/recipes/linkedin' and w[0]['json']['by'] == ADMIN_EMAIL
    sent = w[0]['json']['recipe']
    for k in ('prompt_template', 'price', 'styles', 'sizes', 'est_cost_usd', 'free_rule', 'model'):
        assert sent[k] == before[k], k
    assert sent['enabled'] is True and _recipe(plat, 'linkedin')['enabled'] is True
    assert _audits('tools.')[-1][:3] == ('tools.recipe_enable', 'linkedin', {'enabled': True})


def test_disable_works_and_a_second_press_is_a_conflict_not_a_write(ctx, plat):
    base = _fresh(ctx, plat, 'card')['updated_at']
    assert _call(ctx, 'POST', T + '/recipes/card/enable', {'enabled': False, 'base_updated_at': base, 'confirmed': True}).status_code == 200
    n = len(plat.writes())
    new_base = _fresh(ctx, plat, 'card')['updated_at']
    r = _call(ctx, 'POST', T + '/recipes/card/enable', {'enabled': False, 'base_updated_at': new_base, 'confirmed': True})
    assert r.status_code == 409 and 'موقوفة بالفعل' in r.get_json()['error'] and len(plat.writes()) == n
    # تشغيلها من جديد (يرجّع الحالة لباقي الاختبارات)
    assert _call(ctx, 'POST', T + '/recipes/card/enable', {'enabled': True, 'base_updated_at': new_base, 'confirmed': True}).status_code == 200


def test_a_stale_page_is_refused_with_409_and_no_write(ctx, plat):
    old = _fresh(ctx, plat, 'post')['updated_at']
    plat.ef._put_recipe('post', {'by': 'someone-else', 'recipe': dict(_recipe(plat, 'post'), sub_ar='نص جديد')})     # تعديل من مكان تاني
    n = len(plat.writes())
    for path, method, body in ((T + '/recipes/post/enable', 'POST', {'enabled': True}), (T + '/recipes/post', 'PUT', {'est_cost_usd': 0.05})):
        r = _call(ctx, method, path, dict(body, base_updated_at=old, confirmed=True))
        assert r.status_code == 409 and r.get_json()['error'].startswith('تغيّرت هذه الأداة'), path
    r = _call(ctx, 'POST', T + '/recipes/post/enable', {'enabled': True, 'confirmed': True})
    assert r.status_code == 409
    assert len(plat.writes()) == n
    assert _recipe(plat, 'post')['enabled'] is False


def test_enabling_a_recipe_with_no_places_is_refused(ctx, plat):
    base = _fresh(ctx, plat, 'trend_video')['updated_at']
    _recipe(plat, 'trend_video')['styles'] = []
    base = _fresh(ctx, plat, 'trend_video')['updated_at']
    n = len(plat.writes())
    r = _call(ctx, 'POST', T + '/recipes/trend_video/enable', {'enabled': True, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 422 and 'أضف مكانًا' in r.get_json()['error'] and len(plat.writes()) == n
    _recipe(plat, 'trend_video')['styles'] = ['tv_calm', 'tv_light']


def test_enabling_a_brain_draft_clears_the_draft_mark(ctx, plat):
    _recipe(plat, 'linkedin')['draft'] = True
    _recipe(plat, 'linkedin')['enabled'] = False
    base = _fresh(ctx, plat, 'linkedin')['updated_at']
    assert _call(ctx, 'POST', T + '/recipes/linkedin/enable', {'enabled': True, 'base_updated_at': base, 'confirmed': True}).status_code == 200
    assert plat.writes()[-1]['json']['recipe']['draft'] is False
    _recipe(plat, 'linkedin')['enabled'] = False


def test_an_unknown_recipe_is_404_and_a_platform_rejection_passes_through_in_arabic(ctx, plat):
    assert _call(ctx, 'POST', T + '/recipes/nope_x/enable', {'enabled': True, 'base_updated_at': 'x', 'confirmed': True}).status_code == 404
    base = _fresh(ctx, plat, 'post')['updated_at']
    plat.ef.forced[('PUT', '/api/bridge/tools/recipes/post')] = (422, {'detail': 'سعر EGP أقل من الحد الأدنى (التكلفة × 3)'})
    r = _call(ctx, 'POST', T + '/recipes/post/enable', {'enabled': True, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 422 and 'أقل من الحد الأدنى' in r.get_json()['error']


def test_a_lost_reply_on_enable_is_no_reply_with_no_success_audit(ctx, plat):
    _clear_audits()
    base = _fresh(ctx, plat, 'linkedin')['updated_at']
    plat.ef.forced[('PUT', '/api/bridge/tools/recipes/linkedin')] = (503, {'detail': 'unavailable'})
    r = _call(ctx, 'POST', T + '/recipes/linkedin/enable', {'enabled': True, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 502 and r.get_json().get('no_reply') is True
    assert [a[0] for a in _audits('tools.')] == ['tools.no_reply']


def _edit(ctx, plat, rid, body, **kw):
    base = _fresh(ctx, plat, rid)['updated_at']
    return _call(ctx, 'PUT', T + '/recipes/' + rid, dict({'base_updated_at': base, 'confirmed': True}, **body), **kw)


PRICE_OK = {'EGP': 25, 'SAR': 6, 'AED': 6, 'QAR': 6, 'KWD': 0.5, 'OMR': 0.6, 'USD': 1.5}


def test_edit_the_price_cost_and_free_rule_writes_the_merged_recipe(ctx, plat):
    _clear_audits()
    before = json.loads(json.dumps(_recipe(plat, 'headshot')))
    r = _edit(ctx, plat, 'headshot', {'price': PRICE_OK, 'est_cost_usd': 0.1, 'free_rule': 'daily:2'})
    assert r.status_code == 200, r.get_json()
    sent = plat.writes()[-1]['json']
    assert sent['by'] == ADMIN_EMAIL and sent['recipe']['price'] == PRICE_OK and sent['recipe']['est_cost_usd'] == 0.1 and sent['recipe']['free_rule'] == 'daily:2'
    assert sent['recipe']['styles'] == before['styles'] and sent['recipe']['enabled'] is True
    assert _audits('tools.')[-1][:3] == ('tools.recipe_edit', 'headshot', {'keys': ['est_cost_usd', 'free_rule', 'price']})
    r = _edit(ctx, plat, 'headshot', {'price': before['price'], 'est_cost_usd': before['est_cost_usd'], 'free_rule': before['free_rule']})
    assert r.status_code == 200


@pytest.mark.parametrize('body,frag', [
    ({'price': {'EGP': 20}}, 'العملات السبع'),
    ({'price': dict(PRICE_OK, EGP=-1)}, 'سعر الجنيه'),
    ({'price': dict(PRICE_OK, SAR='5')}, 'سعر الريال السعودي'),
    ({'price': dict(PRICE_OK, USD=True)}, 'سعر الدولار'),
    ({'price': dict(PRICE_OK, KWD=0.12345)}, 'سعر الدينار الكويتي'),
    ({'price': dict(PRICE_OK, OMR=100001)}, 'سعر الريال العماني'),
    ({'est_cost_usd': -0.1}, 'التكلفة التقديرية'),
    ({'est_cost_usd': 21}, 'التكلفة التقديرية'),
    ({'est_cost_usd': '0.1'}, 'التكلفة التقديرية'),
    ({'free_rule': 'weekly:1'}, 'القاعدة المجانية'),
    ({'free_rule': 'daily:0'}, 'القاعدة المجانية'),
    ({'free_rule': 'daily:1000'}, 'القاعدة المجانية'),
    ({'free_rule': 5}, 'القاعدة المجانية'),
    ({}, 'لا يوجد تغيير'),
])
def test_edit_validation_runs_before_any_platform_write(ctx, plat, body, frag):
    base = _fresh(ctx, plat, 'headshot')['updated_at']
    n = len(plat.seen)
    r = _call(ctx, 'PUT', T + '/recipes/headshot', dict(body, base_updated_at=base, confirmed=True))
    assert r.status_code == 400 and frag in r.get_json()['error'], r.get_json()
    assert len(plat.seen) == n


def test_the_price_guard_refuses_below_the_multiple_before_the_platform_is_called(ctx, plat):
    n = len(plat.writes())
    r = _edit(ctx, plat, 'headshot', {'price': dict(PRICE_OK, EGP=5)})        # ٥ جنيه = ٠٫١ دولار < ٠٫١٢ × ٣
    assert r.status_code == 422 and 'أقل من الحد الأدنى' in r.get_json()['error'] and 'الجنيه' in r.get_json()['error']
    assert len(plat.writes()) == n
    r = _edit(ctx, plat, 'headshot', {'price': dict(PRICE_OK, EGP=0), 'free_rule': 'none'})
    assert r.status_code == 422 and 'صفر' in r.get_json()['error'] and len(plat.writes()) == n
    r = _edit(ctx, plat, 'headshot', {'price': dict(PRICE_OK, EGP=0)})              # سعر صفر مع قاعدة مجانية معرّفة مسموح
    assert r.status_code == 200
    assert _edit(ctx, plat, 'headshot', {'price': ORIG_PRICE}).status_code == 200


ORIG_PRICE = {'EGP': 20, 'SAR': 5, 'AED': 5, 'QAR': 5, 'KWD': 0.4, 'OMR': 0.5, 'USD': 1}


def test_a_video_recipe_uses_the_video_multiple(ctx, plat):
    # ٠٫٦ × ٢٫٥ = ١٫٥ دولار ⇒ ٧٥ جنيه أدنى حدّ
    r = _edit(ctx, plat, 'trend_video', {'price': {'EGP': 70, 'SAR': 38, 'AED': 37, 'QAR': 37, 'KWD': 3, 'OMR': 3.8, 'USD': 10}})
    assert r.status_code == 422 and 'الجنيه' in r.get_json()['error']
    r = _edit(ctx, plat, 'trend_video', {'price': {'EGP': 75, 'SAR': 38, 'AED': 37, 'QAR': 37, 'KWD': 3, 'OMR': 3.8, 'USD': 10}})
    assert r.status_code == 200
    _edit(ctx, plat, 'trend_video', {'price': {'EGP': 150, 'SAR': 38, 'AED': 37, 'QAR': 37, 'KWD': 3, 'OMR': 3.8, 'USD': 10}})


def test_edit_with_no_real_difference_is_refused_without_a_write(ctx, plat):
    n = len(plat.writes())
    r = _edit(ctx, plat, 'headshot', {'est_cost_usd': 0.12})
    assert r.status_code == 400 and r.get_json()['error'] == 'لا فرق عن القيم الحالية' and len(plat.writes()) == n


# ---------------------------------------------------------------- ٤) المعاينة التجريبية

def test_test_render_is_always_mock_and_needs_no_confirmation(ctx, plat):
    r = _call(ctx, 'POST', T + '/recipes/headshot/test-render', {'style_id': 'hs_library'})
    d = r.get_json()
    assert r.status_code == 200 and d['provider'] == 'mock' and len(d['images']) == 2 and d['uses_provider'] is True
    assert all(i.startswith('data:image/png;base64,') for i in d['images'])
    c = plat.calls('/api/bridge/tools/test-render')[0]
    assert c['json'] == {'style_id': 'hs_library', 'real': False, 'by': ADMIN_EMAIL} or c['json']['real'] is False
    assert plat.ef.renders == [('headshot', 'hs_library')]


def test_a_real_render_from_the_dashboard_is_refused_with_no_platform_call(ctx, plat):
    for body in ({'real': True}, {'real': 'true'}, {'real': 1, 'style_id': 'hs_plain'}):
        r = _call(ctx, 'POST', T + '/recipes/headshot/test-render', body)
        assert r.status_code == 400 and 'تجريبية فقط' in r.get_json()['error'], body
    assert plat.seen == []


def test_test_render_for_a_video_recipe_returns_no_images_and_bad_ids_are_refused(ctx, plat):
    assert _call(ctx, 'POST', T + '/recipes/trend_video/test-render', {}).get_json()['images'] == []
    assert _call(ctx, 'POST', T + '/recipes/headshot/test-render', {'style_id': '../x'}).status_code == 400
    assert _call(ctx, 'POST', T + '/recipes/headshot/test-render', {'style_id': 'no_such'}).status_code == 422


def test_test_render_only_lets_real_image_data_urls_through(ctx, plat):
    plat.ef.forced[('POST', '/api/bridge/tools/test-render/headshot')] = (200, {'ok': True, 'images': ['javascript:alert(1)', 'data:text/html;base64,AAAA', tfx.render_png()], 'uses_provider': True})
    d = _call(ctx, 'POST', T + '/recipes/headshot/test-render', {}).get_json()
    assert len(d['images']) == 1 and d['images'][0].startswith('data:image/png;base64,')


# ---------------------------------------------------------------- ٥) الأماكن والأنماط

def test_create_a_style_needs_the_form_confirmation_before_any_call(ctx, plat):
    assert _post_style(ctx, confirmed=None).status_code == 400
    assert _post_style(ctx, confirmed='yes').status_code == 400
    assert plat.seen == []


def test_create_a_style_uploads_the_picture_and_attaches_it_to_the_recipe(ctx, plat):
    _clear_audits()
    r = _post_style(ctx)
    d = r.get_json()
    assert r.status_code == 200 and d['attached'] is True and d['attach_failed'] is False and d['style']['id'] == 'st_a1b2c3d4'
    w = plat.writes()
    assert [(c['method'], c['path']) for c in w] == [('POST', '/api/bridge/tools/styles'), ('PUT', '/api/bridge/tools/recipes/headshot')]
    up = w[0]
    assert up['multipart'] is True and up['json']['by'] == ADMIN_EMAIL and 'confirmed' not in up['json']
    assert up['json']['id'] == 'st_a1b2c3d4' and up['json']['recipe_id'] == 'headshot' and up['json']['judge_ok'] == 'true' and up['json']['uses_provider'] == 'true'
    assert up['json']['kind'] == 'scene' and up['json']['sort'] == '5' and up['json']['__file__']['head'].startswith('\x89PNG')
    assert w[1]['json']['recipe']['styles'][-1] == 'st_a1b2c3d4'
    assert _audits('tools.')[-1][:3] == ('tools.style_create', 'st_a1b2c3d4', {'recipe': 'headshot', 'attached': True, 'size': len(PNG)})
    # تنضيف
    assert _call(ctx, 'DELETE', T + '/styles/st_a1b2c3d4', {'confirmed': True}).status_code == 200


def test_create_a_style_without_attaching_makes_one_write(ctx, plat):
    r = _post_style(ctx, id='st_b2c3d4e5', attach='false', judge_ok='false', preview=(io.BytesIO(JPG), 'r.jpg'))
    d = r.get_json()
    assert r.status_code == 200 and d['attached'] is False and d['attach_failed'] is False
    assert len(plat.writes()) == 1 and plat.writes()[0]['json']['judge_ok'] == 'false'
    assert 'st_b2c3d4e5' not in _recipe(plat, 'headshot')['styles']
    _call(ctx, 'DELETE', T + '/styles/st_b2c3d4e5', {'confirmed': True})


def test_a_failed_attach_still_reports_the_created_style_and_how_to_finish(ctx, plat):
    plat.ef.forced[('PUT', '/api/bridge/tools/recipes/headshot')] = (502, {'detail': 'تعذر'})
    r = _post_style(ctx, id='st_c3d4e5f6')
    d = r.get_json()
    assert r.status_code == 200 and d['attached'] is False and d['attach_failed'] is True and d['style']['id'] == 'st_c3d4e5f6'
    del plat.ef.forced[('PUT', '/api/bridge/tools/recipes/headshot')]
    _call(ctx, 'DELETE', T + '/styles/st_c3d4e5f6', {'confirmed': True})


@pytest.mark.parametrize('over,code,frag', [
    ({'id': 'Bad Id'}, 400, 'معرّف غير صالح'),
    ({'recipe_id': '../x'}, 400, 'معرّف غير صالح'),
    ({'title_ar': ''}, 400, 'اسم المكان'),
    ({'title_ar': 'ا' * 61}, 400, 'اسم المكان'),
    ({'place_prompt': ''}, 400, 'صف المكان'),
    ({'place_prompt': 'x' * 401}, 400, 'وصف المكان'),
    ({'sort': 'abc'}, 400, 'الترتيب'),
    ({'sort': '1000'}, 400, 'الترتيب'),
    ({'preview': None}, 400, 'اختر صورة المكان'),
])
def test_create_style_validation_runs_before_any_platform_call(ctx, plat, over, code, frag):
    r = _post_style(ctx, **over)
    assert r.status_code == code and frag in r.get_json()['error'], r.get_json()
    assert plat.seen == []


def test_the_uploaded_file_type_comes_from_the_bytes_not_the_name(ctx, plat):
    r = _post_style(ctx, preview=(io.BytesIO(HTML), 'room.png'))
    assert r.status_code == 400 and 'ليس صورة صالحة' in r.get_json()['error']
    r = _post_style(ctx, preview=(io.BytesIO(b''), 'room.png'))
    assert r.status_code == 400
    assert plat.seen == []
    r = _post_style(ctx, id='st_d4e5f6a7', preview=(io.BytesIO(b'RIFF\x00\x00\x00\x00WEBPVP8 ' + b'\x00' * 32), 'room.webp'), attach='false')
    assert r.status_code == 200
    _call(ctx, 'DELETE', T + '/styles/st_d4e5f6a7', {'confirmed': True})


def test_an_upload_over_three_megabytes_is_refused_before_any_call(ctx, plat):
    big = PNG + b'\x00' * (3 * 1024 * 1024 + 10)
    r = _post_style(ctx, preview=(io.BytesIO(big), 'big.png'))
    assert r.status_code == 413 and '٣ ميجا' in r.get_json()['error'] and plat.seen == []


def test_a_code_only_recipe_takes_no_places_and_a_duplicate_id_is_a_conflict(ctx, plat):
    r = _post_style(ctx, recipe_id='card', id='st_e5f6a7b8')
    assert r.status_code == 400 and 'بالكود' in r.get_json()['error']
    assert _post_style(ctx, recipe_id='no_such_recipe', id='st_f6a7b8c9').status_code == 404
    r = _post_style(ctx, id='hs_plain')
    assert r.status_code == 409 and plat.writes() == []


def test_a_lost_reply_on_the_upload_is_no_reply_and_the_retry_is_a_conflict_not_a_duplicate(ctx, plat):
    _clear_audits()
    plat.ef.forced[('POST', '/api/bridge/tools/styles')] = (504, {'detail': 'timeout'})
    r = _post_style(ctx, id='st_a7b8c9d0')
    assert r.status_code == 502 and r.get_json().get('no_reply') is True
    assert [a[0] for a in _audits('tools.')] == ['tools.no_reply']
    del plat.ef.forced[('POST', '/api/bridge/tools/styles')]
    assert _post_style(ctx, id='st_a7b8c9d0', attach='false').status_code == 200          # الرد ضاع لكن الكتابة تمّت؟ هنا لا: المنصة ما كتبتش
    assert _post_style(ctx, id='st_a7b8c9d0', attach='false').status_code == 409           # الضغطة التانية بنفس المعرّف ⇒ تعارض لا تكرار
    _call(ctx, 'DELETE', T + '/styles/st_a7b8c9d0', {'confirmed': True})


def test_edit_a_style_forwards_only_the_changed_clean_fields(ctx, plat):
    _clear_audits()
    r = _call(ctx, 'PUT', T + '/styles/hs_plain', {'title_ar': 'خلفية هادئة', 'sort': 7, 'judge_ok': False, 'place_prompt': 'a soft grey wall', 'confirmed': True, 'by': 'evil', 'kind': 'x', 'hidden': True})
    assert r.status_code == 200 and r.get_json()['style']['title_ar'] == 'خلفية هادئة'
    sent = plat.writes()[-1]['json']
    assert sent == {'style': {'title_ar': 'خلفية هادئة', 'sort': 7, 'judge_ok': False, 'place_prompt': 'a soft grey wall'}, 'by': ADMIN_EMAIL}
    assert _audits('tools.')[-1][:3] == ('tools.style_edit', 'hs_plain', {'keys': ['judge_ok', 'place_prompt', 'sort', 'title_ar']})
    _call(ctx, 'PUT', T + '/styles/hs_plain', {'title_ar': 'خلفية بسيطة', 'sort': 4, 'judge_ok': True, 'place_prompt': 'a plain softly lit neutral studio backdrop in warm grey', 'confirmed': True})


@pytest.mark.parametrize('body', [
    {'title_ar': ''}, {'title_ar': 'ا' * 61}, {'title_ar': 5}, {'place_prompt': 'x' * 401}, {'sort': -1}, {'sort': 1000}, {'sort': '3'}, {'sort': True},
    {'judge_ok': 'yes'}, {'preview_data': 'data:text/html;base64,PGI+'}, {'preview_data': 'data:image/png;base64,@@@@'}, {'preview_data': 'http://x/y.png'},
    {'preview_data': 'data:image/png;base64,' + base64.b64encode(HTML).decode()}, {}])
def test_edit_a_style_validation_runs_before_any_call(ctx, plat, body):
    r = _call(ctx, 'PUT', T + '/styles/hs_plain', dict(body, confirmed=True))
    assert r.status_code == 400, (body, r.get_json())
    assert plat.seen == []


def test_replace_the_picture_checks_the_bytes_after_decoding(ctx, plat):
    good = 'data:image/png;base64,' + base64.b64encode(PNG).decode()
    assert _call(ctx, 'PUT', T + '/styles/hs_plain', {'preview_data': good, 'confirmed': True}).status_code == 200
    assert plat.writes()[-1]['json']['style']['preview_data'] == good
    big = 'data:image/png;base64,' + base64.b64encode(PNG + b'\x00' * (3 * 1024 * 1024 + 5)).decode()
    r = _call(ctx, 'PUT', T + '/styles/hs_plain', {'preview_data': big, 'confirmed': True})
    assert r.status_code == 400 and '٣ ميجا' in r.get_json()['error']
    assert _call(ctx, 'PUT', T + '/styles/no_such_style', {'title_ar': 'س', 'confirmed': True}).status_code == 404


def test_show_and_hide_a_style_edits_the_recipes_list_with_the_stale_check(ctx, plat):
    _clear_audits()
    base = _fresh(ctx, plat, 'headshot')['updated_at']
    r = _call(ctx, 'POST', T + '/styles/hs_plain/visible', {'visible': False, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['recipe']['styles'] == ['hs_office', 'hs_library', 'hs_entrance']
    assert plat.writes()[-1]['json']['recipe']['styles'] == ['hs_office', 'hs_library', 'hs_entrance']
    n = len(plat.writes())
    r = _call(ctx, 'POST', T + '/styles/hs_plain/visible', {'visible': False, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 409 and len(plat.writes()) == n                  # الصفحة قديمة
    base = _fresh(ctx, plat, 'headshot')['updated_at']
    r = _call(ctx, 'POST', T + '/styles/hs_plain/visible', {'visible': False, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 409 and 'مخفي بالفعل' in r.get_json()['error']
    r = _call(ctx, 'POST', T + '/styles/hs_plain/visible', {'visible': True, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 200 and r.get_json()['recipe']['styles'][-1] == 'hs_plain'
    assert [a[0] for a in _audits('tools.')] == ['tools.style_hide', 'tools.style_show']
    assert _call(ctx, 'POST', T + '/styles/hs_plain/visible', {'visible': 'yes', 'base_updated_at': base, 'confirmed': True}).status_code == 400


def test_hiding_the_last_place_of_a_running_recipe_is_refused(ctx, plat):
    _recipe(plat, 'headshot')['styles'] = ['hs_plain']
    base = _fresh(ctx, plat, 'headshot')['updated_at']
    n = len(plat.writes())
    r = _call(ctx, 'POST', T + '/styles/hs_plain/visible', {'visible': False, 'base_updated_at': base, 'confirmed': True})
    assert r.status_code == 422 and 'آخر أماكن' in r.get_json()['error'] and len(plat.writes()) == n
    _recipe(plat, 'headshot')['styles'] = ['hs_office', 'hs_library', 'hs_entrance', 'hs_plain']


def test_delete_a_style_needs_confirmation_and_removes_it(ctx, plat):
    _clear_audits()
    assert _post_style(ctx, id='st_b8c9d0e1', attach='false').status_code == 200
    n = len(plat.seen)
    assert _call(ctx, 'DELETE', T + '/styles/st_b8c9d0e1', {}).status_code == 400
    assert _call(ctx, 'DELETE', T + '/styles/st_b8c9d0e1', {'confirmed': 'true'}).status_code == 400
    assert len(plat.seen) == n
    r = _call(ctx, 'DELETE', T + '/styles/st_b8c9d0e1', {'confirmed': True})
    assert r.status_code == 200 and r.get_json() == {'ok': True}
    assert plat.ef._style('st_b8c9d0e1') is None
    assert _audits('tools.')[-1][:3] == ('tools.style_delete', 'st_b8c9d0e1', {'recipe': 'headshot'})
    assert _call(ctx, 'DELETE', T + '/styles/st_b8c9d0e1', {'confirmed': True}).status_code == 404


def test_styles_tied_to_screens_in_the_platform_are_never_deleted(ctx, plat):
    n = len(plat.writes())
    for sid in ('card_expert', 'card_cert', 'card_winner'):
        r = _call(ctx, 'DELETE', T + '/styles/' + sid, {'confirmed': True})
        assert r.status_code == 422 and 'مرتبط بشاشات' in r.get_json()['error'], sid
    assert len(plat.writes()) == n


def test_the_last_place_of_a_running_recipe_cannot_be_deleted(ctx, plat):
    _recipe(plat, 'headshot')['styles'] = ['hs_plain']
    n = len(plat.writes())
    r = _call(ctx, 'DELETE', T + '/styles/hs_plain', {'confirmed': True})
    assert r.status_code == 422 and 'آخر أماكن' in r.get_json()['error'] and len(plat.writes()) == n
    _recipe(plat, 'headshot')['styles'] = ['hs_office', 'hs_library', 'hs_entrance', 'hs_plain']


# ---------------------------------------------------------------- ٦) الإعدادات

def test_settings_view_is_a_whitelist_with_the_absolute_limit(ctx, plat):
    plat.ef.tools_settings['provider_key'] = 'sk-123'
    d = _call(ctx, 'GET', T + '/settings').get_json()
    assert d['daily_cap_usd'] == 10 and d['daily_cap_max_usd'] == 20 and d['absolute_max_usd'] == 50 and d['kill'] is False
    assert d['topup_min_by_currency'] == {'EGP': 100, 'SAR': 15, 'AED': 15, 'QAR': 15, 'KWD': 1, 'OMR': 1, 'USD': 3} and d['topup_max_egp'] == 10000
    assert d['image_min_multiple'] == 3 and d['video_min_multiple'] == 2.5 and d['per_user_daily'] == 10 and d['per_ip_daily'] == 30 and d['sample_pct'] == 5
    assert d['rates']['EGP'] == 50 and d['blocked_terms_count'] == 4 and 'blocked_terms' not in d and 'provider_key' not in json.dumps(d)
    del plat.ef.tools_settings['provider_key']


def _put_settings(ctx, changes, **kw):
    return _call(ctx, 'PUT', T + '/settings', dict({'changes': changes, 'confirmed': True}, **kw))


def test_settings_save_needs_confirmation_and_forwards_only_the_changes(ctx, plat):
    _clear_audits()
    assert _call(ctx, 'PUT', T + '/settings', {'changes': {'per_user_daily': 8}}).status_code == 400
    assert plat.seen == []
    r = _put_settings(ctx, {'daily_cap_usd': 15, 'per_user_daily': 8, 'topup_min_by_currency': {'EGP': 150}, 'next_line': 'الجاي: لينكدإن قوي'}, by='evil')
    assert r.status_code == 200, r.get_json()
    sent = plat.writes()[-1]['json']
    assert sent == {'settings': {'daily_cap_usd': 15.0, 'per_user_daily': 8, 'topup_min_by_currency': {'EGP': 150}, 'next_line': 'الجاي: لينكدإن قوي'}, 'by': ADMIN_EMAIL}
    d = r.get_json()
    assert d['daily_cap_usd'] == 15 and d['topup_min_by_currency']['EGP'] == 150 and d['topup_min_by_currency']['SAR'] == 15
    assert _audits('tools.')[-1][:3] == ('tools.settings', 'settings', {'keys': ['daily_cap_usd', 'next_line', 'per_user_daily', 'topup_min_by_currency']})
    _put_settings(ctx, {'daily_cap_usd': 10, 'per_user_daily': 10, 'topup_min_by_currency': {'EGP': 100}, 'next_line': ''})


@pytest.mark.parametrize('changes,frag', [
    ({'daily_cap_usd': 25}, 'لا يزيد على 20'),
    ({'daily_cap_usd': 0}, 'السقف اليومي'),
    ({'daily_cap_usd': -5}, 'السقف اليومي'),
    ({'daily_cap_usd': '10'}, 'السقف اليومي'),
    ({'daily_cap_usd': True}, 'السقف اليومي'),
    ({'daily_cap_usd': 10.123}, 'السقف اليومي'),
    ({'daily_cap_max_usd': 51}, 'لا يزيد على 50'),
    ({'daily_cap_max_usd': 0}, 'أعلى سقف'),
    ({'daily_cap_max_usd': 30, 'daily_cap_usd': 31}, 'لا يزيد على 30'),
    ({'image_min_multiple': 0.5}, 'المضاعِف'),
    ({'video_min_multiple': 21}, 'المضاعِف'),
    ({'per_user_daily': 0}, 'حد المستخدم اليومي'),
    ({'per_user_daily': 201}, 'حد المستخدم اليومي'),
    ({'per_user_daily': 5.5}, 'حد المستخدم اليومي'),
    ({'per_ip_daily': 1001}, 'حد الشبكة اليومي'),
    ({'free_posts_daily': -1}, 'البوستات المجانية'),
    ({'sample_pct': 101}, 'نسبة العيّنات'),
    ({'retry_limit': 11}, 'إعادات المحاولة'),
    ({'topup_max_egp': 99}, 'سقف الشحن'),
    ({'topup_max_egp': 1000.5}, 'سقف الشحن'),
    ({'next_line': 'ا' * 81}, 'أقصر من ٨٠'),
    ({'next_line': 5}, 'أقصر من ٨٠'),
    ({'rates': {'EGP': 0}}, 'سعر الصرف'),
    ({'rates': {'XXX': 3}}, 'عملة غير معروفة'),
    ({'rates': {}}, 'غير صالح'),
    ({'topup_min_by_currency': {'SAR': 0}}, 'أقل شحنة'),
    ({'topup_min_by_currency': {'SAR': 1.5}}, 'أقل شحنة'),
    ({'topup_min_by_currency': {'GBP': 5}}, 'عملة غير معروفة'),
    ({'topup_min_by_currency': 'x'}, 'غير صالح'),
    ({'kill': True}, 'غير مسموح'),
    ({'blocked_terms': ['x']}, 'غير مسموح'),
    ({'rate': 1}, 'غير مسموح'),
    ({}, 'لا يوجد تغيير'),
])
def test_settings_validation_runs_before_any_platform_write(ctx, plat, changes, frag):
    r = _put_settings(ctx, changes)
    assert r.status_code == 422 and frag in r.get_json()['error'], (changes, r.get_json())
    assert plat.writes() == []


def test_the_daily_cap_may_reach_the_absolute_maximum_in_two_explicit_steps(ctx, plat):
    assert _put_settings(ctx, {'daily_cap_max_usd': 50}).status_code == 200
    assert plat.ef.tools_settings['daily_cap_max_usd'] == 50
    assert _put_settings(ctx, {'daily_cap_usd': 45}).status_code == 200
    assert _put_settings(ctx, {'daily_cap_max_usd': 20, 'daily_cap_usd': 10}).status_code == 200
    assert plat.ef.tools_settings['daily_cap_usd'] == 10 and plat.ef.tools_settings['daily_cap_max_usd'] == 20


def test_a_platform_rejection_of_settings_passes_through(ctx, plat):
    plat.ef.forced[('PUT', '/api/bridge/tools/settings')] = (422, {'detail': 'أعلى سقف مسموح به لا يزيد على ٥٠ دولارًا'})
    r = _put_settings(ctx, {'per_user_daily': 9})
    assert r.status_code == 422 and 'أعلى سقف' in r.get_json()['error']


# ---------------------------------------------------------------- ٧) العيّنات

def test_samples_list_is_a_whitelist_and_drops_bad_previews(ctx, plat):
    plat.ef.tools_samples[0]['preview'] = 'javascript:alert(1)'
    plat.ef.tools_samples[0]['extra'] = 'x'
    d = _call(ctx, 'GET', T + '/samples').get_json()
    assert [s['id'] for s in d['samples']] == ['ou-a1b2c3d4', 'ou-e5f6a7b8', 'ou-c9d0e1f2', 'ou-13572468']
    assert d['samples'][0]['preview'] == '' and d['samples'][1]['preview'].startswith('data:image/jpeg;base64,')
    assert all(set(s) == {'id', 'email', 'recipe_id', 'style_id', 'created_at', 'sizes', 'preview'} for s in d['samples'])
    assert plat.calls('/api/bridge/tools/samples')[0]['params'] == {'limit': 50}
    plat.ef.tools_samples[0]['preview'] = tfx._jpeg_data(tfx._silhouette)
    del plat.ef.tools_samples[0]['extra']


def test_a_sample_action_needs_confirmation_and_a_known_action(ctx, plat):
    assert _call(ctx, 'POST', T + '/samples/ou-a1b2c3d4', {'action': 'ok'}).status_code == 400
    assert _call(ctx, 'POST', T + '/samples/ou-a1b2c3d4', {'action': 'delete', 'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', T + '/samples/ou-a1b2c3d4', {'confirmed': True}).status_code == 400
    assert _call(ctx, 'POST', T + '/samples/x', {'action': 'ok', 'confirmed': True}).status_code == 400
    assert plat.seen == []


def test_ok_hide_and_ban_each_write_once_with_by_from_the_token(ctx, plat):
    _clear_audits()
    r = _call(ctx, 'POST', T + '/samples/ou-e5f6a7b8', {'action': 'ok', 'confirmed': True, 'by': 'evil'})
    assert r.status_code == 200 and r.get_json() == {'id': 'ou-e5f6a7b8', 'status': 'ok', 'banned': False, 'refunded': 0}
    assert plat.writes()[-1]['json'] == {'action': 'ok', 'by': ADMIN_EMAIL}
    r = _call(ctx, 'POST', T + '/samples/ou-a1b2c3d4', {'action': 'hide', 'confirmed': True})
    assert r.get_json() == {'id': 'ou-a1b2c3d4', 'status': 'hidden', 'banned': False, 'refunded': 1}
    r = _call(ctx, 'POST', T + '/samples/ou-13572468', {'action': 'ban_user', 'confirmed': True})
    assert r.get_json() == {'id': 'ou-13572468', 'status': 'hidden', 'banned': True, 'refunded': 1}
    assert len(plat.writes()) == 3
    assert [a[:3] for a in _audits('tools.')] == [('tools.sample_ok', 'ou-e5f6a7b8', {'refunded': 0}), ('tools.sample_hide', 'ou-a1b2c3d4', {'refunded': 1}),
                                                   ('tools.sample_ban_user', 'ou-13572468', {'refunded': 1})]
    assert [s['id'] for s in _call(ctx, 'GET', T + '/samples').get_json()['samples']] == ['ou-c9d0e1f2']


def test_a_sample_the_platform_does_not_know_is_404_and_a_lost_reply_is_no_reply(ctx, plat):
    _clear_audits()
    assert _call(ctx, 'POST', T + '/samples/ou-zzzzzzzz', {'action': 'ok', 'confirmed': True}).status_code == 404
    plat.ef.forced[('POST', '/api/bridge/tools/samples/ou-c9d0e1f2')] = (504, {'detail': 'timeout'})
    r = _call(ctx, 'POST', T + '/samples/ou-c9d0e1f2', {'action': 'hide', 'confirmed': True})
    assert r.status_code == 502 and r.get_json().get('no_reply') is True
    assert [a[0] for a in _audits('tools.')] == ['tools.no_reply']


# ---------------------------------------------------------------- ٨) التقرير

def test_report_today_week_and_custom_send_utc_dates_to_the_platform(ctx, plat, monkeypatch):
    import v2_tools_routes as vt
    monkeypatch.setattr(vt, 'utc_today', lambda: datetime.date(2026, 11, 1))
    d = _call(ctx, 'GET', T + '/report?range=today').get_json()
    assert (d['from'], d['to'], d['range']) == ('2026-11-01', '2026-11-01', 'today')
    assert d['recipes'][0]['recipe_id'] == 'headshot' and d['recipes'][0]['count'] == 31 and d['recipes'][0]['revenue_by_currency'] == {'EGP': 460, 'SAR': 20}
    d = _call(ctx, 'GET', T + '/report?range=week').get_json()
    assert (d['from'], d['to']) == ('2026-10-26', '2026-11-01') and d['recipes'][0]['count'] == 186
    d = _call(ctx, 'GET', T + '/report?range=custom&from=2026-10-01&to=2026-10-15').get_json()
    assert (d['from'], d['to'], d['range']) == ('2026-10-01', '2026-10-15', 'custom')
    d = _call(ctx, 'GET', T + '/report?range=bogus').get_json()
    assert d['range'] == 'today'
    assert [c['params'] for c in plat.calls('/api/bridge/tools/report')] == [{'from': '2026-11-01', 'to': '2026-11-01'}, {'from': '2026-10-26', 'to': '2026-11-01'},
                                                                           {'from': '2026-10-01', 'to': '2026-10-15'}, {'from': '2026-11-01', 'to': '2026-11-01'}]


@pytest.mark.parametrize('q', ['range=custom', 'range=custom&from=2026-10-01', 'range=custom&from=2026-13-01&to=2026-13-02', 'range=custom&from=abc&to=def',
                               'range=custom&from=2026-10-10&to=2026-10-01', 'range=custom&from=2024-01-01&to=2026-01-01', 'range=custom&from=2026-1-1&to=2026-1-2'])
def test_a_bad_custom_range_is_refused_before_any_call(ctx, plat, q):
    r = _call(ctx, 'GET', T + '/report?' + q)
    assert r.status_code == 422, r.get_json()
    assert plat.seen == []


def test_topups_show_only_when_the_platform_really_sends_them_and_never_as_a_zero(ctx, plat):
    assert _call(ctx, 'GET', T + '/report').get_json()['topups'] is None
    plat.ef.tools_topups = {'by_currency': {'EGP': 1500, 'SAR': 45, 'XXX': 9}, 'count': 7, 'secret': 'x'}
    d = _call(ctx, 'GET', T + '/report').get_json()
    assert d['topups'] == {'by_currency': {'EGP': 1500, 'SAR': 45}, 'count': 7}
    plat.ef.tools_topups = {'by_currency': 'x'}
    assert _call(ctx, 'GET', T + '/report').get_json()['topups'] is None
    plat.ef.tools_topups = None


def test_report_rows_are_whitelisted_and_numbers_are_numbers(ctx, plat):
    plat.ef.tools_report[0]['api_key'] = 'sk-1'
    plat.ef.tools_report[1]['count'] = 'many'
    d = _call(ctx, 'GET', T + '/report').get_json()
    assert 'api_key' not in json.dumps(d) and d['recipes'][1]['count'] == 0
    del plat.ef.tools_report[0]['api_key']
    plat.ef.tools_report[1]['count'] = 12


# ---------------------------------------------------------------- ٩) كنس الاحتفاظ

def test_the_hourly_sweep_needs_the_platform_secret_and_nothing_else(ctx, plat):
    c = ctx['client']
    assert c.post(T + '/sweep-cron').status_code == 401
    assert c.post(T + '/sweep-cron', headers={'X-ELP-Metrics-Secret': 'wrong'}).status_code == 401
    assert c.post(T + '/sweep-cron', headers=ctx['heads']['admin']).status_code == 401        # توكن أدمن لا يكفي
    assert plat.seen == []
    r = c.post(T + '/sweep-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200 and r.get_json() == {'ok': True, 'inputs': 0, 'outputs_expired': 0, 'outputs_removed': 0, 'jobs_stale': 0}
    assert r.headers.get('Cache-Control') == 'no-store'
    w = plat.writes()
    assert len(w) == 1 and w[0]['path'] == '/api/bridge/tools/sweep' and w[0]['headers']['X-ELP-Metrics-Secret'] == SECRET


def test_the_sweep_runs_even_when_the_dashboard_switch_is_closed(ctx, plat, monkeypatch):
    monkeypatch.delenv('DASH_V2_ENABLED', raising=False)
    r = ctx['client'].post(T + '/sweep-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 200 and len(plat.writes()) == 1


def test_the_sweep_audits_only_when_something_was_removed_and_whitelists_the_counts(ctx, plat):
    _clear_audits()
    c = ctx['client']
    c.post(T + '/sweep-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert _audits('tools.sweep') == []
    plat.ef.sweep_result = {'inputs': 3, 'outputs_expired': 2, 'outputs_removed': 1, 'jobs_stale': 0, 'leak': 'x'}
    r = c.post(T + '/sweep-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.get_json() == {'ok': True, 'inputs': 3, 'outputs_expired': 2, 'outputs_removed': 1, 'jobs_stale': 0}
    a = _audits('tools.sweep')
    assert len(a) == 1 and a[0][0] == 'tools.sweep_cron' and a[0][2] == {'inputs': 3, 'outputs_expired': 2, 'outputs_removed': 1, 'jobs_stale': 0} and a[0][3] == 'cron'
    plat.ef.sweep_result = {'inputs': 0, 'outputs_expired': 0, 'outputs_removed': 0, 'jobs_stale': 0}


def test_a_failed_sweep_is_a_502_the_cron_can_see(ctx, plat):
    plat.ef.down.add('/api/bridge/tools/sweep')
    r = ctx['client'].post(T + '/sweep-cron', headers={'X-ELP-Metrics-Secret': SECRET})
    assert r.status_code == 502


# ---------------------------------------------------------------- ١٠) الإعداد

def test_the_registration_is_guarded_in_app_and_the_dockerfile_copies_the_module():
    app_src = open(os.path.join(ROOT, 'backend', 'app.py'), encoding='utf-8').read()
    assert "import v2_tools_routes as _v2s_tools; _v2s_tools.register(app, globals())" in app_src and "logger.exception('v2 tools routes not loaded')" in app_src
    assert app_src.index('import v2_tools_routes') < app_src.index('# ---- v2 section routes end')
    df = open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()
    assert 'COPY backend/v2_tools_routes.py /app/v2_tools_routes.py' in df


def test_no_route_ever_sends_a_real_flag_or_a_confirmation_to_the_platform(ctx, plat):
    _call(ctx, 'POST', T + '/recipes/headshot/test-render', {'style_id': 'hs_plain'})
    _call(ctx, 'POST', T + '/kill', {'kill': True, 'confirmed': True})
    _call(ctx, 'POST', T + '/kill', {'kill': False, 'confirmed': True})
    for c in plat.writes():
        j = c['json'] or {}
        assert 'confirmed' not in json.dumps(j) and j.get('real') in (None, False), c
