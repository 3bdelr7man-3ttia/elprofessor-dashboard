# -*- coding: utf-8 -*-
"""«العقل» الجولة ٢ — بيانات وهمية لواجهة البطاقات والصف والشريط (P4). ⛔ صفر شبكة: مسارات `/api/v2/brain/*` الجديدة بتتردّ من المتصفح نفسه
(`ctx.route`) من جدول في الذاكرة، والباقي بيعدّي للأداة العادية (`ef_route_harness`) اللي بتقفل أي أصل خارجي. ولا نداء ذكاء اصطناعي.

    bk = BrainBackend(mode='ready')
    bk.install(ctx)          # بعد `harness.context(...)`، قبل فتح الصفحة

`mode` = ready (رأي جاهز فورًا) · queued (queued ثم الرأي بعد عدة استعلامات) · fail (no_writer) · cap · off · busy · closed (404 كأن الخادم بلا المسار).
`bk.opinion_posts` كل جسم أُرسل لـ`/opinion` (لاختبار إن لا بريد ولا هاتف ولا مفتاح خارج القائمة) · `bk.writes` كل (مسار، جسم) اعتماد/رفض.
"""
import copy
import datetime
import json
import re
from urllib.parse import urlparse, parse_qs

DASH = 'https://dash.test'

OPINIONS = {
    'trainer': {'text': 'الطلب مكتمل في الخبرة والمرفقات، لكن العنوان المهني عام. يُستحسن فتح الطلب وقراءة المرفقات قبل القبول.',
                'recommend': 'open', 'why': 'المرفقات لم تُقرأ بعد.'},
    'dispute': {'text': 'الاعتراض واضح، وردّ الخبير لم يصل بعد. الأموال محجوزة لحين قرارك، فالأفضل قراءة الرأيين قبل أي حسم.',
                'recommend': '', 'why': 'القرار هنا يخص الأموال.'},
    'join': {'text': 'الطلب يحمل ترخيصًا لكن رقم القيد ناقص. لا يُقبل قبل استكماله.', 'recommend': 'open', 'why': 'رقم القيد شرط للقبول.'},
    'pending_user': {'text': 'بيانات الزائر متسقة، ويمكن فتح المنصة له.', 'recommend': 'approve', 'why': 'لا علامات تستدعي المراجعة.'},
    'review': {'text': 'رأي الخبير ينتظر مراجعتك، وصاحب الطلب ينتظر.', 'recommend': 'open', 'why': 'لا يصله الرأي قبل موافقتك.'},
    'message': {'text': 'سؤال عن الفرق بين الباقتين. يكفي ردّ قصير يوضح الفرق.', 'recommend': 'open', 'why': 'الرد يحتاج صياغتك.'},
}
DEFAULT_OPINION = {'text': 'هذا البند يحتاج قراءتك قبل القرار.', 'recommend': 'wait', 'why': 'لا جديد يستدعي التعجيل.'}

REPLY_MEMBER = ('مرحبًا بك، وشكرًا على تواصلك معنا. تختلف الباقتان في عدد الملفات المتاحة كل شهر وفي سرعة الرد، '
                'ويمكن الانتقال من إحداهما إلى الأخرى في أي وقت دون فقد ما سبق. يسعدنا توضيح المزيد عند الحاجة.')

ITEMS = [
    {'id': 'rd_member', 'producer': 'reply_draft', 'section': 'people', 'kind': 'draft', 'tag': 'مسودة رد',
     'target_label': 'رد على رسالة: سؤال عن الاشتراك', 'approve_label': 'أرسل الرد', 'body': {'text': REPLY_MEMBER}, 'age_min': 40},
    {'id': 'rd_visitor', 'producer': 'reply_draft', 'section': 'people', 'kind': 'draft', 'tag': 'مسودة رد',
     'target_label': 'رد على رسالة: طلب تعاون', 'approve_label': 'انسخ الرد',
     'body': {'text': 'شكرًا على اهتمامكم بالتعاون. يسعدنا الاطلاع على نماذج من أعمالكم السابقة، ثم نحدد الخطوة التالية معًا.'}, 'age_min': 130,
     'copy_text': 'شكرًا على اهتمامكم بالتعاون. يسعدنا الاطلاع على نماذج من أعمالكم السابقة، ثم نحدد الخطوة التالية معًا.'},
    {'id': 'rd_site', 'producer': 'reply_draft', 'section': 'people', 'kind': 'draft', 'tag': 'مسودة رد',
     'target_label': 'رد على رسالة من الموقع: مشكلة في الدخول', 'approve_label': 'احفظ الرد وانسخه',
     'body': {'text': 'نعتذر عن هذا الإزعاج. جرّبوا طلب رابط جديد للدخول، وإن لم يصل خلال دقائق فأخبرونا ليُراجع الأمر.'}, 'age_min': 300,
     'copy_text': 'نعتذر عن هذا الإزعاج. جرّبوا طلب رابط جديد للدخول، وإن لم يصل خلال دقائق فأخبرونا ليُراجع الأمر.'},
    {'id': 'rd_lead', 'producer': 'reply_draft', 'section': 'people', 'kind': 'draft', 'tag': 'مسودة رد',
     'target_label': 'رد على طلب تواصل من الشات', 'approve_label': 'انسخ الرسالة وعلّمه تم',
     'body': {'text': 'أهلًا بكم. وصلنا طلبكم، ويسعدنا أن نعرف طبيعة القضية ومدة الخبرة المطلوبة لنرشّح الأنسب.'}, 'age_min': 700,
     'copy_text': 'أهلًا بكم. وصلنا طلبكم، ويسعدنا أن نعرف طبيعة القضية ومدة الخبرة المطلوبة لنرشّح الأنسب.'},
    {'id': 'seo_1', 'producer': 'seo_notes', 'section': 'content', 'kind': 'note', 'tag': 'ملاحظة على مسودة',
     'target_label': 'مسودة: أحكام التقادم في العقود التجارية', 'approve_label': '',
     'body': {'text': 'العنوان أطول من المناسب للبحث، ولا توجد جملة افتتاحية تذكر الموضوع. يُستحسن تقصير العنوان وإضافة وصف قصير.'}, 'age_min': 90},
    {'id': 'seo_2', 'producer': 'seo_notes', 'section': 'content', 'kind': 'note', 'tag': 'ملاحظة على مسودة',
     'target_label': 'مسودة: كيف تقرأ عقد الإيجار', 'approve_label': '',
     'body': {'text': 'المقال خالٍ من العناوين الفرعية، وعدد كلماته قليل. أضيفوا عناوين تقسّم الشرح إلى أجزاء.'}, 'age_min': 200},
    {'id': 'course_1', 'producer': 'course_review', 'section': 'courses', 'kind': 'draft', 'tag': 'مراجعة دورة',
     'target_label': 'دورة: عقود المقاولات', 'approve_label': 'افتح الدورة',
     'body': {'text': 'ينقصها: الوصف المختصر ومخرجات التعلم. أصلحوا ذلك قبل النشر.', 'recommend': 'fix_first'}, 'age_min': 500},
    {'id': 'mk_1', 'producer': 'market_match', 'section': 'market', 'kind': 'draft', 'tag': 'ربط بدورة',
     'target_label': 'طلب: أريد تعلّم صياغة العقود', 'approve_label': 'اربطه بالدورة',
     'body': {'text': 'الطلب يطابق دورة «صياغة العقود». يُقترح ربطه بها.', 'course_id': 'c1'}, 'age_min': 800},
]


def _iso(minutes_ago):
    return (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)).isoformat()


def public(item, status='proposed'):
    """ما تعيده `GET /items` بالقائمة المسموحة (لا facts ولا meta ولا copy_text)."""
    out = {k: item.get(k) for k in ('id', 'producer', 'section', 'kind', 'target_label', 'body', 'tag', 'approve_label')}
    out.update({'status': status, 'source': 'ai', 'created_at': _iso(item.get('age_min', 30)), 'decided_at': None, 'decided_by': '', 'last_error': ''})
    return out


class BrainBackend(object):
    def __init__(self, mode='ready', items=None, polls_before_ready=2, lookup_fill=False):
        self.mode = mode
        self.lookup_fill = lookup_fill      # True ⇒ `lookup` يعيد رأيًا مخزّنًا لأي بطاقة (لقطات التذاكر)
        self.items = copy.deepcopy(ITEMS if items is None else items)
        self.cache = {}
        self.polls = {}
        self.polls_before_ready = polls_before_ready
        self.opinion_posts = []
        self.lookup_posts = []
        self.writes = []
        self.list_gets = 0
        self.apply = {}                 # item_id ⇒ ('ok',) | ('no_reply',) | ('error', status, msg) | ('conflict',)
        self.hold_apply = False

    # ---------------------------------------------------------------- الرأي
    def _opinion_item(self, kind, card_id):
        spec = copy.deepcopy(OPINIONS.get(kind, DEFAULT_OPINION))
        return {'id': 'op_' + re.sub(r'\W', '', card_id)[:20], 'producer': 'opinion', 'section': 'home', 'kind': 'opinion', 'target_label': card_id,
                'body': spec, 'status': 'done_alone', 'source': 'ai', 'created_at': _iso(7), 'decided_at': None, 'decided_by': '', 'tag': '', 'approve_label': '', 'last_error': ''}

    def _ask(self, kind, card_id):
        if card_id in self.cache:
            return {'item': self.cache[card_id]}
        if self.mode == 'ready':
            self.cache[card_id] = self._opinion_item(kind, card_id)
            return {'item': self.cache[card_id]}
        if self.mode == 'queued':
            self.polls.setdefault(card_id, 0)
            return {'queued': True}
        reason = {'fail': 'no_writer', 'cap': 'cap', 'off': 'off', 'busy': 'busy'}.get(self.mode, 'not_supported')
        return {'item': None, 'reason': reason}

    def _lookup(self, cards):
        out = {}
        for c in cards:
            cid = c.get('card_id')
            if cid in self.cache:
                out[cid] = self.cache[cid]
            elif self.lookup_fill and c.get('kind') in OPINIONS:
                self.cache[cid] = self._opinion_item(c.get('kind'), cid)
                out[cid] = self.cache[cid]
            elif self.mode == 'queued' and cid in self.polls:
                self.polls[cid] += 1
                if self.polls[cid] >= self.polls_before_ready:
                    self.cache[cid] = self._opinion_item(c.get('kind'), cid)
                    out[cid] = self.cache[cid]
                else:
                    out[cid] = None
            else:
                out[cid] = None
        return {'items': out}

    # ---------------------------------------------------------------- الاعتماد
    def _decide(self, item_id, which, body):
        self.writes.append(('/api/v2/brain/items/%s/%s' % (item_id, which), body))
        it = next((x for x in self.items if x['id'] == item_id), None)
        if it is None:
            return 404, {'error': 'هذا الاقتراح غير موجود'}
        script = self.apply.get(item_id, ('ok',))
        if script[0] == 'conflict':
            self.items = [x for x in self.items if x['id'] != item_id]
            return 409, {'error': 'حُسم هذا الاقتراح من قبل'}
        if script[0] == 'error':
            return script[1], {'error': script[2]}
        if script[0] == 'no_reply':
            self.items = [x for x in self.items if x['id'] != item_id]
            return 200, {'ok': False, 'no_reply': True, 'item': public(it, 'unknown')}
        self.items = [x for x in self.items if x['id'] != item_id]
        resp = {'ok': True, 'item': public(it, 'rejected' if which != 'approve' else ('edited' if body.get('text') else 'approved'))}
        if which == 'approve' and it.get('copy_text'):
            resp['copy_text'] = body.get('text') or it['copy_text']
        return 200, resp

    # ---------------------------------------------------------------- المتصفح
    def install(self, ctx):
        ctx.route(lambda url: urlparse(url).netloc == 'dash.test' and urlparse(url).path.startswith('/api/v2/brain/')
                  and urlparse(url).path.split('/api/v2/brain/')[1].split('/')[0] in ('items', 'opinion', 'opinions'), self._handle)

    def _fulfill(self, route, status, payload):
        route.fulfill(status=status, headers={'content-type': 'application/json'}, body=json.dumps(payload, ensure_ascii=False))

    def _handle(self, route):
        req = route.request
        u = urlparse(req.url)
        path = u.path[len('/api/v2/brain/'):]
        try:
            body = json.loads(req.post_data) if req.post_data else {}
        except Exception:
            body = {}
        if self.mode == 'closed':
            return self._fulfill(route, 404, {'error': 'غير متاح'})
        if path == 'items' and req.method == 'GET':
            self.list_gets += 1
            status = (parse_qs(u.query).get('status') or ['proposed'])[0]
            return self._fulfill(route, 200, {'items': [public(x) for x in self.items] if status in ('proposed', 'all') else []})
        if path == 'opinion' and req.method == 'POST':
            self.opinion_posts.append(body)
            return self._fulfill(route, 200, self._ask(body.get('kind'), body.get('card_id')))
        if path == 'opinions/lookup' and req.method == 'POST':
            self.lookup_posts.append(body)
            return self._fulfill(route, 200, self._lookup(body.get('cards') or []))
        m = re.match(r'^items/([^/]+)/(approve|reject|discard)$', path)
        if m and req.method == 'POST':
            status, payload = self._decide(m.group(1), m.group(2), body)
            return self._fulfill(route, status, payload)
        return self._fulfill(route, 404, {'error': 'مسار غير معروف'})
