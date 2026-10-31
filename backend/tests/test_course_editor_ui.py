# -*- coding: utf-8 -*-
"""محرّر الدورات — الجزء النقي والواجهة (SPEC-C-courses §C1).

Run:  cd backend && python3 -B -m pytest -q -p no:cacheprovider tests/test_course_editor_ui.py

المنطق النقي (قاموس الكتل · عمليات القائمة · فرق الهيكل · أجسام الحفظ · خطة TUS والرافع · أجسام المساعد) بيتشغّل في node على v2-logic.js
(`V2L.courses2`). الرافع بيتجرّب بدالة fetch مزيّفة: ⛔ صفر شبكة. والواجهة (course_editor.js/.css) بتتفحص كملفات: التحميل · الحرّاس · نصوص ممنوعة.
لقطات الشاشة (كمبيوتر وموبايل) في `uiharness/v2_shots_course_editor.py`.
"""
import json
import os
import re
import subprocess
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, 'uiharness'))
import v2_node   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(_HERE))
LOGIC = os.path.join(ROOT, 'dashboard-cloud', 'v2-logic.js')
needs_node = pytest.mark.skipif(not v2_node.NODE, reason='needs node')


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as fh:
        return fh.read()


def C(fn, *args):
    return v2_node.logic('courses2.' + fn, *args)


def _node(js):
    p = subprocess.run([v2_node.NODE, '-e', 'const L=require(%s);const C=L.courses2;%s' % (json.dumps(LOGIC), js)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


# ---------------------------------------------------------------- قائمة الكتل: إضافة · تحريك · حذف
@needs_node
def test_block_list_add_move_delete_are_pure_and_bounded():
    a, b, c = {'type': 'text', 'md': 'أ'}, {'type': 'text', 'md': 'ب'}, {'type': 'text', 'md': 'ج'}
    base = [a, b, c]
    assert C('blocksAdd', base, {'type': 'summary', 'items': []}) [-1]['type'] == 'summary'
    assert [x['md'] for x in C('blocksAdd', base, {'type': 'text', 'md': 'س'}, 1)] == ['أ', 'س', 'ب', 'ج']
    assert len(C('blocksAdd', base, {'type': 'text'}, 99)) == 4 and C('blocksAdd', base, {'type': 'text'}, 99)[-1] == {'type': 'text'}
    assert [x['md'] for x in C('blocksMove', base, 0, 1)] == ['ب', 'أ', 'ج']
    assert [x['md'] for x in C('blocksMove', base, 2, -1)] == ['أ', 'ج', 'ب']
    assert C('blocksMove', base, 0, -1) == base and C('blocksMove', base, 2, 1) == base and C('blocksMove', base, 9, 1) == base
    assert [x['md'] for x in C('blocksDelete', base, 1)] == ['أ', 'ج']
    assert C('blocksDelete', base, 7) == base and C('blocksDelete', [], 0) == []
    assert _node("const b=[{x:1},{x:2}];C.blocksAdd(b,{x:3});C.blocksMove(b,0,1);C.blocksDelete(b,0);console.log(JSON.stringify(b))") == [{'x': 1}, {'x': 2}], 'لا تعديل في الأصل'


@needs_node
def test_set_in_row_ops_lines_and_head():
    blk = {'type': 'decision', 'text': 't', 'options': [{'text': 'أ', 'result': '', 'comment': ''}]}
    out = C('setIn', blk, 'options.0.text', 'جديد')
    assert out['options'][0]['text'] == 'جديد' and blk['options'][0]['text'] == 'أ'
    assert C('setIn', {}, 'a.b.0.c', 5) == {'a': {'b': [{'c': 5}]}}
    assert len(C('rowAdd', blk, 'options', {'text': '', 'result': '', 'comment': ''})['options']) == 2
    assert C('rowDelete', blk, 'options', 0)['options'] == [] and C('rowDelete', blk, 'options', 5) == blk
    assert C('linesToArr', ' أ \r\n\n ب\n   \nج ') == ['أ', 'ب', 'ج'] and C('arrToLines', ['أ', 'ب']) == 'أ\nب'
    assert C('blockHead', {'type': 'decision', 'question': 'تختار إيه؟'}) == 'تختار إيه؟'
    assert C('blockHead', {'type': 'objectives', 'items': ['هدف أول']}) == 'هدف أول' and C('blockHead', {'type': 'text', 'md': 'س' * 100}) == 'س' * 70
    assert C('blockHead', None) == ''


@needs_node
def test_dictionary_covers_the_ten_core_types_with_arabic_names_and_valid_blanks():
    types = {t['type']: t for t in _node("console.log(JSON.stringify(C.TYPES))")}
    for t in ('objectives', 'text', 'situation', 'decision', 'recall', 'quiz', 'summary', 'example', 'cards'):
        assert t in types and types[t]['main'] is True and types[t]['fields'], t       # الأنواع التسعة التي يكتبها المساعد لها نماذج حقول
    assert C('typeAr', 'decision') == 'قرار' and C('typeAr', 'zzz') == 'zzz' and C('typeAr', None) == 'كتلة'
    assert C('blankBlock', 'situation')['options'] and len(C('blankBlock', 'decision')['options']) == 2
    assert C('blankBlock', 'unknown') == {'type': 'unknown'}
    for name, t in types.items():
        assert t['blank']['type'] == name and re.search(r'[؀-ۿ]', t['ar']), name
        assert 'price' not in json.dumps(t, ensure_ascii=False).lower()


@needs_node
def test_advanced_json_parsing():
    assert C('parseBlockJson', '{"type":"text","md":"x"}') == {'ok': True, 'block': {'type': 'text', 'md': 'x'}}
    for bad in ('', '{', '[1]', '"x"', '{"md":"x"}', '{"type":""}', 'null'):
        r = C('parseBlockJson', bad)
        assert r['ok'] is False and r['error'], bad
    assert C('blocksIssues', [{'type': 'text'}, {'md': 'x'}, None]) == ['الكتلة ٢ بلا نوع', 'الكتلة ٣ بلا نوع']


# ---------------------------------------------------------------- فرق الهيكل
def _units():
    return [{'id': 'u1', 'title': 'الأساسيات', 'lessons': [{'id': 'L1', 'title': 'أول', 'kind': 'interactive', 'hasContent': True}, {'id': 'L2', 'title': 'ثان', 'kind': 'recorded', 'hasContent': False}]},
            {'id': 'u2', 'title': 'التنفيذ', 'lessons': [{'id': 'L3', 'title': 'ثالث', 'kind': 'live', 'hasContent': True}]}]


@needs_node
def test_structure_diff_keeps_ids_and_flags_content_loss():
    prev = _units()
    assert C('structureDiff', prev, prev)['changed'] is False
    nxt = _units()
    nxt[0]['lessons'][1]['title'] = 'ثان معدّل'
    nxt[1]['lessons'].append({'title': 'رابع', 'kind': 'recorded'})
    d = C('structureDiff', prev, nxt)
    assert d['kept'] == ['L1', 'L2', 'L3'] and d['renamed'] == [{'id': 'L2', 'from': 'ثان', 'to': 'ثان معدّل'}]
    assert d['added'] == [{'title': 'رابع', 'kind': 'recorded'}] and d['removed'] == [] and d['changed'] is True and d['reordered'] is False
    gone = _units()
    del gone[0]['lessons'][0]
    del gone[1]
    d = C('structureDiff', prev, gone)
    assert [r['id'] for r in d['removed']] == ['L1', 'L3'] and [r['hasContent'] for r in d['removed']] == [True, True] and d['unitsRemoved'] == 1 and d['kept'] == ['L2']
    moved = _units()
    moved[0]['lessons'].reverse()
    d = C('structureDiff', prev, moved)
    assert d['reordered'] is True and d['kept'] == ['L2', 'L1', 'L3'] and d['added'] == [] and d['removed'] == []
    units_swapped = list(reversed(_units()))
    assert C('structureDiff', prev, units_swapped)['reordered'] is True
    assert C('structureDiff', prev, units_swapped + [{'title': 'وحدة جديدة', 'lessons': []}])['unitsAdded'] == 1


@needs_node
def test_a_new_lesson_needs_a_kind_and_titles_are_required():
    u = _units()
    u[0]['lessons'].append({'title': 'جديد'})
    assert C('structureErrors', u) == ['اختر نوع الدرس «جديد»: تفاعلي أو مسجّل أو مباشر']
    u[0]['lessons'][-1]['kind'] = 'bogus'
    assert len(C('structureErrors', u)) == 1
    u[0]['lessons'][-1]['kind'] = 'live'
    assert C('structureErrors', u) == []
    u[0]['title'] = ' '
    u[1]['lessons'][0]['title'] = ''
    assert C('structureErrors', u) == ['الوحدة ١ بلا عنوان', 'الدرس ١ في الوحدة ٢ بلا عنوان']
    assert C('structureErrors', []) == ['أضف وحدة واحدة على الأقل']
    assert C('structureErrors', [{'title': 'و', 'lessons': []}] * 31)[0] == 'الوحدات حتى ٣٠ وحدة'


@needs_node
def test_structure_body_shape_for_the_put():
    u = _units()
    u[0]['lessons'].append({'title': '  جديد  ', 'kind': 'interactive', 'hasContent': True})
    b = C('structureBody', u, ['student'])
    assert b['cases'] == ['student'] and 'hasContent' not in json.dumps(b)
    assert b['units'][0] == {'id': 'u1', 'title': 'الأساسيات', 'lessons': [{'id': 'L1', 'title': 'أول', 'kind': 'interactive'}, {'id': 'L2', 'title': 'ثان', 'kind': 'recorded'}, {'title': 'جديد', 'kind': 'interactive'}]}
    assert 'cases' not in C('structureBody', u)
    course = {'outline': {'units': [{'id': 'u1', 'title': 'أ', 'lessons': [{'id': 'L1', 'title': 'ع', 'kind': 'interactive', 'blocks': [{'type': 'text'}]}, {'id': 'L2', 'title': 'ع', 'kind': 'recorded', 'has_video': False}]}]}}
    s = C('structFrom', course)
    assert s[0]['lessons'][0]['hasContent'] is True and s[0]['lessons'][1]['hasContent'] is False


@needs_node
def test_material_draft_merges_into_the_structure_and_pairs_new_lessons_in_order():
    draft = {'units': [{'title': 'المبادئ', 'lessons': [{'title': 'تعريف', 'summary': ['أ', 'ب', 'ج', 'د'], 'transcript': 'ن1'}, {'title': 'أنواع', 'summary': [], 'transcript': 'ن2'}]},
                       {'title': 'التطبيق', 'lessons': [{'title': 'بند', 'summary': ['س'], 'transcript': 'ن3'}]}]}
    merged = C('mergeDraftIntoStructure', _units(), draft)
    assert [u.get('id') for u in merged] == ['u1', 'u2', None, None] and merged[2]['lessons'] == [{'title': 'تعريف', 'kind': 'recorded'}, {'title': 'أنواع', 'kind': 'recorded'}]
    assert len(C('draftLessons', draft)) == 3
    course = {'outline': {'units': [{'id': 'u1', 'lessons': [{'id': 'L1', 'title': 'أول'}, {'id': 'L2', 'title': 'ثان'}]}, {'id': 'u2', 'lessons': [{'id': 'L3', 'title': 'ثالث'}]},
                                    {'id': 'u9', 'lessons': [{'id': 'N1', 'title': 'تعريف'}, {'id': 'N2', 'title': 'أنواع'}]}, {'id': 'u10', 'lessons': [{'id': 'N3', 'title': 'بند'}]}]}}
    pairs = C('pairNewLessons', ['L1', 'L2', 'L3'], course, draft)
    assert [p['id'] for p in pairs] == ['N1', 'N2', 'N3']
    assert pairs[0]['body'] == {'summary': ['أ', 'ب', 'ج'], 'transcript': 'ن1'}, 'الملخّص ثلاثة أسطر على الأكثر'
    assert pairs[2]['body'] == {'summary': ['س'], 'transcript': 'ن3'}


# ---------------------------------------------------------------- TUS
@needs_node
def test_tus_chunk_planner():
    MB = 1024 * 1024
    assert C('CHUNK') == 5 * MB
    assert C('tusPlan', 0) == []
    assert C('tusPlan', 1) == [{'offset': 0, 'length': 1}]
    assert C('tusPlan', 5 * MB) == [{'offset': 0, 'length': 5 * MB}]
    assert C('tusPlan', 12 * MB) == [{'offset': 0, 'length': 5 * MB}, {'offset': 5 * MB, 'length': 5 * MB}, {'offset': 10 * MB, 'length': 2 * MB}]
    p = C('tusPlan', 10 * MB)
    assert len(p) == 2 and p[1] == {'offset': 5 * MB, 'length': 5 * MB}
    p = C('tusPlan', 1000, 300)
    assert [x['length'] for x in p] == [300, 300, 300, 100] and sum(x['length'] for x in p) == 1000
    assert [x['offset'] for x in p] == [0, 300, 600, 900]
    import base64
    assert C('tusMetadata', {'filetype': 'video/mp4', 'title': 'عنوان'}) == 'filetype dmlkZW8vbXA0,title ' + base64.b64encode('عنوان'.encode('utf-8')).decode()


@needs_node
def test_tus_upload_runs_post_then_chunked_patches_with_the_returned_headers():
    js = r"""
const MB=1024*1024, calls=[], prog=[];
const file={size:12*MB,name:'a.mp4',type:'video/mp4',slice:(a,b)=>({a:a,b:b})};
const up={upload_url:'https://video.bunnycdn.com/tusupload',headers:{AuthorizationSignature:'sig',AuthorizationExpire:'1767000000',VideoId:'vid-1',LibraryId:'9001'}};
function H(o){return {get:k=>o[k]==null?null:o[k]};}
const fetchFn=(url,init)=>{calls.push({url,method:init.method,h:init.headers,b:init.body});
  if(init.method==='POST')return Promise.resolve({status:201,headers:H({Location:'/tusupload/abc123'})});
  const off=+init.headers['Upload-Offset'], len=init.body.b-init.body.a;
  return Promise.resolve({status:204,headers:H({'Upload-Offset':String(off+len)})});};
C.tusUpload(file,up,fetchFn,{title:'درس',onProgress:(s,t)=>prog.push([s,t])}).then(r=>{console.log(JSON.stringify({r,calls,prog}));});
"""
    out = _node(js)
    MB = 1024 * 1024
    post, *patches = out['calls']
    assert out['r'] == {'ok': True, 'chunks': 3}
    assert post['method'] == 'POST' and post['url'] == 'https://video.bunnycdn.com/tusupload'
    assert post['h']['Tus-Resumable'] == '1.0.0' and post['h']['Upload-Length'] == str(12 * MB)
    assert post['h']['AuthorizationSignature'] == 'sig' and post['h']['AuthorizationExpire'] == '1767000000' and post['h']['VideoId'] == 'vid-1' and post['h']['LibraryId'] == '9001'
    meta = dict(kv.split(' ', 1) for kv in post['h']['Upload-Metadata'].split(','))
    assert set(meta) == {'filetype', 'title'} and meta['filetype'] == 'dmlkZW8vbXA0'          # base64 of video/mp4
    assert [p['method'] for p in patches] == ['PATCH'] * 3 and all(p['url'] == 'https://video.bunnycdn.com/tusupload/abc123' for p in patches), 'PATCH على Location'
    assert [p['h']['Upload-Offset'] for p in patches] == ['0', str(5 * MB), str(10 * MB)]
    assert all(p['h']['Content-Type'] == 'application/offset+octet-stream' and p['h']['Tus-Resumable'] == '1.0.0' and p['h']['AuthorizationSignature'] == 'sig' for p in patches)
    assert [p['b'] for p in patches] == [{'a': 0, 'b': 5 * MB}, {'a': 5 * MB, 'b': 10 * MB}, {'a': 10 * MB, 'b': 12 * MB}]
    assert out['prog'][0] == [0, 12 * MB] and out['prog'][-1] == [12 * MB, 12 * MB] and [p[0] for p in out['prog']] == sorted(p[0] for p in out['prog'])


@needs_node
def test_tus_upload_falls_back_to_the_upload_url_and_reports_the_failing_chunk():
    js = r"""
const MB=1024*1024, calls=[];
const file={size:7*MB,name:'a.mp4',type:'',slice:(a,b)=>({a:a,b:b})};
const up={upload_url:'https://video.bunnycdn.com/tusupload',headers:{VideoId:'v'}};
const H={get:()=>null};
let n=0;
const fetchFn=(url,init)=>{calls.push([init.method,url]); if(init.method==='POST')return Promise.resolve({status:201,headers:H}); n++; return Promise.resolve({status:n===1?204:500,headers:H});};
C.tusUpload(file,up,fetchFn,{}).then(()=>console.log(JSON.stringify({ok:true,calls})),e=>console.log(JSON.stringify({ok:false,msg:e.message,status:e.status,calls})));
"""
    out = _node(js)
    assert out['ok'] is False and out['status'] == 500 and 'القطعة ٢ من ٢' in out['msg']
    assert [c[0] for c in out['calls']] == ['POST', 'PATCH', 'PATCH'] and all(c[1] == 'https://video.bunnycdn.com/tusupload' for c in out['calls'])
    js2 = js.replace("status:201,headers:H", "status:403,headers:H")
    out = _node(js2)
    assert out['ok'] is False and out['status'] == 403 and out['msg'] == 'تعذّر بدء الرفع' and len(out['calls']) == 1, 'فشل الإنشاء ⇒ لا PATCH'


# ---------------------------------------------------------------- أجسام الحفظ
@needs_node
def test_lesson_body_per_kind_sends_only_editable_fields():
    inter = {'id': 'L1', 'kind': 'interactive', 'title': 'ع', 'blocks': [{'type': 'text', 'md': 'x'}], 'time': 4, 'for': [], 'hero': '', 'motion': '', 'state': 'ready', 'no': 1, 'kind_ar': 'تفاعلي'}
    b = C('lessonBody', inter, None)
    assert b == {'title': 'ع', 'blocks': [{'type': 'text', 'md': 'x'}], 'time': 4, 'for': []}, 'hero/motion الفارغان لا يُرسلان'
    d = dict(inter, title=' جديد ', time='7', hero='https://a.test/x.png')
    assert C('lessonBody', inter, d) == {'title': 'جديد', 'blocks': [{'type': 'text', 'md': 'x'}], 'time': 7, 'for': [], 'hero': 'https://a.test/x.png'}
    live = {'id': 'L3', 'kind': 'live', 'title': 'لقاء', 'starts_at': '2026-12-01T18:00', 'duration_min': '90', 'zoom_link': ' https://z.test ', 'recording_url': '', 'status': '', 'quiz': {'question': ' ', 'options': []}}
    assert C('lessonBody', live, None) == {'title': 'لقاء', 'starts_at': '2026-12-01T18:00', 'duration_min': 90, 'zoom_link': 'https://z.test', 'recording_url': '', 'status': 'scheduled', 'quiz': None}
    live['quiz'] = {'question': 'سؤال؟', 'options': [{'text': 'أ', 'ok': True}, {'text': '', 'ok': False}, {'text': 'ب'}]}
    assert C('lessonBody', live, None)['quiz'] == {'question': 'سؤال؟', 'options': [{'text': 'أ', 'ok': True, 'explanation': ''}, {'text': 'ب', 'ok': False, 'explanation': ''}]}


@needs_node
def test_recorded_body_video_rules_chapters_checkpoints_and_summary():
    les = {'id': 'L2', 'kind': 'recorded', 'title': 'ع', 'video': {'bunny_video_id': 'g1', 'url': 'https://p.test/x'}, 'has_video': True, 'duration_seconds': 750, 'is_preview': True,
           'chapters': [{'t': 0, 'title': 'مقدمة'}, {'t': 90, 'title': ''}], 'checkpoints': [{'t': 30, 'question': 'س؟', 'options': [{'text': 'أ', 'ok': True, 'explanation': 'ش'}, {'text': 'ب', 'ok': False}]}],
           'summary': ['أ', 'ب'], 'transcript': ' نص '}
    d = C('draftFrom', les)
    assert d['duration_seconds'] == '12:30' and d['chapters'][0]['t'] == '0:00' and d['_video'] == {'touched': False, 'mode': 'upload', 'bunny_video_id': 'g1', 'url': ''}
    b = C('lessonBody', les, d)
    assert 'video' not in b, 'الفيديو لم يُلمس ⇒ لا يُرسل (لا رفع ورابط معًا)'
    assert b['duration_seconds'] == 750 and b['is_preview'] is True and b['chapters'] == [{'t': 0, 'title': 'مقدمة'}] and b['transcript'] == 'نص'
    assert b['checkpoints'] == [{'t': 30, 'question': 'س؟', 'options': [{'text': 'أ', 'ok': True, 'explanation': 'ش'}, {'text': 'ب', 'ok': False, 'explanation': ''}]}]
    d['_video'] = {'touched': True, 'mode': 'link', 'url': ' https://youtu.be/abcdefghijk ', 'bunny_video_id': ''}
    assert C('lessonBody', les, d)['video'] == {'url': 'https://youtu.be/abcdefghijk'}
    d['_video'] = {'touched': True, 'mode': 'upload', 'bunny_video_id': 'new-guid', 'url': ''}
    assert C('lessonBody', les, d)['video'] == {'bunny_video_id': 'new-guid'}
    d['_video'] = {'touched': True, 'mode': 'none', 'url': '', 'bunny_video_id': ''}
    assert C('lessonBody', les, d)['video'] == {}
    d['summary'] = 'أ\nب\nج\nد'
    assert C('lessonBody', les, d)['summary'] == ['أ', 'ب', 'ج'] and 'الملخّص ثلاثة أسطر على الأكثر' in C('lessonIssues', les, d)
    d['chapters'] = [{'t': 'بعد قليل', 'title': 'ع'}]
    assert any('وقت الفصل ١' in i for i in C('lessonIssues', les, d))
    assert C('parseT', '1:30') == 90 and C('parseT', '٢:05') == 125 and C('parseT', '45') == 45 and C('parseT', '1:75') is None and C('parseT', '') is None and C('fmtT', 125) == '2:05'


@needs_node
def test_lesson_issues_block_untitled_and_typeless_blocks_and_bad_dates():
    inter = {'id': 'L1', 'kind': 'interactive', 'title': 'ع', 'blocks': []}
    assert C('lessonIssues', inter, dict(inter, title=' ')) == ['اكتب عنوان الدرس']
    assert C('lessonIssues', inter, dict(inter, blocks=[{'md': 'x'}])) == ['الكتلة ١ بلا نوع']
    live = {'id': 'L3', 'kind': 'live', 'title': 'ع'}
    assert C('lessonIssues', live, dict(live, starts_at='ليس تاريخا')) == ['موعد البدء غير مفهوم'] and C('lessonIssues', live, dict(live, starts_at='')) == []


@needs_node
def test_data_body_cover_issue_and_return_notes_and_idem_key():
    b = C('dataBody', {'title': ' ع ', 'subtitle': '', 'description': ' و ', 'cover': ' https://a.test/c.jpg ', 'level': 'مبتدئ', 'outcomes': ' أ \n\nب '})
    assert b == {'title': 'ع', 'subtitle': '', 'description': 'و', 'cover': 'https://a.test/c.jpg', 'level': 'مبتدئ', 'outcomes': ['أ', 'ب']}
    assert C('coverIssue', 'http://a.test/x') and C('coverIssue', 'javascript:alert(1)') and C('coverIssue', '') == '' and C('coverIssue', 'https://a.test/x') == ''
    rows = [{'on': True, 'kind': 'course', 'id': 'ignored', 'label': 'الدورة', 'text': ' عامة '}, {'on': True, 'kind': 'lesson', 'id': 'L2', 'label': 'الدرس ٢', 'text': 'ينقصه فيديو'}, {'on': False, 'kind': 'lesson', 'id': 'L3', 'label': 'ثالث', 'text': 'x'}]
    assert C('returnBody', rows) == {'notes': [{'target_kind': 'course', 'target_id': '', 'text': 'عامة'}, {'target_kind': 'lesson', 'target_id': 'L2', 'text': 'ينقصه فيديو'}]}
    assert C('returnIssues', rows) == [] and C('returnIssues', []) == ['اختر هدفًا واحدًا على الأقل']
    assert C('returnIssues', [{'on': True, 'label': 'الدرس ٢', 'text': ' '}]) == ['اكتب ملاحظة «الدرس ٢»']
    keys = [_node("console.log(JSON.stringify(C.idemKey()))") for _ in range(3)]
    assert len(set(keys)) == 3 and all(re.match(r'^[A-Za-z0-9_.:-]{8,80}$', k) for k in keys)
    assert _node("console.log(JSON.stringify(C.idemKey(()=>'123e4567-e89b-12d3-a456-426614174000')))") == 'c-123e4567e89b12d3a456426614174000'


# ---------------------------------------------------------------- المساعد
@needs_node
def test_assistant_requests_and_applying_drafts():
    kinds = _node("console.log(JSON.stringify(C.ASSIST.map(a=>[a.kind,a.ar])))")
    assert [k[1] for k in kinds] == ['حوّل إلى نشاط قرار', 'اقترح عناوين أقصر', 'اكتب نص فيديو', 'سؤال حر', 'حوّل مادتي إلى دروس']
    assert [a['kind'] for a in _node("console.log(JSON.stringify(C.assistKinds(true)))")] == ['activity_decision', 'shorter_title', 'video_script', 'free']
    assert [a['kind'] for a in _node("console.log(JSON.stringify(C.assistKinds(false)))")] == ['free', 'from_material']
    assert C('assistErrors', 'activity_decision', '', '', '') == ['اختر درسًا أولًا'] and C('assistErrors', 'activity_decision', '', '', 'L1') == []
    assert C('assistErrors', 'free', ' ', '', '') == ['اكتب سؤالك'] and C('assistErrors', 'free', 'سؤال', '', '') == []
    assert C('assistErrors', 'from_material', '', 'م' * 79, '') == ['الصق مادة من ٨٠ حرفًا على الأقل'] and C('assistErrors', 'from_material', '', 'م' * 80, '') == []
    assert C('assistErrors', 'nope', '', '', '') == ['اختر ما تريده من المساعد']
    assert C('assistBody', 'activity_decision', '', '', 'L1') == {'instruction': 'حوّل الفقرة إلى نشاط قرار', 'kind': 'activity_decision', 'lesson_id': 'L1'}
    assert C('assistBody', 'free', ' كيف أبدأ؟ ', '', 'L1') == {'instruction': 'كيف أبدأ؟', 'kind': 'free'}
    assert C('assistBody', 'from_material', '', ' ' + 'م' * 90 + ' ', '') == {'instruction': 'حوّل مادتي إلى دروس', 'kind': 'from_material', 'material': 'م' * 90}
    les = {'title': 'قديم', 'blocks': [{'type': 'text', 'md': 'x'}], 'transcript': ''}
    r = C('applyDraft', 'interactive', les, 'activity_decision', {'draft': {'block': {'type': 'decision'}}})
    assert r['ok'] and len(r['lesson']['blocks']) == 2 and r['lesson']['blocks'][1] == {'type': 'decision'} and len(les['blocks']) == 1
    assert C('applyDraft', 'interactive', les, 'shorter_title', {'draft': {'titles': ['أ', 'ب', 'ج']}}, 2)['lesson']['title'] == 'ج'
    assert C('applyDraft', 'recorded', les, 'video_script', {'draft': {'transcript': 'نص طويل'}})['lesson']['transcript'] == 'نص طويل'
    assert C('applyDraft', 'interactive', les, 'video_script', {'draft': {'transcript': 'نص'}})['lesson']['blocks'][-1] == {'type': 'text', 'md': 'نص'}
    assert C('applyDraft', 'interactive', les, 'free', {'answer': 'ج'})['ok'] is False and C('applyDraft', 'interactive', les, 'shorter_title', {'draft': {}})['ok'] is False


# ---------------------------------------------------------------- القائمة والمراجعة
@needs_node
def test_list_merge_helpers():
    c2 = [{'id': 'pc-12', 'slug': 's', 'status': 'draft', 'status_ar': 'مسودة', 'kinds': ['interactive', 'recorded'], 'lessons_count': 4, 'open_notes': 2},
          {'id': 'crs-ed1', 'slug': 'neg', 'status': 'draft', 'status_ar': 'مسودة', 'kinds': [], 'lessons_count': 0, 'open_notes': 0}]
    assert C('c2Bits', c2[0]) == {'status': 'مسودة', 'kinds': ['تفاعلي', 'مسجّل'], 'lessons': 4, 'open': 2}
    assert C('c2Line', c2[0]) == 'تفاعلي · مسجّل · ٤ دروس · ٢ ملاحظات مفتوحة'
    assert C('c2Line', c2[1]) == '٠ درسًا' or C('c2Line', c2[1]).startswith('٠')
    assert C('c2Line', dict(c2[0], lessons_count=1, open_notes=1, kinds=['live'])) == 'مباشر · ١ درس · ١ ملاحظة مفتوحة'
    assert C('c2Line', None) == ''
    assert [x['id'] for x in C('c2Extras', c2, [{'id': 'pc-12'}])] == ['crs-ed1']
    assert [x['id'] for x in C('c2Extras', c2, [{'id': 'zzz', 'slug': 'neg'}])] == ['pc-12']
    assert C('c2Extras', None, None) == []
    assert C('gapsLine', {'gaps': ['وصف الدورة', 'الدرس ٢ «ع» (مسودة)']}) == 'ينقصها: وصف الدورة، الدرس ٢ «ع» (مسودة)' and C('gapsLine', {'gaps': []}) == 'جاهزة'


# ---------------------------------------------------------------- الملفات
def test_editor_files_are_wired_and_guarded():
    html = _read('dashboard-cloud', 'index.html')
    assert html.count('v2s/course_editor.js') == 1 and html.count('v2s/course_editor.css') == 1
    js = _read('dashboard-cloud', 'v2s', 'course_editor.js')
    assert "if (!L || !L.courses2) return;" in js, 'الملف يتحمّل دائمًا ولا يرسم إلا لو نادته courses.js'
    cj = _read('dashboard-cloud', 'v2s', 'courses.js')
    assert 'CO.kit = {' in cj and "data-a=\"edit-course\"" in cj and 'حرّر الدورة' in cj and 'تعديل الدروس من «كل السجلات»' not in cj
    assert "if (S.editing && window.V2CE && scr === 'course') return;" in cj, 'إعادة رسم الصفحة لا تمسح مسودّات المحرّر'
    assert 'courses2' in cj and "'/v2/courses2'" in cj
    logic = _read('dashboard-cloud', 'v2-logic.js')
    assert logic.count('// ===== courses2 =====') == 1 and logic.count('// ===== /courses2 =====') == 1
    assert logic.index('// ===== /courses2 =====') < logic.index('// ===== brain2 =====') and logic.rstrip().endswith('// ===== /brain2 =====')   # كتلة العقل تبقى آخر الملف (اختبارها يشترط ذلك)


def _code_only(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'(^|\s)//.*$', '', ln) for ln in src.split('\n'))


def test_visible_copy_rules():
    banned = ['يقوّم', 'يقوم بـ', 'استرداد', 'استرجاع', 'ضمان', 'ضمين', '١٤ يوم', 'مضمون', 'EGP', 'USD', 'جنيه', 'دولار', 'ريال', 'درهم', 'Zoom', 'YouTube', 'Google', 'API', 'JSON ']
    for path in (('dashboard-cloud', 'v2s', 'course_editor.js'), ('dashboard-cloud', 'v2s', 'course_editor.css')):
        code = _code_only(_read(*path))
        for w in banned:
            assert w not in code, (path[-1], w)
    js = _code_only(_read('dashboard-cloud', 'v2s', 'course_editor.js'))
    # لا سعر ولا نسبة في أي شاشة (الكلمة نفسها ولا حقل التسعير)
    for w in ('سعر', 'السعر', 'price', 'pricing', 'is_free', 'نسبة', 'تكلفة', 'مجاني'):
        assert w not in js, w
    logic = _code_only(_read('dashboard-cloud', 'v2-logic.js').split('// ===== courses2 =====')[1].split('// ===== /courses2 =====')[0])
    for w in ('سعر', 'price', 'pricing', 'is_free', 'استرداد', 'ضمان', 'يقوّم', 'جنيه'):
        assert w not in logic, w
    assert not re.search(r'عميل|عزيزي|أخي|أختي|حبيبي', js), 'لغة محايدة'


def test_every_write_goes_through_a_confirm_sheet_and_sends_confirmed_true():
    js = _code_only(_read('dashboard-cloud', 'v2s', 'course_editor.js'))
    writes = []
    for chunk in js.split("api('")[1:]:
        head = chunk[:230]
        if not head.startswith(('PUT', 'POST')):
            continue
        writes.append(head)
        if '/preview' in head or '/brain/draft' in head:
            assert 'confirmed' not in head, head[:90]
        else:
            assert 'confirmed: true' in head or 'payload' in head or ', b)' in head or ', p)' in head, head[:140]
    assert 'confirmed: true' in js and writes
    assert js.count('confirmSheet({') >= 7 and js.count('k.flow({') >= 2 and "title: 'أنشئ دورة'" in js
    assert 'idem_key: idem' in js and 'K.idemKey(' in js, 'مفتاح منع التكرار يُولَّد مرة واحدة عند فتح الورقة'


def test_shots_script_and_fixtures_exist_and_compile():
    for n in ('v2_shots_course_editor.py', 'course_editor_fixtures.py'):
        path = os.path.join(_HERE, 'uiharness', n)
        with open(path, encoding='utf-8') as fh:
            compile(fh.read(), path, 'exec')
