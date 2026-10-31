# -*- coding: utf-8 -*-
"""الجولة C2a · منتج «مسودة درس» (`course_lesson_draft`). SPEC: docs/v2/brain2/SPEC-C-courses.md «C2a».

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_brain2_lessons.py

⛔ صفر شبكة وصفر ذكاء حقيقي: المنصة جدول في الذاكرة يرد على `/api/bridge/courses2…`، ونص الذكاء المزعوم نكتبه يدويًا.
يثبّت: ما يجمعه gather (الحالات والأنواع والسقوف) · نظافة الموجّه · التحقق (الشكل والصدق والمعاينة وفشلها) · المسار والجسم بالحرف في apply.
"""
import copy
import datetime
import json
import re

import pytest

from brain2 import producers_biz as biz
from brain2.contract import Ctx, SourceDown, Target

NOW = datetime.datetime(2026, 11, 20, 9, 0, tzinfo=datetime.timezone.utc)
EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
PHONE_RE = re.compile(r'\d{8,}')


class Resp:
    def __init__(self, status=200, data=None):
        self.status, self.data = status, data if data is not None else {}


def resp_ok(r):
    return 200 <= r.status < 300


def proxy_json(r):
    return r.data if isinstance(r.data, dict) else {}


def lesson(lid, kind, state, title, **extra):
    base = {'id': lid, 'kind': kind, 'title': title, 'state': state}
    base.update(extra)
    return base


def course(cid, status, title, units, **meta):
    m = {'title': title, 'subtitle': 'مدخل عملي', 'level': 'مبتدئ', 'outcomes': ['يكتب عرضًا واضحًا', 'يختار قناة مناسبة'], 'description': 'وصف طويل لا يدخل الحقائق'}
    m.update(meta)
    return {'id': cid, 'slug': cid.lower(), 'status': status, 'meta': m, 'outline': {'units': units},
            'owner': {'email': 'trainer@secret.test', 'name': 'مدرب سري'}}


UNITS_A = [
    {'id': 'u1', 'title': 'الأساسيات', 'lessons': [
        lesson('l1', 'interactive', 'draft', 'مدخل إلى التسويق', blocks=[]),
        lesson('l2', 'interactive', 'draft', 'درس فيه كتل', blocks=[{'type': 'text', 'md': 'موجود'}]),
        lesson('l3', 'recorded', 'draft', 'نظرة على السوق', transcript=''),
        lesson('l4', 'recorded', 'ready', 'درس جاهز', transcript='نص موجود'),
        lesson('l5', 'live', 'draft', 'لقاء مباشر'),
        lesson('l6', 'recorded', 'missing_video', 'ينقصه فيديو', transcript=''),
    ]},
    {'id': 'u2', 'title': 'التطبيق', 'lessons': [
        lesson('l7', 'interactive', 'draft', 'اتصل على sara@example.com أو 01012345678', blocks=[]),
    ]},
]
COURSES = {
    'CRS_A': course('CRS_A', 'draft', 'التسويق للمكاتب', UNITS_A),
    'CRS_B': course('CRS_B', 'changes', 'عقود الشركات', [{'id': 'u1', 'title': 'البداية', 'lessons': [lesson('b1', 'recorded', 'draft', 'مقدمة العقود', transcript='')]}]),
    'CRS_PUB': course('CRS_PUB', 'published', 'منشورة', [{'id': 'u1', 'title': 'x', 'lessons': [lesson('p1', 'interactive', 'draft', 'لا يُلمس', blocks=[])]}]),
    'CRS_REV': course('CRS_REV', 'review', 'عند المراجعة', [{'id': 'u1', 'title': 'x', 'lessons': [lesson('r1', 'interactive', 'draft', 'لا يُلمس', blocks=[])]}]),
}


class Platform:
    def __init__(self):
        self.calls = []
        self.courses = copy.deepcopy(COURSES)
        self.down = set()
        self.preview = Resp(200, {'ok': True, 'preview': {}})
        self.write_resp = Resp(200, {'ok': True})

    def proxy(self, method, path, params=None, json_body=None, timeout=12):
        self.calls.append((method, path, copy.deepcopy(json_body)))
        if path in self.down:
            return Resp(502, {'error': 'x'})
        if method == 'GET' and path == '/api/bridge/courses2':
            return Resp(200, {'ok': True, 'count': len(self.courses), 'courses': [
                {'id': c['id'], 'slug': c['slug'], 'title': c['meta']['title'], 'status': c['status'], 'owner': {'email': 'trainer@secret.test'}}
                for c in self.courses.values()]})
        m = re.match(r'^/api/bridge/courses2/([^/]+)$', path)
        if method == 'GET' and m:
            c = self.courses.get(m.group(1))
            return Resp(200, {'ok': True, 'course': c}) if c else Resp(404, {'error': 'x'})
        if method == 'POST' and path.endswith('/preview'):
            return self.preview
        raise AssertionError('نداء غير متوقّع: %s %s' % (method, path))

    def v2_write(self, method, path, body, audit_action, target, meta, params=None):
        self.calls.append((method, path, copy.deepcopy(body), audit_action, target, meta))
        return self.write_resp

    def paths(self, method=None):
        return [c[1] for c in self.calls if method is None or c[0] == method]


@pytest.fixture
def plat():
    return Platform()


@pytest.fixture
def ctx(plat):
    ns = {'_platform_proxy': plat.proxy, '_v2_write': plat.v2_write, '_resp_ok': resp_ok, '_proxy_json': proxy_json,
          '_extract_json_block': lambda t: json.loads(t)}
    return Ctx(ns=ns, now=NOW, actor='founder@elprofessor.net')


P = next(p for p in biz.PRODUCERS if p.id == 'course_lesson_draft')


# ------------------------------------------------------------------ مسودات جاهزة
def good_blocks():
    return [
        {'type': 'objectives', 'items': ['تعرف فكرة العرض الواضح', 'تختار قناة مناسبة لعملك']},
        {'type': 'text', 'md': 'العرض الواضح يبدأ بمشكلة العميل لا بخدمتك.'},
        {'type': 'situation', 'text': 'مكتب صغير يريد عملاء جددًا. المدير متردد بين أكثر من قناة.', 'question': 'ماذا تفعل؟',
         'options': [{'text': 'يبدأ بقناة واحدة', 'comment': 'تركيز أفضل'}, {'text': 'يستعمل كل القنوات', 'comment': 'تشتيت للجهد'}]},
        {'type': 'decision', 'key': 'first_step', 'text': 'عليك أن تختار أول خطوة.', 'question': 'ماذا تختار؟',
         'options': [{'text': 'كتابة العرض', 'result': 'عرض أوضح', 'comment': 'خطوة سليمة'}, {'text': 'شراء إعلان', 'result': 'إنفاق مبكر', 'comment': 'مبكر قليلًا'}]},
        {'type': 'recall', 'key': 'first_step', 'follow': {'0': 'اخترت كتابة العرض أولًا.', '1': 'اخترت الإعلان أولًا.'}, 'default': 'راجع قرارك.'},
        {'type': 'summary', 'items': ['ابدأ بالعرض', 'ثم اختر القناة']},
    ]


def tgt(ctx, lid='l1'):
    return next(t for t in P.gather(ctx) if t.meta['lesson_id'] == lid)


# ------------------------------------------------------------------ السجل
def test_registry_flags_and_copy():
    assert P.listed is True and P.section == 'courses' and P.kind == 'draft'
    assert P.may_run_alone is False and P.default_mode == 'ask' and P.lock_reason
    assert P.label == 'مسودة درس' and P.tag == 'مسودة درس' and P.approve_label == 'أضف الدرس'
    assert P.per_run_cap == 3 and P.apply is not None and P.template is None
    for t in (P.label, P.sentence, P.lock_reason, P.tag, P.approve_label):
        assert 'يقوّم' not in t and not re.search(r'[A-Za-z]', t) and '⇒' not in t and not t.startswith('الذكاء')


# ------------------------------------------------------------------ gather
def test_gather_filters_statuses_kinds_and_states(ctx, plat):
    ts = P.gather(ctx)
    assert [t.ref for t in ts] == ['lesson:CRS_A:l1', 'lesson:CRS_A:l3', 'lesson:CRS_A:l7', 'lesson:CRS_B:b1']
    # الدرس الذي فيه كتل · والجاهز · والمباشر · وما ينقصه فيديو (حالته غير draft) · والدورات المنشورة/عند المراجعة: كلها خارج
    refs = {t.ref for t in ts}
    assert not refs & {'lesson:CRS_A:l2', 'lesson:CRS_A:l4', 'lesson:CRS_A:l5', 'lesson:CRS_A:l6', 'lesson:CRS_PUB:p1', 'lesson:CRS_REV:r1'}
    assert plat.paths('GET')[0] == '/api/bridge/courses2'
    assert set(plat.paths('GET')[1:]) == {'/api/bridge/courses2/CRS_A', '/api/bridge/courses2/CRS_B'}
    assert all(c[0] == 'GET' for c in plat.calls), 'القراءة فقط'


def test_gather_target_shape_and_privacy(ctx):
    ts = P.gather(ctx)
    t = ts[0]
    assert t.meta == {'course_id': 'CRS_A', 'lesson_id': 'l1', 'kind': 'interactive'}
    assert t.label == 'مسودة درس: مدخل إلى التسويق'
    f = t.facts
    assert set(f) == {'course', 'unit', 'lesson', 'units'}
    assert f['course'] == {'title': 'التسويق للمكاتب', 'subtitle': 'مدخل عملي', 'level': 'مبتدئ', 'outcomes': ['يكتب عرضًا واضحًا', 'يختار قناة مناسبة']}
    assert f['unit'] == {'title': 'الأساسيات'} and f['lesson'] == {'id': 'l1', 'title': 'مدخل إلى التسويق', 'kind': 'interactive'}
    assert f['units'][0]['title'] == 'الأساسيات' and 'مدخل إلى التسويق' in f['units'][0]['lessons']
    blob = json.dumps(ts[0].facts, ensure_ascii=False)
    for t in ts:
        blob = json.dumps(t.facts, ensure_ascii=False)
        assert len(blob.encode('utf-8')) <= 4096
        assert not EMAIL_RE.search(blob) and not PHONE_RE.search(blob) and 'secret' not in blob and 'سري' not in blob
        assert 'وصف طويل' not in blob
    # عنوان درس فيه بريد وهاتف يُنظَّف
    l7 = next(t for t in ts if t.meta['lesson_id'] == 'l7')
    assert '@' not in l7.facts['lesson']['title'] and '0101' not in l7.facts['lesson']['title']
    assert [t.meta['kind'] for t in ts] == ['interactive', 'recorded', 'interactive', 'recorded']


def test_gather_is_bounded(ctx, plat):
    big = [{'id': 'u1', 'title': 'وحدة', 'lessons': [lesson('x%d' % i, 'interactive', 'draft', 'درس %d' % i, blocks=[]) for i in range(40)]}]
    plat.courses = {'CRS_BIG': course('CRS_BIG', 'draft', 'كبيرة', big)}
    assert len(P.gather(ctx)) == 12
    for t in P.gather(ctx):
        assert len(json.dumps(t.facts, ensure_ascii=False).encode('utf-8')) <= 4096


def test_gather_source_down_and_partial(ctx, plat):
    plat.down = {'/api/bridge/courses2'}
    with pytest.raises(SourceDown):
        P.gather(ctx)
    plat.down = {'/api/bridge/courses2/CRS_A'}              # دورة واحدة تفشل: الباقي يعمل
    assert [t.ref for t in P.gather(ctx)] == ['lesson:CRS_B:b1']
    plat.down = {'/api/bridge/courses2/CRS_A', '/api/bridge/courses2/CRS_B'}
    with pytest.raises(SourceDown):                          # كلها فشلت: ليس «لا شيء ناقص»
        P.gather(ctx)


def test_gather_empty_when_nothing_is_missing(ctx, plat):
    plat.courses = {'CRS_PUB': COURSES['CRS_PUB']}
    assert P.gather(ctx) == []


# ------------------------------------------------------------------ الموجّه
def test_prompt_hygiene_interactive(ctx):
    system, user = P.prompt(tgt(ctx, 'l1'))
    from brain2.engine import SYSTEM_AR
    assert SYSTEM_AR in system
    for ty in ('objectives', 'text', 'situation', 'decision', 'recall', 'quiz', 'summary', 'example', 'cards'):
        assert '"type":"%s"' % ty in system
    for banned in ('"type":"order"', '"type":"match"', '"type":"video"', '"type":"ai_station"'):
        assert banned not in system
    for field in ('"md"', '"items"', '"options"', '"comment"', '"result"', '"follow"', '"default"', '"feedback"', '"front"', '"back"', '"prompt"'):
        assert field in system
    assert '٤ إلى ٧' in system and 'blocks' in system
    assert 'يقوّم' not in system and 'يقوّم' not in user
    assert 'مدخل إلى التسويق' in user and 'الحقائق' in user
    assert not EMAIL_RE.search(system + user) and not PHONE_RE.search(system + user)
    assert 'CRS_A' not in user and 'trainer' not in user      # meta لا يُرسَل


def test_prompt_hygiene_recorded(ctx):
    system, user = P.prompt(tgt(ctx, 'l3'))
    assert '"summary"' in system and '"transcript"' in system and '"blocks"' not in system
    assert 'نظرة على السوق' in user and 'CRS_A' not in user


# ------------------------------------------------------------------ validate
def test_validate_interactive_ok_and_preview_call(ctx, plat):
    t = tgt(ctx, 'l1')
    plat.calls.clear()
    body = P.validate({'blocks': good_blocks()}, t)
    assert body is not None
    assert set(body) == {'text', 'fields', 'lesson'}
    assert [b['type'] for b in body['lesson']['blocks']] == ['objectives', 'text', 'situation', 'decision', 'recall', 'summary']
    assert body['text'].startswith('مسودة لدرس «مدخل إلى التسويق»') and not re.search(r'[A-Za-z0-9٠-٩]', body['text'].replace('مدخل إلى التسويق', ''))
    assert body['fields']['title'] == 'مدخل إلى التسويق' and len(body['fields']['body']) <= 900 and 'أهداف' in body['fields']['body']
    # المعاينة: نداء واحد بالمسار والجسم بالحرف، بلا confirmed ولا by (لا كتابة)
    assert plat.calls == [('POST', '/api/bridge/courses2/CRS_A/lessons/l1/preview', {'blocks': body['lesson']['blocks']})]
    assert 'confirmed' not in plat.calls[0][2] and 'by' not in plat.calls[0][2]


def test_validate_passes_engine_checks(ctx):
    """نفس بوابة المحرّك: JSON ⇒ validate ⇒ check_body على text وfields."""
    from brain2 import engine
    t = tgt(ctx, 'l1')
    body, err = engine._parse(ctx.ns, P, t, json.dumps({'blocks': good_blocks()}, ensure_ascii=False))
    assert err is None and body['lesson']['blocks'][0]['type'] == 'objectives'
    assert engine.check_body(body, t.facts, 'draft') is None


def test_validate_recorded_ok(ctx, plat):
    t = tgt(ctx, 'l3')
    transcript = 'مرحبًا بكم في هذا الدرس. سنتعرف معًا على السوق الذي تعمل فيه مكاتب المحاماة، وكيف يبحث العملاء عن الخدمة. ' * 2
    plat.calls.clear()
    body = P.validate({'summary': ['السوق يتغير', 'العميل يبحث أولًا'], 'transcript': transcript}, t)
    assert body['lesson'] == {'summary': ['السوق يتغير', 'العميل يبحث أولًا'], 'transcript': transcript.strip()}
    assert plat.calls[0][1] == '/api/bridge/courses2/CRS_A/lessons/l3/preview'
    assert 'ملخص' in body['text'] and 'نص مفرّغ' in body['text']


@pytest.mark.parametrize('mutate', [
    lambda b: b[:3],                                                  # أقل من ٤ كتل
    lambda b: b + b[:2],                                              # أكثر من ٧
    lambda b: b + [{'type': 'order', 'items': ['a', 'b', 'c']}],      # نوع غير مسموح
    lambda b: [dict(x, type='video') if x['type'] == 'text' else x for x in b],
    lambda b: [dict(x, options=x['options'][:1]) if x['type'] == 'situation' else x for x in b],     # اختيار واحد
    lambda b: [dict(x, options=x['options'] * 2) if x['type'] == 'decision' else x for x in b],      # أربعة قرارات
    lambda b: [dict(x, key='nope') if x['type'] == 'recall' else x for x in b],                      # مفتاح لا يطابق قرارًا
    lambda b: [dict(x, items=[]) if x['type'] == 'summary' else x for x in b],
    lambda b: [dict(x, items=['فقط واحد']) if x['type'] == 'objectives' else x for x in b],
    lambda b: [dict(x, md='   ') if x['type'] == 'text' else x for x in b],
    lambda b: ['نص خام'] + b[1:],
])
def test_validate_rejects_bad_shapes(ctx, plat, mutate):
    t = tgt(ctx, 'l1')
    plat.calls.clear()
    assert P.validate({'blocks': mutate(good_blocks())}, t) is None
    assert plat.calls == [], 'لا معاينة قبل سلامة الشكل'


def test_validate_rejects_non_dict_and_missing_keys(ctx):
    t = tgt(ctx, 'l1')
    for raw in (None, [], 'x', {}, {'blocks': 'x'}, {'summary': ['a']}):
        assert P.validate(raw, t) is None
    r = tgt(ctx, 'l3')
    assert P.validate({'blocks': good_blocks()}, r) is None
    assert P.validate({'summary': [], 'transcript': 'ن' * 300}, r) is None
    assert P.validate({'summary': ['أ'], 'transcript': 'قصير'}, r) is None
    assert P.validate({'summary': ['أ', 'ب', 'ج', 'د'], 'transcript': 'ن ' * 200}, r) is None
    assert P.validate({'summary': ['أ'], 'transcript': 'ن ' * 2500}, r) is None


def test_validate_quiz_cards_example(ctx, plat):
    t = tgt(ctx, 'l1')
    blocks = good_blocks()[:2] + [
        {'type': 'quiz', 'question': 'ما أول خطوة؟', 'options': [{'text': 'العرض', 'ok': True, 'feedback': 'صحيح'}, {'text': 'الإعلان', 'ok': False, 'feedback': ''}]},
        {'type': 'cards', 'prompt': 'اقلب', 'cards': [{'front': 'عرض', 'back': 'وعد واضح'}, {'front': 'قناة', 'back': 'مكان الوصول'}, {'front': 'عميل', 'back': 'صاحب المشكلة'}]},
        {'type': 'example', 'title': 'مثال', 'text': 'مكتب يبدأ برسالة واحدة.'},
    ]
    body = P.validate({'blocks': blocks}, t)
    assert body and [b['type'] for b in body['lesson']['blocks']][2:] == ['quiz', 'cards', 'example']
    bad_quiz = copy.deepcopy(blocks)
    bad_quiz[2]['options'][0]['ok'] = False                         # لا خيار صحيح
    assert P.validate({'blocks': bad_quiz}, t) is None
    bad_cards = copy.deepcopy(blocks)
    bad_cards[3]['cards'] = bad_cards[3]['cards'][:2]               # أقل من ٣ كروت
    assert P.validate({'blocks': bad_cards}, t) is None
    bad_cards = copy.deepcopy(blocks)
    bad_cards[3]['cards'][0]['front'] = 'ك' * 41                    # الوجه يُقصّ إلى ٤٠ فيبقى صالحًا
    ok = P.validate({'blocks': bad_cards}, t)
    assert ok and len(ok['lesson']['blocks'][3]['cards'][0]['front']) == 40


def test_validate_sanitizes_platform_breaking_characters(ctx):
    t = tgt(ctx, 'l1')
    blocks = good_blocks()
    blocks[2]['options'][0]['text'] = 'يبدأ | بقناة\nواحدة'
    blocks[2]['options'][0]['comment'] = 'تركيز — أفضل'
    blocks[1]['md'] = ':: كتلة جديدة مخفية\nسطر ثانٍ'
    blocks[3]['key'] = 'Bad Key!'
    blocks[4]['key'] = 'x'
    body = P.validate({'blocks': blocks}, t)
    assert body is None                                              # المفتاح غير الصالح استُبدل فسقط الاسترجاع
    blocks[4]['key'] = 'decision_1'
    body = P.validate({'blocks': blocks}, t)
    assert body
    opt = body['lesson']['blocks'][2]['options'][0]
    assert '|' not in opt['text'] and '\n' not in opt['text'] and '—' not in opt['comment']
    assert not body['lesson']['blocks'][1]['md'].lstrip().startswith(':')
    assert body['lesson']['blocks'][3]['key'] == 'decision_1'


@pytest.mark.parametrize('mutate,why', [
    (lambda b: b[1].update(md='العرض يخدم 500 عميل'), 'رقم من خارج الحقائق'),
    (lambda b: b[1].update(md='استعمل Google للتسويق'), 'كلمة لاتينية'),
    (lambda b: b[1].update(md='راسلنا على help@brand.com'), 'بريد'),
    (lambda b: b[1].update(md='الطالب يقوّم عمله'), 'لفظ ممنوع'),
    (lambda b: b[2]['options'][0].update(comment='اتصل بنا 01012345678'), 'هاتف'),
    (lambda b: b[5].update(items=['١٢٣ مجرد رقم', 'ثانٍ']), 'رقم هندي'),
])
def test_validate_honesty_failures(ctx, plat, mutate, why):
    t = tgt(ctx, 'l1')
    blocks = good_blocks()
    mutate(blocks)
    plat.calls.clear()
    assert P.validate({'blocks': blocks}, t) is None, why
    assert plat.calls == [], 'الصدق قبل المعاينة'


def test_validate_honest_when_value_is_in_facts(ctx, plat):
    plat.courses['CRS_A']['meta']['title'] = 'SEO للمكاتب'
    t = tgt(ctx, 'l1')
    blocks = good_blocks()
    blocks[1]['md'] = 'درس عن SEO للمكاتب.'
    assert P.validate({'blocks': blocks}, t) is not None


def test_preview_rejection_marks_failed_with_platform_detail(ctx, plat, caplog):
    t = tgt(ctx, 'l1')
    detail = 'المحتوى التفاعلي فيه أخطاء — الدرس «تفاعلي»: ::موقف لازم يكون فيه من 2 لـ3 اختيارات — الموجود 1'
    plat.preview = Resp(400, {'error': detail})
    assert P.validate({'blocks': good_blocks()}, t) is None
    assert biz.preview_detail(t.ref) == detail
    # والمحرّك يحوّل None إلى صف failed
    from brain2 import engine
    body, err = engine._parse(ctx.ns, P, t, json.dumps({'blocks': good_blocks()}, ensure_ascii=False))
    assert body is None and err == 'invalid'


def test_preview_unavailable_is_not_a_pass(ctx, plat):
    t = tgt(ctx, 'l1')
    for resp in (Resp(502, {'error': 'x'}), Resp(404, {'error': 'x'}), Resp(503, {})):
        plat.preview = resp
        assert P.validate({'blocks': good_blocks()}, t) is None
    plat.preview = Resp(200, {})
    biz._RUN['ns'] = None                                            # بلا مرجع ns: لا نعرض مسودة لم تُتحقَّق
    assert P.validate({'blocks': good_blocks()}, t) is None


def test_preview_exception_is_not_a_pass(ctx, plat):
    t = tgt(ctx, 'l1')

    def boom(*a, **k):
        raise RuntimeError('network')
    ctx.ns['_platform_proxy'] = boom
    assert P.validate({'blocks': good_blocks()}, t) is None


# ------------------------------------------------------------------ apply
def drafted(ctx, lid='l1'):
    t = tgt(ctx, lid)
    if t.meta['kind'] == 'interactive':
        return t, P.validate({'blocks': good_blocks()}, t)
    return t, P.validate({'summary': ['السوق يتغير'], 'transcript': 'مرحبًا بكم في هذا الدرس. ' * 12}, t)


def test_apply_puts_exact_path_and_body_interactive(ctx, plat):
    t, body = drafted(ctx)
    plat.calls.clear()
    res = P.apply(ctx, body, t)
    assert res.ok is True and res.info == {'course_id': 'CRS_A', 'lesson_id': 'l1'}
    writes = [c for c in plat.calls if c[0] != 'GET']
    assert len(writes) == 1
    method, path, payload, audit, target, meta = writes[0]
    assert (method, path) == ('PUT', '/api/bridge/courses2/CRS_A/lessons/l1')
    assert payload == {'blocks': body['lesson']['blocks'], 'confirmed': True, 'by': 'founder@elprofessor.net'}
    assert audit == 'course.lesson_brain' and target == 'l1' and meta == {'course': 'CRS_A', 'via': 'brain'}


def test_apply_puts_exact_body_recorded(ctx, plat):
    t, body = drafted(ctx, 'l3')
    plat.calls.clear()
    assert P.apply(ctx, body, t).ok is True
    (w,) = [c for c in plat.calls if c[0] != 'GET']
    assert w[1] == '/api/bridge/courses2/CRS_A/lessons/l3'
    assert w[2] == {'summary': ['السوق يتغير'], 'transcript': body['lesson']['transcript'], 'confirmed': True, 'by': 'founder@elprofessor.net'}


def test_apply_edit_of_summary_text_never_reaches_the_lesson(ctx, plat):
    t, body = drafted(ctx)
    body = dict(body, text='نص معدّل من المؤسس')
    plat.calls.clear()
    P.apply(ctx, body, t)
    (w,) = [c for c in plat.calls if c[0] != 'GET']
    assert set(w[2]) == {'blocks', 'confirmed', 'by'}


def test_apply_refuses_when_lesson_changed_meanwhile(ctx, plat):
    t, body = drafted(ctx)
    plat.courses['CRS_A']['outline']['units'][0]['lessons'][0]['blocks'] = [{'type': 'text', 'md': 'كتبها المدرب'}]
    plat.courses['CRS_A']['outline']['units'][0]['lessons'][0]['state'] = 'ready'
    plat.calls.clear()
    res = P.apply(ctx, body, t)
    assert res.ok is False and 'تغيّر الدرس' in res.error and res.no_reply is False
    assert [c for c in plat.calls if c[0] != 'GET'] == []


def test_apply_refuses_when_lesson_gone_or_unreadable(ctx, plat):
    t, body = drafted(ctx)
    plat.down = {'/api/bridge/courses2/CRS_A'}
    plat.calls.clear()
    res = P.apply(ctx, body, t)
    assert res.ok is False and 'تعذّر التأكد' in res.error
    assert [c for c in plat.calls if c[0] != 'GET'] == []
    plat.down = set()
    plat.courses['CRS_A']['outline']['units'][0]['lessons'].pop(0)
    assert 'تغيّر الدرس' in P.apply(ctx, body, t).error


def test_apply_refuses_without_draft_or_ids(ctx, plat):
    t, body = drafted(ctx)
    plat.calls.clear()
    assert P.apply(ctx, {'text': 'x'}, t).ok is False
    assert P.apply(ctx, body, Target(ref='x', label='x', facts={}, meta={})).ok is False
    assert plat.calls == []


def test_apply_platform_errors(ctx, plat):
    t, body = drafted(ctx)
    plat.write_resp = Resp(400, {'error': 'المحتوى التفاعلي فيه أخطاء'})
    res = P.apply(ctx, body, t)
    assert res.ok is False and res.error == 'المحتوى التفاعلي فيه أخطاء' and res.no_reply is False
    plat.write_resp = Resp(502, {'error': 'ما وصلناش رد', 'no_reply': True})
    res = P.apply(ctx, body, t)
    assert res.ok is False and res.no_reply is True


def test_apply_via_engine_item_shape(ctx, plat):
    """البطاقة تُخزَّن بجسم فيه lesson ثم يُعاد تحميلها من JSON: الاعتماد يعمل على النسخة المحمّلة."""
    t, body = drafted(ctx)
    reloaded = json.loads(json.dumps(body, ensure_ascii=False))
    t2 = Target(ref=t.ref, label=t.label, facts=json.loads(json.dumps(t.facts, ensure_ascii=False)), meta=json.loads(json.dumps(t.meta)))
    plat.calls.clear()
    assert P.apply(ctx, reloaded, t2).ok is True
