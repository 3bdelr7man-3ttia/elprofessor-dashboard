# -*- coding: utf-8 -*-
"""منصّة وهميّة لـ«السوق v4» في الداشبورد (docs/v2/market4/SPEC.md): فوق `MarketPlatform` و`D3Platform` (النسب) بتضيف جسور
`docs/MARKET4-API.md` على المنصة (§٨ و§٢٢.٥ و§٢٣) بأشكالها بالحرف:

  GET  /api/bridge/market/suggestions?status=       POST /api/bridge/market/suggestions/{id}/decide
  GET  /api/bridge/market/catalog?no_range=1&q=      PUT  /api/bridge/market/catalog/{slug}/anchor
  GET  /api/bridge/market/orgs?status=               POST /api/bridge/market/orgs/{id}/verify-reg
  GET  /api/bridge/market/requests   (صفوفها فيها service_slug · service_name · applicable_country · offer_count · attachment_count · attachment_access_count)
  GET  /api/bridge/market/licence-files/{file_id}    (بايتات صورة)
  POST /api/bridge/join-requests/{id}/decide         (licensed_countries ⇒ ٤٢٢ لو بلد مش مفهوم)
  GET|PUT /api/bridge/shares                         (فيها `market.ladder_by_currency` وأرضية ٢٥)

⛔ صفر شبكة: كله في الذاكرة. الكتابة حالتها حقيقية والرفض بنفس رسائل المنصة العربية. `writes` = [(method, path, body)].
`down = {path}` ⇒ ٥٠٢ · `m4_missing = {path}` ⇒ ٤٠٤ · `forced[(method, path)] = (status, payload)` يفرض ردًّا.
"""
import copy
import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import market_fixtures as mfx      # noqa: E402
import d3_fixtures as d3fx         # noqa: E402

iso = mfx.iso
NOT_FOUND = {"detail": "Not Found"}
CURRENCIES = ["EGP", "SAR", "AED", "QAR", "KWD", "OMR", "USD"]
SERVICE_TYPES = ["contract_review", "contract_draft", "memo", "objection", "legal_research", "written_opinion", "case_review",
                 "company_setup", "compliance", "thesis_review", "filing_prep", "training"]
SPECIALTIES = ["civil", "criminal", "commercial", "labor", "family", "administrative", "constitutional", "real_estate", "arbitration",
               "ip", "tax", "banking", "compliance", "corporate", "practice_skills", "general"]
SPEC_AR = {"civil": "مدني وتعويضات", "criminal": "جنائي", "commercial": "تجاري وشركات", "labor": "عمل وتأمينات", "family": "أحوال شخصية وميراث",
           "administrative": "إداري ومناقصات", "constitutional": "دستوري وحقوق", "real_estate": "عقاري وتوثيق", "arbitration": "تحكيم وتسوية منازعات",
           "ip": "ملكية فكرية وتقنية", "tax": "ضرائب وجمارك", "banking": "مصرفي وتمويل", "compliance": "امتثال وحوكمة", "corporate": "تجاري وشركات",
           "practice_skills": "مهارات المهنة وإدارة المكتب", "general": "عام/غير محدد"}
KNOWN_COUNTRIES = {"EG", "SA", "AE", "QA", "KW", "OM", "BH", "JO", "IQ", "LB", "PS", "SY", "YE", "LY", "TN", "DZ", "MA", "SD", "XX"}
LICENCE_FILE_ID = "lf-3c9a41d2-7b05-4e88-a1f0"
LICENCE_URL = "https://api.elprofessor.net/api/bridge/market/licence-files/" + LICENCE_FILE_ID
MARKET_FLOOR = 25

SUGGESTIONS = [
    {"id": "sg-1", "user_email": "lawyer.hala@example.test", "org_id": None, "name": "ترجمة وثائق قانونية", "note": "ترجمة العقود والأحكام من العربية إلى الإنجليزية وبالعكس، مع مراجعة لغوية يعتمدها محامٍ.",
     "status": "pending", "created_slug": None, "decided_by": "", "decided_at": "", "created_at": iso(-3)},
    {"id": "sg-2", "user_email": "faisal.office@example.test", "org_id": "org-1", "name": "صياغة اللوائح الداخلية للشركات", "note": "لوائح الموارد البشرية والجزاءات وسياسة الإجازات للشركات الصغيرة.",
     "status": "pending", "created_slug": None, "decided_by": "", "decided_at": "", "created_at": iso(-20)},
    {"id": "sg-3", "user_email": "nadia.f@example.test", "org_id": None, "name": "تسجيل علامة تجارية", "note": "",
     "status": "pending", "created_slug": None, "decided_by": "", "decided_at": "", "created_at": iso(-52)},
    {"id": "sg-4", "user_email": "maha.s@example.test", "org_id": None, "name": "مراجعة عقود الامتياز التجاري", "note": "عقود الفرنشايز بين صاحب العلامة والفرع، وبنود الرسوم والتجديد.",
     "status": "pending", "created_slug": None, "decided_by": "", "decided_at": "", "created_at": iso(-90)},
    {"id": "sg-5", "user_email": "amr.q@example.test", "org_id": None, "name": "توثيق عقود الزواج", "note": "", "status": "approved", "created_slug": "svc-4f1a9c2e",
     "decided_by": "founder@example.test", "decided_at": iso(-70), "created_at": iso(-200)},
    {"id": "sg-6", "user_email": "rania.k@example.test", "org_id": None, "name": "خدمة غير واضحة", "note": "", "status": "rejected", "created_slug": None,
     "decided_by": "founder@example.test", "decided_at": iso(-100), "created_at": iso(-300)},
]


def _item(slug, name, stype, spec, mode="quote", licensed=False, rng=None):
    return {"slug": slug, "name": name, "service_type": stype, "specialty": spec, "specialty_label": SPEC_AR[spec], "pricing_mode": mode,
            "licensed": licensed, "status": "active", "anchor_range": rng, "has_range": bool(rng)}


CATALOG = [
    _item("legal-research", "بحث قانوني مسنَد", "legal_research", "general"),
    _item("contract-review", "مراجعة عقد تجاري", "contract_review", "commercial", rng={"EGP": [2500, 6000], "SAR": [400, 1100], "USD": [80, 220]}),
    _item("contract-draft", "صياغة عقد شراكة", "contract_draft", "commercial"),
    _item("memo-defence", "مذكرة دفاع جنائية", "memo", "criminal", licensed=True),
    _item("objection-appeal", "لائحة استئناف مدني", "objection", "civil", licensed=True, rng={"EGP": [3000, 7500], "SAR": [500, 1300]}),
    _item("company-setup", "تأسيس شركة ذات مسؤولية محدودة", "company_setup", "commercial"),
    _item("compliance-policies", "مراجعة سياسات الامتثال", "compliance", "compliance"),
    _item("thesis-review", "مراجعة رسالة ماجستير قانونية", "thesis_review", "general", rng={"EGP": [1500, 9000]}),
    _item("labor-dispute", "نزاع عمل وتعويض فصل", "case_review", "labor"),
    _item("tax-opinion", "رأي ضريبي لمسألة محددة", "written_opinion", "tax"),
    _item("ip-registration", "تسجيل علامة تجارية", "filing_prep", "ip"),
    _item("training-workshop", "ورشة مخصّصة لفريق قانوني", "training", "practice_skills"),
    _item("family-opinion", "رأي في مسألة أحوال شخصية", "written_opinion", "family", mode="fixed"),
    _item("rent-opinion", "رأي في عقد إيجار", "written_opinion", "real_estate", mode="fixed"),
]

ORGS = [
    {"id": "org-1", "name": "مكتب النور للمحاماة", "city": "القاهرة", "country": "EG", "founded_year": 2011, "status": "pending", "created_at": iso(-30),
     "commercial_reg": {"url": "https://files.example.test/regs/nour-2011.pdf", "verified_by": "", "verified_at": ""},
     "members": [{"email": "noor.admin@example.test", "role": "admin", "verified_lawyer": True}, {"email": "lawyer.a@example.test", "role": "lawyer", "verified_lawyer": True},
                 {"email": "lawyer.b@example.test", "role": "lawyer", "verified_lawyer": False}], "badge": False},
    {"id": "org-2", "name": "مكتب الفاروق وشركاه", "city": "الرياض", "country": "SA", "founded_year": 2018, "status": "pending", "created_at": iso(-70),
     "commercial_reg": {"url": "https://files.example.test/regs/farouq.png", "verified_by": "", "verified_at": ""},
     "members": [{"email": "farouq@example.test", "role": "admin", "verified_lawyer": True}, {"email": "lawyer.c@example.test", "role": "lawyer", "verified_lawyer": True}], "badge": False},
    {"id": "org-3", "name": "مكتب الأفق القانوني", "city": "الإسكندرية", "country": "EG", "founded_year": 2020, "status": "pending", "created_at": iso(-5),
     "commercial_reg": None, "members": [{"email": "ofoq@example.test", "role": "admin", "verified_lawyer": False}], "badge": False},
    {"id": "org-4", "name": "مكتب السلام", "city": "عمّان", "country": "JO", "founded_year": None, "status": "suspended", "created_at": iso(-400),
     "commercial_reg": {"url": "https://files.example.test/regs/salam.pdf", "verified_by": "", "verified_at": ""}, "members": [], "badge": False},
]

# رقم v4 الإضافي في صفوف الطلبات: (service_slug, service_name, applicable_country, attachment_count, attachment_access_count)
V4_ROWS = {
    "mk-n1": ("contract-review", "مراجعة عقد تجاري", "EG", 2, 3),
    "mk-n2": ("memo-defence", "مذكرة دفاع جنائية", "SA", 0, 0),
    "mk-w2": ("contract-draft", "صياغة عقد شراكة", "AE", 1, 0),
    "mk-w5": ("", "", "", 0, 0),
    "mk-w9": ("company-setup", "تأسيس شركة ذات مسؤولية محدودة", "QA", 3, 7),
    "mk-o1": ("company-setup", "تأسيس شركة ذات مسؤولية محدودة", "EG", 1, 1),
    "mk-o2": ("legal-research", "بحث قانوني مسنَد", "KW", 0, 0),
    "mk-w11": ("labor-dispute", "نزاع عمل وتعويض فصل", "OM", 2, 2),
}

JOINS = [
    {"id": "jr-lic-1", "status": "pending", "section": "lawyer_offers", "section_label": "محامٍ معتمد", "user_name": "أ. هبة الجندي", "user_email": "heba.g@example.test",
     "submitted_at": iso(-6), "note": "محامية بالنقض، أترافع في القضايا التجارية والمدنية.", "service_label": "مرافعة أمام المحاكم", "licensed": True,
     "licensed_family": "litigation", "licence_missing": False, "licence_note": "", "status_label": "بانتظار القرار", "info_request": "",
     "attachments": [LICENCE_URL], "granted_services": [], "catalog_services": ["memo-defence"],
     "answers": {"capacity": "محامية", "bar_number": "١٢٣٤٥", "licence_country": "SA", "licence": LICENCE_URL}},
    {"id": "jr-lic-2", "status": "pending", "section": "lawyer_offers", "section_label": "محامٍ معتمد", "user_name": "أ. ميشيل كوستا", "user_email": "michel.k@example.test",
     "submitted_at": iso(-30), "note": "", "service_label": "توثيق العقود", "licensed": True, "licensed_family": "notarization", "licence_missing": False, "licence_note": "",
     "status_label": "بانتظار القرار", "info_request": "", "attachments": [], "granted_services": [], "catalog_services": [],
     "answers": {"capacity": "موثّق", "bar_number": "٩٨٧٦", "licence_country": "XX", "licence_country_name": "قبرص"}},
    {"id": "jr-plain", "status": "pending", "section": "expert_offers", "section_label": "خبير معتمد", "user_name": "أ. مها الشريف", "user_email": "maha@example.test",
     "submitted_at": iso(-20), "note": "أقدّم مراجعة عقود تجارية.", "service_label": "مراجعة العقود التجارية", "licensed": False, "licensed_family": "", "licence_missing": False,
     "licence_note": "", "status_label": "بانتظار القرار", "info_request": "", "attachments": [], "granted_services": [], "catalog_services": ["contract-review"],
     "answers": {"capacity": "خبيرة", "done_before": "نعم، أكثر من ٣٠ مرة"}},
]

SHARES_MARKET = {"ladder_by_currency": {
    "EGP": [{"max": 10000, "platform_pct": 35}, {"max": 30000, "platform_pct": 30}, {"max": None, "platform_pct": 25}],
    "SAR": [{"max": 750, "platform_pct": 35}, {"max": 2250, "platform_pct": 30}, {"max": None, "platform_pct": 25}],
    "AED": [{"max": 750, "platform_pct": 35}, {"max": 2250, "platform_pct": 30}, {"max": None, "platform_pct": 25}],
    "QAR": [{"max": 750, "platform_pct": 35}, {"max": 2250, "platform_pct": 30}, {"max": None, "platform_pct": 25}],
    "KWD": [{"max": 60, "platform_pct": 35}, {"max": 180, "platform_pct": 30}, {"max": None, "platform_pct": 25}],
    "OMR": [{"max": 75, "platform_pct": 35}, {"max": 225, "platform_pct": 30}, {"max": None, "platform_pct": 25}],
    "USD": [{"max": 200, "platform_pct": 35}, {"max": 600, "platform_pct": 30}, {"max": None, "platform_pct": 25}]}}


def licence_png():
    """صورة بطاقة قيد وهمية (بلا نص حقيقي): مستطيل بخط وشعار، من PIL لو موجودة وإلا بايتات PNG صغيرة صالحة."""
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (720, 440), "#F6F1EA")
        d = ImageDraw.Draw(im)
        d.rectangle([14, 14, 705, 425], outline="#9E2B4E", width=6)
        d.rectangle([14, 14, 705, 96], fill="#9E2B4E")
        d.ellipse([60, 140, 200, 280], outline="#9E2B4E", width=6)
        d.ellipse([90, 170, 170, 250], fill="#E9D5DC")
        for i, w in enumerate((380, 330, 400, 260)):
            d.rounded_rectangle([250, 150 + i * 44, 250 + w, 176 + i * 44], radius=8, fill="#D9CFC0")
        d.rectangle([60, 330, 200, 360], fill="#D9CFC0")
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()
    except Exception:   # noqa: BLE001
        import base64
        return base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAHnOcQAAAAABJRU5ErkJggg==")


class Market4Platform(mfx.MarketPlatform, d3fx.D3Platform):
    def __init__(self, empty=False, **kw):
        super(Market4Platform, self).__init__(empty=empty, **kw)
        self.m4_missing = set()
        self.suggestions = [] if empty else copy.deepcopy(SUGGESTIONS)
        self.catalog = [] if empty else copy.deepcopy(CATALOG)
        self.orgs = [] if empty else copy.deepcopy(ORGS)
        self.joins = [] if empty else copy.deepcopy(JOINS)
        self.file_png = licence_png()
        self.file_missing = False
        self.shares["market"] = copy.deepcopy(SHARES_MARKET)
        if not empty:
            for r in self.rows:
                slug, name, country, files, seen = V4_ROWS.get(r["id"], ("", "", "", 0, 0))
                r.update({"service_slug": slug, "service_name": name, "applicable_country": country, "attachment_count": files, "attachment_access_count": seen})

    # ---------------------------------------------------------------- التوجيه
    def _route(self, method, path, params, body):
        m = method.upper()
        forced = self.forced.get((m, path))
        if forced is not None:
            return forced
        if path in self.down:
            return 502, {"detail": "تعذر الاتصال"}
        if path in self.m4_missing:
            return 404, NOT_FOUND
        out = self._m4(m, path, params or {}, body or {})
        if out is not None:
            return out
        return super(Market4Platform, self)._route(method, path, params, body)

    @staticmethod
    def _by(body):
        return None if str(body.get("by") or "").strip() else (422, {"detail": "لازم نعرف مين اللي بيقرّر"})

    def _m4(self, m, path, params, body):
        if path == "/api/bridge/market/suggestions" and m == "GET":
            st = params.get("status") or "pending"
            rows = [r for r in self.suggestions if st == "all" or r["status"] == st]
            return 200, {"items": copy.deepcopy(rows), "total": len(rows), "pending": sum(1 for r in self.suggestions if r["status"] == "pending"), "status": st}
        mm = re.match(r"^/api/bridge/market/suggestions/([^/]+)/decide$", path)
        if mm and m == "POST":
            return self._decide(mm.group(1), body)
        if path == "/api/bridge/market/catalog" and m == "GET":
            return self._catalog(params)
        mm = re.match(r"^/api/bridge/market/catalog/([^/]+)/anchor$", path)
        if mm and m == "PUT":
            return self._anchor(mm.group(1), body)
        if path == "/api/bridge/market/orgs" and m == "GET":
            st = params.get("status") or "pending"
            rows = [r for r in self.orgs if st == "all" or r["status"] == st]
            return 200, {"items": copy.deepcopy(rows), "total": len(rows), "status": st}
        mm = re.match(r"^/api/bridge/market/orgs/([^/]+)/verify-reg$", path)
        if mm and m == "POST":
            return self._verify(mm.group(1), body)
        mm = re.match(r"^/api/bridge/market/licence-files/([^/]+)$", path)
        if mm and m == "GET":
            if self.file_missing or mm.group(1) != LICENCE_FILE_ID:
                return 404, {"detail": "الملف مش موجود"}
            return 200, (self.file_png, "image/png")
        mm = re.match(r"^/api/bridge/join-requests/([^/]+)/decide$", path)
        if mm and m == "POST":
            return self._join_decide(mm.group(1), body)
        return None

    def _decide(self, sid, body):
        bad = self._by(body)
        if bad:
            return bad
        cur = next((r for r in self.suggestions if r["id"] == sid), None)
        if cur is None:
            return 404, {"detail": "الاقتراح مش موجود"}
        dec = body.get("decision")
        if dec not in ("approve", "reject"):
            return 422, {"detail": "decision غير صالح"}
        stype = (body.get("service_type") or "").strip() or "written_opinion"
        spec = (body.get("specialty") or "").strip() or "general"
        if dec == "approve" and (stype not in SERVICE_TYPES or spec not in SPECIALTIES):
            return 422, {"detail": "نوع الخدمة أو التخصص غير معروف"}
        if cur["status"] != "pending":
            return 409, {"detail": "اتقرّر في الاقتراح ده قبل كده"}
        self.writes.append(("POST", "/api/bridge/market/suggestions/%s/decide" % sid, copy.deepcopy(body)))
        cur["status"] = "approved" if dec == "approve" else "rejected"
        cur["decided_by"], cur["decided_at"] = body["by"], iso(0)
        if dec == "reject":
            return 200, {"ok": True, "status": "rejected"}
        slug = "svc-%08x" % (0xA1B2C3D4 + len(self.catalog))
        cur["created_slug"] = slug
        self.catalog.append(_item(slug, cur["name"], stype, spec))
        return 200, {"ok": True, "status": "approved", "slug": slug, "claimed": True}

    def _catalog(self, params):
        q = (params.get("q") or "").strip()
        rows = [r for r in self.catalog if not q or q in r["name"]]
        total_no = sum(1 for r in self.catalog if r["pricing_mode"] == "quote" and not r["anchor_range"])
        if str(params.get("no_range") or "").lower() in ("1", "true"):
            rows = [r for r in rows if r["pricing_mode"] == "quote" and not r["anchor_range"]]
        return 200, {"items": copy.deepcopy(rows[:int(params.get("limit") or 300)]), "total": len(rows), "currencies": list(CURRENCIES), "no_range_count": total_no}

    def _anchor(self, slug, body):
        bad = self._by(body)
        if bad:
            return bad
        if "anchor_range" not in body:
            return 422, {"detail": "anchor_range مطلوب (أو null لمسحه)"}
        row = next((r for r in self.catalog if r["slug"] == slug), None)
        if row is None:
            return 404, {"detail": "الخدمة مش في الكتالوج"}
        rng = body["anchor_range"]
        out = {}
        if rng is not None:
            for k, v in rng.items():
                k = k.upper()
                if k not in CURRENCIES:
                    return 422, {"detail": "عملة غير معروفة"}
                if v is None:
                    continue
                if (not isinstance(v, list) or len(v) != 2 or any(isinstance(x, bool) or not isinstance(x, int) for x in v)):
                    return 422, {"detail": "%s: أرقام صحيحة بس، الأدنى والأعلى معًا" % k}
                if v[0] < 0 or v[0] >= v[1]:
                    return 422, {"detail": "%s: الأدنى لازم يكون أقل من الأعلى" % k}
                out[k] = v
        if row["pricing_mode"] == "fixed":
            return 409, {"detail": "الخدمة دي مالهاش مدى سعر"}
        self.writes.append(("PUT", "/api/bridge/market/catalog/%s/anchor" % slug, copy.deepcopy(body)))
        row["anchor_range"] = out or None
        row["has_range"] = bool(out)
        return 200, {"ok": True, "slug": slug, "anchor_range": copy.deepcopy(row["anchor_range"])}

    def _verify(self, oid, body):
        bad = self._by(body)
        if bad:
            return bad
        org = next((r for r in self.orgs if r["id"] == oid), None)
        if org is None:
            return 404, {"detail": "المكتب مش موجود"}
        reg = org.get("commercial_reg")
        if not (reg and reg.get("url")):
            return 422, {"detail": "المكتب لم يرفع سجله التجاري بعد"}
        self.writes.append(("POST", "/api/bridge/market/orgs/%s/verify-reg" % oid, copy.deepcopy(body)))
        if reg.get("verified_at"):
            return 200, {"ok": True, "already": True, "status": org["status"]}
        reg["verified_by"], reg["verified_at"] = body["by"], iso(0)
        if org["status"] == "pending":
            org["status"] = "active"
        return 200, {"ok": True, "already": False, "status": org["status"], "verified_at": reg["verified_at"]}

    def _join_decide(self, jid, body):
        row = next((r for r in self.joins if r["id"] == jid), None)
        if row is None:
            return 404, {"detail": "Join request not found"}
        if body.get("decision") == "approve":
            for c in body.get("licensed_countries") or []:
                if str(c).upper() not in KNOWN_COUNTRIES:
                    return 422, {"detail": "بلد القيد غير مفهوم — اكتب رمز البلد (مثل EG أو SA)"}
        self.writes.append(("POST", "/api/bridge/join-requests/%s/decide" % jid, copy.deepcopy(body)))
        self.joins = [r for r in self.joins if r["id"] != jid]
        return 200, {"ok": True}

    # ---------------------------------------------------------------- النسب: سلّم السوق وأرضية ٢٥
    def _shares(self, method, path, body):
        if method == "PUT":
            mk = ((body or {}).get("changes") or {}).get("market")
            if mk:
                for cur, ladder in ((mk.get("ladder_by_currency") or {}).items()):
                    for step in ladder:
                        if step.get("platform_pct", 100) < MARKET_FLOOR:
                            return 422, {"detail": "نصيب المنصّة في السوق ما ينزلش عن %s٪" % MARKET_FLOOR}
        before = copy.deepcopy(self.shares.get("market"))
        out = d3fx.D3Platform._shares(self, method, path, body)
        if method == "PUT" and out and out[0] == 200 and self.shares_log:
            self.shares_log[0]["before"]["market"] = before
            self.shares_log[0]["after"]["market"] = copy.deepcopy(self.shares.get("market"))
            out = (200, dict(out[1], history=copy.deepcopy(self.shares_log)))
        return out
