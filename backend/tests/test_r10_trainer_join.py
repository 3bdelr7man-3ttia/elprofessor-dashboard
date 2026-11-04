# -*- coding: utf-8 -*-
"""R10 §D — طلب الانضمام الواحد (خبير / مدرّب / الاثنان) في الداشبورد.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r10_trainer_join.py

⛔ صفر شبكة حقيقية: المنصة دالة في الذاكرة تسجّل النداءات، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
  ١. المسارات: إلغاء · تأجيل يومين · إلغاء المتأخر (الأدوار، المسار والجسم المرسَلين للمنصة، التدقيق عند النجاح بس، رفض المنصة يمرّ كما هو).
  ٢. المنطق (node): صفة الانضمام · الخدمات · حالة الفيديو (أُرسل / لاحقًا / فات / أُلغي تلقائيًا) · عدّاد المتأخر · الطلب القديم بلا تغيير.
  ٣. الواجهة (نصوص المصدر): الأزرار والتصفية والتنبيه في الرئيسية، ونصوص بلا «·» جنب أرقام ولا «استشار».
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
NOW = 1793000000000        # ثابت: 2026-10-26 تقريبًا، لا يعتمد على ساعة الجهاز


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _iso(ms):
    return datetime.datetime.fromtimestamp(ms / 1000.0, datetime.timezone.utc).isoformat()


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
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
        heads = {r: _bearer(_mkuser('r10-%s@x.test' % r, r)) for r in ('admin', 'employee', 'viewer', 'investor', 'trainer')}
        yield {'heads': heads, 'client': flask_app.test_client()}


class Plat(object):
    def __init__(self):
        self.seen = []
        self.blocked = []
        self.reply = None          # (status, body) لتجربة رفض المنصة

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):], 'json': json, 'params': params, 'headers': headers})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        if self.reply:
            return _Resp(*self.reply)
        if url.endswith('/expire-sweep'):
            return _Resp(200, {'checked': 3, 'cancelled': 2, 'ids': ['ta-1', 'ta-2']})
        return _Resp(200, {'id': 'ta-1', 'status': 'cancelled'})


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


def _post(ctx, path, body=None, who='admin'):
    return ctx['client'].post(path, headers={} if who is None else ctx['heads'][who], json=body)


def _audits(action):
    return AuditLog.query.filter_by(action=action).count()


# ——————————————————————————————————————————————————————— ١. المسارات
def test_cancel_goes_to_the_bridge_without_needing_a_reason_and_is_audited(ctx, plat):
    n0 = _audits('trainer_application.cancel')
    r = _post(ctx, '/api/platform-trainer-applications/ta-1/cancel', {})
    assert r.status_code == 200
    call = plat.seen[-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/trainer-applications/ta-1/cancel'
    assert call['json'] == {'admin_note': ''}                       # الإلغاء ليس رفضًا: لا سبب مطلوب
    assert call['headers'] == {'X-ELP-Metrics-Secret': SECRET}
    assert _audits('trainer_application.cancel') == n0 + 1


def test_postpone_sends_no_body_and_is_audited(ctx, plat):
    n0 = _audits('trainer_application.postpone')
    r = _post(ctx, '/api/platform-trainer-applications/ta-2/postpone', {'days': 30, 'admin_note': 'x'})
    assert r.status_code == 200
    call = plat.seen[-1]
    assert call['path'] == '/api/bridge/trainer-applications/ta-2/postpone' and call['json'] is None      # ٤٨ ساعة ثابتة على المنصة
    assert _audits('trainer_application.postpone') == n0 + 1


def test_expire_sweep_proxy_returns_counts_and_audits_the_number(ctx, plat):
    n0 = _audits('trainer_application.expire_sweep')
    r = _post(ctx, '/api/platform-trainer-applications/expire-sweep', {})
    assert r.status_code == 200 and r.get_json()['cancelled'] == 2
    call = plat.seen[-1]
    assert call['method'] == 'POST' and call['path'] == '/api/bridge/trainer-applications/expire-sweep'
    assert _audits('trainer_application.expire_sweep') == n0 + 1
    row = AuditLog.query.filter_by(action='trainer_application.expire_sweep').order_by(AuditLog.id.desc()).first()
    assert json.loads(row.meta_json) == {'cancelled': 2, 'checked': 3}


def test_platform_refusal_passes_through_and_nothing_is_audited(ctx, plat):
    plat.reply = (409, {'detail': 'لا يمكن إلغاء طلب صدر فيه قرار'})
    for path, act in (('/api/platform-trainer-applications/ta-9/cancel', 'cancel'), ('/api/platform-trainer-applications/ta-9/postpone', 'postpone'),
                      ('/api/platform-trainer-applications/expire-sweep', 'expire_sweep')):
        n0 = _audits('trainer_application.' + act)
        r = _post(ctx, path, {})
        assert r.status_code == 409 and r.get_json()['error'] == 'لا يمكن إلغاء طلب صدر فيه قرار'
        assert _audits('trainer_application.' + act) == n0


def test_roles_follow_the_existing_decision_rule(ctx, plat):
    for path in ('/api/platform-trainer-applications/ta-1/cancel', '/api/platform-trainer-applications/ta-1/postpone', '/api/platform-trainer-applications/expire-sweep'):
        assert _post(ctx, path, {}, who=None).status_code == 401
        for role in ('viewer', 'investor', 'trainer'):
            assert _post(ctx, path, {}, who=role).status_code == 403, (path, role)
        assert _post(ctx, path, {}, who='employee').status_code == 200
    assert plat.blocked == []


def test_unknown_action_is_still_refused_and_reject_still_needs_a_reason(ctx, plat):
    n = len(plat.seen)
    assert _post(ctx, '/api/platform-trainer-applications/ta-1/delete', {}).status_code == 400
    assert _post(ctx, '/api/platform-trainer-applications/ta-1/reject', {}).status_code == 400
    assert len(plat.seen) == n                                       # لا نداء للمنصة في الحالتين


def test_the_bridge_list_filter_is_passed_through_for_cancelled(ctx, plat):
    plat.reply = (200, {'applications': [], 'count': 0})
    r = ctx['client'].get('/api/platform-trainer-applications?status=cancelled', headers=ctx['heads']['admin'])
    assert r.status_code == 200
    assert plat.seen[-1]['params'] == {'status': 'cancelled'} and plat.seen[-1]['path'] == '/api/bridge/trainer-applications'


# ——————————————————————————————————————————————————————— ٢. المنطق (node)
def _co(fn, *args):
    return v2_node.logic('v2s.courses.' + fn, *args)


def _app(**kw):
    base = {'id': 'ta-n', 'status': 'pending', 'user_name': 'منى', 'user_email': 'mona@example.test', 'headline': 'قانون العمل', 'expertise': ['عمل'],
            'experience_summary': '', 'linkedin_url': '', 'contact_phone': '+201000000000', 'created_at': _iso(NOW - 3600 * 1000), 'updated_at': _iso(NOW - 3600 * 1000)}
    base.update(kw)
    return base


@needs_node
def test_join_as_and_claimed_slugs_show_on_the_ticket():
    t = _co('appTickets', [_app(join_as='both', claimed_slugs=['contract-review', 'legal-notice'])], {'now': NOW})[0]
    assert t['joinAs'] == 'both' and t['joinAsText'] == 'خبير ومدرّب' and t['hasJoin'] is True
    assert t['claimed'] == ['contract-review', 'legal-notice']
    assert _co('appTickets', [_app(join_as='expert')], {'now': NOW})[0]['joinAsText'] == 'خبير'
    assert _co('appTickets', [_app(join_as='trainer')], {'now': NOW})[0]['joinAsText'] == 'مدرّب'
    # شكل غريب ⇒ يُقرأ مدرّبًا بلا انهيار، والخدمات غير النصية تُهمل
    odd = _co('appTickets', [_app(join_as='x', claimed_slugs=[None, 5, '  ', 'ok'])], {'now': NOW})[0]
    assert odd['joinAs'] == 'trainer' and odd['hasJoin'] is False and odd['claimed'] == ['ok']


@needs_node
def test_the_one_form_has_no_cv_or_summary_so_phone_and_field_are_enough():
    t = _co('appTickets', [_app(join_as='expert')], {'now': NOW})[0]
    assert t['missing'] == [] and t['suggestion'] == 'accept' and 'رقم تواصل' in t['line'] and 'نبذة' not in t['line']
    none = _co('appTickets', [_app(join_as='expert', contact_phone='', expertise=[], headline='')], {'now': NOW})[0]
    assert none['suggestion'] == 'open' and none['missing'] == ['رابط أو رقم للتواصل', 'مجال واحد على الأقل']


@needs_node
def test_old_application_without_join_as_reads_as_trainer_and_keeps_its_line():
    old = {'id': 'ta-1', 'status': 'pending', 'user_name': 'أ', 'user_email': 'a@x.test', 'headline': 'ه', 'expertise': ['عقود', 'شركات', 'ملكية فكرية'],
           'experience_summary': 'عملت اثنتي عشرة سنة في مكاتب محاماة تجارية، وأدرّب المحامين الجدد على صياغة العقود.', 'linkedin_url': 'https://l.test/a',
           'portfolio_url': 'https://a.test', 'cv_url': 'https://cv.test/a.pdf', 'created_at': _iso(NOW - 3600 * 1000)}
    t = _co('appTickets', [old], {'now': NOW})[0]
    assert t['joinAs'] == 'trainer' and t['hasJoin'] is False and t['claimed'] == []
    assert t['line'] == '٣ مجالات، لينكدإن، سيرة ذاتية، نماذج أعمال'
    assert t['video'] == {'kind': 'none', 'text': '', 'open': False}      # لا ندّعي «فيديو ناقص» على طلب قديم بلا موعد


@needs_node
def test_video_state_table():
    due_future, due_past = _iso(NOW + 24 * 3600 * 1000), _iso(NOW - 3600 * 1000)
    sent = _co('appTickets', [_app(join_as='trainer', intro_video_url='https://youtu.be/abc', video_due_at=due_past)], {'now': NOW})[0]['video']
    assert sent == {'kind': 'sent', 'text': 'أُرسل الفيديو', 'open': False}
    later = _co('appTickets', [_app(join_as='both', video_due_at=due_future)], {'now': NOW})[0]['video']
    assert later['kind'] == 'later' and later['open'] is True and later['text'].startswith('لاحقًا: آخر موعد ') and 'T' not in later['text'] and '-' not in later['text']
    over = _co('appTickets', [_app(join_as='trainer', video_due_at=due_past)], {'now': NOW})[0]['video']
    assert over['kind'] == 'overdue' and over['overdue'] is True and over['text'].endswith('وقد فات')
    miss = _co('appTickets', [_app(join_as='trainer')], {'now': NOW})[0]['video']
    assert miss == {'kind': 'missing', 'text': 'لم يُرسل الفيديو بعد', 'open': True}
    exp = _co('appTickets', [_app(join_as='expert', video_due_at=due_past)], {'now': NOW})[0]['video']
    assert exp['kind'] == 'none' and exp['open'] is False                  # الخبير وحده بلا فيديو
    auto = _co('appTickets', [_app(join_as='trainer', status='cancelled', cancel_reason='video_overdue', cancelled_at=_iso(NOW))], {'now': NOW})[0]
    assert auto['video'] == {'kind': 'cancelled', 'text': 'أُلغي تلقائيًا', 'open': False} and auto['status'] == 'cancelled'
    hand = _co('appTickets', [_app(join_as='trainer', status='cancelled', cancel_reason='manual')], {'now': NOW})[0]['video']
    assert hand['text'] == 'أُلغي'


@needs_node
def test_overdue_count_matches_the_platform_sweep_rule():
    past, future = _iso(NOW - 1000), _iso(NOW + 3600 * 1000)
    rows = [_app(id='a', join_as='trainer', video_due_at=past),                                     # يُحسب
            _app(id='b', join_as='both', video_due_at=past),                                        # يُحسب
            _app(id='c', join_as='expert', video_due_at=past),                                      # خبير وحده: لا
            _app(id='d', join_as='trainer', video_due_at=past, intro_video_url='https://youtu.be/x'),  # الفيديو وصل: لا
            _app(id='e', join_as='trainer', video_due_at=future),                                   # لم يفت: لا
            _app(id='f', join_as='trainer'),                                                        # بلا موعد: لا
            _app(id='g', join_as='trainer', video_due_at=past, status='needs_info'),               # الكنسة تتخطّاه: لا
            _app(id='h', join_as='trainer', video_due_at=past, status='cancelled'),                # ملغي: لا
            _app(id='i', video_due_at=past)]                                                        # طلب قديم بموعد ⇒ مدرّب ⇒ يُحسب
    assert _co('videoOverdueCount', rows, NOW) == 3
    assert _co('videoOverdueCount', [], NOW) == 0
    assert _co('videoOverdueCount', None, NOW) is None                     # مصدر فاشل ⇒ لا صفر كاذب
    assert _co('videoOverdueLine', 3) == 'طلبات انضمام فات موعد الفيديو: ٣'


# ——————————————————————————————————————————————————————— ٣. الواجهة (المصدر)
def test_courses_screen_has_cancel_postpone_filter_and_sweep():
    js = _read('dashboard-cloud', 'v2s', 'courses.js')
    for w in ("data-a=\"appcancel\"", "data-a=\"apppostpone\"", "data-a=\"appsweep\"", "data-a=\"appsview\"", ">تأجيل يومين<", ">إلغاء<", "إلغاء المتأخر",
              "'/platform-trainer-applications/' + encodeURIComponent(id) + '/cancel'", "'/platform-trainer-applications/' + encodeURIComponent(id) + '/postpone'",
              "'/platform-trainer-applications/expire-sweep'", "status=cancelled", "أُلغيت"):
        assert w in js, w
    # الأزرار لا تظهر إلا حيث الفيديو ناقص والطلب معلّق (الخادم هو الحَكَم بعدها)
    assert "a.video.open" in js
    # خبير وحده: لا اتفاقية تدريب في نص القبول
    i = js.index('function openAppAccept')
    body = js[i:i + 1700]
    assert "a.joinAs === 'expert'" in body and 'لا اتفاقية تدريب' in body


def test_home_shows_the_overdue_strip_with_a_confirm_step():
    js = _read('dashboard-cloud', 'v2s', 'home.js')
    for w in ("INBOX_VIDEO_OVERDUE", "videoOverdueLine", "إلغاء المتأخر", "sweep_ask", "sweep_go", "sweep_x", "trainerExpireSweep"):
        assert w in js, w
    api = _read('dashboard-cloud', 'dashboard-api.js')
    assert 'EP.trainerExpireSweep' in api and '"/platform-trainer-applications/expire-sweep"' in api
    assert 'window.INBOX_VIDEO_OVERDUE = videoOverdue' in api


def _between(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


def test_new_visible_copy_has_no_banned_words():
    # كتلنا الجديدة فقط (بقية الملف نصوصه قديمة ومراجَعة): لا «·» جنب رقم، لا «استشار»، لا كلام استرداد، لا «يقوّم»
    co = _read('dashboard-cloud', 'v2s', 'courses.js')
    home = _read('dashboard-cloud', 'v2s', 'home.js')
    blocks = [_between(co, '// R10: صفة الانضمام', '  function trainerRowHtml'), _between(co, 'function overdueCount', 'function drawTrainers'),
              _between(co, '// R10: إلغاء طلب لم يصل', '  function openAppDetail'), _between(home, 'R10 §E.3: طلبات انضمام', '// وضع الخدمة')]
    added = ''
    for src in blocks:
        for m in re.finditer(r"'([^'\n]*[\u0600-\u06FF][^'\n]*)'", src):
            added += m.group(1) + '\n'
    assert 'تأجيل يومين' in added and 'إلغاء المتأخر' in added                   # الفحص فعلًا شايف نصوصنا
    for bad in ('استشار', 'استرداد', 'يقوّم', 'ردّ المبلغ'):
        assert bad not in added, bad
    assert not re.search(r'[0-9\u0660-\u0669]\s*·|·\s*[0-9\u0660-\u0669]', added)


def test_backend_routes_are_registered_once():
    src = _read('backend', 'app.py')
    assert src.count("'/api/platform-trainer-applications/expire-sweep'") == 1
    assert "('approve', 'reject', 'cancel', 'postpone')" in src
