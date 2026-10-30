# -*- coding: utf-8 -*-
"""منصّة وهميّة لتبويب «الكتب والأعمال» (قسم «الكتب»): فوق `D3Platform` بتضيف جسور هذا التبويب بحالتها —
قائمة أعمال السوق `/api/bridge/knowledge` (بحقول P1 أو من غيرها) · قوائم المراجعة `/api/bridge/knowledge/review` بالوثيقة الكاملة
(عشان الاختبار يثبّت إن النص الخاص ورابط الملف ما بيخرجوش) · كتب المتجر `/api/bridge/books/works` (P2) · مسارات الكتابة الأربعة الموجودة.

⛔ صفر شبكة: كله في الذاكرة. الأشكال بالحرف من `routes/admin_bridge.py` و`routes/knowledge.py` على المنصة (شُوهدت قراءةً فقط)،
والأسماء والأرقام مخترعة. الكتابة حالتها حقيقية والرفض بنفس رسائل المنصة العربية، فالواجهة بتتجرّب على ٤٢٢ و٤٠٩ فعلًا.

`p1 = True` ⇒ قائمة السوق فيها الحقول الجديدة (status · created_at · has_file · review_note · legacy_split · owner_pct · platform_pct).
`works = False` ⇒ جسر المتجر P2 غير مبني (٤٠٤). `store_open = False` ⇒ المتجر مقفول (الأسعار والعروض والطلبات والكتب ٤٠٤).
`write_log` = [(الوقت, method, path, body)] لكل نداء غير قراءة (حتى المرفوض)، و`forced[(method, path)] = (status, payload)` يفرض ردًّا.
"""
import copy
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import d3_fixtures as d3fx        # noqa: E402

iso = d3fx.iso
SECRET_TEXT = 'نص العمل الخاص — لا يخرج من المنصة أبدًا'


def _doc(i, title, **kw):
    d = {"id": i, "slug": "slug-" + i, "title": title, "type": "book", "description": "وصف " + title, "cover_url": "",
         "file_url": "https://files.example.test/%s.pdf" % i, "material_text": SECRET_TEXT, "owner_email": "mai@example.test", "owner_name": "أ. مي حسن",
         "rights": "owned_for_sale", "pricing": {"eg": {"amount": 150.0, "currency": "EGP", "label": ""}}, "bid_enabled": False,
         "segment_pricing_mode": "discount_only", "is_active": False, "total_acquired": 0, "status": "published", "review_note": "",
         "reviewed_by": "", "reviewed_at": "", "owns_it": True, "created_at": iso(-24 * 100), "updated_at": iso(-24 * 90)}
    d.update(kw)
    return d


def works():
    """اثنا عشر عملًا من السوق: ٣ في المراجعة (واحد بلا ملف) · ٥ ظاهرة · ٢ مخفية (أحدهما بيع منه) · ١ مرفوض · ١ ظاهر وجديد."""
    return [
        _doc("kn-1", "دليل صياغة العقود التجارية", status="pending_review", created_at=iso(-30), updated_at=iso(-30), owner_name="أ. مي حسن"),
        _doc("kn-2", "مذكرة دفاع في قضايا الإيجار", status="pending_review", file_url="", created_at=iso(-24 * 5), updated_at=iso(-24 * 5),
             owner_email="karim.l@example.test", owner_name="د. كريم لطفي"),
        _doc("kn-3", "قانون العمل: خلاصة للمبتدئين", status="pending_review", rights="public_domain_feed", pricing={}, type="guide", created_at=iso(-2), updated_at=iso(-2),
             owner_email="", owner_name="البروفيسور"),
        _doc("kn-4", "الوجيز في أحكام الشركات", status="published", is_active=True, total_acquired=12, pricing={"eg": {"amount": 250.0, "currency": "EGP", "label": ""}},
             created_at=iso(-24 * 100)),
        _doc("kn-5", "نماذج الإنذارات القانونية", status="published", is_active=True, total_acquired=0, created_at=iso(-24 * 45), type="guide"),
        _doc("kn-6", "نصوص قانون المرافعات", status="published", is_active=True, rights="public_domain_feed", pricing={}, total_acquired=31, type="other",
             owner_email="", owner_name="البروفيسور", created_at=iso(-24 * 200)),
        _doc("kn-7", "دليل التحكيم التجاري", status="published", is_active=False, total_acquired=4, pricing={"eg": {"amount": 320.0, "currency": "EGP", "label": ""}},
             created_at=iso(-24 * 150), type="research"),
        _doc("kn-8", "قضايا النفقة: أسئلة وأجوبة", status="published", is_active=False, total_acquired=0, created_at=iso(-24 * 20)),
        _doc("kn-9", "ملخص قانون الأحوال الشخصية", status="rejected", review_note="الملف المرفق ناقص الصفحات الأخيرة", created_at=iso(-24 * 12), updated_at=iso(-24 * 3)),
        _doc("kn-10", "صيغ الدعاوى المدنية", status="published", is_active=True, total_acquired=1, created_at=iso(-24 * 80)),
        _doc("kn-11", "بحث في حماية البيانات", status="published", is_active=True, rights="public_domain_feed", pricing={}, total_acquired=0, type="research",
             owner_email="", owner_name="البروفيسور", created_at=iso(-24 * 9)),
        _doc("kn-12", "عقود المقاولات خطوة بخطوة", status="published", is_active=True, total_acquired=2, pricing={"eg": {"amount": 180.0, "currency": "EGP", "label": ""}},
             created_at=iso(-24 * 60)),
    ]


STORE_ITEMS = [
    {"slug": "bk-tenant-guide", "title": "دليل المستأجر في عقود الإيجار", "source": "member", "type": "guide", "owner_email": "nadia@example.test", "owner_name": "أ. نادية فؤاد",
     "catalog_id": "bk-tenant-guide", "offer_id": "off-9", "plan": "ads", "plan_label": "النشر مع إعلانات على حسابك", "owner_pct": 65, "platform_pct": 35,
     "owners_total": 7, "paid_owners": 5, "by_version": {"read": 3, "pdf": 2}, "last_sold_at": iso(-30)},
    {"slug": "bk-startup-law", "title": "قانون الشركات الناشئة", "source": "ours", "type": "book", "owner_email": "", "owner_name": "البروفيسور", "catalog_id": None, "offer_id": None,
     "plan": None, "plan_label": "", "owner_pct": None, "platform_pct": None, "owners_total": 0, "paid_owners": 0, "by_version": {"read": 0, "pdf": 0}, "last_sold_at": None},
    {"slug": "bk-labor", "title": "الوجيز في قانون العمل", "source": "member", "type": "book", "owner_email": "hala@example.test", "owner_name": "د. هالة سمير",
     "catalog_id": "bk-labor", "offer_id": "off-10", "plan": "normal", "plan_label": "النشر على المنصة", "owner_pct": 60, "platform_pct": 40,
     "owners_total": 1, "paid_owners": 1, "by_version": {"read": 1, "pdf": 0}, "last_sold_at": iso(-100)},
    {"slug": "bk-hidden", "title": "أحكام الميراث بالأمثلة", "source": "member", "type": "book", "owner_email": "omar@example.test", "owner_name": "أ. عمر شريف",
     "catalog_id": "bk-hidden", "offer_id": "off-11", "plan": "normal", "plan_label": "النشر على المنصة", "owner_pct": 60, "platform_pct": 40,
     "owners_total": 2, "paid_owners": 2, "by_version": {"read": 0, "pdf": 2}, "last_sold_at": iso(-500)},
]

EXTRA_PRICES = {"bk-hidden": {"title": "أحكام الميراث بالأمثلة", "visible": False, "versions": {"read": {"eg": 140.0, "default": 8.0}, "pdf": {"eg": 200.0}}}}
EXTRA_OFFERS = [
    {"id": "off-9", "title": "دليل المستأجر في عقود الإيجار", "about": "", "type": "guide", "suggested_price": None, "owner_email": "nadia@example.test", "owner_name": "أ. نادية فؤاد",
     "status": "live", "submitted_at": iso(-24 * 30), "catalog_id": "bk-tenant-guide", "catalog_slug": "bk-tenant-guide",
     "agreement": {"plan": "ads", "plan_label": "النشر مع إعلانات على حسابك", "owner_pct": 65, "platform_pct": 35}},
    {"id": "off-10", "title": "الوجيز في قانون العمل", "about": "", "type": "book", "suggested_price": None, "owner_email": "hala@example.test", "owner_name": "د. هالة سمير",
     "status": "live", "submitted_at": iso(-24 * 40), "catalog_id": "bk-labor", "catalog_slug": "bk-labor",
     "agreement": {"plan": "normal", "plan_label": "النشر على المنصة", "owner_pct": 60, "platform_pct": 40}},
    {"id": "off-12", "title": "كتاب في التحكيم الرياضي", "about": "", "type": "book", "suggested_price": {"amount": 200.0, "currency": "EGP"}, "owner_email": "sami@example.test",
     "owner_name": "أ. سامي النجار", "status": "rejected", "submitted_at": iso(-24 * 6), "reviewed_at": iso(-24 * 2), "review_note": "الموضوع خارج تخصص المنصة",
     "agreement": {"plan": "normal", "plan_label": "النشر على المنصة", "owner_pct": 60, "platform_pct": 40}},
    {"id": "off-13", "title": "مسودة لم تُرسل", "about": "", "type": "book", "suggested_price": None, "owner_email": "x@example.test", "owner_name": "أ. خالد", "status": "draft",
     "submitted_at": iso(-24)},
]
INBOX_REVIEW_STATUS = ("pending_review", "rejected", "published")


class BooksPlatform(d3fx.D3Platform):
    def __init__(self, empty=False, p1=True, works_bridge=True, store_open=True, **kw):
        super(BooksPlatform, self).__init__(empty=empty, d2=kw.pop('d2', True), course_prices=kw.pop('course_prices', False), **kw)
        self.p1 = p1
        self.works_bridge = works_bridge
        self.store_open = store_open
        self.items = [] if empty else works()
        self.store = [] if empty else copy.deepcopy(STORE_ITEMS)
        self.write_log = []
        self.down_status = set()        # حالات قائمة المراجعة اللي ترد ٥٠٢ (مثلًا {'pending_review'})
        self.ingest = {"ok": True, "found": 7, "ingested": 5, "skipped": 2, "titles": []}
        if not empty:
            self.prices.update(copy.deepcopy(EXTRA_PRICES))
            self.offers.extend(copy.deepcopy(EXTRA_OFFERS))
        self.books = [i for i in self.items if i["status"] == "pending_review"]        # صفوف الوارد القديمة (نفس الوثائق)

    # ---------------------------------------------------------------- التسجيل
    def handle(self, method, path, params=None, body=None):
        if str(method).upper() != 'GET':
            self.write_log.append((time.time(), str(method).upper(), path, copy.deepcopy(body)))
        return super(BooksPlatform, self).handle(method, path, params, body)

    def _route(self, method, path, params, body):
        forced = self.forced.get((method.upper(), path))
        if forced is not None:
            return forced
        if path in self.down:
            return 502, {"detail": "تعذر الاتصال"}
        out = self._books(method.upper(), path, params, body)
        if out is not None:
            return out
        return super(BooksPlatform, self)._route(method, path, params, body)

    def _gated(self, path):
        return not self.store_open and (path.startswith("/api/bridge/prices/") or path.startswith("/api/bridge/book-") or path == "/api/bridge/books/works")

    # ---------------------------------------------------------------- الأشكال
    def _listed(self, d):
        eg = (d.get("pricing") or {}).get("eg") or (d.get("pricing") or {}).get("default") or {}
        out = {"id": d["id"], "slug": d["slug"], "title": d["title"], "type": d["type"], "owner_email": d["owner_email"], "owner_name": d["owner_name"],
               "rights": d["rights"], "is_active": bool(d["is_active"]), "bid_enabled": bool(d["bid_enabled"]), "price_amount": eg.get("amount"),
               "price_currency": eg.get("currency") or "", "total_acquired": int(d["total_acquired"] or 0)}
        if self.p1:
            out.update({"status": d["status"], "created_at": d["created_at"], "updated_at": d["updated_at"], "has_file": bool(str(d["file_url"]).strip()),
                        "review_note": d["review_note"]})
            if d["rights"] == "owned_for_sale":
                out.update({"legacy_split": True, "owner_pct": 80, "platform_pct": 20})
        return out

    def _item(self, item_id):
        return next((d for d in self.items if d["id"] == item_id), None)

    # ---------------------------------------------------------------- التوجيه
    def _books(self, method, path, params, body):
        if self._gated(path):
            return 404, {"detail": "Not Found"}
        if method == "GET" and path == "/api/bridge/knowledge":
            rows = [d for d in self.items if not (params or {}).get("rights") or d["rights"] == params["rights"]]
            return 200, {"items": [self._listed(d) for d in rows], "count": len(rows)}
        if method == "GET" and path == "/api/bridge/knowledge/review":
            st = (params or {}).get("status") or "pending_review"
            if st in self.down_status:
                return 502, {"detail": "تعذر الاتصال"}
            rows = [copy.deepcopy(d) for d in self.items if d["status"] == st]
            return 200, {"items": rows, "count": len(rows)}
        if method == "GET" and path == "/api/bridge/books/works":
            if not self.works_bridge:
                return 404, {"detail": "Not Found"}
            return 200, {"ok": True, "count": len(self.store), "items": copy.deepcopy(self.store)}
        if method == "PUT" and path.startswith("/api/bridge/knowledge/") and path.count("/") == 4:
            return self._update(path.rsplit("/", 1)[1], body or {})
        if method == "POST" and path.startswith("/api/bridge/knowledge/") and path.endswith("/decide"):
            return self._decide(path.split("/")[4], body or {})
        if method == "POST" and path == "/api/bridge/books":
            return self._create(body or {})
        if method == "POST" and path == "/api/bridge/library/ingest-drive-folder":
            if not str((body or {}).get("folder_id") or "").strip():
                return 422, {"detail": "folder_id مطلوب"}
            return 200, copy.deepcopy(self.ingest)
        return None

    def _update(self, item_id, body):
        d = self._item(item_id)
        if d is None:
            return 404, {"detail": "العنصر غير موجود"}
        patch = {}
        if isinstance(body.get("title"), str) and body["title"].strip():
            patch["title"] = body["title"].strip()
        if body.get("is_active") is not None:
            patch["is_active"] = bool(body["is_active"])
        if body.get("bid_enabled") is not None and d["rights"] == "owned_for_sale":
            patch["bid_enabled"] = bool(body["bid_enabled"])
        if body.get("price_egp") is not None and d["rights"] == "owned_for_sale":
            amount = float(body["price_egp"])
            if amount < 0:
                return 422, {"detail": "السعر لا يكون سالبًا"}
            patch["pricing"] = {"eg": {"amount": amount, "currency": "EGP", "label": ""}}
        if not patch:
            return 422, {"detail": "لا يوجد تغيير صالح"}
        d.update(patch)
        d["updated_at"] = iso(0)
        self._ok_write("PUT", "/api/bridge/knowledge/%s" % item_id, body)
        return 200, {"id": d["id"], "slug": d["slug"], "title": d["title"], "is_active": d["is_active"], "bid_enabled": d["bid_enabled"], "pricing": d["pricing"]}

    def _decide(self, item_id, body):
        d = self._item(item_id)
        if d is None:
            return 404, {"detail": "العنصر غير موجود"}
        if d["status"] != "pending_review":
            return 409, {"detail": "العمل ده اتحسم قبل كده"}
        approve = body.get("decision") == "approve"
        if approve and d["rights"] == "owned_for_sale" and not str(d["file_url"]).strip():
            return 422, {"detail": "لا يمكن اعتماد عمل للبيع بلا ملف مرفق"}
        d["status"] = "published" if approve else "rejected"
        d["is_active"] = approve
        d["review_note"] = "" if approve else str(body.get("note") or "")
        d["updated_at"] = iso(0)
        self.books = [i for i in self.items if i["status"] == "pending_review"]
        self._ok_write("POST", "/api/bridge/knowledge/%s/decide" % item_id, body)
        return 200, copy.deepcopy(d)

    def _create(self, body):
        if not str(body.get("title") or "").strip() or not str(body.get("file_url") or "").strip():
            return 422, {"detail": "العنوان ورابط الملف مطلوبان"}
        price = float(body.get("price") or 0)
        n = len(self.items) + 1
        d = _doc("kn-%d" % (100 + n), body["title"], status="published", is_active=bool(body.get("is_active", True)), created_at=iso(0), updated_at=iso(0),
                 owner_email="admin@local.test", owner_name="البروفيسور", file_url=body["file_url"],
                 rights="owned_for_sale" if price > 0 else "public_domain_feed",
                 pricing={"eg": {"amount": price, "currency": body.get("currency") or "EGP", "label": ""}} if price > 0 else {})
        self.items.insert(0, d)
        self._ok_write("POST", "/api/bridge/books", body)
        return 200, {"ok": True, "id": d["id"], "slug": d["slug"]}
