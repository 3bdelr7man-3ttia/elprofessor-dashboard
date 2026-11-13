# -*- coding: utf-8 -*-
"""R24 م٣ — مستويات العقل · «راجعت…» على البطاقة · التعلّم بعد ٨ موافقات · «عمل لوحده» و«رجّعها».

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_r24_dash_p3.py

⛔ صفر شبكة حقيقية وصفر نداء ذكاء مدفوع وصفر تليجرام/إيميل: المنصة `FakePlatform` في الذاكرة (أي نداء `requests` بيوقّع الاختبار)،
والموديل مزيّف (`Script`/`ai_call`)، والواجهة بتتشغّل في node:vm بردود جاهزة (`uiharness/r24p3_ui.js`).
  ١. الجدول والحارس: كل منتج مسجّل له صف · الفلوس والنشر والرسايل ⇒ ٤٠٩ في الخادم · نوع فعله ما بيتعكسش ⇒ ٤٠٩ · شبكة الأمان بالاسم · الافتراضي زي النهارده.
  ٢. المسارات: أدمن بس · المفتاح مقفول ٤٠٤ · تغيير المستوى بتدقيق · مزامنة مفتاح المنتج القديم · توزيع الملفات (إعداد المنصة) · القديم ما بيلفّش على الحارس.
  ٣. التعلّم: ٨ موافقات متتالية من غير تعديل (زي ما هي بس) · التعديل والرفض والتغيير يصفّروا · «لا» تسكّت ٣٠ يوم · «آه» ⇒ لوحده بنفس الحارس.
  ٤. «عمل لوحده»: ما بيتنفّذ إلا على «لوحده» · زائر عادي وتعليق مسيء بوضوح بس · سقف · مصدر واقع ⇒ ولا فعل · سجل برجوع · «رجّعها» مرة واحدة · رجوع مستحيل ⇒ جملة صريحة.
  ٥. مراجعة طلبات الانضمام: حقائق بلا اسم ولا إيميل · سقف الجولة · قالب لو الذكاء وقع · نقط صادقة · `/reviews`.
  ٦. الواجهة (node): جدول المستويات · «تخليها لوحده؟» · «راجعت…» · شريطة السؤال · صندوق «العقل عمل لوحده» · تسجيل القرار للتعلّم.
  ٧. ثابت: الـDockerfile بيشحن الملفات الجديدة · index.html · app.py · نصوص بلا «·» جنب رقم عربي · CLAUDE.md وSTATUS.md.
"""
import datetime
import json
import os
import re
import subprocess
import sys

import pytest
from sqlalchemy import text

import app as appmod
from app import app as flask_app, db, AuditLog
from brain2 import alone, autorun, engine, levels, registry
from brain2 import producers_apply
from brain2.contract import Ctx, SourceDown, Target

from test_brain2_engine import env, fp, use, rows, run, F1, F2, F3   # noqa: F401  (env = fixture)
from test_brain2_routes import api   # noqa: F401  (api = fixture)

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
NS = appmod.__dict__
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')
ACTOR = 'founder@x.test'


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


# ——————————————————————————————————————————————————————— أدوات

class FakePlatform(object):
    """المنصة في الذاكرة: زوّار · تعليقات · طلبات انضمام · وثائق هوية · إعداد التوزيع. أي مسار غير معروف ⇒ ٤٠٤. ولا شبكة."""

    def __init__(self):
        self.calls = []
        self.users = []
        self.opinions = []
        self.apps = []
        self.idocs = []
        self.pmsgs = []
        self.leads = []
        self.down = set()           # مسارات ترجّع ٥٠٢
        self.access_fail = False
        self.auto_assign_fail = False

    def _r(self, payload, status=200):
        return (appmod.jsonify(payload), status)

    def __call__(self, method, path, params=None, json_body=None, timeout=12, data=None, files=None):
        self.calls.append((method, path, params, json_body))
        if path in self.down:
            return self._r({'error': 'تعذر الاتصال بالمنصة'}, 502)
        if method == 'GET' and path == '/api/bridge/pending-users':
            return self._r({'users': self.users})
        m = re.match(r'^/api/bridge/users/([^/]+)/access$', path)
        if method == 'POST' and m:
            if self.access_fail:
                return self._r({'error': 'المنصة رفضت'}, 409)
            return self._r({'ok': True, 'id': m.group(1), 'access': json_body.get('access')})
        if method == 'GET' and path == '/api/bridge/opinions':
            return self._r(self.opinions)
        m = re.match(r'^/api/bridge/opinions/([^/]+)/(approve|reject)$', path)
        if method == 'POST' and m:
            return self._r({'ok': True})
        if method == 'GET' and path == '/api/bridge/messages':
            return self._r({'messages': self.pmsgs})
        if method == 'GET' and path == '/api/bridge/leads':
            return self._r({'leads': self.leads})
        if method == 'GET' and path == '/api/bridge/trainer-applications':
            return self._r({'applications': self.apps})
        if method == 'GET' and path == '/api/bridge/identity-docs':
            return self._r({'items': self.idocs})
        if method == 'PUT' and path == '/api/bridge/expert-files/settings':
            if self.auto_assign_fail:
                return self._r({'error': 'المنصة ما قبلتش'}, 502)
            return self._r({'auto_assign': json_body.get('auto_assign')})
        return self._r({'error': 'not found'}, 404)

    def paths(self, method=None):
        return [c[1] for c in self.calls if method is None or c[0] == method]


def visitor(uid, email=None, flags=None, status='requested', name=None):
    return {'id': uid, 'email': email if email is not None else 'u%s@x.test' % uid, 'full_name': name or ('زائر ' + uid),
            'flag_labels': flags or [], 'invite_request': {'status': status, 'requested_at': '2026-11-13T08:00:00Z'}}


def opinion(oid, abusive=True, checked=True, status='pending', topic='موضوع'):
    return {'id': oid, 'status': status, 'topic_title': topic, 'body': 'نص', 'ai_moderation': {'ai_checked': checked, 'abusive': abusive}}


def application(aid, **kw):
    a = {'id': aid, 'status': 'pending', 'user_name': 'منى عبد الحميد', 'user_email': 'mona%s@x.test' % aid, 'join_as': 'both',
         'headline': 'محامية بالنقض', 'specialty': 'عقود', 'years_experience': '12', 'attachments': [{'name': 'cv.pdf'}],
         'intro_video_url': 'https://v.example/1'}
    a.update(kw)
    return a


@pytest.fixture()
def fx(env, api, monkeypatch):    # noqa: F811
    """بيئة المحرّك المزيّفة + منصة في الذاكرة + جداول م٣ نضيفة."""
    plat = FakePlatform()
    monkeypatch.setattr(appmod, '_platform_proxy', plat)
    monkeypatch.setattr(appmod, '_ef_bridge', lambda method, path, params=None, json_body=None, timeout=12, errors=None: plat(method, path, params, json_body))
    levels.ensure(db)

    def wipe():
        for t in ('brain_levels', 'alone_log', 'brain_learn', 'brain_learn_ask'):
            db.session.execute(text('DELETE FROM ' + t))
        AuditLog.query.filter(AuditLog.action.like('brain.%')).delete(synchronize_session=False)
        db.session.commit()
    wipe()
    engine._SWEEP['at'] = 0.0

    class X(object):
        pass
    x = X()
    x.plat, x.api, x.env = plat, api, env
    yield x
    wipe()


def audits(action, target=None):
    q = AuditLog.query.filter_by(action=action)
    if target:
        q = q.filter_by(target=target)
    return q.all()


def level(wt):
    return levels.level_of(NS, wt)


def put_level(x, wt, lv, role='admin'):
    return x.api.put('/api/v2/brain/levels/' + wt, {'level': lv}, role=role)


def report(x, wt, outcome, n=1):
    for i in range(n):
        r = x.api.post('/api/v2/brain/learn', {'work_type': wt, 'outcome': outcome, 'ref': 'c%d' % i})
        assert r.status_code == 200, r.get_json()


def prompts(x):
    r = x.api.get('/api/v2/brain/learn')
    assert r.status_code == 200
    return {p['work_type']: p for p in r.get_json()['prompts']}


_SEQ = [0]


def seed_items(pid, outcomes, base=None):
    """صفوف قرارات حقيقية لمنتج (الأحدث آخر القايمة): outcomes = ['approved', ...]."""
    Item = engine._models(db)[0]
    base = base or datetime.datetime.utcnow() + datetime.timedelta(minutes=1)     # بعد لحظة تغيير المستوى (اختيارك بيصفّر العدّ)
    for i, st in enumerate(outcomes):
        _SEQ[0] += 1
        at = base + datetime.timedelta(minutes=i)
        db.session.add(Item(id='%032x' % _SEQ[0], producer=pid, section='content', kind='note', target_ref='t:%d' % _SEQ[0], target_label='ملاحظة %d' % _SEQ[0],
                            input_hash='h%d' % _SEQ[0], facts_json='{}', meta_json='{}', body_json=json.dumps({'text': 'نص'}), status=st, source='ai', mode='ask',
                            created_at=at, decided_at=at, decided_by=ACTOR))
    db.session.commit()


# ═══════════════════════════════════════════════════════ ١) الجدول والحارس

def test_every_listed_producer_has_a_work_type_row():
    """كل منتج مسجّل ظاهر له صف في الجدول الوحيد (مش الشبكة التلقائية) — فنوع جديد ما يعدّيش من غير ما يتقرّر قفله."""
    listed = {p.id for p in registry.PRODUCERS if p.listed}
    covered = {w.producer for w in levels.WORK_TYPES if w.producer}
    assert listed <= covered, listed - covered
    assert 'application_review' in covered


MONEY_PUBLISH = ['payout', 'manual_payment', 'refund', 'book_offer_price', 'course_review', 'course_lesson_draft', 'book_publish', 'topic_publish',
                 'creative_publish', 'article_publish', 'reply_draft', 'file_review', 'application_decide', 'identity_verify', 'invite_approve',
                 'ask_correction', 'library_contribution', 'training_item', 'ask_topic', 'site_review', 'market_match']


@pytest.mark.parametrize('wt', MONEY_PUBLISH)
def test_money_publish_message_types_can_never_be_alone(wt):
    w = levels.get_type(wt)
    assert w is not None and levels.lock_of(w), wt
    ok, status, msg = levels.check_level(w, 'alone')
    assert (ok, status) == (False, 409) and levels.LOCK_TEXT in msg
    assert not levels.eligible(w) and 'alone' not in w.levels


def test_the_hard_rule_is_enforced_by_the_server_for_every_locked_type(fx):
    for w in levels.catalog():
        if not levels.lock_of(w):
            continue
        before = level(w)
        r = put_level(fx, w.id, 'alone')
        assert r.status_code == 409, w.id
        body = r.get_json()
        assert levels.LOCK_TEXT in body['error'] and body['locked'] is True and body['lock_text'] == levels.LOCK_TEXT
        assert level(w) == before and levels.stored(db, w.id) is None
    assert audits('brain.level') == []


def test_non_reversible_types_are_refused_for_alone(fx, monkeypatch):
    nr = levels._wt('weird_thing', 'notes', 'شغل بلا رجوع', reversible=False, levels=levels.LEVELS)
    monkeypatch.setitem(levels.BY_ID, 'weird_thing', nr)
    assert not levels.lock_of(nr) and not levels.eligible(nr)
    ok, status, msg = levels.check_level(nr, 'alone')
    assert (ok, status) == (False, 409) and 'ما بيتعكسش' in msg
    r = put_level(fx, 'weird_thing', 'alone')
    assert r.status_code == 409 and 'ما بيتعكسش' in r.get_json()['error']
    assert levels.stored(db, 'weird_thing') is None and audits('brain.level') == []
    assert put_level(fx, 'weird_thing', 'suggest').status_code == 200      # باقي المستويات تمشي عادي


def test_name_safety_net_locks_a_forgotten_money_or_publish_type(monkeypatch):
    for name in ('refund_x', 'price_change', 'publish_thing', 'send_digest', 'payout_batch'):
        w = levels._wt(name, 'notes', 'نسيناه', reversible=True, levels=levels.LEVELS)
        assert levels.lock_of(w), name
        assert levels.check_level(w, 'alone')[:2] == (False, 409) and not levels.eligible(w)


def test_unlisted_producer_gets_a_safe_automatic_row(monkeypatch):
    use(monkeypatch, fp(pid='brand_new', kind='draft', alone=False), fp(pid='brand_note', kind='note', alone=True))
    cat = {w.id: w for w in levels.catalog()}
    assert levels.lock_of(cat['brand_new']) and not cat['brand_new'].reversible
    assert not levels.lock_of(cat['brand_note']) and cat['brand_note'].reversible


def test_defaults_stay_as_today_the_registry_default_mode():
    for p in registry.PRODUCERS:
        w = levels.BY_ID.get(p.id)
        if not (p.listed and w):
            continue
        assert w.default == levels.MODE_TO_LEVEL[p.default_mode], p.id
        assert levels.LEVEL_TO_MODE[w.default] == p.default_mode, p.id


def test_the_work_types_table_eligibility_and_reversibility():
    """الجدول المسلَّم في تقرير م٣: المؤهَّل (مش مقفول + بيتعكس + لوحده ويقترح متاحين) بالظبط."""
    expect = {'application_review', 'visitor_open', 'file_assign', 'comment_reject_abusive', 'seo_notes', 'campaign_comment', 'weekly_read',
              'forecast_comment', 'links_digest'}
    assert {w.id for w in levels.WORK_TYPES if levels.eligible(w)} == expect
    for w in levels.WORK_TYPES:
        if w.lock:
            assert not w.reversible, w.id        # المقفول مش «بيتعكس»: وكده حتى لو القفل اتشال غلط الرجوع بيمنعه
    assert levels.get_type('opinion').levels == ('alone', 'ask')


# ═══════════════════════════════════════════════════════ ٢) المسارات

LEVELS_URL = '/api/v2/brain/levels'
NON_ADMIN = ['employee', 'trainer', 'investor', 'viewer', 'pending']


@pytest.mark.parametrize('method,path,body', [
    ('GET', LEVELS_URL, None), ('PUT', LEVELS_URL + '/visitor_open', {'level': 'suggest'}),
    ('POST', '/api/v2/brain/learn', {'work_type': 'visitor_open', 'outcome': 'approved'}), ('GET', '/api/v2/brain/learn', None),
    ('POST', '/api/v2/brain/learn/visitor_open/answer', {'answer': 'no'}), ('GET', '/api/v2/brain/alone-log', None),
    ('POST', '/api/v2/brain/alone-log/%s/undo' % ('a' * 32), {}), ('GET', '/api/v2/brain/reviews', None)])
def test_admin_only_and_flag_closed(fx, monkeypatch, method, path, body):
    for role in NON_ADMIN:
        assert fx.api.call(method, path, body, role=role).status_code == 403, (role, path)
    assert fx.api.anon(method, path, body).status_code in (401, 403)
    ok = fx.api.call(method, path, body)
    assert ok.status_code in (200, 404, 409) and ok.headers.get('Cache-Control') == 'no-store'
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    r = fx.api.call(method, path, body)
    assert r.status_code == 404 and r.headers.get('Cache-Control') == 'no-store'
    assert fx.plat.calls == [], 'مفيش نداء للمنصة من مسارات المستويات'


def test_get_levels_shape(fx):
    r = fx.api.get(LEVELS_URL)
    assert r.status_code == 200
    d = r.get_json()
    by = {t['id']: t for t in d['types']}
    assert len(by) >= 30 and d['streak_needed'] == 8
    assert [g['key'] for g in d['groups']] == ['people', 'files', 'content', 'notes', 'locked']
    assert by['payout']['locked'] is True and by['payout']['lock_text'] == 'دايمًا بموافقتك' and by['payout']['level'] == 'suggest'
    assert by['visitor_open']['eligible'] is True and by['visitor_open']['reversible'] is True and by['visitor_open']['level'] == 'suggest'
    assert by['visitor_open']['levels'] == ['alone', 'suggest', 'ask']
    assert by['seo_notes']['level'] == 'alone' and by['opinion']['levels'] == ['alone', 'ask']
    assert by['file_assign']['external'] == 'auto_assign' and by['file_assign']['levels'] == ['alone', 'suggest']
    for t in d['types']:
        assert set(t) >= {'id', 'group', 'title', 'level', 'default', 'locked', 'reversible', 'eligible', 'levels', 'stats', 'learn'}
        assert t['group'] in {g['key'] for g in d['groups']}
    assert 'facts' not in json.dumps(d) and 'meta' not in json.dumps(d)


def test_put_level_happy_path_is_audited_and_resets_nothing_else(fx):
    r = put_level(fx, 'visitor_open', 'alone')
    assert r.status_code == 200 and r.get_json()['level'] == 'alone' and r.get_json()['updated_by']
    assert level('visitor_open') == 'alone'
    a = audits('brain.level', 'visitor_open')
    assert len(a) == 1 and json.loads(a[0].meta_json) == {'from': 'suggest', 'to': 'alone'}
    row = [t for t in fx.api.get(LEVELS_URL).get_json()['types'] if t['id'] == 'visitor_open'][0]
    assert row['level'] == 'alone' and row['updated_by'] and row['updated_at']
    assert put_level(fx, 'visitor_open', 'ask').status_code == 200 and level('visitor_open') == 'ask'
    assert len(audits('brain.level', 'visitor_open')) == 2


def test_put_level_bad_input(fx):
    assert put_level(fx, 'visitor_open', 'maybe').status_code == 400
    assert fx.api.put(LEVELS_URL + '/visitor_open', {}).status_code == 400
    assert put_level(fx, 'no_such_type', 'alone').status_code == 404
    assert fx.api.put(LEVELS_URL + '/Bad-Name', {'level': 'ask'}).status_code == 404
    r = put_level(fx, 'opinion', 'suggest')           # الرأي مالوش «يقترح»
    assert r.status_code == 400 and levels.stored(db, 'opinion') is None


def test_put_level_for_a_producer_type_drives_the_engine_mode(fx, monkeypatch):
    p = registry.by_id('seo_notes')
    assert engine.effective_mode(NS, p) == 'alone' and level('seo_notes') == 'alone'
    assert put_level(fx, 'seo_notes', 'suggest').status_code == 200
    assert engine.effective_mode(NS, p) == 'ask'
    assert put_level(fx, 'seo_notes', 'ask').status_code == 200
    assert engine.effective_mode(NS, p) == 'off'
    assert put_level(fx, 'seo_notes', 'alone').status_code == 200
    assert engine.effective_mode(NS, p) == 'alone'
    sw = {s['id']: s for s in fx.api.get('/api/v2/brain/switches').get_json()['switches']}
    assert sw['seo_notes']['mode'] == 'alone'


def test_locked_producer_never_reaches_alone_even_through_the_old_switch_route(fx):
    for pid in ('course_review', 'reply_draft', 'file_review', 'ask_correction'):
        r = fx.api.put('/api/v2/brain/switches/' + pid, {'mode': 'alone', 'confirmed': True})
        assert r.status_code == 400, pid
        assert engine.effective_mode(NS, registry.by_id(pid)) != 'alone'
    r = put_level(fx, 'course_review', 'ask')            # «يسألك» على المقفول مسموح (بيوفّر نداءات)
    assert r.status_code == 200 and engine.effective_mode(NS, registry.by_id('course_review')) == 'off'


def test_old_switch_route_mirrors_into_levels_and_uses_the_same_guard(fx, monkeypatch):
    r = fx.api.put('/api/v2/brain/switches/seo_notes', {'mode': 'off', 'confirmed': True})
    assert r.status_code == 200 and level('seo_notes') == 'ask'
    r = fx.api.put('/api/v2/brain/switches/seo_notes', {'mode': 'ask', 'confirmed': True})
    assert r.status_code == 200 and level('seo_notes') == 'suggest'
    # نوع جديد لا يتسمحله «لوحده» لو الحارس رفضه — حتى من الطريق القديم
    monkeypatch.setitem(levels.BY_ID, 'seo_notes', levels.BY_ID['seo_notes']._replace(reversible=False))
    r = fx.api.put('/api/v2/brain/switches/seo_notes', {'mode': 'alone', 'confirmed': True})
    assert r.status_code == 409 and 'ما بيتعكسش' in r.get_json()['error']


def test_file_assign_is_the_platform_setting_and_failure_writes_nothing(fx):
    assert put_level(fx, 'file_assign', 'ask').status_code == 400          # المنصة مالهاش «يسألك» للتوزيع
    r = put_level(fx, 'file_assign', 'alone')
    assert r.status_code == 200 and level('file_assign') == 'alone'
    put_calls = [c for c in fx.plat.calls if c[0] == 'PUT']
    assert put_calls and put_calls[-1][1] == '/api/bridge/expert-files/settings' and put_calls[-1][3]['auto_assign'] is True
    assert put_calls[-1][3]['by']
    assert put_level(fx, 'file_assign', 'suggest').status_code == 200 and fx.plat.calls[-1][3]['auto_assign'] is False
    fx.plat.auto_assign_fail = True
    r = put_level(fx, 'file_assign', 'alone')
    assert r.status_code == 502 and level('file_assign') == 'suggest', 'المنصة رفضت ⇒ مفيش مستوى اتسجّل'
    assert len(audits('brain.level', 'file_assign')) == 2


# ═══════════════════════════════════════════════════════ ٣) التعلّم

def test_eight_unchanged_approvals_trigger_the_question(fx):
    report(fx, 'visitor_open', 'approved', 7)
    assert 'visitor_open' not in prompts(fx)
    report(fx, 'visitor_open', 'approved', 1)
    p = prompts(fx)['visitor_open']
    assert p['n'] == 8 and p['title'] == 'فتح المنصة لزائر عادي' and p['unit']
    row = [t for t in fx.api.get(LEVELS_URL).get_json()['types'] if t['id'] == 'visitor_open'][0]
    assert row['learn'] == {'n': 8, 'show': True} and row['stats'] == {'kind': 'approvals', 'n': 8, 'of': 8}
    report(fx, 'visitor_open', 'approved', 3)
    assert prompts(fx)['visitor_open']['n'] == 11


def test_an_edit_or_a_rejection_or_a_level_change_resets_the_streak(fx):
    report(fx, 'visitor_open', 'approved', 5)
    report(fx, 'visitor_open', 'rejected')
    report(fx, 'visitor_open', 'approved', 7)
    assert 'visitor_open' not in prompts(fx), 'رفض في النص ⇒ العدّ يبدأ بعده'
    report(fx, 'visitor_open', 'approved', 1)
    assert 'visitor_open' in prompts(fx)
    report(fx, 'visitor_open', 'edited')
    assert 'visitor_open' not in prompts(fx)
    report(fx, 'visitor_open', 'approved', 8)
    assert 'visitor_open' in prompts(fx)
    assert put_level(fx, 'visitor_open', 'ask').status_code == 200            # اختيارك بيصفّر
    assert put_level(fx, 'visitor_open', 'suggest').status_code == 200
    assert 'visitor_open' not in prompts(fx)
    # ⛔ الاختيار المحفوظ بيعدّ من لحظة التغيير (الموافقات قبله ما بتحسبش)
    report(fx, 'visitor_open', 'approved', 8)
    assert 'visitor_open' in prompts(fx)


def test_only_suggest_level_asks_and_alone_or_ask_never_prompt(fx):
    report(fx, 'visitor_open', 'approved', 8)
    assert 'visitor_open' in prompts(fx)
    put_level(fx, 'visitor_open', 'ask')
    report(fx, 'visitor_open', 'approved', 8)
    assert 'visitor_open' not in prompts(fx)
    put_level(fx, 'visitor_open', 'alone')
    report(fx, 'visitor_open', 'approved', 8)
    assert 'visitor_open' not in prompts(fx)


def test_report_validation(fx):
    assert fx.api.post('/api/v2/brain/learn', {'work_type': 'visitor_open', 'outcome': 'maybe'}).status_code == 400
    assert fx.api.post('/api/v2/brain/learn', {'work_type': 'nope_nope', 'outcome': 'approved'}).status_code == 404
    r = fx.api.post('/api/v2/brain/learn', {'work_type': 'seo_notes', 'outcome': 'approved'})
    assert r.status_code == 400, 'المنتجات بتتعلّم من صفوفها مش من الواجهة'


def test_producer_types_learn_from_their_real_item_decisions(fx):
    put_level(fx, 'seo_notes', 'suggest')
    seed_items('seo_notes', ['approved'] * 8)
    p = prompts(fx)['seo_notes']
    assert p['n'] == 8
    seed_items('seo_notes', ['edited'], base=datetime.datetime.utcnow() + datetime.timedelta(minutes=20))
    assert 'seo_notes' not in prompts(fx), 'تعديل واحد أحدث ⇒ العدّ صفر'
    seed_items('seo_notes', ['approved'] * 7, base=datetime.datetime.utcnow() + datetime.timedelta(minutes=30))
    assert 'seo_notes' not in prompts(fx)
    seed_items('seo_notes', ['approved'], base=datetime.datetime.utcnow() + datetime.timedelta(minutes=60))
    assert prompts(fx)['seo_notes']['n'] == 8


def test_locked_types_never_ask_even_with_a_perfect_streak(fx):
    report(fx, 'payout', 'approved', 12)
    assert 'payout' not in prompts(fx)
    assert levels.learn_state(NS, levels.get_type('payout')) == {'n': 0, 'show': False}
    r = fx.api.post('/api/v2/brain/learn/payout/answer', {'answer': 'yes'})
    assert r.status_code == 409 and level('payout') == 'suggest'
    seed_items('course_review', ['approved'] * 10)
    assert 'course_review' not in prompts(fx)


def test_answer_yes_sets_alone_with_the_same_guard_and_audit(fx):
    assert fx.api.post('/api/v2/brain/learn/visitor_open/answer', {'answer': 'yes'}).status_code == 409, 'السؤال مش مستحق'
    report(fx, 'visitor_open', 'approved', 8)
    r = fx.api.post('/api/v2/brain/learn/visitor_open/answer', {'answer': 'yes'})
    assert r.status_code == 200 and level('visitor_open') == 'alone'
    assert len(audits('brain.learn_yes', 'visitor_open')) == 1 and len(audits('brain.level', 'visitor_open')) == 1
    assert 'visitor_open' not in prompts(fx)
    assert fx.api.post('/api/v2/brain/learn/visitor_open/answer', {'answer': 'maybe'}).status_code == 400


def test_answer_no_suppresses_the_question_for_thirty_days(fx):
    report(fx, 'visitor_open', 'approved', 8)
    r = fx.api.post('/api/v2/brain/learn/visitor_open/answer', {'answer': 'no'})
    assert r.status_code == 200 and level('visitor_open') == 'suggest'
    until = levels._parse(r.get_json()['until'])
    assert abs((until - datetime.datetime.utcnow()).total_seconds() - 30 * 86400) < 120
    assert 'visitor_open' not in prompts(fx)
    report(fx, 'visitor_open', 'approved', 5)
    assert 'visitor_open' not in prompts(fx)
    row = [t for t in fx.api.get(LEVELS_URL).get_json()['types'] if t['id'] == 'visitor_open'][0]
    assert row['learn']['show'] is False, 'الإيحاء «تخليها لوحده؟» كمان بيسكت'
    assert len(audits('brain.learn_no', 'visitor_open')) == 1
    # ٢٩ يوم: لسه ساكت · بعد الـ٣٠: يرجع يسأل
    db.session.execute(text("UPDATE brain_learn_ask SET until = :u WHERE work_type = 'visitor_open'"),
                       {'u': (datetime.datetime.utcnow() + datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')})
    db.session.commit()
    assert 'visitor_open' not in prompts(fx)
    db.session.execute(text("UPDATE brain_learn_ask SET until = :u WHERE work_type = 'visitor_open'"),
                       {'u': (datetime.datetime.utcnow() - datetime.timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M:%SZ')})
    db.session.commit()
    assert 'visitor_open' in prompts(fx)


# ═══════════════════════════════════════════════════════ ٤) «عمل لوحده» و«رجّعها»

def make_alone(x, wt):
    assert put_level(x, wt, 'alone').status_code == 200


def test_nothing_runs_unless_the_level_is_alone(fx):
    fx.plat.users = [visitor('1')]
    fx.plat.opinions = [opinion('o1')]
    assert level('visitor_open') == 'suggest' and level('comment_reject_abusive') == 'suggest'
    assert alone.run_pending(NS) == {}
    assert fx.plat.calls == [], 'مستوى «يقترح» ⇒ ولا نداء للمنصة أصلًا'
    put_level(fx, 'visitor_open', 'ask')
    assert alone.run_pending(NS) == {} and fx.plat.calls == []


def test_visitor_open_alone_opens_only_the_normal_ones_and_logs_each(fx):
    make_alone(fx, 'visitor_open')
    fx.plat.users = [visitor('1'), visitor('2', flags=['حساب مكرر']), visitor('3', status='none'), visitor('4', email=''), visitor('5', name='نادية')]
    assert alone.run_pending(NS, actor='العقل') == {'visitor_open': 2}
    posts = [c for c in fx.plat.calls if c[0] == 'POST']
    assert [c[1] for c in posts] == ['/api/bridge/users/1/access', '/api/bridge/users/5/access']
    assert all(c[3] == {'access': 'member'} for c in posts)
    log = {r['target_ref']: r for r in levels.alone_rows(NS)}
    assert set(log) == {'pu:1', 'pu:5'} and log['pu:5']['what'] == 'فتح المنصة لـنادية' and log['pu:5']['can_undo'] is True
    assert [json.loads(a.meta_json)['access'] for a in audits('pending_user.access')] == ['member', 'member']
    assert {a.actor_email for a in audits('pending_user.access')} == {'العقل'}, 'نفس دالة اللوحة ونفس التدقيق، والفاعل العقل'


def test_visitor_open_alone_is_capped_and_never_runs_blind(fx, monkeypatch):
    make_alone(fx, 'visitor_open')
    fx.plat.users = [visitor(str(i)) for i in range(1, 9)]
    assert alone.run_pending(NS) == {'visitor_open': alone.PER_TICK}
    assert len([c for c in fx.plat.calls if c[0] == 'POST']) == alone.PER_TICK
    fx.plat.calls[:] = []
    fx.plat.down.add('/api/bridge/pending-users')            # المصدر ما وصلش ⇒ ولا فعل على الأعمى
    assert alone.run_pending(NS) == {} and [c for c in fx.plat.calls if c[0] == 'POST'] == []
    fx.plat.down.clear()
    monkeypatch.setenv('DASH_BRAIN_WRITE', '0')              # مفتاح الطوارئ
    fx.plat.calls[:] = []
    assert alone.run_pending(NS) == {} and fx.plat.calls == []


def test_platform_refusal_logs_nothing(fx):
    make_alone(fx, 'visitor_open')
    fx.plat.users = [visitor('1')]
    fx.plat.access_fail = True
    assert alone.run_pending(NS) == {} and levels.alone_rows(NS) == []


def test_abusive_comments_alone_and_undo(fx):
    make_alone(fx, 'comment_reject_abusive')
    fx.plat.opinions = [opinion('o1'), opinion('o2', abusive=False), opinion('o3', checked=False), opinion('o4', status='approved'), opinion('o5', topic='نفقة')]
    assert alone.run_pending(NS) == {'comment_reject_abusive': 2}
    assert [c[1] for c in fx.plat.calls if c[0] == 'POST'] == ['/api/bridge/opinions/o1/reject', '/api/bridge/opinions/o5/reject']
    row = [r for r in levels.alone_rows(NS) if r['target_ref'] == 'op:o5'][0]
    assert row['what'] == 'إخفاء تعليق مسيء على «نفقة»'
    status, payload = levels.undo(NS, row['id'], ACTOR)
    assert status == 200 and fx.plat.calls[-1][1] == '/api/bridge/opinions/o5/approve' and payload['line'] == alone.MSG_COMMENT_UNDO


def test_undo_runs_once_logs_it_and_second_time_says_so(fx):
    make_alone(fx, 'visitor_open')
    fx.plat.users = [visitor('7', name='سلمى')]
    alone.run_pending(NS)
    row = levels.alone_rows(NS)[0]
    status, payload = levels.undo(NS, row['id'], ACTOR)
    assert status == 200 and payload['line'] == alone.MSG_VISITOR_UNDO
    last = fx.plat.calls[-1]
    assert last[1] == '/api/bridge/users/7/access' and last[3]['access'] == 'pending'
    again = levels.alone_rows(NS)[0]
    assert again['undone'] is True and again['can_undo'] is False and again['undone_by'] == ACTOR and again['undo_note'] == alone.MSG_VISITOR_UNDO
    assert len(audits('brain.alone_undo', row['id'])) == 1
    n = len(fx.plat.calls)
    status, payload = levels.undo(NS, row['id'], ACTOR)
    assert status == 409 and payload['error'] == 'اترجّعت قبل كده' and len(fx.plat.calls) == n, 'ما نبعتش للمنصة تاني'


def test_an_undo_that_is_impossible_now_says_so_plainly(fx):
    make_alone(fx, 'visitor_open')
    fx.plat.users = [visitor('8')]
    alone.run_pending(NS)
    row = levels.alone_rows(NS)[0]
    fx.plat.access_fail = True
    status, payload = levels.undo(NS, row['id'], ACTOR)
    assert status == 409 and payload['can_undo'] is False
    assert payload['error'].startswith('مقدرناش نرجّعها دلوقتي') and 'المنصة رفضت' in payload['error']
    again = levels.alone_rows(NS)[0]
    assert again['undone'] is False and audits('brain.alone_undo') == []
    fx.plat.access_fail = False
    assert levels.undo(NS, row['id'], ACTOR)[0] == 200, 'ولما المنصة ترجع بتتعمل'
    # صف من غير بيانات رجوع ⇒ مينفعش
    lid = levels.log_alone(NS, 'visitor_open', 'فعل قديم', undo=None)
    status, payload = levels.undo(NS, lid, ACTOR)
    assert status == 409 and payload['error'] == 'مينفعش ترجّعها دلوقتي'
    assert levels.undo(NS, 'f' * 32, ACTOR)[0] == 404


def test_notes_written_alone_are_logged_with_a_discard_undo(fx, monkeypatch):
    use(monkeypatch, fp(pid='seo_notes', kind='note', alone=True, targets=[('a:1', F1)]),
        fp(pid='opinion', kind='opinion', section='home', targets=[]))
    run()
    items = rows(producer='seo_notes')
    assert [i.status for i in items] == ['done_alone']
    log = levels.alone_rows(NS)
    assert len(log) == 1 and log[0]['work_type'] == 'seo_notes' and log[0]['target_ref'] == items[0].id and log[0]['can_undo']
    assert 'ملاحظة' in log[0]['what'] or 'وسم' in log[0]['what']
    status, payload = levels.undo(NS, log[0]['id'], ACTOR)
    assert status == 200 and payload['line'] == alone.MSG_NOTE_UNDO
    assert rows(producer='seo_notes')[0].status == 'discarded'
    assert levels.undo(NS, log[0]['id'], ACTOR)[0] == 409
    # الملاحظة اتحسمت قبل «رجّعها» ⇒ جملة صريحة مش «تم» كاذبة
    lid = levels.log_alone(NS, 'seo_notes', 'ملاحظة', undo={'kind': 'discard_item', 'item_id': items[0].id})
    status, payload = levels.undo(NS, lid, ACTOR)
    assert status == 409 and payload['error'] == alone.ERR_NOTE_GONE


def test_opinions_are_not_logged_one_by_one_and_proposals_are_not_alone_actions(fx, monkeypatch):
    use(monkeypatch, fp(pid='opinion', kind='opinion', section='home', targets=[('c:1', F1)]),
        fp(pid='seo_notes', kind='note', alone=True, default_mode='ask', targets=[('a:1', F2)]))
    run()
    assert [r.status for r in rows(producer='seo_notes')] == ['proposed']
    assert levels.alone_rows(NS) == [], 'اقتراح ينتظر موافقتك مش «عمل لوحده»'


def test_alone_log_routes(fx):
    make_alone(fx, 'visitor_open')
    fx.plat.users = [visitor('1'), visitor('2')]
    alone.run_pending(NS)
    old = levels.log_alone(NS, 'seo_notes', 'قديمة', undo=None, at=datetime.datetime.utcnow() - datetime.timedelta(days=5))
    today = fx.api.get('/api/v2/brain/alone-log?day=today').get_json()['rows']
    assert len(today) == 2 and today[0]['at'] >= today[1]['at'] and old not in [r['id'] for r in today]
    allr = fx.api.get('/api/v2/brain/alone-log?day=all').get_json()['rows']
    assert {r['id'] for r in allr} >= {old} and len(allr) == 3
    r = fx.api.post('/api/v2/brain/alone-log/%s/undo' % today[0]['id'], {})
    assert r.status_code == 200 and r.get_json()['ok'] is True
    assert fx.api.post('/api/v2/brain/alone-log/nothex/undo', {}).status_code == 400
    assert fx.api.post('/api/v2/brain/alone-log/%s/undo' % ('e' * 32), {}).status_code == 404
    assert fx.api.post('/api/v2/brain/alone-log/%s/undo' % today[0]['id'], {}).status_code == 409


def test_the_autorun_tick_runs_the_alone_actions_without_any_ai(fx, monkeypatch):
    calls = []
    monkeypatch.setattr(alone, 'run_pending', lambda ns, actor='العقل': calls.append(actor) or {})

    def boom(*a, **k):
        raise AssertionError('نداء ذكاء ممنوع في فحص «عمل لوحده»')
    monkeypatch.setattr(appmod, 'ai_call', boom)
    now = datetime.datetime(2098, 3, 10, 18, 30)
    monkeypatch.setattr(engine, 'utcnow', lambda: now)
    autorun.tick(NS, now)
    assert calls == ['العقل']
    monkeypatch.setenv('DASH_BRAIN_AUTORUN', '0')
    calls[:] = []
    autorun.tick(NS, now)
    assert calls == [], 'المشغّل متوقّف ⇒ ولا فحص'


# ═══════════════════════════════════════════════════════ ٥) مراجعة طلبات الانضمام و«راجعت…»

REVIEW_AI = {'text': 'الورق كامل تقريبًا، افتح الطلب قبل القرار', 'recommend': 'approve', 'why': 'السيرة والفيديو وصلا',
             'points': [{'ok': True, 'text': 'السيرة وصلت'}, {'ok': True, 'text': 'الفيديو وصل'}]}


def review_env(fx, monkeypatch, reply=None, apps=None, ids=True):
    fx.plat.apps = apps if apps is not None else [application('11')]
    if ids:
        fx.plat.idocs = [{'email': 'mona11@x.test', 'status': 'pending'}]
    use(monkeypatch, *producers_apply.PRODUCERS)
    fx.env.default = reply if reply is not None else dict(REVIEW_AI)
    return fx


def test_application_review_facts_carry_no_name_or_email(fx, monkeypatch):
    review_env(fx, monkeypatch)
    ts = producers_apply.gather(Ctx(ns=NS, now=datetime.datetime.utcnow(), actor='x'))
    assert len(ts) == 1 and ts[0].ref == 'trainer:11' and ts[0].meta == {'application_id': '11'}
    f = ts[0].facts
    assert f == {'role': 'خبير ومدرّب', 'headline': 'محامية بالنقض', 'specialty': 'عقود', 'years': '12', 'cv_files': 1, 'video': 'وصل',
                 'identity_doc': 'وثيقة محفوظة بانتظار المراجعة'}
    blob = json.dumps(f, ensure_ascii=False)
    assert 'منى' not in blob and '@' not in blob and 'mona' not in blob


def test_application_review_licence_and_identity_only_when_the_source_says_so(fx, monkeypatch):
    review_env(fx, monkeypatch, apps=[application('12', bar_number='', intro_video_url=''), application('13', bar_number='123'),
                                      application('14', status='approved'), application('bad id')], ids=False)
    fx.plat.down.add('/api/bridge/identity-docs')
    by = {t.ref: t.facts for t in producers_apply.gather(Ctx(ns=NS, now=None, actor='x'))}
    assert set(by) == {'trainer:12', 'trainer:13'}
    assert by['trainer:12']['licence_number'] == 'غير مكتوب' and by['trainer:12']['video'] == 'لم يصل بعد'
    assert by['trainer:13']['licence_number'] == 'مكتوب'
    assert all('identity_doc' not in f for f in by.values()), 'مصدر الهوية ما وصلش ⇒ ما نقولش «لا توجد وثيقة»'
    assert 'licence_number' not in producers_apply._facts_of(application('15'), None)


def test_application_review_source_down_is_reported_not_swallowed(fx, monkeypatch):
    review_env(fx, monkeypatch)
    fx.plat.down.add('/api/bridge/trainer-applications')
    with pytest.raises(SourceDown):
        producers_apply.gather(Ctx(ns=NS, now=None, actor='x'))


def test_application_review_runs_through_the_engine_prompt_only(fx, monkeypatch):
    review_env(fx, monkeypatch)
    run(only=['application_review'])
    assert len(fx.env.calls) == 1, 'نداء واحد لطلب واحد'
    sysmsg, usermsg = fx.env.calls[0]['system'], fx.env.calls[0]['user']
    assert 'ما شفتش السيرة' in sysmsg and 'منى' not in usermsg and '@' not in usermsg
    r = rows(producer='application_review')
    assert len(r) == 1 and r[0].status == 'done_alone' and r[0].target_ref == 'trainer:11'
    body = json.loads(r[0].body_json)
    assert body['points'] == REVIEW_AI['points'] and body['recommend'] == 'approve' and body['why'] == 'السيرة والفيديو وصلا'
    assert json.loads(r[0].meta_json) == {'application_id': '11'}
    assert len(levels.alone_rows(NS)) == 1, 'المراجعة اللي كتبها لوحده اتسجّلت برجوع'


def test_approve_with_a_missing_point_is_downgraded_to_open(fx, monkeypatch):
    reply = dict(REVIEW_AI, points=[{'ok': True, 'text': 'السيرة وصلت'}, {'ok': False, 'text': 'الفيديو لسه ما وصلش'}])
    review_env(fx, monkeypatch, reply=reply)
    run(only=['application_review'])
    assert json.loads(rows(producer='application_review')[0].body_json)['recommend'] == 'open'


@pytest.mark.parametrize('reply', [
    dict(REVIEW_AI, points=[{'ok': True, 'text': 'السيرة تغطي ٩٩ قضية'}, {'ok': True, 'text': 'الفيديو وصل'}]),       # رقم مش في الحقائق
    dict(REVIEW_AI, points=[{'ok': True, 'text': 'السيرة وصلت'}]),                                                        # نقطة واحدة
    dict(REVIEW_AI, points=[{'ok': 'yes', 'text': 'السيرة وصلت'}, {'ok': True, 'text': 'x'}]),
    dict(REVIEW_AI, recommend='maybe'), dict(REVIEW_AI, text='x' * 300), dict(REVIEW_AI, why='x' * 200),
    dict(REVIEW_AI, text='مراجعة sara@example.com'),
])
def test_a_dishonest_or_malformed_review_falls_back_to_the_facts_template(fx, monkeypatch, reply):
    review_env(fx, monkeypatch, reply=reply)
    run(only=['application_review'])
    r = rows(producer='application_review')
    assert len(r) == 1 and r[0].source == 'template' and r[0].status == 'done_alone'
    b = json.loads(r[0].body_json)
    assert [p['ok'] for p in b['points']] == [True, True, False] and b['recommend'] == 'open'
    assert b['points'][-1]['text'] == 'وثيقة الهوية محفوظة وبتستنى مراجعتك' and 'من حقائق الطلب بس' in b['why']


def test_model_failure_gives_the_template_and_respects_the_per_run_cap(fx, monkeypatch):
    review_env(fx, monkeypatch, apps=[application(str(i)) for i in range(20, 27)], ids=False)
    fx.env.default = RuntimeError('boom')
    run(only=['application_review'])
    r = rows(producer='application_review')
    assert len(fx.env.calls) == 3 and len(r) == 3 and {x.source for x in r} == {'template'}, 'سقف الجولة للمنتج ٣، والفاشل قالب من الحقائق'


def test_review_cap_and_run_cap_apply(fx, monkeypatch):
    review_env(fx, monkeypatch, apps=[application(str(i)) for i in range(30, 38)], ids=False)
    run(only=['application_review'])
    assert len(fx.env.calls) == 3 == len(rows(producer='application_review')), 'سقف المنتج ٣ نداءات في الجولة'
    monkeypatch.setenv('DASH_BRAIN_RUN_CAP', '1')
    run(only=['application_review'])
    assert len(fx.env.calls) == 4, 'سقف الجولة مطبَّق برضه'


def test_reviews_route_is_a_white_list_keyed_by_the_card_ref(fx, monkeypatch):
    review_env(fx, monkeypatch, apps=[application('41'), application('42')])
    run(only=['application_review'])
    d = fx.api.get('/api/v2/brain/reviews').get_json()['reviews']
    assert set(d) == {'trainer:41', 'trainer:42'}
    one = d['trainer:41']
    assert set(one) == {'producer', 'text', 'why', 'recommend', 'points', 'source', 'created_at'} and one['producer'] == 'application_review'
    assert '@' not in json.dumps(d) and 'منى' not in json.dumps(d, ensure_ascii=False)


def test_engine_points_honesty_and_shape():
    facts = {'years': '12'}
    ok = {'text': 'جيد', 'points': [{'ok': True, 'text': 'خبرة ١٢ سنة'}]}
    assert engine.check_body(ok, facts, 'note') is None
    assert engine.check_body({'text': 'جيد', 'points': [{'ok': True, 'text': 'خبرة ٩٩ سنة'}]}, facts, 'note') == 'number'
    assert engine.check_body({'text': 'جيد', 'points': [{'ok': True, 'text': 'Python expert'}]}, facts, 'note') == 'latin'
    assert engine.check_body({'text': 'جيد', 'points': 'x'}, facts, 'note') == 'points'
    assert engine.check_body({'text': 'جيد', 'points': [{'ok': 1, 'text': 'x'}]}, facts, 'note') == 'points'
    assert engine.check_body({'text': 'جيد', 'points': [{'ok': True, 'text': 'x' * 121}]}, facts, 'note') == 'points'
    assert engine.check_body({'text': 'جيد', 'points': [{'ok': True, 'text': 'ن'}] * 6}, facts, 'note') == 'points'
    assert engine.check_body({'text': 'جيد'}, facts, 'note') is None
    assert engine.safe_points([{'ok': True, 'text': 'ن'}], facts) == [{'ok': True, 'text': 'ن'}]
    assert engine.safe_points([{'ok': True, 'text': 'عدد ٧٧'}], facts) is None and engine.safe_points('x', facts) is None


def test_file_review_and_ask_correction_keep_honest_points_and_drop_bad_ones():
    from brain2 import producers_files, producers_ask
    t = Target(ref='file:f1', label='x', facts={'title': 'ملف', 'questions': ['س'], 'facts': [], 'pending_opinion': {'answers': ['ج']}}, meta={'file_id': 'f1'})
    good = {'text': 'راجعته', 'recommend': 'approve', 'points': [{'ok': True, 'text': 'كل سؤال اتجاوب'}, {'ok': False, 'text': 'تنقص خطوة تالية'}]}
    assert producers_files.validate(good, t)['points'] == good['points']
    assert 'points' not in producers_files.validate(dict(good, points=[{'ok': True, 'text': 'عدد ٥٥٥'}]), t), 'نقطة غير صادقة ⇒ تتشال والمراجعة تفضل'
    assert 'points' not in producers_files.validate({'text': 'راجعته', 'recommend': 'approve'}, t)
    t2 = Target(ref='askfb:a1', label='x', facts={'track': 'x', 'question': 'س', 'wrong_answer': 'ج', 'correction': 'التصحيح المكتوب هنا طويل', 'articles': [{'ref': '[م]', 'text': 'نص'}]},
                meta={'feedback_id': 'a1', 'track': 'x'})
    raw = {'text': 'ملاحظة الخبير', 'verdict': 'no_text', 'why': 'x', 'article_refs': [], 'points': [{'ok': True, 'text': 'التصحيح واضح'}]}
    assert producers_ask.validate(raw, t2)['points'] == [{'ok': True, 'text': 'التصحيح واضح'}]
    assert 'points' not in producers_ask.validate(dict(raw, points='bad'), t2)


# ═══════════════════════════════════════════════════════ ٦) الواجهة (node)

def ui(payload):
    proc = subprocess.run([v2_node.NODE, os.path.join(_HERE, 'uiharness', 'r24p3_ui.js')], input=json.dumps(payload, ensure_ascii=False),
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, proc.stderr[-1500:]
    return json.loads(proc.stdout)


def text_of(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html or '')).strip()


def T(id, group, title, level, **kw):
    t = {'id': id, 'group': group, 'title': title, 'hint': kw.pop('hint', ''), 'level': level, 'default': level, 'locked': False, 'lock': '', 'lock_text': '',
         'reversible': True, 'eligible': True, 'levels': ['alone', 'suggest', 'ask'], 'external': '', 'unit': ['طلبات', 'طلبًا'],
         'stats': {'kind': 'none'}, 'learn': {'n': 0, 'show': False}, 'updated_at': None, 'updated_by': None}
    t.update(kw)
    return t


LEVELS_RESP = {'streak_needed': 8, 'groups': [{'key': 'people', 'title': 'الناس'}, {'key': 'content', 'title': 'المحتوى'}, {'key': 'locked', 'title': 'الفلوس والنشر للناس'}], 'types': [
    T('application_review', 'people', 'مراجعة طلب انضمام خبير أو مدرّب', 'suggest', hint='السيرة، والفيديو، ورقم القيد، والهوية', stats={'kind': 'approvals', 'n': 8, 'of': 8},
      learn={'n': 8, 'show': True}),
    T('visitor_open', 'people', 'فتح المنصة لزائر عادي', 'alone', hint='إيميل عادي من غير علامة اشتباه', stats={'kind': 'times', 'n': 23}),
    T('comment_reject_abusive', 'content', 'إخفاء تعليق مسيء بوضوح', 'suggest', stats={'kind': 'approvals', 'n': 5, 'of': 6}),
    T('seo_notes', 'content', 'ملاحظات الظهور في البحث', 'ask', stats={'kind': 'none'}),
    T('payout', 'locked', 'تحويل أرباح خبير أو مدرّب', 'suggest', locked=True, lock='money', lock_text='دايمًا بموافقتك', reversible=False, eligible=False,
      levels=['suggest', 'ask'], stats={'kind': 'locked'}),
    T('course_review', 'locked', 'نشر دورة جديدة', 'suggest', locked=True, lock='publish', lock_text='دايمًا بموافقتك', reversible=False, eligible=False,
      levels=['suggest', 'ask'], stats={'kind': 'locked'}),
]}


@needs_node
def test_levels_table_renders_grouped_with_locked_rows_and_the_hint():
    o = ui({'mode': 'tab', 'api': {'GET /v2/brain/levels': LEVELS_RESP}})
    h, t = o['html'], text_of(o['html'])
    assert 'العقل وقواعده' in t and 'اللي عمله لوحده' in t
    assert 'كل شغل ليه واحدة من تلاتة' in t and 'الفلوس والنشر للناس دايمًا بموافقتك' in t
    for lab in ('لوحده', 'يقترح وانت توافق', 'يسألك'):
        assert lab in t
    th = lambda name: h.index('<th colspan="4">' + name)
    assert th('الناس') < th('المحتوى') < th('الفلوس والنشر للناس')
    assert 'وافقت ٨ من ٨' in t and '٢٣ مرة' in t and 'وافقت ٥ من ٦' in t and 'لسه ما حصلش حاجة' in t
    # صف المراجعة (يقترح + ٨ من ٨) عليه «تخليها لوحده؟» والتاني لأ
    assert h.count('تخليها لوحده؟') == 1 and re.search(r'data-lv="hint" data-wt="application_review"', h)
    # المقفول: الاختيار كله disabled و«دايمًا بموافقتك» مكان الإحصاء
    row = re.search(r'<tr class="v2lv-row locked" data-wt="payout">.*?</tr>', h, re.S).group(0)
    assert row.count('disabled') == 3 and 'دايمًا بموافقتك' in row and 'aria-checked="true"' in row and 'يقترح وانت توافق' in row
    assert 'class="suggest on"' in row
    # غير المقفول: الاختيار الحالي بس عليه on، والكل شغّال
    vrow = re.search(r'<tr class="v2lv-row" data-wt="visitor_open">.*?</tr>', h, re.S).group(0)
    assert 'class="alone on"' in vrow and 'disabled' not in vrow
    assert '<tr class="v2lv-grp">' in h or 'class="v2lv-grp"' in h


@needs_node
def test_levels_table_failure_is_announced_not_empty():
    o = ui({'mode': 'tab', 'api': {}})
    t = text_of(o['html'])
    assert 'ما وصلتش البيانات' in t and 'حاول تاني' in t and 'v2lv-row' not in o['html']


@needs_node
def test_changing_a_level_calls_the_server_and_alone_needs_a_confirmation_sheet():
    api_ = {'GET /v2/brain/levels': LEVELS_RESP, 'PUT /v2/brain/levels/comment_reject_abusive': {'ok': True}, 'PUT /v2/brain/levels/seo_notes': {'ok': True}}
    o = ui({'mode': 'tab', 'api': api_, 'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'set', 'data-wt': 'comment_reject_abusive', 'data-level': 'ask'}}]})
    puts = [c for c in o['calls'] if c.get('m') == 'PUT']
    assert puts == [{'fn': 'api', 'm': 'PUT', 'path': '/v2/brain/levels/comment_reject_abusive', 'body': {'level': 'ask'}}]
    assert o['modals'] == [], '«يسألك» من غير ورقة'
    assert 'اتغيّر: «إخفاء تعليق مسيء بوضوح» بقى «يسألك»' in text_of(o['html'])
    o = ui({'mode': 'tab', 'api': api_, 'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'set', 'data-wt': 'seo_notes', 'data-level': 'alone'}}]})
    assert [c for c in o['calls'] if c.get('m') == 'PUT'] == [] and o['modals'] == ['تشغّل «ملاحظات الظهور في البحث» لوحده؟']
    assert 'دايمًا بموافقتك' in o['modal']['html'] and 'ترجّع أي واحدة' in o['modal']['html']
    o = ui({'mode': 'tab', 'api': api_, 'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'set', 'data-wt': 'seo_notes', 'data-level': 'alone'}}, {'modalClick': '#v2lv_go'}]})
    assert [c['body'] for c in o['calls'] if c.get('m') == 'PUT'] == [{'level': 'alone'}]


@needs_node
def test_the_server_409_text_reaches_the_screen_and_the_sheet_stays_open():
    refuse = {'__status': 409, 'error': '«نشر دورة جديدة» بيوصل للناس. دايمًا بموافقتك'}
    o = ui({'mode': 'tab', 'api': {'GET /v2/brain/levels': LEVELS_RESP, 'PUT /v2/brain/levels/seo_notes': refuse},
            'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'set', 'data-wt': 'seo_notes', 'data-level': 'alone'}}, {'modalClick': '#v2lv_go'}]})
    errs = [v for sel, v in o['sets'] if sel == '#v2lv_err']
    assert errs and 'بيوصل للناس. دايمًا بموافقتك' in errs[-1] and 'role="alert"' in errs[-1]
    assert [c['body'] for c in o['calls'] if c.get('m') == 'PUT'] == [{'level': 'alone'}]


@needs_node
def test_hint_opens_the_alone_sheet_for_that_row():
    o = ui({'mode': 'tab', 'api': {'GET /v2/brain/levels': LEVELS_RESP}, 'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'hint', 'data-wt': 'application_review'}}]})
    assert o['modals'] == ['تشغّل «مراجعة طلب انضمام خبير أو مدرّب» لوحده؟']


ALONE_ROWS = [
    {'id': 'a' * 32, 'work_type': 'visitor_open', 'title': 'فتح المنصة لزائر عادي', 'what': 'فتح المنصة لـسلمى', 'target_ref': 'pu:1', 'target_label': 'سلمى', 'at': '2026-11-13T09:40:00Z',
     'undone': False, 'can_undo': True, 'undo_note': ''},
    {'id': 'b' * 32, 'work_type': 'visitor_open', 'title': 'فتح المنصة لزائر عادي', 'what': 'فتح المنصة لـنادية', 'target_ref': 'pu:2', 'target_label': 'نادية', 'at': '2026-11-13T09:41:00Z',
     'undone': False, 'can_undo': True, 'undo_note': ''},
    {'id': 'c' * 32, 'work_type': 'seo_notes', 'title': 'ملاحظات الظهور في البحث', 'what': 'كتب ملاحظة بحث على «مقال النفقة»', 'target_ref': 'x', 'target_label': 'مقال النفقة',
     'at': '2026-11-13T09:50:00Z', 'undone': False, 'can_undo': False, 'undo_note': 'الملاحظة اتحسمت قبل كده'},
    {'id': 'd' * 32, 'work_type': 'comment_reject_abusive', 'title': 'إخفاء تعليق مسيء بوضوح', 'what': 'إخفاء تعليق مسيء على «نفقة»', 'target_ref': 'op:1', 'target_label': 'نفقة',
     'at': '2026-11-13T10:00:00Z', 'undone': True, 'can_undo': False, 'undo_note': 'اترجّعت'},
]


@needs_node
def test_home_box_lists_todays_alone_rows_grouped_with_undo():
    o = ui({'mode': 'board', 'api': {'GET /v2/brain/alone-log?day=today': {'rows': ALONE_ROWS}}})
    h = o['html']
    box = re.search(r'<section class="v2-box v2-brainbox".*?</section>', h, re.S).group(0)
    t = text_of(box)
    assert 'العقل عمل لوحده النهارده' in t and 'السجل كله' in t
    assert 'فتح المنصة لزائرين جدد (إيميلات عادية، من غير علامة اشتباه)' in t, 'اتنين بالمثنّى مش «لـ٢ زوّار»'
    assert 'كتب ملاحظة بحث على «مقال النفقة»' in t and 'الملاحظة اتحسمت قبل كده' in t, 'الرجوع المستحيل بيتقال صراحة'
    assert 'اترجّعت' in t and 'رجّعها' in t
    assert box.count('data-lv="undo"') == 1 and ('data-ids="%s,%s"' % ('a' * 32, 'b' * 32)) in box
    # اللي اترجّع ما فيهوش زرار
    assert 'class="undone"' in box


@needs_node
def test_home_box_group_text_for_one_and_many():
    one = ui({'mode': 'board', 'api': {'GET /v2/brain/alone-log?day=today': {'rows': ALONE_ROWS[:1]}}})
    assert 'فتح المنصة لـسلمى' in text_of(one['html'])
    six = [dict(ALONE_ROWS[0], id=('%032x' % i), what='فتح المنصة لـ' + str(i)) for i in range(6)]
    many = ui({'mode': 'board', 'api': {'GET /v2/brain/alone-log?day=today': {'rows': six}}})
    assert 'فتح المنصة لـ٦ زوّار جدد (إيميلات عادية، من غير علامة اشتباه)' in text_of(many['html'])
    eleven = [dict(ALONE_ROWS[0], id=('%032x' % i), what='فتح المنصة لـ' + str(i)) for i in range(11)]
    assert 'فتح المنصة لـ١١ زائرًا جديدًا' in text_of(ui({'mode': 'board', 'api': {'GET /v2/brain/alone-log?day=today': {'rows': eleven}}})['html'])


@needs_node
def test_home_box_undo_posts_every_row_of_the_group_and_stops_at_the_first_failure():
    ids = [('%032x' % i) for i in (1, 2, 3)]
    rows_ = [dict(ALONE_ROWS[0], id=i) for i in ids]
    api_ = {'GET /v2/brain/alone-log?day=today': {'rows': rows_}}
    for i in ids:
        api_['POST /v2/brain/alone-log/%s/undo' % i] = {'ok': True}
    o = ui({'mode': 'board', 'api': api_, 'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'undo'}}]})
    posts = [c['path'] for c in o['calls'] if c.get('m') == 'POST']
    assert posts == ['/v2/brain/alone-log/%s/undo' % i for i in ids]
    api_['POST /v2/brain/alone-log/%s/undo' % ids[1]] = {'__status': 409, 'error': 'مقدرناش نرجّعها دلوقتي — المنصة رفضت'}
    o = ui({'mode': 'board', 'api': api_, 'steps': [{'click': '[data-lv]', 'attr': {'data-lv': 'undo'}}]})
    posts = [c['path'] for c in o['calls'] if c.get('m') == 'POST']
    assert len(posts) == 2, 'وقف عند أول فشل'
    assert 'اترجّع ١ بس. مقدرناش نرجّعها دلوقتي — المنصة رفضت' in text_of(o['html'])


@needs_node
def test_home_box_states_failed_and_empty():
    bad = ui({'mode': 'board', 'api': {}})
    box = re.search(r'<section class="v2-box v2-brainbox".*?</section>', bad['html'], re.S).group(0)
    assert 'ما وصلتش البيانات' in box and 'حاول تاني' in box
    empty = ui({'mode': 'board', 'api': {'GET /v2/brain/alone-log?day=today': {'rows': []}}})
    assert 'لسه مفيش حاجة اتعملت لوحدها' in text_of(empty['html'])


@needs_node
def test_full_alone_log_view_has_times_and_undo():
    o = ui({'mode': 'tab', 'seg': 'alone', 'api': {'GET /v2/brain/alone-log?day=all': {'rows': ALONE_ROWS}, 'GET /v2/brain/levels': LEVELS_RESP}})
    t = text_of(o['html'])
    assert 'كل حاجة عملها العقل لوحده' in t and 'رجّعها' in o['html'] and re.search(r'[٠-٩]+:[٠-٩]{2} [صم]', t)
    assert 'v2lv-row' not in o['html']


VISITOR_ROW = {'apiKind': 'pending_user', 'apiId': 'u1', 'ref': 'PU-1', 'who': 'منى عبد الحميد', 'personEmail': 'mona@x.test', 'email': 'mona@x.test', 'ts': 1763020800000 - 3 * 3600e3,
               'canReject': True, 'flagLabels': [], 'puCountry': 'مصر'}
FLAGGED_ROW = dict(VISITOR_ROW, apiId='u2', ref='PU-2', who='بدر', personEmail='bader@x.test', email='bader@x.test', flagLabels=['حساب مكرر'])
PAYOUT_ROW = {'apiKind': 'manual_payment', 'apiId': 'm1', 'ref': 'PAY-1', 'who': 'منى', 'amount': 300, 'currency': 'EGP', 'payMethod': 'InstaPay', 'canReject': True, 'ts': 1763020800000}
PROMPTS = {'prompts': [{'work_type': 'visitor_open', 'n': 8, 'title': 'فتح المنصة لزائر عادي', 'unit': ['زوّار', 'زائرًا']},
                       {'work_type': 'payout', 'n': 9, 'title': 'x', 'unit': ['x', 'x']}], 'streak_needed': 8}


@needs_node
def test_learn_bar_shows_on_the_visitor_card_and_answers_go_to_the_server():
    api_ = {'GET /v2/brain/learn': PROMPTS, 'POST /v2/brain/learn/visitor_open/answer': {'ok': True}}
    o = ui({'mode': 'board', 'inbox': [VISITOR_ROW, FLAGGED_ROW, PAYOUT_ROW], 'mount': 'people', 'api': api_})
    s = o['strip']
    cards = re.split(r'<article class="v2z-c', s)[1:]
    people = [c for c in cards if 'منى عبد الحميد' in c]
    assert len(people) == 1 and 'v2lv-bar' in people[0]
    t = text_of(people[0])
    assert 'وافقت على اقتراحي في ٨ زوّار من غير ما تغيّر حاجة. تخليني أعملها لوحدي وأقولك بعدها؟' in t
    assert 'آه، خليها لوحده' in t and 'لا، فضّل اسألني' in t
    assert all('v2lv-bar' not in c for c in cards if 'بدر' in c), 'زائر عليه علامة اشتباه ⇒ مفيش سؤال'
    o = ui({'mode': 'board', 'inbox': [VISITOR_ROW], 'mount': 'people', 'api': api_,
            'steps': [{'strip': '[data-lv]', 'attr': {'data-lv': 'yes', 'data-wt': 'visitor_open'}}]})
    assert [c['path'] for c in o['calls'] if c.get('m') == 'POST'] == ['/v2/brain/learn/visitor_open/answer']
    assert [c['body'] for c in o['calls'] if c.get('m') == 'POST'] == [{'answer': 'yes'}]
    o = ui({'mode': 'board', 'inbox': [VISITOR_ROW], 'mount': 'people', 'api': api_,
            'steps': [{'strip': '[data-lv]', 'attr': {'data-lv': 'no', 'data-wt': 'visitor_open'}}]})
    assert [c['body'] for c in o['calls'] if c.get('m') == 'POST'] == [{'answer': 'no'}]


@needs_node
def test_learn_bar_absent_without_a_prompt_and_for_locked_card_kinds():
    o = ui({'mode': 'board', 'inbox': [VISITOR_ROW, PAYOUT_ROW], 'mount': 'people', 'api': {'GET /v2/brain/learn': {'prompts': [], 'streak_needed': 8}}})
    assert 'v2lv-bar' not in o['strip']
    o = ui({'mode': 'board', 'inbox': [PAYOUT_ROW], 'mount': 'money', 'api': {'GET /v2/brain/learn': PROMPTS}})
    assert 'v2lv-bar' not in o['strip'], 'تأكيد إيصال فلوس ⇒ ولا سؤال حتى لو الخادم رجّع نوع غريب'
    o = ui({'mode': 'board', 'inbox': [VISITOR_ROW], 'mount': 'people', 'api': {}})
    assert 'v2z-c' in o['strip'] and 'v2lv-bar' not in o['strip'], 'الخادم ما وصلش ⇒ البطاقة سليمة من غير شريطة'


@needs_node
def test_learn_bar_on_a_focus_card():
    o = ui({'mode': 'focus', 'inbox': [VISITOR_ROW], 'api': {'GET /v2/brain/learn': PROMPTS}})
    assert 'v2lv-bar' in o['html'] and 'تخليني أعملها لوحدي وأقولك بعدها؟' in text_of(o['html'])


@needs_node
def test_learn_bar_on_a_brain_item_card_uses_its_producer():
    item = {'id': 'f' * 32, 'producer': 'seo_notes', 'section': 'content', 'kind': 'note', 'target_label': 'مقال', 'tag': 'ملاحظة بحث', 'status': 'proposed',
            'body': {'text': 'نص', 'why': ''}, 'created_at': '2026-11-13T05:00:00Z', 'approve_label': 'احتفظ بها'}
    prm = {'prompts': [{'work_type': 'seo_notes', 'n': 9, 'title': 'ملاحظات', 'unit': ['ملاحظات', 'ملاحظة']}]}
    o = ui({'mode': 'board', 'inbox': [], 'brain': [item], 'mount': 'content', 'api': {'GET /v2/brain/learn': prm}})
    assert 'وافقت على اقتراحي في ٩ ملاحظات من غير ما تغيّر حاجة' in text_of(o['strip'])


TRAINER_ROW = {'apiKind': 'trainer', 'apiId': 't1', 'ref': 'TRN-1', 'who': 'منى عبد الحميد', 'personEmail': 'mona@x.test', 'ts': 1763020800000 - 48 * 3600e3, 'canReject': True,
               'rejectNeedsReason': True, 'trJoin': 'both', 'trHeadline': 'محامية بالنقض'}
REVIEWS = {'reviews': {'trainer:t1': {'producer': 'application_review', 'text': 'اقبلها واطلب صورة أوضح للبطاقة', 'why': 'الورق كامل إلا الهوية',
                                      'recommend': 'open', 'source': 'ai', 'created_at': '2026-11-13T05:00:00Z',
                                      'points': [{'ok': True, 'text': 'السيرة وصلت'}, {'ok': True, 'text': 'الفيديو وصل'}, {'ok': False, 'text': 'وثيقة الهوية لسه بتستنى مراجعتك'}]}}}


@needs_node
def test_review_box_on_the_application_card():
    o = ui({'mode': 'board', 'inbox': [TRAINER_ROW], 'mount': 'people', 'api': {'GET /v2/brain/reviews': REVIEWS}})
    s = o['strip']
    box = re.search(r'<div class="v2lv-rv".*?</details></div></div>', s, re.S).group(0)
    t = text_of(box)
    assert 'راجعت ملف الطلب' in t and 'اقتراحي: اقبلها واطلب صورة أوضح للبطاقة' in t and 'ليه؟ الورق كامل إلا الهوية' in t
    assert box.count('<li class="ok">') == 2 and box.count('<li class="no">') == 1 and '✓' in box and '>!<' in box
    assert '<details class="v2lv-why"><summary>ليه؟</summary>' in box
    o = ui({'mode': 'board', 'inbox': [TRAINER_ROW], 'mount': 'people', 'api': {'GET /v2/brain/reviews': {'reviews': {}}}})
    assert 'v2lv-rv' not in o['strip'], 'مفيش مراجعة ⇒ مفيش صندوق ولا نقط من عندنا'
    o = ui({'mode': 'board', 'inbox': [TRAINER_ROW], 'mount': 'people', 'api': {}})
    assert 'v2lv-rv' not in o['strip'] and 'محامية بالنقض' in o['strip']


@needs_node
def test_review_box_on_the_focus_card_and_on_brain_item_cards():
    o = ui({'mode': 'focus', 'inbox': [TRAINER_ROW], 'api': {'GET /v2/brain/reviews': REVIEWS}})
    assert 'v2lv-rv' in o['html'] and 'راجعت ملف الطلب' in text_of(o['html'])
    item = {'id': 'e' * 32, 'producer': 'ask_correction', 'section': 'home', 'kind': 'draft', 'target_label': 'تصحيح «اسأل»: سؤال', 'tag': 'تصحيح «اسأل»', 'status': 'proposed',
            'body': {'text': 'ملاحظة الخبير', 'why': 'يتّفق مع المادة', 'points': [{'ok': True, 'text': 'التصحيح واضح'}, {'ok': False, 'text': 'مفيش مرجع مكتوب'}]},
            'created_at': '2026-11-13T05:00:00Z', 'approve_label': 'اعتمد التصحيح'}
    o = ui({'mode': 'board', 'inbox': [], 'brain': [item], 'mount': 'home', 'api': {}})
    # شريط القسم الرئيسي ما بيتعرضش، فنجرّب شريط المحتوى بنفس البند
    item2 = dict(item, section='content')
    o = ui({'mode': 'board', 'inbox': [], 'brain': [item2], 'mount': 'content', 'api': {}})
    t = text_of(o['strip'])
    assert 'راجعت التصحيح' in t and 'التصحيح واضح' in t and 'مفيش مرجع مكتوب' in t and 'اقتراحي: ملاحظة الخبير' in t and 'ليه؟ يتّفق مع المادة' in t


@needs_node
def test_visitor_decision_is_reported_for_learning_but_other_cards_are_not():
    api_ = {'POST /v2/brain/learn': {'ok': True}, 'GET /v2/brain/learn': {'prompts': []}}
    o = ui({'mode': 'focus', 'inbox': [VISITOR_ROW], 'api': api_, 'steps': [{'click': '[data-a="primary"]'}]})
    learn = [c for c in o['calls'] if c.get('path') == '/v2/brain/learn' and c.get('m') == 'POST']
    assert [c['body']['work_type'] for c in learn] == ['visitor_open'] and learn[0]['body']['outcome'] == 'approved'
    o = ui({'mode': 'focus', 'inbox': [TRAINER_ROW], 'api': api_, 'steps': [{'click': '[data-a="primary"]'}]})
    assert [c for c in o['calls'] if c.get('path') == '/v2/brain/learn' and c.get('m') == 'POST'] == [], 'قبول مدرّب مش من أنواع التعلّم'
    o = ui({'mode': 'focus', 'inbox': [PAYOUT_ROW], 'api': api_, 'steps': [{'click': '[data-a="primary"]'}]})
    assert [c for c in o['calls'] if c.get('path') == '/v2/brain/learn'] == [] or all(c.get('m') == 'GET' for c in o['calls'] if c.get('path') == '/v2/brain/learn')


@needs_node
def test_comment_decisions_report_only_for_clearly_abusive_ones():
    code = ("const vm=require('vm'),fs=require('fs'),path=require('path');const dc=process.argv[1];const calls=[];"
            "const sb={console,setTimeout:(f)=>{f();return 0},Promise,JSON,Math,Date,Object,Array,String,Number,RegExp,Error,Intl};sb.window=sb;"
            "sb.document={readyState:'complete',addEventListener(){},getElementById(){return null},querySelector(){return null}};"
            "sb.V2SHELL={on:true};sb.EP={authed:true,api(p,o){calls.push([o&&o.method,p,o&&o.body]);return Promise.resolve({})}};"
            "vm.createContext(sb);['v2-logic.js','v2-levels.js'].forEach(f=>vm.runInContext(fs.readFileSync(path.join(dc,f),'utf8'),sb));"
            "const V=sb.V2LEVELS;V.reportComment({id:'1',moderation:{ai_checked:true,abusive:true}},'reject');V.reportComment({id:'2',moderation:{ai_checked:true,abusive:true}},'approve');"
            "V.reportComment({id:'3',moderation:{ai_checked:true,abusive:false}},'reject');V.reportComment({id:'4',moderation:null},'reject');V.reportComment({id:'5',moderation:{ai_checked:false,abusive:true}},'approve');"
            "setImmediate(()=>process.stdout.write(JSON.stringify(calls)))")
    proc = subprocess.run([v2_node.NODE, '-e', code, os.path.join(ROOT, 'dashboard-cloud')], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr[-800:]
    posts = [c for c in json.loads(proc.stdout) if c[0] == 'POST' and c[1] == '/v2/brain/learn']
    assert [(c[2]['work_type'], c[2]['outcome']) for c in posts] == [('comment_reject_abusive', 'approved'), ('comment_reject_abusive', 'rejected')]


@needs_node
def test_pure_helpers_learn_text_and_stat_text():
    code = ("const vm=require('vm'),fs=require('fs'),path=require('path');const dc=process.argv[1];"
            "const sb={console,setTimeout,Promise,JSON,Math,Date,Object,Array,String,Number,RegExp,Error,Intl};sb.window=sb;sb.document={};"
            "vm.createContext(sb);['v2-logic.js','v2-levels.js'].forEach(f=>vm.runInContext(fs.readFileSync(path.join(dc,f),'utf8'),sb));const lv=sb.V2L.lv;"
            "process.stdout.write(JSON.stringify({a:lv.learnText({n:8,unit:['طلبات','طلبًا']}),b:lv.learnText({n:12,unit:['طلبات','طلبًا']}),c:lv.learnText({}),"
            "d:lv.statText({stats:{kind:'times',n:1}}),e:lv.statText({stats:{kind:'times',n:0}}),f:lv.statText({locked:true,stats:{}}),g:lv.statText({stats:{kind:'external'}}),"
            "h:lv.cardWorkType({kind:'pending_user',row:{flagLabels:[]}}),i:lv.cardWorkType({kind:'pending_user',row:{flagLabels:['x']}}),j:lv.cardWorkType({kind:'payout'}),"
            "k:lv.cardWorkType({brainItem:{producer:'seo_notes'}}),l:lv.rows({types:'x'}),m:lv.aloneGroups('x')}))")
    proc = subprocess.run([v2_node.NODE, '-e', code, os.path.join(ROOT, 'dashboard-cloud')], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr[-800:]
    o = json.loads(proc.stdout)
    assert o['a'] == 'وافقت على اقتراحي في ٨ طلبات من غير ما تغيّر حاجة. تخليني أعملها لوحدي وأقولك بعدها؟'
    assert o['b'].startswith('وافقت على اقتراحي في ١٢ طلبًا من غير')
    assert o['c'].startswith('وافقت على اقتراحي في ٨ عناصر')
    assert (o['d'], o['e'], o['f']) == ('مرة واحدة', 'لسه ما حصلش حاجة', 'دايمًا بموافقتك') and o['g'].startswith('حسب إعداد')
    assert (o['h'], o['i'], o['j'], o['k']) == ('visitor_open', '', '', 'seo_notes') and o['l'] is None and o['m'] is None


# ═══════════════════════════════════════════════════════ ٨) مسودات الرد: واحدة لكل رسالة · وتتقفل لما هدفها يتقفل

def pmsg(mid, email='', name='', subject='طلب التعرف على كادر الأساتذة', body='أرجو التعرف على كادر الأساتذة', at='2026-11-09T08:00:00Z'):
    return {'id': mid, 'from_email': email, 'from_name': name, 'subject': subject, 'body': body, 'created_at': at}


def gather_replies(fx):
    from brain2 import producers_ops
    return producers_ops.gather_with_errors(Ctx(ns=NS, now=None, actor='x'))[0]


def test_replies_without_a_name_are_told_apart_by_who_sent_them(fx):
    fx.plat.pmsgs = [pmsg('1', email='sara@x.test'), pmsg('2', email='omar@x.test'), pmsg('3', email='dina@x.test')]
    labels = [t.label for t in gather_replies(fx) if t.ref.startswith('pmsg:')]
    assert len(labels) == 3 and len(set(labels)) == 3, labels
    assert 'رسالة عضو من sara — طلب التعرف على كادر الأساتذة' in labels
    fx.plat.pmsgs = [pmsg('4', email='a@x.test', name='منى')]
    named = [t.label for t in gather_replies(fx) if t.ref.startswith('pmsg:')]
    assert named == ['رسالة عضو من منى — طلب التعرف على كادر الأساتذة'], 'الاسم الصريح يعلو الإيميل'


def test_the_same_message_sent_three_times_gets_one_draft_the_latest(fx):
    fx.plat.pmsgs = [pmsg('1', email='sara@x.test', at='2026-11-09T08:00:00Z'), pmsg('2', email='sara@x.test', at='2026-11-09T09:00:00Z'),
                     pmsg('3', email='sara@x.test', at='2026-11-09T08:30:00Z'), pmsg('4', email='omar@x.test'), pmsg('5', email='', at='2026-11-09T08:00:00Z'),
                     pmsg('6', email='', at='2026-11-09T08:00:00Z')]
    refs = sorted(t.ref for t in gather_replies(fx) if t.ref.startswith('pmsg:'))
    assert refs == ['pmsg:2', 'pmsg:4', 'pmsg:5', 'pmsg:6'], 'نفس الإيميل والعنوان والنص ⇒ الأحدث بس؛ وبلا إيميل مش بنفترض إنهم نفس الشخص'


def test_old_duplicate_drafts_are_collapsed_on_read_and_expired_on_write(fx, monkeypatch):
    Item = engine._models(db)[0]
    base = datetime.datetime.utcnow() - datetime.timedelta(days=4)
    for i, mid in enumerate(('1', '2', '3')):
        db.session.add(Item(id='%032x' % (900 + i), producer='reply_draft', section='people', kind='draft', target_ref='pmsg:' + mid, target_label='رسالة عضو — طلب التعرف',
                            input_hash='dup%s' % mid, facts_json=json.dumps({'subject': 'طلب', 'body': 'نفس النص', 'has_account': True}, ensure_ascii=False),
                            meta_json=json.dumps({'id': mid, 'email': 'sara@x.test'}), body_json=json.dumps({'text': 'مسودة ' + mid}, ensure_ascii=False), status='proposed',
                            source='ai', mode='ask', created_at=base + datetime.timedelta(minutes=i)))
    db.session.commit()
    fx.plat.pmsgs = [pmsg('1', email='sara@x.test'), pmsg('2', email='sara@x.test'), pmsg('3', email='sara@x.test')]
    got = fx.api.get('/api/v2/brain/items?status=proposed').get_json()['items']
    assert [i['body']['text'] for i in got] == ['مسودة 3'], 'بطاقة واحدة بأحدث مسودة'
    # كتابة مسودة جديدة لنفس الرسالة بمعرّف تالت ⇒ القديمة تنتهي في القاعدة
    use(monkeypatch, *[p for p in registry.PRODUCERS if p.id == 'reply_draft'])
    fx.env.default = {'text': 'رد جديد'}
    monkeypatch.setattr(appmod, 'ai_call', lambda system, user, purpose='ai': json.dumps({'text': 'شكرًا لتواصلك معنا'}, ensure_ascii=False))
    fx.plat.pmsgs = [pmsg(m, email='sara@x.test', subject='طلب', body='نفس النص', at='2026-11-13T09:0%s:00Z' % m) for m in ('1', '2', '3', '9')]
    run(only=['reply_draft'])
    st = {r.target_ref: r.status for r in rows(producer='reply_draft')}
    assert st['pmsg:9'] == 'proposed' and st['pmsg:1'] == st['pmsg:2'] == st['pmsg:3'] == 'expired'


def seed_draft(ref, status='proposed', n=[0]):
    Item = engine._models(db)[0]
    n[0] += 1
    db.session.add(Item(id='%032x' % (7000 + n[0]), producer='reply_draft', section='people', kind='draft', target_ref=ref, target_label='رسالة ' + ref,
                        input_hash='s%d' % n[0], facts_json=json.dumps({'subject': 'س%d' % n[0], 'body': 'ب%d' % n[0]}), meta_json=json.dumps({'email': 'u%d@x.test' % n[0]}),
                        body_json=json.dumps({'text': 'مسودة'}), status=status, source='ai', mode='ask', created_at=datetime.datetime.utcnow()))
    db.session.commit()


def test_a_draft_whose_message_is_closed_closes_itself_as_stale(fx):
    for r in ('pmsg:1', 'pmsg:2', 'lead:7'):
        seed_draft(r)
    fx.plat.pmsgs = [pmsg('2', email='a@x.test')]          # الرسالة ١ اتردّ عليها واتقفلت، والليد ٧ اتعالج
    fx.plat.leads = []
    got = fx.api.get('/api/v2/brain/items?status=proposed').get_json()['items']
    assert [i['id'] for i in got] and len(got) == 1
    st = {r.target_ref: r.status for r in rows(producer='reply_draft')}
    assert st == {'pmsg:1': 'stale', 'pmsg:2': 'proposed', 'lead:7': 'stale'}
    assert fx.api.get('/api/v2/brain/items?status=stale').status_code == 200 and len(fx.api.get('/api/v2/brain/items?status=stale').get_json()['items']) == 2


def test_stale_sweep_never_closes_on_a_blind_or_truncated_source(fx):
    for r in ('pmsg:1', 'lead:7'):
        seed_draft(r)
    fx.plat.down.add('/api/bridge/messages')              # مصدر الرسايل واقع ⇒ ما نقفلش مسوداته
    fx.plat.leads = []
    assert engine.sweep_stale(NS, force=True) == 1
    assert {r.target_ref: r.status for r in rows(producer='reply_draft')} == {'pmsg:1': 'proposed', 'lead:7': 'stale'}
    fx.plat.down.clear()
    fx.plat.pmsgs = [pmsg(str(i), email='u%d@x.test' % i, body='ب%d' % i) for i in range(100, 100 + 20)]      # قايمة مقصوصة عند السقف
    assert engine.sweep_stale(NS, force=True) == 0, 'قايمة وصلت للسقف ⇒ ممكن الهدف مفتوح بره منها'
    assert {r.target_ref: r.status for r in rows(producer='reply_draft')}['pmsg:1'] == 'proposed'


def test_stale_sweep_is_throttled_and_leaves_other_producers_alone(fx):
    seed_draft('pmsg:1')
    fx.plat.pmsgs = [pmsg('2', email='a@x.test')]
    engine._SWEEP['at'] = 0.0
    assert engine.sweep_stale(NS) == 1
    seed_draft('pmsg:5')
    assert engine.sweep_stale(NS) == 0, 'مرة كل دقيقة بحد أقصى'
    assert engine.sweep_stale(NS, force=True) == 1
    assert 'stale' in engine.STATUSES


# ═══════════════════════════════════════════════════════ ٩) الشرائط الكحلي · «رجّعها» · توست واحد · سطر العقل · درج القراية

@needs_node
def test_a_section_info_line_lives_inside_the_strip_not_in_a_dark_bar():
    o = ui({'mode': 'board', 'inbox': [], 'mount': 'files', 'api': {}, 'info': {'files': 'التوزيع التلقائي يعمل، ووزّع ٣ ملفات اليوم'}})
    s = o['strip']
    assert 'مفيش حاجة مستنياك هنا' in s and 'v2z-info' in s and 'للعلم:</b> التوزيع التلقائي يعمل، ووزّع ٣ ملفات اليوم' in s
    none = ui({'mode': 'board', 'inbox': [], 'mount': 'files', 'api': {}})
    assert 'v2z-info' not in none['strip'], 'من غير سطر حقيقي مفيش «للعلم» فاضية'
    other = ui({'mode': 'board', 'inbox': [], 'mount': 'money', 'api': {}, 'info': {'files': 'x'}})
    assert 'v2z-info' not in other['strip'], 'سطر قسم ما بيظهرش في قسم تاني'


def test_dark_insight_bars_are_gone_or_light():
    css = _read('dashboard-cloud', 'v2-strip.css')
    for sel in ('.v2d-auto', '.v2p-brain', '.co-brain', '.mk-brainstrip', '.v2r-brain', '.v3-minbar'):
        assert sel in css.split('R24 م٣: ولا شريط كحلي')[1], sel
    assert re.search(r'\.v2d-auto,\.v2p-brain.*?\{background:#fff!important;color:#21262E!important', css)
    # الجمل المكرّرة للشريط اتشالت من مصدرها
    assert 'لا شيء يحتاج قرارك في الشركة الآن' not in _read('dashboard-cloud', 'v2s', 'company.js')
    assert 'جارٍ تحميل طلبات السوق' not in _read('dashboard-cloud', 'v2s', 'market.js')
    assert 'طلبات الدخول والانضمام كلها في بطاقات' not in _read('dashboard-cloud', 'v2s', 'people.js')
    assert 'v2ct-hero-in' not in _read('dashboard-cloud', 'v2s', 'content.js')
    assert "'التوزيع التلقائي يعمل' + (today ? '، ووزّع '" in _read('dashboard-cloud', 'v2-logic.js')
    for f in ('v2-d2.js', 'v2s/market.js', 'v2s/content.js'):
        assert 'V2STRIP.info' in _read('dashboard-cloud', *f.split('/'))


def test_the_reading_drawer_header_is_light():
    css = _read('dashboard-cloud', 'v2-strip.css')
    blk = css[css.index('.v2rd .drawer .dh,.v2rd .drawer .dh[style]'):]
    assert re.search(r'background:#F1EBE1!important;color:#21262E!important;border-top:4px solid #9E2B4E', blk)
    assert 'navy' not in blk.split('}')[0]


def _ep3(responses, code):
    script = os.path.join(_HERE, 'uiharness', 'r24_ep.js')
    p = subprocess.run([v2_node.NODE, script], input=json.dumps({'responses': responses, 'code': code, 'role': 'admin'}, ensure_ascii=False), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:] + p.stdout[-800:]
    return json.loads(p.stdout)


SIGNUPS3 = {'signups': [{'user_id': 'u1', 'email': 'a@x.test', 'full_name': 'أحمد', 'provider': 'google'}, {'user_id': 'u2', 'email': 'b@x.test', 'full_name': 'بهاء', 'provider': 'google'}]}
HIDE_U1 = {'rows': [{'key': 'signup:u1', 'until': None, 'kind': 'dismiss', 'reason': 'معروف', 'by': 'a', 'created_at': '2026-11-13T00:00:00Z', 'fingerprint': ''}]}


RESP3 = {'/api/v2/decisions/snoozed': {'status': 200, 'body': HIDE_U1}, '/api/platform-signups': {'status': 200, 'body': SIGNUPS3},
         '/api/v2/decisions/signup%3Au1/restore': {'status': 200, 'body': {'ok': True}}, '/api/v2/decisions/signup%3Au2/snooze': {'status': 200, 'body': {'ok': True}},
         '/api/v2/decisions/signup%3Au2/dismiss': {'status': 200, 'body': {'ok': True}}}


def _after(action):
    """يحمّل الوارد، ينفّذ الفعل، ويقرا الحالة **لحظة رجوع الفعل** (قبل ما إعادة التحميل الكاملة تخلص)."""
    code = ("window.__r = 0; window.V2 = { refresh: function () { window.__r++; } };EP.reload('inbox', null); return settled('inbox').then(function () {"
            "  return (" + action + ").then(function (res) { return { ok: res.ok, inbox: window.INBOX.map(function (r) { return r.ref; }).sort(),"
            "    hidden: window.INBOX_SNOOZED.map(function (h) { return h.key; }), map: Object.keys(EP.data.snooze.map), r: window.__r }; }); });")
    return _ep3(RESP3, code)['result']


@needs_node
def test_restore_snooze_and_dismiss_move_the_row_at_once_and_refresh_the_screen():
    assert _after("EP.restoreItem('signup:u1')") == {'ok': True, 'inbox': ['SGN-u1', 'SGN-u2'], 'hidden': [], 'map': [], 'r': 1}
    snz = _after("EP.snoozeItem('signup:u2', new Date(Date.now() + 86400e3).toISOString(), '')")
    assert snz['ok'] and snz['inbox'] == [] and snz['hidden'] == ['signup:u1', 'signup:u2'] and sorted(snz['map']) == ['signup:u1', 'signup:u2'] and snz['r'] == 1
    dis = _after("EP.dismissItem('signup:u2', 'معروف', '')")
    assert dis['ok'] and dis['inbox'] == [] and 'signup:u2' in dis['hidden'] and dis['r'] == 1


@needs_node
def test_a_failed_restore_changes_nothing_locally():
    code = ("window.V2 = { refresh: function () { window.__r = 1; } };EP.reload('inbox', null); return settled('inbox').then(function () {"
            "  return EP.restoreItem('signup:u1').then(function (res) { return { ok: res.ok, hidden: window.INBOX_SNOOZED.length, inbox: window.INBOX.length, r: window.__r || 0 }; }); });")
    out = _ep3({'/api/v2/decisions/snoozed': {'status': 200, 'body': HIDE_U1}, '/api/platform-signups': {'status': 200, 'body': SIGNUPS3},
                '/api/v2/decisions/signup%3Au1/restore': {'status': 500, 'body': {'error': 'x'}}}, code)['result']
    assert out == {'ok': False, 'hidden': 1, 'inbox': 1, 'r': 0}


@needs_node
def test_a_finished_card_leaves_the_counts_immediately_and_toasts_once():
    api_ = {'GET /v2/brain/learn': {'prompts': []}}
    o = ui({'mode': 'board', 'inbox': [VISITOR_ROW], 'mount': 'people', 'api': api_, 'steps': [{'strip': '[data-a]', 'attr': {'data-a': 'p'}}]})
    t = [c['t'] for c in o['calls'] if c.get('fn') == 'toast'] + o['toasts']
    assert len(t) <= 1, t
    brain_js = _read('dashboard-cloud', 'v2-brain2.js')
    assert "if (!ct) { finish(); return; }" in brain_js and "if (!ct) { toast(" not in brain_js, 'توست واحد بعد رفض اقتراح العقل'
    home = _read('dashboard-cloud', 'v2-home.js')
    assert 'function dropRows(c)' in home and 'dropRows(c);' in home and 'V2.refresh = function' in home


@needs_node
def test_brain_tab_line_counts_only_visible_suggestions_and_says_where():
    code = ("const vm=require('vm'),fs=require('fs'),path=require('path');const dc=process.argv[1];"
            "const sb={console,setTimeout,Promise,JSON,Math,Date,Object,Array,String,Number,RegExp,Error,Intl};sb.window=sb;sb.document={};"
            "vm.createContext(sb);vm.runInContext(fs.readFileSync(path.join(dc,'v2-logic.js'),'utf8'),sb);const L=sb.V2L;"
            "const base={queue:{alerts:[]},settings:{auto_assign:{value:true}},entries:{autoCount:0,changedCount:0}};"
            "process.stdout.write(JSON.stringify({two:L.v2sBrainLine(Object.assign({},base,{proposed:2,proposedBy:{people:1,content:1}})).text,"
            "one:L.v2sBrainLine(Object.assign({},base,{proposed:1,proposedBy:{people:1}})).text,"
            "none:L.v2sBrainLine(Object.assign({},base,{proposed:0,proposedBy:{}})).text}))")
    proc = subprocess.run([v2_node.NODE, '-e', code, os.path.join(ROOT, 'dashboard-cloud')], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr[-800:]
    o = json.loads(proc.stdout)
    assert o['two'] == 'ينتظرك من العقل: اقتراحان في الناس والمحتوى' and o['one'] == 'ينتظرك من العقل: اقتراح واحد في الناس'
    assert 'ينتظرك من العقل' not in o['none']
    assert 'visibleBrainCards' in _read('dashboard-cloud', 'v2s', 'brain.js')


# ═══════════════════════════════════════════════════════ ١٠) ولا قرار بيتسقط: كل اقتراح له بيت، والأرقام واحدة بالتركيب

def brain_item(i, producer, section, status='proposed'):
    return {'id': '%032x' % i, 'producer': producer, 'section': section, 'kind': 'draft', 'target_label': 'اقتراح %d' % i, 'tag': 'وسم', 'status': status,
            'body': {'text': 'نص %d' % i, 'why': ''}, 'created_at': '2026-11-13T05:00:00Z', 'approve_label': 'اعتمد'}


def all_sections_fixture():
    """اقتراح لكل منتج مسجّل بقسمه الحقيقي + نسخ قديمة مكتوب فيها `home` + أقسام وأسماء غريبة + اقتراحات مش `proposed`."""
    items, i = [], 1
    for p in registry.PRODUCERS:
        if p.kind == 'opinion':
            continue
        items.append(brain_item(i, p.id, p.section)); i += 1
    for pid in ('ask_correction', 'ask_topic', 'library_contribution', 'training_item'):
        items.append(brain_item(i, pid, 'home')); i += 1               # صفوف قديمة: القسم المكتوب `home`
    for sec, pid in (('weird_section', 'seo_notes'), ('', 'unknown_producer'), ('nowhere', 'unknown_producer'), ('reports', 'weekly_read'), ('brain', 'links_digest')):
        items.append(brain_item(i, pid, sec)); i += 1
    items.append(brain_item(i, 'seo_notes', 'content', status='approved')); i += 1      # مش مقترح ⇒ ولا بيتعدّ
    return items


def test_ask_family_producers_live_in_content_by_their_registry_section():
    for pid in ('ask_correction', 'ask_topic', 'library_contribution', 'training_item'):
        assert registry.by_id(pid).section == 'content', pid
    for p in registry.PRODUCERS:
        assert p.kind == 'opinion' or p.section in {'people', 'files', 'disputes', 'money', 'courses', 'books', 'market', 'content', 'marketing', 'company', 'reports', 'brain'}, (p.id, p.section)   # reports/brain أسماء قديمة بتتحوّل (marketing/company)


@needs_node
def test_every_proposed_brain_item_lands_in_exactly_one_strip_and_the_numbers_agree():
    items = all_sections_fixture()
    # مراجعة طلب الانضمام بتتعرض جوه بطاقة الطلب نفسه، فمش بطاقة قرار لوحدها (مش «بتتسقط»).
    proposed = [x for x in items if x['status'] == 'proposed' and x['producer'] != 'application_review']
    snoozed_ids = [proposed[0]['id'], proposed[3]['id']]
    until = '2099-01-01T08:00:00Z'
    snooze = {'map': {'brain_item:' + sid: {'key': 'brain_item:' + sid, 'kind': 'snooze', 'until': until, 'fingerprint': ''} for sid in snoozed_ids}, 'ok': True, 'at': 1}
    o = ui({'mode': 'board', 'inbox': [], 'brain': items, 'snooze': snooze, 'api': {}})
    sums = o['sums']
    want = len(proposed) - len(snoozed_ids)
    strips = sums['strips']
    landed = [cid for st in strips.values() for cid in st['ids']]
    assert len(landed) == len(set(landed)) == want, '«ولا قرار بيتسقط ولا بيتكرّر»'
    assert sum(st['n'] for st in strips.values()) == want == sums['deckN'] == sums['counts']['total']
    expected_ids = {'brain_item|' + x['id'] for x in proposed if x['id'] not in snoozed_ids}
    assert set(landed) == expected_ids
    # المربّعات (والقايمة الجانبية) = نفس الأرقام بالظبط، ومجموعها = «ابدأ القرارات (ن)»
    tiles = {t['key']: t['count'] for t in sums['tiles']}
    assert all(tiles[k] == strips[k]['n'] for k in tiles) and sum(tiles.values()) == want
    assert 'ابدأ القرارات (' + ar_digits(want) + ')' in text_of(o['html'])
    # الأماكن: منتجات «اسأل» ⇒ المحتوى (حتى الصفوف القديمة `home`)، والبيت المجهول ⇒ الشركة والعقل
    by_label = {}
    for sec, st in strips.items():
        for cid, home in zip(st['ids'], st['homes']):
            assert home == sec, 'c.home لازم يطابق الشريط اللي اتعدّ فيه'
            by_label[cid] = sec
    for x in proposed:
        cid = 'brain_item|' + x['id']
        if cid not in by_label:
            continue
        if x['producer'] in ('ask_correction', 'ask_topic', 'library_contribution', 'training_item'):
            assert by_label[cid] == 'content', x
        if x['section'] in ('weird_section', 'nowhere', '') and x['producer'] == 'unknown_producer':
            assert by_label[cid] == 'company', x
        if x['section'] == 'weird_section':
            assert by_label[cid] == 'company'
        if x['section'] == 'reports':
            assert by_label[cid] == 'marketing'


def ar_digits(n):
    return str(n).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))


@needs_node
def test_unknown_inbox_kinds_and_homes_fall_back_to_company_and_are_counted():
    odd = {'apiKind': 'something_new', 'apiId': 'z1', 'ref': 'ZZ-1', 'who': 'غريب', 'ts': 1763020800000 - 3600e3, 'note': 'بند من نوع لسه ما اتعرفش'}
    o = ui({'mode': 'board', 'inbox': [odd, VISITOR_ROW], 'brain': [], 'api': {}})
    sums = o['sums']
    landed = [cid for st in sums['strips'].values() for cid in st['ids']]
    assert sum(st['n'] for st in sums['strips'].values()) == len(landed) == sums['deckN'] == sums['counts']['total']
    assert sums['deckN'] >= 1 and all(t['count'] == sums['strips'][t['key']]['n'] for t in sums['tiles'])


@needs_node
def test_the_company_strip_shows_brain_items_whose_section_was_home():
    item = brain_item(77, 'unknown_producer', 'home')
    o = ui({'mode': 'board', 'inbox': [], 'brain': [item], 'mount': 'company', 'api': {}})
    assert o['sums']['strips']['company']['n'] == 1 and 'اقتراح 77' in o['strip'] and 'مفيش حاجة مستنياك هنا' not in o['strip']


# ═══════════════════════════════════════════════════════ ٧) ثابت

DOCKERFILE = _read('Dockerfile')
NEW_JS = _read('dashboard-cloud', 'v2-levels.js')
NEW_CSS = _read('dashboard-cloud', 'v2-levels.css')


def test_dockerfile_ships_every_new_file():
    assert 'COPY backend/v2_levels_routes.py /app/v2_levels_routes.py' in DOCKERFILE
    assert 'dashboard-cloud/v2-levels.js' in DOCKERFILE and 'dashboard-cloud/v2-levels.css' in DOCKERFILE
    assert 'COPY backend/brain2 /app/brain2' in DOCKERFILE, 'levels.py وalone.py وproducers_apply.py جوه brain2'
    for f in ('levels.py', 'alone.py', 'producers_apply.py'):
        assert os.path.exists(os.path.join(ROOT, 'backend', 'brain2', f))
    html = _read('dashboard-cloud', 'index.html')
    assert html.count('<script src="v2-levels.js"></script>') == 1 and html.count('<link rel="stylesheet" href="v2-levels.css">') == 1
    assert html.index('v2-strip.js') < html.index('v2-levels.js') < html.index('v2s/_registry.js')
    assert 'import v2_levels_routes as _v2lv' in _read('backend', 'app.py')


def test_the_flask_app_registers_the_new_routes():
    rules = {(r.rule, m) for r in flask_app.url_map.iter_rules() for m in r.methods}
    for rule, m in [('/api/v2/brain/levels', 'GET'), ('/api/v2/brain/levels/<work_type>', 'PUT'), ('/api/v2/brain/learn', 'GET'), ('/api/v2/brain/learn', 'POST'),
                    ('/api/v2/brain/learn/<work_type>/answer', 'POST'), ('/api/v2/brain/alone-log', 'GET'), ('/api/v2/brain/alone-log/<log_id>/undo', 'POST'),
                    ('/api/v2/brain/reviews', 'GET')]:
        assert (rule, m) in rules, (rule, m)


AR_DIGIT_DOT = re.compile(r'[٠-٩]\s*·|·\s*[٠-٩]')
TECH = re.compile(r'\b(API|JSON|SQL|token|endpoint|payload|null|undefined)\b', re.I)


def _visible_strings(js):
    """نصوص عربية ظاهرة بين علامات اقتباس في الملف (تقريب كفاية لمسح النصوص)."""
    return re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js)


def test_copy_scan_no_dot_next_to_arabic_digits_and_no_technical_words():
    for name, src in (('v2-levels.js', NEW_JS), ('levels.py', _read('backend', 'brain2', 'levels.py')), ('alone.py', _read('backend', 'brain2', 'alone.py')),
                      ('producers_apply.py', _read('backend', 'brain2', 'producers_apply.py'))):
        assert not AR_DIGIT_DOT.search(src), name
    for s in _visible_strings(NEW_JS):
        if s.strip().startswith(('/', '<', '.', '#')):
            continue
        assert not TECH.search(re.sub(r'<[^>]+>', ' ', s)), s
    for s in re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", _read('backend', 'brain2', 'levels.py')):
        if 'ERR_' in s:
            continue
    assert 'ما بيتعكسش' in _read('backend', 'brain2', 'levels.py') and 'دايمًا بموافقتك' in _read('backend', 'brain2', 'levels.py')


def test_visible_server_sentences_are_plain_and_gender_neutral():
    sentences = [levels.LOCK_TEXT, levels.ERR_BAD_LEVEL, levels.ERR_NOT_ALLOWED, levels.FAIL_AR, alone.MSG_VISITOR_UNDO, alone.MSG_COMMENT_UNDO, alone.MSG_NOTE_UNDO,
                 alone.ERR_PLATFORM, alone.ERR_NOTE_GONE]
    for s in sentences:
        assert not AR_DIGIT_DOT.search(s) and not TECH.search(s) and not engine.has_banned(s), s
    for w in levels.WORK_TYPES:
        for s in (w.title, w.hint):
            assert not AR_DIGIT_DOT.search(s) and not engine.has_banned(s) and not re.match(r'^\s*(الذكاء|AI)', s), s


def test_css_is_scoped_and_uses_the_approved_look():
    assert '#F7F3ED' in NEW_CSS and '#9E2B4E' in NEW_CSS and '#21262E' in NEW_CSS and 'IBM Plex Sans Arabic' in NEW_CSS
    for sel in re.findall(r'^([^{@/][^{]*)\{', NEW_CSS, re.M):
        for part in sel.split(','):
            part = part.strip()
            if part:
                assert 'v2lv-' in part or part.startswith('from') or part.startswith('to') or part.endswith('%'), part


def test_spec_docs_mention_phase_three():
    assert 'م٣' in _read('STATUS.md') and 'brain_levels' in _read('STATUS.md')
    assert 'مستويات العقل' in _read('CLAUDE.md')
