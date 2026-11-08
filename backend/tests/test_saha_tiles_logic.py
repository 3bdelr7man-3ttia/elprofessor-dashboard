# -*- coding: utf-8 -*-
"""منطق مربّعات «الساحة» و«الديوان» في الداشبورد (v2s/saha.js، الجزء النقي) — بيتشغّل في node بلا شبكة وبلا DOM.

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_saha_tiles_logic.py

اللي بيثبّته:
  ١. الفرص: النموذج الفاضي يرفض (النوع والنشر صريحان · العنوان · رابط https رسمي) · الإضافة تبعت المكتوب فقط · التعديل يبعت الفرق فقط ويمسح بـ''/[] · «أخرى» في كل قائمة اختيار ·
     البلد «أخرى» برمز حرفين · الشروط ٨×١٦٠ · التواريخ الحقيقية · مدة الإعلان ١..٣٦٥ · النشر والتمييز · لا تغيير ⇒ خطأ.
  ٢. فلتر الطابور بالنوع (منح تشمل الزمالات) · قرار الاعتماد والرفض بسبب (٣..١٤٠ حرفًا).
  ٣. الأخبار: اعتماد/سحب/تعديل بالفرق فقط · التصنيف بينه «أخرى» · غلاف https · جلب الأخبار (١..٨).
  ٤. رابط دورة التحضير (https · المسح · نفس الرابط) · الاستيراد (شكل الملف · عدّاد التجربة · التنبيهات) · الآراء · التذكير («التذكير مقفول» · «لم يُشغَّل بعد» · «تعذّر آخر تشغيل»).
  ٥. الديوان: إجراءات الأعمال حسب الحالة · الرفض بسبب · التمييز بتاريخ · التحديات (اللجنة ثلاثة قبل الفتح · الإغلاق بعد البدء · الجوائز · الفرق فقط · المسح بـnull) ·
     الفائزون (المركز الأول أولًا · لا تكرار · سطر لجنة) · التقرير (الغايب «لا رقم بعد» لا صفر · الصفر الحقيقي ٠ · النسب).
  ٦. النصوص: أرقام هندية و«·» ما تلاصق رقمًا · لا «يقوّم» ولا مصطلحات تقنية · المصدر الفاشل null.
"""
import json
import os
import re
import shutil
import subprocess

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
NODE = shutil.which('node')
needs_node = pytest.mark.skipif(not NODE, reason='needs node')
NOW = 1793361600000          # 2026-10-30T12:00:00Z
APPLY = os.path.join(_HERE, 'uiharness', 'saha_apply.js')
PRELUDE = ("const path=require('path');const DC=%r;require(path.join(DC,'v2-logic.js'));const S=require(path.join(DC,'v2s','saha.js')).v2sSaha;"
           "const out=(x)=>process.stdout.write(JSON.stringify(x));" % os.path.join(ROOT, 'dashboard-cloud'))


def _js(code):
    p = subprocess.run([NODE, '-e', PRELUDE + code], capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    if p.returncode != 0:
        raise RuntimeError('node failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def S(fn, *args):
    p = subprocess.run([NODE, APPLY], input=json.dumps({'fn': fn, 'args': list(args)}, ensure_ascii=False), capture_output=True, text=True, timeout=60, env=dict(os.environ, TZ='UTC'))
    if p.returncode != 0:
        raise RuntimeError('node failed: ' + p.stderr[-1500:])
    return json.loads(p.stdout)


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def _texts(o, out=None):
    out = [] if out is None else out
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            _texts(v, out)
    elif isinstance(o, list):
        for v in o:
            _texts(v, out)
    return out


def _clean_copy(*objs):
    """«·» ما تلاصق رقمًا · لا أرقام لاتينية في النص الظاهر (باستثناء الروابط والإيميلات) · لا كلمات ممنوعة."""
    for t in [x for o in objs for x in _texts(o)]:
        if '@' in t or re.match(r'^[A-Za-z0-9_.:/?#=&%+-]+$', t) or t.startswith('http'):
            continue
        assert not re.search(r'[0-9٠-٩]\s*·|·\s*[0-9٠-٩]', t), t
        assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', t), t
        assert not re.search(r'\bAPI\b|JSON|undefined|NaN|\[object|\bnull\b', t), t
        assert not re.search(r'[0-9]', t), 'رقم لاتيني ظاهر: ' + t


OPP_ROW = {'id': 'job-1', 'title': 'منحة ماجستير القانون', 'kind': 'grant', 'review_status': 'pending', 'provider': 'مؤسسة', 'place': 'لندن', 'country': 'GB', 'language': 'en', 'funding': 'full',
           'eligibility_ar': ['خريج حقوق', 'إجادة الإنجليزية'], 'covers_ar': 'الرسوم', 'deadline': '2026-12-08', 'days_left': 37, 'official_url': 'https://g.example.test/o',
           'source_url': 'https://g.example.test/s', 'image': 'https://i.example.test/c.jpg', 'featured': True, 'created_at': '2026-10-30T09:00:00Z', 'submitted_by': 'a@example.test'}


def _opp_row(**kw):
    return _js("out(S.opps({items:[Object.assign(%s,%s)]},%d).rows[0])" % (json.dumps(OPP_ROW), json.dumps(kw), NOW))


def _form(row=None, **kw):
    f = _js("const r=%s;out(S.oppForm(r))" % json.dumps(row))
    f.update(kw)
    return f


# ---------------------------------------------------------------- ١) الفرص
@needs_node
def test_a_new_opportunity_needs_an_explicit_kind_publish_title_and_https_official_url():
    r = S('oppCheck', _form(None), 'create', None)
    assert not r['ok'] and set(r['errors']) >= {'kind', 'publish', 'title', 'official_url'}
    for url in ('http://x.example.test/a', 'javascript:alert(1)', 'ftp://x.test/a'):
        r = S('oppCheck', _form(None, kind='grant', publish='draft', title='منحة جديدة', official_url=url), 'create', None)
        assert not r['ok'] and 'https' in r['errors']['official_url'], url
    r = S('oppCheck', _form(None, kind='grant', publish='draft', title='من', official_url='https://g.example.test/a'), 'create', None)
    assert not r['ok'] and 'title' in r['errors']
    r = S('oppCheck', _form(None, kind='grant', publish='draft', title='منحة جديدة', source_url='https://s.example.test/x'), 'create', None)
    assert r['ok'] and r['body']['source_url'] == 'https://s.example.test/x'       # رابط المصدر يكفي بدل الرسمي


@needs_node
def test_create_sends_only_what_was_written_and_the_publish_flag_as_a_real_boolean():
    r = S('oppCheck', _form(None, kind='other', publish='published', title='ورشة الكتابة', official_url='https://w.example.test/a', country='other', country_other='jp',
                            funding='varies', eligibility='خريج قانون\n\n إجادة الإنجليزية \n', featured=True, deadline='2026-12-08', expires_in_days='٣٠'), 'create', None)
    assert r['ok'], r
    assert r['body'] == {'kind': 'other', 'publish': True, 'title': 'ورشة الكتابة', 'official_url': 'https://w.example.test/a', 'country': 'JP', 'funding': 'varies',
                         'eligibility_ar': ['خريج قانون', 'إجادة الإنجليزية'], 'featured': True, 'deadline': '2026-12-08', 'expires_in_days': 30}
    assert 'ستُنشر' in r['lead'] and [l['label'] for l in r['lines']][:2] == ['النوع', 'النشر']
    r2 = S('oppCheck', _form(None, kind='job', publish='draft', title='محامٍ للشركات', official_url='https://w.example.test/a'), 'create', None)
    assert r2['body']['publish'] is False and 'مسودة' in r2['lead'] and 'featured' not in r2['body']


@needs_node
def test_every_picker_has_an_other_choice():
    lists = _js("out({kinds:S.OPP_KINDS,langs:S.LANGS,funds:S.FUNDS,cats:S.NEWS_CATS,works:S.WORK_KINDS,prizes:S.PRIZE_TYPES,chips:S.KIND_CHIPS,ccodes:S.COUNTRIES})")
    for k in ('kinds', 'langs', 'works', 'prizes', 'chips'):
        assert any(x[1] == 'أخرى' for x in lists[k]), k
    assert 'أخرى' in lists['cats'] and any(x[1].startswith('أخرى') for x in lists['funds'])
    # البلد: «أخرى» قيمة المنتقي، وتحتها خانة رمز حرفين
    r = S('oppCheck', _form(None, kind='grant', publish='draft', title='منحة جديدة', official_url='https://g.example.test/a', country='other', country_other=''), 'create', None)
    assert not r['ok'] and 'رمز البلد' in r['errors']['country']
    r = S('oppCheck', _form(None, kind='grant', publish='draft', title='منحة جديدة', official_url='https://g.example.test/a', country='other', country_other='Japan'), 'create', None)
    assert not r['ok'] and 'country' in r['errors']
    assert S('countryText', 'JP') == 'أخرى (JP)' and S('countryText', 'online') == 'عبر الإنترنت' and S('kindText', 'weird') == 'أخرى'


@needs_node
def test_validation_limits_match_the_server():
    base = dict(kind='grant', publish='draft', title='منحة جديدة', official_url='https://g.example.test/a')
    cases = [({'eligibility': '\n'.join('شرط %d' % i for i in range(9))}, 'eligibility'), ({'eligibility': 'ا' * 161}, 'eligibility'), ({'covers_ar': 'ا' * 301}, 'covers_ar'),
             ({'deadline': '2026-02-30'}, 'deadline'), ({'deadline': '٢٠٢٦/١٢/٠١'}, 'deadline'), ({'verified_at': 'غدًا'}, 'verified_at'), ({'expires_in_days': '٠'}, 'expires_in_days'),
             ({'expires_in_days': '٣٦٦'}, 'expires_in_days'), ({'expires_in_days': 'x'}, 'expires_in_days'), ({'image': 'http://i.test/a.jpg'}, 'image'), ({'logo_initial': 'ابج'}, 'logo_initial'),
             ({'language': 'xx'}, 'language'), ({'funding': 'zz'}, 'funding'), ({'title': 'ا' * 201}, 'title')]
    for extra, field in cases:
        r = S('oppCheck', _form(None, **dict(base, **extra)), 'create', None)
        assert not r['ok'] and field in r['errors'], (extra, r)
    ok = S('oppCheck', _form(None, **dict(base, expires_in_days='٣٦٥', eligibility='\n'.join('شرط %d' % i for i in range(8)), deadline='2028-02-29')), 'create', None)
    assert ok['ok'] and ok['body']['expires_in_days'] == 365


@needs_node
def test_edit_sends_only_the_difference_clears_with_empty_and_refuses_no_change():
    row = _opp_row()
    same = S('oppCheck', _form(row), 'edit', row)
    assert not same['ok'] and same['error'] == 'لا يوجد تغيير'
    r = S('oppCheck', _form(row, featured=False, image='', eligibility='', deadline='', country='online', funding='', title=row['title']), 'edit', row)
    assert r['ok'], r
    assert r['body'] == {'featured': False, 'image': '', 'eligibility_ar': [], 'deadline': '', 'country': 'online', 'funding': ''}
    labels = [l['label'] for l in r['lines']]
    assert 'التمييز' in labels and 'رابط الصورة' in labels and 'الشروط' in labels and 'العنوان' not in labels
    assert next(l for l in r['lines'] if l['label'] == 'التمييز') == {'label': 'التمييز', 'from': 'نعم', 'to': 'لا'}
    # النشر: المنتظر ⇒ منشورة يبعت publish:true، ومنشورة ⇒ منشورة لا يبعت شيء
    pub = S('oppCheck', _form(row, publish='published'), 'edit', row)
    assert pub['ok'] and pub['body'] == {'publish': True}
    live = _opp_row(review_status='published')
    assert not S('oppCheck', _form(live, publish='published'), 'edit', live)['ok']
    assert S('oppCheck', _form(live, publish='draft'), 'edit', live)['body'] == {'publish': False}
    # مسح الرابط الرسمي أو رابط المصدر عند التعديل تردّه المنصة ٤٢٢ فيُمنع هنا؛ والصورة تُمسح
    gone = S('oppCheck', _form(row, official_url=''), 'edit', row)
    assert not gone['ok'] and 'official_url' in gone['errors'] and 'مطلوب' in gone['errors']['official_url']
    gone = S('oppCheck', _form(row, source_url=''), 'edit', row)
    assert not gone['ok'] and 'source_url' in gone['errors']
    assert S('oppCheck', _form(row, image=''), 'edit', row)['body'] == {'image': ''}
    # بلد «أخرى» بعد تعديل بلد معروف
    other = S('oppCheck', _form(row, country='other', country_other='jp'), 'edit', row)
    assert other['body'] == {'country': 'JP'} and other['lines'][0]['from'] == 'المملكة المتحدة' and other['lines'][0]['to'] == 'أخرى (JP)'


@needs_node
def test_rows_filters_and_review_decisions():
    got = _js("""const rows=S.opps({items:[{id:'a',kind:'grant',review_status:'pending',title:'منحة'},{id:'b',kind:'fellowship',review_status:'pending',title:'زمالة'},{id:'c',kind:'job',review_status:'pending',title:'وظيفة'},
      {id:'d',kind:'training',review_status:'published',title:'تدريب'},{id:'e',kind:'competition',review_status:'draft',title:'مسابقة'},{id:'f',kind:'other',review_status:'rejected',title:'غير ذلك'},{id:'g',kind:'weird',review_status:'pending',title:'غريب'}]},0).rows;
      out({all:S.oppFilter(rows,'all').length,grants:S.oppFilter(rows,'grants').map(r=>r.id),job:S.oppFilter(rows,'job').map(r=>r.id),other:S.oppFilter(rows,'other').map(r=>r.id),
           training:S.oppFilter(rows,'training').length,pending:rows.filter(r=>r.pending).length,txt:S.pendingText(0)+'|'+S.pendingText(1)+'|'+S.pendingText(2)+'|'+S.pendingText(5)+'|'+S.pendingText(11)})""")
    assert got['all'] == 7 and got['grants'] == ['a', 'b'] and got['job'] == ['c'] and got['other'] == ['f', 'g'] and got['training'] == 1 and got['pending'] == 4
    assert got['txt'] == 'لا إعلانات تنتظر|إعلان واحد ينتظر|إعلانان ينتظران|٥ إعلانات تنتظر|١١ إعلانًا ينتظر'
    row = _opp_row()
    assert S('oppDecision', 'approve', '', row)['body'] == {'decision': 'approve'}
    for bad in ('', 'ab', '   '):
        assert not S('oppDecision', 'reject', bad, row)['ok']
    assert not S('oppDecision', 'reject', 'ا' * 141, row)['ok']
    rej = S('oppDecision', 'reject', '  الرابط لا يعمل ', row)
    assert rej['ok'] and rej['body'] == {'decision': 'reject', 'reason': 'الرابط لا يعمل'}


@needs_node
def test_rows_never_invent_numbers_or_trust_urls():
    r = _js("out(S.opps({items:[{id:'x',title:'بلا تفاصيل',kind:'job',review_status:'draft',official_url:'javascript:alert(1)',image:'data:x',deadline:'',days_left:null}]},0).rows[0])")
    assert r['officialUrl'] == '' and r['image'] == '' and r['deadlineText'] == '' and r['reviewText'] == 'مسودة'
    assert _js("out(S.opps({}, 0))") is None and _js("out(S.opps({items:'x'}, 0))") is None and _js("out(S.news(null,0))") is None
    expired = _opp_row(days_left=-3)
    assert 'انتهى الموعد' in expired['deadlineText'] and expired['expired']
    today = _opp_row(days_left=0)
    assert 'اليوم' in today['deadlineText']


# ---------------------------------------------------------------- ٣) الأخبار
@needs_node
def test_news_intents_send_status_and_only_changed_fields():
    row = _js("out(S.news({items:[{id:'n-1',title:'قانون جديد',summary:'ملخص',category:'أحكام',featured:false,cover_url:'',status:'draft',source_name:'م',source_url:'https://s.test/a',created_at:'2026-10-30T08:00:00Z'}]},%d).rows[0])" % NOW)
    form = _js("out(S.newsForm(%s))" % json.dumps(row))
    ok = S('newsCheck', form, row, 'approve')
    assert ok['ok'] and ok['body'] == {'status': 'published'} and ok['lines'][0] == {'label': 'الحالة', 'from': 'مسودة', 'to': 'منشور'}
    edited = S('newsCheck', dict(form, title='قانون جديد للعمل', featured=True, cover_url='https://i.example.test/c.jpg', category='أخرى'), row, 'approve')
    assert edited['body'] == {'status': 'published', 'title': 'قانون جديد للعمل', 'featured': True, 'cover_url': 'https://i.example.test/c.jpg', 'category': 'أخرى'}
    assert S('newsCheck', form, row, 'unpublish')['body'] == {'status': 'draft'}
    assert not S('newsCheck', form, row, 'edit')['ok'] and S('newsCheck', form, row, 'edit')['error'] == 'لا يوجد تغيير'
    for bad, field in (({'title': ''}, 'title'), ({'cover_url': 'http://x.test/a.jpg'}, 'cover_url'), ({'category': 'غير معروف'}, 'category'), ({'summary': 'ا' * 2001}, 'summary')):
        r = S('newsCheck', dict(form, **bad), row, 'approve')
        assert not r['ok'] and field in r['errors'], bad
    assert S('newsRunCheck', {'limit': ''})['body'] == {}
    assert S('newsRunCheck', {'limit': '٣'})['body'] == {'per_country_limit': 3}
    assert not S('newsRunCheck', {'limit': '٩'})['ok'] and not S('newsRunCheck', {'limit': '٠'})['ok']
    assert S('newsRunDone', {'total_created': 0}) == 'اكتمل الجلب، ولم تُضَف مسودات جديدة' and S('newsRunDone', {'total_created': 2}) == 'أُضيفت مسودتان تنتظر مراجعتك'


# ---------------------------------------------------------------- ٤) الرابط · الاستيراد · الآراء · التذكير
@needs_node
def test_prep_url_seed_file_and_seed_numbers():
    assert S('prepCheck', 'http://x.test/a', 'https://old.test/a', False)['error'] == 'يجب أن يبدأ الرابط بـ https'
    assert S('prepCheck', '', '', False)['error'].startswith('اكتب الرابط')
    assert S('prepCheck', 'https://old.test/a', 'https://old.test/a', False)['error'] == 'هذا هو الرابط المحفوظ الآن'
    ok = S('prepCheck', ' https://new.test/a ', 'https://old.test/a', False)
    assert ok['ok'] and ok['url'] == 'https://new.test/a' and ok['lines'] == [{'label': 'رابط دورة التحضير', 'from': 'https://old.test/a', 'to': 'https://new.test/a'}]
    assert S('prepCheck', '', 'https://old.test/a', True)['url'] == '' and not S('prepCheck', '', '', True)['ok']
    assert S('seedCheck', {'items': [{'a': 1}]}) == {'ok': True, 'count': 1}
    for bad in (None, [], {}, {'items': 'x'}, {'items': [1]}, {'items': [[]]}, {'items': [{}] * 501}):
        assert not S('seedCheck', bad)['ok'], bad
    v = S('seedView', {'created': 34, 'filled': 1, 'skipped_unverified': 4, 'unchanged': 2, 'warnings': ['الصف 7: لا تاريخ تحقق', 5], 'dry_run': True})
    assert [r['n'] for r in v['rows']] == [34, 1, 4, 2] and v['changes'] == 35 and v['warnings'] == ['الصف ٧: لا تاريخ تحقق'] and v['dry']
    assert S('seedView', {})['changes'] == 0 and S('seedView', None) is None
    assert S('seedDone', v) == 'تم الاستيراد: ٣٤ فرصة جديدة، وأُكمل ما ينقص فرصة'
    _clean_copy(v, S('seedDone', v))


@needs_node
def test_opinions_and_topics_rows():
    got = _js("""out(S.opinions({items:[{id:'o1',status:'pending',body:'رأي',author_email:'a@x.test',is_expert:true,topic_title:'نقاش'},{id:'o2',status:'approved',body:'ب'},{id:'o3',status:'rejected',body:'ج'}]},0))""")
    rows = {r['id']: r for r in got['rows']}
    assert rows['o1']['canHide'] and rows['o1']['canShow'] and rows['o1']['authorText'] == 'خبير' and rows['o1']['showLabel'] == 'أظهره'
    assert rows['o2']['canHide'] and not rows['o2']['canShow'] and not rows['o3']['canHide'] and rows['o3']['canShow'] and rows['o3']['showLabel'] == 'أعد إظهاره'
    assert rows['o3']['statusText'] == 'مخفي' and got['countText'] == '٣ آراء'
    assert S('opinionAction', 'hide', {})['goLabel'] == 'أخفِ الرأي' and S('opinionAction', 'show', {})['goLabel'] == 'أظهر الرأي'
    t = S('topics', {'items': [{'id': 't1', 'title': 'نقاش'}, {'title': 'بلا معرّف'}]})
    assert [(r['id'], r['title']) for r in t['rows']] == [('t1', 'نقاش')] and t['countText'] == 'نقاش واحد'


@needs_node
def test_topic_rows_show_the_legal_gate_and_the_hide_restore_sheet():
    """R17 — النقاش المختوم ok:false «مخفي» (يدويًا أو لعدم الصلة) وزرّه «أرجِع»؛ الغايب أو الختم المجهول ⇒ ظاهر."""
    t = S('topics', {'items': [{'id': 'a', 'title': 'أ', 'status': 'open', 'opinions_count': 3, 'legal': {'ok': False, 'by': 'human'}},
                               {'id': 'b', 'title': 'ب', 'status': 'open', 'legal': {'ok': False, 'by': 'rule'}},
                               {'id': 'c', 'title': 'ج', 'status': 'open', 'legal': {'ok': None}},
                               {'id': 'd', 'title': 'د', 'status': 'zzz'}]})
    rows = {r['id']: r for r in t['rows']}
    assert rows['a']['hidden'] and rows['a']['hiddenText'] == 'مخفي يدويًا' and rows['a']['opinions'] == 3
    assert rows['b']['hidden'] and rows['b']['hiddenText'] == 'مخفي لعدم الصلة بالقانون'
    assert not rows['c']['hidden'] and rows['c']['statusText'] == 'مفتوح' and rows['d']['statusText'] == 'حالة غير معروفة'
    assert rows['d']['opinions'] is None                                   # الغايب «لا رقم» مش صفر
    assert t['hiddenCount'] == 2 and t['countText'] == '٤ نقاشات'
    assert S('topicAction', 'hide')['goLabel'] == 'أخفِ النقاش' and S('topicAction', 'show')['goLabel'] == 'أرجِع النقاش'
    _clean_copy(t, S('topicAction', 'hide'), S('topicAction', 'show'))


@needs_node
def test_gate_check_view_counts_lists_reasons_and_marks_missing_sources():
    resp = {'applied': False, 'collections': {
        'news': {'would_hide': 2, 'hidden': [{'id': 'n1', 'title': 'خبر رياضي', 'reason': 'off-theme'}, {'id': 'n2', 'title': '', 'reason': 'negative'}, {'title': 'بلا معرّف'}]},
        'topics': {'would_hide': 0, 'hidden': []}, 'articles': None}}
    v = S('gateView', resp)
    assert [(c['key'], c['n']) for c in v['counts']] == [('news', 2), ('topics', 0)] and v['failed'] == ['المقالات']
    assert [(r['id'], r['kind'], r['title'], r['reason']) for r in v['rows']] == [
        ('n1', 'الأخبار', 'خبر رياضي', 'لا يتناول موضوعًا قانونيًا'), ('n2', 'الأخبار', 'بلا عنوان', 'حوادث أو سياسة أو منوّعات')]
    assert v['total'] == 2 and v['applied'] is False and v['totalText'] == 'عنصران غير مرتبطين بالقانون'
    assert S('gateReason', 'zzz') == 'غير مرتبط بالقانون'
    assert S('gateView', {'collections': {}})['totalText'] == 'كل ما فُحص مرتبط بالقانون'
    assert S('gateView', None) is None and S('gateView', {'x': 1}) is None
    done = S('gateDone', dict(v, total=12))
    assert done == 'أُخفي ١٢ عنصرًا من الساحة، ويمكن إرجاع أي نقاش منها'
    assert S('gateDone', dict(v, total=0)) == 'لم يكن هناك ما يُخفى'
    _clean_copy(v, done)


@needs_node
def test_reminder_states_tile_and_run_text():
    last = {'at': '2026-10-30T11:00:00Z', 'ok': True, 'trigger': 'cron', 'opportunities': 3, 'sent': 5, 'skipped_already': 1, 'skipped_toggle_off': 2, 'errors': 0, 'enabled': True}
    v = _js("out(S.reminders({last:%s,enabled:true,locked:false},%d))" % (json.dumps(last), NOW))
    assert v['kind'] == 'ok' and v['headline'] == 'التذكير مفتوح' and v['sent'] == 5 and 'تشغيل تلقائي' in v['when'] and [r['n'] for r in v['rows']] == [3, 5, 1, 2, 0]
    assert _js("out(S.reminderTile(S.reminders({last:%s,enabled:true,locked:false},%d)))" % (json.dumps(last), NOW)) == {'n': '٥', 'sub': 'تذكير أُرسل في آخر تشغيل', 'hot': False}
    locked = _js("out(S.reminders({last:%s,enabled:false,locked:true},%d))" % (json.dumps(dict(last, enabled=False, sent=0)), NOW))
    assert locked['kind'] == 'locked' and locked['headline'] == 'التذكير مقفول' and locked['rows'] == []
    tile = _js("out(S.reminderTile(S.reminders({last:%s,enabled:false,locked:true},%d)))" % (json.dumps(dict(last, enabled=False)), NOW))
    assert tile['sub'] == 'التذكير مقفول' and tile['n'] == 'مقفول' and tile['off']
    never = _js("out(S.reminders({last:null,enabled:null,locked:false},%d))" % NOW)
    assert never['kind'] == 'never' and never['headline'] == 'لم يُشغَّل بعد'
    assert _js("out(S.reminderTile(S.reminders({last:null,enabled:null,locked:false},0)))")['sub'] == 'لم يُشغَّل بعد'
    failed = _js("out(S.reminders({last:{at:'2026-10-30T11:00:00Z',ok:false,trigger:'cron'},enabled:null,locked:false},%d))" % NOW)
    assert failed['kind'] == 'failed' and failed['headline'] == 'تعذّر آخر تشغيل'
    assert _js("out(S.reminders(null,0))") is None and _js("out(S.reminders({},0))") is None and S('reminderTile', None)['sub'] == 'غير متاح بعد'
    assert S('reminderRunDone', {'enabled': False, 'locked': True, 'sent': 0}) == 'التذكير مقفول، فلم يُرسَل شيء'
    assert S('reminderRunDone', {'enabled': True, 'sent': 5, 'errors': 0}) == 'أُرسل ٥ تذكيرات'
    assert S('reminderRunDone', {'enabled': True, 'sent': 1, 'errors': 2}) == 'أُرسل تذكير واحد، وتعذّر تذكيران'
    assert S('reminderRunDone', {'enabled': True, 'sent': 0, 'errors': 0}) == 'اكتمل التشغيل ولم يكن هناك ما يُرسل'
    _clean_copy(v, locked, never, failed)


# ---------------------------------------------------------------- ٥) الديوان
def _work(**kw):
    w = {'id': 'CR_1', 'title': 'ليلة في المحكمة', 'kind': 'story', 'status': 'pending_review', 'creator_name': 'كاتب', 'creator_email': 'w@example.test', 'featured': False, 'comments_locked': False,
         'likes': 0, 'comments_count': None, 'created_at': '2026-10-31T10:00:00Z', 'media_url': 'javascript:x', 'ai_assisted': True}
    w.update(kw)
    return _js("out(S.works({items:[%s]},%d).rows[0])" % (json.dumps(w), NOW))


@needs_node
def test_work_actions_depend_on_status_and_every_write_is_explicit():
    def acts(**kw):
        return [a[0] for a in S('workActions', _work(**kw))]
    assert acts() == ['approve', 'reject']
    assert acts(status='published') == ['feature', 'lock', 'hide']
    assert acts(status='published', featured=True, comments_locked=True) == ['unfeature', 'unlock', 'hide']
    assert acts(status='hidden') == ['show'] and acts(status='rejected') == []
    # مميَّز بتاريخ لم ينتهِ (ومنه أسبوع الفائزين) ⇒ «ألغِ التمييز»، وبعد انتهائه ⇒ «ميّز» ولا يظهر تاريخه
    assert acts(status='published', featured_until='2026-12-01T21:59:59+00:00')[0] == 'unfeature'
    assert acts(status='published', featured_until='2026-10-01T21:59:59+00:00')[0] == 'feature'
    assert _work(featured_until='2026-12-01T21:59:59+00:00')['featured'] and _work(featured_until='2026-12-01T21:59:59+00:00')['featuredUntil'] == '2026-12-01'
    assert _work(featured_until='2026-10-01T21:59:59+00:00')['featuredUntil'] == '' and not _work(featured_until='2026-10-01T21:59:59+00:00')['featured']
    w = _work()
    assert w['mediaUrl'] == '' and w['comments'] is None and w['likes'] == 0 and w['ai']      # الغايب null لا صفر، والرابط غير الآمن يضيع
    assert S('workAction', 'approve', w, {})['body'] == {'decision': 'approve'}
    assert not S('workAction', 'reject', w, {'reason': 'لا'})['ok'] and not S('workAction', 'reject', w, {'reason': 'ا' * 141})['ok'] and not S('workAction', 'reject', w, {'reason': 'سبب', 'note': 'ا' * 1001})['ok']
    rej = S('workAction', 'reject', w, {'reason': ' لا يناسب التحدّي ', 'note': ' نرحب بمشاركتك '})
    assert rej['ok'] and rej['op'] == 'decide' and rej['body'] == {'decision': 'reject', 'reason': 'لا يناسب التحدّي', 'note': 'نرحب بمشاركتك'}
    assert S('workAction', 'feature', w, {'until': ''})['body'] == {'featured': True}
    # بتاريخ نهاية: التاريخ وحده (آخر لحظة من اليوم) ولا تثبيت، وإلا ظل العمل مميَّزًا بعد التاريخ
    assert S('workAction', 'feature', w, {'until': '2026-12-01'})['body'] == {'featured': False, 'featured_until': '2026-12-01T23:59:59+02:00'} and not S('workAction', 'feature', w, {'until': '2026-13-01'})['ok']
    assert S('workAction', 'unfeature', w, {})['body'] == {'featured': False, 'featured_until': ''}
    assert S('workAction', 'hide', w, {})['body'] == {'status': 'hidden'} and S('workAction', 'show', w, {})['body'] == {'status': 'published'}
    assert S('workAction', 'lock', w, {})['body'] == {'comments_locked': True} and S('workAction', 'unlock', w, {})['body'] == {'comments_locked': False}
    assert all(S('workAction', k, w, {'reason': 'سبب كافٍ'})['op'] == ('decide' if k in ('approve', 'reject') else 'patch') for k in ('approve', 'reject', 'feature', 'unfeature', 'hide', 'show', 'lock', 'unlock'))
    assert not S('workAction', 'delete', w, {})['ok']
    _clean_copy(S('workAction', 'feature', w, {'until': '2026-12-01'}), rej, w)


CH = {'id': 'CH_2', 'title': 'تحدّي القصة', 'brief': 'اكتب قصة', 'kind_allowed': ['story', 'poem'], 'word_cap': 800, 'opens_at': '2026-10-01T00:00:00+00:00', 'closes_at': '2026-10-25T00:00:00+00:00', 'results_at': '',
      'status': 'closed', 'prizes': [{'type': 'certificate', 'label': 'شهادة', 'ref': '', 'place': 1}], 'jury': [{'name': 'د. سلمى', 'title': 'أستاذة'}], 'sponsor': None, 'cover_url': '', 'entries_count': 3}


def _ch_row(**kw):
    return _js("out(S.challenges({items:[Object.assign(%s,%s)]},%d).rows[0])" % (json.dumps(CH), json.dumps(kw), NOW))


def _ch_form(row=None, **kw):
    f = _js("const r=%s;out(S.challengeForm(r))" % json.dumps(row))
    f.update(kw)
    return f


JURY3 = [{'name': 'د. منى', 'title': ''}, {'name': 'أ. كريم', 'title': 'محامٍ'}, {'name': 'أ. ريم', 'title': ''}]


@needs_node
def test_challenge_create_rules():
    r = S('challengeCheck', _ch_form(None), 'create', None)
    assert not r['ok'] and set(r['errors']) >= {'title', 'kinds', 'opens_at', 'closes_at'}
    base = dict(title='تحدّي الرسالة', kinds=['story'], opens_at='2026-12-01', closes_at='2026-12-20', status='draft')
    ok = S('challengeCheck', _ch_form(None, **base), 'create', None)
    assert ok['ok'] and ok['body'] == {'title': 'تحدّي الرسالة', 'kind_allowed': ['story'], 'opens_at': '2026-12-01', 'closes_at': '2026-12-20T23:59:59+02:00', 'status': 'draft'} and 'مسودة' in ok['lead']
    early = S('challengeCheck', _ch_form(None, **dict(base, closes_at='2026-12-01')), 'create', None)
    assert not early['ok'] and early['errors']['closes_at'] == 'يجب أن يكون الإغلاق بعد البدء'
    # الفتح يطلب لجنة من ثلاثة بالظبط
    for jury in ([], JURY3[:2], JURY3 + [{'name': 'رابع', 'title': ''}]):
        r = S('challengeCheck', _ch_form(None, **dict(base, status='open', jury=jury)), 'create', None)
        assert not r['ok'] and 'ثلاثة أعضاء' in r['errors']['jury'], len(jury)
    opened = S('challengeCheck', _ch_form(None, **dict(base, status='open', jury=JURY3 + [{'name': '', 'title': ''}])), 'create', None)
    assert opened['ok'] and opened['body']['status'] == 'open' and len(opened['body']['jury']) == 3 and 'سيُفتح' in opened['lead']
    assert not S('challengeCheck', _ch_form(None, **dict(base, status='closed')), 'create', None)['ok']          # الإنشاء مسودة أو مفتوح فقط
    # الجوائز: «أخرى» تُكتب شهادة باسمها الحر، والمركز ١..٣، والصف الفاضي يسقط
    pr = S('challengeCheck', _ch_form(None, **dict(base, prizes=[{'type': 'other', 'label': 'درع الديوان', 'ref': '', 'place': '١'}, {'type': 'book', 'label': 'كتاب', 'ref': 'book-1', 'place': ''},
                                                                    {'type': 'book', 'label': '', 'ref': '', 'place': ''}])), 'create', None)
    assert pr['ok'] and pr['body']['prizes'] == [{'type': 'certificate', 'label': 'درع الديوان', 'ref': '', 'place': 1}, {'type': 'book', 'label': 'كتاب', 'ref': 'book-1'}]
    for bad in ({'type': 'book', 'label': 'ا' * 81, 'ref': '', 'place': ''}, {'type': 'book', 'label': 'كتاب', 'ref': '', 'place': '٤'}, {'type': 'nope', 'label': 'كتاب', 'ref': '', 'place': ''}):
        assert not S('challengeCheck', _ch_form(None, **dict(base, prizes=[bad])), 'create', None)['ok'], bad
    assert not S('challengeCheck', _ch_form(None, **dict(base, prizes=[{'type': 'book', 'label': 'ك', 'ref': '', 'place': ''}] * 7)), 'create', None)['ok']
    # السقف والراعي والغلاف
    assert S('challengeCheck', _ch_form(None, **dict(base, word_cap='٥٠٠')), 'create', None)['body']['word_cap'] == 500
    assert not S('challengeCheck', _ch_form(None, **dict(base, word_cap='٢٠٠٠١')), 'create', None)['ok']
    sp = S('challengeCheck', _ch_form(None, **dict(base, sponsor_name='شركة', sponsor_logo='https://l.example.test/a.png', cover_url='https://c.example.test/a.png')), 'create', None)
    assert sp['body']['sponsor'] == {'name': 'شركة', 'logo_url': 'https://l.example.test/a.png'} and sp['body']['cover_url'] == 'https://c.example.test/a.png'
    assert not S('challengeCheck', _ch_form(None, **dict(base, sponsor_name='شركة', sponsor_logo='http://l.test/a.png')), 'create', None)['ok']
    assert not S('challengeCheck', _ch_form(None, **dict(base, sponsor_logo='https://l.example.test/a.png')), 'create', None)['ok']


@needs_node
def test_challenge_edit_sends_only_changes_and_clears_with_null():
    row = _ch_row(word_cap=800, sponsor={'name': 'راعٍ', 'logo_url': 'https://l.example.test/a.png'})
    assert not S('challengeCheck', _ch_form(row), 'edit', row)['ok']
    r = S('challengeCheck', _ch_form(row, brief='وصف جديد', word_cap='', sponsor_name='', sponsor_logo=''), 'edit', row)
    assert r['ok'] and r['body'] == {'brief': 'وصف جديد', 'word_cap': None, 'sponsor': None}
    assert {l['label'] for l in r['lines']} == {'الوصف', 'سقف الكلمات', 'الراعي'} and next(l for l in r['lines'] if l['label'] == 'سقف الكلمات')['to'] == 'بلا سقف'
    st = S('challengeCheck', _ch_form(row, status='open', kinds=['poem', 'other']), 'edit', row)
    assert st['body'] == {'kind_allowed': ['poem', 'other'], 'status': 'open'}
    assert not S('challengeCheck', _ch_form(row, kinds=['poem', 'story']), 'edit', row)['ok']       # نفس الأنواع بترتيب آخر ليست تغييرًا
    results = _ch_row(status='results')
    f = _ch_form(results)
    assert f['status'] == 'results' and not S('challengeCheck', f, 'edit', results)['ok']     # الحالة «أُعلنت النتائج» لا تتحول بالتعديل
    assert S('challengeCheck', dict(f, brief='وصف أحدث'), 'edit', results)['body'] == {'brief': 'وصف أحدث'}
    dates = S('challengeCheck', _ch_form(row, results_at='2026-11-05'), 'edit', row)
    assert dates['body'] == {'results_at': '2026-11-05'} and dates['lines'][0]['from'] == 'فارغ'


@needs_node
def test_winners_rules_first_place_first_no_duplicates_and_a_jury_line():
    entries = [{'id': 'CR_4', 'title': 'حكاية القاضي', 'creator': 'كاتب'}, {'id': 'CR_5', 'title': 'رسالة', 'creator': ''}, {'id': 'CR_6', 'title': 'دفتر', 'creator': 'ك'}]

    def chk(rows):
        return S('winnersCheck', {'rows': rows}, entries)
    E = {'work_id': '', 'jury_line': ''}
    assert chk([E, E, E])['error'] == 'اختر فائزًا واحدًا على الأقل'
    assert 'الأول' in chk([E, {'work_id': 'CR_4', 'jury_line': 'جيد'}, E])['error']
    assert 'سطر اللجنة' in chk([{'work_id': 'CR_4', 'jury_line': ''}, E, E])['error']
    assert 'لا يتكرر' in chk([{'work_id': 'CR_4', 'jury_line': 'أ'}, {'work_id': 'CR_4', 'jury_line': 'ب'}, E])['error']
    assert not chk([{'work_id': 'CR_4', 'jury_line': 'ا' * 141}, E, E])['ok']
    assert 'الثاني' in chk([{'work_id': 'CR_4', 'jury_line': 'أ'}, E, {'work_id': 'CR_5', 'jury_line': 'ب'}])['error']
    assert 'الثالث' in chk([E, E, {'work_id': '', 'jury_line': 'سطر بلا عمل'}])['error']
    ok = chk([{'work_id': 'CR_4', 'jury_line': ' أجمل بداية '}, {'work_id': 'CR_5', 'jury_line': 'لغة نقية'}, E])
    assert ok['ok'] and ok['body'] == {'winners': [{'place': 1, 'work_id': 'CR_4', 'jury_line': 'أجمل بداية'}, {'place': 2, 'work_id': 'CR_5', 'jury_line': 'لغة نقية'}]}
    assert ok['lines'][0] == {'label': 'المركز الأول', 'to': 'حكاية القاضي (كاتب) — «أجمل بداية»'} and 'راجع الأسماء جيدًا' in ok['lead']
    assert S('winnersDone', {'already': True}) == 'سبق إعلان نتيجة هذا التحدّي، ولم يتغير شيء'
    assert S('winnersDone', {'certificates': [{}, {}], 'emails_sent': 2}) == 'أُعلنت النتيجة، وأُصدرت شهادتان، وأُرسل بريدان'
    _clean_copy(ok, S('winnersDone', {'certificates': [{}], 'emails_sent': 0}))


@needs_node
def test_report_missing_is_never_zero_and_real_zero_stays_zero():
    empty = _js("out(S.report({window_days:30,visitors:null,legal_open_share:null,signups:null,share_card_clicks:0,return_7d:null,entries_per_challenge:null,works_acceptance:null}))")
    by = {c['key']: c for c in empty['cards']}
    assert by['visitors']['na'] and by['visitors']['text'] == 'لا رقم بعد' and by['signups']['na'] and by['return_7d']['text'] == 'لا رقم بعد'
    assert not by['share_card_clicks']['na'] and by['share_card_clicks']['text'] == '٠'
    assert empty['acceptance']['na'] and empty['acceptance']['text'] == 'لا رقم بعد' and empty['challenges'] is None and empty['daysText'] == 'آخر ٣٠ يومًا'
    full = _js("out(S.report({window_days:7,visitors:1240,legal_open_share:0.35,signups:18,share_card_clicks:57,return_7d:0.31,entries_per_challenge:[{title:'تحدّي',entries:3},{title:'آخر',entries:null}],works_acceptance:{submitted:4,accepted:3,ratio:0.75}}))")
    by = {c['key']: c for c in full['cards']}
    assert by['visitors']['text'] == '١٬٢٤٠' and by['legal_open_share']['text'] == '٣٥٪' and not any(c['na'] for c in full['cards'])
    assert by['return_7d']['text'] == '٣١٪'          # نسبة من صفر إلى واحد من المنصة لا عدد
    assert full['acceptance'] == {'na': False, 'text': '٣ من ٤', 'pct': '٧٥٪'} and full['challenges'] == [{'title': 'تحدّي', 'n': 3}, {'title': 'آخر', 'n': None}] and full['daysText'] == 'آخر ٧ أيام'
    assert S('report', None) is None and S('report', 'x') is None and S('reportTile', None)['sub'] == 'غير متاح بعد'
    assert S('reportTile', empty)['sub'] == 'لا رقم بعد' and S('reportTile', full)['n'] == '١٬٢٤٠'
    _clean_copy(empty, full)


@needs_node
def test_comments_and_challenge_rows_and_empty_sources():
    c = _js("out(S.comments({items:[{id:'c1',display_name:'قارئ',user_email:'a@x.test',body:'جميل',work_title:'عمل',status:'visible'},{id:'c2',user_email:'b@x.test',body:'ب',status:'hidden'}]},0))")
    assert [r['hidden'] for r in c['rows']] == [False, True] and c['rows'][1]['name'] == 'b@x.test' and c['countText'] == 'تعليقان'
    ch = _js("out(S.challenges({items:[%s,{id:'CH_3',title:'مفتوح',status:'open',entries_count:null}]},0))" % json.dumps(CH))
    assert [r['canWinners'] for r in ch['rows']] == [True, False] and ch['open'] == 1 and ch['rows'][1]['entries'] is None and ch['rows'][0]['datesText'] == 'يبدأ ١ أكتوبر ٢٠٢٦، يُغلق ٢٥ أكتوبر ٢٠٢٦'
    for fn in ('works', 'comments', 'challenges', 'opinions', 'news', 'opps'):
        assert _js("out(S.%s(null,0))" % fn) is None and _js("out(S.%s({},0))" % fn) is None, fn
    _clean_copy(c, ch)


# ---------------------------------------------------------------- ٦) النصوص والأخطاء
@needs_node
def test_write_errors_pass_the_platform_text_and_never_sound_like_a_rejection_when_lost():
    assert S('writeError', 422, {'error': 'أكمل عنوان الإعلان قبل النشر'}) == 'أكمل عنوان الإعلان قبل النشر'
    assert S('writeError', 409, {'error': 'الوظائف تُقفل ولا تُحذف'}) == 'الوظائف تُقفل ولا تُحذف'
    assert S('writeError', 404, {'error': 'العمل غير موجود 12'}) == 'العمل غير موجود ١٢'
    assert S('writeError', 404, {}) == 'لم يعد هذا العنصر موجودًا على المنصة'
    lost = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
    assert S('writeError', 502, {'error': lost, 'no_reply': True}) == lost
    assert S('writeError', 401, {}) == 'انتهت الجلسة، سجّل الدخول من جديد ثم جرّب'
    assert S('writeError', 500, {'error': 'x'}) == 'تعذّر تنفيذ العملية، حاول مرة أخرى' and S('writeError', 0, None) == 'تعذّر تنفيذ العملية، حاول مرة أخرى'


@needs_node
def test_all_visible_copy_is_clean_arabic():
    js = _read('dashboard-cloud', 'v2s', 'saha.js') + _read('dashboard-cloud', 'v2s', 'saha_diwan.js')
    js = re.sub(r'/\*.*?\*/', '', js, flags=re.S)
    js = '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in js.split('\n'))
    strings = ' '.join(re.findall(r"'([^'\n]*[؀-ۿ][^'\n]*)'", js))
    assert not re.search('ي[ً-ْ]*ق[ً-ْ]*و[ً-ْ]*ّ?[ً-ْ]*م', strings)
    assert not re.search(r'[\d٠-٩]\s*·|·\s*[\d٠-٩]', strings)
    assert not re.search(r'\b(API|JSON|token|endpoint|bridge|dry_run|DeepSeek|Claude)\b', strings)
    assert 'أخرى' in strings and 'غير متاح بعد' in strings and 'أعد المحاولة' in strings and 'التذكير مقفول' in strings and 'لا رقم بعد' in strings
    assert not re.search(r'تقييم|تقوّم|يقوّم', strings)
    # لا عنوان يبدأ بـ«الذكاء»
    assert not re.search(r"(title|name|label):\s*'الذكاء", js)


@needs_node
def test_platform_english_messages_never_reach_the_screen():
    ar_msg = S('writeError', 409, {'error': 'الوظائف تُقفل ولا تُحذف'})
    assert ar_msg == 'الوظائف تُقفل ولا تُحذف'
    for status, want in ((404, 'لم يعد'), (409, 'تغيّرت حالة'), (400, 'لم تقبل'), (422, 'لم تقبل')):
        got = S('writeError', status, {'error': 'Job not found'})
        assert want in got and not any('a' <= c.lower() <= 'z' for c in got), (status, got)


@needs_node
def test_jobs_cannot_be_deleted_and_challenge_close_is_end_of_day():
    job = _opp_row(kind='job')
    assert job['isJob'] and not _opp_row(kind='training')['isJob']
    ch = S('challengeCheck', _ch_form(None, title='تحدّي الرسالة', kinds=['story'], opens_at='2026-12-01', closes_at='2026-12-20', status='draft'), 'create', None)
    assert ch['body']['closes_at'].endswith('T23:59:59+02:00') and ch['body']['opens_at'] == '2026-12-01'
    assert [l for l in ch['lines'] if l['label'] == 'يُغلق'][0]['to'] == '٢٠ ديسمبر ٢٠٢٦'
