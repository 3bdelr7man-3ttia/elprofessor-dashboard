# -*- coding: utf-8 -*-
"""الجولة ٢ للعقل · الحزمة P3 (منتجو الأقسام). SPEC: docs/v2/brain2/SPEC.md §3.3 / §3.4 / §5

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_biz.py

⛔ صفر شبكة وصفر ذكاء حقيقي: كل مساعدات `ns` (`_platform_proxy` · `_v2_get` · `_bridge_get` · `_v2_write` · `_seo_scorecard`
والموديلات) بدائل محلية في الذاكرة، والمحرّك غير مستورد (يُحقن بديل له حين يلزم).
"""
import datetime
import json
import re
import sys
import types

import pytest

from brain2 import producers_biz as biz
from brain2.contract import ApplyResult, Ctx, Producer, SourceDown, Target

NOW = datetime.datetime(2026, 11, 20, 9, 0, tzinfo=datetime.timezone.utc)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'\d{8,}')
ALL_IDS = ['course_review', 'market_match', 'seo_notes', 'campaign_comment', 'weekly_read', 'forecast_comment', 'course_lesson_draft']


# ------------------------------------------------------------------ بدائل ns
class Resp:
    def __init__(self, status=200, data=None):
        self.status, self.data = status, data if data is not None else {}


def resp_ok(r):
    return 200 <= r.status < 300


def proxy_json(r):
    return r.data if isinstance(r.data, dict) else {}


class Rows:
    """موديل بسيط: `Model.query.all()`."""
    def __init__(self, rows):
        self.rows = rows

    @property
    def query(self):
        return self

    def all(self):
        return list(self.rows)


class Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


COURSES = [
    {'id': 'c-pend-1', 'slug': 'cp1', 'title': 'عقود الشركات للمبتدئين', 'type': 'recorded_paid', 'is_active': False,
     'approval_status': 'pending', 'short_description': 'تواصل مع sara@example.com أو 01012345678 للتفاصيل', 'lesson_count': 7},
    {'id': 'c-pend-2', 'slug': 'cp2', 'title': 'التحكيم التجاري', 'type': 'recorded_free', 'is_active': False,
     'approval_status': 'pending', 'short_description': 'مدخل إلى التحكيم', 'lesson_count': 4},
    {'id': 'c-live-1', 'slug': 'cl1', 'title': 'صياغة العقود', 'type': 'recorded_paid', 'is_active': True,
     'approval_status': 'approved', 'lesson_count': 12},
    {'id': 'c-live-2', 'slug': 'cl2', 'title': 'الملكية الفكرية', 'type': 'recorded_paid', 'is_active': True,
     'approval_status': None, 'lesson_count': 9},
    {'id': 'c-old', 'slug': 'co', 'title': 'دورة مؤرشفة', 'type': 'recorded_paid', 'is_active': True,
     'approval_status': 'approved', 'archived_at': '2026-01-01'},
    {'id': 'c-hidden', 'slug': 'ch', 'title': 'مسودة', 'type': 'recorded_paid', 'is_active': False, 'approval_status': 'approved'},
]
CHECKLISTS = {
    'c-pend-1': [{'key': 'content', 'item': 'فيها محتوى', 'ok': True}, {'key': 'intro', 'item': 'فيديو تعريفي مرفوع', 'ok': False},
                 {'key': 'level', 'item': 'مستوى الدورة محدّد', 'ok': False}],
    'c-pend-2': [{'key': 'content', 'item': 'فيها محتوى', 'ok': True}, {'key': 'level', 'item': 'مستوى الدورة محدّد', 'ok': True}],
}
REQUESTS = [
    {'id': 'r1', 'kind': 'request', 'need_kind': 'course', 'status': 'open', 'title': 'أريد دورة في صياغة العقود',
     'body': 'أحتاج تعلم الصياغة، راسلوني على ali@example.com أو 00201001234567', 'specialty': 'عقود',
     'member_email': 'ali@example.com', 'member_name': 'علي محمود', 'linked_course_id': ''},
    {'id': 'r2', 'kind': 'request', 'need_kind': 'service', 'status': 'open', 'title': 'محامٍ لقضية إيجار', 'body': 'قضية',
     'linked_course_id': 'c-live-1'},
    {'id': 'r3', 'kind': 'request', 'need_kind': 'course', 'status': 'open', 'title': 'مخفي', 'body': 'x', 'hidden': True},
    {'id': 'r4', 'kind': 'training_offer', 'need_kind': 'training_offer', 'status': 'open', 'title': 'عرض تدريب', 'body': 'y'},
    {'id': 'r5', 'kind': 'request', 'need_kind': 'course', 'status': 'open', 'title': 'تجريبي', 'body': 'z', 'is_test': True},
]
ARTICLES = [
    {'id': 'a1', 'title': 'مقال ضعيف'}, {'id': 'a2', 'title': 'مقال متوسط'}, {'id': 'a3', 'title': 'مقال سليم'}, {'title': 'بلا معرّف'},
]
SCORES = {
    'a1': {'id': 'a1', 'title': 'مقال ضعيف', 'score': 40, 'words': 200,
           'issues': ['لا يوجد وصف ميتا (meta description)', 'المقال قصير جدًا (أقل من ٣٠٠ كلمة)', '⚠️ يذكر منصة منافسة (ممنوع)']},
    'a2': {'id': 'a2', 'title': 'مقال متوسط', 'score': 70, 'words': 700, 'issues': ['لا يوجد قسم أسئلة شائعة']},
    'a3': {'id': 'a3', 'title': 'مقال سليم', 'score': 100, 'words': 900, 'issues': []},
}
WEEK_PAYLOAD = {
    'ok': True, 'week': {'start': '2026-11-08', 'end': '2026-11-14', 'label': '٨ نوفمبر إلى ١٤ نوفمبر'},
    'sources': {'money': 'ok', 'users': 'partial'},
    'text': 'تقرير الأسبوع\n٨ نوفمبر إلى ١٤ نوفمبر، مقارنة بالأسبوع الذي قبله\n\nملخص العقل\nما يعمل: المبيعات ارتفعت\n\nالأرقام\nالحسابات الجديدة: ٤٢',
}


class Platform:
    """منصّة في الذاكرة + سجل النداءات."""
    def __init__(self):
        self.calls = []
        self.down = set()
        self.write_resp = Resp(200, {'ok': True})

    def proxy(self, method, path, params=None, json_body=None, timeout=12):
        self.calls.append((method, path, params, json_body))
        if path in self.down:
            return Resp(502, {'error': 'x'})
        if path == '/api/bridge/courses':
            return Resp(200, {'courses': COURSES, 'count': len(COURSES)})
        m = re.match(r'^/api/bridge/courses/([^/]+)/checklist$', path)
        if m:
            if m.group(1) not in CHECKLISTS:
                return Resp(404, {'error': 'x'})
            return Resp(200, {'course_id': m.group(1), 'checklist': CHECKLISTS[m.group(1)]})
        raise AssertionError('نداء غير متوقّع: %s %s' % (method, path))

    def v2_get(self, path, params=None):
        self.calls.append(('GET', path, params, None))
        if path in self.down:
            return Resp(502, {'error': 'x'})
        if path == '/api/bridge/market/requests':
            return Resp(200, {'items': REQUESTS, 'total': len(REQUESTS)})
        raise AssertionError('نداء غير متوقّع: %s' % path)

    def v2_write(self, method, path, body, audit_action, target, meta, params=None):
        self.calls.append((method, path, body, audit_action, target, meta))
        return self.write_resp

    def bridge_get(self, path, params=None):
        self.calls.append(('GET', path, params, None))
        if path in self.down:
            return None
        return {'articles': ARTICLES}


@pytest.fixture
def plat():
    return Platform()


@pytest.fixture
def ctx(plat):
    snapshot = {
        'financials': {'total_revenue_egp': 120000, 'total_expenses_egp': 80000, 'net_profit_egp': 40000, 'payout_cost_egp': 5000,
                       'top_clients': [{'name': 'عميل سري', 'total_egp': 9}], 'revenue_by_source': {'x': 1}},
        'cashflow': {'balance_egp': 55000, 'transactions': [{'description': 'سري'}]},
    }
    ns = {
        '_platform_proxy': plat.proxy, '_v2_get': plat.v2_get, '_v2_write': plat.v2_write, '_bridge_get': plat.bridge_get,
        '_resp_ok': resp_ok, '_proxy_json': proxy_json,
        '_seo_scorecard': lambda a: dict(SCORES[a['id']]),
        'Campaign': Rows([
            Row(id=1, name='حملة الخريف', platform='facebook', status='active', budget=500.0, spent=320.5, currency='USD',
                impressions=12000, clicks=340, leads=21, conversions=4, revenue_attributed=900.0),
            Row(id=2, name='حملة متوقفة', platform='google_ads', status='paused', budget=100.0, spent=10.0, currency='USD',
                impressions=100, clicks=5, leads=0, conversions=0, revenue_attributed=0.0),
            Row(id=3, name='مسودة', platform='tiktok', status='draft', budget=50.0, spent=0.0, currency='USD',
                impressions=0, clicks=0, leads=0, conversions=0, revenue_attributed=0.0),
            Row(id=4, name='منتهية', platform='x', status='completed', budget=50.0, spent=40.0, currency='USD',
                impressions=1, clicks=1, leads=1, conversions=1, revenue_attributed=1.0),
            Row(id=5, name='نشطة بلا إنفاق', platform='x', status='active', budget=50.0, spent=0.0, currency='USD',
                impressions=0, clicks=0, leads=0, conversions=0, revenue_attributed=0.0),
        ]),
        'ForecastMonth': Rows([
            Row(month='2026-10', revenue_egp=1, cogs_egp=0, marketing_egp=0, payroll_egp=0, rent_egp=0, other_sga_egp=0, target_courses=1, target_students=1),
            Row(month='2026-12', revenue_egp=60000.0, cogs_egp=5000.0, marketing_egp=10000.0, payroll_egp=20000.0, rent_egp=3000.0, other_sga_egp=2000.0, target_courses=3, target_students=120),
            Row(month='2026-11', revenue_egp=50000.0, cogs_egp=4000.0, marketing_egp=9000.0, payroll_egp=20000.0, rent_egp=3000.0, other_sga_egp=1000.0, target_courses=2, target_students=100),
            Row(month='2027-01', revenue_egp=70000.0, cogs_egp=0, marketing_egp=0, payroll_egp=0, rent_egp=0, other_sga_egp=0, target_courses=4, target_students=140),
            Row(month='2027-02', revenue_egp=80000.0, cogs_egp=0, marketing_egp=0, payroll_egp=0, rent_egp=0, other_sga_egp=0, target_courses=5, target_students=160),
        ]),
        'generate_ai_snapshot': lambda: snapshot,
    }
    return Ctx(ns=ns, now=NOW, actor='founder@elprofessor.net')


@pytest.fixture(autouse=True)
def weekly(monkeypatch):
    monkeypatch.setattr(biz, '_load_weekly_for', lambda: (lambda G, w=None: (json.loads(json.dumps(WEEK_PAYLOAD)), None)))


def prod(pid):
    return next(p for p in biz.PRODUCERS if p.id == pid)


def gather(pid, ctx):
    return prod(pid).gather(ctx)


# ------------------------------------------------------------------ السجل والبيانات الثابتة
def test_registry_ids_and_flags():
    assert [p.id for p in biz.PRODUCERS] == ALL_IDS
    assert all(isinstance(p, Producer) for p in biz.PRODUCERS)
    alone = {p.id for p in biz.PRODUCERS if p.may_run_alone}
    assert alone == {'seo_notes', 'campaign_comment', 'weekly_read', 'forecast_comment'}
    for p in biz.PRODUCERS:
        if p.may_run_alone:
            assert p.lock_reason == '' and p.default_mode == 'alone' and p.kind == 'note'
        else:
            assert p.lock_reason and p.default_mode == 'ask' and p.kind == 'draft'
    assert prod('weekly_read').per_run_cap == 1 and prod('forecast_comment').per_run_cap == 1
    assert all(prod(i).per_run_cap == 3 for i in ('course_review', 'market_match', 'seo_notes', 'campaign_comment'))
    assert {p.id: p.section for p in biz.PRODUCERS} == {
        'course_review': 'courses', 'market_match': 'market', 'seo_notes': 'content', 'campaign_comment': 'marketing',
        'weekly_read': 'reports', 'forecast_comment': 'company', 'course_lesson_draft': 'courses'}


def test_registry_copy_is_exact():
    cr, mm, seo, cc, wr, fc = (prod(i) for i in ALL_IDS[:6])
    assert cr.label == 'مراجعة الدورة قبل النشر'
    assert cr.sentence == 'عندما تُقدَّم دورة للنشر، يكتب العقل ما ينقصها ويقترح: انشر أو أصلح أولًا.'
    assert cr.lock_reason == 'يسألك دائمًا لأن النشر يظهر للناس.' and cr.approve_label == 'انشر الدورة'
    assert mm.label == 'ربط طلبات السوق بدورة مناسبة'
    assert mm.sentence == 'عندما يطلب عضو شيئًا تغطيه دورة لدينا، يقترح العقل ربطه بها.'
    assert mm.lock_reason == 'يسألك دائمًا لأنه يغيّر بيانات الطلب على المنصة.' and mm.approve_label == 'اربطه بالدورة'
    assert seo.label == 'ملاحظات الظهور في البحث على المسودات'
    assert seo.sentence == 'عندما تنتظر مسودة مقال، يكتب العقل ما يحسّن ظهورها في البحث. لا يُنشر شيء.'
    assert cc.label == 'تعليق على الحملات' and cc.sentence == 'عندما تتغير أرقام حملة، يكتب العقل تعليقًا قصيرًا عليها.'
    assert wr.label == 'قراءة الأسبوع' and wr.sentence == 'في بداية كل أسبوع، يكتب العقل قراءة قصيرة لأرقام الأسبوع الماضي.'
    assert fc.label == 'تعليق على التوقعات'
    assert fc.sentence == 'عندما تتغير التوقعات أو الأرقام الفعلية، يكتب العقل تعليقًا عليها.'


def test_arabic_copy_rules():
    texts = []
    for p in biz.PRODUCERS:
        texts += [p.label, p.sentence, p.lock_reason, p.tag, p.approve_label]
    texts += [biz.CR_PUBLISH_LABEL, biz.CR_OPEN_LABEL]
    for t in texts:
        assert 'يقوّم' not in t and 'اعكس' not in t and '⇒' not in t and '✓' not in t and 'لما ' not in t
        assert not t.startswith('الذكاء') and not re.search(r'[A-Za-z]', t)
        assert 'null' not in t and 'undefined' not in t


def test_hidden_hook():
    h = prod('course_lesson_draft')
    assert h.listed is False and h.may_run_alone is False and h.apply is None and h.kind == 'draft'
    assert h.gather(None) == []
    d = h.gather.__doc__
    assert 'gather' in d and 'validate' in d and 'apply' in d and "'fields'" in d and 'confirmed:true' in d
    assert all(p.listed for p in biz.PRODUCERS if p.id != 'course_lesson_draft')


# ------------------------------------------------------------------ course_review
def test_course_review_gather_targets(ctx, plat):
    ts = gather('course_review', ctx)
    assert [t.ref for t in ts] == ['course:c-pend-1', 'course:c-pend-2']
    t = ts[0]
    assert t.label == 'عقود الشركات للمبتدئين'
    assert t.meta == {'course_id': 'c-pend-1', 'slug': 'cp1'}
    assert set(t.facts) == {'id', 'title', 'type', 'short_description', 'lessons', 'outcomes', 'level', 'checklist'}
    assert t.facts['lessons'] == 7 and t.facts['type'] == 'recorded_paid'
    assert t.facts['checklist'][1] == {'item': 'فيديو تعريفي مرفوع', 'ok': False}
    assert plat.calls[0][:2] == ('GET', '/api/bridge/courses')
    assert [c[1] for c in plat.calls[1:]] == ['/api/bridge/courses/c-pend-1/checklist', '/api/bridge/courses/c-pend-2/checklist']
    assert not any(c[0] != 'GET' for c in plat.calls)
    assert not any('/agents/' in c[1] for c in plat.calls)       # قاعدة §0.3


def test_course_review_facts_clean_and_small(ctx):
    for t in gather('course_review', ctx):
        blob = json.dumps(t.facts, ensure_ascii=False)
        assert not EMAIL_RE.search(blob) and not PHONE_RE.search(blob)
        assert len(blob.encode('utf-8')) <= 4096


def test_course_review_facts_trimmed_to_4k(ctx):
    big = dict(COURSES[0], short_description='ع' * 900)
    ctx.ns['_platform_proxy'] = lambda m, p, params=None, json_body=None, timeout=12: (
        Resp(200, {'courses': [big]}) if p == '/api/bridge/courses'
        else Resp(200, {'checklist': [{'item': 'بند طويل جدا ' * 8, 'ok': i % 2 == 0} for i in range(80)]}))
    [t] = gather('course_review', ctx)
    assert len(json.dumps(t.facts, ensure_ascii=False).encode('utf-8')) <= 4096


def test_course_review_source_down(ctx, plat):
    plat.down.add('/api/bridge/courses')
    with pytest.raises(SourceDown):
        gather('course_review', ctx)


def test_course_review_checklist_down_is_source_down(ctx, plat):
    plat.down.add('/api/bridge/courses/c-pend-2/checklist')
    with pytest.raises(SourceDown):
        gather('course_review', ctx)


def test_course_review_missing_ns_helper_is_source_down(ctx):
    del ctx.ns['_platform_proxy']
    with pytest.raises(SourceDown):
        gather('course_review', ctx)


def test_course_review_validate_enum_and_shape(ctx):
    t = gather('course_review', ctx)[1]          # كل بنودها مكتملة
    v = prod('course_review').validate
    assert v({'text': 'جاهزة', 'recommend': 'publish'}, t) == {
        'text': 'جاهزة', 'recommend': 'publish', 'course_id': 'c-pend-2', 'approve_label': 'انشر الدورة'}
    assert v({'text': 'ناقص', 'recommend': 'fix_first'}, t)['approve_label'] == 'افتح الدورة'
    for bad in (None, [], 'x', {}, {'text': '', 'recommend': 'publish'}, {'text': 'a', 'recommend': 'ship'},
                {'text': 'a'}, {'text': 5, 'recommend': 'publish'}, {'text': 'ع' * 901, 'recommend': 'publish'}):
        assert v(bad, t) is None


def test_course_review_publish_downgraded_when_item_fails(ctx):
    t = gather('course_review', ctx)[0]          # بندان ناقصان
    body = prod('course_review').validate({'text': 'انشرها', 'recommend': 'publish'}, t)
    assert body['recommend'] == 'fix_first' and body['approve_label'] == 'افتح الدورة'


def test_course_review_templates(ctx):
    t1, t2 = gather('course_review', ctx)
    tpl = prod('course_review').template
    b1 = tpl(t1)
    assert b1['text'] == 'ينقصها: فيديو تعريفي مرفوع، مستوى الدورة محدّد' and b1['recommend'] == 'fix_first'
    b2 = tpl(t2)
    assert b2['text'] == 'بنود الفحص كلها مكتملة' and b2['recommend'] == 'publish'


def test_course_review_apply_publish_exact_call(ctx, plat):
    [t, _] = gather('course_review', ctx)
    plat.calls.clear()
    res = prod('course_review').apply(ctx, {'text': 'x', 'recommend': 'publish', 'course_id': 'c-pend-1'}, t)
    assert res.ok is True and res.no_reply is False
    assert plat.calls == [('POST', '/api/bridge/courses/c-pend-1/approve',
                           {'confirmed': True, 'by': 'founder@elprofessor.net'}, 'course.approve', 'c-pend-1',
                           {'payout_model': None, 'via': 'brain'})]


def test_course_review_apply_fix_first_writes_nothing(ctx, plat):
    [t, _] = gather('course_review', ctx)
    plat.calls.clear()
    res = prod('course_review').apply(ctx, {'text': 'x', 'recommend': 'fix_first'}, t)
    assert res.ok is True and res.info == {'open_course': 'c-pend-1', 'no_write': True}
    assert plat.calls == []


def test_course_review_apply_failure_modes(ctx, plat):
    [t, _] = gather('course_review', ctx)
    pub = {'text': 'x', 'recommend': 'publish'}
    plat.write_resp = Resp(422, {'error': 'المدرّب لم يوقّع الاتفاقية'})
    r = prod('course_review').apply(ctx, pub, t)
    assert (r.ok, r.no_reply, r.error) == (False, False, 'المدرّب لم يوقّع الاتفاقية')
    plat.write_resp = Resp(502, {'error': 'ما وصلناش رد', 'no_reply': True})
    r = prod('course_review').apply(ctx, pub, t)
    assert (r.ok, r.no_reply) == (False, True)
    plat.write_resp = Resp(500, {})
    assert prod('course_review').apply(ctx, pub, t).error == 'تعذّر التنفيذ الآن'


def test_course_review_prompt_hygiene(ctx):
    for t in gather('course_review', ctx):
        system, user = prod('course_review').prompt(t)
        assert system.startswith(biz._SYSTEM_AR_FALLBACK)
        assert not EMAIL_RE.search(user) and not PHONE_RE.search(user)
        assert 'ali@' not in user and 'c-pend' not in t.meta.get('slug', '')
        assert json.dumps(t.facts, ensure_ascii=False, sort_keys=True) in user
        assert 'publish' in system and 'fix_first' in system


# ------------------------------------------------------------------ market_match
def test_market_match_gather_targets(ctx, plat):
    ts = gather('market_match', ctx)
    assert [t.ref for t in ts] == ['mreq:r1']
    t = ts[0]
    assert t.meta == {'request_id': 'r1'} and t.label == 'أريد دورة في صياغة العقود'
    assert [c['id'] for c in t.facts['courses']] == ['c-live-1', 'c-live-2']       # النشطة فقط، لا المؤرشفة ولا المخفية ولا قيد المراجعة
    assert set(t.facts['request']) == {'title', 'body', 'need_kind', 'specialty'}
    assert ('GET', '/api/bridge/market/requests', {'status': 'open', 'limit': 50}, None) in plat.calls


def test_market_match_facts_have_no_pii(ctx):
    for t in gather('market_match', ctx):
        blob = json.dumps(t.facts, ensure_ascii=False)
        assert not EMAIL_RE.search(blob) and not PHONE_RE.search(blob)
        assert 'علي محمود' not in blob and 'member' not in blob
        system, user = prod('market_match').prompt(t)
        assert not EMAIL_RE.search(user) and not PHONE_RE.search(user) and 'request_id' not in user


def test_market_match_course_list_capped_at_40_and_4k(ctx):
    many = [{'id': 'id-%02d-' % i + 'x' * 30, 'title': 'عنوان دورة طويل جدا رقم %d ' % i + 'ب' * 40, 'is_active': True,
             'approval_status': 'approved'} for i in range(60)]
    ctx.ns['_platform_proxy'] = lambda m, p, params=None, json_body=None, timeout=12: Resp(200, {'courses': many})
    [t] = gather('market_match', ctx)
    assert 1 <= len(t.facts['courses']) <= 40
    assert len(json.dumps(t.facts, ensure_ascii=False).encode('utf-8')) <= 4096


def test_market_match_no_active_courses_means_nothing_to_do(ctx):
    ctx.ns['_platform_proxy'] = lambda m, p, params=None, json_body=None, timeout=12: Resp(200, {'courses': []})
    assert gather('market_match', ctx) == []


def test_market_match_source_down_each_source(ctx, plat):
    plat.down.add('/api/bridge/market/requests')
    with pytest.raises(SourceDown):
        gather('market_match', ctx)
    plat.down.clear()
    plat.down.add('/api/bridge/courses')
    with pytest.raises(SourceDown):
        gather('market_match', ctx)


def test_market_match_validate_course_must_be_in_list(ctx):
    [t] = gather('market_match', ctx)
    v = prod('market_match').validate
    ok = v({'text': 'الدورة تغطي الصياغة', 'course_id': 'c-live-1'}, t)
    assert ok == {'text': 'الدورة تغطي الصياغة', 'course_id': 'c-live-1', 'course_title': 'صياغة العقود'}
    assert v({'text': 'x', 'course_id': 'c-pend-1'}, t) is None       # خارج القائمة (قيد المراجعة)
    assert v({'text': 'x', 'course_id': 'نص'}, t) is None
    assert v({'text': 'x', 'course_id': 7}, t) is None
    assert v({'text': '', 'course_id': 'c-live-1'}, t) is None
    for bad in (None, [], 'x', {'text': 5, 'course_id': 'c-live-1'}):
        assert v(bad, t) is None


def test_market_match_null_course_signals_discard(ctx):
    [t] = gather('market_match', ctx)
    v = prod('market_match').validate
    assert v({'text': 'لا شيء يناسب', 'course_id': None}, t) == {'text': 'لا شيء يناسب', 'course_id': None}
    assert v({'text': '', 'course_id': None}, t) == {'text': 'لا توجد دورة مناسبة', 'course_id': None}
    assert v({'course_id': 'null'}, t)['course_id'] is None
    assert v({'text': 'x'}, t)['course_id'] is None


def test_market_match_apply_exact_call(ctx, plat):
    [t] = gather('market_match', ctx)
    plat.calls.clear()
    res = prod('market_match').apply(ctx, {'text': 'x', 'course_id': 'c-live-1'}, t)
    assert res.ok is True
    assert plat.calls == [('POST', '/api/bridge/market/requests/r1/annotate',
                           {'linked_course_id': 'c-live-1', 'confirmed': True, 'by': 'founder@elprofessor.net'},
                           'market.link_course', 'r1', {'course': 'c-live-1', 'via': 'brain'})]


def test_market_match_apply_without_course_is_refused(ctx, plat):
    [t] = gather('market_match', ctx)
    plat.calls.clear()
    res = prod('market_match').apply(ctx, {'text': 'x', 'course_id': None}, t)
    assert res.ok is False and res.error and plat.calls == []


def test_market_match_apply_no_reply(ctx, plat):
    [t] = gather('market_match', ctx)
    plat.write_resp = Resp(502, {'error': 'ما وصلناش رد', 'no_reply': True})
    r = prod('market_match').apply(ctx, {'text': 'x', 'course_id': 'c-live-1'}, t)
    assert r.ok is False and r.no_reply is True


# ------------------------------------------------------------------ seo_notes
def test_seo_notes_gather(ctx, plat):
    ts = gather('seo_notes', ctx)
    assert [t.ref for t in ts] == ['article:a1', 'article:a2']      # الأضعف أولًا، والسليم والمجهول المعرّف خارجًا
    assert ts[0].facts == {'title': 'مقال ضعيف', 'score': 40, 'words': 200, 'issues': SCORES['a1']['issues']}
    assert plat.calls == [('GET', '/api/bridge/articles', {'limit': 60, 'status': 'draft'}, None)]
    assert ts[0].label == 'مقال ضعيف' and ts[0].meta == {'article_id': 'a1'}


def test_seo_notes_source_down(ctx, plat):
    plat.down.add('/api/bridge/articles')
    with pytest.raises(SourceDown):
        gather('seo_notes', ctx)


def test_seo_notes_scorecard_error_skips_only_that_article(ctx):
    def sc(a):
        if a['id'] == 'a1':
            raise ValueError('boom')
        return dict(SCORES[a['id']])
    ctx.ns['_seo_scorecard'] = sc
    assert [t.ref for t in gather('seo_notes', ctx)] == ['article:a2']


def test_seo_notes_validate_lines(ctx):
    [t, _] = gather('seo_notes', ctx)
    v = prod('seo_notes').validate
    assert v({'lines': [' أضف وصفًا للمقال ', 'وسّع المقال']}, t) == {'text': 'أضف وصفًا للمقال\nوسّع المقال'}
    assert v({'lines': ['a', 'b', 'c', 'd']}, t) == {'text': 'a\nb\nc\nd'}
    for bad in (None, {}, {'lines': 'x'}, {'lines': ['one']}, {'lines': ['a'] * 5}, {'lines': ['a', '']}, {'lines': ['a', 3]},
                {'lines': ['ع' * 201, 'b']}, {'lines': ['ع' * 190] * 4}):
        assert v(bad, t) is None


def test_seo_notes_template_is_scorecard_issues(ctx):
    [t1, t2] = gather('seo_notes', ctx)
    b = prod('seo_notes').template(t1)
    assert b['text'] == 'لا يوجد وصف ميتا (meta description)\nالمقال قصير جدًا (أقل من ٣٠٠ كلمة)\nيذكر منصة منافسة (ممنوع)'
    assert '⚠' not in b['text']
    assert prod('seo_notes').template(Target(ref='article:z', label='z', facts={'issues': []})) is None


def test_seo_notes_prompt(ctx):
    [t, _] = gather('seo_notes', ctx)
    system, user = prod('seo_notes').prompt(t)
    assert system.startswith(biz._SYSTEM_AR_FALLBACK) and '"lines"' in system
    assert 'مقال ضعيف' in user and 'article_id' not in user


# ------------------------------------------------------------------ campaign_comment
def test_campaign_comment_gather(ctx):
    ts = gather('campaign_comment', ctx)
    assert [t.ref for t in ts] == ['campaign:1', 'campaign:2']        # نشطة أو متوقفة بإنفاق > 0
    assert ts[0].facts == {'name': 'حملة الخريف', 'platform': 'facebook', 'budget': 500, 'spent': 320.5, 'currency': 'USD',
                           'impressions': 12000, 'clicks': 340, 'leads': 21, 'conversions': 4, 'revenue_attributed': 900}
    assert ts[0].meta == {'campaign_id': 1}


def test_campaign_comment_source_down(ctx):
    class Broken:
        @property
        def query(self):
            raise RuntimeError('db')
    ctx.ns['Campaign'] = Broken()
    with pytest.raises(SourceDown):
        gather('campaign_comment', ctx)
    del ctx.ns['Campaign']
    with pytest.raises(SourceDown):
        gather('campaign_comment', ctx)


def test_campaign_comment_validate_and_prompt(ctx):
    [t, _] = gather('campaign_comment', ctx)
    v = prod('campaign_comment').validate
    assert v({'text': ' الإنفاق قريب من الميزانية '}, t) == {'text': 'الإنفاق قريب من الميزانية'}
    for bad in (None, {}, {'text': ''}, {'text': 3}, {'text': 'ع' * 501}):
        assert v(bad, t) is None
    system, user = prod('campaign_comment').prompt(t)
    assert system.startswith(biz._SYSTEM_AR_FALLBACK) and 'campaign_id' not in user
    assert prod('campaign_comment').template is None


# ------------------------------------------------------------------ weekly_read
def test_weekly_read_gather(ctx):
    [t] = gather('weekly_read', ctx)
    assert t.ref == 'week:2026-11-08' and t.label.startswith('قراءة الأسبوع')
    assert t.facts['week'] == '٨ نوفمبر إلى ١٤ نوفمبر'
    assert t.facts['lines'][0].startswith('٨ نوفمبر إلى ١٤ نوفمبر، مقارنة') and 'تقرير الأسبوع' not in t.facts['lines']
    assert all(t.facts['lines']) and 'الحسابات الجديدة: ٤٢' in t.facts['lines']
    assert t.meta == {'start': '2026-11-08', 'end': '2026-11-14'}


def test_weekly_read_source_down(ctx, monkeypatch):
    monkeypatch.setattr(biz, '_load_weekly_for', lambda: (lambda G, w=None: (None, 'اختر أسبوعًا اكتمل')))
    with pytest.raises(SourceDown):
        gather('weekly_read', ctx)
    monkeypatch.setattr(biz, '_load_weekly_for', lambda: (_ for _ in ()).throw(RuntimeError('x')))
    with pytest.raises(SourceDown):
        gather('weekly_read', ctx)
    dead = dict(WEEK_PAYLOAD, sources={'money': 'failed', 'users': 'failed'})
    monkeypatch.setattr(biz, '_load_weekly_for', lambda: (lambda G, w=None: (dead, None)))
    with pytest.raises(SourceDown):
        gather('weekly_read', ctx)


def test_weekly_read_passes_ns_as_G(ctx, monkeypatch):
    seen = []
    monkeypatch.setattr(biz, '_load_weekly_for', lambda: (lambda G, w=None: seen.append((G, w)) or (json.loads(json.dumps(WEEK_PAYLOAD)), None)))
    gather('weekly_read', ctx)
    assert seen == [(ctx.ns, None)]


def test_weekly_read_validate_prompt(ctx):
    [t] = gather('weekly_read', ctx)
    assert prod('weekly_read').validate({'text': 'أسبوع هادئ'}, t) == {'text': 'أسبوع هادئ'}
    assert prod('weekly_read').validate({'text': 'ع' * 551}, t) is None
    system, user = prod('weekly_read').prompt(t)
    assert system.startswith(biz._SYSTEM_AR_FALLBACK) and 'الحسابات الجديدة' in user


# ------------------------------------------------------------------ forecast_comment
def test_forecast_comment_gather(ctx):
    [t] = gather('forecast_comment', ctx)
    assert t.ref == 'forecast:2026-11' and t.meta == {'months': ['2026-11', '2026-12', '2027-01']}
    assert [m['month'] for m in t.facts['months']] == ['2026-11', '2026-12', '2027-01']
    assert t.facts['months'][0] == {'month': '2026-11', 'revenue_egp': 50000, 'expenses_egp': 37000, 'target_courses': 2, 'target_students': 100}
    assert t.facts['financials'] == {'total_revenue_egp': 120000, 'total_expenses_egp': 80000, 'net_profit_egp': 40000, 'payout_cost_egp': 5000}
    assert t.facts['cashflow'] == {'balance_egp': 55000}


def test_forecast_comment_year_rollover_and_no_rows(ctx):
    assert biz._months_from(datetime.datetime(2026, 12, 5), 3) == ['2026-12', '2027-01', '2027-02']
    ctx.ns['ForecastMonth'] = Rows([Row(month='2026-01')])
    assert gather('forecast_comment', ctx) == []


def test_forecast_comment_no_customer_names(ctx):
    [t] = gather('forecast_comment', ctx)
    blob = json.dumps(t.facts, ensure_ascii=False)
    assert 'عميل سري' not in blob and 'سري' not in blob and 'top_clients' not in blob and 'transactions' not in blob
    system, user = prod('forecast_comment').prompt(t)
    assert 'سري' not in user and len(blob.encode('utf-8')) <= 4096


def test_forecast_comment_source_down(ctx):
    def boom():
        raise RuntimeError('db')
    ctx.ns['generate_ai_snapshot'] = boom
    with pytest.raises(SourceDown):
        gather('forecast_comment', ctx)
    del ctx.ns['generate_ai_snapshot']
    with pytest.raises(SourceDown):
        gather('forecast_comment', ctx)
    del ctx.ns['ForecastMonth']
    with pytest.raises(SourceDown):
        gather('forecast_comment', ctx)


def test_forecast_comment_validate(ctx):
    [t] = gather('forecast_comment', ctx)
    assert prod('forecast_comment').validate({'text': 'الإيراد المتوقع أعلى'}, t) == {'text': 'الإيراد المتوقع أعلى'}
    assert prod('forecast_comment').validate({'text': ''}, t) is None


# ------------------------------------------------------------------ مشتركات
def test_notes_have_no_apply_and_alone_ones_have_tags():
    for pid in ('seo_notes', 'campaign_comment', 'weekly_read', 'forecast_comment'):
        assert prod(pid).apply is None and prod(pid).tag


def test_system_prompt_uses_engine_when_importable(monkeypatch):
    fake = types.ModuleType('brain2.engine')
    fake.SYSTEM_AR = 'مقدمة المحرّك'
    monkeypatch.setitem(sys.modules, 'brain2.engine', fake)
    system, _ = prod('seo_notes').prompt(Target(ref='article:1', label='x', facts={'title': 'x', 'issues': []}))
    assert system.startswith('مقدمة المحرّك')


def test_system_prompt_falls_back_without_engine(monkeypatch):
    monkeypatch.setitem(sys.modules, 'brain2.engine', None)        # الاستيراد يفشل
    assert biz._system_ar() == biz._SYSTEM_AR_FALLBACK
    assert biz._SYSTEM_AR_FALLBACK.startswith('اكتب بالعربية الفصحى البسيطة، بصيغة محايدة')
    assert biz._SYSTEM_AR_FALLBACK.endswith('أعد JSON صالحًا فقط بالشكل المطلوب.')


def test_every_prompt_starts_from_preamble(ctx):
    for pid in ALL_IDS[:6]:
        for t in gather(pid, ctx):
            system, user = prod(pid).prompt(t)
            assert system.startswith(biz._SYSTEM_AR_FALLBACK) and len(system) > len(biz._SYSTEM_AR_FALLBACK)
            assert '"meta"' not in user and not EMAIL_RE.search(user) and not PHONE_RE.search(user)
            assert not any(str(v) in user for v in t.meta.values() if isinstance(v, str) and len(v) > 3 and v not in json.dumps(t.facts, ensure_ascii=False))


def test_no_network_in_module():
    src = open(biz.__file__, encoding='utf-8').read()
    assert 'import requests' not in src and 'urlopen' not in src and 'http.client' not in src and 'ai_call' not in src and '/agents/' not in src


def test_scrub_helpers():
    assert biz._scrub('كلمني على a.b@x.com أو +20 100 123 4567 أو http://x.y/z', 100) == 'كلمني على أو أو'
    assert biz._scrub('من ٢٠٢٦-١١-٠٥ حتى', 100, phones=False) == 'من ٢٠٢٦-١١-٠٥ حتى'
    assert biz._scrub(None, 10) == '' and len(biz._scrub('ع' * 50, 10)) == 10
