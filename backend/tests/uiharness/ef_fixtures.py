# -*- coding: utf-8 -*-
"""«ملف للخبير» — حمولات الجسر المزيّفة (الجولة ٦) + منصّة صغيرة في الذاكرة بحالة.

⛔ صفر اتصال بأي سيرفر: ده جدول ردود في الذاكرة. الأشكال منسوخة **بالحرف** من كود المنصة على فرع
`expert-file-r5-expert` (routes/expert_files.py: `bridge_list_files` · `bridge_view` · `ops_queue_snapshot`،
وroutes/consultations.py: `bridge_list_consultations` · `_serialize`) — docs/EXPERT-FILES-DASHBOARD-SPEC.md §٤.
الأسماء متخيّلة.

بيستعمله: `tests/test_expert_files_dashboard.py` (حمولات ثابتة) و`ef_route_harness.py` (الصور + اختبار
الواجهة) — `EFPlatform` بيعدّل القوايم بعد الفعل (الصفّ يتشال أو يتنقل) عشان صورة «بعد» تبقى صادقة.
"""
import copy
import datetime
import threading
import time

_NOW = datetime.datetime.now(datetime.timezone.utc)


def iso(hours_from_now=0.0):
    return (_NOW + datetime.timedelta(hours=hours_from_now)).isoformat()


STATUS_LABELS = {
    "awaiting_assignment": "بنختار لك خبير", "assigned": "بنختار لك خبير", "claimed": "{name} استلمه",
    "writing": "الرأي بيتكتب", "needs_info": "محتاجين ردّك", "delivered": "رأيك جاهز",
    "disputed": "بنراجعها معاك", "closed": "خلص", "refunded": "فلوسك رجعت", "cancelled": "اتلغى",
}
TIER_LABELS = {"written": "رأي مكتوب", "written_session": "رأي مكتوب + جلسة ٣٠ دقيقة"}
LAW_LABELS = {"eg": "القانون المصري", "sa": "القانون السعودي"}

# الخبراء المعتمدين (pool) — `_candidates` بيرتّبهم: نفس بلد القانون الأول، بعدين اللي ما اعتذرش، بعدين بالاسم.
EXPERTS = {
    "hala@experts.test": ("أ. هالة سمير", "eg"),
    "nada@experts.test": ("د. ندى حسن", "eg"),
    "karim@experts.test": ("أ. كريم عادل", "eg"),
    "sami@experts.test": ("م. سامي فؤاد", "sa"),
    "faisal@experts.test": ("أ. فيصل العتيبي", "sa"),
}
CLIENT_EMAILS = {"F1": "mona@clients.test", "F2": "ahmed@clients.test", "F3": "yasmin@clients.test",
                 "F4": "hassan@clients.test", "F5": "tarek@clients.test", "D1": "reem@clients.test"}


def candidates(law_country, declined=(), pool=None):
    out = []
    for email in (pool or EXPERTS):
        name, country = EXPERTS[email]
        out.append({"email": email, "name": name, "declined": email in declined,
                    "same_country": country == law_country})
    out.sort(key=lambda c: (not c["same_country"], c["declined"], c["name"]))
    return out


def _file(fid, *, title, status, law, tier, amount, currency, expert_amount, paid_h, deadline_h,
          client, counterparty="", flags=(), assigned_to=None, assigned_h=None, overdue=False,
          expert_email=None, writing_due_h=None, declined=(), dispute=None, pool=None):
    """صفّ `bridge_list_files` بنفس المفاتيح والترتيب."""
    hours_left = round(max(0.0, deadline_h), 1)
    in_work = status in ("awaiting_assignment", "assigned", "claimed", "writing", "needs_info")
    return {
        "id": fid, "title": title, "status": status, "status_label": STATUS_LABELS.get(status, ""),
        "law_country": law, "law_label": LAW_LABELS[law], "tier": tier, "tier_label": TIER_LABELS[tier],
        "amount": amount, "currency": currency, "expert_amount": expert_amount,
        "paid_at": iso(paid_h), "claim_deadline_at": iso(deadline_h), "hours_left": hours_left,
        "assigned_to": assigned_to,
        "assigned_name": EXPERTS[assigned_to][0] if assigned_to else "",
        "assigned_at": iso(assigned_h) if assigned_h is not None else None,
        "assign_overdue": bool(overdue),
        "expert_email": expert_email, "expert_name": EXPERTS[expert_email][0] if expert_email else "",
        "writing_due_at": iso(writing_due_h) if writing_due_h is not None else None,
        "declined": [{"email": e, "at": iso(-3), "reason": r} for e, r in declined],
        "client_first_name": client, "counterparty_name": counterparty, "price_flags": list(flags),
        "followup": None, "dispute": dispute,
        "candidates": candidates(law, [e for e, _ in declined], pool) if in_work else [],
    }


F1 = _file("ef-f1-0a1b2c3d", title="إيجار شقة — المالك عايز يطلعني", status="awaiting_assignment", law="eg",
           tier="written", amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-6.5, deadline_h=41.5,
           client="منى", counterparty="شركة النور للعقارات",
           pool=["hala@experts.test", "nada@experts.test", "sami@experts.test"])
F2 = _file("ef-f2-1b2c3d4e", title="فصل تعسفي بعد ٧ سنين", status="awaiting_assignment", law="eg",
           tier="written_session", amount=1000.0, currency="EGP", expert_amount=650.0, paid_h=-42.8,
           deadline_h=5.2, client="أحمد", counterparty="مصنع الأمل للملابس الجاهزة", flags=["country_mismatch"])
F3 = _file("ef-f3-2c3d4e5f", title="شيك من غير رصيد", status="assigned", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-17.0, deadline_h=31.0, client="ياسمين",
           counterparty="محمود السيد", assigned_to="hala@experts.test", assigned_h=-14.0, overdue=True)
F4 = _file("ef-f4-3d4e5f6a", title="ميراث أرض زراعية", status="awaiting_assignment", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-28.0, deadline_h=20.0, client="حسن",
           counterparty="", flags=["phone_ambiguous"],
           declined=[("karim@experts.test", "عندي قضية ضد نفس العيلة")])
F5 = _file("ef-f5-4e5f6a7b", title="عقد توريد مع مورد سعودي", status="writing", law="sa", tier="written",
           amount=500.0, currency="SAR", expert_amount=300.0, paid_h=-80.0, deadline_h=0.0, client="طارق",
           counterparty="مؤسسة الرمال للتجارة", expert_email="sami@experts.test", writing_due_h=-24.0,
           pool=["sami@experts.test", "faisal@experts.test", "hala@experts.test"])

D1 = _file("ef-d1-5f6a7b8c", title="حضانة بعد الطلاق", status="disputed", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-120.0, deadline_h=-72.0, client="ريم",
           counterparty="طليقي — أحمد فتحي", expert_email="nada@experts.test",
           dispute={"reason": "not_answered",
                    "note": "سألت إمتى الحضانة تنتقل للأب، والرأي اتكلم عن النفقة بس.",
                    "at": iso(-5.0)})

D1_OPINION = {
    "answers": [
        {"question_id": "q1", "question": "إمتى الحضانة ممكن تنتقل للأب؟",
         "text": "الحضانة في القانون المصري للأم لحد ما الطفل يكمل ١٥ سنة، وبعدها القاضي بيخيّره. "
                 "النفقة بتتحسب على دخل الأب الثابت، ومن حقك ترفعي دعوى نفقة متجمدة عن الشهور اللي فاتت. "
                 "لو الأب مش بيدفع، فيه طريق الحبس بعد صدور الحكم والامتناع عن التنفيذ."},
        {"question_id": "q2", "question": "هل جوازي تاني بيأثر على الحضانة؟",
         "text": "أيوه، جواز الأم من أجنبي عن الطفل بيسقط حضانتها وبتنتقل لأمها هي الأول، مش للأب مباشرة."},
    ],
    "next_step": "specialist", "next_step_note": "محامي أحوال شخصية يرفع دعوى النفقة.",
    "based_on": "اتكتب على الوقائع اللي ريم كتبتها ومستندين.",
    "expert_name": "د. ندى حسن", "law_line": "خبرة في القانون المصري", "approved_at": iso(-50.0),
}
D1_REVISION = {
    "answers": [
        {"question_id": "q1", "question": "إمتى الحضانة ممكن تنتقل للأب؟",
         "text": "الحضانة للأم لحد ١٥ سنة. بتنتقل للأب في حالتين بس: لو الأم اتجوزت من أجنبي عن الطفل "
                 "ومفيش جدة من ناحية الأم تقدر تحضن، أو لو المحكمة شافت إن الأم مش أمينة على الطفل. "
                 "الترتيب بعد الأم: أمها، بعدين أم الأب، وبعدين الأب."},
        {"question_id": "q2", "question": "هل جوازي تاني بيأثر على الحضانة؟",
         "text": "أيوه — بس الحضانة بتروح لأمك الأول، مش للأب. والأب يقدر يطلبها لو مفيش حد قبله في الترتيب."},
    ],
    "next_step": "self", "next_step_note": "", "submitted_at": iso(-2.0),
}


def detail_view(row, client_email):
    """شكل `bridge_view(f, full=True)` — الملف كله + الأسماء + ملخّص الفلوس."""
    out = {k: v for k, v in row.items() if k not in ("candidates", "hours_left", "assign_overdue",
                                                     "client_first_name")}
    out.update({
        "client_email": client_email, "file_no": None, "facts": [], "questions": [],
        "opinion": None, "revision": None, "previous_experts": [], "consultation_id": "c-" + row["id"],
        "docs": [], "client_name": row["client_first_name"] + " عبد الله",
        "money": {"consultation_id": "c-" + row["id"], "status": "held", "escrow_state": "held",
                  "held_at": row["paid_at"], "delivered_at": None, "auto_release_at": None,
                  "payment_id": "pay-" + row["id"][:8], "on_platform": row["status"] in
                  ("awaiting_assignment", "assigned")},
    })
    return out


# --------------------------------------------------------------------------- نزاعات الاستشارات (٤-د)
def _cons(cid, *, title, kind, amount, expert_amount, client, client_email, expert_email, expert_name,
          disputed_from, reason, disputed_h, manual_refund=False, cancel=False, verified_by="",
          expert_file_id=None):
    return {
        "id": cid, "title": title, "kind": kind, "amount": amount, "currency": "EGP",
        "expert_amount": expert_amount, "platform_fee": amount - expert_amount,
        "member_email": client_email, "expert_email": expert_email, "client_first_name": client,
        "expert_name": expert_name, "status": "disputed", "disputed_from": disputed_from,
        "dispute_reason": reason, "disputed_at": iso(disputed_h), "held_at": iso(disputed_h - 60),
        "delivered_at": iso(disputed_h - 10) if disputed_from == "delivered" else "",
        "payment_id": "pay-" + cid[:8], "cancel_requested": cancel, "cancel_full_refund": False,
        "manual_refund_settled_at": iso(disputed_h + 1) if manual_refund else "",
        "verified_by_email": verified_by, "expert_file_id": expert_file_id, "created_at": iso(disputed_h - 70),
    }


D2 = _cons("cs-d2-6a7b8c9d", title="مراجعة عقد شراكة", kind="consultation", amount=750, expert_amount=600,
           client="سارة", client_email="sara@clients.test", expert_email="amr@experts.test",
           expert_name="أ. عمرو الشريف", disputed_from="delivered",
           reason="الخبير رد بكلام عام وما راجعش البنود اللي طلبتها في العقد.", disputed_h=-20.0)
D3 = _cons("cs-d3-7b8c9d0e", title="هل الإنذار على يد محضر لازم؟", kind="expert_opinion", amount=250,
           expert_amount=150, client="خالد", client_email="khaled@clients.test",
           expert_email="nada@experts.test", expert_name="د. ندى حسن", disputed_from="held",
           reason="الرأي ما وصلش في الميعاد.", disputed_h=-30.0, manual_refund=True, cancel=True,
           verified_by="nada@experts.test")
# D1′ — نفس نزاع الملف D1 من قايمة الاستشارات: لازم ما يظهرش مرتين (د٨).
D1_CONS = _cons("c-" + D1["id"], title=D1["title"], kind="expert_file", amount=500, expert_amount=300,
                client="ريم", client_email=CLIENT_EMAILS["D1"], expert_email="nada@experts.test",
                expert_name="د. ندى حسن", disputed_from="delivered",
                reason="الرأي ما ردّش على سؤالي — سألت إمتى الحضانة تنتقل للأب", disputed_h=-5.0,
                expert_file_id=D1["id"])


def queue_payload(*, waiting=4, late=1, disputed=1, unactivated=1, awaiting_payment=3, open_total=8,
                  enabled=True):
    """`GET /api/bridge/ops/queue` — العدّادات القديمة (قليلة) + مفاتيح «ملف للخبير» (٤-و) + التنبيهات
    بالحرف (f-strings المنصة بأرقام لاتيني)."""
    q = {
        "generated_at": iso(0), "trainer_applications_pending": {"count": 0, "oldest_hours": None, "names": []},
        "courses_pending": {"count": 0, "titles": []},
        "manual_payments_pending": {"count": 0, "oldest_hours": None, "ages_hours": []},
        "wallet_payouts_pending": {"count": 0, "total_amount": 0, "oldest_hours": None},
        "stuck_card_payments": {"count": 0, "orders": []}, "course_interests_24h": 0,
        "training_interests_24h": 0, "course_split_pending": {"count": 0, "rows": []},
        "testimonials_pending": 0, "topics_drafts": 0, "founding_leads_new": {"count": 0, "oldest_hours": None},
        "lead_magnet_24h": {"count_24h": 0, "awaiting_asset": 0}, "lead_magnet_awaiting_asset": 0,
        "live_needs_decision": [], "heartbeats": {},
    }
    stuck = ([f"⚠️ {unactivated} ملف اتدفع وما وصلش لقايمة التوزيع — راجعه من الداشبورد"]
             if unactivated else [])
    if not enabled:
        q.update({"expert_files_open_total": open_total, "expert_files_unactivated": unactivated,
                  "expert_files_awaiting_payment": awaiting_payment,
                  "alerts": ([f"⚠️ {open_total} ملف مدفوع والميزة مقفولة — افتح المفتاح أو رجّع الفلوس"]
                             if open_total else []) + stuck})
        return q
    alerts = []
    if waiting:
        alerts.append(f"📁 {waiting} ملف مستني خبير")
    if late:
        alerts.append(f"⚠️ {late} رأي متأخر")
    if disputed:
        alerts.append(f"🛑 {disputed} ملف فيه ملاحظة مستنية قرارك")
    q.update({"expert_files_waiting": waiting, "expert_files_late": late, "expert_files_disputed": disputed,
              "expert_files_open_total": open_total, "expert_files_unactivated": unactivated,
              "expert_files_awaiting_payment": awaiting_payment, "alerts": alerts + stuck})
    return q


def list_payload(status, files):
    return {"status": status, "files": files, "count": len(files), "total": len(files)}


def cons_payload(rows):
    return {"status": "disputed", "consultations": rows, "count": len(rows), "total": len(rows)}


def serialize_cons(c, status):
    """شكل `_serialize` (رد الحسم)."""
    return {"id": c["id"], "request_id": None, "offer_id": None, "kind": c["kind"], "title": c["title"],
            "source_question": "", "segment": "", "member_email": c["member_email"],
            "expert_email": c["expert_email"], "expert_name": c["expert_name"],
            "client_first_name": c["client_first_name"], "amount": c["amount"],
            "platform_fee": c["platform_fee"], "expert_amount": c["expert_amount"], "currency": c["currency"],
            "status": status, "escrow": {"state": status}, "created_at": c["created_at"], "updated_at": iso(0)}


NOT_FOUND = {"detail": "Not Found"}


class EFPlatform(object):
    """منصّة «ملف للخبير» صغيرة في الذاكرة. `handle(method, path, params, body)` ⇒ (status, payload).
    `enabled=False` ⇒ كل `/bridge/expert-files*` ٤٠٤ (المفتاح مقفول) والطابور بالمفاتيح التلاتة بس.
    `delay[(method, path)]` ثواني تأخير (صورة «بيرجع…»). `calls` = كل اللي اتطلب، بالترتيب."""

    def __init__(self, enabled=True, empty=False, cons_enabled=True, off_open_total=2):
        self.enabled = enabled
        self.cons_enabled = cons_enabled
        self.off_open_total = off_open_total
        self.lock = threading.Lock()
        self.calls = []
        self.delay = {}
        if empty:
            self.waiting, self.late, self.disputed, self.cons = [], [], [], []
        else:
            self.waiting = [copy.deepcopy(f) for f in (F2, F4, F3, F1)]   # بـclaim_deadline_at ↑
            self.late = [copy.deepcopy(F5)]
            self.disputed = [copy.deepcopy(D1)]
            self.cons = [copy.deepcopy(D1_CONS), copy.deepcopy(D2), copy.deepcopy(D3)]
        self.extra = {"unactivated": 0 if empty else 1, "awaiting_payment": 0 if empty else 3}
        # تعديل الخبير على D1 (None = لسه ما عدّلش) · `detail_fail` = قراية الملف الجاية ترجع ٥٠٠ (مرة).
        self.d1_revision = copy.deepcopy(D1_REVISION)
        self.detail_fail = False

    # ---------------------------------------------------------------- مساعدات
    def _find(self, fid):
        for lane in (self.waiting, self.late, self.disputed):
            for f in lane:
                if f["id"] == fid:
                    return lane, f
        return None, None

    def _detail(self, f):
        d = detail_view(f, CLIENT_EMAILS.get(self._key(f), "client@clients.test"))
        if f["id"] == D1["id"]:
            d["opinion"] = copy.deepcopy(D1_OPINION)
            d["revision"] = copy.deepcopy(self.d1_revision)
            d["file_no"] = 1042
            d["docs"] = [{"id": "doc-1", "name": "حكم الطلاق.pdf", "content_type": "application/pdf",
                          "size": 120000, "stage": "draft", "created_at": iso(-130)}]
        return d

    @staticmethod
    def _key(f):
        for k, v in (("F1", F1), ("F2", F2), ("F3", F3), ("F4", F4), ("F5", F5), ("D1", D1)):
            if v["id"] == f["id"]:
                return k
        return ""

    def queue(self):
        if not self.enabled:
            return queue_payload(enabled=False, unactivated=self.extra["unactivated"],
                                 awaiting_payment=self.extra["awaiting_payment"], open_total=self.off_open_total)
        w, l, d = len(self.waiting), len(self.late), len(self.disputed)
        return queue_payload(waiting=w, late=l, disputed=d, unactivated=self.extra["unactivated"],
                             awaiting_payment=self.extra["awaiting_payment"],
                             open_total=w + l + d + self.extra["unactivated"])

    # ---------------------------------------------------------------- الموزّع
    def handle(self, method, path, params=None, body=None):
        with self.lock:
            self.calls.append((method, path, dict(params or {}), copy.deepcopy(body)))
            wait = self.delay.get((method, path), 0)
        if wait:
            time.sleep(wait)
        with self.lock:
            return self._route(method, path, params or {}, body or {})

    def _route(self, method, path, params, body):
        if path == "/api/bridge/ops/queue" and method == "GET":
            return 200, self.queue()
        if path.startswith("/api/bridge/consultations"):
            return self._consultations(method, path, params, body)
        if path.startswith("/api/bridge/expert-files"):
            if not self.enabled:
                return 404, NOT_FOUND
            return self._files(method, path, params, body)
        return None   # مش من شغلنا — الأداة بترد عليه

    def _files(self, method, path, params, body):
        parts = path[len("/api/bridge/expert-files"):].strip("/").split("/")
        if method == "GET" and parts == [""]:
            s = params.get("status") or "waiting"
            lane = {"waiting": self.waiting, "late": self.late, "disputed": self.disputed}.get(s)
            if lane is None:
                return 422, {"detail": [{"loc": ["query", "status"], "msg": "bad"}]}
            return 200, list_payload(s, copy.deepcopy(lane))
        fid = parts[0]
        lane, f = self._find(fid)
        if f is None:
            return 404, {"detail": "الملف ده مش موجود"}
        if method == "GET" and len(parts) == 1:
            if self.detail_fail:
                self.detail_fail = False
                return 500, {"detail": "Internal Server Error"}
            return 200, self._detail(f)
        act = parts[1] if len(parts) > 1 else ""
        if act == "assign":
            if f["status"] not in ("awaiting_assignment", "assigned"):
                return 409, {"detail": "الملف ده مش مستني توزيع"}
            target = (body.get("expert_email") or "").lower()
            if target not in EXPERTS:
                return 404, {"detail": "الخبير غير موجود أو غير معتمد"}
            if f["hours_left"] <= 0:
                return 409, {"detail": "فات ميعاد استلام الملف"}
            f.update({"status": "assigned", "assigned_to": target, "assigned_name": EXPERTS[target][0],
                      "assigned_at": iso(0), "assign_overdue": False,
                      "status_label": STATUS_LABELS["assigned"]})
            return 200, self._detail(f)
        if act == "reassign":
            if f["status"] not in ("claimed", "writing", "needs_info"):
                return 409, {"detail": "الملف ده مش عند خبير دلوقتي"}
            target = (body.get("expert_email") or "").lower()
            if target not in EXPERTS:
                return 404, {"detail": "الخبير غير موجود أو غير معتمد"}
            if target == f["expert_email"]:
                return 409, {"detail": "الملف عند الخبير ده أصلًا"}
            old = f["expert_email"]
            lane.remove(f)
            f.update({"status": "assigned", "assigned_to": target, "assigned_name": EXPERTS[target][0],
                      "assigned_at": iso(0), "assign_overdue": False, "expert_email": None, "expert_name": "",
                      "writing_due_at": None, "claim_deadline_at": iso(48), "hours_left": 48.0,
                      "status_label": STATUS_LABELS["assigned"]})
            self.waiting.append(f)
            d = self._detail(f)
            d["previous_experts"] = [{"email": old, "claimed_at": iso(-60), "removed_at": iso(0), "draft": None}]
            return 200, d
        if act == "refund":
            if f["status"] not in ("awaiting_assignment", "assigned", "claimed", "writing", "needs_info"):
                return 409, {"detail": "الاسترداد من هنا قبل تسليم الرأي بس"}
            lane.remove(f)
            f.update({"status": "refunded", "status_label": STATUS_LABELS["refunded"]})
            return 200, self._detail(f)
        if act == "resolve":
            if f["status"] != "disputed":
                return 409, {"detail": "الملف ده مفيهوش ملاحظة مستنية قرار"}
            action = body.get("action")
            lane.remove(f)
            self.cons = [c for c in self.cons if c.get("expert_file_id") != fid]
            f.update({"status": "closed" if action == "release" else "refunded"})
            return 200, self._detail(f)
        return 404, NOT_FOUND

    def _consultations(self, method, path, params, body):
        if not self.cons_enabled:
            return 404, NOT_FOUND
        if method == "GET" and path == "/api/bridge/consultations":
            if params.get("status") != "disputed":
                return 422, {"detail": [{"loc": ["query", "status"], "msg": "bad"}]}
            return 200, cons_payload(copy.deepcopy(self.cons))
        tail = path[len("/api/bridge/consultations/"):].split("/")
        if method == "POST" and len(tail) == 2 and tail[1] == "resolve":
            c = next((x for x in self.cons if x["id"] == tail[0]), None)
            if c is None:
                return 404, {"detail": "Consultation not found"}
            action = body.get("action")
            if action == "refund" and c.get("manual_refund_settled_at"):
                return 409, {"detail": "Already refunded manually"}
            self.cons.remove(c)
            if c.get("expert_file_id"):
                lane, f = self._find(c["expert_file_id"])
                if f is not None:
                    lane.remove(f)
            return 200, serialize_cons(c, "released" if action == "release" else "refunded")
        return 404, NOT_FOUND
