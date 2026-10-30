# -*- coding: utf-8 -*-
"""بيانات وهمية لشاشة «التسويق»: `MKPlatform` = منصة الفلوس والكتب (D3) + جسر «من أين جاء كل شخص» (يشتغل أو يرد ٤٠٤)،
و`seed_mk` يزرع حملات ومقالات في قاعدة الداشبورد المؤقتة.

⛔ صفر شبكة: كله في الذاكرة. الأسماء والأرقام مخترعة، وشكل الجسر بالحرف من SPEC-marketing.md §9 P1.
`attribution=False` (الافتراضي) ⇒ المنصة ما عندهاش الجسر بعد: ٤٠٤ كما في الواقع.
"""
import copy
import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import d3_fixtures as d3fx        # noqa: E402
from sqlalchemy import text       # noqa: E402

iso = d3fx.iso


def attribution_summary(campaign_ids=None):
    """رد الجسر: قنوات (مدفوعة وغير مدفوعة) · بلا مصدر · حملات بمفتاح c{id}."""
    cid = campaign_ids or {}
    return {
        'ok': True, 'month': '', 'captured_since': iso(-24 * 12),
        'channels': [
            {'key': 'meta', 'paid': True, 'signups': 12, 'paid_people': 4, 'totals': [{'currency': 'EGP', 'amount': 3400.0}]},
            {'key': 'meta', 'paid': False, 'signups': 20, 'paid_people': 5, 'totals': [{'currency': 'EGP', 'amount': 1250.0}]},
            {'key': 'google', 'paid': False, 'signups': 30, 'paid_people': 9, 'totals': [{'currency': 'EGP', 'amount': 2300.0}, {'currency': 'SAR', 'amount': 150.0}]},
            {'key': 'invite', 'paid': False, 'signups': 8, 'paid_people': 3, 'totals': [{'currency': 'EGP', 'amount': 900.0}]},
            {'key': 'direct', 'paid': False, 'signups': 14, 'paid_people': 4, 'totals': [{'currency': 'EGP', 'amount': 700.0}]},
        ],
        'untracked': {'signups': 40, 'paid_people': 11, 'totals': [{'currency': 'EGP', 'amount': 5200.0}]},
        'campaigns': [
            {'campaign': 'c%s' % cid.get('winning', 1), 'source': 'facebook', 'signups': 9, 'paid_people': 3, 'totals': [{'currency': 'EGP', 'amount': 2100.0}]},
            {'campaign': 'c%s' % cid.get('losing', 2), 'source': 'google', 'signups': 4, 'paid_people': 1, 'totals': [{'currency': 'EGP', 'amount': 450.0}]},
        ],
    }


class MKPlatform(d3fx.D3Platform):
    def __init__(self, attribution=False, **kw):
        super(MKPlatform, self).__init__(**kw)
        self.attribution = attribution
        self.attr_calls = []
        self.campaign_ids = {}

    def _route(self, method, path, params, body):
        if path == '/api/bridge/attribution/summary':
            forced = self.forced.get((method.upper(), path))
            if forced is not None:
                return forced
            self.attr_calls.append(dict(params or {}))
            if not self.attribution:
                return 404, {'detail': 'Not Found'}
            if path in self.down:
                return 502, {'detail': 'تعذر الاتصال'}
            out = attribution_summary(self.campaign_ids)
            out['month'] = (params or {}).get('month') or datetime.date.today().strftime('%Y-%m')
            return 200, out
        return super(MKPlatform, self)._route(method, path, params, body)


def seed_mk(h, with_owner=True, campaigns=True):
    """يمسح الحملات والمقالات وجدولَي التسويق ثم يزرع: ست حملات (الخامسة بالدولار من «الشاشة القديمة») وأربعة مقالات منشورة (اثنان
    في آخر ٧ أيام) وثلاث مسودات. `h` = Harness (فيه التطبيق والعميل والتوكن). يعيد {اسم: رقم الحملة}."""
    m = h.app
    today = datetime.date.today()

    def day(n):
        return today + datetime.timedelta(days=n)

    spec = [
        ('winning', dict(name='حملة الدورات على فيسبوك', platform='facebook_instagram', status='active', start_date=day(-40), budget=5000.0, spent=2000.0, currency='EGP',
                         clicks=840, leads=52, conversions=9, revenue_attributed=10400.0, target_audience='محامون شباب')),
        ('losing', dict(name='حملة جوجل للاستشارات', platform='google_ads', status='active', start_date=day(-20), budget=3000.0, spent=1500.0, currency='EGP',
                        clicks=320, leads=18, conversions=3, revenue_attributed=1200.0, target_audience='أصحاب الشركات الصغيرة')),
        ('noresults', dict(name='حملة لينكدإن للمحامين', platform='linkedin', status='active', start_date=day(-15), budget=2000.0, spent=900.0, currency='EGP',
                           clicks=0, leads=0, conversions=0, revenue_attributed=0.0, target_audience='')),
        ('paused', dict(name='حملة تيك توك للطلاب', platform='tiktok', status='paused', start_date=day(-50), end_date=day(-30), budget=1000.0, spent=300.0, currency='SAR',
                        clicks=120, leads=8, conversions=2, revenue_attributed=450.0, target_audience='طلاب الحقوق')),
        ('legacy', dict(name='حملة الكتب القديمة', platform='facebook', status='completed', start_date=day(-90), end_date=day(-60), budget=300.0, spent=200.0, currency='USD',
                        clicks=90, leads=7, conversions=2, revenue_attributed=380.0, target_audience='')),
        ('young', dict(name='حملة إنستجرام الجديدة', platform='instagram', status='active', start_date=day(-1), budget=2000.0, spent=100.0, currency='EGP',
                       clicks=40, leads=2, conversions=0, revenue_attributed=0.0, target_audience='')),
    ]
    ids = {}
    with m.app.app_context():
        for t in ('v2_campaign_owner', 'v2_marketing_meta'):
            m.db.session.execute(text('DROP TABLE IF EXISTS %s' % t))
        m.db.session.commit()
        m.Campaign.query.delete()
        m.Article.query.delete()
        m.db.session.commit()
        if campaigns:
            for key, kw in spec:
                c = m.Campaign(**kw)
                m.db.session.add(c)
                m.db.session.flush()
                ids[key] = c.id
        now = datetime.datetime.utcnow()
        arts = [('مقال حديث ١: كيف تختار محاميًا لعقد الإيجار', 'published', now - datetime.timedelta(days=1)),
                ('مقال حديث ٢: حقوق المستأجر عند الإنهاء', 'published', now - datetime.timedelta(days=4)),
                ('مقال قديم ١: دليل تأسيس شركة', 'published', now - datetime.timedelta(days=12)),
                ('مقال قديم ٢: عقود العمل الحر', 'published', now - datetime.timedelta(days=30)),
                ('مسودة ١', 'draft', None), ('مسودة ٢', 'draft', None), ('مسودة ٣', 'draft', None)]
        for title, st, at in arts:
            m.db.session.add(m.Article(title=title, status=st, published_at=at))
        m.db.session.commit()
    if with_owner and campaigns:
        heads = {'Authorization': 'Bearer ' + h.tokens['admin']}
        h.client.get('/api/v2/marketing/owners', headers=heads)          # أول تشغيل: يكتب حدّ حملات الشاشة القديمة
        h.client.put('/api/v2/marketing/campaigns/%d/owner' % ids['losing'], headers=heads,
                     json={'owner_kind': 'course', 'owner_id': 'contract-basics', 'owner_title': 'أساسيات صياغة العقود'})
    return ids
