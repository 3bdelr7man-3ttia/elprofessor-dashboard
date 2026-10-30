# -*- coding: utf-8 -*-
"""منصّة وهميّة لقسم «الناس والدعوات» النهائي: فوق `V2Platform` بتضيف قائمة الانتظار · دعوات بكل المحطات · زوّار (طلبوا ولم يطلبوا ورُفض واحد) ·
حسابات بأدوارها · أرقام العملاء · تفصيل الدعوة · إعدادات الدعوة · رسائل المحادثة وطلبات التواصل · وكل كتابة بحالتها (تتسجّل في `writes`).

⛔ صفر شبكة: كله في الذاكرة. الأشكال بالحرف من جسور المنصة؛ الأسماء والأرقام مخترعة. `forced[(method, path)] = (status, payload)` يفرض ردًّا،
و`down = {path}` يخلّي المصدر يرد ٥٠٢، و`missing = {path}` يخلّيه يرد ٤٠٤ (جسر لم يُنشر بعد).
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


def _inviter(uid, name, kind="member"):
    return {"user_id": uid, "name": name, "kind": kind, "roles": ["lawyer"], "video_url": None}


def _inv(iid, name, stage, status=None, hours=-5.0, **kw):
    row = {"id": iid, "name": name, "email": kw.pop("email", ""), "status": status or ("registered" if stage == "registered" else ("revoked" if stage == "revoked" else "pending")),
           "stage": stage, "created_at": iso(hours), "generation": kw.pop("generation", 1), "invited_by": kw.pop("invited_by", {"kind": "founder", "name": "المؤسس", "user_id": None}),
           "roles": kw.pop("roles", []), "specialty": kw.pop("specialty", None), "note": kw.pop("note", ""), "link": kw.pop("link", "https://example.test/i/" + iid),
           "expires_at": kw.pop("expires_h", None)}
    if row["expires_at"] is not None:
        row["expires_at"] = iso(row["expires_at"])
    row.update(kw)
    return row


def invites_all():
    nadia = _inviter("u-nadia", "أ. نادية فؤاد")
    hala = _inviter("u-hala", "د. هالة سمير")
    return [
        _inv("inv-aw1", "منال حسن", "awaiting_approval", "awaiting_approval", -72, generation=2, invited_by=nadia, note="زميلتي في المكتب", link=""),
        _inv("inv-aw2", "طارق سيد", "awaiting_approval", "awaiting_approval", -5, generation=3, invited_by=hala, link=""),
        _inv("inv-p1", "سامي رشدي", "pending", "pending", -20, expires_h=24 * 6, phone="+201001234567"),
        _inv("inv-p2", "لمياء عبد الرحيم", "pending", "pending", -2, expires_h=24 * 9, invited_by=nadia),
        _inv("inv-o1", "وليد منصور", "opened", "opened", -80, expires_h=30, invited_by=nadia, roles=["lawyer"], opened_at=iso(-79)),
        _inv("inv-o2", "ريم الشافعي", "exercised", "opened", -5, expires_h=24 * 7, roles=["consultant"], specialty="civil", opened_at=iso(-4.5)),
        _inv("inv-o3", "عمر فتحي", "declared", "opened", -52, expires_h=24 * 5, invited_by=hala, roles=["trainer"], opened_at=iso(-51),
             demo={"documented": {"mode": "request"}}),
        _inv("inv-r1", "د. هالة سمير", "registered", "registered", -24 * 2, email="hala@example.test", registered_at=iso(-24 * 2 + 3), opened_at=iso(-24 * 2 + 1), invited_by=nadia),
        _inv("inv-r2", "منى سعيد", "registered", "registered", -24 * 15, email="mona.s@example.test", registered_at=iso(-24 * 12), opened_at=iso(-24 * 14)),
        _inv("inv-x1", "كامل ياسين", "expired", "pending", -24 * 20, expires_h=-24 * 2),
        _inv("inv-x2", "دينا فاروق", "revoked", "revoked", -24 * 8, invited_by=hala),
        _inv("inv-x3", "ماجد عز", "rejected", "rejected", -24 * 4, generation=2, invited_by=nadia, approval_note="الاسم غير مكتمل", link=""),
    ]


WAITLIST = [
    {"id": "wl-1", "name": "ياسمين طه", "email": "yasmin.t@example.test", "why": "أتابع محتوى البروفيسور وأريد دعوة للانضمام", "role": "lawyer", "specialty": "family",
     "phone": "+201112223344", "country": "مصر", "status": "new", "created_at": iso(-26)},
    {"id": "wl-2", "name": "", "email": "anon@example.test", "why": "", "role": "researcher", "specialty": "", "phone": "", "country": "", "status": "new", "created_at": iso(-4)},
    {"id": "wl-3", "name": "حسن بدر", "email": "hassan.b@example.test", "why": "باحث في القانون التجاري", "role": "researcher", "specialty": "corporate",
     "phone": "0501112233", "country": "السعودية", "status": "new", "created_at": iso(-50)},
    {"id": "wl-4", "name": "تم دعوتها", "email": "done@example.test", "why": "", "role": "", "specialty": "", "phone": "", "country": "", "status": "invited", "created_at": iso(-90)},
]

PENDING = [
    {"id": "pu-1", "full_name": "نور الهدى سالم", "email": "nour.pending@example.test", "phone": "+201000000011", "created_at": iso(-31), "access": "pending",
     "invite_request": {"status": "requested", "requested_at": iso(-30), "decided_at": None, "note": ""}, "role_requested": "lawyer", "country": "مصر", "specialty": "civil",
     "why": "أريد الانضمام لمجتمع المحامين والسؤال بلا حدود", "last_login_at": iso(-1), "ai_used": 5, "signup_country": "EG"},
    {"id": "pu-2", "full_name": "كريم عادل", "email": "karim.pending@example.test", "phone": "+966500000022", "created_at": iso(-6), "access": "pending",
     "invite_request": {"status": "requested", "requested_at": iso(-3), "decided_at": None, "note": ""}, "role_requested": "consultant", "country": "السعودية", "specialty": "",
     "why": "", "last_login_at": iso(-3), "ai_used": 2, "signup_flags": ["dotted_gmail", "random_name"], "flag_labels": ["إيميل بنقط", "اسم عشوائي"], "signup_country": "US", "signup_ip": "8.8.8.8"},
    {"id": "pu-3", "full_name": "زائر لم يطلب بعد", "email": "silent.pending@example.test", "phone": "", "created_at": iso(-2), "access": "pending", "invite_request": {"status": "none"},
     "role_requested": "", "country": "", "specialty": "", "why": "", "last_login_at": iso(-2), "ai_used": 0},
    {"id": "pu-4", "full_name": "ياسر منير", "email": "yasser.m@example.test", "phone": "", "created_at": iso(-70), "access": "pending",
     "invite_request": {"status": "rejected", "requested_at": iso(-60), "decided_at": iso(-50), "note": "نحتاج بيانات أوضح"}, "role_requested": "", "country": "", "specialty": "", "why": "",
     "last_login_at": None, "ai_used": None},
    {"id": "pu-5", "full_name": "مصطفى هشام", "email": "mostafa.h@example.test", "phone": "", "created_at": iso(-100), "access": "pending", "invite_request": {"status": "none"},
     "role_requested": "", "country": "", "specialty": "", "why": "", "last_login_at": iso(-30), "ai_used": 4},
]


def _u(uid, name, email, **kw):
    return v2fx._u(uid, name, email, **kw)


PEOPLE_EXTRA = [
    _u("u-founder", "المؤسس", "admin@local.test", role="admin", joined_h=-24 * 400, login_h=-0.5),
    _u("u-staff", "موظفة المتابعة", "staff.nora@example.test", role="staff", joined_h=-24 * 200, login_h=-6),
    _u("u-inv", "ماجد المستثمر", "investor@example.test", role="investor", joined_h=-24 * 150, login_h=-90),
    _u("u-pend", "طالب اعتماد", "trainer.pending@example.test", trainer_status="pending", joined_h=-24 * 3, login_h=-4, segment="lawyer"),
    _u("u-test", "حساب تجريبي", "demo.account@example.test", joined_h=-24 * 30, login_h=-500, is_test=True, tags=["تجريبي", "اختبار"]),
    _u("u-off", "حساب موقوف", "off.user@example.test", joined_h=-24 * 90, login_h=-24 * 80, is_active=False, segment="company"),
]
HIDDEN_PEOPLE = [
    _u("u-h1", "سلوى محمود", "salwa.m@example.test", joined_h=-24 * 500, login_h=-24 * 300),
    _u("u-h2", "علي سلوى", "ali.salwa@example.test", joined_h=-24 * 520, login_h=-24 * 100),
]
ALL_EXTRA_TAGS = {"u-hala": ["خبيرة مؤسسة", "كاتبة", "متحدثة", "محكّمة", "زائرة دائمة"]}

INVITE_DETAIL = {
    "inv-o2": {"id": "inv-o2", "inviter": {"kind": "founder", "name": "المؤسس", "user_id": None}, "user": {"phone": "+201005550000", "email": ""}, "years": 9, "generation": 1,
               "focus": "نزاعات العمل والتعويضات", "video_source": "platform", "video_url": "",
               "timeline": [{"key": "created", "at": iso(-5)}, {"key": "opened", "at": iso(-4.5)}, {"key": "email_bound", "at": iso(-4.4)}, {"key": "pain_seen", "at": iso(-4.2)}, {"key": "exercised", "at": iso(-4)}],
               "exercises": [],
               "demo": {"question": "هل يجوز فصل العامل أثناء الإجازة المرضية؟",
                        "transcript": [{"who": "user", "text": "هل يجوز فصل العامل أثناء الإجازة المرضية؟"},
                                       {"who": "ai", "text": "الأصل أنه لا يجوز إنهاء العقد أثناء الإجازة المرضية المقررة قانونًا، إلا في حالات محددة.", "ai_source": "fallback"},
                                       {"who": "user", "text": "وما الحالات المحددة؟"},
                                       {"who": "ai", "text": "مثل ثبوت خطأ جسيم أو انتهاء مدة العقد، وبشرط الإخطار الكتابي."}],
                        "documented": {"mode": "answer", "final_text": "لا يجوز الفصل أثناء الإجازة المرضية إلا لخطأ جسيم مع إخطار كتابي.", "verdict": "partly",
                                       "notes": "أضفت شرط الإخطار الكتابي", "proposal": "أريد أن أتعلم صياغة الإنذارات"}},
               "declaration": None, "founding": False, "proposals": []},
}

SETTINGS_FOUNDING = {"open": True, "updated_at": iso(-100)}
SETTINGS_INVITES = {"welcome_video_url": "", "platform_video_url": "", "member_invite_quota": None, "invite_approval_from_generation": 2}
SETTINGS_VIDEOS = {"trainer": "https://example.test/v/trainer", "lawyer": "", "consultant": "", "researcher": "", "graduate": "", "multi": ""}

CHAT_MESSAGES = {"messages": [
    {"id": "pm-1", "from_name": "ليلى أحمد", "from_email": "layla.a@example.test", "subject": "سؤال عن ملف الخبير", "body": "أرسلت لكم ملفي أمس وأريد أن أعرف متى سيصلني رأي الخبير؟ شكرًا لكم.",
     "contact_phone": "+201098765432", "created_at": iso(-30)},
    {"id": "pm-2", "from_name": "", "from_email": "", "subject": "", "body": "هل الدورات متاحة بالإنجليزية؟", "contact_phone": "+971501234567", "created_at": iso(-2)},
]}
CHAT_LEADS = {"leads": [
    {"id": "ld-1", "full_name": "سلمى منصور", "phone": "+201555000111", "experience": "محامية منذ ٥ سنوات", "want": "استشارة في نفقة الصغير بشكل مستعجل", "from_email": "salma.m@example.test", "created_at": iso(-8)},
    {"id": "ld-2", "full_name": "", "phone": "", "experience": "", "want": "عرض أسعار لتأسيس شركة", "from_email": "founder.co@example.test", "created_at": iso(-1)},
]}

CUSTOMERS = {"total": 128, "members": 101, "admins": 1, "staff": 2, "investors": 1, "trainers_approved": 14, "paid_plan": 23, "signups_today": 3, "signups_7d": 19}
PLANS = {"plans": [{"id": "free", "name": "المجانية", "is_free": True, "prices": {}}, {"id": "pro", "name": "الاحترافية", "prices": {"default": {"amount": 9}}},
                   {"id": "premium", "name": "بريميوم", "prices": {"default": {"amount": 29}}}]}


class PeoplePlatform(v2fx.V2Platform):
    def __init__(self, empty=False, **kw):
        super(PeoplePlatform, self).__init__(empty=empty, d2=True, **kw)
        self.down = set()
        self.missing = set()
        self.writes = []
        self.customers = copy.deepcopy(CUSTOMERS)
        self.settings_founding = copy.deepcopy(SETTINGS_FOUNDING)
        self.settings_invites = copy.deepcopy(SETTINGS_INVITES)
        self.settings_videos = copy.deepcopy(SETTINGS_VIDEOS)
        self.invites_total = None            # لو أكبر من عدد الصفوف ⇒ شريط «معروض x من y»
        self.hidden_people = copy.deepcopy(HIDDEN_PEOPLE)
        self.invite_seq = 100
        if empty:
            self.waitlist, self.pending_users, self.invites, self.person_invites, self.joins, self.founding = [], [], [], [], [], []
            self.chat, self.leads2 = {"messages": []}, {"leads": []}
            self.people = []
            self.customers = {k: 0 for k in CUSTOMERS}
            return
        self.waitlist = copy.deepcopy(WAITLIST)
        self.pending_users = copy.deepcopy(PENDING)
        self.invites = invites_all()
        self.person_invites = []
        self.joins = [
            {"id": "jr-1", "status": "pending", "section": "expert_offers", "section_label": "خبير معتمد", "user_name": "أ. مها الشريف", "user_email": "maha@example.test", "submitted_at": iso(-20),
             "note": "محامية بالنقض، أقدّم مراجعة عقود تجارية.", "service_label": "مراجعة العقود التجارية", "licensed": True, "licence_missing": False, "licence_note": "", "status_label": "بانتظار القرار",
             "attachments": ["https://example.test/licence.pdf"], "answers": {"الخبرة": "١٢ سنة في القضايا التجارية", "المدينة": "القاهرة"}},
            {"id": "jr-2", "status": "needs_info", "section": "lawyer_offers", "section_label": "محامٍ معتمد", "user_name": "أ. عمرو القاضي", "user_email": "amr@example.test", "submitted_at": iso(-70),
             "note": "", "service_label": "صياغة العقود", "licensed": True, "licence_missing": True, "licence_note": "الترخيص بلا رقم قيد — لا يُقبل الطلب قبل استكماله",
             "status_label": "بانتظار الاستكمال", "info_request": "أرسل رقم القيد في النقابة", "attachments": [], "answers": {}},
        ]
        self.founding = [
            {"id": "fl-1", "name": "د. ثابت أبو الروس", "whatsapp": "+970599000000", "email": "thabit@example.test", "specialization": "تحكيم", "years_experience": "أكثر من 15",
             "country": "فلسطين", "status": "new", "linkedin_url": "https://www.linkedin.com/in/example", "created_at": iso(-30), "updated_at": iso(-30)},
            {"id": "fl-3", "name": "أ. رانيا الخطيب", "whatsapp": "+201000000777", "email": "hala@example.test", "specialization": "مدني", "years_experience": "10", "country": "مصر",
             "status": "contacted", "created_at": iso(-60), "updated_at": iso(-20)},
        ]
        self.chat = copy.deepcopy(CHAT_MESSAGES)
        self.leads2 = copy.deepcopy(CHAT_LEADS)
        self.people = copy.deepcopy(v2fx.PEOPLE) + copy.deepcopy(PEOPLE_EXTRA)
        for u in self.people:
            if u["id"] in ALL_EXTRA_TAGS:
                u["tags"] = list(ALL_EXTRA_TAGS[u["id"]])

    # ---------------------------------------------------------------- تتبّع
    def _rec(self, method, path, body):
        self.writes.append((method.upper(), path, copy.deepcopy(body)))

    def _down(self, path):
        if path in self.down:
            return 502, {"detail": "down"}
        if path in self.missing:
            return 404, NOT_FOUND
        return None

    def _route(self, method, path, params, body):
        method = method.upper()
        forced = self.forced.get((method, path))
        if forced is not None:
            return forced
        d = self._down(path)
        if d is not None:
            return d
        out = self._people(method, path, params, body)
        if out is not None:
            return out
        return super(PeoplePlatform, self)._route(method, path, params, body)

    def _find(self, rows, rid):
        for r in rows:
            if r.get("id") == rid:
                return r
        return None

    def queue(self):
        q = super(PeoplePlatform, self).queue()
        return q

    # ---------------------------------------------------------------- الجسور
    def _people(self, method, path, params, body):
        if method == "GET":
            if path == "/api/admin/metrics":
                return 200, {"customers": copy.deepcopy(self.customers)}
            if path == "/api/bridge/plans":
                return 200, copy.deepcopy(PLANS)
            if path == "/api/bridge/waitlist":
                return 200, {"waitlist": copy.deepcopy(self.waitlist), "count": len(self.waitlist)}
            if path == "/api/bridge/invites":
                rows = copy.deepcopy(self.invites)
                return 200, {"invites": rows, "count": self.invites_total if self.invites_total is not None else len(rows)}
            m = re.match(r"^/api/bridge/invites/([^/]+)$", path)
            if m:
                d = INVITE_DETAIL.get(m.group(1))
                return (200, copy.deepcopy(d)) if d else (200, {"id": m.group(1), "inviter": {"kind": "founder", "name": "المؤسس"}, "timeline": [{"key": "created", "at": iso(-30)}, {"key": "opened", "at": iso(-29)}],
                                                                 "exercises": [], "demo": None, "declaration": None, "founding": False})
            if path == "/api/bridge/users":
                q = str(params.get("search") or "").strip().lower()
                rows = self.people if not q else self.people + self.hidden_people
                rows = [u for u in rows if not q or q in u["email"].lower() or q in u["full_name"].lower() or q in str(u.get("phone", ""))]
                return 200, {"users": copy.deepcopy(rows), "count": len(rows)}
            if path == "/api/bridge/settings/founding":
                return 200, copy.deepcopy(self.settings_founding)
            if path == "/api/bridge/settings/invites":
                return 200, copy.deepcopy(self.settings_invites)
            if path == "/api/bridge/settings/invite-videos":
                return 200, copy.deepcopy(self.settings_videos)
            if path == "/api/bridge/messages":
                return 200, copy.deepcopy(self.chat)
            if path == "/api/bridge/leads":
                return 200, copy.deepcopy(self.leads2)
            return None
        if method in ("POST", "DELETE", "PUT"):
            self._rec(method, path, body)
            if path == "/api/bridge/invites":
                self.invite_seq += 1
                iid = "inv-new%d" % self.invite_seq
                row = _inv(iid, body.get("name", ""), "pending", "pending", -0.01, email=body.get("email", ""), phone=body.get("phone", ""), expires_h=24 * 10, link="https://example.test/i/" + iid)
                self.invites.insert(0, row)
                return 200, {"id": iid, "link": row["link"], "invite_url": row["link"]}
            m = re.match(r"^/api/bridge/invites/([^/]+)/(approve|reject|revoke|reissue)$", path)
            if m:
                r = self._find(self.invites, m.group(1))
                if r is None:
                    return 404, {"detail": "الدعوة غير موجودة"}
                act = m.group(2)
                if act == "approve":
                    r.update({"stage": "pending", "status": "pending", "link": "https://example.test/i/" + r["id"]})
                    return 200, {"ok": True}
                if act == "reject":
                    r.update({"stage": "rejected", "status": "rejected", "approval_note": (body or {}).get("note", "")})
                    return 200, {"ok": True}
                if act == "revoke":
                    r.update({"stage": "revoked", "status": "revoked"})
                    return 200, {"ok": True}
                if r.get("stage") == "pending":
                    return 409, {"detail": "الدعوة ما زالت تعمل — لا حاجة لإعادة إصدارها"}
                r.update({"stage": "pending", "status": "pending", "link": "https://example.test/i/%s-v2" % r["id"], "created_at": iso(-0.01), "expires_at": iso(24 * 10)})
                return 200, {"link": r["link"], "invite_url": r["link"]}
            m = re.match(r"^/api/bridge/waitlist/([^/]+)/invite$", path)
            if m:
                r = self._find(self.waitlist, m.group(1))
                if r is None:
                    return 404, {"detail": "الصف غير موجود"}
                r["status"] = "invited"
                self.invite_seq += 1
                iid = "inv-wl%d" % self.invite_seq
                row = _inv(iid, r.get("name", ""), "pending", "pending", -0.01, email=r.get("email", ""), phone=(body or {}).get("phone", ""), expires_h=24 * 10)
                self.invites.insert(0, row)
                return 200, {"id": iid, "link": row["link"]}
            m = re.match(r"^/api/bridge/users/([^/]+)/(access|role|plan|tags|flag-test|purge)$", path)
            if m:
                uid, act = m.group(1), m.group(2)
                if act == "access":
                    r = self._find(self.pending_users, uid)
                    if r is None:
                        return 404, {"detail": "الحساب غير موجود"}
                    if (body or {}).get("access") == "member":
                        self.pending_users = [x for x in self.pending_users if x["id"] != uid]
                    else:
                        r["invite_request"] = {"status": "rejected", "requested_at": r["invite_request"].get("requested_at"), "decided_at": iso(0), "note": (body or {}).get("note", "")}
                    return 200, {"ok": True}
                if act == "purge":
                    linked = v2fx.PERSON_LINKED.get(uid)
                    if linked:
                        return 409, {"detail": "عنده مدفوعات", "purgeable": False}
                    self.pending_users = [x for x in self.pending_users if x["id"] != uid]
                    self.people = [x for x in self.people if x["id"] != uid]
                    return 200, {"ok": True, "removed": {}}
                r = self._find(self.people, uid)
                if r is None:
                    return 404, {"detail": "الحساب غير موجود"}
                if act == "role":
                    r["role"] = (body or {}).get("role", r["role"])
                elif act == "plan":
                    r["plan_id"] = (body or {}).get("plan_id", r["plan_id"])
                elif act == "tags":
                    r["tags"] = list((body or {}).get("tags", []))
                elif act == "flag-test":
                    r["is_test"] = bool((body or {}).get("is_test"))
                return 200, {"ok": True}
            m = re.match(r"^/api/bridge/trainers/([^/]+)/deactivate$", path)
            if m:
                r = self._find(self.people, m.group(1))
                if r is not None:
                    r["trainer_status"] = "none"
                    r["is_test"] = bool((body or {}).get("is_test", True))
                return 200, {"ok": True}
            if path == "/api/bridge/settings/founding":
                self.settings_founding["open"] = bool((body or {}).get("open"))
                return 200, copy.deepcopy(self.settings_founding)
            if path == "/api/bridge/settings/invites":
                self.settings_invites.update(body or {})
                return 200, copy.deepcopy(self.settings_invites)
            if path == "/api/bridge/settings/invite-videos":
                self.settings_videos.update(body or {})
                return 200, copy.deepcopy(self.settings_videos)
            m = re.match(r"^/api/bridge/(messages|leads)/([^/]+)/resolve$", path)
            if m:
                lst = self.chat["messages"] if m.group(1) == "messages" else self.leads2["leads"]
                keep = [x for x in lst if x["id"] != m.group(2)]
                lst[:] = keep
                return 200, {"ok": True}
            m = re.match(r"^/api/bridge/join-requests/([^/]+)/decide$", path)
            if m:
                self.joins = [x for x in self.joins if x["id"] != m.group(1)]
                return 200, {"ok": True}
            m = re.match(r"^/api/bridge/founding-leads/([^/]+)/status$", path)
            if m:
                self.founding = [x for x in self.founding if x["id"] != m.group(1) or (body or {}).get("status") not in ("rejected", "converted")]
                return 200, {"ok": True}
        return None
