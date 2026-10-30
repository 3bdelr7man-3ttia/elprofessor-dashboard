# -*- coding: utf-8 -*-
"""منصّة وهميّة لشاشة «الفلوس» الجديدة (D3): فوق `V2Platform` بتضيف جسور الجولة — الحد الأدنى للسحب · جدول النِّسَب · أرصدة
الإعلانات · المدفوعات العالقة · الدخل حسب الخدمة · الاستردادات اليدوية · الأسعار الموحّدة · طابور عروض الكتب وطلبات القرّاء.

⛔ صفر شبكة: كله في الذاكرة. الأشكال بالحرف من `routes/money_bridge.py` و`routes/books_bridge.py` و`routes/scheduling.py` على المنصة
(شُوهدت قراءةً فقط)، والأسماء والأرقام مخترعة. الكتابة حالتها حقيقية (rev/version) والرفض بنفس رسائل المنصة العربية، فالواجهة
بتتجرّب على ٤٢٢ و٤٠٩ فعلًا.

`forced[(method, path)] = (status, payload)` يفرض ردًّا (لاختبار المصدر الفاشل). `down = {path, …}` يخلّي المصدر يرد ٥٠٢.
`course_prices = False` (الافتراضي) ⇒ أسعار الدورات ٤٠٤ كما لو مفتاح الدورات مقفول.
"""
import copy
import datetime
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ef_fixtures as fx          # noqa: E402
import v2_fixtures as v2fx        # noqa: E402

iso = fx.iso

COUNTRIES = ["eg", "sa", "ae", "kw", "qa", "default"]
CURRENCIES = {"eg": "EGP", "sa": "SAR", "ae": "AED", "kw": "KWD", "qa": "QAR", "default": "USD"}
NOT_FOUND = {"detail": "Not Found"}

DEFAULT_SHARES = {
    "version": 3,
    "books": {"normal": {"owner": 60, "platform": 40}, "ads": {"owner": 65, "platform": 35}},
    "courses": {"base": 35, "code_max": 50, "ads_max_bonus": 25, "owner_cap": 65},
    "cases": {"ladder": [{"max_egp": 10000, "platform_pct": 35}, {"max_egp": 30000, "platform_pct": 30},
                         {"max_egp": 50000, "platform_pct": 25}, {"max_egp": None, "platform_pct": 25}]},
    "case_floor": 25, "platform_floor": 35,
    "affiliate": {"rate": 10, "split": "pro_rata", "floor_measured": "before_affiliate"},
    "updated_at": iso(-26), "updated_by": "founder@example.test",
}

STUCK_ITEMS = [
    {"order_id": "ord-s1", "kind": "course", "title": "أساسيات التسويق القانوني", "amount": 750.0, "currency": "EGP", "created_at": iso(-26),
     "buyer_email": "nour@example.test", "buyer_name": "نور الهدى سالم", "age_hours": 26.0, "provider": "stripe"},
    {"order_id": "ord-s2", "kind": "book", "title": "دليل المستأجر في عقود الإيجار", "amount": 149.0, "currency": "EGP", "created_at": iso(-5),
     "buyer_email": "omar@example.test", "buyer_name": "عمر شريف", "age_hours": 5.0, "provider": "paymob"},
    {"order_id": "ord-s3", "kind": "consultation", "title": "ملف: مراجعة عقد شراكة", "amount": 300.0, "currency": "SAR", "created_at": iso(-3),
     "buyer_email": "faten@example.test", "buyer_name": "", "age_hours": 3.2, "provider": "stripe"},
]

ADS_ITEMS = [
    {"owner_kind": "book", "owner_id": "bk-tenant-guide", "balance": [{"currency": "EGP", "amount": 1850.0}], "last_entry_at": iso(-4),
     "owner_email": "nadia@example.test", "entries": 5, "title": "دليل المستأجر في عقود الإيجار"},
    {"owner_kind": "book", "owner_id": "bk-startup-law", "balance": [{"currency": "EGP", "amount": 420.5}, {"currency": "USD", "amount": 30.0}],
     "last_entry_at": iso(-70), "owner_email": "", "entries": 3, "title": "قانون الشركات الناشئة"},
    {"owner_kind": "course", "owner_id": "contract-basics", "balance": [{"currency": "SAR", "amount": 600.0}], "last_entry_at": iso(-200),
     "owner_email": "hala@example.test", "entries": 2, "title": ""},
]

ADS_ENTRIES = {
    "bk-tenant-guide": [
        {"owner_id": "bk-tenant-guide", "owner_kind": "book", "entry": "deposit", "amount": 2000.0, "currency": "EGP", "at": iso(-24 * 9), "by": "system"},
        {"owner_id": "bk-tenant-guide", "owner_kind": "book", "entry": "spend", "amount": 150.0, "currency": "EGP", "at": iso(-24 * 3), "by": "founder@example.test"},
    ],
}

REFUNDS = [
    {"consultation_id": "c-r1", "booking_id": "b-1", "member_email": "salma@example.test", "expert_email": "hala@experts.test", "amount": 450.0,
     "currency": "EGP", "escrow_state": "held", "payment_id": "pay-1", "cancelled_at": iso(-52), "settled_at": "", "full_refund": True, "cancelled_by": "member"},
    {"consultation_id": "c-r2", "booking_id": "b-2", "member_email": "yasser@example.test", "expert_email": "nada@experts.test", "amount": 300.0,
     "currency": "EGP", "escrow_state": "held", "payment_id": "pay-2", "cancelled_at": iso(-8), "settled_at": "", "full_refund": False, "cancelled_by": "expert"},
]

BOOK_PRICES = {
    "bk-tenant-guide": {"title": "دليل المستأجر في عقود الإيجار", "visible": True,
                        "versions": {"read": {"eg": 150.0, "sa": 40.0, "default": 9.0}, "pdf": {"eg": 220.0, "default": 12.0}}},
    "bk-startup-law": {"title": "قانون الشركات الناشئة", "visible": True, "versions": {"read": {"eg": 250.0, "default": 10.0}, "pdf": {"eg": 320.0}}},
    "bk-labor": {"title": "الوجيز في قانون العمل", "visible": True, "versions": {"read": {"eg": 180.0}, "pdf": {}}},
    "bk-new": {"title": "دليل الميراث للأسرة", "visible": False, "versions": None},
}

OFFERS = [
    {"id": "off-1", "title": "عقد الوكالة التجارية: شرح عملي", "about": "دليل مبسّط يشرح أنواع الوكالة وحقوق الطرفين مع نماذج جاهزة.", "type": "guide",
     "suggested_price": {"amount": 390.0, "currency": "EGP"}, "cover": {"mode": "design_for_me", "url": ""}, "file": {"name": "agency.pdf", "url": "https://example.test/agency.pdf"},
     "owner_email": "mai@example.test", "owner_name": "أ. مي حسن", "status": "in_review", "submitted_at": iso(-30),
     "agreement": {"id": "ag-1", "offer_id": "off-1", "plan": "normal", "plan_label": "نشر عادي", "owner_pct": 60, "platform_pct": 40, "shares_version": 3,
                   "text_version": "v1", "text": "", "accepted_at": iso(-31)}, "ai_review": None},
    {"id": "off-2", "title": "بحث: التحكيم التجاري الدولي", "about": "مراجعة لأحكام التحكيم في المنطقة العربية مع قضايا مختارة.", "type": "research",
     "suggested_price": None, "cover": {"mode": "upload", "url": "https://example.test/cover.jpg"}, "file": {"name": "arb.pdf", "url": "https://example.test/arb.pdf"},
     "owner_email": "karim.l@example.test", "owner_name": "د. كريم لطفي", "status": "in_review", "submitted_at": iso(-6),
     "agreement": {"id": "ag-2", "offer_id": "off-2", "plan": "ads", "plan_label": "نشر مع إعلانات", "owner_pct": 65, "platform_pct": 35, "shares_version": 3,
                   "text_version": "v1", "text": "", "accepted_at": iso(-7)}, "ai_review": None},
]

REQUESTS = [
    {"id": "rq-1", "type": "book", "topic": "كتاب عن قانون الإيجار القديم", "group_key": "g-rent", "status": "new", "hidden": False, "created_at": iso(-48), "book": None, "public_text": ""},
    {"id": "rq-2", "type": "book", "topic": "كتاب عن قانون الإيجار القديم", "group_key": "g-rent", "status": "new", "hidden": False, "created_at": iso(-20), "book": None, "public_text": ""},
    {"id": "rq-3", "type": "book", "topic": "كتاب عن قانون الإيجار القديم", "group_key": "g-rent", "status": "new", "hidden": False, "created_at": iso(-3), "book": None, "public_text": ""},
    {"id": "rq-4", "type": "guide", "topic": "دليل تأسيس شركة فردية", "group_key": "g-sole", "status": "new", "hidden": False, "created_at": iso(-10), "book": None, "public_text": ""},
    {"id": "rq-5", "type": "research", "topic": "بحث في حماية البيانات الشخصية", "group_key": "g-data", "status": "seeking", "hidden": False, "created_at": iso(-100), "book": None,
     "public_text": "حماية البيانات الشخصية"},
]


def _groups(rows):
    groups = {}
    for r in rows:
        g = groups.setdefault(r["group_key"], {"key": r["group_key"], "topic": r["topic"], "public_text": r.get("public_text") or "", "type": r["type"],
                                               "count": 0, "first_at": r["created_at"], "last_at": r["created_at"], "request_ids": []})
        g["count"] += 1
        g["request_ids"].append(r["id"])
        g["last_at"] = max(g["last_at"], r["created_at"])
    return sorted(groups.values(), key=lambda g: -g["count"])


class D3Platform(v2fx.V2Platform):
    """`V2Platform` + جسور الفلوس والكتب بحالتها. كل ما بتسجّله الكتابة: `writes` (method, path, body)."""

    def __init__(self, empty=False, d2=False, course_prices=False, **kw):
        super(D3Platform, self).__init__(empty=empty, d2=d2, **kw)
        self.down = set()
        self.course_prices = course_prices
        self.money = {"withdraw_min": 500, "rev": 0, "updated_at": "", "updated_by": "", "history": []}
        self.shares = copy.deepcopy(DEFAULT_SHARES)
        self.shares_log = []
        self.stuck = [] if empty else copy.deepcopy(STUCK_ITEMS)
        self.ads = [] if empty else copy.deepcopy(ADS_ITEMS)
        self.refunds = [] if empty else copy.deepcopy(REFUNDS)
        self.prices = {} if empty else copy.deepcopy(BOOK_PRICES)
        self.price_docs = {}
        self.course_docs = {"contract-basics": {"title": "أساسيات صياغة العقود", "visible": True, "versions": {"standard": {"eg": 450.0, "default": 20.0}}}}
        self.offers = [] if empty else copy.deepcopy(OFFERS)
        self.requests = [] if empty else copy.deepcopy(REQUESTS)
        self.writes = []
        self.income = {"ok": True, "month": "", "services": [
            {"key": "expert_files", "label": "ملفات الخبراء", "count": 14, "totals": [{"currency": "EGP", "amount": 9300.0}]},
            {"key": "courses", "label": "الدورات", "count": 6, "totals": [{"currency": "EGP", "amount": 2700.0}, {"currency": "SAR", "amount": 300.0}]},
            {"key": "books", "label": "الكتب", "count": 9, "totals": [{"currency": "EGP", "amount": 1100.0}]},
            {"key": "other", "label": "أخرى", "count": 2, "totals": [{"currency": "EGP", "amount": 400.0}]}]}
        if empty:
            for s in self.income["services"]:
                s["count"], s["totals"] = 0, []

    def queue(self):
        q = super(D3Platform, self).queue()
        if not self.empty:
            q["manual_refunds_pending"] = len(self.refunds)
            q["stuck_card_payments"] = {"count": len(self.stuck), "orders": [
                {"id": s["order_id"], "user_email": s["buyer_email"], "amount": s["amount"], "currency": s["currency"], "kind": s["kind"],
                 "gateway": s["provider"], "created_at": s["created_at"]} for s in self.stuck]}
        return q

    # ---------------------------------------------------------------- التوجيه
    def _route(self, method, path, params, body):
        forced = self.forced.get((method.upper(), path))
        if forced is not None:
            return forced
        if path in self.down or path.rsplit("/", 1)[0] in self.down:
            return 502, {"detail": "تعذر الاتصال"}
        out = self._d3(method.upper(), path, params, body)
        if out is not None:
            return out
        return super(D3Platform, self)._route(method, path, params, body)

    def _ok_write(self, method, path, body):
        self.writes.append((method, path, copy.deepcopy(body)))

    def _d3(self, method, path, params, body):
        if path == "/api/bridge/settings/money":
            return self._money(method, path, body)
        if path == "/api/bridge/shares":
            return self._shares(method, path, body)
        if path == "/api/bridge/ads-ledger" and method == "GET":
            return 200, {"ok": True, "count": len(self.ads), "items": copy.deepcopy(self.ads)}
        m = re.match(r"^/api/bridge/ads-ledger/([^/]+)$", path)
        if m and method == "GET":
            oid = m.group(1)
            row = next((a for a in self.ads if a["owner_id"] == oid), None)
            return 200, {"ok": True, "owner_id": oid, "owner_kind": "book", "balance": copy.deepcopy(row["balance"]) if row else [],
                         "report": {}, "entries": copy.deepcopy(ADS_ENTRIES.get(oid, []))}
        if path == "/api/bridge/payments/stuck" and method == "GET":
            return 200, {"ok": True, "count": len(self.stuck), "after_hours": 2, "paid_without_delivery": None, "items": copy.deepcopy(self.stuck)}
        if path == "/api/bridge/income/by-service" and method == "GET":
            out = copy.deepcopy(self.income)
            out["month"] = (params or {}).get("month") or datetime.date.today().strftime("%Y-%m")
            return 200, out
        if path == "/api/bridge/refunds/pending" and method == "GET":
            return 200, {"refunds": copy.deepcopy(self.refunds), "count": len(self.refunds), "total": len(self.refunds), "settled_count": 0, "next_cursor": ""}
        m = re.match(r"^/api/bridge/prices/(book|course)(?:/([^/]+))?$", path)
        if m:
            return self._prices(method, m.group(1), m.group(2), body)
        if path == "/api/bridge/book-offers" and method == "GET":
            st = (params or {}).get("status") or "in_review"
            rows = [o for o in self.offers if st == "all" or o["status"] == st]
            return 200, {"ok": True, "count": len(rows), "offers": copy.deepcopy(rows)}
        m = re.match(r"^/api/bridge/book-offers/([^/]+)/(approve|reject)$", path)
        if m and method == "POST":
            return self._offer_decide(m.group(1), m.group(2), body)
        if path == "/api/bridge/book-requests" and method == "GET":
            return 200, {"ok": True, "count": len(self.requests), "groups": _groups(self.requests), "requests": copy.deepcopy(self.requests)}
        m = re.match(r"^/api/bridge/book-requests/([^/]+)$", path)
        if m and method == "PATCH":
            return self._request_patch(m.group(1), body)
        return None

    # ---------------------------------------------------------------- الإعدادات
    def _money(self, method, path, body):
        if method == "GET":
            out = {"ok": True, "withdraw_min": self.money["withdraw_min"], "rev": self.money["rev"], "updated_at": self.money["updated_at"],
                   "updated_by": self.money["updated_by"], "allowed": {"withdraw_min": {"min": 50, "max": 20000}}, "history": copy.deepcopy(self.money["history"])}
            return 200, out
        if method == "PUT":
            if body.get("confirmed") is not True:
                return 422, {"detail": "لازم تأكيد صريح قبل التعديل"}
            if not str(body.get("by") or "").strip():
                return 422, {"detail": "لازم نعرف مين اللي بيعدّل"}
            v = body.get("withdraw_min")
            if not isinstance(v, int) or isinstance(v, bool) or v < 50 or v > 20000:
                return 422, {"detail": "الحدّ الأدنى للسحب لازم يبقى بين 50 و20000 جنيه"}
            if body.get("rev") is not None and body["rev"] != self.money["rev"]:
                return 409, {"detail": "حدّ تاني عدّل الإعداد ده دلوقتي — حدّث الشاشة وجرّب تاني"}
            self._ok_write(method, path, body)
            before = self.money["withdraw_min"]
            self.money.update({"withdraw_min": v, "rev": self.money["rev"] + 1, "updated_at": iso(0), "updated_by": body["by"]})
            self.money["history"].insert(0, {"setting": "money", "by": body["by"], "at": iso(0), "rev_before": self.money["rev"] - 1, "rev_after": self.money["rev"],
                                             "changes": {"withdraw_min": v}, "before": {"withdraw_min": before}, "after": {"withdraw_min": v}})
            return 200, {"ok": True, "withdraw_min": v, "rev": self.money["rev"], "updated_at": self.money["updated_at"],
                         "updated_by": self.money["updated_by"], "history": copy.deepcopy(self.money["history"])}
        return None

    @staticmethod
    def _merge(base, patch):
        if isinstance(base, dict) and isinstance(patch, dict):
            out = dict(base)
            for k, v in patch.items():
                out[k] = D3Platform._merge(base.get(k), v) if k in base else copy.deepcopy(v)
            return out
        return copy.deepcopy(patch)

    def _shares(self, method, path, body):
        if method == "GET":
            return 200, {"ok": True, "shares": copy.deepcopy(self.shares), "version": self.shares["version"], "history": copy.deepcopy(self.shares_log)}
        if method == "PUT":
            if body.get("confirmed") is not True:
                return 422, {"detail": "لازم تأكيد صريح قبل التعديل"}
            if int(body.get("version", -1)) != self.shares["version"]:
                return 409, {"detail": "حدّ تاني عدّل النِّسَب دلوقتي — حدّث الشاشة وجرّب تاني"}
            after = copy.deepcopy(self.shares)
            for k, v in (body.get("changes") or {}).items():
                after[k] = self._merge(self.shares[k], v)
            for plan, row in after["books"].items():
                if row["platform"] < 35:
                    return 422, {"detail": "نصيب المنصّة من الكتب ما ينزلش عن 35٪"}
                if row["owner"] + row["platform"] != 100:
                    return 422, {"detail": "نصيب الكاتب + نصيب المنصّة لازم = ١٠٠"}
            for step in after["cases"]["ladder"]:
                if step["platform_pct"] < after["case_floor"]:
                    return 422, {"detail": "نصيب المنصّة في القضايا ما ينزلش عن 25٪"}
            self._ok_write(method, path, body)
            keys = ("books", "courses", "cases", "case_floor", "platform_floor", "affiliate")
            self.shares_log.insert(0, {"setting": "shares", "by": body["by"], "at": iso(0), "version_before": self.shares["version"], "version_after": self.shares["version"] + 1,
                                       "changes": copy.deepcopy(body.get("changes")), "before": {k: copy.deepcopy(self.shares[k]) for k in keys},
                                       "after": {k: copy.deepcopy(after[k]) for k in keys}})
            after["version"] = self.shares["version"] + 1
            after["updated_at"], after["updated_by"] = iso(0), body["by"]
            self.shares = after
            return 200, {"ok": True, "shares": copy.deepcopy(self.shares), "version": self.shares["version"], "history": copy.deepcopy(self.shares_log)}
        return None

    # ---------------------------------------------------------------- الأسعار
    def _docs(self, kind):
        return self.prices if kind == "book" else self.course_docs

    @staticmethod
    def _entry(c, a):
        return {"amount": a, "currency": CURRENCIES[c]}

    def _view(self, kind, item_id):
        d = self._docs(kind).get(item_id)
        if d is None or d.get("versions") is None:
            return {"kind": kind, "id": item_id, "title": (d or {}).get("title", ""), "visible": False, "versions": {}, "updated_at": "", "updated_by": "", "rev": 0, "history": []}
        versions = {v: {c: self._entry(c, a) for c, a in row.items()} for v, row in d["versions"].items()}
        return {"kind": kind, "id": item_id, "title": d["title"], "visible": d["visible"], "versions": versions, "updated_at": d.get("updated_at") or iso(-100),
                "updated_by": d.get("updated_by") or "founder@example.test", "rev": d.get("rev", 1), "history": d.get("history", [])}

    def _prices(self, method, kind, item_id, body):
        if kind == "course" and not self.course_prices:
            return 404, NOT_FOUND
        docs = self._docs(kind)
        if item_id is None and method == "GET":
            items = []
            for iid, d in docs.items():
                v = self._view(kind, iid)
                mins = {}
                for row in v["versions"].values():
                    for c, e in row.items():
                        if c not in mins or e["amount"] < mins[c]["amount"]:
                            mins[c] = dict(e)
                items.append({"id": iid, "title": d["title"], "visible": v["visible"], "has_prices": d.get("versions") is not None,
                              "min_price": {c: mins[c] for c in COUNTRIES if c in mins}, "updated_at": v["updated_at"] or None})
            return 200, {"ok": True, "kind": kind, "countries": COUNTRIES, "currencies": CURRENCIES, "count": len(items), "items": items}
        if item_id is not None and method == "GET":
            if item_id not in docs:
                return 404, {"detail": "الكتاب مش موجود"}
            return 200, {"ok": True, "countries": COUNTRIES, "currencies": CURRENCIES, "versions_allowed": ["read", "pdf"] if kind == "book" else None,
                         "prices": self._view(kind, item_id)}
        if item_id is not None and method == "PUT":
            if item_id not in docs:
                return 404, {"detail": "الكتاب مش موجود"}
            if body.get("confirmed") is not True:
                return 422, {"detail": "لازم تأكيد التعديل الأول"}
            cur = self._view(kind, item_id)
            if body.get("rev") is not None and body["rev"] != cur["rev"]:
                return 409, {"detail": "الأسعار اتعدّلت من مكان تاني — حدّث الصفحة وجرّب تاني"}
            versions = {}
            for v, row in (body.get("versions") or {}).items():
                versions[v] = {}
                for c, e in (row or {}).items():
                    if c not in COUNTRIES:
                        return 422, {"detail": "بلد غير معروف في السعر"}
                    if e.get("currency") != CURRENCIES[c]:
                        return 422, {"detail": "العملة في %s لازم %s" % (c, CURRENCIES[c])}
                    versions[v][c] = float(e["amount"])
            if body.get("visible") and not any("default" in row for row in versions.values()):
                return 422, {"detail": "علشان يظهر للناس لازم سعر «باقي البلاد» لنسخة واحدة على الأقل"}
            self._ok_write(method, "/api/bridge/prices/%s/%s" % (kind, item_id), body)
            docs[item_id].update({"versions": versions, "visible": body["visible"], "rev": cur["rev"] + 1, "updated_by": body["by"], "updated_at": iso(0)})
            return 200, {"ok": True, "prices": dict(self._view(kind, item_id), changes=1)}
        return None

    # ---------------------------------------------------------------- الكتب
    def _offer_decide(self, oid, action, body):
        o = next((x for x in self.offers if x["id"] == oid), None)
        if o is None:
            return 404, {"detail": "العرض مش موجود"}
        if o["status"] != "in_review":
            return 409, {"detail": "العرض ده مش في المراجعة"}
        if action == "reject":
            if not str(body.get("reason") or "").strip():
                return 422, {"detail": "اكتب سبب الرفض"}
            self._ok_write("POST", "/api/bridge/book-offers/%s/reject" % oid, body)
            o["status"] = "rejected"
            return 200, {"ok": True, "offer": copy.deepcopy(o)}
        read = ((body.get("versions") or {}).get("read") or {}).get("pricing") or ((body.get("versions") or {}).get("read") or {})
        if not read:
            return 422, {"detail": "حدّد سعر القراءة لبلد واحد على الأقل"}
        self._ok_write("POST", "/api/bridge/book-offers/%s/approve" % oid, body)
        o["status"] = "live"
        return 200, {"ok": True, "offer": copy.deepcopy(o)}

    def _request_patch(self, rid, body):
        row = next((r for r in self.requests if r["id"] == rid), None)
        if row is None:
            return 404, {"detail": "الطلب مش موجود"}
        self._ok_write("PATCH", "/api/bridge/book-requests/%s" % rid, body)
        targets = [r for r in self.requests if r["group_key"] == row["group_key"]] if body.get("apply_to_group") else [row]
        for r in targets:
            if "status" in body:
                r["status"] = body["status"]
            if "hidden" in body:
                r["hidden"] = body["hidden"]
        return 200, {"ok": True, "updated": len(targets), "request": copy.deepcopy(row)}


# ---------------------------------------------------------------- بيانات الداشبورد نفسه (SQLite): دفتر الإيرادات والضمان
def seed_dash(appmod, today=None):
    """يزرع في قاعدة الداشبورد المؤقتة صفوف إيراد (اليوم · هذا الشهر · هذه السنة · بعملة أجنبية) وجلسات ضمان محجوزة. يعيد عدد الصفوف."""
    today = today or datetime.date.today()
    m = appmod
    rows = []

    def rev(days_ago, source, egp=0.0, usd=0.0, foreign=None, desc=""):
        d = today - datetime.timedelta(days=days_ago)
        r = m.Revenue(date=d, source=source, description=desc or ("إيراد " + source), amount_egp=egp if not foreign else None, amount_usd=usd,
                      payment_id="seed-%s-%s-%s" % (source, days_ago, len(rows)), payment_method="platform")
        if foreign:
            r.amount_original, r.currency, r.needs_fx = foreign[1], foreign[0], True
        rows.append(r)

    first = today.replace(day=1)
    in_month = (today - first).days            # أقدم يوم في الشهر ⇒ نحسب الأيام داخل الشهر الحالي
    rev(0, "consultation", egp=500.0)
    rev(0, "consultation", egp=500.0)
    rev(0, "course", egp=450.0)
    rev(0, "course", usd=30.0)
    rev(0, "book", egp=150.0)
    rev(0, "course", foreign=("SAR", 300.0))
    if in_month >= 2:
        rev(2, "consultation", egp=1000.0)
        rev(in_month, "book", egp=220.0)
    rev(40, "consultation", egp=1500.0)
    rev(70, "course", egp=900.0)
    with m.app.app_context():
        for r in rows:
            m.db.session.add(r)
        for i, (amt, cur, st) in enumerate(((600.0, "EGP", "held"), (1000.0, "EGP", "held"), (200.0, "USD", "held"), (500.0, "EGP", "dispute"), (400.0, "EGP", "released"))):
            m.db.session.add(m.EscrowSession(id="ESC-D3%02d" % i, student_name="طالب %d" % i, student_email="s%d@example.test" % i, expert_name="خبير", expert_email="e@example.test",
                                             amount=amt, currency=cur, status=st, held_at=datetime.datetime.utcnow(), ref="seed-esc-%d" % i, source="platform"))
        m.db.session.commit()
    return len(rows)
