# -*- coding: utf-8 -*-
"""منصّة وهميّة لقسم «التقارير» (الجولة النهائية): فوق `V2Platform` وتضيف الجسور التي يقرؤها القسم:

  /api/bridge/users            ٦٠٠ مستخدم موزّعين على ٢٠٠ يوم (يحترم `limit`)
  /api/bridge/market/requests  ٦٠ طلب سوق من الأعضاء
  /api/bridge/chat-insights    تحليل أسئلة المحادثة كاملًا (+ تفاصيل سؤال + تصنيف)
  /api/bridge/reports/funnel   ٤٠٤ افتراضيًا · `funnel=True` ⇒ حمولة N3 كاملة
  /api/bridge/reports/weekly/* ٤٠٤ افتراضيًا · `delivery=True` ⇒ N6 (الحالة + الإرسال)

⛔ صفر شبكة: كله في الذاكرة. الأسماء والرسائل مخترعة. `rp_force[(method, path)] = (status, body)` يفرض ردًّا، و`rp_down` مجموعة مسارات ترد ٥٠٢.
"""
import copy
import datetime
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import v2_fixtures as v2fx   # noqa: E402

UTC = datetime.timezone.utc

QUESTION_TEXTS = ['سؤال خاص عن فسخ عقد الإيجار رقم ' + ''.join('٠١٢٣٤٥٦٧٨٩'[int(c)] for c in str(i)) for i in range(1, 41)]
USER_EMAILS = ['reportuser%d@example.test' % i for i in range(1, 601)]
ASKER_EMAIL = 'asker.signed@example.test'
ASKER_NAME = 'سائلة مسجّلة'

UNMET = [{'label': 'تأسيس الشركات', 'count': 41, 'sample_question': 'كيف أؤسس شركة في الخليج؟'},
         {'label': 'مراجعة عقود العمل', 'count': 12, 'sample_question': 'هل هذا العقد قانوني؟'}]


def _iso(dt):
    return dt.astimezone(UTC).strftime('%Y-%m-%dT%H:%M:%S+00:00')


def chat_payload(now, unclassified=3, empty=False):
    recent = []
    if not empty:
        segs = ['lawyer', 'student', 'company', 'individual', 'influencer', 'unknown']
        ctrs = ['egypt', 'saudi', 'uae', 'egypt', 'unknown', 'qatar']
        cats = ['مدني', 'تجاري', 'عمالي', 'civil', '', 'عقاري وتوثيق']
        for i in range(40):
            recent.append({'id': 'q%02d' % (i + 1), 'question': QUESTION_TEXTS[i], 'segment': segs[i % 6], 'country': ctrs[i % 6], 'category': cats[i % 6],
                           'intent': 'consult' if i % 2 else 'draft', 'needs_expert': i % 3 == 0, 'anonymous': i % 4 != 0,
                           'created_at': _iso(now - datetime.timedelta(hours=3 + i * 20))})
    return {'total': 0 if empty else 1840, 'needs_expert': 0 if empty else 412, 'needs_expert_rate': 0.224, 'anonymous': 1310, 'authed': 530,
            'by_segment': [{'segment': 'lawyer', 'count': 640}, {'segment': 'student', 'count': 420}, {'segment': 'company', 'count': 210},
                           {'segment': 'unknown', 'count': 380}, {'segment': 'influencer', 'count': 190}],
            'by_country': [{'country': 'egypt', 'count': 1220}, {'country': 'saudi', 'count': 310}, {'country': 'uae', 'count': 140},
                           {'country': 'unknown', 'count': 170}],
            'by_category': [{'category': 'مدني', 'count': 530}, {'category': 'تجاري', 'count': 410}, {'category': 'عمالي', 'count': 220}],
            'by_subcategory': [{'subcategory': 'عقود الإيجار', 'count': 210}, {'subcategory': 'تأسيس الشركات', 'count': 160}],
            'by_intent': [{'intent': 'استشارة', 'count': 900}, {'intent': 'صياغة عقد', 'count': 520}],
            'unmet': [] if empty else copy.deepcopy(UNMET), 'classified': 1560 if not unclassified else 1837 - unclassified, 'unclassified': unclassified,
            'recent_questions': recent, 'expert_opinions': {'requested': 112, 'paid': 61, 'conversion_rate': 0.545}}


class ReportsPlatform(v2fx.V2Platform):
    """`now` = لحظة المنصة (تُحسب منها تواريخ المستخدمين والطلبات)، افتراضيًا اللحظة الحقيقية."""

    def __init__(self, empty=False, now=None, funnel=False, delivery=False, unclassified=3, **kw):
        super(ReportsPlatform, self).__init__(empty=empty, **kw)
        self.rnow = now or datetime.datetime.now(UTC)
        self.funnel_on = funnel
        self.delivery_on = delivery
        self.rp_down = set()
        self.rp_force = {}
        self.delivered = []
        self.classify_posts = []
        self.chat = chat_payload(self.rnow, unclassified=unclassified, empty=empty)
        n = 0 if empty else 600
        self.r_users = []
        for i in range(n):
            self.r_users.append({'id': 'ru-%d' % i, 'full_name': 'مستخدم تقرير %d' % i, 'email': USER_EMAILS[i], 'phone': '0100%07d' % i, 'role': 'user',
                                 'created_at': _iso(self.rnow - datetime.timedelta(hours=1 + i * 8)), 'is_active': True})
        self.r_market = []
        for i in range(0 if empty else 60):
            st = 'open' if i % 3 else ('matched' if i % 2 else 'closed')
            offers = 0 if (i % 4 == 0 or st == 'open' and i % 5 == 0) else (1 + i % 3)
            self.r_market.append({'id': 'rm-%d' % i, 'kind': 'request', 'title': 'طلب سوق %d' % i, 'status': st, 'offer_count': offers,
                                  'need_kind': 'course' if i % 6 == 0 else 'expert', 'member_alias': 'عضو %d' % i, 'is_test': False,
                                  'created_at': _iso(self.rnow - datetime.timedelta(hours=2 + i * 30))})
        self.funnel_calls = []

    # -------------------------------------------------------------- حمولة N3
    def funnel_payload(self, params):
        f, u = params.get('from'), params.get('until')
        base = 1.0 if f and f > '2026-09-15' else 0.82
        return {'ok': True, 'from': f, 'until': u, 'tz': 'Africa/Cairo', 'generated_at': _iso(self.rnow),
                'stages': {'visits': int(12400 * base), 'visitors': int(9100 * base), 'asked': int(3100 * base), 'signed_up': int(1240 * base), 'opened': int(410 * base),
                           'paid_people': int(268 * base), 'paid_orders': int(301 * base)},
                'by_day': [{'date': (datetime.date.fromisoformat(f) + datetime.timedelta(days=i)).isoformat(), 'visits': 300 + i * 9, 'signups': 30 + i,
                            'paid_orders': 6 + i % 4, 'income': [{'currency': 'EGP', 'amount': 3000.0 + i * 50}]}
                           for i in range((datetime.date.fromisoformat(u) - datetime.date.fromisoformat(f)).days)] if f and u else [],
                'origins': {'channels': [{'key': 'google', 'visits': 4700, 'signups': 470, 'paid_people': 101}, {'key': 'meta', 'visits': 3300, 'signups': 330, 'paid_people': 60},
                                         {'key': 'whatsapp', 'visits': 1900, 'signups': 150, 'paid_people': 52}, {'key': 'direct', 'visits': 1500, 'signups': 150, 'paid_people': 30},
                                         {'key': 'invite', 'visits': 700, 'signups': 90, 'paid_people': 20}, {'key': 'other', 'visits': 300, 'signups': 50, 'paid_people': 5}],
                            'countries': [{'code': 'EG', 'signups': 790, 'paid_people': 170}, {'code': 'SA', 'signups': 230, 'paid_people': 50}, {'code': 'AE', 'signups': 110, 'paid_people': 30},
                                          {'code': 'KW', 'signups': 40, 'paid_people': 8}, {'code': 'ZZ', 'signups': 70, 'paid_people': 10}],
                            'top_pages': [{'path': '/blog/rent', 'title': 'فسخ عقد الإيجار', 'visits': 1900, 'signups': 120},
                                          {'path': '/blog/company', 'title': 'تأسيس شركة', 'visits': 1200, 'signups': 80},
                                          {'path': '/courses', 'title': 'الدورات', 'visits': 900, 'signups': 60}]},
                'sections': {'files': {'opened': 160, 'paid_orders': 41, 'income': [{'currency': 'EGP', 'amount': 112400.0}]},
                             'courses': {'page_visits': 2100, 'enrolled': 300, 'paid_orders': 60, 'income': [{'currency': 'EGP', 'amount': 31000.0}]},
                             'books': {'page_visits': 900, 'buy_clicks': 270, 'paid_orders': 33, 'income': [{'currency': 'EGP', 'amount': 4900.0}]},
                             'content': {'published': 24, 'visits': 4200, 'signups_from_articles': 85}}}

    # -------------------------------------------------------------- التوجيه
    def _route(self, method, path, params, body):
        m = method.upper()
        forced = self.rp_force.get((m, path))
        if forced is not None:
            return forced
        if path in self.rp_down:
            return 502, {'detail': 'تعذر الاتصال'}
        out = self._rp(m, path, params, body)
        if out is not None:
            return out
        return super(ReportsPlatform, self)._route(method, path, params, body)

    def _rp(self, m, path, params, body):
        if m == 'GET' and path == '/api/bridge/users':
            lim = int(params.get('limit') or 200)
            rows = self.r_users[:lim]
            return 200, {'users': copy.deepcopy(rows), 'count': len(rows)}
        if m == 'GET' and path == '/api/bridge/market/requests':
            lim = int(params.get('limit') or 200)
            rows = self.r_market[:lim]
            return 200, {'items': copy.deepcopy(rows), 'total': len(self.r_market), 'counts': {}}
        if m == 'GET' and path == '/api/bridge/chat-insights':
            return 200, copy.deepcopy(self.chat)
        mm = re.match(r'^/api/bridge/chat-insights/([^/]+)$', path)
        if m == 'GET' and mm and mm.group(1) != 'classify':
            qid = mm.group(1)
            row = next((r for r in self.chat['recent_questions'] if r['id'] == qid), None)
            if row is None:
                return 404, {'detail': 'السؤال غير موجود'}
            signed = not row['anonymous']
            return 200, {'identity': {'full_name': ASKER_NAME, 'email': ASKER_EMAIL} if signed else None, 'category': row['category'], 'intent': row['intent'],
                         'agent': 'prof', 'created_at': row['created_at'], 'truncated': not signed,
                         'messages': [{'role': 'user', 'content': row['question']}, {'role': 'assistant', 'content': 'رد محفوظ على السؤال: راجع العقد أولًا.'}]}
        if m == 'POST' and path == '/api/bridge/chat-insights/classify':
            self.classify_posts.append(copy.deepcopy(params))
            self.chat['unclassified'] = 0
            return 200, {'classified': 12, 'remaining': 3}
        if m == 'GET' and path == '/api/bridge/reports/funnel':
            self.funnel_calls.append(dict(params))
            if not self.funnel_on:
                return 404, {'detail': 'Not Found'}
            return 200, self.funnel_payload(params)
        if m == 'GET' and path == '/api/bridge/reports/weekly/delivery':
            if not self.delivery_on:
                return 404, {'detail': 'Not Found'}
            return 200, {'enabled': True, 'channel': 'telegram', 'last_sent_week': '2026-10-18'}
        if m == 'POST' and path == '/api/bridge/reports/weekly/deliver':
            if not self.delivery_on:
                return 404, {'detail': 'Not Found'}
            if (body or {}).get('confirmed') is not True:
                return 400, {'detail': 'لازم تأكيد صريح'}
            self.delivered.append(copy.deepcopy(body))
            return 200, {'sent': True, 'already': False}
        return None


# ---------------------------------------------------------------- بيانات الداشبورد نفسه (SQLite)
def seed_dash(appmod, today=None):
    """يزرع ~٩٠ يومًا من صفوف الإيراد (دخل الملفات ينمو · الكتب واقفة) + صف دولار + صف ريال يحتاج صرفًا + إيداع إعلانات + اشتراك + ٢٠ مقالًا منشورًا.
    `today` = تاريخ القاهرة الحالي. يعيد عدد صفوف الإيراد."""
    today = today or datetime.date.today()
    m = appmod
    rows = []

    def rev(days_ago, source, egp=0.0, usd=0.0, foreign=None, desc=''):
        d = today - datetime.timedelta(days=days_ago)
        r = m.Revenue(date=d, source=source, description=desc or ('إيراد ' + source), amount_egp=egp if not foreign else None, amount_usd=usd,
                      payment_id='rp-%s-%s-%s' % (source, days_ago, len(rows)), payment_method='platform')
        if foreign:
            r.amount_original, r.currency, r.needs_fx = foreign[1], foreign[0], True
        rows.append(r)

    for d in range(1, 31, 2):            # الملفات: ١٥ عملية في آخر ٣٠ يومًا
        rev(d, 'consultation', egp=900.0)
    for d in range(31, 61, 3):           # ١٠ عمليات قبلها
        rev(d, 'consultation', egp=900.0)
    for d in range(2, 31, 3):            # الدورات: ١٠ ثم ١٠ (ثابتة)
        rev(d, 'course', egp=450.0)
    for d in range(32, 61, 3):
        rev(d, 'course', egp=450.0)
    for d in (35, 45, 55):               # الكتب: ٣ قبلها، وصفر في آخر ٣٠ يومًا (واقفة)
        rev(d, 'book', egp=150.0)
    for d in range(61, 90, 4):
        rev(d, 'consultation', egp=700.0)
    rev(0, 'consultation', egp=500.0)    # اليوم الجاري
    rev(0, 'course', egp=300.0)
    rev(5, 'course', usd=30.0)           # دولار
    rev(8, 'course', foreign=('SAR', 300.0))   # ريال يحتاج صرفًا
    rev(3, 'ads_deposit', egp=2000.0)    # لا يدخل «دفعوا» ولا أي سطر
    rev(4, 'subscription', egp=199.0)
    with m.app.app_context():
        for r in rows:
            m.db.session.add(r)
        for i in range(20):
            pub = datetime.datetime.combine(today - datetime.timedelta(days=1 + i * 3), datetime.time(10, 0))
            m.db.session.add(m.Article(title='مقال تقرير %d' % i, status='published', published_at=pub, slug='rep-art-%d' % i))
        m.db.session.commit()
    return len(rows)


def wipe_dash(appmod):
    m = appmod
    with m.app.app_context():
        m.Revenue.query.filter(m.Revenue.payment_id.like('rp-%')).delete(synchronize_session=False)
        m.Article.query.filter(m.Article.slug.like('rep-art-%')).delete(synchronize_session=False)
        m.db.session.commit()
