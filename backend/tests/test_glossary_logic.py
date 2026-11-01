# -*- coding: utf-8 -*-
"""منطق تبويب «القاموس» في الداشبورد (v2s/glossary.js، الجزء النقي) — بيتشغّل في node بلا شبكة وبلا DOM.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_glossary_logic.py

اللي بيثبّته:
  ١. الصفوف والعدّادات: المصدر الفاشل null · الافتراضي «المراجعة غير مطلوبة» · الحقول الغايبة ما تتخترعش · «أخرى» لأي مجال مجهول · الحالات مسودة وتحت التأكيد ومؤكّد.
  ٢. البحث والفلاتر: عربي بلا تشكيل ولا همزات · إنجليزي · فرنسي · الرابط · التعريف · المجال «أخرى» · الحالة · المراجعة.
  ٣. النموذج: الإنشاء يرفض الناقص ويبعت المكتوب فقط · الرابط يُشتقّ من الإنجليزي · حدود الطول وروابط النص تطابق الخادم · «أخرى» في المجال.
  ٤. التعديل بالفرق فقط · المسح بـ'' · الرابط المتجمّد لا يتحرك · لا تغيير ⇒ خطأ · تحذير ختم المراجعة (مفعّل ومعطّل × منشور وغير منشور).
  ٥. ختم «راجعه» (الاسم ٢..١٢٠ والصفة ٢..٨٠ بلا روابط ولا @) · مسحه · النشر يتطلب مراجعة · إلغاء النشر · الحذف قبل أول نشر فقط.
  ٦. شرط المراجعة (تفعيل مع «تحت التأكيد» · إغلاق، والافتراضي مغلق) · نقاش الساحة (ربط موجود وفصله) · الاستيراد (ملف · تجربة · أخطاء بأسماء عربية).
  ٨. «مراجعات القاموس»: الصفوف والفلاتر · اعتمد (تأكيد يختم · اقتراح يفتح المحرّر · دورة ومسار «تمّ») · ارفض بملاحظة وبلا · تحذير تغيّر المصطلح.
  ٧. النصوص: أرقام هندية و«·» ما تلاصق رقمًا · لا «يقوّم» ولا مصطلحات تقنية · نصوص الخادم الإنجليزية الحقول تتعرّب.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
BACKEND = os.path.dirname(_HERE)
NODE = shutil.which('node')
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
APPLY = os.path.join(_HERE, 'uiharness', 'glossary_apply.js')

if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


def G(fn, *args):
    p = subprocess.run([NODE, APPLY], input=json.dumps({'fn': fn, 'args': list(args)}, ensure_ascii=False), capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    if p.returncode != 0:
        raise RuntimeError('node failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def _texts(o, out=None):
    out = [] if out is None else out
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k in ('slug', 'id', 'previewUrl', 'topicId', 'source', 'area'):
                continue
            _texts(v, out)
    elif isinstance(o, list):
        for v in o:
            _texts(v, out)
    return out


def _clean_copy(*objs):
    """«·» ما تلاصق رقمًا · لا «يقوّم» · لا مصطلحات تقنية ظاهرة. (الإنجليزي واللاتيني وحده يُستثنى من الأرقام اللاتينية)"""
    for t in [x for o in objs for x in _texts(o)]:
        assert not re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', t), t
        assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', t), t
        assert not re.search(r'\bAPI\b|JSON|undefined|NaN|\[object|\bnull\b|\bslug\b|\bdraft\b|\bpublished\b', t), t


def _item(i=1, **kw):
    row = {'id': i, 'slug': 'force-majeure', 'ar': 'القوة القاهرة', 'en': 'force majeure', 'fr': 'force majeure', 'area': 'contracts', 'area_label': 'عقود',
           'definition_ar': 'حدث خارج عن إرادة الطرفين يعفي من التنفيذ.', 'example_en': 'The seller is not liable.', 'example_ar': 'لا يسأل البائع.',
           'false_friend_note_ar': 'ليست القضاء والقدر.', 'countries_note_ar': 'تختلف الدول.', 'related': ['frustration'], 'status': 'draft', 'reviewed': False,
           'reviewed_by_name': None, 'reviewed_by_role': None, 'reviewed_at': None, 'reviewer_name_public': False, 'saha_topic_id': None, 'source': 'seed', 'slug_frozen': False,
           'created_at': '2026-11-01T10:00:00', 'updated_at': '2026-11-01T10:00:00', 'published_at': None}
    row.update(kw)
    return row


def _reviewed(**kw):
    base = dict(reviewed=True, reviewed_by_name='أ. هبة الجندي', reviewed_by_role='محامية', reviewed_at='2026-10-30T10:00:00')
    base.update(kw)
    return base


def _resp(items, **kw):
    r = {'items': items, 'total': len(items), 'counts': {'all': len(items), 'draft': 0, 'under_review': 0, 'confirmed': 0, 'published': 0, 'reviewed': 0, 'unreviewed': 0,
                                                    'published_unreviewed': 0, 'reviews_pending': 0, 'by_area': {}},
         'require_review': False}
    r.update(kw)
    return r


def _row(**kw):
    return G('terms', _resp([_item(**kw)]))['rows'][0]


def _form(**kw):
    f = {'slug': '', 'ar': 'القوة القاهرة', 'en': 'force majeure', 'fr': '', 'area': 'contracts', 'definition_ar': 'حدث خارج عن الإرادة.', 'example_en': '', 'example_ar': '',
         'false_friend_note_ar': '', 'countries_note_ar': '', 'related': []}
    f.update(kw)
    return f


# ====================================================================== ١) الصفوف والعدّادات

@needs_node
def test_a_failed_source_is_null_and_the_review_requirement_defaults_to_off():
    assert G('terms', None) is None and G('terms', {}) is None and G('terms', {'items': 'x'}) is None
    v = G('terms', {'items': []})
    assert v['rows'] == [] and v['requireReview'] is False and v['counts']['all'] == 0 and v['counts']['reviewsPending'] == 0
    assert G('terms', {'items': [], 'require_review': True})['requireReview'] is True and G('terms', {'items': [], 'require_review': 'yes'})['requireReview'] is False


@needs_node
def test_rows_keep_the_server_facts_and_never_invent_a_reviewer_or_a_link():
    r = _row()
    assert (r['id'], r['slug'], r['ar'], r['en'], r['areaText'], r['statusText'], r['reviewed'], r['reviewLine'], r['canDelete'], r['previewUrl'], r['siteBadge']) == (
        '1', 'force-majeure', 'القوة القاهرة', 'force majeure', 'عقود', 'مسودة', False, '', True, '', '')
    p = _row(status='confirmed', slug_frozen=True, **_reviewed(), saha_topic_id='c0ffee00-1111')
    assert p['published'] and p['confirmed'] and p['reviewed'] and p['reviewLine'] == 'راجعه: أ. هبة الجندي، محامية' and p['reviewedOn'] == '٣٠ أكتوبر ٢٠٢٦'
    assert p['statusText'] == 'مؤكّد' and p['namePublic'] is False and p['siteBadge'] == 'راجعه متخصص', 'بلا موافقة الاسم لا يظهر المراجع على الموقع'
    named = _row(status='confirmed', **_reviewed(reviewer_name_public=True))
    assert named['namePublic'] is True and named['siteBadge'] == 'راجعه: أ. هبة الجندي، محامية'
    under = _row(status='under_review')
    assert under['published'] and under['underReview'] and not under['confirmed'] and under['statusText'] == 'تحت التأكيد' and under['canDelete'] is False
    assert under['siteBadge'] == 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' and under['previewUrl'].endswith('/force-majeure.html')
    assert _row(status='published')['status'] == 'draft', 'قيمة قديمة مجهولة لا تُعدّ منشورة'
    assert p['previewUrl'] == 'https://elprofessor.net/glossary/force-majeure.html' and p['canDelete'] is False and p['topicId'] == 'c0ffee00-1111'
    # ختم ناقص لا يُعدّ مراجعة · معرّف نقاش غير صالح يُهمَل · مجال مجهول ⇒ أخرى
    half = _row(reviewed=True, reviewed_by_name='أ. هبة', reviewed_by_role=None)
    assert half['reviewed'] is False and half['reviewLine'] == ''
    odd = _row(area='nonsense', saha_topic_id='bad id', related=['ok-slug', 'BAD SLUG', 7])
    assert odd['area'] == 'other' and odd['areaText'] == 'أخرى' and odd['topicId'] == '' and odd['related'] == ['ok-slug']


@needs_node
def test_counts_come_from_the_server_and_fall_back_to_the_rows():
    items = [_item(1), _item(2, slug='a-b', status='confirmed', **_reviewed()), _item(3, slug='c-d', status='under_review')]
    v = G('terms', {'items': items})
    assert v['counts']['all'] == 3 and v['counts']['published'] == 2 and v['counts']['draft'] == 1 and v['counts']['reviewed'] == 1 and v['counts']['unreviewed'] == 2
    assert v['counts']['publishedUnreviewed'] == 1 and v['counts']['underReview'] == 1 and v['counts']['confirmed'] == 1
    srv = _resp(items, counts={'all': 111, 'draft': 100, 'under_review': 8, 'confirmed': 3, 'published': 11, 'reviewed': 5, 'unreviewed': 106, 'published_unreviewed': 8,
                               'reviews_pending': 4, 'by_area': {'contracts': 30}})
    c = G('terms', srv)['counts']
    assert (c['all'], c['published'], c['reviewed'], c['publishedUnreviewed'], c['byArea']['contracts']) == (111, 11, 5, 8, 30)
    assert (c['underReview'], c['confirmed'], c['reviewsPending']) == (8, 3, 4)
    assert G('summary', c) == 'مؤكّد ٣، تحت التأكيد ٨، مسودة ١٠٠'
    assert G('terms', dict(srv, total=600, items=items))['truncated'] is True


@needs_node
def test_the_area_list_matches_the_server_and_has_other_everywhere():
    import v2_glossary_routes as gr
    areas = G('AREAS')
    assert [tuple(a) for a in areas] == list(gr.AREAS) and areas[-1] == ['other', 'أخرى']
    chips = G('areaChips', {'byArea': {'contracts': 3, 'other': 0}})
    assert chips[0] == ['all', 'الكل'] and chips[1] == ['contracts', 'عقود (٣)'] and chips[-1] == ['other', 'أخرى'] and len(chips) == 11
    assert G('SUBSTANTIVE') == list(gr.SUBSTANTIVE)
    assert {f[0]: f[2] for f in G('FIELDS')} == gr.MAX_LEN
    assert G('RELATED_MAX') == gr.RELATED_MAX and G('IMPORT_MAX') == gr.IMPORT_MAX
    assert [s[0] for s in G('IMPORT_SOURCES')] == list(gr.SOURCES)
    for ok in ('a', 'force-majeure', 'a1'):
        assert gr.SLUG_RE.match(ok) and re.match(r'^[a-z](?:[a-z0-9-]{0,62}[a-z0-9])?$', ok)
    assert G('slugify', 'Force Majeure!') == 'force-majeure' and G('slugify', 'قوة') == '' and G('slugify', 'x' * 100) == 'x' * 64


# ====================================================================== ٢) البحث والفلاتر

@needs_node
def test_search_ignores_case_diacritics_and_alef_forms_and_covers_every_language():
    rows = G('terms', _resp([
        _item(1, slug='force-majeure', ar='القُوَّة القاهرة', en='Force Majeure', fr='force majeure'),
        _item(2, slug='arbitral-award', ar='حكم التحكيم', en='arbitral award', fr='sentence arbitrale', area='arbitration', definition_ar='قرار يصدر عن هيئة التحكيم.'),
        _item(3, slug='other-thing', ar='أمر آخر', en='misc', fr='', area='other', status='confirmed', **_reviewed()),
        _item(4, slug='under-thing', ar='شيء ثالث', en='third', fr='', area='general', status='under_review')]))['rows']

    def hit(**f):
        return [r['slug'] for r in G('filterRows', rows, f)]
    assert hit(q='القوه القاهره') == ['force-majeure'] and hit(q='FORCE') == ['force-majeure'] and hit(q='sentence') == ['arbitral-award']
    assert hit(q='هيئة') == ['arbitral-award'] and hit(q='arbitral-aw') == ['arbitral-award'] and hit(q='امر اخر') == ['other-thing']
    assert hit(q='') == ['force-majeure', 'arbitral-award', 'other-thing', 'under-thing'] and hit(q='لا شيء مطابق') == []
    assert hit(area='other') == ['other-thing'] and hit(area='arbitration') == ['arbitral-award'] and hit(area='all') == hit()
    assert hit(status='published') == ['other-thing', 'under-thing'] and hit(status='draft') == ['force-majeure', 'arbitral-award']
    assert hit(status='confirmed') == ['other-thing'] and hit(status='under_review') == ['under-thing']
    assert hit(review='reviewed') == ['other-thing'] and hit(review='unreviewed') == ['force-majeure', 'arbitral-award', 'under-thing']
    assert hit(q='force', area='contracts', status='draft', review='unreviewed') == ['force-majeure']


# ====================================================================== ٣) الإنشاء

@needs_node
def test_create_needs_the_three_texts_and_an_area_and_refuses_links_and_long_texts():
    r = G('termCheck', _form(ar='', en='', definition_ar='', area=''), 'create', None, True)
    assert r['ok'] is False and set(r['errors']) >= {'ar', 'en', 'definition_ar', 'area'}
    assert G('termCheck', _form(definition_ar='انظر https://example.test'), 'create', None, True)['errors']['definition_ar'] == 'لا تضع روابط في النص'
    assert 'definition_ar' in G('termCheck', _form(definition_ar='x' * 3001), 'create', None, True)['errors']
    assert 'ar' in G('termCheck', _form(ar='ا' * 301), 'create', None, True)['errors']
    assert 'area' in G('termCheck', _form(area='nonsense'), 'create', None, True)['errors']
    assert G('termCheck', _form(area='other'), 'create', None, True)['ok'] is True, '«أخرى» مجال صالح'
    assert 'slug' in G('termCheck', _form(slug='Bad Slug'), 'create', None, True)['errors']
    assert 'slug' in G('termCheck', _form(en='قاعدة', slug=''), 'create', None, True)['errors'], 'إنجليزي غير لاتيني ولا رابط ⇒ يطلب رابطًا'
    assert 'related' in G('termCheck', _form(related=['ok'] * 2 + ['Bad Slug']), 'create', None, True)['errors']
    assert 'related' in G('termCheck', _form(related=['a%d' % i for i in range(21)]), 'create', None, True)['errors']


@needs_node
def test_create_sends_only_what_was_written_derives_the_link_and_saves_a_draft():
    r = G('termCheck', _form(), 'create', None, True)
    assert r['ok'] and r['body'] == {'slug': 'force-majeure', 'ar': 'القوة القاهرة', 'en': 'force majeure', 'area': 'contracts', 'definition_ar': 'حدث خارج عن الإرادة.'}
    assert 'مسودة' in r['lead'] and 'يراجعه خبير' in r['lead'] and any('يتجمّد' in w for w in r['warns'])
    assert 'يراجعه خبير' not in G('termCheck', _form(), 'create', None, False)['lead']
    full = G('termCheck', _form(slug='fm-clause', fr='force majeure', example_en='Example.', example_ar='مثال.', false_friend_note_ar='خطأ.', countries_note_ar='دول.', related=['b-c', 'b-c', 'd-e']), 'create', None, True)
    assert full['body']['slug'] == 'fm-clause' and full['body']['related'] == ['b-c', 'd-e'] and full['body']['fr'] == 'force majeure'
    assert set(full['body']) == {'slug', 'ar', 'en', 'fr', 'area', 'definition_ar', 'example_en', 'example_ar', 'false_friend_note_ar', 'countries_note_ar', 'related'}
    assert 'status' not in full['body'] and 'reviewed_by_name' not in full['body'] and 'confirmed' not in full['body'] and 'by' not in full['body']
    assert [ln['label'] for ln in r['lines']][:3] == ['المصطلح', 'بالإنجليزية', 'المجال'] and r['lines'][1]['ltr'] is True


# ====================================================================== ٤) التعديل

def _check(form, row_kw=None, require=True, **form_kw):
    row = _row(**(row_kw or {}))
    f = G('termForm', row)
    f.update(form)
    return G('termCheck', f, 'edit', row, require)


@needs_node
def test_edit_sends_only_the_difference_clears_with_empty_and_refuses_no_change():
    assert _check({})['ok'] is False and _check({})['error'] == 'لا يوجد تغيير'
    r = _check({'definition_ar': 'تعريف أدق.'})
    assert r['ok'] and r['body'] == {'definition_ar': 'تعريف أدق.'} and r['lines'][0]['label'] == 'التعريف'
    r = _check({'fr': '', 'example_en': '', 'area': 'other', 'related': []})
    assert r['body'] == {'fr': '', 'example_en': '', 'area': 'other', 'related': []}
    r = _check({'related': ['frustration', 'x-y']})
    assert r['body'] == {'related': ['frustration', 'x-y']}
    assert _check({'ar': ''})['errors']['ar'] and _check({'definition_ar': ' '})['errors']['definition_ar']


@needs_node
def test_the_link_changes_only_before_the_first_publication():
    assert _check({'slug': 'fm-new'})['body'] == {'slug': 'fm-new'}
    assert _check({'slug': ''})['errors']['slug'] == 'رابط المصطلح مطلوب'
    frozen = _check({'slug': 'fm-new'}, {'slug_frozen': True, 'status': 'confirmed', **_reviewed()})
    assert frozen['ok'] is False and frozen['error'] == 'لا يوجد تغيير', 'الرابط المتجمّد يُتجاهل ولو كتبه المستخدم'


@needs_node
def test_the_review_sheet_warns_about_the_stamp_exactly_as_the_server_acts():
    reviewed_draft = _check({'definition_ar': 'جديد.'}, {**_reviewed()})
    assert any('سيُلغى ختم المراجعة لأنك عدّلت النص' in w for w in reviewed_draft['warns']) and reviewed_draft['clearsReview'] is True and reviewed_draft['drops'] is False
    # مؤكَّد + الشرط مفعّل: يعود مسودة وتسقط صفحته
    pub = _check({'definition_ar': 'جديد.'}, {'status': 'confirmed', 'slug_frozen': True, **_reviewed()}, True)
    assert pub['drops'] is True and any('يعود المصطلح مسودة' in w for w in pub['warns']) and any('سيُلغى ختم المراجعة' in w for w in pub['warns'])
    # الشرط مغلق (الافتراضي): يمسح الختم ويرجع «تحت التأكيد» ويبقى ظاهرًا
    off = _check({'definition_ar': 'جديد.'}, {'status': 'confirmed', 'slug_frozen': True, **_reviewed()}, False)
    assert off['drops'] is False and 'سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا.' in off['warns'] and not any('مسودة' in w for w in off['warns'])
    assert any('سيُلغى ختم المراجعة' in w for w in off['warns'])
    # تعديل غير جوهري (مجال · قريبة) يُبقي الختم والحالة ولا تحذير
    soft = _check({'area': 'litigation', 'related': ['x-y']}, {'status': 'confirmed', 'slug_frozen': True, **_reviewed()}, True)
    assert soft['warns'] == [] and soft['clearsReview'] is False and soft['drops'] is False and 'تتحدّث صفحته' in soft['lead']
    # تحت التأكيد (لا ختم): لا شيء يُمسح ولا يعود مسودة
    nostamp = _check({'definition_ar': 'جديد.'}, {'status': 'under_review', 'slug_frozen': True}, True)
    assert nostamp['warns'] == [] and nostamp['drops'] is False
    # مسودة بلا ختم: لا تحذير
    assert _check({'definition_ar': 'جديد.'})['warns'] == []


@needs_node
def test_edit_done_text_reports_what_the_server_did():
    assert G('termDone', 'edit', {'changed': ['definition_ar'], 'review_cleared': False, 'unpublished': False}) == 'حُفظت التعديلات'
    t = G('termDone', 'edit', {'changed': ['definition_ar'], 'review_cleared': True, 'unpublished': True})
    assert 'أُلغي ختم المراجعة' in t and 'عاد المصطلح مسودة' in t
    u = G('termDone', 'edit', {'changed': ['definition_ar'], 'review_cleared': True, 'unpublished': False, 'item': {'status': 'under_review'}})
    assert u == 'حُفظت التعديلات، وأُلغي ختم المراجعة، وعاد المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا'
    assert G('termDone', 'edit', {'changed': []}) == 'لا يوجد تغيير' and 'أُضيف المصطلح «س»' in G('termDone', 'create', {'item': {'ar': 'س'}})


# ====================================================================== ٥) المراجعة والنشر والحذف

@needs_node
def test_the_review_stamp_needs_a_real_name_and_role_without_links_or_mail():
    row = _row()
    ok = G('reviewCheck', {'reviewer_name': '  أ.  هبة   الجندي ', 'reviewer_role': 'محامية'}, row)
    assert ok['ok'] and ok['body'] == {'reviewer_name': 'أ. هبة الجندي', 'reviewer_role': 'محامية', 'reviewer_name_public': False} and ok['goLabel'] == 'ضع ختم المراجعة'
    assert any('لن يظهر اسم المراجع للناس' in w and 'راجعه متخصص' in w for w in ok['warns']) and 'confirmed' not in ok['body'] and 'reviewed_at' not in ok['body']
    assert any('يبقى مسودة' in w for w in ok['warns']) and {'label': 'ظهور الاسم للناس', 'from': '', 'to': 'لا يظهر'} in ok['lines']
    named = G('reviewCheck', {'reviewer_name': 'أ. هبة', 'reviewer_role': 'محامية', 'reviewer_name_public': True}, _row(status='under_review'))
    assert named['body']['reviewer_name_public'] is True and any('يظهر هذا الاسم وصفته للناس' in w for w in named['warns']) and {'label': 'الحالة', 'from': 'تحت التأكيد', 'to': 'مؤكّد'} in named['lines']
    assert G('reviewCheck', {'reviewer_name': 'أ. هبة', 'reviewer_role': 'محامية', 'reviewer_name_public': 'true'}, row)['body']['reviewer_name_public'] is False, 'قيمة غير منطقية لا تُعدّ موافقة'
    for bad in ({'reviewer_name': 'أ', 'reviewer_role': 'محامية'}, {'reviewer_name': 'أ. هبة', 'reviewer_role': ''}, {'reviewer_name': 'x@example.test', 'reviewer_role': 'محامية'},
                {'reviewer_name': 'أ. هبة', 'reviewer_role': 'https://example.test'}, {'reviewer_name': 'ا' * 121, 'reviewer_role': 'محامية'}, {'reviewer_name': 'أ. هبة', 'reviewer_role': 'ا' * 81}):
        assert G('reviewCheck', bad, row)['ok'] is False, bad
    redo = G('reviewCheck', {'reviewer_name': 'د. سلمى', 'reviewer_role': 'أستاذة قانون'}, _row(**_reviewed()))
    assert redo['goLabel'] == 'جدّد ختم المراجعة' and redo['lines'][1]['from'] == 'أ. هبة الجندي، محامية'


@needs_node
def test_removing_the_stamp_returns_to_under_review_or_to_draft_while_review_is_required():
    assert G('unreviewCheck', _row(), True)['ok'] is False
    pub = _row(status='confirmed', slug_frozen=True, **_reviewed())
    on = G('unreviewCheck', pub, True)
    assert on['ok'] and on['unpublishes'] is True and any('سيعود مسودة' in w for w in on['warns']) and {'label': 'الحالة', 'from': 'مؤكّد', 'to': 'مسودة'} in on['lines']
    off = G('unreviewCheck', pub, False)
    assert off['unpublishes'] is False and 'سيرجع المصطلح إلى «تحت التأكيد» ويبقى ظاهرًا.' in off['warns'] and {'label': 'الحالة', 'from': 'مؤكّد', 'to': 'تحت التأكيد'} in off['lines']
    draft = G('unreviewCheck', _row(**_reviewed()), True)
    assert draft['ok'] and draft['warns'] == [] and draft['unpublishes'] is False
    assert G('unreviewDone', {'unpublished': True}) == 'مُسح الختم، وعاد المصطلح مسودة' and G('unreviewDone', {}) == 'مُسح ختم المراجعة'
    assert G('unreviewDone', {'unpublished': False, 'item': {'status': 'under_review'}}) == 'مُسح الختم، وعاد المصطلح إلى «تحت التأكيد»'


@needs_node
def test_publishing_needs_a_review_only_while_the_setting_is_on_and_says_why():
    unrev = _row()
    assert G('publishBlock', unrev, True) == 'يُنشر بعد أن يراجعه خبير' and G('publishBlock', unrev, False) == ''
    blocked = G('publishCheck', unrev, True)
    assert blocked['ok'] is False and blocked['error'] == 'يُنشر بعد أن يراجعه خبير' and blocked['needsReview'] is True
    rev = _row(**_reviewed())
    assert G('publishBlock', rev, True) == ''
    ok = G('publishCheck', rev, True)
    assert ok['ok'] and ok['lead'] == 'ستظهر صفحة المصطلح على الموقع خلال دقائق.' and ok['warns'] == ['يتجمّد رابط المصطلح بعد أول نشر ولا يتغير.']
    assert {'label': 'الحالة', 'from': 'مسودة', 'to': 'مؤكّد'} in ok['lines']
    assert ok['lines'][2] == {'label': 'الصفحة', 'to': 'elprofessor.net/glossary/force-majeure.html', 'ltr': True}
    loose = G('publishCheck', _row(), False)
    assert loose['ok'] and {'label': 'الحالة', 'from': 'مسودة', 'to': 'تحت التأكيد'} in loose['lines']
    assert any('لم يراجعه خبير بعد' in w and 'تحت التأكيد: نبحث عن متخصص يراجع هذا المصطلح' in w for w in loose['warns']) and any('ملاحظة الدول لا تظهر' in w for w in loose['warns'])
    already = _row(status='confirmed', slug_frozen=True, **_reviewed())
    assert G('publishCheck', already, True)['ok'] is False and G('publishBlock', already, True) == ''
    assert 'تحت التأكيد' in G('publishDone', unrev) and 'تحت التأكيد' not in G('publishDone', rev)


@needs_node
def test_unpublish_and_delete_rules():
    pub = _row(status='confirmed', slug_frozen=True, **_reviewed())
    u = G('unpublishCheck', pub)
    assert u['ok'] and 'ستختفي صفحة المصطلح من الموقع خلال دقائق' in u['lead'] and G('unpublishCheck', _row())['ok'] is False
    assert u['lines'] == [{'label': 'الحالة', 'from': 'مؤكّد', 'to': 'مسودة'}] and G('unpublishCheck', _row(status='under_review'))['lines'][0]['from'] == 'تحت التأكيد'
    assert G('deleteCheck', _row())['ok'] is True and 'نهائيًا' in G('deleteCheck', _row())['lead']
    gone = G('deleteCheck', _row(slug_frozen=True))
    assert gone['ok'] is False and 'ألغِ نشره' in gone['error'], 'ما اتنشر قبل كده يتحذف، وبعده يُلغى نشره فقط'
    assert G('deleteCheck', pub)['ok'] is False


# ====================================================================== ٦) الشرط · النقاش · الاستيراد

@needs_node
def test_the_review_requirement_toggle_explains_both_directions():
    v = G('terms', _resp([], require_review=True, counts={'all': 3, 'draft': 1, 'under_review': 2, 'confirmed': 0, 'published': 2, 'reviewed': 0, 'unreviewed': 3, 'published_unreviewed': 2, 'by_area': {}}))
    r = G('rulesView', v)
    assert r['on'] is True and r['word'] == 'مطلوبة' and r['publishedUnreviewed'] == 2 and 'تحت التأكيد' in r['puText'] and 'مصطلحان' in r['puText'] and G('rulesView', None) is None
    assert 'لا يُنشر أي مصطلح قبل أن يراجعه خبير' in r['text'] and r['text'] == r['onText'] and 'تحت التأكيد' in r['offText']
    off = G('rulesView', G('terms', _resp([])))
    assert off['on'] is False and off['word'] == 'غير مطلوبة' and off['text'] == off['offText'] and 'يُنشر المصطلح فورًا' in off['text']
    on = G('settingsCheck', True, False, 2)
    assert on['ok'] and on['body'] == {'require_review': True} and any('لا يُنزَل تلقائيًا' in w and 'تحت التأكيد' in w for w in on['warns']) and on['goLabel'] == 'اجعل المراجعة مطلوبة'
    assert G('settingsCheck', True, False, 0)['warns'] == []
    close = G('settingsCheck', False, True, 0)
    assert close['body'] == {'require_review': False} and any('سيُنشر أي مصطلح بشارة «تحت التأكيد»' in w for w in close['warns']) and 'يُنشر المصطلح فورًا' in close['lead']
    assert G('settingsCheck', True, True, 0)['ok'] is False and G('settingsCheck', 'x', True, 0)['ok'] is False
    assert 'مطلوبة' in G('settingsDone', {'require_review': True}) and 'أُغلق' in G('settingsDone', {'require_review': False})


@needs_node
def test_attach_only_a_discussion_from_the_list_and_detach_with_a_review():
    tv = G('topics', {'topics': [{'id': 'c0ffee00-1111', 'title': 'متى تُعفي القوة القاهرة؟', 'status': 'published'}, {'id': 'bad id', 'title': 'x'}, {'id': 'aaaaaaaa0000', 'title': ''}]})
    assert [t['id'] for t in tv['rows']] == ['c0ffee00-1111', 'aaaaaaaa0000'] and tv['rows'][1]['title'] == 'نقاش بلا عنوان' and G('topics', None) is None and G('topics', {}) is None
    row = _row(status='confirmed', slug_frozen=True, **_reviewed())
    assert G('attachCheck', '', tv, row)['ok'] is False and G('attachCheck', 'zzzzzzzz9999', tv, row)['ok'] is False
    ok = G('attachCheck', 'c0ffee00-1111', tv, row)
    assert ok['ok'] and ok['body'] == {'saha_topic_id': 'c0ffee00-1111'} and 'ناقشه في الساحة' in ok['lead'] and ok['lines'][0]['to'] == 'متى تُعفي القوة القاهرة؟'
    assert G('attachCheck', 'c0ffee00-1111', tv, _row(saha_topic_id='aaaaaaaa0000'))['ok'] is False
    det = G('detachCheck', _row(saha_topic_id='c0ffee00-1111'), tv)
    assert det['ok'] and det['lines'][0]['to'] == 'متى تُعفي القوة القاهرة؟' and G('detachCheck', _row(), tv)['ok'] is False
    assert G('topicUrl', 'c0ffee00-1111') == 'https://app.elprofessor.net/?page=saha&topic=c0ffee00-1111' and G('topicUrl', 'bad id') == ''


@needs_node
def test_import_file_check_body_and_preview_view():
    assert G('importFileCheck', None)['ok'] is False and G('importFileCheck', {'items': 'x'})['ok'] is False and G('importFileCheck', {'items': []})['ok'] is False
    assert G('importFileCheck', {'items': [1]})['ok'] is False and G('importFileCheck', {'items': [{}] * 501})['error'] == 'الملف أكبر من ٥٠١ مصطلح'.replace('٥٠١', '٥٠٠')
    both = [G('importFileCheck', {'items': [{'id': 'a-b'}]}), G('importFileCheck', [{'id': 'a-b'}])]
    assert all(b['ok'] and b['count'] == 1 for b in both)
    assert G('importBody', 'seed', None) == {'source': 'seed'} and G('importBody', 'upload', both[0]) == {'source': 'upload', 'payload': {'items': [{'id': 'a-b'}]}}
    assert G('importCanPreview', 'upload', None)['ok'] is False and G('importCanPreview', 'seed', None)['ok'] is True and G('importCanPreview', 'x', None)['ok'] is False
    assert [s[1] for s in G('IMPORT_SOURCES')] == ['القاموس الأساسي (٨٠)', 'مرشّحة من دورة القراءة (٣١)', 'ملف من جهازك']
    v = G('importView', {'source': 'seed', 'total': 80, 'new_count': 78, 'skip_existing': 1, 'skip_duplicate_in_file': 0, 'invalid_count': 1,
                         'problems': [{'row': 7, 'slug': 'bad-one', 'problem': 'definition_ar: النص أطول من 3000 حرفًا (definition_ar)'}, {'row': 9, 'slug': None, 'problem': 'الحقل مطلوب: ar'}],
                         'sample': [{'slug': 'a-b', 'ar': 'أ', 'en': 'a', 'area': 'litigation', 'area_label': 'تقاضٍ'}]})
    assert [(r['key'], r['n']) for r in v['rows']] == [('new', 78), ('exists', 1), ('dup', 0), ('bad', 1)] and v['changes'] == 78
    assert v['problems'][0]['row'] == '٧' and 'التعريف' in v['problems'][0]['text'] and 'definition_ar' not in v['problems'][0]['text'] and '٣٠٠٠' in v['problems'][0]['text']
    assert v['problems'][1]['text'] == 'الحقل مطلوب: المصطلح بالعربية' and v['sample'][0]['areaText'] == 'تقاضٍ'
    assert G('importView', None) is None and G('importView', {})['changes'] == 0
    assert 'مصطلحًا جديدًا' in G('importDone', G('importView', {'new_count': 78, 'imported': 78})) and 'بلا مصطلحات جديدة' in G('importDone', G('importView', {'imported': 0}))


# ====================================================================== ٧) الأخطاء والنصوص

@needs_node
def test_write_errors_pass_the_server_arabic_text_and_never_leak_field_names():
    assert G('writeError', 409, {'error': 'يُنشر بعد أن يراجعه خبير'}) == 'يُنشر بعد أن يراجعه خبير'
    assert G('writeError', 502, {'error': 'لم يصل رد. حدّث الصفحة ثم أعد المحاولة.', 'no_reply': True}).startswith('لم يصل رد')
    assert G('writeError', 502, {'error': 'تعذّر الاتصال بالمنصة'}) == 'تعذّر الاتصال بالمنصة'
    assert G('writeError', 401, {}) == 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب'
    assert G('writeError', 500, {'error': 'Internal Server Error'}) == 'تعذّر تنفيذ العملية، حاول مرة أخرى'
    assert G('writeError', 409, {'error': 'conflict'}) == 'تغيّرت حالة هذا المصطلح، حدّث الصفحة وحاول مرة أخرى'
    assert G('writeError', 400, {'error': 'definition_ar: النص أطول من 3000 حرفًا (definition_ar)'}).startswith('التعريف:')


@needs_node
def test_all_visible_copy_is_clean_arabic():
    rev = _row(**_reviewed())
    pub = _row(status='confirmed', slug_frozen=True, **_reviewed(), saha_topic_id='c0ffee00-1111')
    tv = G('topics', {'topics': [{'id': 'c0ffee00-1111', 'title': 'نقاش', 'status': 'published'}]})
    outs = [G('termCheck', _form(), 'create', None, True), _check({'definition_ar': 'جديد.'}, {'status': 'confirmed', 'slug_frozen': True, **_reviewed()}),
            G('reviewCheck', {'reviewer_name': 'أ. هبة', 'reviewer_role': 'محامية'}, rev), G('unreviewCheck', pub, True), G('publishCheck', rev, True), G('publishCheck', _row(), True),
            G('unpublishCheck', pub), G('deleteCheck', _row()), G('settingsCheck', True, False, 2), G('settingsCheck', False, True, 0), G('attachCheck', 'c0ffee00-1111', tv, rev),
            G('detachCheck', pub, tv), G('importView', {'total': 80, 'new_count': 78, 'skip_existing': 2, 'problems': [{'row': 3, 'slug': 'x', 'problem': 'الحقل مطلوب: ar'}]}),
            G('importDone', G('importView', {'new_count': 5, 'imported': 5})), G('summary', G('terms', _resp([_item()]))['counts']), G('termCountText', 1), G('termCountText', 0),
            G('termCountText', 5), G('termCountText', 11), G('rulesView', G('terms', _resp([], counts={'published_unreviewed': 3}))), G('settingsDone', {'require_review': True}),
            G('publishDone', rev), G('unpublishDone', pub), G('reviewDone', rev), G('termDone', 'edit', {'changed': ['ar'], 'review_cleared': True, 'unpublished': True}),
            [c[1] for c in G('STATUS_CHIPS') + G('REVIEW_CHIPS') + G('areaChips', {'byArea': {'contracts': 4}}) + G('IMPORT_SOURCES')]]
    _clean_copy(*outs)
    assert G('fixSep', 'عدد ٣ · وفي') == 'عدد ٣، وفي'


# ====================================================================== ٨) مراجعات القاموس

def _rv(i=1, **kw):
    row = {'id': i, 'kind': 'glossary_term', 'ref': 'force-majeure', 'ref_title': 'القوة القاهرة', 'name': 'د. نادر فؤاد', 'email': 'nader@example.test', 'specialty': 'law_teaching',
           'specialty_label': 'تدريس القانون', 'specialty_other': None, 'specialty_text': 'تدريس القانون', 'verdict': 'confirm', 'text': '', 'show_name': True, 'status': 'pending',
           'created_at': '2026-10-28T09:00:00', 'decided_at': None, 'decided_by': None, 'admin_note': '', 'term_changed': False,
           'term': _item(5, status='under_review')}
    row.update(kw)
    return row


def _rvs(*items, **kw):
    d = {'items': list(items), 'total': len(items)}
    d.update(kw)
    return G('reviews', d)


def _one(**kw):
    return _rvs(_rv(**kw))['rows'][0]


@needs_node
def test_reviews_failed_source_is_null_and_rows_keep_the_server_facts():
    assert G('reviews', None) is None and G('reviews', {}) is None and G('reviews', {'items': 'x'}) is None
    v = _rvs(_rv(1), _rv(2, status='approved', decided_at='2026-10-29T10:00:00'), _rv(3, status='rejected', admin_note='خارج النطاق'), _rv(4, kind='course', term=None, ref='c-1', ref_title=''))
    assert v['counts'] == {'pending': 2, 'approved': 1, 'rejected': 1, 'all': 4}, 'العدّ من الصفوف لو غاب من الخادم'
    r = v['rows'][0]
    assert (r['id'], r['kindText'], r['isTerm'], r['title'], r['name'], r['specialtyText'], r['verdictText'], r['statusText'], r['pending'], r['createdOn'], r['termId']) == (
        '1', 'مصطلح', True, 'القوة القاهرة', 'د. نادر فؤاد', 'تدريس القانون', 'يؤكد الترجمة والتعريف', 'تنتظر القرار', True, '٢٨ أكتوبر ٢٠٢٦', '5')
    assert r['showNameText'] == 'وافق على ظهور اسمه' and r['term']['statusText'] == 'تحت التأكيد'
    assert v['rows'][1]['statusText'] == 'اعتُمدت' and v['rows'][1]['decidedOn'] == '٢٩ أكتوبر ٢٠٢٦' and v['rows'][2]['note'] == 'خارج النطاق'
    c = v['rows'][3]
    assert c['kindText'] == 'دورة' and c['isTerm'] is False and c['term'] is None and c['title'] == 'c-1', 'بلا عنوان ⇒ المعرّف'
    odd = _one(kind='zzz', status='zzz', verdict='zzz', show_name='yes', specialty_text='', specialty_label='')
    assert odd['kind'] == 'glossary_term' and odd['status'] == 'pending' and odd['verdict'] == 'confirm' and odd['showName'] is False and odd['specialtyText'] == 'أخرى'
    assert _one(verdict='suggest')['suggests'] is True
    server = _rvs(_rv(1), counts={'pending': 9, 'approved': 3, 'rejected': 2, 'all': 14})
    assert server['counts'] == {'pending': 9, 'approved': 3, 'rejected': 2, 'all': 14}


@needs_node
def test_reviews_filters_and_chips_cover_every_status_and_kind():
    rows = _rvs(_rv(1), _rv(2, status='approved'), _rv(3, kind='track', term=None, status='rejected'), _rv(4, kind='course', term=None))['rows']

    def ids(**f):
        return [r['id'] for r in G('filterReviews', rows, f)]
    assert ids(status='pending') == ['1', '4'] and ids(status='approved') == ['2'] and ids(status='rejected') == ['3'] and ids(status='all') == ['1', '2', '3', '4'] and ids() == ids(status='all')
    assert ids(kind='course') == ['4'] and ids(kind='track') == ['3'] and ids(kind='glossary_term') == ['1', '2'] and ids(status='pending', kind='course') == ['4']
    assert [c[1] for c in G('REVIEW_STATUS_CHIPS')] == ['تنتظر القرار', 'اعتُمدت', 'رُفضت', 'الكل'] and [c[1] for c in G('REVIEW_KIND_CHIPS')] == ['الكل', 'مصطلح', 'دورة', 'مسار']
    assert [c[1] for c in G('STATUS_CHIPS')] == ['الكل', 'مؤكّد', 'تحت التأكيد', 'مسودة']
    assert G('reviewCountText', 0) == 'لا مراجعات هنا' and G('reviewCountText', 1) == 'مراجعة واحدة' and G('reviewCountText', 5) == '٥ مراجعات'


@needs_node
def test_approving_a_confirmation_stamps_the_term_and_shows_before_and_after():
    r = _one()
    c = G('approveCheck', r)
    assert c['ok'] and c['body'] == {} and c['goLabel'] == 'اعتمد وضع الختم' and 'سيُختم المصطلح «القوة القاهرة» بأن متخصصًا راجعه' in c['lead']
    assert {'label': 'ختم المصطلح', 'from': 'بلا ختم', 'to': 'د. نادر فؤاد، تدريس القانون'} in c['lines']
    assert {'label': 'حالة المصطلح', 'from': 'تحت التأكيد', 'to': 'مؤكّد'} in c['lines'] and {'label': 'ظهور الاسم للناس', 'from': '', 'to': 'يظهر'} in c['lines']
    assert c['warns'] == ['وتظهر ملاحظة الدول في الصفحة بعد الختم.'], 'مصطلح تحت التأكيد عنده ملاحظة دول'
    assert G('approveCheck', _one(term=_item(5, status='under_review', countries_note_ar=None)))['warns'] == []
    stamped = _one(term=_item(5, status='confirmed', **_reviewed(reviewer_name_public=False)), show_name=False)
    s = G('approveCheck', stamped)
    assert 'يحلّ هذا المراجع محلّ أ. هبة الجندي.' in s['warns'] and 'لن يظهر اسم المراجع للناس، وتقول الصفحة «راجعه متخصص» فقط.' in s['warns']
    assert {'label': 'ظهور الاسم للناس', 'from': 'لا يظهر', 'to': 'لا يظهر'} in s['lines'] and {'label': 'ختم المصطلح', 'from': 'أ. هبة الجندي، محامية', 'to': 'د. نادر فؤاد، تدريس القانون'} in s['lines']
    draft = G('approveCheck', _one(term=_item(5, status='draft')))
    assert any('يُختم ويبقى مسودة حتى تنشره' in w for w in draft['warns']) and {'label': 'حالة المصطلح', 'from': 'مسودة', 'to': 'مسودة'} in draft['lines']
    changed = G('approveCheck', _one(term_changed=True))
    assert changed['ok'] and any('تغيّر نص المصطلح بعد وصول هذه المراجعة' in w for w in changed['warns']), 'التحذير لا يمنع الاعتماد'
    other = G('approveCheck', _one(specialty='other', specialty_other='خبير تحكيم', specialty_text='خبير تحكيم'))
    assert {'label': 'ختم المصطلح', 'from': 'بلا ختم', 'to': 'د. نادر فؤاد، خبير تحكيم'} in other['lines'], '«أخرى» تحمل ما كتبه المتخصص'
    gone = G('approveCheck', _one(term=None))
    assert gone['ok'] is False and gone['error'] == 'المصطلح لم يعد موجودًا'
    done = G('approveDone', r, {'term': {'status': 'confirmed'}})
    assert done == 'اعتُمدت المراجعة وصار المصطلح «القوة القاهرة» مؤكّدًا' and 'يبقى المصطلح مسودة' in G('approveDone', r, {'term': {'status': 'draft'}})


@needs_node
def test_approving_a_suggestion_opens_the_editor_and_leaves_the_term_alone():
    r = _one(verdict='suggest', text='أقترح إضافة شرط عدم إمكان الدفع.')
    c = G('approveCheck', r)
    assert c['ok'] and c['goLabel'] == 'اعتمد وافتح المحرّر' and 'يفتح محرّر المصطلح والاقتراح بجانبه' in c['lead'] and 'ويبقى «تحت التأكيد»' in c['lead']
    assert {'label': 'المراجعة', 'from': 'تنتظر القرار', 'to': 'اعتُمدت'} in c['lines'] and any(l['label'] == 'اقتراحه' and 'شرط عدم إمكان الدفع' in l['to'] for l in c['lines'])
    assert not any(l['label'] == 'ختم المصطلح' for l in c['lines'])
    assert G('approveDone', r, {}) == 'اعتُمد الاقتراح، وعدّل المصطلح من الشاشة المفتوحة'
    sg = G('suggestionView', r)
    assert sg == {'name': 'د. نادر فؤاد', 'specialtyText': 'تدريس القانون', 'text': 'أقترح إضافة شرط عدم إمكان الدفع.', 'title': 'القوة القاهرة', 'termId': '5'} and G('suggestionView', None) is None


@needs_node
def test_course_and_track_reviews_are_marked_done_without_any_stamp():
    for kind, word in (('course', 'الدورة'), ('track', 'المسار')):
        r = _one(kind=kind, ref='x-1', ref_title='عنوان', term=None, verdict='suggest', text='مثال إضافي')
        assert G('approveLabel', r) == 'تمّ' and G('approveLabel', _one()) == 'اعتمد'
        c = G('approveCheck', r)
        assert c['ok'] and c['goLabel'] == 'تمّ' and 'بلا أي ختم' in c['lead'] and word in c['lead'] and 'من المنصة' in c['lead']
        assert {'label': 'المراجعة', 'from': 'تنتظر القرار', 'to': 'تمّ'} in c['lines'] and not any(l['label'] == 'ختم المصطلح' for l in c['lines'])
        assert G('approveDone', r, {}) == 'تمّت المراجعة'


@needs_node
def test_rejecting_takes_an_optional_private_note_and_says_nothing_is_sent():
    r = _one()
    plain = G('rejectCheck', r, {})
    assert plain['ok'] and plain['body'] == {} and plain['goLabel'] == 'ارفض المراجعة' and 'لا يصل إلى صاحب المراجعة أي رد من هنا.' in plain['warns']
    assert {'label': 'المراجعة', 'from': 'تنتظر القرار', 'to': 'رُفضت'} in plain['lines'] and 'ولا يتغيّر المصطلح' in plain['lead']
    noted = G('rejectCheck', r, {'admin_note': '  خارج   النطاق '})
    assert noted['body'] == {'admin_note': 'خارج   النطاق'} and {'label': 'ملاحظتك الخاصة', 'to': 'خارج   النطاق'} in noted['lines']
    long = G('rejectCheck', r, {'admin_note': 'ن' * 501})
    assert long['ok'] is False and 'admin_note' in long['errors'] and G('rejectCheck', r, {'admin_note': 'ن' * 500})['ok'] is True
    assert 'الدورة' in G('rejectCheck', _one(kind='course', term=None), {})['lead'] and G('rejectDone') == 'رُفضت المراجعة'
    for done in (_one(status='approved'), _one(status='rejected')):
        assert G('approveCheck', done)['ok'] is False and G('rejectCheck', done, {})['ok'] is False, 'سبق البتّ فيها'


@needs_node
def test_review_copy_is_clean_arabic_and_the_server_error_text_passes_through():
    r, s = _one(), _one(verdict='suggest', text='اقتراح.')
    c = _one(kind='course', term=None)
    outs = [G('approveCheck', r), G('approveCheck', s), G('approveCheck', c), G('approveCheck', _one(term_changed=True)), G('rejectCheck', r, {'admin_note': 'ملاحظة ٣'}), G('rejectCheck', c, {}),
            G('approveDone', r, {'term': {'status': 'confirmed'}}), G('approveDone', s, {}), G('approveDone', c, {}), G('rejectDone'), G('reviewCountText', 3),
            [x[1] for x in G('REVIEW_STATUS_CHIPS') + G('REVIEW_KIND_CHIPS')], [r['statusText'], r['verdictText'], r['showNameText'], r['createdOn'], r['kindText']]]
    _clean_copy(*outs)
    assert G('writeError', 409, {'error': 'سبق البتّ في هذه المراجعة'}) == 'سبق البتّ في هذه المراجعة'
    assert G('writeError', 404, {'error': 'المراجعة غير موجودة'}) == 'المراجعة غير موجودة'
