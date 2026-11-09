# -*- coding: utf-8 -*-
"""منصّة وهميّة لـ«سعر خاص لكل دليل» (عقد الجولة، 2026-11-02): فوق `D3Platform` بتغيّر جسر الأسعار للكتب بس:

  * القائمة `GET /api/bridge/prices/book` = صفوف الكتب (`group:"book"`) ثم صف السعر العام (`id:"_guides"`, `group:"guides_general"`)
    ثم صف لكل دليل (`group:"guide"`, `has_own`, `uses_general`).
  * `GET/PUT /api/bridge/prices/book/<slug الدليل>` بنفس سلوك الكتب (rev · confirmed:true · by)، ودليل بلا وثيقة خاصة يرد نموذجًا فاضيًا (rev ٠).
  * `DELETE /api/bridge/prices/book/<slug الدليل>` = «ارجع للسعر العام»: يحذف الوثيقة الخاصة ويكتب سطر سجل «removed».
    كتاب أو `_guides` ⇒ ٤٠٩. دليل بلا سعر خاص ⇒ ٤٠٩. rev قديم ⇒ ٤٠٩. بلا `confirmed:true` ⇒ ٤٢٢.

⛔ صفر شبكة: كله في الذاكرة. الأسماء والأرقام مخترعة.
`guide_min_effective = False` ⇒ صف الدليل الذي يأخذ العام يرد بلا `min_price` (الواجهة تعرض أقل سعر العام).
`forced[(method, path)] = (status, payload)` من الأب يفرض ردًّا.
"""
import copy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import d3_fixtures as d3fx          # noqa: E402

iso = d3fx.iso
COUNTRIES = d3fx.COUNTRIES
CURRENCIES = d3fx.CURRENCIES
GENERAL_TITLE = "السعر العام للأدلّة"

GUIDES = [
    ("guide-rent", "دليل عقد الإيجار السكني"),
    ("guide-sole", "دليل تأسيس شركة فردية"),
    ("guide-labor", "دليل عقد العمل للموظف"),
    ("guide-heirs", "دليل المواريث للأسرة"),
    ("guide-trademark", "دليل تسجيل العلامة التجارية"),
]

GENERAL_DOC = {"title": GENERAL_TITLE, "visible": True,
               "versions": {"read": {"eg": 99.0, "sa": 25.0, "default": 5.0}}}

GUIDE_OWN = {
    "guide-rent": {"visible": True, "versions": {"read": {"eg": 120.0, "sa": 30.0, "default": 7.0}}},
    "guide-heirs": {"visible": False, "versions": {"read": {"eg": 75.0, "default": 4.0}}},
}


class ItemPricesPlatform(d3fx.D3Platform):
    """`D3Platform` + جسر الأسعار الجديد للأدلّة. `price_log` = سطور السجل (تعديل/حذف) لكل دليل."""

    def __init__(self, empty=False, d2=False, course_prices=False, guide_min_effective=True, no_guides=False,
                 short_guides=(), min_words=None, sellers=None, **kw):
        super(ItemPricesPlatform, self).__init__(empty=empty, d2=d2, course_prices=course_prices, **kw)
        self.guide_min_effective = guide_min_effective
        # حد البيع (المنصة 2026-11-09): الأدلّة دي أقصر من الحد (source=short)، والباقي فوقه. `min_words` = guides_min_words.
        self.short_guides = set(short_guides)
        self.min_words = min_words
        # «الأسعار المبدئية»: {id الكتاب: seed|ours|catalog|expert} و`free` في نفس الصف لو القيمة "free".
        self.sellers = dict(sellers or {})
        self.guides = [] if (empty or no_guides) else list(GUIDES)
        self.general = None if empty else copy.deepcopy(GENERAL_DOC)
        self.guide_docs = {} if (empty or no_guides) else {k: dict(copy.deepcopy(v), title=dict(GUIDES)[k]) for k, v in GUIDE_OWN.items()}
        self.price_log = []

    # ---------------------------------------------------------------- مساعدات
    def _titles(self):
        return dict(self.guides)

    def _merged(self):
        docs = dict(self.prices)
        if self.general is not None:
            docs["_guides"] = self.general
        docs.update(self.guide_docs)
        return docs

    def _docs(self, kind):
        return self._merged() if kind == "book" else self.course_docs

    @staticmethod
    def _mins(view):
        mins = {}
        for row in view["versions"].values():
            for c, e in row.items():
                if c not in mins or e["amount"] < mins[c]["amount"]:
                    mins[c] = dict(e)
        return {c: mins[c] for c in COUNTRIES if c in mins}

    def _has_prices(self, doc):
        return bool(doc and doc.get("versions") and any(doc["versions"].values()))

    def _row(self, iid, doc, group, **extra):
        v = self._view("book", iid)
        row = {"id": iid, "title": doc["title"], "group": group, "visible": v["visible"], "has_prices": doc.get("versions") is not None,
               "min_price": self._mins(v), "updated_at": v["updated_at"] or None}
        row.update(extra)
        return row

    def _list(self):
        items = []
        for iid, d in self.prices.items():
            row = self._row(iid, d, "book")
            if iid in self.sellers:
                sv = self.sellers[iid]
                row.update({"seller": "catalog" if sv == "free" else sv, "free": sv == "free"})
            items.append(row)
        if self.general is not None:
            items.append(self._row("_guides", self.general, "guides_general"))
        for slug, title in self.guides:
            own = self.guide_docs.get(slug)
            has_own = self._has_prices(own)
            words = (1200 if slug in self.short_guides else 5200) if self.min_words else None
            if has_own:
                row = self._row(slug, own, "guide", has_own=True, uses_general=False)
            elif slug in self.short_guides:
                row = {"id": slug, "title": title, "group": "guide", "visible": False, "has_prices": False, "min_price": {},
                       "updated_at": None, "has_own": bool(own), "uses_general": False, "source": "short"}
            else:
                gen = self._row("_guides", self.general, "guides_general") if self.general is not None else {"visible": False, "min_price": {}, "updated_at": None}
                row = {"id": slug, "title": title, "group": "guide", "visible": gen["visible"], "has_prices": self._has_prices(self.general),
                       "min_price": gen["min_price"] if self.guide_min_effective else {}, "updated_at": gen["updated_at"],
                       "has_own": bool(own), "uses_general": True}
            if words is not None:
                row["words"] = words
            items.append(row)
        out = {"ok": True, "kind": "book", "countries": COUNTRIES, "currencies": CURRENCIES, "count": len(items), "items": items}
        if self.min_words:
            out["guides_min_words"] = self.min_words
        return out

    # ---------------------------------------------------------------- الأسعار
    def _prices(self, method, kind, item_id, body):
        if kind != "book":
            return super(ItemPricesPlatform, self)._prices(method, kind, item_id, body)
        if item_id is None and method == "GET":
            return 200, self._list()
        titles = self._titles()
        if item_id in titles and item_id not in self.guide_docs:
            # دليل بلا وثيقة خاصة: GET ⇒ نموذج فاضي، PUT ⇒ ينشئ الوثيقة ثم يكمل كالكتب
            if method == "GET":
                return 200, {"ok": True, "countries": COUNTRIES, "currencies": CURRENCIES, "versions_allowed": ["read"],
                             "prices": {"kind": "book", "id": item_id, "title": titles[item_id], "visible": False, "versions": {},
                                        "updated_at": "", "updated_by": "", "rev": 0, "history": []}}
            if method == "PUT":
                self.guide_docs[item_id] = {"title": titles[item_id], "visible": False, "versions": None, "rev": 0}
        if method == "DELETE" and item_id is not None:
            return self._reset_to_general(item_id, body)
        out = super(ItemPricesPlatform, self)._prices(method, kind, item_id, body)
        if method == "GET" and out and out[0] == 200 and (item_id in titles or item_id == "_guides"):
            out[1]["versions_allowed"] = ["read"]                # المنصة: الأدلّة والسعر العام قراءة فقط (books_bridge._sells_read_only)
        if method == "PUT" and item_id in titles and out and out[0] != 200 and not self._has_prices(self.guide_docs.get(item_id)):
            self.guide_docs.pop(item_id, None)          # PUT فاشل على دليل جديد ما يترك وثيقة فاضية
        if method == "PUT" and out and out[0] == 200 and item_id in titles:
            self.price_log.append({"op": "update", "id": item_id, "by": body.get("by"), "note": body.get("note") or ""})
        return out

    def _reset_to_general(self, item_id, body):
        if item_id not in self._titles():
            return 409, {"detail": "الرجوع للسعر العام للأدلّة فقط"}
        if body.get("confirmed") is not True:
            return 422, {"detail": "لازم تأكيد التعديل الأول"}
        if not str(body.get("by") or "").strip():
            return 422, {"detail": "لازم نعرف مين اللي بيعدّل"}
        doc = self.guide_docs.get(item_id)
        if not doc:
            return 409, {"detail": "الدليل ده بياخد السعر العام أصلًا"}
        if body.get("rev") is not None and body["rev"] != doc.get("rev", 1):
            return 409, {"detail": "الأسعار اتعدّلت من مكان تاني — حدّث الصفحة وجرّب تاني"}
        self._ok_write("DELETE", "/api/bridge/prices/book/%s" % item_id, body)
        self.price_log.append({"op": "removed", "id": item_id, "by": body["by"], "note": body.get("note") or "",
                               "old_versions": copy.deepcopy(doc.get("versions"))})
        del self.guide_docs[item_id]
        return 200, {"ok": True, "id": item_id, "removed": True, "uses_general": True}
