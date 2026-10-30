# -*- coding: utf-8 -*-
"""قسم «المحتوى» بالشكل الجديد (الجولة الأخيرة): خط النشر · المقالات · الموضوعات · الأخبار · التعليقات · دليل الاستخدام.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_v2s_content.py

⛔ صفر شبكة حقيقية: المنصة نداء `requests.request` مبدَّل بدالة تسجّل وترد من الذاكرة، وأي عنوان برّه `https://platform.test` يوقّع الاختبار.
المنطق النقي (الأعمدة · الحقائق · الزرّ الأساسي · الشرائح) بيتشغّل في node على v2-logic.js، و`dashboard-api.js` جوه node:vm بـfetch من الذاكرة.

اللي بيثبّته: الخريطة والتبويبات والروابط القديمة · لوحة خط النشر (كل نوع في عموده · الترتيب · نافذة الأسبوع بتاريخ القرار الحقيقي · المصدر الفاشل
«+» أو «غير متاح بعد» لا صفر) · الحقائق وتطابق العنوان بالتساوي فقط · الزرّ الأساسي (التعليق غير المحسوم «افتح واقرأ» أبدًا) · حالة صفحات
محركات البحث وجملة النشر · شرائح الموضوعات = قاعدة topicTabOf القديمة · حارس النصوص (لا «يقوّم»/AI/SEO…) · الكتابة عبر دوال EP الموجودة فقط ·
المحمّلات الخمسة وكتم التوست وسؤال isOpen · بطاقة المربّع · البروكسيات الجديدة (أدمن بس · confirmed · no-store · بلا نداء منصة للنظرة) ·
عقد الـCMS ما اتغيّرش (سبب prerender وشكل serialize_article وprerender.py).
"""
import copy
import datetime
import json
import os
import re
import subprocess
import sys

import jwt
import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app, db, User, AuditLog, Article  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
DC = os.path.join(ROOT, 'dashboard-cloud')
PLATFORM = 'https://platform.test'
SECRET = 'test-metrics-secret'
NODE = v2_node.NODE
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
BASE_COMMIT = '7d1aa83'          # آخر نقطة من dash-v2-d3 قبل هذا الفرع


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


JS = _read('dashboard-cloud', 'v2s', 'content.js')
CSS = _read('dashboard-cloud', 'v2s', 'content.css')
LOGIC = _read('dashboard-cloud', 'v2-logic.js')
API_JS = _read('dashboard-cloud', 'dashboard-api.js')
HTML = _read('dashboard-cloud', 'index.html')
HOME = _read('dashboard-cloud', 'v2-home.js')


def _block():
    a = LOGIC.index('// ===== v2s:content =====')
    return LOGIC[a:LOGIC.index('// ===== /v2s:content =====')]


def _logic(fn, *args):
    return v2_node.logic(fn, *args)


def _node(js):
    script = "const L=require(%s);\n%s" % (json.dumps(os.path.join(DC, 'v2-logic.js')), js)
    p = subprocess.run([NODE, '-e', script], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-1500:]
    return json.loads(p.stdout)


NOW = int(datetime.datetime(2026, 10, 30, 12, 0, tzinfo=datetime.timezone.utc).timestamp() * 1000)


def ago(h):
    return datetime.datetime.fromtimestamp((NOW - h * 3600e3) / 1000.0, tz=datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def ms_ago(h):
    return int(NOW - h * 3600e3)


# ====================================================================== ١) الخريطة والروابط

EXPECTED_TABS = [['pipeline', 'خط النشر', 'topics'], ['articles', 'المقالات', 'topics'], ['topics', 'الموضوعات', 'topics'],
                 ['news', 'الأخبار', 'topics'], ['comments', 'التعليقات', 'topics'], ['tutorials', 'دليل الاستخدام', 'topics']]


@needs_node
def test_the_section_has_six_tabs_all_on_the_old_module():
    got = _node("const s=L.sectionByKey('content');console.log(JSON.stringify({d:s.desc,t:s.tabs.map(t=>[t.key,t.label,t.mod]),st:s.tabs.map(t=>t.st)}))")
    assert got['t'] == EXPECTED_TABS
    assert got['d'] == 'المقالات والموضوعات والأخبار والتعليقات ودليل الاستخدام'
    assert [s['topicsTab'] for s in got['st']] == ['pipeline', 'articles', 'pending', 'news', 'comments', 'tutorials']


@needs_node
def test_every_tab_recognises_itself_and_every_legacy_state_lands_right():
    res = _node("""const out=[];L.sectionByKey('content').tabs.forEach(t=>{const m=L.sectionFor(t.mod,t.st);out.push([t.key,m.section,m.tab]);});console.log(JSON.stringify(out))""")
    for key, sec, tab in res:
        assert (sec, tab) == ('content', key), key
    legacy = {'pending': 'topics', 'ideas': 'topics', 'incoming': 'topics', 'working': 'topics', 'board': 'topics', 'rejected': 'topics', 'news': 'news',
              'articles': 'articles', 'blog': 'articles', 'auto': 'articles', 'comments': 'comments', 'tutorials': 'tutorials', 'pipeline': 'pipeline'}
    got = _node("const ks=%s;console.log(JSON.stringify(ks.map(k=>{const m=L.sectionFor('topics',{topicsTab:k});return [k,m.section,m.tab,L.v2ContentTabFor(k)];})))" % json.dumps(list(legacy)))
    for k, sec, tab, tf in got:
        assert (sec, tab, tf) == ('content', legacy[k], legacy[k]), k
    assert _logic('v2ContentTabFor', 'nonsense') == 'pipeline' and _logic('v2ContentTabFor', '') == 'pipeline'


@needs_node
def test_bare_old_links_open_the_front_door_and_tutorials_alias_lands():
    r = _node("console.log(JSON.stringify([L.routeFor('#topics',{}),L.routeFor('topics',{}),L.routeFor('#tutorials',{}),L.sectionFor('tutorials'),L.routeFor('#s/content/news',{})]))")
    assert (r[0]['section'], r[0]['tab'], r[0]['st']) == ('content', 'pipeline', {'topicsTab': 'pipeline'}) and r[1]['tab'] == 'pipeline'
    assert (r[2]['section'], r[2]['tab']) == ('content', 'tutorials') and (r[3]['section'], r[3]['tab']) == ('content', 'tutorials')
    assert (r[4]['section'], r[4]['tab']) == ('content', 'news')


# ====================================================================== ٢) لوحة خط النشر

def base_src(**over):
    src = {
        'memberTopics': [{'id': 'm1', 'title': 'موضوع عضو قديم', 'category': 'عقاري', 'segment_label': 'عقاري', 'segment_auto': True, 'at': ms_ago(60)},
                         {'id': 'm2', 'title': 'موضوع عضو أحدث', 'category': '', 'segment_label': '', 'segment_auto': True, 'at': ms_ago(5)}],
        'testimonials': [{'id': 't1', 'text': 'رأي', 'name': 'منى', 'user_email': 'm@x.test', 'course_title': 'دورة', 'rating': 5, 'consent_public': True, 'created_at': ago(20)}],
        'comments': [{'id': 'c1', 'body': 'تعليق', 'topic_title': 'موضوع', 'author_email': 'a@x.test', 'at': ms_ago(9), 'moderation': None}],
        'creative': [{'id': 'w1', 'title': 'قصيدة', 'kind': 'poem', 'creator_email': 'p@x.test', 'creator_name': 'شاعر', 'media_url': '', 'created_at': ago(30)}],
        'siteArticles': [
            {'id': 1, 'title': 'مسودة موقع', 'status': 'draft', 'by': 'فريق', 'words': 500, 'has_image': True, 'has_meta': False, 'reviewed_by': None, 'created_at': ago(3), 'published_at': None},
            {'id': 2, 'title': 'منشور اليوم', 'status': 'published', 'by': 'فريق', 'words': 400, 'has_image': True, 'has_meta': True, 'reviewed_by': 'نادية', 'created_at': ago(70), 'published_at': ago(1)},
            {'id': 3, 'title': 'منشور قديم', 'status': 'published', 'by': 'فريق', 'words': 300, 'has_image': False, 'has_meta': True, 'reviewed_by': None, 'created_at': ago(400), 'published_at': ago(24 * 9)}],
        'platformArticles': [{'id': 'pa1', 'title': 'مسودة منصة', 'category': 'feature', 'status': 'draft', 'created_at': ago(12)},
                             {'id': 'pa2', 'title': 'منشور اليوم', 'category': 'law', 'status': 'draft', 'created_at': ago(18)},
                             {'id': 'pa3', 'title': 'منشور على المنصة', 'category': 'law', 'status': 'published', 'created_at': ago(80)}],
        'topics': [{'id': 'k1', 'title': 'يُكتب', 'status': 'merged', 'source': 'human', 'ai_answer': 'نص', 'merged_article': '', 'at': ms_ago(30), 'category': 'تجاري'},
                   {'id': 'k2', 'title': 'يُكتب بلا نص', 'status': 'merged', 'source': 'idea', 'ai_answer': '', 'merged_article': '', 'at': ms_ago(10), 'category': ''},
                   {'id': 'i1', 'title': 'فكرة', 'status': 'draft', 'source': 'human', 'ai_answer': 'مسودة', 'at': ms_ago(8), 'category': 'عمل', 'segment_label': 'عمل'},
                   {'id': 'i2', 'title': 'فكرة من خبر', 'status': 'draft', 'source': 'news', 'ai_answer': '', 'at': ms_ago(4), 'category': ''},
                   {'id': 'i3', 'title': 'فكرة خبير', 'status': 'draft', 'source': 'expert', 'ai_answer': '', 'at': ms_ago(40), 'category': 'جنائي'},
                   {'id': 'b1', 'title': 'على اللوحة', 'status': 'open', 'source': 'human', 'at': ms_ago(100)},
                   {'id': 'b2', 'title': 'منشور', 'status': 'published', 'source': 'human', 'at': ms_ago(100)},
                   {'id': 'a1', 'title': 'مؤرشف', 'status': 'archived', 'source': 'human', 'at': ms_ago(100)},
                   {'id': 'r1', 'title': 'مرفوض', 'status': 'rejected', 'source': 'human', 'at': ms_ago(100)},
                   {'id': 'p1', 'title': 'معلّق في القائمة العامة', 'status': 'pending_review', 'source': 'human', 'at': ms_ago(100)}],
        'news': [{'id': 'n1', 'title': 'خبر مسودة مكتمل', 'status': 'draft', 'summary': 'ملخص', 'sources': [{'title': 'م', 'url': 'https://x.test'}], 'country': 'مصر', 'specialty': 'عمل', 'at': ms_ago(6)},
                 {'id': 'n2', 'title': 'خبر ناقص', 'status': 'draft', 'summary': '', 'sources': [], 'country': '', 'specialty': '', 'at': ms_ago(2)},
                 {'id': 'n3', 'title': 'خبر منشور هذا الأسبوع', 'status': 'published', 'summary': 'ملخص', 'sources': [], 'country': 'مصر', 'specialty': '', 'at': ms_ago(100), 'published_at': ago(48)},
                 {'id': 'n4', 'title': 'خبر منشور بلا تاريخ', 'status': 'published', 'summary': 'ملخص', 'sources': [], 'at': ms_ago(100)}],
        'approvedComments': [{'id': 'oa1', 'body': 'اعتمده إنسان', 'topic_title': 'موضوع', 'ai_moderation': {'decided_by': 'human', 'decided_at': ago(10)}},
                             {'id': 'oa2', 'body': 'اعتمده الفحص الآلي', 'topic_title': 'موضوع', 'ai_moderation': {'decided_by': 'ai', 'decided_at': ago(10)}},
                             {'id': 'oa3', 'body': 'قديم', 'topic_title': 'موضوع', 'ai_moderation': {'decided_by': 'human', 'decided_at': ago(24 * 9)}},
                             {'id': 'oa4', 'body': 'بلا تاريخ قرار', 'topic_title': 'موضوع', 'ai_moderation': {'decided_by': 'human'}}],
        'approvedTestimonials': [{'id': 'ta1', 'text': 'معتمد', 'course_title': 'دورة', 'decided_at': ago(40)}, {'id': 'ta2', 'text': 'بلا قرار', 'course_title': 'دورة'}],
        'generating': {}, 'queueTestimonials': 7,
    }
    src.update(over)
    return src


def board(src=None, now=NOW):
    return _logic('v2ContentBoard', src if src is not None else base_src(), now)


def ids(B, col):
    return [i['id'] for i in B['cols'][col]]


@needs_node
def test_board_has_four_columns_in_one_order_with_each_kind_in_its_column():
    B = board()
    assert B['order'] == ['wait', 'draft', 'idea', 'done']
    assert set(ids(B, 'wait')) == {'m:m1', 'm:m2', 't:t1', 'c:c1', 'w:w1'}
    assert set(ids(B, 'draft')) == {'s:1', 'p:pa1', 'p:pa2', 'k:k1', 'k:k2'}
    assert set(ids(B, 'idea')) == {'i:i1', 'i:i2', 'i:i3', 'n:n1', 'n:n2'}
    # المستبعد: مؤرشف · على اللوحة (open/published) · مرفوض · معلّق في القائمة العامة · منشور المنصة
    allids = ids(B, 'wait') + ids(B, 'draft') + ids(B, 'idea') + ids(B, 'done')
    for bad in ('a1', 'b1', 'b2', 'r1', 'p1', 'pa3'):
        assert not any(x.endswith(':' + bad) for x in allids), bad


@needs_node
def test_wait_order_is_member_topics_oldest_first_then_testimonials_comments_works():
    B = board()
    assert ids(B, 'wait') == ['m:m1', 'm:m2', 't:t1', 'c:c1', 'w:w1']
    assert [i['tone'] for i in B['cols']['wait']][:2] == ['late', 'wait']         # أكثر من ٤٨ ساعة ⇒ أحمر
    # الأقدم أولًا داخل النوع
    src = base_src()
    src['memberTopics'] = list(reversed(src['memberTopics']))
    assert ids(board(src), 'wait')[:2] == ['m:m1', 'm:m2']


@needs_node
def test_draft_column_puts_generating_first_then_oldest_and_idea_column_is_newest_first():
    src = base_src(generating={'k2': ms_ago(0.1)})
    B = board(src)
    assert ids(B, 'draft')[0] == 'g:k2' and 'k:k2' not in ids(B, 'draft')
    assert B['cols']['draft'][0]['status'] == 'جارٍ الكتابة…' and L_none(_logic('v2ContentSuggest', B['cols']['draft'][0]))
    rest = ids(B, 'draft')[1:]
    assert rest.index('p:pa2') < rest.index('p:pa1') < rest.index('s:1')            # الأقدم (٣٠ س > ١٨ > ١٢ > ٣) أولًا… مع k:k1 الأقدم
    assert ids(B, 'idea')[0] in ('n:n2', 'i:i2')                                      # الأحدث أولًا
    ats = [i['at'] for i in B['cols']['idea']]
    assert ats == sorted(ats, reverse=True)


def L_none(x):
    return x is None


@needs_node
def test_done_column_uses_the_real_decision_date_inside_seven_days_only():
    B = board()
    done = ids(B, 'done')
    assert set(done) == {'ds:2', 'dn:n3', 'dc:oa1', 'dt:ta1'}
    assert 'dc:oa2' not in done, 'تعليق اعتمده الفحص الآلي ليس قرار المؤسس'
    assert 'dc:oa3' not in done and 'ds:3' not in done, 'خارج السبعة أيام'
    assert 'dc:oa4' not in done and 'dt:ta2' not in done and 'dn:n4' not in done, 'بلا تاريخ قرار ⇒ لا يُخمَّن من تاريخ آخر'
    ats = [i['at'] for i in B['cols']['done']]
    assert ats == sorted(ats, reverse=True)
    assert B['top']['today'] == 1 and B['top']['week'] == 1


@needs_node
def test_today_and_week_counts_follow_the_fixed_clock():
    src = base_src()
    src['siteArticles'] = [dict(a) for a in src['siteArticles']]
    src['siteArticles'][2]['published_at'] = ago(24 * 3)
    B = board(src)
    assert B['top']['week'] == 2 and B['top']['today'] == 1
    assert board(base_src(siteArticles=None))['top']['today'] is None


@needs_node
def test_a_failed_source_marks_the_count_partial_and_never_becomes_zero():
    B = board(base_src(comments=None, creative=None))
    assert B['partial']['wait'] is True and B['counts']['wait'] == 3 and B['failed']['wait'] is False
    B2 = board(base_src(siteArticles=None))
    assert B2['partial']['draft'] and B2['partial']['done'] and B2['counts']['done'] is not None
    # كل مصادر العمود فاشلة ⇒ null (غير متاح بعد) لا ٠
    B3 = board(base_src(memberTopics=None, testimonials=None, comments=None, creative=None, queueTestimonials=None))
    assert B3['counts']['wait'] is None and B3['failed']['wait'] is True and B3['partial']['wait'] is False
    # تحميل ⇒ undefined (يُحذف من JSON) ⇒ لا يُحسب صفرًا ولا فشلًا
    src = base_src()
    for k in ('memberTopics', 'testimonials', 'comments', 'creative'):
        del src[k]
    B4 = board(src)
    assert B4['counts']['wait'] is None and B4['loading']['wait'] is True and B4['failed']['wait'] is False


@needs_node
def test_testimonials_count_card_comes_from_the_queue_when_their_list_failed():
    B = board(base_src(testimonials=None, queueTestimonials=7))
    card = [i for i in B['cols']['wait'] if i['kind'] == 'testimonialCount']
    assert len(card) == 1 and card[0]['n'] == 7 and card[0]['title'] == '٧ رأي متعلّم ينتظر المراجعة'
    assert B['partial']['wait'] is True and B['counts']['wait'] == 2 + 7 + 1 + 1, B['counts']        # عضوان + بطاقة العدد ٧ + تعليق + عمل
    assert _logic('v2ContentSuggest', card[0]) == {'label': 'أعد المحاولة', 'act': 'retry'}
    # بلا رقم في الطابور ⇒ لا بطاقة
    assert not [i for i in board(base_src(testimonials=None, queueTestimonials=None))['cols']['wait'] if i['kind'] == 'testimonialCount']


@needs_node
def test_brain_line_follows_the_four_rules_and_never_claims_nothing_waits_with_a_failed_source():
    assert board()['top']['line'] == 'ابدأ بموضوعات الأعضاء: ٢ ينتظر صاحبه قرارك، أقدمها منذ يومين.'
    assert board()['top']['rule'] == 1
    r2 = board(base_src(memberTopics=[]))['top']
    assert r2['rule'] == 2 and r2['line'] == '٣ ينتظر قرارك من الأعضاء والمتعلّمين.'
    r3 = board(base_src(memberTopics=[], testimonials=[], comments=[], creative=[]))['top']
    assert r3['rule'] == 3 and r3['line'] == '١ مسودة للموقع جاهزة للقراءة.'
    empty = base_src(memberTopics=[], testimonials=[], comments=[], creative=[], siteArticles=[], platformArticles=[], topics=[], news=[], approvedComments=[], approvedTestimonials=[])
    r4 = board(empty)['top']
    assert r4['rule'] == 4 and r4['line'] == 'لا شيء ينتظر قرارك الآن.'
    failed = dict(empty, comments=None)
    rf = board(failed)['top']
    assert rf['rule'] == 0 and rf['line'] == 'بعض المصادر لم تصل، فلا أستطيع القول إن لا شيء ينتظرك.'
    # قاعدة ١ تُتخطّى لو مصدرها فشل
    assert board(base_src(memberTopics=None))['top']['rule'] == 2
    src = base_src()
    del src['comments']
    assert board(src)['top']['line'] == '…جارٍ جمع المحتوى'


@needs_node
def test_more_button_points_at_the_first_hidden_kinds_tab_or_expands_in_place():
    members = [{'id': 'm%d' % i, 'title': 'م%d' % i, 'at': ms_ago(60 - i)} for i in range(8)]
    B = board(base_src(memberTopics=members))
    assert len(B['cols']['wait']) == 8 + 1 + 1 + 1 and B['more']['wait']['n'] == 8 + 3 - 6
    assert B['more']['wait']['go'] == {'tab': 'topics', 'st': 'pending'}
    B2 = board(base_src(memberTopics=[], testimonials=[dict(base_src()['testimonials'][0], id='t%d' % i) for i in range(7)]))
    assert B2['more']['wait']['go'] is None            # شهادة ليس لها تبويب ⇒ توسيع في المكان
    drafts = [{'id': 20 + i, 'title': 'مسودة %d' % i, 'status': 'draft', 'created_at': ago(i + 1)} for i in range(8)]
    B3 = board(base_src(siteArticles=drafts))
    assert B3['more']['draft']['go']['tab'] in ('articles', 'topics')


# ====================================================================== ٣) الحقائق وتطابق العنوان

@needs_node
def test_facts_words_image_meta_reviewer_and_line():
    f = _logic('v2ContentFacts', {'title': 'عنوان', 'status': 'draft', 'words': 840, 'has_image': True, 'has_meta': False, 'reviewed_by': 'نادية'}, [])
    assert f['words'] == 840 and f['hasImage'] is True and f['hasMeta'] is False and f['reviewer'] == 'نادية' and f['dupTitle'] is False
    assert f['line'] == '٨٤٠ كلمة · بصورة · بلا وصف لمحركات البحث · راجعه نادية'
    g = _logic('v2ContentFacts', {'title': 'عنوان', 'status': 'draft', 'words': 12, 'has_image': False, 'has_meta': True, 'reviewed_by': None}, [])
    assert g['line'] == '١٢ كلمة · بلا صورة · بوصف لمحركات البحث · لم يراجعه أحد'
    h = _logic('v2ContentFacts', {'title': 'عنوان', 'status': 'draft'}, [])         # الحالة غير معروفة: لا حقائق مخترعة
    assert h['words'] is None and h['line'] == ''


@needs_node
def test_duplicate_title_is_equality_only_after_trim_and_published_never_duplicates_itself():
    pub = ['دليل الشركات الناشئة', 'عقود الإيجار']
    assert _logic('v2ContentFacts', {'title': '  دليل الشركات الناشئة ', 'status': 'draft'}, pub)['dupTitle'] is True
    assert _logic('v2ContentFacts', {'title': 'دليل الشركات', 'status': 'draft'}, pub)['dupTitle'] is False, 'عنوان يحتوي على آخر ليس تكرارًا'
    assert _logic('v2ContentFacts', {'title': 'دليل الشركات الناشئة للمبتدئين', 'status': 'draft'}, pub)['dupTitle'] is False
    assert _logic('v2ContentFacts', {'title': 'عقود الإيجار', 'status': 'published'}, pub)['dupTitle'] is False
    d = _logic('v2ContentFacts', {'title': 'عقود الإيجار', 'status': 'draft'}, pub)
    assert d['line'] == 'عنوانه مطابق لمقال منشور على الموقع'
    # مسودة المنصة المكرّرة بنفس القاعدة (من اللوحة)
    B = board(base_src())
    pa2 = [i for i in B['cols']['draft'] if i['id'] == 'p:pa2'][0]
    pa1 = [i for i in B['cols']['draft'] if i['id'] == 'p:pa1'][0]
    assert pa2['dup'] is True and pa1['dup'] is False
    assert pa2['brain'] == 'عنوانه مطابق لمقال منشور على الموقع' and pa1['brain'] == 'تظهر في صفحة المقالات على المنصة بعد النشر'


# ====================================================================== ٤) الزرّ الأساسي وحكم الفحص الآلي

@needs_node
def test_comment_verdict_states_only_what_the_platform_check_said():
    assert _logic('v2ContentCommentVerdict', {'abusive': True, 'on_topic': True}) == {'key': 'abusive', 'text': 'الفحص الآلي على المنصة: قد يحوي إساءة', 'suggest': 'reject'}
    assert _logic('v2ContentCommentVerdict', {'abusive': False, 'on_topic': False})['text'] == 'الفحص الآلي على المنصة: خارج الموضوع'
    for m in (None, {}, {'ai_checked': False}, {'abusive': False, 'on_topic': True}, {'abusive': None, 'on_topic': None}):
        v = _logic('v2ContentCommentVerdict', m)
        assert v == {'key': 'open', 'text': 'لم يحسمه الفحص الآلي', 'suggest': 'read'}, m


@needs_node
def test_suggest_labels_for_every_kind_and_an_undecided_comment_is_never_approve():
    S = lambda it: _logic('v2ContentSuggest', it)
    assert S({'kind': 'memberTopic'}) == {'label': 'اعتمد وبلّغ', 'act': 'approveMemberTopic'}
    assert S({'kind': 'testimonial'})['label'] == 'اعتمد'
    assert S({'kind': 'comment', 'moderation': None})['label'] == 'افتح واقرأ'
    assert S({'kind': 'comment', 'moderation': {'abusive': True}}) == {'label': 'ارفض', 'act': 'rejectComment'}
    assert S({'kind': 'comment', 'moderation': {'on_topic': False}})['label'] == 'ارفض'
    for m in (None, {}, {'ai_checked': False}, {'abusive': False}):
        assert S({'kind': 'comment', 'moderation': m})['label'] != 'اعتمد'
    assert S({'kind': 'creative'})['label'] == 'افتح وراجع'
    assert S({'kind': 'siteDraft', 'dup': False})['label'] == 'اقرأ وانشر' and S({'kind': 'siteDraft', 'dup': True})['label'] == 'افتح وقارن'
    assert S({'kind': 'platformDraft', 'dup': False})['label'] == 'اقرأ وانشر' and S({'kind': 'platformDraft', 'dup': True})['label'] == 'افتح وقارن'
    assert S({'kind': 'working', 'ready': True})['label'] == 'انشر على اللوحة' and S({'kind': 'working', 'ready': False})['label'] == 'افتح'
    assert S({'kind': 'idea', 'hasAnswer': True})['label'] == 'اعتمد للنقاش' and S({'kind': 'idea', 'hasAnswer': False})['label'] == 'افتح وراجع'
    assert S({'kind': 'newsDraft', 'complete': True})['label'] == 'انشر الخبر' and S({'kind': 'newsDraft', 'complete': False})['label'] == 'أكمل الخبر'
    assert S({'kind': 'generating'}) is None and S({'kind': 'doneArticle'}) is None


@needs_node
def test_ticket_lines_carry_only_facts_and_the_testimonial_consent_line_follows_the_field():
    B = board()
    T = {i['id']: i for i in B['cols']['wait']}
    assert T['m:m1']['brain'] == 'القرار يصل إلى صاحب الموضوع · الفئة: عقاري (اختيار آلي)'
    assert T['m:m2']['brain'] == 'القرار يصل إلى صاحب الموضوع · بلا فئة' and T['m:m2']['who']['text'] == 'بلا تخصص'
    assert T['t:t1']['brain'] == 'دورة · التقييم ٥ من ٥ · وافق كاتبه على النشر باسمه'
    assert T['c:c1']['brain'] == 'لم يحسمه الفحص الآلي' and T['c:c1']['who']['text'] == 'على: موضوع'
    assert T['w:w1']['brain'] == 'قصيدة · بلا رابط'
    for consent, tail in ((True, ' · وافق كاتبه على النشر باسمه'), (False, ' · لم يوافق على ذكر اسمه'), (None, '')):
        r = {'id': 't9', 'text': 'x', 'course_title': 'دورة', 'rating': None, 'created_at': ago(1)}
        if consent is not None:
            r['consent_public'] = consent
        item = board(base_src(testimonials=[r]))['cols']['wait']
        item = [i for i in item if i['id'] == 't:t9'][0]
        assert item['brain'] == 'دورة' + tail, consent               # التقييم المفقود يُحذف لا يُكتب ٠
    # لا حكم بلا حقيقة: لا «آمن» ولا «لا أحد ينتظره»
    blob = json.dumps(B, ensure_ascii=False)
    assert 'آمن' not in blob and 'لا أحد ينتظره' not in blob


# ====================================================================== ٥) صفحات محركات البحث وجملة النشر

@needs_node
def test_prerender_states_texts_and_live_flag():
    P = lambda p: _logic('v2ContentPrerender', p, NOW)
    ok = P({'state': 'ok', 'at': ago(3)})
    assert ok['text'] == 'صفحات محركات البحث حُدّثت منذ ٣ ساعات' and ok['tone'] == 'ok' and ok['live'] is True
    assert P({'state': 'running'}) == {'text': 'صفحات محركات البحث تتحدّث الآن', 'tone': 'neutral', 'live': True}
    er = P({'state': 'error', 'at': ago(26)})
    assert er['text'] == 'تعذّر آخر تحديث لصفحات محركات البحث (منذ يوم) — يُعاد مع أول نشر' and er['tone'] == 'bad' and er['live'] is False
    for p in ({'state': 'skipped'}, {'state': 'never-run'}, None, {}):
        x = P(p)
        assert x['text'] == 'تحديث صفحات محركات البحث: غير متاح بعد' and x['live'] is False and x['tone'] == 'na', p


@needs_node
def test_publish_lead_promises_search_pages_only_when_the_pages_are_live():
    L_ = lambda p: _logic('v2ContentPublishLead', 'عنوان', p)
    assert L_({'state': 'ok'}) == 'سيظهر «عنوان» على الموقع الآن، وتتحدّث صفحته لمحركات البحث خلال دقائق.'
    assert L_({'state': 'running'}).endswith('خلال دقائق.')
    for p in ({'state': 'error'}, {'state': 'skipped'}, {'state': 'never-run'}, None):
        assert L_(p) == 'سيظهر «عنوان» على الموقع الآن.', p


# ====================================================================== ٦) شرائح الموضوعات

OLD_TOPIC_TAB = """function topicTabOf(t){var st=t.status||'draft',src=t.source||'human';if(st==='pending_review')return 'pending';if(st==='rejected')return 'rejected';
 if(st==='published'||st==='open')return 'board';if(st==='merged')return 'working';if(src==='expert')return 'incoming';return 'ideas';}"""


@needs_node
def test_topic_chips_equal_the_old_split_and_the_pending_count_never_borrows_from_the_main_list():
    topics = base_src()['topics']
    pend = [{'id': 'x%d' % i} for i in range(3)]
    got = _logic('v2ContentTopicChips', topics, pend, 'pending', {})
    byk = {c['key']: c['count'] for c in got}
    old = json.loads(subprocess.run([NODE, '-e', OLD_TOPIC_TAB + "const t=%s;const c={ideas:0,incoming:0,working:0,board:0,rejected:0};t.forEach(x=>{const k=topicTabOf(x);if(c[k]!=null)c[k]++;});console.log(JSON.stringify(c))" % json.dumps(topics)],
                                    capture_output=True, text=True).stdout)
    # القديمة كانت تضع «المؤرشف» تحت «أفكار» فيُعرض للاعتماد؛ هنا يخرج من القوائم (انحراف مقصود وموثّق في STATUS)
    assert old['ideas'] - 1 == byk['ideas'] and old['incoming'] == byk['incoming'] and old['working'] == byk['working'] and old['board'] == byk['board'] and old['rejected'] == byk['rejected']
    assert byk['pending'] == 3 and [c['label'] for c in got] == ['من الأعضاء', 'أفكار', 'من الخبراء', 'يُكتب', 'على اللوحة', 'مرفوضة']
    # مصدر الأعضاء فاشل ⇒ null (لا الرقم الموجود في القائمة العامة وهو ١ معلّق)
    assert {c['key']: c['count'] for c in _logic('v2ContentTopicChips', topics, None, 'ideas', {})}['pending'] is None
    # القائمة العامة فاشلة ⇒ باقي العدّات null
    assert {c['key']: c['count'] for c in _logic('v2ContentTopicChips', None, pend, 'pending', {})}['ideas'] is None
    # يُكتب يضمّ «يُكتب الآن» (غير الموجود بحالة merged)
    assert {c['key']: c['count'] for c in _logic('v2ContentTopicChips', topics, pend, 'pending', {'zz': 1})}['working'] == byk['working'] + 1
    # «مرفوضة» تختفي عند الصفر إلا لو نشطة
    none_rej = [t for t in topics if t['status'] != 'rejected']
    assert 'rejected' not in [c['key'] for c in _logic('v2ContentTopicChips', none_rej, pend, 'pending', {})]
    assert 'rejected' in [c['key'] for c in _logic('v2ContentTopicChips', none_rej, pend, 'rejected', {})]


@needs_node
def test_segments_keep_the_locked_order_zeros_included_and_report_the_gap():
    an = {'by_segment': [{'segment': 'a', 'label': 'أولى', 'count': 4}, {'segment': 'b', 'label': 'ثانية', 'count': 0}, {'segment': 'c', 'label': 'ثالثة', 'count': 2}, {'segment': 'd', 'label': 'رابعة', 'count': 0}]}
    r = _logic('v2ContentSegments', an)
    assert [l['label'] for l in r['lanes']] == ['أولى', 'ثانية', 'ثالثة', 'رابعة'] and [l['count'] for l in r['lanes']] == [4, 0, 2, 0]
    assert r['gap'] == 'ثانية' and r['low'] == {'id': 'b', 'label': 'ثانية', 'count': 0}
    full = _logic('v2ContentSegments', {'by_segment': [{'segment': 'a', 'label': 'أولى', 'count': 4}, {'segment': 'c', 'label': 'ثالثة', 'count': 2}]})
    assert full['gap'] is None and full['low']['label'] == 'ثالثة'
    assert _logic('v2ContentSegments', {}) is None and _logic('v2ContentSegments', None) is None


# ====================================================================== ٧) حارس النصوص والكتابة

def _strings(src):
    return re.findall(r"'((?:[^'\\\n]|\\.)*)'", src)


def test_copy_guard_over_the_section_files_and_the_reworded_strings():
    text = JS + _block()
    for bad in ('يقوّم', 'يقيّم', 'يقوم بتقييم', 'DEEPSEEK', 'الوكيل الذكي', 'بالذكاء', 'استنّاه', 'آمن', 'ولا أحد ينتظره', 'لا أحد ينتظره'):
        assert bad not in text, bad
    assert not re.search(r'(?<![A-Za-z.\-/_])AI(?![A-Za-z])', re.sub(r"https?://\S+", '', text.replace('data-a=', ''))), 'AI ظاهرة'
    assert not re.search(r'(?<![A-Za-z.\-/_])SEO(?![A-Za-z])', text), 'SEO ظاهرة'
    for s in _strings(text):
        if re.search(r'[؀-ۿ]', s):
            assert not s.lstrip('«» ').startswith('الذكاء'), s
            for latin in ('app.elprofessor.net', 'Anthropic', 'LLM', 'DeepSeek', 'API', 'SEO'):
                assert latin not in s, s
    # النصوص المعاد صياغتها في dashboard-api.js
    for good in ('الكتابة الآلية تعمل الآن بالفعل.', 'بدأت الكتابة الآلية. تظهر المسودات بعد انتهائها.', 'سُحب " + n + " مقال جاهز من المنصة إلى الموقع.', 'لا مقالات جاهزة جديدة على المنصة الآن.'):
        assert good in API_JS, good
    for gone in ('فيه توليد شغّال بالفعل — استنّاه.', 'بدأ التوليد بالذكاء', 'اتسحب " + n + " مقال من الذكاء', 'مفيش مقالات جديدة من الذكاء'):
        assert gone not in API_JS, gone


VERBATIM = [
    'ينتظرك', 'مسودات', 'أفكار', 'نُشر هذا الأسبوع', 'أصحابها ينتظرون قرارك', 'لم تُنشر بعد', 'مادة خام تنتظر أن تتحول إلى نقاش أو خبر منشور', 'ما نُشر أو اعتُمد خلال ٧ أيام',
    'لا شيء هنا الآن', 'العدد ناقص — تعذّر جلب بعض المصادر', 'أعد المحاولة', 'غير متاح بعد', '…جارٍ جمع المحتوى', 'اعتمد وبلّغ', 'افتح واقرأ', 'افتح وراجع',
    'سيظهر على اللوحة العامة، ويصل القرار إلى صاحبه.', 'لن يظهر على اللوحة، ويبقى محفوظًا بلا حذف.', 'سيظهر على اللوحة العامة.', 'سيظهر على اللوحة العامة بنصه الحالي.', 'سيُحذف الموضوع نهائيًا.',
    'سيظهر الرأي بلا اسم على صفحة الدورة.', 'سيظهر الرأي باسم كاتبه على صفحة الدورة.', 'سيظهر الرأي على صفحة الدورة.', 'لن يظهر الرأي على صفحة الدورة.',
    'لن يظهر التعليق على المنصة.', 'سيظهر التعليق للجميع تحت الموضوع.', 'يُحذف التعليق من المنصة نهائيًا.', 'سيظهر العمل للجميع في ركن الإبداع.', 'اكتب سبب الرفض، ويصل إلى صاحب العمل.',
    'ستُحذف هذه المسودة نهائيًا ولا يمكن استرجاعها.', 'سيختفي «', 'سيظهر «', 'يظهر التعديل على الموقع فور الحفظ.', 'لحذف مقال منشور: أوقف نشره أولًا، ثم احذفه من المسودات.',
    'سيظهر في صفحة المقالات داخل المنصة.', 'سيختفي من صفحة المقالات داخل المنصة.', 'يظهر التعديل على اللوحة العامة فور الحفظ.', 'سيظهر الخبر للأعضاء على المنصة.', 'سيختفي الخبر من المنصة.',
    'يصبح الخبر موضوع نقاش على اللوحة.', 'يظهر هذا القسم للأعضاء فور الحفظ.', 'يظهر هذا القسم للأعضاء في دليل الاستخدام.', 'يُحذف هذا القسم من الدليل.',
    'يظهر الرد للجميع تحت التعليق باسم هيئة التحرير.', 'خلاصة مكتوبة آليًا من آخر التعليقات المعتمدة', 'احفظ واكتب الإجابة المقترحة', 'لم يُنشأ أي مقال، والموضوع بقي كما هو.',
    'اكتب مقالات الآن', 'اسحب الجاهز من المنصة', 'موضوعات المدوّنة', 'مقالات elprofessor.net: يقرؤها الناس ومحركات البحث.', 'مقالات صفحة المقالات داخل المنصة.',
    'عنوانه مطابق لمقال منشور', 'عنوانه مطابق لمقال على الموقع', 'فريق البروفيسور', 'المقال المنشور بنفس العنوان: ',
    'لا تعليقات تنتظر قرارك. التعليق المطابق للموضوع يُعتمد تلقائيًا، والمشكوك فيه فقط يصل هنا.',
    'لا مسودات الآن. اكتب مقالًا جديدًا أو اسحب الجاهز من المنصة من «أدوات الكتابة».', 'لا مقالات على المنصة بعد.', 'أرقام الموضوعات', 'أرقام التعليقات', 'ما يسأل عنه الناس في المحادثة',
]
CREDIT = ['يبدأ النظام كتابة ٣ مقالات وموضوعين كمسودات. يستهلك ذلك من رصيد الكتابة الآلية.', 'يستهلك ذلك من رصيد الكتابة الآلية. لا يُنشر شيء قبل اعتمادك.',
          'ولا ينسخ نصه، ويستهلك ذلك من رصيد الكتابة الآلية.', 'يكتب النظام ردًّا ويظهر تحت التعليق باسم هيئة التحرير مباشرة، ويستهلك ذلك من رصيد الكتابة الآلية.',
          'يكتب النظام خلاصة من آخر التعليقات المعتمدة، ويستهلك ذلك من رصيد الكتابة الآلية.', 'لهذا الموضوع مقال بالفعل. تكتب مقالًا آخر؟ يستهلك ذلك من رصيد الكتابة الآلية.']


def test_every_spec_sentence_is_present_verbatim_and_every_credit_lead_names_the_credit():
    text = JS + _block()
    missing = [s for s in VERBATIM if s not in text]
    assert not missing, missing
    miss2 = [s for s in CREDIT if s not in text]
    assert not miss2, miss2
    assert JS.count('رصيد الكتابة الآلية') >= 6


EP_WRITES = ('decidePendingTopic setTopicSegment updateTopic deleteTopic publishTopic createTopic generateArticleFromTopic markTopicArticled createArticle updateArticle '
             'publishArticle unpublishArticle rejectArticle syncContent runDailyContent saveBlogTopic publishArticleP unpublishArticleP deleteArticleP createNews updateNews '
             'deleteNews deriveTopicFromNews saveNewsSources approveOpinion rejectOpinion deleteOpinion replyOpinion createTutorial updateTutorial deleteTutorial decideInboxItem blogTopics').split()
LOADERS = {'content', 'contentOverview', 'platformArticles', 'platformTopics', 'platformPendingTopics', 'platformTopicSegments', 'platformTopicsAnalysis', 'platformOpinions',
           'platformOpinionsApproved', 'platformNews', 'platformNewsSources', 'platformCreative', 'testimonials', 'testimonialsApproved', 'platformOpinionsNumbers', 'tutorials', 'opsQueue'}


def test_the_screen_writes_only_through_existing_ep_functions_and_posts_testimonials_only():
    called = set(re.findall(r'ep\(\)\.(\w+)\(|\bE\.(\w+)\(', JS))
    names = {a or b for a, b in called}
    allowed = set(EP_WRITES) | {'ensure', 'reload', 'api', 'state', 'data'}
    unknown = {n for n in names if n not in allowed}
    assert not unknown, unknown
    # EP.api: مسارين فقط — POST على /v2/testimonials/ وقراءة الخلاصة المدفوعة
    api_calls = re.findall(r"E\.api\(([^)]*)\)", JS)
    assert any("'/v2/testimonials/'" in c or '"/v2/testimonials/"' in c for c in api_calls + re.findall(r"apiPost\(([^,]*),", JS))
    assert "apiPost('/v2/testimonials/'" in JS and "method: 'POST'" in JS
    # الكتابة الوحيدة عبر E.api هي apiPost (الشهادات)
    assert len(re.findall(r"method: 'POST'", JS)) == 1
    # المصادر: المحمّلات المعلنة فقط، ولا platformOpinionsAnalysis أبدًا
    for k in set(re.findall(r"(?:ensure|reload)\('(\w+)'", JS)):
        assert k in LOADERS, k
    for k in re.findall(r"\[((?:'\w+'(?:, )?)+)\]", JS[JS.index('var KEYS'):JS.index('var FAIL_LABEL')]):
        for name in re.findall(r"'(\w+)'", k):
            assert name in LOADERS, name
    assert 'platformOpinionsAnalysis' not in re.sub(r'/\*.*?\*/', '', JS, flags=re.S)
    summ = re.findall(r"/platform-opinions-analysis[^']*'", JS)
    assert summ == ["/platform-opinions-analysis?summarize=true'"], summ
    run = JS[JS.index('function summaryConfirm()'):]
    run = run[:run.index('// ====')]
    assert 'summarize=true' in run and "run: function (done)" in run
    # الكتابة الآلية اليومية دايمًا مع isOpen · ولا لمس لتوليد الصفحات · ولا قائمة «…»
    assert 'runDailyContent(function' in JS and 'isOpen' in JS
    assert not re.search(r'_prerender_push|prerender_push', JS)
    assert '⋯' not in JS and 'popover' not in JS.lower() and 'class="menu' not in JS


def test_every_confirm_press_stamps_the_guard_and_exempt_steps_are_the_listed_ones():
    # كل ورقة تأكيد وتأكيد داخلي ومؤلّف (موضوع جديد · ردّ · سبب رفض العمل) تضع __v2ctConfirmAt
    assert JS.count('window.__v2ctConfirmAt = Date.now()') >= 5
    # لا يوجد حفظ على عنصر عام من غير تأكيد: كل saveDraft/exempt مكتوب تعليقه «مستثنى»
    assert JS.count('مستثنى من التأكيد') >= 5


# ====================================================================== ٨) dashboard-api.js داخل node:vm

API_HARNESS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const inp = JSON.parse(fs.readFileSync(0, 'utf8'));
const calls = [], toasts = [], timers = [];
const sb = { console, Promise, JSON, Math, Date, Intl, Object, Array, String, Number, Error };
sb.setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
sb.clearTimeout = () => {};
const intervals = [];
sb.setInterval = (fn, ms) => { intervals.push({ fn, ms, cleared: false }); return intervals.length; };
sb.clearInterval = (id) => { if (intervals[id - 1]) intervals[id - 1].cleared = true; };
sb.window = sb;
sb.document = { readyState: 'loading', addEventListener() {}, getElementById(id) { return inp.dom && inp.dom.indexOf(id) > -1 ? {} : null; }, createElement() { return { style: {}, appendChild() {}, classList: { add() {}, remove() {} } }; }, body: { appendChild() {} } };
sb.localStorage = { getItem() { return 'tok'; }, setItem() {}, removeItem() {} };
sb.location = { reload() {}, hash: '' };
sb.toast = (m) => toasts.push(m);
sb.notify = (m) => toasts.push(m);
sb.fetch = function (url, opts) {
  const u = String(url).replace(/^.*\/api/, '');
  calls.push({ url: u, method: (opts && opts.method) || 'GET', body: opts && opts.body ? JSON.parse(opts.body) : null });
  const r = inp.replies[u] || inp.replies[u.split('?')[0]] || { status: 200, body: {} };
  if (r.throw) return Promise.reject(new TypeError('Failed to fetch'));
  return Promise.resolve({ ok: r.status >= 200 && r.status < 300, status: r.status, json: () => Promise.resolve(r.body || {}) });
};
vm.createContext(sb);
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), sb);
const EP = sb.EP; EP.authed = true; EP.role = 'admin'; const window = sb;
const tick = (ms) => new Promise((r) => setTimeout(r, ms || 0)); const realSetTimeout = setTimeout;
async function flush() { for (let i = 0; i < 6; i++) await new Promise((r) => realSetTimeout(r, 1)); }
(async () => { const out = await eval('(async () => {' + inp.script + '})()'); await flush(); process.stdout.write(JSON.stringify({ out, calls, toasts, states: EP.state, lastError: EP.lastError, intervals: intervals.map(i => ({ ms: i.ms, cleared: i.cleared })) })); })();
"""


def _api(script, replies=None, dom=None):
    api_path = os.path.join(DC, 'dashboard-api.js')
    p = subprocess.run([NODE, '-e', API_HARNESS, api_path], input=json.dumps({'script': script, 'replies': replies or {}, 'dom': dom or []}), capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


@needs_node
def test_the_five_new_loaders_hit_their_urls_set_data_and_error_on_failure():
    res = _api("""EP.reload('contentOverview'); EP.reload('platformCreative'); EP.reload('testimonials'); EP.reload('testimonialsApproved'); EP.reload('platformOpinionsNumbers'); await new Promise(r => setTimeout(r, 0));
      return {ov: EP.data.contentOverview, cr: EP.data.platformCreative, ts: EP.data.testimonials, ta: EP.data.testimonialsApproved, nn: EP.data.platformOpinionsNumbers, win: [window.PCREATIVE.length, window.PTESTIMONIALS.length]};""",
               {'/v2/content/overview': {'status': 200, 'body': {'articles': [{'id': 1}], 'prerender': {'state': 'ok'}}},
                '/platform-creative': {'status': 200, 'body': {'items': [{'id': 'c1'}, {'id': 'c2'}]}},
                '/v2/testimonials': {'status': 200, 'body': {'testimonials': [{'id': 't1'}], 'count': 1}},
                '/platform-opinions-analysis': {'status': 200, 'body': {'status_counts': {'pending': 2}}}})
    urls = [c['url'] for c in res['calls']]
    assert '/v2/content/overview' in urls and '/platform-creative?status=pending_review' in urls
    assert '/v2/testimonials?status=pending' in urls and '/v2/testimonials?status=approved' in urls and '/platform-opinions-analysis?summarize=false' in urls
    assert all(c['method'] == 'GET' for c in res['calls'])
    o = res['out']
    assert o['ov']['prerender']['state'] == 'ok' and o['cr'] == {'raw': [{'id': 'c1'}, {'id': 'c2'}]} and o['ts'] == {'raw': [{'id': 't1'}]} and o['win'] == [2, 1]
    assert o['nn']['status_counts']['pending'] == 2
    for k in ('contentOverview', 'platformCreative', 'testimonials', 'testimonialsApproved', 'platformOpinionsNumbers'):
        assert res['states'][k] == 'ready', k
    bad = _api("""EP.reload('contentOverview'); EP.reload('testimonials'); await new Promise(r => setTimeout(r, 0)); return 1;""",
               {'/v2/content/overview': {'status': 502, 'body': {'error': 'x'}}, '/v2/testimonials': {'throw': True}})
    assert bad['states']['contentOverview'] == 'error' and bad['states']['testimonials'] == 'error'


@needs_node
def test_mute_notes_silences_toasts_but_the_last_error_is_always_recorded():
    loud = _api("""EP.muteNotes = false; let done; await new Promise(r => EP.deleteTopic({id: 't1', title: 'x'}, r)); return EP.muteNotes;""", {'/platform-topics/t1': {'status': 200, 'body': {}}})
    assert loud['toasts'] and loud['out'] is False
    mute = _api("""EP.muteNotes = true; await new Promise(r => EP.deleteTopic({id: 't1', title: 'x'}, r)); return EP.muteNotes;""", {'/platform-topics/t1': {'status': 200, 'body': {}}})
    assert mute['toasts'] == [] and mute['out'] is True
    fail = _api("""EP.muteNotes = true; EP.lastError = ''; await new Promise(r => EP.deleteTopic({id: 't1', title: 'x'}, r)); return EP.lastError;""",
                {'/platform-topics/t1': {'status': 500, 'body': {'error': 'رفضت المنصة'}}})
    assert fail['toasts'] == [] and fail['out'] == 'رفضت المنصة' and fail['lastError'] == 'رفضت المنصة'
    loudfail = _api("""EP.muteNotes = false; await new Promise(r => EP.deleteTopic({id: 't1', title: 'x'}, r)); return EP.lastError;""", {'/platform-topics/t1': {'status': 500, 'body': {'error': 'رفضت المنصة'}}})
    assert loudfail['toasts'] == ['رفضت المنصة'] and loudfail['out'] == 'رفضت المنصة'


@needs_node
def test_run_daily_content_polls_while_is_open_and_the_old_path_still_checks_the_old_rows():
    replies = {'/platform-articles/daily-run': {'status': 200, 'body': {'started': True}}, '/content/sync-from-platform': {'status': 200, 'body': {'imported': 1}}}
    res = _api("""let open = true, afterN = 0;
      EP.runDailyContent(() => { afterN++; }, { isOpen: () => open });
      await flush();
      const iv = intervals[0], first = calls.length;
      iv.fn(); await flush();
      const polled = calls.slice(first).map(c => c.method + ' ' + c.url);
      const afterPoll = afterN;
      open = false; const before = calls.length;
      iv.fn(); await flush();
      return { afterFirst: 1, polled, afterPoll, extraAfterClose: calls.length - before, cleared: !!iv.cleared };""", replies)
    assert res['calls'][0]['url'] == '/platform-articles/daily-run' and res['calls'][0]['body'] == {'articles': 3, 'topics': 2, 'publish': False}
    o = res['out']
    assert res['intervals'][0]['ms'] == 30000
    assert o['polled'][0] == 'POST /content/sync-from-platform'
    assert {'GET /content/articles/all', 'GET /platform-articles', 'GET /v2/content/overview'} <= set(o['polled'])
    assert o['afterPoll'] >= 2, 'after() بعد المزامنة وإعادة تحميل النظرة'
    assert o['extraAfterClose'] == 0 and o['cleared'] is True, 'الشاشة اتقفلت ⇒ لا نداءات والمؤقّت وقف'
    # المسار القديم بلا opts: بلا عناصر الشاشة القديمة ⇒ يقف بلا نداء · ومع #ctRows ⇒ يزامن ويعيد تحميل المقالات فقط
    old_closed = _api("""EP.runDailyContent(() => {}); await flush(); const iv = intervals[0], n = calls.length; iv.fn(); await flush(); return { extra: calls.length - n, cleared: !!iv.cleared };""", replies)
    assert old_closed['out'] == {'extra': 0, 'cleared': True}
    old_open = _api("""EP.runDailyContent(() => {}); await flush(); const iv = intervals[0], n = calls.length; iv.fn(); await flush(); return calls.slice(n).map(c => c.method + ' ' + c.url);""", replies, dom=['ctRows'])
    assert old_open['out'][0] == 'POST /content/sync-from-platform' and 'GET /content/articles/all' in old_open['out'] and 'GET /v2/content/overview' not in old_open['out']
    # الصيغة المعاد صياغتها تظهر بالحرف في توست المسار القديم (المكتوم ليس الافتراضي)
    loud = _api("""EP.runDailyContent(() => {}); await flush(); return 1;""", replies)
    assert loud['toasts'] == ['بدأت الكتابة الآلية. تظهر المسودات بعد انتهائها.']
    again = _api("""EP.runDailyContent(() => {}); await flush(); return 1;""", {'/platform-articles/daily-run': {'status': 200, 'body': {'already_running': True}}})
    assert again['toasts'] == ['الكتابة الآلية تعمل الآن بالفعل.']
    sync = _api("""await new Promise(r => EP.syncContent(r)); return 1;""", {'/content/sync-from-platform': {'status': 200, 'body': {'imported': 2}}})
    assert sync['toasts'] == ['سُحب ٢ مقال جاهز من المنصة إلى الموقع.'.replace('٢', '2')]
    sync0 = _api("""await new Promise(r => EP.syncContent(r)); return 1;""", {'/content/sync-from-platform': {'status': 200, 'body': {'imported': 0}}})
    assert sync0['toasts'] == ['لا مقالات جاهزة جديدة على المنصة الآن.']


# ====================================================================== ٩) بطاقة المربّع والملفات

@needs_node
def test_home_tile_speaks_the_boards_words_and_always_lands_on_the_ideas_list():
    got = _node("""const T=L.v2Tiles(%s);const t=(T.tiles||T).filter(x=>x.key==='content')[0];console.log(JSON.stringify(t));""" % json.dumps({'topics_drafts': 3, 'testimonials_pending': 2}))
    assert got['next'] == '٣ أفكار · رأيان لمتعلّمَين' and got['land'] == 'topics_drafts' and got['dest'] == 'topics'
    one = _node("const T=L.v2Tiles(%s);console.log(JSON.stringify((T.tiles||T).filter(x=>x.key==='content')[0]))" % json.dumps({'topics_drafts': 1, 'testimonials_pending': 1}))
    assert one['next'] == 'فكرة واحدة · رأي متعلّم واحد'
    many = _node("const T=L.v2Tiles(%s);console.log(JSON.stringify((T.tiles||T).filter(x=>x.key==='content')[0]))" % json.dumps({'topics_drafts': 12, 'testimonials_pending': 4}))
    assert many['next'] == '١٢ فكرة · ٤ آراء متعلّمين'
    only = _node("const T=L.v2Tiles(%s);console.log(JSON.stringify((T.tiles||T).filter(x=>x.key==='content')[0]))" % json.dumps({'topics_drafts': 0, 'testimonials_pending': 5}))
    assert only['next'] == '٥ آراء متعلّمين' and only['land'] == 'topics_drafts'
    zero = _node("const T=L.v2Tiles(%s);console.log(JSON.stringify((T.tiles||T).filter(x=>x.key==='content')[0]))" % json.dumps({'topics_drafts': 0, 'testimonials_pending': 0}))
    assert zero['next'] == 'خط النشر'
    assert 'شهادة' not in _block() and "'شهادة" not in LOGIC[LOGIC.index('// —— المحتوى'):LOGIC.index('// —— بلا رقم في D1')]
    assert "key === 'content'" in HOME and 'openSection(key)' in HOME
    assert re.search(r"testimonials_pending:function\(\)\{[^}]*v2OpenSection\('content','pipeline'\)", HTML)
    assert 'آراء متعلّمين بانتظار المراجعة' in HTML and 'شهادات بانتظار المراجعة' not in HTML


def test_index_html_hooks_are_inside_the_sections_block_and_the_dispatcher_needs_the_shell():
    b = HTML[HTML.index('<!-- v2 sections begin -->'):HTML.index('<!-- v2 sections end -->')]
    assert 'href="v2s/content.css"' in b and 'src="v2s/content.js"' in b
    disp = [l for l in HTML.split('\n') if 'V2SEC' in l and 'owns' in l]
    assert len(disp) == 1 and 'V2SHELL.on' in disp[0] and 'v2-bare' in disp[0]
    assert HTML.index('V2D3.render(current,v)') < HTML.index('V2SEC') < HTML.index("if(current==='inbox')return viewInbox(v);")
    assert os.path.isfile(os.path.join(DC, 'v2s', 'content.js')) and os.path.isfile(os.path.join(DC, 'v2s', 'content.css'))


def test_the_image_ships_the_route_module_and_the_section_folder():
    d = _read('Dockerfile')
    assert 'COPY backend/v2_content_routes.py /app/v2_content_routes.py' in d, 'غياب الوحدة = الحاوية لا تقوم (app.py يستوردها)'
    assert 'COPY dashboard-cloud/v2s /app/dist/v2s' in d


def test_css_is_scoped_under_the_section_roots_and_meets_the_touch_rules():
    css = re.sub(r'/\*.*?\*/', '', CSS, flags=re.S)
    for sel in re.findall(r'([^{}]+)\{', css):
        sel = sel.strip()
        if sel.startswith('@') or sel in ('from', 'to') or re.match(r'^\d+%$', sel):
            continue
        for part in sel.split(','):
            assert part.strip().startswith(('.v2ct', '#epModal')), part
    assert '.v2ct-b1{' in CSS and 'min-height:52px' in CSS and 'min-height:60px' in CSS and 'min-height:44px' in CSS
    assert '#9E2B4E' in CSS and '#FBFAF7' in CSS and '#21262E' in CSS and 'rgb(190,88,48)' in CSS


# ====================================================================== ١٠) الخادم

def _mkuser(email, role):
    u = User.query.filter_by(email=email).first()
    if u:
        u.role = role
        u.dashboard_role = role
        u.is_active = True
        db.session.commit()
        return u
    u = User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=email.split('@')[0], role=role, dashboard_role=role, linked_to_name='',
             preferred_currency='AUTO', is_active=True)
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
        heads = {'admin': _bearer(_mkuser('v2sc-admin@x.test', 'admin')), 'employee': _bearer(_mkuser('v2sc-emp@x.test', 'employee'))}
        yield {'heads': heads, 'client': flask_app.test_client()}


class _Resp(object):
    def __init__(self, status, payload):
        self.status_code = status
        self._p = payload
        self.content = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.headers = {'Content-Type': 'application/json'}

    def json(self):
        return self._p


class Plat(object):
    def __init__(self):
        self.seen, self.blocked, self.replies = [], [], {}

    def __call__(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.seen.append({'method': method.upper(), 'path': url[len(PLATFORM):] if url.startswith(PLATFORM) else url, 'params': dict(params or {}), 'json': copy.deepcopy(json),
                          'headers': dict(headers or {})})
        if not url.startswith(PLATFORM + '/'):
            self.blocked.append(url)
            raise RuntimeError('طلب حقيقي ممنوع: ' + url)
        r = self.replies.get((method.upper(), url[len(PLATFORM):]))
        return _Resp(*(r if r else (200, {'testimonials': [{'id': 'TST_1', 'status': (params or {}).get('status', 'pending')}], 'count': 1} if '/testimonials' in url and method.upper() == 'GET' else {'ok': True})))


@pytest.fixture
def plat(monkeypatch):
    import app as appmod
    p = Plat()
    monkeypatch.setattr(appmod, 'PLATFORM_METRICS_SECRET', SECRET)
    monkeypatch.setattr(appmod, 'PLATFORM_API_URL', PLATFORM)
    monkeypatch.setattr(appmod.requests, 'request', p)
    monkeypatch.setenv('DASH_V2_ENABLED', 'true')
    yield p
    assert p.blocked == []


def _call(c, method, path, body=None, role='admin'):
    kw = {'headers': c['heads'][role] if role else {}}
    if body is not None:
        kw['json'] = body
    return c['client'].open(path, method=method, **kw)


@pytest.fixture
def seeded(plat):
    import app as appmod
    with flask_app.app_context():
        Article.query.delete()
        db.session.commit()
        now = datetime.datetime.utcnow()
        a = Article(title='مقال كامل', excerpt='مقتطف فقط', cat='ق', status='published', body=json.dumps(['## عنوان فرعي هنا', 'فقرة من خمس كلمات هنا', 'كلمتان'], ensure_ascii=False),
                    image_url='https://x.test/i.jpg', meta_description='وصف خام', reviewed_by=' نادية ', created_at=now - datetime.timedelta(hours=5), published_at=now - datetime.timedelta(hours=2))
        b = Article(title='مسودة بمقتطف فقط', excerpt='المقتطف ليس وصفًا', status='draft', body=json.dumps(['كلمة'], ensure_ascii=False), created_at=now - datetime.timedelta(hours=1))
        db.session.add_all([a, b])
        db.session.commit()
        yield {'full': a.id, 'draft': b.id}
        Article.query.delete()
        db.session.commit()


def test_overview_is_admin_only_no_store_read_only_and_never_calls_the_platform(ctx, plat, seeded, monkeypatch):
    import app as appmod
    assert _call(ctx, 'GET', '/api/v2/content/overview', role=None).status_code == 401
    assert _call(ctx, 'GET', '/api/v2/content/overview', role='employee').status_code == 403
    monkeypatch.setattr(appmod, '_prerender_last', {'state': 'ok', 'at': '2026-10-30T10:00:00.123456', 'uploaded': 3, 'reason': 'secret-reason', 'error': 'boom'})
    monkeypatch.setattr(appmod, '_prerender_running', False)
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': (_ for _ in ()).throw(AssertionError('ممنوع تشغيل توليد الصفحات من القراءة')))
    r = _call(ctx, 'GET', '/api/v2/content/overview')
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    d = r.get_json()
    assert plat.seen == [], 'نداء للمنصة من نظرة المقالات'
    rows = {a['title']: a for a in d['articles']}
    full, draft = rows['مقال كامل'], rows['مسودة بمقتطف فقط']
    assert full['words'] == 9           # «عنوان فرعي هنا» ٣ بعد حذف ## + ٥ + ١
    assert full['has_image'] is True and full['has_meta'] is True and full['reviewed_by'] == 'نادية' and full['status'] == 'published'
    assert draft['has_meta'] is False, 'المقتطف البديل في serialize_article لا يُحسب وصفًا'
    assert draft['has_image'] is False and draft['reviewed_by'] is None and draft['published_at'] is None
    assert full['published_at'].endswith('Z') and full['created_at'].endswith('Z')
    for a in d['articles']:
        assert not ({'body', 'meta_description', 'keywords', 'excerpt', 'faq', 'image_url'} & set(a)), 'نص مقال أو وصف في النظرة'
    assert d['prerender'] == {'state': 'ok', 'at': '2026-10-30T10:00:00.123456Z', 'uploaded': 3}
    assert 'reason' not in d['prerender'] and 'error' not in d['prerender'] and 'secret-reason' not in r.get_data(as_text=True) and 'boom' not in r.get_data(as_text=True)
    assert d['now'].endswith('Z')
    assert [a['title'] for a in d['articles']][0] == 'مسودة بمقتطف فقط', 'الأحدث إنشاءً أولًا'


def test_overview_words_count_ignores_heading_marks_and_states_map_one_to_one(ctx, plat, seeded, monkeypatch):
    import app as appmod
    d = _call(ctx, 'GET', '/api/v2/content/overview').get_json()
    full = [a for a in d['articles'] if a['title'] == 'مقال كامل'][0]
    assert full['words'] == 3 + 5 + 1, full['words']          # «عنوان فرعي هنا» ٣ (بلا ##) + ٥ + ١
    for last, running, want in (({'state': 'error', 'error': 'x'}, False, 'error'), ({'state': 'skipped', 'reason': 'r'}, False, 'skipped'), ({'state': 'never-run'}, False, 'never-run'),
                                ({'state': 'ok'}, True, 'running'), ({'state': 'queued-after-current'}, False, 'never-run')):
        monkeypatch.setattr(appmod, '_prerender_last', last)
        monkeypatch.setattr(appmod, '_prerender_running', running)
        got = _call(ctx, 'GET', '/api/v2/content/overview').get_json()['prerender']
        assert got['state'] == want, (last, got)
        assert got['uploaded'] is None


def test_the_new_routes_are_closed_with_a_404_when_the_switch_is_off(ctx, plat, monkeypatch):
    monkeypatch.setenv('DASH_V2_ENABLED', 'false')
    for m, p in (('GET', '/api/v2/content/overview'), ('GET', '/api/v2/testimonials'), ('POST', '/api/v2/testimonials/TST_1/reject')):
        assert _call(ctx, m, p, {} if m == 'POST' else None).status_code == 404, p
    assert plat.seen == []


def test_testimonials_list_is_admin_only_passes_status_through_and_falls_back_to_pending(ctx, plat):
    assert _call(ctx, 'GET', '/api/v2/testimonials', role=None).status_code == 401
    assert _call(ctx, 'GET', '/api/v2/testimonials', role='employee').status_code == 403 and plat.seen == []
    for q, want in (('', 'pending'), ('?status=approved', 'approved'), ('?status=rejected', 'rejected'), ('?status=pending', 'pending'), ('?status=weird', 'pending')):
        plat.seen.clear()
        r = _call(ctx, 'GET', '/api/v2/testimonials' + q)
        assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
        assert len(plat.seen) == 1 and plat.seen[0]['path'] == '/api/bridge/testimonials' and plat.seen[0]['params'] == {'status': want}
        assert plat.seen[0]['headers'].get('X-ELP-Metrics-Secret') == SECRET


def test_approve_needs_an_explicit_true_reject_does_not_and_both_are_audited_on_success_only(ctx, plat):
    for body in (None, {}, {'confirmed': 'true'}, {'confirmed': 1}, {'confirmed': False}):
        plat.seen.clear()
        r = _call(ctx, 'POST', '/api/v2/testimonials/TST_1/approve', body)
        assert r.status_code == 400 and r.get_json()['error'] == 'أكّد النشر أولًا' and plat.seen == [], body
    with flask_app.app_context():
        before = AuditLog.query.filter(AuditLog.action.like('testimonial.%')).count()
    r = _call(ctx, 'POST', '/api/v2/testimonials/TST_1/approve', {'confirmed': True})
    assert r.status_code == 200 and r.headers['Cache-Control'] == 'no-store'
    assert [(c['method'], c['path']) for c in plat.seen] == [('POST', '/api/bridge/testimonials/TST_1/approve')]
    plat.seen.clear()
    r = _call(ctx, 'POST', '/api/v2/testimonials/TST_1/reject', {})
    assert r.status_code == 200 and [(c['method'], c['path']) for c in plat.seen] == [('POST', '/api/bridge/testimonials/TST_1/reject')]
    with flask_app.app_context():
        rows = AuditLog.query.filter(AuditLog.action.like('testimonial.%')).order_by(AuditLog.id.desc()).all()
        assert len(rows) == before + 2 and {rows[0].action, rows[1].action} == {'testimonial.approve', 'testimonial.reject'} and rows[0].target == 'TST_1'
    # رفض المنصة (٤٠٤) ⇒ يصل كما هو ولا تدقيق
    plat.replies[('POST', '/api/bridge/testimonials/NOPE/reject')] = (404, {'detail': 'التقييم غير موجود'})
    r = _call(ctx, 'POST', '/api/v2/testimonials/NOPE/reject', {})
    assert r.status_code == 404 and r.get_json()['error'] == 'التقييم غير موجود'
    with flask_app.app_context():
        assert AuditLog.query.filter(AuditLog.action.like('testimonial.%')).count() == before + 2


def test_bad_action_or_id_is_a_400_and_a_platform_401_or_403_becomes_a_502(ctx, plat):
    assert _call(ctx, 'POST', '/api/v2/testimonials/TST_1/delete', {'confirmed': True}).status_code == 400
    for bad in ('a%2Fb', 'x' * 65, 'a b', 'a.b', 'a$b'):
        r = _call(ctx, 'POST', '/api/v2/testimonials/%s/reject' % bad, {})
        assert r.status_code in (400, 404, 405), bad
    assert plat.seen == []
    for code in (401, 403):
        plat.replies[('POST', '/api/bridge/testimonials/TST_9/reject')] = (code, {'detail': 'x'})
        r = _call(ctx, 'POST', '/api/v2/testimonials/TST_9/reject', {})
        assert r.status_code == 502 and r.get_json()['error'] == 'تعذّر الوصول إلى المنصة'
        plat.replies[('GET', '/api/bridge/testimonials')] = (code, {'detail': 'x'})
        assert _call(ctx, 'GET', '/api/v2/testimonials').status_code == 502


def test_cms_contract_is_unchanged_prerender_reasons_and_article_key_set(ctx, plat, seeded, monkeypatch):
    import app as appmod
    pushes = []
    monkeypatch.setattr(appmod, '_prerender_push_async', lambda reason='': pushes.append(reason) or {'state': 'started'})
    draft, full = seeded['draft'], seeded['full']
    r = _call(ctx, 'POST', '/api/content/articles/%d/publish' % draft, {})
    assert r.status_code == 200 and pushes == ['article-publish:%d' % draft]
    pushes.clear()
    assert _call(ctx, 'PUT', '/api/content/articles/%d' % full, {'title': 'مقال كامل (معدّل)'}).status_code == 200 and pushes == ['article-update:%d' % full]
    pushes.clear()
    _call(ctx, 'PUT', '/api/content/articles/%d' % draft, {'status': 'draft'})
    assert pushes == ['article-update:%d' % draft], 'إلغاء النشر يمرّ على PUT كما اليوم'
    pushes.clear()
    assert _call(ctx, 'DELETE', '/api/content/articles/%d' % full).status_code == 200 and pushes == ['article-delete:%d' % full]
    pushes.clear()
    assert _call(ctx, 'DELETE', '/api/content/articles/%d' % draft).status_code == 200 and pushes == [], 'حذف المسودة لا يولّد صفحات'
    with flask_app.app_context():
        a = Article(title='مفتاح', status='draft', body='[]')
        db.session.add(a)
        db.session.commit()
        keys = set(appmod.serialize_article(a))
        db.session.delete(a)
        db.session.commit()
    assert keys == {'id', 'slug', 'title', 'excerpt', 'cat', 'kicker', 'date', 'by', 'tone', 'video', 'image_url', 'body', 'meta_description', 'keywords', 'faq', 'target_audience', 'status',
                    'published_at', 'updated_at', 'content_hash', 'primary_kw', 'cluster_id', 'role', 'parent_id', 'topic_slug', 'topic_label', 'reviewed_by', 'reviewed_at',
                    'refresh_count', 'last_refreshed_at'} | {k for k in keys if k.startswith(('byline', 'author', 'reviewer'))}


def test_prerender_py_has_no_diff_against_the_branch_base():
    git = subprocess.run(['git', '-C', ROOT, 'cat-file', '-e', BASE_COMMIT], capture_output=True)
    if git.returncode != 0:
        pytest.skip('القاعدة غير متاحة في هذا المستودع')
    d = subprocess.run(['git', '-C', ROOT, 'diff', '--quiet', BASE_COMMIT, '--', 'backend/prerender.py'])
    assert d.returncode == 0, 'prerender.py اتغيّر'
    app_src = _read('backend', 'app.py')
    assert "import v2_content_routes as _v2s_content; _v2s_content.register(app, globals())" in app_src
    assert app_src.index('_v2s_content.register') < app_src.index('# ---- v2 section routes end')
