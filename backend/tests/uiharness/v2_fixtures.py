# -*- coding: utf-8 -*-
"""منصّة وهميّة للّوحة الجديدة (D1): فوق `EFPlatform` (ملف للخبير: الجولات ٦–١٤) بتضيف باقي الجسور اللي بتقراها اللوحة —
سحوبات الأرباح (مع settle/reject بنفس أخطاء المنصة) · الإيصالات · المدرّبين · الزوّار · الدعوات · الخبراء المؤسسين · طلبات
الانضمام · الكتب · السوق — وطابور فيه رقم في كل مربّع.

⛔ صفر شبكة: كله في الذاكرة. الأشكال بالحرف من `fake_platform.py` ومن جسور المنصة؛ الأسماء والأرقام مخترعة.
المرشّحين بيتزوّدوا بحقول `_candidates` الحقيقية (`eligible` · `auto_pick` · `load` · `same_specialty`) عشان بطاقة
«أرسله إلى …» تتبني من نفس الشكل اللي المنصة بتبعته.
"""
import copy
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ef_fixtures as fx          # noqa: E402
import fake_platform as fp        # noqa: E402

iso = fx.iso

PAYOUT_OK = {
    "id": "po-1", "user_email": "hala@example.test", "user_name": "د. هالة سمير", "user_phone": "01000000001",
    "amount": 1200.0, "currency": "EGP", "status": "pending", "method": "إنستاباي", "destination": "hala@instapay",
    "reason": "طلب سحب", "created_at": iso(-9), "age_hours": 9.0, "fx_alert": False,
}
PAYOUT_FX = {
    "id": "po-2", "user_email": "faisal@experts.test", "user_name": "أ. فيصل العتيبي", "user_phone": "0500000000",
    "amount": 3500.0, "currency": "SAR", "status": "pending", "method": "تحويل بنكي", "destination": "SA03 8000 0000 6080 1016 7519",
    "reason": "طلب سحب", "created_at": iso(-30), "age_hours": 30.0, "fx_alert": True,
}

JOIN_REQUESTS = {"requests": [
    {"id": "jr-1", "status": "pending", "section": "expert_offers", "section_label": "خبير معتمد",
     "user_name": "أ. مها الشريف", "user_email": "maha@example.test", "submitted_at": iso(-20),
     "note": "محامية بالنقض، أقدّم مراجعة عقود تجارية.", "service_label": "مراجعة العقود التجارية",
     "licensed": True, "licence_missing": False, "licence_note": "", "status_label": "بانتظار القرار",
     "attachments": ["https://example.test/licence.pdf"], "answers": {}},
]}

BOOKS_REVIEW = {"items": [
    {"id": "kb-1", "title": "دليل المستأجر في عقود الإيجار", "owner_name": "أ. نادية فؤاد", "owner_email": "nadia@example.test",
     "file_url": "https://example.test/book.pdf"},
]}

TOPICS_PENDING = {"topics": [
    {"id": "tp-1", "title": "هل يجوز إنهاء العقد قبل مدته؟", "summary": "سؤال من عضو عن الإنهاء المبكر لعقد إيجار.",
     "category": "عقود"},
]}

LEADS = {"leads": [
    {"id": "ld-1", "name": "سلمى منصور", "need": "تسأل عن استشارة في نفقة الصغير ومستعجلة.", "email": "salma.m@example.test"},
]}

MARKET = {"items": [
    {"id": "mk-1", "kind": "request", "title": "أحتاج مراجعة عقد شراكة", "status": "open", "offer_count": 0,
     "created_at": iso(-26), "need_kind": "consult", "member_alias": "عضو ٤٢"},
    {"id": "mk-2", "kind": "request", "title": "صياغة إنذار على يد محضر", "status": "open", "offer_count": 0,
     "created_at": iso(-6), "need_kind": "consult", "member_alias": "عضو ٧"},
    {"id": "mk-3", "kind": "request", "title": "استشارة ضريبية", "status": "open", "offer_count": 2,
     "created_at": iso(-3), "need_kind": "consult", "member_alias": "عضو ١٢"},
], "total": 3, "counts": {"by_lane": {}, "by_need_kind": {}, "by_status": {"open": 3}}}

STUCK = copy.deepcopy(fp.QUEUE["stuck_card_payments"])


def enrich_candidates(files):
    """يزوّد `candidates` بحقول `_candidates` الحقيقية: التخصص · الحمل · الأهلية · `auto_pick` على أول مؤهّل."""
    loads = {"hala@experts.test": 2, "nada@experts.test": 0, "karim@experts.test": 4, "sami@experts.test": 1,
             "faisal@experts.test": 3}
    for f in files:
        cands = f.get("candidates")
        if not isinstance(cands, list) or not cands:
            continue
        # الحالي: المختار (قبل الاستلام) أو اللي شغّال على الملف (بعد الاستلام) — مش مؤهَّل ليه تاني.
        current = f.get("assigned_to") if f.get("status") == "assigned" else f.get("expert_email")
        first = True
        for c in cands:
            email = c.get("email")
            prof = fx.EXPERT_PROFILES.get(email, {})
            available = c.get("available", prof.get("available", True)) is not False
            c.setdefault("available", available)
            c["current"] = bool(current and email == current)
            c.setdefault("previous", False)
            c["same_specialty"] = bool(f.get("specialty") and f.get("specialty") in (c.get("specialties") or prof.get("specialties") or []))
            c["load"] = loads.get(email, 0)
            c["eligible"] = bool(available and not c.get("declined") and not c["current"])
            c["auto_pick"] = bool(c["eligible"] and first)
            first = first and not c["eligible"]
    return files


class V2Platform(fx.EFPlatform):
    """`EFPlatform` + باقي جسور اللوحة. `forced[(method, path)] = (status, payload)` يفرض ردًّا لاختبار الأخطاء."""

    def __init__(self, empty=False, **kw):
        kw.setdefault("r8", True)
        kw.setdefault("r13", True)
        kw.setdefault("r14", True)
        super(V2Platform, self).__init__(empty=empty, **kw)
        self.empty = empty
        self.forced = {}
        self.payouts = [] if empty else [copy.deepcopy(PAYOUT_OK), copy.deepcopy(PAYOUT_FX)]
        self.settled = []
        self.rejected = []
        self.payments = [] if empty else copy.deepcopy(fp.MANUAL_PAYMENTS["payments"])
        self.trainer_apps = [] if empty else copy.deepcopy(fp.TRAINER_APPS["applications"])
        self.pending_users = [] if empty else copy.deepcopy(fp.PENDING_USERS["users"])
        self.invites = [] if empty else copy.deepcopy(fp.INVITES["invites"])
        self.founding = [] if empty else copy.deepcopy(fp.FOUNDING_LEADS)
        self.joins = [] if empty else copy.deepcopy(JOIN_REQUESTS["requests"])
        self.books = [] if empty else copy.deepcopy(BOOKS_REVIEW["items"])
        self.topics = [] if empty else copy.deepcopy(TOPICS_PENDING["topics"])
        self.leads = [] if empty else copy.deepcopy(LEADS["leads"])
        self.market = [] if empty else copy.deepcopy(MARKET["items"])

    # —— الملفات: المرشّحين بحقول المنصة الحقيقية
    def _list(self, status, rows):
        out = super(V2Platform, self)._list(status, rows)
        enrich_candidates(out["files"])
        # ملاحظة العميل على مرحلة قضية: الفيكستشر القديم بيبعتها {text, at}، والقوايم بتعدّيها زي ما هي (التفاصيل بس بتسطّحها) —
        # نسطّحها هنا عشان فحص «[object Object]» في الصور ما يتعلّقش بحاجة برّه اللوحة الجديدة.
        for f in out["files"]:
            for m in ((f.get("case") or {}).get("milestones") or []):
                if isinstance(m.get("problem"), dict):
                    m["problem"] = m["problem"].get("text") or ""
        return out

    def queue(self):
        q = super(V2Platform, self).queue()
        if self.empty:
            q["alerts"] = []
            return q
        q["expert_files_case_disputed"] = len(self.case_disputed)
        q["manual_refunds_pending"] = 1
        q["trainer_applications_pending"] = {"count": len(self.trainer_apps), "oldest_hours": 51.2,
                                             "names": [a.get("full_name", "") for a in self.trainer_apps]}
        q["courses_pending"] = {"count": 2, "titles": ["عقود المقاولات", "أساسيات التسويق القانوني"]}
        q["manual_payments_pending"] = {"count": len(self.payments), "oldest_hours": 30.0, "ages_hours": [30.0, 4.0]}
        q["wallet_payouts_pending"] = {"count": len(self.payouts),
                                       "total_amount": round(sum(p["amount"] for p in self.payouts), 2), "oldest_hours": 30.0}
        q["stuck_card_payments"] = copy.deepcopy(STUCK)
        q["course_split_pending"] = {"count": 1, "rows": []}
        q["testimonials_pending"] = 4
        q["topics_drafts"] = 311
        q["founding_leads_new"] = {"count": sum(1 for f in self.founding if f.get("status") == "new"), "oldest_hours": 30.0}
        q["live_needs_decision"] = copy.deepcopy(fp.QUEUE["live_needs_decision"])
        q["heartbeats"] = {"tick_last": iso(-0.2), "remind_last": iso(-2), "sla_last": iso(-1), "backup_last": iso(-20),
                           "invite_reminders_last": None, "coach_stalled_last": iso(-5)}
        q["alerts"] = list(q.get("alerts", [])) + ["⏰ طلب بلا أول رد منذ 26 ساعة: أحتاج مراجعة عقد شراكة"]
        return q

    # —— الجسور الإضافية
    def _route(self, method, path, params, body):
        forced = self.forced.get((method.upper(), path))
        if forced is not None:
            return forced
        out = self._extra(method, path, params, body)
        if out is not None:
            return out
        return super(V2Platform, self)._route(method, path, params, body)

    def _payout(self, pid):
        for p in self.payouts:
            if p["id"] == pid:
                return p
        return None

    def _extra(self, method, path, params, body):
        method = method.upper()          # `requests.get` بتعدّي 'get' صغيرة عبر Session
        if method == "GET":
            if path == "/api/bridge/wallet-payouts":
                rows = [p for p in self.payouts if p["status"] == (params.get("status") or "pending")]
                return 200, {"payouts": copy.deepcopy(rows), "count": len(rows)}
            if path == "/api/bridge/manual-payments":
                return 200, {"payments": copy.deepcopy(self.payments)}
            if path == "/api/bridge/trainer-applications":
                return 200, {"applications": copy.deepcopy(self.trainer_apps)}
            if path == "/api/bridge/pending-users":
                return 200, {"users": copy.deepcopy(self.pending_users), "count": len(self.pending_users)}
            if path == "/api/bridge/invites":
                return 200, {"invites": copy.deepcopy(self.invites), "count": len(self.invites)}
            if path == "/api/bridge/founding-expert-leads":
                return 200, copy.deepcopy(self.founding)
            if path == "/api/bridge/join-requests":
                return 200, {"requests": copy.deepcopy(self.joins)}
            if path == "/api/bridge/knowledge/review":
                return 200, {"items": copy.deepcopy(self.books)}
            if path == "/api/bridge/topics":
                return 200, {"topics": copy.deepcopy(self.topics)}
            if path == "/api/bridge/leads":
                return 200, {"leads": copy.deepcopy(self.leads)}
            if path == "/api/bridge/market/requests":
                return 200, {"items": copy.deepcopy(self.market), "total": len(self.market), "counts": {}}
            return None
        if method == "POST":
            parts = path.strip("/").split("/")
            # api/bridge/wallet-payouts/{id}/settle|reject — أخطاء المنصة بالحرف (ops_bridge.py)
            if len(parts) == 5 and parts[:3] == ["api", "bridge", "wallet-payouts"] and parts[4] in ("settle", "reject"):
                p = self._payout(parts[3])
                if p is None:
                    return 404, {"detail": "طلب السحب غير موجود"}
                if p["status"] != "pending":
                    return 409, {"detail": "طلب السحب محسوم بالفعل (%s)" % p["status"]}
                if parts[4] == "settle":
                    p["status"] = "paid"
                    p["reference"] = (body or {}).get("reference", "")
                    self.settled.append(copy.deepcopy(p))
                else:
                    p["status"] = "rejected"
                    p["reject_reason"] = (body or {}).get("reason", "")
                    self.rejected.append(copy.deepcopy(p))
                return 200, {"ok": True, "payout": copy.deepcopy(p)}
            if len(parts) == 5 and parts[:3] == ["api", "bridge", "manual-payments"] and parts[4] == "decide":
                self.payments = [x for x in self.payments if x["id"] != parts[3]]
                return 200, {"ok": True}
            if len(parts) == 5 and parts[:3] == ["api", "bridge", "trainer-applications"]:
                self.trainer_apps = [x for x in self.trainer_apps if x["id"] != parts[3]]
                return 200, {"ok": True}
        return None
