# -*- coding: utf-8 -*-
"""منصّة وهميّة لـ«سوق الخدمات» (الجولة النهائية): فوق `V2Platform` بتضيف جسور السوق بحالتها —
قائمة الطلبات بالفلاتر والصفحات و`counts` (على المجموعة المفلترة بالحرف، زي جسر المنصة) · تفاصيل الطلب بعروضه · الإغلاق (٤٠٩ للمطابَق)
· الإخفاء والإظهار · النقل `relane` (٤٠٩ لو عليه عرض) · الربط `annotate` (٤٠٤ بسببين مختلفين) · «الطلب الحقيقي» · «مين طلب التدريب».

⛔ صفر شبكة: كله في الذاكرة. الأشكال بالحرف من `routes/marketplace.py` و`routes/ops_bridge.py` على المنصة (شُوهدت قراءةً فقط)،
والأسماء والأرقام مخترعة. `forced[(method, path)] = (status, payload)` يفرض ردًّا. `writes` يسجّل كل كتابة (method, path, body).

الصفوف تغطي كل عمود وكل قاعدة من قواعد العقل B0–B11: جديد · ينتظر (قديم · راكد · يجمع منضمّين · اكتمل عدده بلا دورة · رُبطت دورة · مخفي · حالة غير معروفة)
· وصله عرض · انتهى (مطابَق · مغلق · أقدم من أسبوع) · تجريبي · عرضا مدرّب.
"""
import copy
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ef_fixtures as fx          # noqa: E402
import v2_fixtures as v2fx        # noqa: E402

iso = fx.iso
NOT_FOUND = {"detail": "Not Found"}
NEED_LANE = {"course": "course_request", "service": "public_service", "expert": "request", "book": "request", "other": "request"}
NEED_FOR_KIND = {"request": "expert", "course_request": "course", "public_service": "service", "training_offer": "training_offer", "knowledge": "book"}
PLATFORM_COURSES = ("contract-basics", "marketing-basics")


def req(rid, title, **kw):
    kind = kw.pop("kind", "request")
    h = kw.pop("h", -3.0)
    r = {"id": rid, "kind": kind, "lane": kind, "need_kind": kw.pop("need_kind", NEED_FOR_KIND.get(kind, "expert")), "title": title,
         "body": kw.pop("body", "أحتاج مساعدة في هذا الموضوع، وأفضّل أن يكون الرد خلال أيام قليلة."), "specialty": kw.pop("specialty", ""), "service": "",
         "status": "open", "visibility": "public", "member_alias": kw.pop("alias", "عضو ٤٢"), "member_email": kw.pop("email", "member%s@example.test" % rid[-2:]),
         "member_name": kw.pop("name", ""), "preferred_expert_email": "", "budget": 0, "currency": "EGP", "offer_count": 0, "accepted_offer_id": None,
         "consultation_id": None, "is_test": False, "hidden": False, "hidden_reason": "", "created_at": iso(h), "updated_at": iso(h), "last_offer_at": "",
         "stale_unanswered": False, "member_phone": kw.pop("phone", ""), "author_kind": "member", "open_demand": False, "source": "", "is_platform": False,
         "join_goal": 0, "joined_count": 0, "goal_reached_at": None, "linked_course_id": "", "linked_course_slug": ""}
    r.update(kw)
    return r


def default_rows():
    return [
        # —— طلب جديد (أقل من ٢٤ ساعة، عام، بلا عرض)
        req("mk-n1", "أحتاج مراجعة عقد شراكة بين ثلاثة أطراف", h=-2.0, name="سلمى منصور", alias="عضو ٤٢", specialty="عقود", budget=1500, phone="+201000000111",
            email="salma.m@example.test", body="شراكة في مطعم بين ثلاثة أصدقاء، وأحتاج رأيًا في بند الخروج من الشراكة وتوزيع الأرباح.\nالعقد من ثماني صفحات."),
        req("mk-n2", "صياغة إنذار على يد محضر لمستأجر متأخر", h=-7.0, kind="public_service", need_kind="service", name="عمر شريف", alias="عضو ٧", phone="01200000222"),
        req("mk-n3", "أريد تعلّم كتابة العقود التجارية خطوة بخطوة", h=-5.0, kind="request", need_kind="course", name="هبة علي", alias="عضو ١٩"),   # B6: نوعه دورة ومعروض مع طلبات الخبرة
        req("mk-n4", "استشارة في ميراث خاصة بأسرتي", h=-9.0, visibility="private", preferred_expert_email="hala@experts.test", name="ياسر فؤاد", alias="عضو ٣"),
        req("mk-n5", "طلب خاص: مراجعة وصية", h=-12.0, visibility="private", name="منى سعيد", alias="عضو ٥١"),
        # —— ينتظر خبيرًا
        req("mk-w1", "نزاع على أتعاب مقاول بعد تسليم متأخر", h=-240.0, stale_unanswered=True, name="فاتن حسن", alias="عضو ٨"),
        req("mk-w2", "رأي قانوني في عقد عمل عن بُعد", h=-72.0, name="نور الهدى", alias="عضو ٢٢"),
        req("mk-w3", "ما هي خطوات تسجيل علامة تجارية؟", h=-240.0, joined_count=1, last_activity_at=iso(-48.0), name="كريم عادل", alias="عضو ٣٣"),
        req("mk-w4", "دورة: تسويق مكتب المحاماة على المنصات", h=-24.0 * 30, kind="course_request", need_kind="course", author_kind="platform", open_demand=True, is_platform=True,
            join_goal=20, joined_count=20, goal_reached_at=iso(-30.0), last_activity_at=iso(-30.0), catalog_name="كتالوج التسويق", member_name="البروفيسور", email="",
            alias="البروفيسور", body="هل تريد دورة عملية في تسويق مكتب المحاماة؟ انضم لنعرف حجم الاهتمام."),
        req("mk-w5", "دورة: الذكاء في إدارة القضايا", h=-24.0 * 10, kind="course_request", need_kind="course", author_kind="platform", open_demand=True, is_platform=True,
            join_goal=15, joined_count=6, last_activity_at=iso(-3.0), catalog_name="كتالوج الأدوات", member_name="البروفيسور", email="", alias="البروفيسور"),
        req("mk-w6", "دورة: أساسيات صياغة العقود", h=-24.0 * 40, kind="course_request", need_kind="course", author_kind="platform", open_demand=True, is_platform=True,
            join_goal=12, joined_count=12, goal_reached_at=iso(-24.0 * 6), linked_course_id="c-contract", linked_course_slug="contract-basics", member_name="البروفيسور", email="",
            alias="البروفيسور", last_activity_at=iso(-24.0 * 5)),
        req("mk-w7", "إعلان خدمات غير مناسب", h=-50.0, hidden=True, hidden_reason="محتوى ترويجي", name="حساب مجهول", alias="عضو ٩٩"),
        req("mk-w8", "طلب بحالة غير معروفة", h=-60.0, status="paused", name="هالة", alias="عضو ١"),
        req("mk-w9", "مراجعة اتفاقية سرية بين شركتين", h=-120.0, name="طارق يوسف", alias="عضو ٦١"),
        req("mk-w10", "خلاف مع شريك على حصص الأرباح", h=-96.0, name="وليد حسن", alias="عضو ٧٣"),
        req("mk-w11", "تسجيل ملكية عقار موروث", h=-150.0, name="إيمان صلاح", alias="عضو ٨١"),
        req("mk-w12", "عقد توريد بين شركتين", h=-180.0, name="شريف نجيب", alias="عضو ٩٠"),
        # —— وصله عرض
        req("mk-o1", "تأسيس شركة ذات مسؤولية محدودة", h=-30.0, offer_count=3, last_offer_at=iso(-4.0), name="ليلى مراد", alias="عضو ١٢", specialty="شركات", budget=4000, phone="+201111111222"),
        req("mk-o2", "تعويض عن تأخر شحنة دولية", h=-80.0, offer_count=1, last_offer_at=iso(-30.0), name="أيمن سعد", alias="عضو ٢٧", budget=900),
        # —— انتهى
        req("mk-d1", "عقد إيجار محل تجاري", h=-60.0, status="matched", updated_at=iso(-3.0), offer_count=2, accepted_offer_id="of-d1", consultation_id="c-1", name="رنا خالد", alias="عضو ١٥"),
        req("mk-d2", "استفسار عن نفقة", h=-120.0, status="closed", updated_at=iso(-80.0), name="سامي نبيل", alias="عضو ٣٨"),
        req("mk-d3", "طلب قديم أُغلق", h=-24.0 * 40, status="closed", updated_at=iso(-24.0 * 20), name="جميلة", alias="عضو ٤"),
        # —— تجريبي
        req("mk-t1", "طلب تجريبي للفحص", h=-6.0, is_test=True, name="اختبار", alias="عضو ٠"),
        # —— عرضا مدرّب (جانب العرض: لا يظهران في اللوحة)
        req("mk-s1", "دورة صياغة العقود (مدرّب)", h=-24.0 * 3, kind="training_offer", need_kind="training_offer", name="د. هالة سمير", alias="مدرّب ١"),
        req("mk-s2", "ورشة التحكيم التجاري (مدرّب)", h=-24.0 * 5, kind="training_offer", need_kind="training_offer", name="أ. فيصل", alias="مدرّب ٢"),
    ]


OFFERS = [
    {"id": "of-1", "expert_display": "د. هالة سمير", "expert_email": "hala@experts.test", "price": 3500.0, "currency": "EGP", "eta_days": 7, "status": "pending",
     "message": "أنفّذ التأسيس كاملًا بما فيه عقد التأسيس والسجل التجاري، وأتابع الإجراءات حتى الاستلام.", "created_at": iso(-4.0), "course": None},
    {"id": "of-2", "expert_display": "أ. فيصل العتيبي", "expert_email": "faisal@experts.test", "price": 3000.0, "currency": "EGP", "eta_days": 10, "status": "pending",
     "message": "", "created_at": iso(-12.0), "course": None},
    {"id": "of-3", "expert_display": "أ. نادية فؤاد", "expert_email": "nadia@example.test", "price": 4200.0, "currency": "EGP", "eta_days": 1, "status": "pending",
     "message": "لدي دورة قصيرة تغطي هذا الموضوع وأرفقتها مع العرض.", "created_at": iso(-26.0), "course": {"title": "أساسيات الشركات الناشئة"}},
]

DEMAND = {
    "generated_at": iso(0), "window_days": 90,
    "by_need_kind": [
        {"need_kind": "expert", "label": "خبير", "count": 14, "total": 22, "matched": 3, "closed": 5, "zero_offer": 6, "with_offers": 8},
        {"need_kind": "course", "label": "دورة", "count": 9, "total": 12, "matched": 0, "closed": 3, "zero_offer": 9, "with_offers": 0},
        {"need_kind": "service", "label": "خدمة", "count": 4, "total": 6, "matched": 1, "closed": 1, "zero_offer": 0, "with_offers": 4},
        {"need_kind": "book", "label": "كتاب", "count": 2, "total": 2, "matched": 0, "closed": 0, "zero_offer": 2, "with_offers": 0},
    ],
    "top_topics": [{"term": "عقود", "count": 11, "sources": {}}, {"term": "ميراث", "count": 6, "sources": {}}],
    "suggested_courses": [
        {"title_hint": "أساسيات صياغة العقود التجارية", "signal_count": 17, "origin": "explicit", "specialty": "عقود",
         "sources": {"market_requests": 6, "training_interests": 5, "course_interests": 2, "chat": 4, "open_demand_joins": 0}, "samples": ["دورة في صياغة العقود"]},
        {"title_hint": "تسويق مكتب المحاماة", "signal_count": 20, "origin": "explicit", "specialty": "تسويق",
         "sources": {"market_requests": 0, "training_interests": 0, "course_interests": 0, "chat": 0, "open_demand_joins": 20}, "samples": []},
        {"title_hint": "دورة في الميراث", "signal_count": 6, "origin": "chat_terms", "specialty": "",
         "sources": {"market_requests": 0, "training_interests": 0, "course_interests": 0, "chat": 6}, "samples": []},
    ],
    "signals": {"open_requests": 12, "total_requests": 41, "member_requests": 36, "unanswered_requests": 9, "open_demand_cards": 3,
                "open_demand_joins": 38, "open_demand_goal_reached": 2, "course_interests": 4, "training_interests": 7, "chat_rows": 120},
    "scanned": {"market_requests": 41},
}

TRAINING = [
    {"id": "ti-1", "name": "ياسمين عادل", "phone": "+201000000333", "email": "yasmin@example.test", "wanted_course": "أساسيات صياغة العقود", "status": "new",
     "created_at": iso(-5.0), "updated_at": iso(-5.0)},
    {"id": "ti-2", "name": "محمود سالم", "phone": "", "email": "mahmoud@example.test", "wanted_course": "", "status": "new",
     "created_at": iso(-50.0), "updated_at": iso(-50.0)},
    {"id": "ti-3", "name": "دعاء حسين", "phone": "01155555555", "email": "", "wanted_course": "التحكيم التجاري", "status": "new",
     "created_at": iso(-24.0 * 6), "updated_at": iso(-24.0 * 6)},
]


class MarketPlatform(v2fx.V2Platform):
    """`V2Platform` + جسور السوق بحالتها."""

    def __init__(self, empty=False, d2=True, **kw):
        super(MarketPlatform, self).__init__(empty=empty, d2=d2, **kw)
        self.rows = [] if empty else default_rows()
        self.writes = []
        self.market = self.rows           # لوحة D1 (مربّع السوق) تقرأ نفس القائمة
        self.demand = None if empty else copy.deepcopy(DEMAND)
        self.training = [] if empty else copy.deepcopy(TRAINING)
        self.detail_offers = {"mk-o1": copy.deepcopy(OFFERS), "mk-o2": copy.deepcopy(OFFERS[:1])}
        self.missing = False               # True ⇒ جسر السوق ٤٠٤ (لم يُنشر)

    # —— التوجيه
    def _route(self, method, path, params, body):
        m = method.upper()
        forced = self.forced.get((m, path))
        if forced is not None:
            return forced
        out = self._market(m, path, params or {}, body or {})
        if out is not None:
            return out
        return super(MarketPlatform, self)._route(method, path, params, body)

    def _find(self, rid):
        return next((r for r in self.rows if r["id"] == rid), None)

    def _counts(self, rows):
        c = {"by_lane": {}, "by_need_kind": {}, "by_status": {}, "by_author_kind": {}}
        for r in rows:
            for b, k in (("by_lane", r["kind"]), ("by_need_kind", r["need_kind"]), ("by_status", r["status"] if r["status"] in ("open", "matched", "closed") else None),
                         ("by_author_kind", "platform" if r.get("author_kind") == "platform" else "member")):
                if k:
                    c[b][k] = c[b].get(k, 0) + 1
        return c

    def _row_out(self, r):
        out = copy.deepcopy(r)
        out["offer_count"] = r["offer_count"]
        return out

    def _market(self, m, path, params, body):
        if path == "/api/bridge/market/requests" and m == "GET":
            if self.missing:
                return 404, NOT_FOUND
            rows = list(self.rows)
            lane = params.get("lane") or "all"
            if lane != "all":
                rows = [r for r in rows if r["kind"] == lane]
            st = params.get("status") or "all"
            if st != "all":
                rows = [r for r in rows if r["status"] == st]
            if params.get("author_kind") == "platform":
                rows = [r for r in rows if r.get("author_kind") == "platform"]
            elif params.get("author_kind") == "member":
                rows = [r for r in rows if r.get("author_kind") != "platform"]
            nk = params.get("need_kind")
            if nk:
                rows = [r for r in rows if r["need_kind"] == nk]
            q = (params.get("q") or "").strip().lower()
            if q:
                rows = [r for r in rows if q in r["title"].lower() or q in r["body"].lower() or q in r["member_email"].lower()]
            inc = params.get("include_test")
            if str(inc).lower() in ("false", "0"):
                rows = [r for r in rows if not r["is_test"]]
            rows.sort(key=lambda r: r["created_at"], reverse=True)
            limit = int(params.get("limit") or 200)
            skip = int(params.get("skip") or 0)
            page = rows[skip:skip + limit]
            return 200, {"items": [self._row_out(r) for r in page], "total": len(rows), "counts": self._counts(rows), "lane": lane, "status": st}
        mm = re.match(r"^/api/bridge/market/requests/([^/]+)(?:/(close|hide|relane|annotate))?$", path)
        if mm:
            r = self._find(mm.group(1))
            act = mm.group(2)
            if m == "GET" and not act:
                if r is None:
                    return 404, {"detail": "Request not found"}
                out = self._row_out(r)
                out["offers"] = copy.deepcopy(self.detail_offers.get(r["id"], []))
                return 200, out
            if m == "POST" and act:
                if r is None:
                    return 404, {"detail": "Request not found"}
                self.writes.append((m, path, copy.deepcopy(body)))
                if act == "close":
                    if r["status"] == "matched":
                        return 409, {"detail": "A matched request cannot be closed"}
                    if r["status"] == "closed":
                        return 200, {"ok": True, "status": "closed", "already": True}
                    r["status"] = "closed"
                    r["updated_at"] = iso(0)
                    return 200, {"ok": True, "status": "closed", "already": False}
                if act == "hide":
                    r["hidden"] = bool(body.get("hidden", True))
                    r["hidden_reason"] = (body.get("reason") or "") if r["hidden"] else ""
                    return 200, {"ok": True, "hidden": r["hidden"]}
                if act == "relane":
                    target = body.get("need_kind")
                    if target not in NEED_LANE:
                        return 422, {"detail": {"message": "نوع احتياج غير معروف", "allowed": sorted(NEED_LANE)}}
                    if r["offer_count"]:
                        return 409, {"detail": "الطلب عليه عروض بالفعل — نقله يضيّع المزايد"}
                    r["need_kind"] = target
                    r["kind"] = NEED_LANE[target]
                    r["lane"] = r["kind"]
                    return 200, {"ok": True, "id": r["id"], "changed": True}
                if act == "annotate":
                    course = (body.get("linked_course_id") or "").strip()
                    if course and course not in PLATFORM_COURSES:
                        return 404, {"detail": "الدورة المرتبطة غير موجودة"}
                    r["linked_course_id"] = course
                    r["linked_course_slug"] = course
                    return 200, {"ok": True, "id": r["id"], "linked_course_id": course}
        if path == "/api/bridge/market/demand" and m == "GET":
            if self.demand is None:
                return 404, NOT_FOUND
            return 200, copy.deepcopy(self.demand)
        if path == "/api/bridge/training-interests" and m == "GET":
            rows = copy.deepcopy(self.training)
            return 200, {"interests": rows, "count": len(rows)}
        return None
