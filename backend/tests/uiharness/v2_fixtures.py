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
import re
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
    "amount": 3500.5, "currency": "SAR", "status": "pending", "method": "تحويل بنكي", "destination": "SA03 8000 0000 6080 1016 7519",
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



# ======================================================================= D2 — الشخص في مكان واحد
# ⛔ كله مخترع في الذاكرة (صفر شبكة): الأشكال بالحرف من جسور المنصة (`admin_bridge._user_row` · `invites._public_invite` ·
# `experts` · `wallet-payouts` · `purge-check` · `expert-files`).
HALA = "hala@example.test"                 # هالة: مدرّبة معتمدة + خبيرة ولها طلب سحب معلّق (PAYOUT_OK) وتحويل سابق
PERSON_INVITER = {"kind": "member", "user_id": "u-nadia", "name": "أ. نادية فؤاد", "roles": ["expert"], "video_url": None}


def _u(uid, name, email, **kw):
    row = {"id": uid, "full_name": name, "email": email, "phone": kw.pop("phone", ""), "role": kw.pop("role", "member"),
           "trainer_status": kw.pop("trainer_status", "none"), "plan_id": kw.pop("plan_id", "free"), "is_active": True,
           "created_at": iso(kw.pop("joined_h", -400)), "last_login_at": iso(kw.pop("login_h", -30)), "segment": kw.pop("segment", ""),
           "tags": kw.pop("tags", [])}
    row.update(kw)
    return row


PEOPLE = [
    _u("u-hala", "د. هالة سمير", HALA, trainer_status="approved", plan_id="pro", joined_h=-24 * 190, login_h=-2, tags=["خبيرة مؤسسة"]),
    _u("u-mona", "منى سعيد", "mona.s@example.test", joined_h=-24 * 60, login_h=-5, segment="طالب"),
    _u("u-salma", "سلمى عبد الله", "salma@example.test", plan_id="pro", joined_h=-24 * 45, login_h=-50),
    _u("u-faisal", "أ. فيصل العتيبي", "faisal@experts.test", trainer_status="approved", joined_h=-24 * 120, login_h=-8),
    _u("u-nour", "نور الهدى سالم", "nour.pending@example.test", joined_h=-31, login_h=-1),
    _u("u-karim", "كريم عادل", "karim.pending@example.test", joined_h=-6, login_h=-3),
    _u("u-nadia", "أ. نادية فؤاد", "nadia@example.test", trainer_status="approved", joined_h=-24 * 300, login_h=-1),
]


def _hala_invite():
    return {"id": "inv-hala", "name": "د. هالة سمير", "email": HALA, "status": "registered", "stage": "registered",
            "created_at": iso(-24 * 192), "opened_at": iso(-24 * 191), "email_bound_at": iso(-24 * 191),
            "approved_at": iso(-24 * 191), "registered_at": iso(-24 * 190), "generation": 2, "invited_by": dict(PERSON_INVITER),
            "link": "https://example.test/i/hala"}


PERSON_EXPERTS = {"experts": [
    {"email": HALA, "full_name": "د. هالة سمير", "expertise": ["civil"], "bio": "", "trainer_status": "approved", "rating_avg": 4.7,
     "rating_count": 12, "online": True, "last_seen_at": iso(-0.5), "referral_count": 9, "courses_count": 2, "students_count": 31},
    {"email": "faisal@experts.test", "full_name": "أ. فيصل العتيبي", "expertise": [], "bio": "", "trainer_status": "approved",
     "rating_avg": None, "rating_count": 0, "online": False, "last_seen_at": None, "referral_count": 0, "courses_count": 0,
     "students_count": 0},
], "count": 2}

PERSON_COURSES = {"courses": [
    {"id": "pc-h1", "slug": "contract-basics", "title": "أساسيات صياغة العقود", "type": "recorded_paid", "is_active": True, "bid_enabled": False,
     "price_amount": 450, "price_currency": "EGP", "total_enrolled": 24, "approval_status": "approved", "source": "native",
     "created_at": iso(-24 * 100), "archived_at": "", "short_description": "", "instructor_name": "د. هالة سمير", "lesson_count": 12, "story": None},
    {"id": "pc-h2", "slug": "lease-review", "title": "مراجعة عقود الإيجار", "type": "recorded_paid", "is_active": False, "bid_enabled": False,
     "price_amount": 300, "price_currency": "EGP", "total_enrolled": 7, "approval_status": "pending", "source": "native",
     "created_at": iso(-24 * 9), "archived_at": "", "short_description": "", "instructor_name": "د. هالة سمير", "lesson_count": 5, "story": None},
], "count": 2}

PERSON_PAID = [
    {"id": "po-h-old1", "user_email": HALA, "user_name": "د. هالة سمير", "amount": 2400.0, "currency": "EGP", "status": "paid", "method": "إنستاباي",
     "destination": "hala@instapay", "created_at": iso(-24 * 40), "settled_at": iso(-24 * 39), "reference": "IP-7781"},
    {"id": "po-h-old2", "user_email": HALA, "user_name": "د. هالة سمير", "amount": 950.5, "currency": "EGP", "status": "paid", "method": "إنستاباي",
     "destination": "hala@instapay", "created_at": iso(-24 * 12), "settled_at": iso(-24 * 11), "reference": "IP-8120"},
]

# الأقسام اللي بتتحسب من فحص الحساب (عدّ فقط): تسجيلات الدورات لكل حساب.
PERSON_LINKED = {"u-hala": {"payments": 2, "wallet_payouts": 3, "courses": 2, "consultations": 4, "expert_files": 4},
                 "u-mona": {"enrollments": 3, "payments": 3, "course_reservations": 1}}


def person_files():
    """ملفات هالة كخبيرة: واحد بيكتب · واحد متسلّم من ساعتين · اتنين اتسلّموا — شكل `bridge_list_files(all)`."""
    rows = []
    for fid, title, status, amt, a_h, deadline in (
            ("ef-ph-1a2b3c4d", "عقد إيجار تجاري — بند الإخلاء", "writing", 500.0, -20.0, 12.0),
            ("ef-ph-2b3c4d5e", "إنذار بسداد متأخرات الإيجار", "assigned", 500.0, -2.0, 40.0),
            ("ef-ph-3c4d5e6f", "نفقة زوجة بعد الانفصال", "delivered", 1000.0, -90.0, -40.0),
            ("ef-ph-4d5e6f7a", "اعتراض على قرار فصل", "delivered", 500.0, -300.0, -250.0)):
        f = fx._file(fid, title=title, status=status, law="eg", tier="written", amount=amt, currency="EGP",
                     expert_amount=round(amt * 0.6, 2), paid_h=a_h - 3, deadline_h=deadline, client="عميل",
                     expert_email=HALA if status != "assigned" else None, assigned_to=HALA if status == "assigned" else None,
                     assigned_h=a_h, writing_due_h=(deadline if status == "writing" else None),
                     file_no=(1200 + len(rows) if status == "delivered" else None))
        f["assign_log"] = [fx.assign_entry(a_h - 0.5, HALA, by="founder", reason="manual", why="")]
        rows.append(f)
    return rows


# —— ملفات جديدة لشاشة «ملفات الخبراء» (D2): بتتضاف بس لو `d2=True` (غيره الأعداد القديمة زي ما هي بالحرف).
def d2_files():
    """٤ ملفات اتبعتت لخبراء من ساعات (في موعدها ⇒ عمود «عند الخبراء») + رأيين اتعتمدوا النهارده (عمود «خلص اليوم»)."""
    sent = []
    spec = (("ef-w1-aa11bb22", "عقد شراكة بين ثلاثة أطراف", "hala@experts.test", "طارق", -3.0, 44.0, "مؤسسة الندى"),
            ("ef-w2-bb22cc33", "إخلاء محل تجاري", "nada@experts.test", "ليلى", -5.0, 40.0, "مالك العقار"),
            ("ef-w3-cc33dd44", "ميراث وتقسيم تركة", "karim@experts.test", "عمر", -1.0, 46.0, ""),
            ("ef-w4-dd44ee55", "تأخر تسليم وحدة سكنية", "hala@experts.test", "رنا", -6.5, 30.5, "شركة التطوير"))
    for fid, title, expert, client, a_h, left, cp in spec:
        f = fx._file(fid, title=title, status="assigned", law="eg", tier="written", amount=500.0, currency="EGP", expert_amount=300.0,
                     paid_h=a_h - 1, deadline_h=left, client=client, counterparty=cp, assigned_to=expert, assigned_h=a_h,
                     pool=["hala@experts.test", "nada@experts.test", "karim@experts.test"])
        sent.append(f)
    done = []
    for fid, title, expert, client, ap_h in (("ef-dn-1a1a2b2b", "تعويض عن تأخر شحنة", "rana@experts.test", "هبة", -1.2),
                                              ("ef-dn-2b2b3c3c", "مراجعة وصية", "wael@experts.test", "أيمن", -3.5)):
        f = fx._file(fid, title=title, status="in_review", law="eg", tier="written", amount=500.0, currency="EGP", expert_amount=300.0,
                     paid_h=-60.0, deadline_h=-12.0, client=client, expert_email=expert, writing_due_h=12.0,
                     review={"submitted_at": iso(ap_h - 1.0), "round": 1, "returns": 0, "returned_at": None, "note": "",
                             "approved_at": iso(ap_h)}, pending_opinion=fx.R1_OPINION, delivered_count=0)
        done.append(f)
    return sent, done


class V2Platform(fx.EFPlatform):
    """`EFPlatform` + باقي جسور اللوحة. `forced[(method, path)] = (status, payload)` يفرض ردًّا لاختبار الأخطاء."""

    def __init__(self, empty=False, d2=False, **kw):
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
        self.decided_payments = {}     # id ⇒ الوثيقة بعد القرار (المنصة بترد بيها لو اتحسمت قبل كده)
        self.trainer_apps = [] if empty else copy.deepcopy(fp.TRAINER_APPS["applications"])
        self.pending_users = [] if empty else copy.deepcopy(fp.PENDING_USERS["users"])
        self.invites = [] if empty else copy.deepcopy(fp.INVITES["invites"])
        self.founding = [] if empty else copy.deepcopy(fp.FOUNDING_LEADS)
        self.joins = [] if empty else copy.deepcopy(JOIN_REQUESTS["requests"])
        self.books = [] if empty else copy.deepcopy(BOOKS_REVIEW["items"])
        self.topics = [] if empty else copy.deepcopy(TOPICS_PENDING["topics"])
        self.leads = [] if empty else copy.deepcopy(LEADS["leads"])
        self.market = [] if empty else copy.deepcopy(MARKET["items"])
        # D2: الأشخاص + ملفاتهم + سحوباتهم (لا تمس الأعداد القديمة: قوائم منفصلة تتقدّم بس في ردود الشخص)
        self.people = [] if empty else copy.deepcopy(PEOPLE)
        self.person_invites = [] if empty else [_hala_invite()]
        self.person_paid = [] if empty else copy.deepcopy(PERSON_PAID)
        self.person_files = [] if empty else person_files()
        if d2 and not empty:
            sent, done = d2_files()
            self.waiting = sorted(self.waiting + sent, key=lambda f: f["claim_deadline_at"])
            self.review = self.review + done

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
                st = params.get("status") or "pending"
                rows = [p for p in self.payouts if p["status"] == st]
                if st == "paid":
                    rows = rows + [p for p in self.person_paid if p["status"] == "paid"]
                return 200, {"payouts": copy.deepcopy(rows), "count": len(rows)}
            if path == "/api/bridge/users":
                q = str(params.get("search") or "").strip().lower()
                rows = [u for u in self.people if not q or q in u["email"].lower() or q in u["full_name"].lower()]
                rows = rows[: int(params.get("limit") or 500)]
                return 200, {"users": copy.deepcopy(rows), "count": len(rows)}
            if path == "/api/bridge/experts":
                return 200, ({"experts": [], "count": 0} if self.empty else copy.deepcopy(PERSON_EXPERTS))
            if path == "/api/bridge/courses":
                return 200, ({"courses": [], "count": 0} if self.empty else copy.deepcopy(PERSON_COURSES))
            m_pc = re.match(r"^/api/bridge/users/([^/]+)/purge-check$", path)
            if m_pc:
                linked = PERSON_LINKED.get(m_pc.group(1), {})
                return 200, {"purgeable": not linked, "reason": ("عنده مدفوعات" if linked else None), "linked": dict(linked)}
            if path == "/api/bridge/expert-files" and params.get("status") == "all":
                rows = [f for lane in self._lanes() for f in lane] + list(self.person_files)
                return 200, {"status": "all", "files": copy.deepcopy(rows), "count": len(rows), "total": len(rows),
                             "service_open": self.service_open, "service_mode": self.mode, "allowlist_size": len(self.allowlist)}
            if path == "/api/bridge/manual-payments":
                return 200, {"payments": copy.deepcopy(self.payments)}
            if path == "/api/bridge/trainer-applications":
                return 200, {"applications": copy.deepcopy(self.trainer_apps)}
            if path == "/api/bridge/pending-users":
                return 200, {"users": copy.deepcopy(self.pending_users), "count": len(self.pending_users)}
            if path == "/api/bridge/invites":
                rows = self.invites + self.person_invites
                return 200, {"invites": copy.deepcopy(rows), "count": len(rows)}
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
                # `bridge_decide_manual_payment`: الوثيقة بعد القرار (حالتها confirmed|rejected)؛ لو اتحسمت قبل كده بترجّع
                # الموجودة كما هي بـ٢٠٠ (confirm_manual_payment_doc idempotent)؛ غير موجودة ⇒ ٤٠٤.
                mid = parts[3]
                doc = next((x for x in self.payments if x["id"] == mid), None)
                if doc is not None:
                    self.payments = [x for x in self.payments if x["id"] != mid]
                    doc = copy.deepcopy(doc)
                    decision = (body or {}).get("decision")
                    doc["status"] = "confirmed" if decision == "confirm" else "rejected"
                    doc["admin_note"] = (body or {}).get("admin_note", "")
                    self.decided_payments[mid] = doc
                    return 200, copy.deepcopy(doc)
                if mid in self.decided_payments:
                    return 200, copy.deepcopy(self.decided_payments[mid])
                return 404, {"detail": "طلب الدفع غير موجود"}
            if len(parts) == 5 and parts[:3] == ["api", "bridge", "trainer-applications"]:
                self.trainer_apps = [x for x in self.trainer_apps if x["id"] != parts[3]]
                return 200, {"ok": True}
        return None
