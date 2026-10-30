# -*- coding: utf-8 -*-
"""بيانات تجريبية لشاشات غير الأدمن (القسم «roles»): مستخدمون وصفوف في SQLite الداشبورد + منصة مزيّفة في الذاكرة.

⛔ صفر شبكة: كل شيء في الذاكرة. `seed(m)` يُستدعى داخل `app_context()` بوحدة `app` ويرجع {اسم: User}.
الأسماء المربوطة (`linked_to_name`): المدرّبة «م. سارة» (لها دورات ومستحقات وفرصة محفظة) · المدرّبة «م. هدى» (محفظة بلا رصيد) ·
المستثمر «المستثمر أحمد» (محفظة بها رصيد وسحب قيد المراجعة واستثمارات جارية ومنتهية).
"""
import copy
import datetime
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import v2_fixtures as v2fx  # noqa: E402

TODAY = datetime.date.today()


def _d(days_ago):
    return TODAY - datetime.timedelta(days=days_ago)


def _iso(h):
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=h)).strftime('%Y-%m-%dT%H:%M:%SZ')


PCOURSES = [
    {"id": "pc-1", "slug": "marketing-basics", "title": "أساسيات التسويق القانوني", "type": "recorded_paid", "is_active": True, "approval_status": "approved",
     "price_amount": 1200, "price_currency": "EGP", "total_enrolled": 42, "source": "story-seed", "archived_at": "", "instructor_name": "م. سارة",
     "lesson_count": 0, "story": {"units": 5, "lessons": 24, "minutes": 310}},
    {"id": "pc-2", "slug": "contracts", "title": "صياغة العقود التجارية", "type": "recorded_paid", "is_active": False, "approval_status": "pending",
     "price_amount": 40, "price_currency": "USD", "total_enrolled": 0, "source": "native", "archived_at": "", "instructor_name": "م. سارة",
     "lesson_count": 9, "story": None},
    {"id": "pc-3", "slug": "free-intro", "title": "مدخل إلى التسويق للمحامين", "type": "recorded_free", "is_active": True, "approval_status": "approved",
     "price_amount": 0, "price_currency": "EGP", "total_enrolled": 310, "source": "dashboard", "archived_at": "", "instructor_name": "",
     "lesson_count": 6, "story": None},
    {"id": "pc-4", "slug": "old-live", "title": "ورشة المرافعة المباشرة", "type": "live_upcoming", "is_active": False, "approval_status": "approved",
     "price_amount": 900, "price_currency": "EGP", "total_enrolled": 12, "source": "titch", "archived_at": "2026-08-01T00:00:00Z", "instructor_name": "م. ليلى",
     "lesson_count": 4, "story": None},
    {"id": "pc-5", "slug": "draft-1", "title": "مسودة: التفاوض على العقود", "type": "recorded_paid", "is_active": False, "approval_status": "approved",
     "price_amount": 0, "price_currency": "EGP", "total_enrolled": 0, "source": "native", "archived_at": "", "instructor_name": "م. ليلى",
     "lesson_count": 0, "story": None},
    {"id": "pc-6", "slug": "rej-1", "title": "دورة مرفوضة", "type": "recorded_paid", "is_active": False, "approval_status": "rejected",
     "price_amount": 300, "price_currency": "EGP", "total_enrolled": 0, "source": "native", "archived_at": "", "instructor_name": "م. ليلى",
     "lesson_count": 2, "story": None},
]

TOPICS = [
    {"id": "tp-1", "title": "هل يجوز إنهاء العقد قبل مدته؟", "summary": "سؤال من عضو عن الإنهاء المبكر لعقد إيجار.\nيطلب معرفة الشروط والإجراءات.",
     "category": "عقود", "status": "pending_review", "source": "human", "comments": 0, "reactions": 3, "created_at": _iso(-30)},
    {"id": "tp-2", "title": "كيف تسعّر خدمتك القانونية؟", "summary": "موضوع عن التسعير.", "category": "تسويق", "status": "published", "source": "expert",
     "comments": 4, "reactions": 21, "created_at": _iso(-24 * 9)},
    {"id": "tp-3", "title": "أخبار: تعديل قانون الإيجار", "summary": "", "category": "أخبار", "status": "open", "source": "news", "comments": 0, "reactions": 0,
     "created_at": _iso(-24 * 3)},
    {"id": "tp-4", "title": "فكرة: دليل العقد الأول", "summary": "فكرة مسودة.", "category": "عقود", "status": "draft", "source": "idea", "created_at": _iso(-24 * 20)},
    {"id": "tp-5", "title": "موضوع قيد العمل", "summary": "", "category": "ضرائب", "status": "merged", "source": "idea", "comments": 1, "reactions": 2,
     "created_at": _iso(-24 * 4)},
    {"id": "tp-6", "title": "موضوع مرفوض", "summary": "", "category": "عام", "status": "rejected", "source": "human", "comments": 0, "reactions": 0,
     "created_at": _iso(-24 * 30)},
]

TUTORIALS = [
    {"id": "tu-1", "title": "كيف تسجّل في المنصة", "section": "البداية", "order": 1, "published": True, "body": "افتح الصفحة الرئيسية.\nاختر «سجّل الآن».\nأكمل بياناتك.",
     "video_url": "https://example.test/video/1"},
    {"id": "tu-2", "title": "كيف تطلب استشارة", "section": "البداية", "order": 2, "published": True, "body": "اكتب سؤالك ثم اختر الخبير.", "video_url": ""},
    {"id": "tu-3", "title": "كيف تتابع دورتك", "section": "", "order": 3, "published": False, "body": "قيد الكتابة.", "video_url": ""},
]


class RolesPlatform(v2fx.V2Platform):
    """`V2Platform` + دليل الاستخدام + دورات وموضوعات للموظف. `capped` ⇒ قائمة الأعضاء تعيد ٣ صفوف و`count` أكبر."""

    def __init__(self, capped=False, **kw):
        super(RolesPlatform, self).__init__(**kw)
        self.capped = capped
        self.pcourses = copy.deepcopy(PCOURSES)
        self.topic_rows = copy.deepcopy(TOPICS)
        self.tutorials = copy.deepcopy(TUTORIALS)

    def _extra(self, method, path, params, body):
        m = method.upper()
        if m == "GET":
            if path == "/api/tutorials":
                return 200, copy.deepcopy(self.tutorials)
            if path == "/api/bridge/courses":
                return 200, {"courses": copy.deepcopy(self.pcourses), "count": len(self.pcourses)}
            if path == "/api/bridge/topics":
                return 200, {"topics": copy.deepcopy(self.topic_rows)}
            if path == "/api/bridge/users" and self.capped:
                q = str(params.get("search") or "").strip().lower()
                rows = [u for u in self.people if not q or q in u["email"].lower() or q in u["full_name"].lower()][:3]
                return 200, {"users": copy.deepcopy(rows), "count": 900 if not q else len(rows)}
        return super(RolesPlatform, self)._extra(method, path, params, body)


def seed(m):
    """يزرع المستخدمين والصفوف مرة واحدة (آمن للتكرار) ويرجع {اسم: User}."""
    from werkzeug.security import generate_password_hash
    out = {}

    def mk(key, email, role, name, linked='', dash=None):
        u = m.User.query.filter_by(email=email).first()
        if u is None:
            u = m.User(email=email, password_hash=generate_password_hash('x', method='pbkdf2:sha256'), name=name, role=role,
                       dashboard_role=dash or role, linked_to_name=linked, preferred_currency='AUTO', is_active=True)
            m.db.session.add(u)
        else:
            u.role = role
            u.dashboard_role = dash or role
            u.linked_to_name = linked
            u.name = name
            u.is_active = True
        m.db.session.commit()
        out[key] = u
        return u

    mk('admin', 'admin@local.test', 'admin', 'المؤسس')
    mk('employee', 'staff@local.test', 'employee', 'موظف المتابعة')
    mk('trainer', 'trainer@roles.test', 'trainer', 'سارة المدرّبة', 'م. سارة')
    mk('trainer_unlinked', 'trainer-unl@roles.test', 'trainer', 'مدرّب بلا ربط', '')
    mk('trainer_wallet0', 'trainer0@roles.test', 'trainer', 'هدى المدرّبة', 'م. هدى')
    mk('investor', 'investor@roles.test', 'investor', 'أحمد المستثمر', 'المستثمر أحمد')
    mk('investor_unlinked', 'investor-unl@roles.test', 'investor', 'مستثمر بلا ربط', '')
    mk('viewer', 'viewer@roles.test', 'viewer', 'زائر جديد', '')
    mk('pending', 'pending@roles.test', 'pending', 'حساب معلّق', '')
    mk('split', 'split@roles.test', 'trainer', 'هوية منقسمة', '', dash='admin')

    if m.Course.query.filter_by(title='أساسيات التسويق القانوني').first():
        return out
    rate = m.get_rate()
    C = m.Course
    c1 = C(title='أساسيات التسويق القانوني', trainer_name='م. سارة', status='active', price_egp=1500, students_count=42, start_date=_d(40))
    c2 = C(title='صياغة العقود التجارية', trainer_name='م. سارة', status='draft', price_usd=40, students_count=0)
    c3 = C(title='مهارات المرافعة', trainer_name='م. سارة', status='completed', price_egp=0, price_usd=0, students_count=18)
    c4 = C(title='برنامج الدبلومة المهنية', trainer_name='م. ليلى', status='active', price_egp=6000, students_count=25, open_for_investment=True)
    c5 = C(title='ورشة التفاوض', trainer_name='م. ليلى', status='active', price_egp=2000, students_count=9, open_for_investment=True)
    c6 = C(title='دورة مدرّبة أخرى', trainer_name='م. ليلى', status='active', price_egp=500, students_count=3)
    m.db.session.add_all([c1, c2, c3, c4, c5, c6])
    m.db.session.flush()
    m.db.session.add(m.RevenueSplit(course_id=c1.id, trainer_percent=40, platform_percent=35, investor_percent=25, affiliate_percent=0))
    m.db.session.add(m.RevenueSplit(course_id=c2.id, trainer_percent=0, platform_percent=100, investor_percent=0, affiliate_percent=0))
    # مستحقات المدرّبة: الحالات الحقيقية الثلاث فقط (accrued · paid · waived)
    P = m.Payout
    for days, name, rel, amt, status in ((5, 'م. سارة', 'أساسيات التسويق القانوني', 1200, 'accrued'), (12, 'م. سارة', 'صياغة العقود التجارية', 450, 'accrued'),
                                        (25, 'م. سارة', 'أساسيات التسويق القانوني', 800, 'paid'), (10, 'م. سارة', 'مهارات المرافعة', 300, 'waived'),
                                        (40, 'م. سارة', 'أساسيات التسويق القانوني', 700, 'accrued'), (3, 'م. ليلى', 'برنامج الدبلومة المهنية', 5000, 'accrued')):
        m.db.session.add(P(date=_d(days), name=name, role='trainer', related_to=rel, amount_egp=amt, percent=0, status=status))
    # فرص الاستثمار
    O = m.InvestmentOpportunity
    o1 = O(course_id=c4.id, target_amount=5000, min_investment=200, expected_roi=35, expected_start=_d(-10), expected_end=_d(-100), status='open')
    o2 = O(course_id=c5.id, target_amount=12000, min_investment=500, expected_roi=48, status='hot')
    o3 = O(course_id=c6.id, target_amount=0, min_investment=0, expected_roi=0, status='invite_only')
    m.db.session.add_all([o1, o2, o3])
    m.db.session.flush()
    inv = m.Investment
    inv_user = out['investor']
    trn_user = out['trainer']
    # المستثمر أحمد: جارٍ ١ + منتهي ٢ ⇒ العوائد ٥٤٠ دولارًا، وسحب قيد المراجعة ٤٠
    m.db.session.add(inv(opportunity_id=o1.id, course_id=c4.id, investor_name='المستثمر أحمد', investor_user_id=inv_user.id, amount_usd=200,
                         amount_egp=200 * rate, profit_percent=20, status='active', actual_return=0, created_at=datetime.datetime.utcnow() - datetime.timedelta(days=20)))
    m.db.session.add(inv(opportunity_id=o2.id, course_id=c5.id, investor_name='المستثمر أحمد', investor_user_id=inv_user.id, amount_usd=100,
                         amount_egp=100 * rate, profit_percent=20, status='completed', actual_return=130, created_at=datetime.datetime.utcnow() - datetime.timedelta(days=90)))
    m.db.session.add(inv(opportunity_id=None, course_id=c4.id, investor_name='المستثمر أحمد', investor_user_id=inv_user.id, amount_usd=300,
                         amount_egp=300 * rate, profit_percent=20, status='completed', actual_return=410, created_at=datetime.datetime.utcnow() - datetime.timedelta(days=150)))
    # المدرّبة سارة تستثمر أيضًا (محفظة)
    m.db.session.add(inv(opportunity_id=o2.id, course_id=c5.id, investor_name='م. سارة', investor_user_id=trn_user.id, amount_usd=150,
                         amount_egp=150 * rate, profit_percent=20, status='completed', actual_return=210, created_at=datetime.datetime.utcnow() - datetime.timedelta(days=60)))
    m.db.session.add(inv(opportunity_id=o1.id, course_id=c4.id, investor_name='م. سارة', investor_user_id=trn_user.id, amount_usd=100,
                         amount_egp=100 * rate, profit_percent=20, status='active', actual_return=0, created_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)))
    m.db.session.commit()
    w = m.get_or_create_wallet('المستثمر أحمد', inv_user.id)
    m.sync_wallet(w)
    m.db.session.add(m.WithdrawalRequest(wallet_id=w.id, amount=40, status='pending'))
    m.get_or_create_wallet('م. سارة', trn_user.id)
    m.get_or_create_wallet('م. هدى', out['trainer_wallet0'].id)
    m.db.session.add(m.Message(name='سلمى منصور', email='salma@example.test', topic='استفسار عن دورة', body='أريد معرفة موعد الدورة القادمة.', status='new'))
    m.db.session.commit()
    for wl in m.InvestorWallet.query.all():
        m.sync_wallet(wl)
    m.db.session.commit()
    return out


def tokens(m, users):
    import jwt
    return {k: jwt.encode({'user_id': u.id, 'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1)}, m.app.config['SECRET_KEY'], algorithm='HS256')
            for k, u in users.items()}
