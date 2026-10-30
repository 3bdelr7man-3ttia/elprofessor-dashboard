# -*- coding: utf-8 -*-
"""منصّة وهميّة لقسم «الدورات والمدرّبون» (الجولة الأخيرة): فوق `D3Platform` (فيها جدول النسب) بتضيف جسور الدورات بحالتها —
قائمة الدورات · التفاصيل · المواعيد · الخبراء · طلبات المدرّبين · عروض الأسعار · طلبات البرامج وإحصاؤها · تحليل الشات · الحجوزات ·
وكتابات الاعتماد والرفض والظهور والأرشفة والموعد والعروض وقرار الدورة الحيّة بنفس رسائل المنصة العربية.

`with_abc=True` ⇒ الإضافات أ/ب/ج التي طلبتها المواصفة (حقول الدورة الجديدة · فحص النشر · المبيعات والإكمال) موجودة؛ `False` ⇒ غائبة
(الفحص والمبيعات ٤٠٤ كما لو لم تُنشر بعد). ⛔ صفر شبكة: كله في الذاكرة. الأسماء والأرقام مخترعة، والأشكال بالحرف من جسور المنصة.
"""
import copy
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ef_fixtures as fx          # noqa: E402
import d3_fixtures as d3fx        # noqa: E402

iso = fx.iso
NOT_FOUND = {"detail": "Not Found"}


def _course(cid, slug, title, ctype="recorded_paid", active=False, approval="approved", price=450.0, lessons=0, enrolled=0, instructor="", email="",
            created_h=-24 * 40, updated_h=None, archived=False, bid=False, story=None, source="native", note="", submitted_h=None, thumb="", owned=False,
            signed=True):
    c = {"id": cid, "slug": slug, "title": title, "type": ctype, "is_active": active, "bid_enabled": bid, "segment_pricing_mode": "discount_only",
         "price_amount": price, "price_currency": "EGP" if price else "", "total_enrolled": enrolled, "approval_status": approval, "source": source,
         "created_at": iso(created_h), "archived_at": iso(-24) if archived else "", "short_description": "", "instructor_name": instructor,
         "lesson_count": lessons, "story": story}
    c["_abc"] = {"instructor_email": email, "platform_owned": owned, "thumbnail_url": thumb, "updated_at": iso(updated_h if updated_h is not None else created_h),
                 "submitted_at": iso(submitted_h) if submitted_h is not None else "", "review_note": note,
                 "agreement_signed": None if owned else signed, "payout_model": "share" if email else None, "trainer_share_pct": 35 if email else None}
    c["_email"] = email
    return c


def base_courses():
    st = {"units": 5, "lessons": 39, "minutes": 420}
    return [
        # —— منشورة (١١)
        _course("pc-01", "contract-drafting-basics", "أساسيات صياغة العقود", active=True, price=450, lessons=12, enrolled=312, instructor="د. هالة سمير", email="hala@example.test", bid=True, thumb="v2/img/books.jpg"),
        _course("pc-02", "legal-marketing-basics", "أساسيات التسويق القانوني", ctype="recorded_paid", active=True, price=600, lessons=0, enrolled=148, instructor="البروفيسور", source="story-seed", story=st, owned=True),
        _course("pc-03", "lease-review", "مراجعة عقود الإيجار", active=True, price=300, lessons=9, enrolled=88, instructor="أ. نادية فؤاد", email="nadia@example.test", thumb="v2/img/content.jpg"),
        _course("pc-04", "labor-law-managers", "قانون العمل للمديرين", active=True, price=520, lessons=14, enrolled=64, instructor="أ. فيصل العتيبي", email="faisal@experts.test", bid=True, thumb="v2/img/reports.jpg"),
        _course("pc-05", "commercial-arbitration", "التحكيم التجاري: مدخل عملي", active=True, price=700, lessons=11, enrolled=41, instructor="د. هالة سمير", email="hala@example.test"),
        _course("pc-06", "ip-creators", "الملكية الفكرية للمبدعين", active=True, price=380, lessons=8, enrolled=37, instructor="أ. نادية فؤاد", email="nadia@example.test"),
        _course("pc-07", "startup-basics", "أساسيات الشركات الناشئة", ctype="recorded_free", active=True, price=0, lessons=6, enrolled=220, instructor="البروفيسور", owned=True),
        _course("pc-08", "warnings-drafting", "صياغة الإنذارات", active=True, price=250, lessons=5, enrolled=29, instructor="أ. فيصل العتيبي", email="faisal@experts.test"),
        _course("pc-09", "inheritance-live", "ورشة الميراث", ctype="live_upcoming", active=True, price=900, lessons=0, enrolled=14, instructor="د. هالة سمير", email="hala@example.test"),
        _course("pc-10", "data-protection", "مدخل إلى حماية البيانات", active=True, price=410, lessons=7, enrolled=18, instructor="أ. نادية فؤاد", email="nadia@example.test"),
        _course("pc-11", "corporate-compliance", "الامتثال للشركات", active=True, price=350, lessons=0, enrolled=0, instructor="أ. فيصل العتيبي", email="faisal@experts.test"),
        # —— تحت البناء (٣): مسودة · مُعادة بملاحظات · مسودة أخرى
        _course("pc-12", "construction-contracts", "عقود المقاولات", active=False, approval=None, price=0, lessons=3, enrolled=0, instructor="د. هالة سمير", email="hala@example.test", updated_h=-5),
        _course("pc-13", "family-law-engaged", "قانون الأسرة للمقبلين على الزواج", active=False, approval="rejected", price=280, lessons=4, enrolled=0, instructor="أ. فيصل العتيبي",
                email="faisal@experts.test", updated_h=-30, note="الفيديو التعريفي غير واضح، وأعد كتابة وصف الدورة قبل إعادتها."),
        _course("pc-14", "consumer-rights", "حقوق المستهلك", active=False, approval=None, price=0, lessons=0, enrolled=0, instructor="أ. نادية فؤاد", email="nadia@example.test", updated_h=-70),
        # —— في المراجعة (٢)
        _course("pc-15", "contract-management", "إدارة العقود للشركات", active=False, approval="pending", price=480, lessons=14, enrolled=0, instructor="أ. نادية فؤاد", email="nadia@example.test",
                created_h=-24 * 90, submitted_h=-24 * 3, thumb="v2/img/marketing.jpg"),
        _course("pc-16", "arbitration-lawyer-guide", "دليل المحامي في التحكيم", active=False, approval="pending", price=None, lessons=6, enrolled=0, instructor="أ. فيصل العتيبي",
                email="faisal@experts.test", created_h=-24 * 12, submitted_h=-30),
    ]


def public_course(c, abc):
    out = {k: v for k, v in c.items() if not k.startswith("_")}
    if abc:
        a = c["_abc"]
        out.update({"instructor_email": a["instructor_email"], "platform_owned": a["platform_owned"], "thumbnail_url": a["thumbnail_url"], "updated_at": a["updated_at"],
                    "submitted_at": a["submitted_at"], "review_note": a["review_note"], "agreement_signed": a["agreement_signed"],
                    "payout_model": a["payout_model"], "trainer_share_pct": a["trainer_share_pct"]})
    return out


def base_schedules():
    return [
        {"id": "pc-live1", "slug": "commercial-contracts-live", "title": "ورشة العقود التجارية", "instructor_name": "د. هالة سمير", "is_active": True,
         "start_date": iso(24 * 9), "end_date": iso(24 * 9 + 3), "timezone": "Africa/Cairo", "zoom_link": "", "registration_deadline": iso(-10), "max_seats": 30,
         "booked_count": 0, "quorum": 8, "payment_window_hours": 48, "reserved_count": 4, "live_status": "reserving", "payment_deadline": "", "quorum_met": False, "confirmed": False},
        {"id": "pc-09", "slug": "inheritance-live", "title": "ورشة الميراث", "instructor_name": "د. هالة سمير", "is_active": True,
         "start_date": iso(24 * 5), "end_date": iso(24 * 5 + 3), "timezone": "Africa/Cairo", "zoom_link": "https://meet.test/inh", "registration_deadline": iso(-48), "max_seats": 20,
         "booked_count": 14, "quorum": 10, "payment_window_hours": 48, "reserved_count": 14, "live_status": "confirmed", "payment_deadline": iso(-30), "quorum_met": True, "confirmed": True},
    ]


def base_experts():
    rows = [("hala@example.test", "د. هالة سمير", ["civil"], 3), ("nadia@example.test", "أ. نادية فؤاد", ["commercial"], 4), ("faisal@experts.test", "أ. فيصل العتيبي", ["labor"], 4),
            ("rana@experts.test", "أ. رنا عادل", ["family"], 0), ("wael@experts.test", "أ. وائل حمدي", ["criminal"], 0), ("sami@experts.test", "أ. سامي نصر", ["tax"], 0)]
    return [{"email": e, "full_name": n, "expertise": x, "bio": "", "trainer_status": "approved", "rating_avg": 4.6, "rating_count": 9, "online": False,
             "last_seen_at": None, "referral_count": 2, "courses_count": cc, "students_count": 40 * cc} for e, n, x, cc in rows]


def base_apps():
    return [
        {"id": "ta-1", "status": "pending", "user_name": "أ. منار يوسف", "user_email": "manar@example.test", "headline": "محامية متخصصة في عقود الشركات",
         "expertise": ["عقود", "شركات", "ملكية فكرية"], "experience_summary": "عملت اثنتي عشرة سنة في مكاتب محاماة تجارية، وأدرّب المحامين الجدد على صياغة العقود.",
         "linkedin_url": "https://linkedin.test/manar", "portfolio_url": "https://manar.test", "cv_url": "https://cv.test/manar.pdf", "founding_lead_id": "", "created_at": iso(-52), "updated_at": iso(-52)},
        {"id": "ta-2", "status": "pending", "user_name": "أ. طارق فهمي", "user_email": "tarek@example.test", "headline": "مستشار عمل",
         "expertise": [], "experience_summary": "خبرة قصيرة", "linkedin_url": "", "portfolio_url": "", "cv_url": "", "founding_lead_id": "", "created_at": iso(-20), "updated_at": iso(-20)},
        {"id": "ta-3", "status": "pending", "user_name": "د. لبنى سعيد", "user_email": "lubna@example.test", "headline": "أستاذة قانون مدني",
         "expertise": ["مدني", "عقود"], "experience_summary": "أستاذة في كلية الحقوق وأشرف على رسائل في العقود الإلكترونية منذ ثماني سنوات.",
         "linkedin_url": "https://linkedin.test/lubna", "portfolio_url": "", "cv_url": "", "founding_lead_id": "fl-9", "created_at": iso(-5), "updated_at": iso(-5)},
    ]


def base_offers():
    return [
        {"id": "co-1", "status": "pending", "course_slug": "contract-drafting-basics", "course_title": "أساسيات صياغة العقود", "buyer_email": "sara.m@example.test", "segment": "student",
         "currency": "EGP", "base_amount": 450, "situational_amount": 360, "floor_amount": 250, "offered_amount": 300, "message": "أنا طالبة وهذا أقصى ما أستطيع دفعه.", "created_at": iso(-9)},
        {"id": "co-2", "status": "pending", "course_slug": "labor-law-managers", "course_title": "قانون العمل للمديرين", "buyer_email": "omar.k@example.test", "segment": "company",
         "currency": "EGP", "base_amount": 520, "situational_amount": 500, "floor_amount": 300, "offered_amount": 200, "message": "", "created_at": iso(-50)},
    ]


def base_programs():
    rows = [("pr-1", "التسويق القانوني المتقدم", "نور الهدى سالم", "nour@example.test", -30), ("pr-2", "التسويق القانوني المتقدم", "عمر شريف", "omar@example.test", -22),
            ("pr-3", "التسويق القانوني المتقدم", "هبة مراد", "heba@example.test", -9), ("pr-4", "عقود الفرنشايز", "ياسر نبيل", "yasser@example.test", -14),
            ("pr-5", "الصياغة التشريعية", "منى سعيد", "mona.s@example.test", -3)]
    return [{"id": i, "program_id": "prog-" + i, "title": t, "user_name": n, "user_email": e, "status": "pending", "notes": "", "created_at": iso(h), "updated_at": iso(h)} for i, t, n, e, h in rows]


def chat_analysis():
    qs = []

    def q(text, intent, cat):
        qs.append({"id": "q%d" % len(qs), "anonymous": False, "has_thread": False, "question": text, "segment": "individual", "country": "eg", "category": cat, "intent": intent,
                   "needs_expert": False, "agent": "master", "action_type": "answer"})
    q("هل في دورة تعلمني كتابة العقود؟", "دورة", "عقود")
    q("أريد دورة عملية في صياغة عقود الإيجار", "دورة", "عقود")
    q("عندكم دورة في قانون العمل للموظفين؟", "دورة", "عمل")
    q("أبحث عن دورة تدريبية مناسبة للمبتدئين", "دورة", None)
    for t in ("ما عقوبة إصدار شيك بلا رصيد؟", "كيف أرفع دعوى نفقة؟", "هل يجوز فسخ العقد من طرف واحد؟", "ما مدة التقادم في الديون التجارية؟",
              "كيف أسجل علامة تجارية؟", "ما إجراءات تأسيس شركة؟", "هل أحتاج محاميًا لتوثيق عقد بيع؟", "كيف أعترض على قرار فصل؟"):
        q(t, "استشارة", "عام")
    return {"total": 40, "recent_questions": qs}


class CoursesPlatform(d3fx.D3Platform):
    def __init__(self, with_abc=True, **kw):
        kw.setdefault("d2", True)
        super(CoursesPlatform, self).__init__(**kw)
        self.with_abc = with_abc
        self.courses = base_courses()
        self.schedules = base_schedules()
        self.experts = base_experts()
        self.trainer_apps = base_apps()
        self.course_offers = base_offers()
        self.programs = base_programs()
        self.analysis = chat_analysis()
        self.reservations = {
            "commercial-contracts-live": [
                {"id": "rs-1", "course_slug": "commercial-contracts-live", "user_name": "ليلى أحمد", "user_email": "layla@example.test", "status": "reserved", "created_at": iso(-70)},
                {"id": "rs-2", "course_slug": "commercial-contracts-live", "user_name": "طارق منصور", "user_email": "tariq@example.test", "status": "reserved", "created_at": iso(-60)},
                {"id": "rs-3", "course_slug": "commercial-contracts-live", "user_name": "رنا سمير", "user_email": "rana.s@example.test", "status": "reserved", "created_at": iso(-40)},
                {"id": "rs-4", "course_slug": "commercial-contracts-live", "user_name": "حسن علي", "user_email": "hassan@example.test", "status": "reserved", "created_at": iso(-30)}],
            "inheritance-live": [
                {"id": "rs-5", "course_slug": "inheritance-live", "user_name": "منى فاروق", "user_email": "mona.f@example.test", "status": "paid", "created_at": iso(-90)},
                {"id": "rs-6", "course_slug": "inheritance-live", "user_name": "كريم عادل", "user_email": "karim.a@example.test", "status": "paid", "created_at": iso(-80)}]}
        self.cancel_refunds = [
            {"email": "mona.f@example.test", "name": "منى فاروق", "phone": "+201001112223", "payment_id": "pay-9", "amount": 900.0, "currency": "EGP"},
            {"email": "karim.a@example.test", "name": "كريم عادل", "phone": "", "payment_id": "pay-10", "amount": 900.0, "currency": "EGP"},
            {"email": "free.user@example.test", "name": "عضو بلا دفع", "phone": "", "payment_id": "", "amount": None, "currency": "", "no_payment_found": True}]
        self.cwrites = []         # (method, path, body) — كل كتابة وصلت المنصة
        self.decided = []

    # ------------------------------------------------------------------ مساعدات
    def _find(self, key):
        for c in self.courses:
            if c["id"] == key or c["slug"] == key:
                return c
        return None

    def _sched(self, slug):
        for s in self.schedules:
            if s["slug"] == slug or s["id"] == slug:
                return s
        return None

    def queue(self):
        q = super(CoursesPlatform, self).queue()
        if self.empty:
            return q
        need = [{"slug": s["slug"], "title": s["title"], "live_status": s["live_status"], "reserved_count": s["reserved_count"], "quorum": s["quorum"]}
                for s in self.schedules if s["live_status"] in ("reserving", "payment_window", "needs_decision") and s["reserved_count"] < s["quorum"]]
        q["live_needs_decision"] = need
        q["courses_pending"] = {"count": sum(1 for c in self.courses if c["approval_status"] == "pending"), "titles": []}
        return q

    def _checklist(self, c):
        a = c["_abc"]
        live = c["type"] == "live_upcoming"
        items = [("content", "فيها محتوى (دروس مسجّلة أو موعد بدء للدورة الحيّة)", live or c["lesson_count"] > 0 or bool(c.get("story"))),
                 ("outcomes", "نواتج التعلّم مذكورة", True), ("intro_video", "فيديو تعريفي مرفوع", c["id"] != "pc-16"),
                 ("level", "مستوى الدورة محدّد", True), ("pricing", "التسعير سليم", c["type"] == "recorded_free" or bool(c["price_amount"]))]
        if live:
            items.append(("zoom", "رابط اللقاء للدورة الحيّة", False))
        if not a["platform_owned"]:
            items.append(("agreement", "صاحب الدورة وقّع الاتفاقية", bool(a["agreement_signed"])))
        rows = [{"key": k, "item": t, "ok": ok} for k, t, ok in items]
        return {"course_id": c["id"], "slug": c["slug"], "checklist": rows, "all_ok": all(r["ok"] for r in rows), "sale_block_reason": ""}

    def _stats(self):
        out = []
        for c in self.courses:
            if not c["is_active"]:
                continue
            n = c["total_enrolled"]
            paid = int(n * 0.45)
            amount = round(paid * (c["price_amount"] or 0), 2)
            entry = {"course_id": c["id"], "slug": c["slug"], "enrolled": n, "paid_count": paid, "sales": [{"currency": "EGP", "amount": amount}] if amount else [],
                     "completed": int(n * 0.4), "certificates": int(n * 0.38), "completion_pct": int(round(40)) if n else None,
                     "stall_lesson": {"index": 4, "title": "بنود الجزاءات", "learners": 51} if n > 100 else None}
            out.append(entry)
        return {"generated_at": iso(0), "courses": out}

    # ------------------------------------------------------------------ التوجيه
    def _route(self, method, path, params, body):
        forced = self.forced.get((method.upper(), path))
        if forced is not None:
            return forced
        if path in self.down or path.rsplit("/", 1)[0] in self.down:
            return 502, {"detail": "تعذر الاتصال"}
        out = self._co(method.upper(), path, params, body or {})
        if out is not None:
            return out
        return super(CoursesPlatform, self)._route(method, path, params, body)

    def _w(self, method, path, body):
        self.cwrites.append((method, path, copy.deepcopy(body)))

    def _co(self, method, path, params, body):
        if method == "GET":
            if path == "/api/bridge/courses":
                return 200, {"courses": [public_course(c, self.with_abc) for c in self.courses], "count": len(self.courses)}
            if path == "/api/bridge/courses/stats":
                return (200, self._stats()) if self.with_abc else (404, NOT_FOUND)
            m = re.match(r"^/api/bridge/courses/([^/]+)/checklist$", path)
            if m:
                c = self._find(m.group(1))
                if not self.with_abc:
                    return 404, NOT_FOUND
                return (200, self._checklist(c)) if c else (404, {"detail": "الدورة غير موجودة"})
            m = re.match(r"^/api/bridge/courses/([^/]+)/detail$", path)
            if m:
                c = self._find(m.group(1))
                if not c:
                    return 404, {"detail": "الدورة غير موجودة"}
                spec = [("الأولى: المدخل", "الأساسيات", 1), ("الثانية: الأركان", "الأساسيات", 1), ("الثالثة: الصياغة", "التطبيق", 2)]
                vids = [{"id": "v%d" % i, "title": "المحاضرة " + t, "is_preview": i == 0, "section_title": s, "section_order": so, "order": i, "duration_seconds": 600}
                        for i, (t, s, so) in enumerate(spec)] if c["lesson_count"] > 0 else []
                secs = []
                for v in vids:
                    for s in secs:
                        if s["title"] == v["section_title"]:
                            s["lessons"].append(v)
                            break
                    else:
                        secs.append({"title": v["section_title"], "order": v["section_order"], "lessons": [v]})
                return 200, {"id": c["id"], "slug": c["slug"], "title": c["title"], "type": c["type"], "is_active": c["is_active"], "videos": vids, "sections": secs, "lessons": []}
            if path == "/api/bridge/schedules":
                return 200, {"schedules": copy.deepcopy(self.schedules), "count": len(self.schedules)}
            if path == "/api/bridge/experts":
                rows = copy.deepcopy(self.experts)
                for e in rows:
                    mine = [c for c in self.courses if (c["_email"] and c["_email"] == e["email"]) or (not c["_email"] and c["instructor_name"] == e["full_name"])]
                    e["courses_count"] = len(mine)
                    e["students_count"] = sum(c["total_enrolled"] for c in mine)
                    if self.with_abc:
                        e["agreement_signed"] = True
                        e["first_course_due_at"] = None
                return 200, {"experts": rows, "count": len(rows)}
            if path == "/api/bridge/trainer-applications":
                return 200, {"applications": copy.deepcopy(self.trainer_apps), "count": len(self.trainer_apps)}
            if path == "/api/bridge/course-offers":
                return 200, {"offers": copy.deepcopy(self.course_offers), "count": len(self.course_offers)}
            if path == "/api/bridge/program-requests":
                return 200, {"requests": copy.deepcopy(self.programs), "count": len(self.programs)}
            if path == "/api/bridge/program-requests/stats":
                counts = {}
                for p in self.programs:
                    counts[p["title"]] = counts.get(p["title"], 0) + 1
                stats = sorted([{"title": k, "count": v} for k, v in counts.items()], key=lambda x: -x["count"])
                return 200, {"stats": stats, "count": len(self.programs)}
            if path == "/api/bridge/chat-insights":
                return 200, copy.deepcopy(self.analysis)
            m = re.match(r"^/api/bridge/courses/([^/]+)/reservations$", path)
            if m:
                rows = list(self.reservations.get(m.group(1), []))
                st = params.get("status") or "all"
                if st != "all":
                    rows = [r for r in rows if r["status"] == st]
                return 200, {"reservations": copy.deepcopy(rows), "count": len(rows)}
            return None
        # —— كتابات
        if method == "POST" and path == "/api/bridge/courses":
            self._w(method, path, body)
            cid = "pc-new%d" % (len(self.courses) + 1)
            owned = bool(body.get("platform_owned"))
            c = _course(cid, "new-course-%d" % len(self.courses), body.get("title", ""), ctype=body.get("type") or "recorded_paid", active=bool(body.get("is_active", True)),
                        approval=None, price=0, lessons=0, enrolled=0, instructor=body.get("trainer_name") or ("البروفيسور" if owned else ""),
                        email=body.get("instructor_email", ""), created_h=0, updated_h=0, owned=owned)
            self.courses.append(c)
            return 200, {"id": cid, "slug": c["slug"], "title": c["title"], "is_active": c["is_active"]}
        m = re.match(r"^/api/bridge/courses/([^/]+)/(approve|reject)$", path)
        if method == "POST" and m:
            self._w(method, path, body)
            c = self._find(m.group(1))
            if not c:
                return 404, {"detail": "الدورة غير موجودة"}
            if m.group(2) == "approve":
                if c["_abc"]["agreement_signed"] is False and not c["_abc"]["platform_owned"]:
                    return 422, {"detail": "لا يمكن نشر الدورة قبل أن يوقّع صاحبها الاتفاقية الحالية"}
                c["approval_status"], c["is_active"] = "approved", True
                c["_abc"]["submitted_at"] = ""
                return 200, {"ok": True, "id": c["id"], "approval_status": "approved", "is_active": True}
            c["approval_status"], c["is_active"] = "rejected", False
            c["_abc"]["review_note"] = body.get("note", "")
            return 200, {"ok": True, "id": c["id"], "approval_status": "rejected"}
        m = re.match(r"^/api/bridge/courses/([^/]+)$", path)
        if method == "PUT" and m:
            self._w(method, path, body)
            c = self._find(m.group(1))
            if not c:
                return 404, {"detail": "الدورة غير موجودة"}
            if "is_active" in body:
                c["is_active"] = bool(body["is_active"])
                if c["is_active"]:
                    c["archived_at"] = ""
            if "bid_enabled" in body:
                c["bid_enabled"] = bool(body["bid_enabled"])
            return 200, {"ok": True, "course": {"id": c["id"], "is_active": c["is_active"]}}
        if method == "DELETE" and m:
            self._w(method, path, {"params": dict(params)})
            c = self._find(m.group(1))
            if not c:
                return 404, {"detail": "الدورة غير موجودة"}
            if params.get("hard") == "true":
                if c["is_active"] or c["total_enrolled"] > 0:
                    return 409, {"detail": "لا يمكن حذف دورة عليها اشتراك أو دفعة — استعمل الأرشفة"}
                self.courses.remove(c)
                return 200, {"ok": True, "deleted": True}
            c["is_active"], c["archived_at"] = False, iso(0)
            return 200, {"ok": True, "archived": True}
        m = re.match(r"^/api/bridge/courses/([^/]+)/schedule$", path)
        if method == "PUT" and m:
            self._w(method, path, body)
            s = self._sched(m.group(1))
            if not s:
                return 404, {"detail": "الدورة الحية غير موجودة"}
            for k in ("start_date", "zoom_link", "max_seats"):
                if k in body:
                    s[k] = body[k]
            if "confirmed" in body:
                s["confirmed"] = bool(body["confirmed"])
            return 200, {"ok": True, "course": {"id": s["id"], "schedule": s}}
        m = re.match(r"^/api/bridge/course-offers/([^/]+)/decide$", path)
        if method == "POST" and m:
            self._w(method, path, body)
            o = next((x for x in self.course_offers if x["id"] == m.group(1)), None)
            if not o:
                return 404, {"detail": "العرض غير موجود أو محسوم"}
            self.course_offers.remove(o)
            self.decided.append((m.group(1), body.get("decision"), body.get("amount")))
            return 200, {"ok": True, "id": o["id"], "status": "approved" if body.get("decision") != "reject" else "rejected"}
        m = re.match(r"^/api/bridge/live/([^/]+)/decide$", path)
        if method == "POST" and m:
            self._w(method, path, body)
            s = self._sched(m.group(1))
            if not s:
                return 404, {"detail": "الدورة غير موجودة"}
            act = body.get("action")
            if act == "confirm":
                if not s["zoom_link"]:
                    return 422, {"detail": "لا يمكن تثبيت دورة بلا رابط للقاء"}
                s["live_status"], s["confirmed"] = "confirmed", True
                return 200, {"ok": True, "live_status": "confirmed"}
            if act == "extend":
                s["live_status"], s["payment_deadline"] = "payment_window", iso(int(body.get("extend_hours", 48)))
                return 200, {"ok": True, "live_status": "payment_window"}
            if act == "cancel":
                s["live_status"] = "canceled"
                return 200, {"ok": True, "live_status": "canceled", "refunds": copy.deepcopy(self.cancel_refunds), "pending_receipts": []}
            return 422, {"detail": "إجراء غير معروف"}
        m = re.match(r"^/api/bridge/program-requests/([^/]+)/(approve|reject)$", path)
        if method == "POST" and m:
            self._w(method, path, body)
            p = next((x for x in self.programs if x["id"] == m.group(1)), None)
            if not p:
                return 404, {"detail": "Program request not found"}
            self.programs.remove(p)
            return 200, {"id": p["id"], "status": "approved" if m.group(2) == "approve" else "rejected"}
        m = re.match(r"^/api/bridge/trainers/([^/]+)/deactivate$", path)
        if method == "POST" and m:
            self._w(method, path, body)
            return 200, {"ok": True}
        return None
