# -*- coding: utf-8 -*-
"""منصّة وهميّة لمحرّر الدورات (SPEC-C-courses §C1): فوق `CoursesPlatform` (لوحة الدورات القديمة) بتضيف جسور `/api/bridge/courses2…` بحالتها —
قائمة · دورة كاملة · إنشاء بمفتاح منع تكرار · بيانات · هيكل · محتوى درس · معاينة · نشر · إيقاف · إرجاع بملاحظات · مسودة المساعد · رفع الفيديو —
بنفس رسائل المنصة العربية وأكوادها (٤٠٠ · ٤٠٤ · ٤٠٩ · ٤٢٢). ⛔ صفر شبكة: كله في الذاكرة. الأسماء مخترعة، والأشكال بالحرف من PARALLEL.md.

المنصّة الحقيقية تتجاهل أي حقل سعر في الجسم؛ هنا نسجّل الجسم كما وصل في `self.c2calls` ليتأكد الاختبار أن الداشبورد ما بعتش سعرًا أصلًا.
"""
import copy
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import courses_fixtures as cfx   # noqa: E402

CONFIRM_DETAIL = 'لازم تأكيد صريح قبل الحفظ (confirmed:true) واسم اللي أكّد (by)'
STATUS_AR = {'draft': 'مسودة', 'review': 'عند المراجعة', 'changes': 'رجعت بملاحظات', 'published': 'منشورة', 'paused': 'موقوفة'}
STATE_AR = {'ready': 'جاهز', 'missing_video': 'ينقصه فيديو', 'draft': 'مسودة'}
KIND_AR = {'interactive': 'تفاعلي', 'recorded': 'مسجّل', 'live': 'مباشر'}
BLOCK_TYPES = set('objectives text video audio case_pick accordion quote image steps exercise quiz ai_station download summary goal eval chat gate registered sheet certificate '
                  'situation decision recall order match spot line predict cards before_after icon_line example'.split())
AR_D = '٠١٢٣٤٥٦٧٨٩'


def ar(n):
    return str(n).translate({ord(str(i)): AR_D[i] for i in range(10)})


def blk_text():
    return {'type': 'text', 'md': 'عقد المقاولة اتفاق يلتزم فيه المقاول بإنجاز عمل مقابل أجر.'}


def seed():
    def les(i, kind, title, **kw):
        base = {'id': i, 'kind': kind, 'title': title}
        base.update(kw)
        return base
    c1 = {
        'id': 'pc-12', 'slug': 'construction-contracts', 'type': 'recorded_paid', 'status': 'draft', 'owner': {'email': 'hala@example.test', 'name': 'د. هالة سمير', 'platform_owned': False},
        'meta': {'title': 'عقود المقاولات', 'subtitle': 'من الاتفاق إلى التسليم', 'description': '', 'cover': '', 'level': 'متوسط', 'outcomes': ['صياغة عقد مقاولة سليم', 'تحديد التزامات الأطراف']},
        'cases': ['student', 'office'], 'is_free': False, 'price_set': True, 'notes': [],
        'units': [
            {'id': 'u1', 'title': 'الأساسيات', 'lessons': [
                les('L1', 'interactive', 'ما هو عقد المقاولة؟', time=6, **{'for': []}, hero='', motion='', blocks=[
                    {'type': 'objectives', 'items': ['تعرّف عقد المقاولة', 'تفرّق بينه وبين عقد العمل']},
                    blk_text(),
                    {'type': 'decision', 'text': 'عميل يطلب بناء سور ويرفض كتابة العقد.', 'question': 'تختار إيه؟', 'options': [
                        {'text': 'أكتب العقد أولًا', 'result': 'تحمي حقك', 'comment': 'الكتابة تقلّل النزاع'}, {'text': 'أبدأ بالعمل', 'result': 'مخاطرة', 'comment': 'لا إثبات للاتفاق'}]},
                    {'type': 'summary', 'items': ['العقد يُكتب قبل العمل']}]),
                les('L2', 'recorded', 'أركان العقد', video={}, has_video=False, duration_seconds=0, is_preview=False, chapters=[], checkpoints=[], summary=[], transcript=''),
                les('L3', 'live', 'ورشة الصياغة', starts_at='2026-12-01T18:00', duration_min=90, zoom_link='https://meet.example.test/x', recording_url='', status='scheduled', quiz=None)]},
            {'id': 'u2', 'title': 'التنفيذ', 'lessons': [
                les('L4', 'recorded', 'التسليم والاستلام', video={'bunny_video_id': 'b1c2d3e4-1111', 'bunny_library_id': '9001', 'url': ''}, has_video=True, duration_seconds=750, is_preview=True,
                    chapters=[{'t': 0, 'title': 'المقدمة'}, {'t': 210, 'title': 'محضر التسليم'}], checkpoints=[{'t': 300, 'question': 'متى يتم التسليم؟', 'options': [
                        {'text': 'عند انتهاء العمل', 'ok': True, 'explanation': 'التسليم يتبع الإنجاز'}, {'text': 'قبل البدء', 'ok': False, 'explanation': ''}]}],
                    summary=['التسليم يُوثَّق', 'المحضر يحمي الطرفين'], transcript='نص الفيديو التجريبي.')]}],
        'updated_at': '2026-10-30T10:00:00+00:00'}
    c2 = {
        'id': 'pc-15', 'slug': 'contract-management', 'type': 'recorded_paid', 'status': 'review', 'owner': {'email': 'nadia@example.test', 'name': 'أ. نادية فؤاد', 'platform_owned': False},
        'meta': {'title': 'إدارة العقود للشركات', 'subtitle': '', 'description': 'دليل عملي لإدارة دورة حياة العقد.', 'cover': 'https://img.example.test/c.jpg', 'level': 'متقدم', 'outcomes': ['بناء سجل عقود']},
        'cases': [], 'is_free': False, 'price_set': True,
        'notes': [{'id': 'n1', 'target_kind': 'lesson', 'target_id': 'M2', 'target_label': 'الدرس ٢', 'target_no': 2, 'target_title': 'متابعة التنفيذ', 'text': 'ينقصه الفيديو. سجّل دقيقة أو اثنتين.', 'status': 'open', 'status_ar': 'لم يُعدّل', 'created_at': '2026-10-29T10:00:00+00:00', 'by': 'admin@x.test'},
                  {'id': 'n2', 'target_kind': 'course', 'target_id': '', 'target_label': 'الدورة', 'target_no': 0, 'target_title': '', 'text': 'وصف الدورة قصير، أضف مثالًا.', 'status': 'edited', 'status_ar': 'عُدّل', 'created_at': '2026-10-29T10:00:00+00:00', 'edited_at': '2026-10-30T09:00:00+00:00', 'by': 'admin@x.test'}],
        'units': [{'id': 'm1', 'title': 'البداية', 'lessons': [
            {'id': 'M1', 'kind': 'recorded', 'title': 'لماذا نُدير العقود؟', 'video': {'url': 'https://youtu.be/abcdefghijk'}, 'has_video': True, 'duration_seconds': 600, 'is_preview': False, 'chapters': [], 'checkpoints': [], 'summary': ['العقد أصل من أصول الشركة'], 'transcript': 'نص.'},
            {'id': 'M2', 'kind': 'recorded', 'title': 'متابعة التنفيذ', 'video': {}, 'has_video': False, 'duration_seconds': 0, 'is_preview': False, 'chapters': [], 'checkpoints': [], 'summary': [], 'transcript': ''}]}],
        'updated_at': '2026-10-30T11:00:00+00:00'}
    c3 = {
        'id': 'pc-01', 'slug': 'contract-drafting-basics', 'type': 'recorded_paid', 'status': 'published', 'owner': {'email': 'hala@example.test', 'name': 'د. هالة سمير', 'platform_owned': False},
        'meta': {'title': 'أساسيات صياغة العقود', 'subtitle': '', 'description': 'مدخل عملي إلى صياغة العقود.', 'cover': '', 'level': 'مبتدئ', 'outcomes': ['صياغة بند واضح']},
        'cases': [], 'is_free': False, 'price_set': True, 'notes': [],
        'units': [{'id': 'p1', 'title': 'الصياغة', 'lessons': [
            {'id': 'P1', 'kind': 'recorded', 'title': 'بند الأطراف', 'video': {'bunny_video_id': 'aaaa1111-2222', 'bunny_library_id': '9001', 'url': ''}, 'has_video': True, 'duration_seconds': 480, 'is_preview': True, 'chapters': [], 'checkpoints': [], 'summary': ['اكتب الأطراف كاملة'], 'transcript': 'نص.'}]}],
        'updated_at': '2026-10-20T11:00:00+00:00'}
    c4 = {
        'id': 'crs-ed1', 'slug': 'negotiation', 'type': 'recorded_paid', 'status': 'draft', 'owner': {'email': '', 'name': 'البروفيسور', 'platform_owned': True},
        'meta': {'title': 'التفاوض على العقود', 'subtitle': '', 'description': '', 'cover': '', 'level': '', 'outcomes': []},
        'cases': [], 'is_free': False, 'price_set': False, 'notes': [], 'units': [], 'updated_at': '2026-10-31T08:00:00+00:00'}
    return [c1, c2, c3, c4]


class Courses2Platform(cfx.CoursesPlatform):
    def __init__(self, bunny=True, **kw):
        super(Courses2Platform, self).__init__(**kw)
        self.c2 = seed()
        self.bunny = bunny
        self.c2calls = []        # (method, path, body كما وصل)
        self.c2n = 0
        self.idem = {}

    # ------------------------------------------------------------------ عرض الدورة بالشكل المشترك
    def _find2(self, key):
        for c in self.c2:
            if key in (c['id'], c['slug']):
                return c
        return None

    def _lesson_state(self, l):
        if l['kind'] == 'interactive':
            return 'ready' if l.get('blocks') else 'draft'
        if l['kind'] == 'recorded':
            return 'ready' if l.get('has_video') else 'missing_video'
        return 'ready' if l.get('starts_at') else 'draft'

    def _view_lesson(self, l, no):
        out = copy.deepcopy(l)
        st = self._lesson_state(l)
        out.update({'state': st, 'state_ar': STATE_AR[st], 'no': no, 'kind_ar': KIND_AR[l['kind']]})
        return out

    def view(self, c):
        units, lessons, no, gaps, kinds = [], 0, 0, [], set()
        for u in c['units']:
            ls = []
            for l in u['lessons']:
                no += 1
                v = self._view_lesson(l, no)
                ls.append(v)
                kinds.add(l['kind'])
                if v['state'] != 'ready':
                    gaps.append('الدرس %s «%s» (%s)' % (ar(no), l['title'], STATE_AR[v['state']]))
            units.append({'id': u['id'], 'title': u['title'], 'no': len(units) + 1, 'lessons': ls})
            lessons += len(ls)
        if not c['meta'].get('description'):
            gaps.insert(0, 'وصف الدورة')
        if not lessons:
            gaps.append('دروس الدورة')
        open_n = sum(1 for n in c['notes'] if n['status'] == 'open')
        total = len(c['notes'])
        return {'id': c['id'], 'slug': c['slug'], 'type': c['type'], 'status': c['status'], 'status_ar': STATUS_AR[c['status']], 'meta': copy.deepcopy(c['meta']),
                'outline': {'cases': list(c['cases']), 'units': units}, 'kinds': sorted(kinds), 'mixed': len(kinds) > 1, 'lessons_count': lessons,
                'notes': {'items': copy.deepcopy(c['notes']), 'total': total, 'edited': total - open_n, 'open': open_n, 'summary_ar': 'عُدّل %s من %s' % (ar(total - open_n), ar(total))},
                'gaps': gaps, 'pricing': {'is_free': c['is_free'], 'price_set': c['price_set']}, 'owner': copy.deepcopy(c['owner']), 'updated_at': c['updated_at']}

    # ------------------------------------------------------------------ التوجيه
    def _route(self, method, path, params, body):
        forced = self.forced.get((method.upper(), path))
        if forced is not None:
            return forced
        out = self._c2(method.upper(), path, params or {}, body or {})
        if out is not None:
            return out
        return super(Courses2Platform, self)._route(method, path, params, body)

    def _need_confirm(self, body):
        if body.get('confirmed') is not True or not str(body.get('by') or '').strip():
            return 400, {'detail': CONFIRM_DETAIL}
        return None

    def _c2(self, method, path, params, body):
        if not path.startswith('/api/bridge/courses2'):
            return None
        self.c2calls.append((method, path, copy.deepcopy(body)))
        rest = path[len('/api/bridge/courses2'):]
        if rest == '':
            if method == 'GET':
                rows = [{'id': c['id'], 'slug': c['slug'], 'title': c['meta']['title'], 'status': c['status'], 'status_ar': STATUS_AR[c['status']],
                         'kinds': self.view(c)['kinds'], 'lessons_count': self.view(c)['lessons_count'], 'open_notes': sum(1 for n in c['notes'] if n['status'] == 'open'),
                         'owner': {'email': c['owner']['email'], 'platform_owned': c['owner']['platform_owned']}, 'updated_at': c['updated_at']} for c in self.c2]
                return 200, {'ok': True, 'count': len(rows), 'courses': rows}
            if method == 'POST':
                bad = self._need_confirm(body)
                if bad:
                    return bad
                title = str(body.get('title') or '').strip()
                if not title:
                    return 400, {'detail': 'اكتب عنوان الدورة'}
                key = str(body.get('idem_key') or '')
                if not 8 <= len(key) <= 80:
                    return 400, {'detail': 'مفتاح منع التكرار غير صالح'}
                if not body.get('owner_email') and body.get('platform_owned') is not True:
                    return 422, {'detail': 'اكتب بريد المدرّب صاحب الدورة — أو علّم «دورة من المنصّة»'}
                if key in self.idem:
                    return 200, {'ok': True, 'created': False, 'course': self.view(self.idem[key])}
                self.c2n += 1
                c = {'id': 'CRS_NEW%03d' % self.c2n, 'slug': 'new-%d' % self.c2n, 'type': 'recorded_paid', 'status': 'draft',
                     'owner': {'email': body.get('owner_email', ''), 'name': 'مدرّب' if body.get('owner_email') else 'البروفيسور', 'platform_owned': body.get('platform_owned') is True},
                     'meta': {'title': title, 'subtitle': '', 'description': '', 'cover': '', 'level': '', 'outcomes': []}, 'cases': [], 'is_free': False, 'price_set': False, 'notes': [], 'units': [],
                     'updated_at': '2026-10-31T09:00:00+00:00'}
                self.c2.append(c)
                self.idem[key] = c
                return 200, {'ok': True, 'created': True, 'course': self.view(c)}
            return None
        m = re.match(r'^/([^/]+)(?:/(.*))?$', rest)
        if not m:
            return None
        c = self._find2(m.group(1))
        sub = m.group(2) or ''
        if c is None:
            return 404, {'detail': 'الدورة غير موجودة'}
        if method == 'GET' and sub == '':
            return 200, {'ok': True, 'course': self.view(c)}
        pm = re.match(r'^lessons/([^/]+)/preview$', sub)
        if pm:
            return self._preview(c, pm.group(1), method, body)
        if method == 'POST' and sub == 'brain/draft':
            return self._brain(c, body)
        if method not in ('PUT', 'POST'):
            return None
        bad = self._need_confirm(body)
        if bad:
            return bad
        if sub == 'data' and method == 'PUT':
            cover = body.get('cover')
            if cover and not str(cover).startswith('https://'):
                return 400, {'detail': 'رابط الغلاف لازم يبدأ بـ https://'}
            for k in ('title', 'subtitle', 'description', 'cover', 'level', 'outcomes'):
                if k in body:
                    c['meta'][k] = body[k]
            return 200, {'ok': True, 'course': self.view(c)}
        if sub == 'structure' and method == 'PUT':
            return self._structure(c, body)
        lm = re.match(r'^lessons/([^/]+)$', sub)
        if lm and method == 'PUT':
            return self._lesson(c, lm.group(1), body)
        if sub == 'publish' and method == 'POST':
            if c['status'] == 'published':
                return 409, {'detail': 'الدورة منشورة بالفعل'}
            v = self.view(c)
            if v['gaps']:
                return 422, {'detail': 'الدورة ناقصها: ' + '، '.join(v['gaps'])}
            c['status'] = 'published'
            return 200, {'ok': True, 'course': self.view(c)}
        if sub == 'pause' and method == 'POST':
            if c['status'] != 'published':
                return 409, {'detail': 'الدورة غير منشورة، فلا يمكن إيقافها'}
            c['status'] = 'paused'
            return 200, {'ok': True, 'course': self.view(c)}
        if sub == 'return' and method == 'POST':
            if c['status'] != 'review':
                return 409, {'detail': 'تُرجَع الدورة من حالة «عند المراجعة» فقط'}
            notes = body.get('notes') or []
            if not 1 <= len(notes) <= 40:
                return 400, {'detail': 'ملاحظة واحدة على الأقل، وحتى ٤٠'}
            for i, n in enumerate(notes):
                c['notes'].append({'id': 'nn%d' % (len(c['notes']) + 1), 'target_kind': n['target_kind'], 'target_id': n.get('target_id', ''), 'target_label': 'الدورة' if n['target_kind'] == 'course' else 'الدرس',
                                   'target_no': 0, 'target_title': '', 'text': n['text'], 'status': 'open', 'status_ar': 'لم يُعدّل', 'created_at': '2026-10-31T09:00:00+00:00', 'by': body['by']})
            c['status'] = 'changes'
            return 200, {'ok': True, 'course': self.view(c)}
        if sub == 'upload' and method == 'POST':
            if not self.bunny:
                return 200, {'ok': True, 'configured': False}
            return 200, {'ok': True, 'configured': True, 'video_id': 'vid-0000-aaaa-1111', 'library_id': '9001', 'upload_url': 'https://video.bunnycdn.com/tusupload', 'expires': 1767000000,
                         'headers': {'AuthorizationSignature': 'sig-abc', 'AuthorizationExpire': '1767000000', 'VideoId': 'vid-0000-aaaa-1111', 'LibraryId': '9001'}}
        return None

    # —— الهيكل: استبدال كامل. درس بمعرّف يحتفظ بمحتواه، ودرس بلا معرّف جديد ولازم kind.
    def _structure(self, c, body):
        units = body.get('units')
        if not isinstance(units, list) or not units:
            return 400, {'detail': 'الهيكل لازم يحتوي وحدة واحدة على الأقل'}
        old = {l['id']: l for u in c['units'] for l in u['lessons']}
        kept, out = set(), []
        for ui, u in enumerate(units):
            if not str(u.get('title') or '').strip():
                return 400, {'detail': 'الوحدة %s بلا عنوان' % ar(ui + 1)}
            ls = []
            for l in u.get('lessons') or []:
                if not str(l.get('title') or '').strip():
                    return 400, {'detail': 'درس بلا عنوان في الوحدة %s' % ar(ui + 1)}
                lid = l.get('id')
                if lid:
                    if lid not in old:
                        return 400, {'detail': 'درس غير موجود: ' + lid}
                    if l.get('kind') and l['kind'] != old[lid]['kind']:
                        return 400, {'detail': 'نوع الدرس لا يتغيّر بعد إنشائه'}
                    x = copy.deepcopy(old[lid])
                    x['title'] = l['title']
                    kept.add(lid)
                else:
                    kind = l.get('kind')
                    if kind not in KIND_AR:
                        return 400, {'detail': 'الدرس الجديد «%s» يحتاج نوعًا: تفاعلي أو مسجّل أو مباشر' % l['title']}
                    self.c2n += 1
                    base = {'id': 'N%03d' % self.c2n, 'kind': kind, 'title': l['title']}
                    if kind == 'interactive':
                        base.update({'time': 0, 'for': [], 'hero': '', 'motion': '', 'blocks': []})
                    elif kind == 'recorded':
                        base.update({'video': {}, 'has_video': False, 'duration_seconds': 0, 'is_preview': False, 'chapters': [], 'checkpoints': [], 'summary': [], 'transcript': ''})
                    else:
                        base.update({'starts_at': '', 'duration_min': 0, 'zoom_link': '', 'recording_url': '', 'status': 'scheduled', 'quiz': None})
                    x = base
                ls.append(x)
            out.append({'id': u.get('id') or 'U%03d' % (len(out) + 100 + self.c2n), 'title': u['title'], 'lessons': ls})
        removed = [i for i in old if i not in kept]
        if removed and c['status'] == 'published':
            return 409, {'detail': 'دورة منشورة فيها متعلّمون: لا يمكن حذف درس منها'}
        c['units'] = out
        if 'cases' in body:
            c['cases'] = list(body['cases'])
        return 200, {'ok': True, 'course': self.view(c)}

    def _lesson(self, c, lid, body):
        for u in c['units']:
            for l in u['lessons']:
                if l['id'] != lid:
                    continue
                if l['kind'] == 'interactive':
                    blocks = body.get('blocks')
                    if blocks is not None:
                        for b in blocks:
                            if b.get('type') not in BLOCK_TYPES:
                                return 400, {'detail': 'المحتوى التفاعلي فيه أخطاء — نوع كتلة غير معروف: ' + str(b.get('type'))}
                            if b['type'] in ('decision', 'situation') and not 2 <= len(b.get('options') or []) <= 3:
                                return 400, {'detail': 'المحتوى التفاعلي فيه أخطاء — الدرس «%s»: ::%s لازم يكون فيه من 2 لـ3 اختيارات — الموجود %d' % (l['title'], 'قرار' if b['type'] == 'decision' else 'موقف', len(b.get('options') or []))}
                        l['blocks'] = blocks
                    for k in ('time', 'for', 'hero', 'motion'):
                        if k in body:
                            l[k] = body[k]
                elif l['kind'] == 'recorded':
                    if 'video' in body:
                        v = body['video'] or {}
                        if v.get('bunny_video_id') and v.get('url'):
                            return 400, {'detail': 'فيديو مرفوع ورابط معًا: اختر واحدًا'}
                        if v.get('url') and not re.match(r'^https://(www\.)?(youtube\.com|youtu\.be|drive\.google\.com)/|\.mp4$', v['url']):
                            return 400, {'detail': 'الرابط غير مدعوم: استخدم يوتيوب أو درايف أو ملف mp4'}
                        l['video'] = {'bunny_video_id': v.get('bunny_video_id', ''), 'bunny_library_id': '9001' if v.get('bunny_video_id') else '', 'url': v.get('url', '')}
                        l['has_video'] = bool(v.get('bunny_video_id') or v.get('url'))
                    for k in ('duration_seconds', 'is_preview', 'chapters', 'checkpoints', 'summary', 'transcript'):
                        if k in body:
                            l[k] = body[k]
                else:
                    for k in ('starts_at', 'duration_min', 'zoom_link', 'recording_url', 'status', 'quiz'):
                        if k in body:
                            l[k] = body[k]
                if 'title' in body and str(body['title']).strip():
                    l['title'] = body['title']
                return 200, {'ok': True, 'course': self.view(c)}
        return 404, {'detail': 'الدرس غير موجود'}

    def _preview(self, c, lid, method, body):
        for u in c['units']:
            for l in u['lessons']:
                if l['id'] == lid:
                    src = l if method == 'GET' else dict(l, **{k: v for k, v in body.items() if k not in ('confirmed', 'by')})
                    if method == 'POST' and l['kind'] == 'interactive':
                        for b in src.get('blocks') or []:
                            if b.get('type') in ('decision', 'situation') and not 2 <= len(b.get('options') or []) <= 3:
                                return 400, {'detail': 'المحتوى التفاعلي فيه أخطاء — الدرس «%s»: ::قرار لازم يكون فيه من 2 لـ3 اختيارات — الموجود %d' % (l['title'], len(b.get('options') or []))}
                    pv = {'kind': l['kind'], 'lesson_id': lid}
                    if l['kind'] == 'interactive':
                        pv.update({'story': {'blocks': src.get('blocks') or []}, 'state': {}, 'progress': {}})
                    else:
                        pv['lesson'] = {'id': lid, 'title': src['title']}
                    return 200, {'ok': True, 'saved': False, 'preview': pv}
        return 404, {'detail': 'الدرس غير موجود'}

    def _brain(self, c, body):
        kind = body.get('kind') or ('from_material' if len(str(body.get('material') or '')) >= 80 else 'free')
        if kind == 'activity_decision':
            blk = {'type': 'decision', 'text': 'مقاول تأخر في التسليم أسبوعين، والعميل غاضب.', 'question': 'تختار إيه؟',
                   'options': [{'text': 'أوثّق التأخير كتابةً', 'result': 'حقك محفوظ', 'comment': 'التوثيق يمنع الإنكار'}, {'text': 'أتجاهل التأخير', 'result': 'تضيع الحجة', 'comment': 'السكوت يُضعف موقفك'}]}
            valid = 'غير صالح' not in str(body.get('instruction') or '')
            return 200, {'ok': True, 'saved': False, 'kind': kind, 'draft': {'block': blk}, 'valid': valid, 'issues': [] if valid else ['القرار يحتاج اختيارين على الأقل']}
        if kind == 'shorter_title':
            return 200, {'ok': True, 'saved': False, 'kind': kind, 'draft': {'titles': ['العقد أولًا', 'اكتب قبل أن تبدأ', 'حماية الاتفاق']}}
        if kind == 'video_script':
            return 200, {'ok': True, 'saved': False, 'kind': kind, 'draft': {'transcript': 'أهلًا بكم. في هذا الدرس نتعرّف على أركان العقد.\nأولًا: الأطراف. ثانيًا: المحل. ثالثًا: المقابل.'}}
        if kind == 'from_material':
            if len(str(body.get('material') or '')) < 80:
                return 400, {'detail': 'ألصق مادة من 80 حرفًا على الأقل'}
            return 200, {'ok': True, 'saved': False, 'kind': kind, 'units': 2, 'lessons': 3, 'draft': {'units': [
                {'title': 'المبادئ', 'lessons': [{'title': 'تعريف العقد', 'kind': 'recorded', 'summary': ['العقد اتفاق', 'له أركان'], 'transcript': 'نص الدرس الأول.', 'state': 'missing_video', 'state_ar': 'ينقصه فيديو'},
                                               {'title': 'أنواع العقود', 'kind': 'recorded', 'summary': ['عقود مسمّاة وغير مسمّاة'], 'transcript': 'نص الدرس الثاني.', 'state': 'missing_video', 'state_ar': 'ينقصه فيديو'}]},
                {'title': 'التطبيق', 'lessons': [{'title': 'صياغة بند', 'kind': 'recorded', 'summary': ['اكتب بوضوح'], 'transcript': 'نص الدرس الثالث.', 'state': 'missing_video', 'state_ar': 'ينقصه فيديو'}]}]}}
        return 200, {'ok': True, 'saved': False, 'kind': 'free', 'answer': 'اكتب الأطراف كاملة ثم المحل ثم المقابل، وراجع كل بند قبل التوقيع.'}
