# -*- coding: utf-8 -*-
"""«ملف للخبير» — حمولات الجسر المزيّفة + منصّة صغيرة في الذاكرة بحالة (الجولة ٦، متحدّثة للجولة ٧).

⛔ صفر اتصال بأي سيرفر: ده جدول ردود في الذاكرة. الأشكال منسوخة **بالحرف** من كود المنصة على فرع
`expert-file-r7-polish` (routes/expert_files.py: `_bridge_row` · `_unactivated_rows` · `bridge_reply` ·
`bridge_refund_unactivated` · `ops_queue_snapshot` · `BLOCK_LABELS` · `E_*`، وroutes/consultations.py:
`bridge_list_consultations` · `bridge_resolve_reply` · `E_RESOLVE_*`، وroutes/ops_bridge.py: `bridge_ops_queue`)
— docs/expert-files/SPEC.md §١٨-ج في ريبو المنصة. الأسماء متخيّلة.

بيستعمله: `tests/test_expert_files_dashboard.py` (حمولات ثابتة) و`ef_route_harness.py` (الصور + اختبار
الواجهة) — `EFPlatform` بيعدّل القوايم بعد الفعل (الصفّ يتشال أو يتنقل) عشان صورة «بعد» تبقى صادقة.

حالتين للخدمة (الجولة ٧ ب١):
  * `service_open=False` — الخدمة مقفولة للناس، والجسر **شغّال بالسرّ**: القوايم والرجوع والحسم شغّالين،
    و«ابعته لـ…»/النقل ⇒ ٤٠٩ `E_SERVICE_OFF`.
  * `deployed=False` — الجسر مش منشور على المنصة (الإنتاج النهارده): كل `/bridge/expert-files*` ٤٠٤ والطابور
    من غير مفاتيح الملفات خالص.
"""
import copy
import datetime
import threading
import time

_NOW = datetime.datetime.now(datetime.timezone.utc)
PLATFORM_EMAIL = "admin@platform.test"


def iso(hours_from_now=0.0):
    return (_NOW + datetime.timedelta(hours=hours_from_now)).isoformat()


# --------------------------------------------------------------------------- النصوص (بالحرف من المنصة)
STATUS_LABELS = {
    "draft": "مسودة", "awaiting_payment": "مستني الدفع", "awaiting_assignment": "بنختار لك خبير",
    "assigned": "بنختار لك خبير", "claimed": "الملف عند {name}", "writing": "الرأي بيتكتب",
    "needs_info": "محتاجين ردّك", "delivered": "رأيك جاهز", "disputed": "بنراجعها معاك",
    "closed": "خلص", "refunded": "فلوسك رجعت", "cancelled": "اتلغى",
}
TIER_LABELS = {"written": "رأي مكتوب", "written_session": "رأي مكتوب + جلسة ٣٠ دقيقة"}
LAW_LABELS = {"eg": "القانون المصري", "sa": "القانون السعودي"}
REASON_LABELS = {"unclear": "فيه حاجة مش فاهمها", "not_answered": "الرأي ما ردّش على سؤالي",
                 "wrong_facts": "فيه غلط في الوقائع"}
BLOCK_LABELS = {
    "refund_blocked_at": "عدّت ٤٨ ساعة وما حدّش استلم الملف، والفلوس ما رجعتش لوحدها — راجعها ورجّعها بإيدك",
    "release_blocked_at": "عدّت الـ٣ أيام والفلوس ما اتحوّلتش للخبير لوحدها — راجعها",
    "approval_blocked_at": "الخبير اعتمد الرأي والملف ما اتحرّكش — راجعه",
    "file_activation_blocked_at": "الفلوس وصلت ومش لاقيين الملف بتاعها — رجّعها للعميل",
}
FILE_BLOCK_STAMPS = ("refund_blocked_at", "release_blocked_at", "approval_blocked_at")
UNACTIVATED_LABEL = "اتدفع وما وصلش لقايمة التوزيع"
PRE_CLAIM = ("awaiting_assignment", "assigned")
EXPERT_WORK = ("claimed", "writing", "needs_info")
BEFORE_DELIVERY = PRE_CLAIM + EXPERT_WORK
TERMINAL = ("closed", "refunded", "cancelled")

E_NOT_FOUND = "الملف ده مش موجود"
E_SERVICE_OFF = "الخدمة مقفولة للناس دلوقتي — تقدر ترجّع الفلوس أو تحسم، بس ما ينفعش تبعت ملف لخبير"
E_MONEY_MOVED = "الفلوس اتحرّكت على الملف ده — حدّث الصفحة"
E_NOT_PAID_YET = "الملف ده لسه ما اتدفعش"
E_ALREADY_LISTED = "الملف ده وصل لقايمة التوزيع — رجّع فلوسه من صفّه"
E_REFUND_GATEWAY = "الفلوس رجعت من بوابة الدفع قبل كده"
E_REFUND_MANUAL = "الفلوس رجعت يدوي قبل كده"
E_RESOLVE_MISSING = "النزاع ده مش موجود — حدّث الصفحة"
E_RESOLVE_NOT_DISPUTED = "مفيش نزاع مستني قرار هنا — يمكن اتحسم قبل كده، حدّث الصفحة"
E_RESOLVE_MANUAL = "الفلوس دي رجعت للعميل يدوي قبل كده"
E_RESOLVE_GATEWAY = "الفلوس دي رجعت للعميل من بوابة الدفع قبل كده"

# الخبراء المعتمدين (pool) — `_candidates` بيرتّبهم: نفس بلد القانون الأول، بعدين اللي ما اعتذرش، بعدين بالاسم.
EXPERTS = {
    "hala@experts.test": ("أ. هالة سمير", "eg"),
    "nada@experts.test": ("د. ندى حسن", "eg"),
    "karim@experts.test": ("أ. كريم عادل", "eg"),
    "sami@experts.test": ("م. سامي فؤاد", "sa"),
    "faisal@experts.test": ("أ. فيصل العتيبي", "sa"),
}
CLIENT_EMAILS = {"F1": "mona@clients.test", "F2": "ahmed@clients.test", "F3": "yasmin@clients.test",
                 "F4": "hassan@clients.test", "F5": "tarek@clients.test", "F6": "nour@clients.test",
                 "F7": "walid@clients.test", "D1": "reem@clients.test"}


def candidates(law_country, declined=(), pool=None):
    out = []
    for email in (pool or EXPERTS):
        name, country = EXPERTS[email]
        out.append({"email": email, "name": name, "declined": email in declined,
                    "same_country": country == law_country})
    out.sort(key=lambda c: (not c["same_country"], c["declined"], c["name"]))
    return out


def _name(email):
    return EXPERTS[email][0] if email in EXPERTS else ""


def _release_amount(status, expert_email, expert_amount, amount):
    """`_release_amount` بالحرف: الفلوس لسه على بريد المنصة (قبل الاستلام) ⇒ None؛ وإلا أجر الخبير، ولو
    فاضي المبلغ كله."""
    if status in PRE_CLAIM or not expert_email:
        return None
    return expert_amount if expert_amount is not None else amount


def blocked_of(row, cons_stamp=None):
    """`_blocked` بالحرف — أختام الملف بالترتيب + ختم «مش لاقيين الملف» من الاستشارة."""
    out = [{"key": k, "at": row.get(k), "label": BLOCK_LABELS[k]} for k in FILE_BLOCK_STAMPS if row.get(k)]
    if cons_stamp:
        out.append({"key": "file_activation_blocked_at", "at": cons_stamp,
                    "label": BLOCK_LABELS["file_activation_blocked_at"]})
    return out


def _file(fid, *, title, status, law, tier, amount, currency, expert_amount, paid_h, deadline_h,
          client, counterparty="", flags=(), assigned_to=None, assigned_h=None, overdue=False,
          expert_email=None, writing_due_h=None, declined=(), dispute=None, pool=None, file_no=None,
          stamps=None):
    """صفّ `_bridge_row` بنفس المفاتيح والترتيب."""
    hours_left = round(max(0.0, deadline_h), 1)
    in_work = status in PRE_CLAIM + EXPERT_WORK
    expert_name = _name(expert_email) if expert_email else ""
    reason_label = REASON_LABELS.get((dispute or {}).get("reason") or "", "")
    stamps = dict(stamps or {})
    row = {
        "id": fid, "title": title, "status": status,
        "status_label": STATUS_LABELS.get(status, "").format(name=expert_name or "الخبير"), "file_no": file_no,
        "law_country": law, "law_label": LAW_LABELS[law], "tier": tier, "tier_label": TIER_LABELS[tier],
        "amount": amount, "currency": currency, "expert_amount": expert_amount,
        "platform_fee": (amount - expert_amount) if expert_amount is not None else None,
        "release_amount": _release_amount(status, expert_email, expert_amount, amount),
        "consultation_id": "c-" + fid,
        "paid_at": iso(paid_h), "claim_deadline_at": iso(deadline_h), "hours_left": hours_left,
        "assigned_to": assigned_to, "assigned_name": _name(assigned_to) if assigned_to else "",
        "assigned_at": iso(assigned_h) if assigned_h is not None else None,
        "assign_overdue": bool(overdue),
        "expert_email": expert_email, "expert_name": expert_name,
        "writing_due_at": iso(writing_due_h) if writing_due_h is not None else None,
        "declined": [{"email": e, "name": _name(e), "at": iso(-3), "reason": r} for e, r in declined],
        "client_first_name": client, "counterparty_name": counterparty, "price_flags": list(flags),
        "followup": None,
        "dispute": ({**dispute, "reason_label": reason_label} if dispute else None),
        "reason_label": reason_label,
        "refund_blocked_at": stamps.get("refund_blocked_at"), "release_blocked_at": stamps.get("release_blocked_at"),
        "approval_blocked_at": stamps.get("approval_blocked_at"), "file_activation_blocked_at": None,
        "blocked": [], "needs_attention": False,
        "candidates": candidates(law, [e for e, _ in declined], pool) if in_work else [],
    }
    row["blocked"] = blocked_of(row)
    row["needs_attention"] = bool(row["blocked"])
    return row


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
# الجولة ٧ (ب٩): فلوس اتوقّفت والكنسة ما قدرتش تحرّكها.
# F6 — رأي اتسلّم وعدّت الـ٣ أيام والتحويل للخبير اتوقّف: في فلتر `blocked` بس (مش في أي حارة تانية).
F6 = _file("ef-f6-5a6b7c8d", title="نفقة متجمدة من سنتين", status="delivered", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-170.0, deadline_h=-122.0, client="نور",
           counterparty="", expert_email="hala@experts.test", file_no=1037,
           stamps={"release_blocked_at": iso(-3.0)})
# F7 — عدّى ٤٨ ساعة وما حدّش استلمه، والرجوع التلقائي اتوقّف: في حارة `waiting` (الميعاد عدّى) وفي `blocked`.
F7 = _file("ef-f7-6b7c8d9e", title="حدود أرض مع الجار", status="awaiting_assignment", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-54.0, deadline_h=-6.0, client="وليد",
           counterparty="", stamps={"refund_blocked_at": iso(-5.0)})

D1 = _file("ef-d1-5f6a7b8c", title="حضانة بعد الطلاق", status="disputed", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-120.0, deadline_h=-72.0, client="ريم",
           counterparty="طليقي — أحمد فتحي", expert_email="nada@experts.test", file_no=1042,
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


# --------------------------------------------------------------------------- «اتدفع وما وصلش» (ب٢)
def _unact(cid, *, title, tier, amount, expert_amount, paid_h, client, file_id=None, file_found=False,
           file_on_this_payment=False, file_status=None, activation_blocked_h=None):
    """صفّ `_unactivated_rows` بالحرف — الصفّ هو **الفلوس** (الاستشارة)، والملف ممكن يكون مش لاقيينه."""
    stamp = iso(activation_blocked_h) if activation_blocked_h is not None else None
    return {
        "unactivated": True, "consultation_id": cid, "id": file_id if file_found else None,
        "file_id": file_id if file_found else None,
        "file_found": bool(file_found), "file_on_this_payment": bool(file_found and file_on_this_payment),
        "title": title, "status": file_status if file_found else None, "status_label": UNACTIVATED_LABEL,
        "tier": tier, "tier_label": TIER_LABELS.get(tier, ""),
        "amount": amount, "currency": "EGP", "expert_amount": expert_amount,
        "platform_fee": amount - expert_amount, "release_amount": None,
        "paid_at": iso(paid_h), "hours_since_paid": round(-paid_h, 1),
        "client_first_name": client, "file_activation_blocked_at": stamp,
        "blocked": blocked_of({}, stamp), "needs_attention": True,
    }


# U1 — الملف لاقيينه ولسه «مستني الدفع» مع إن الفلوس اتمسكت.
U1 = _unact("cu-u1-7c8d9e0f", title="توكيل عام لبيع عربية", tier="written", amount=500.0, expert_amount=300.0,
            paid_h=-3.0, client="مها", file_id="ef-u1-8d9e0f1a", file_found=True, file_on_this_payment=True,
            file_status="awaiting_payment")
# U2 — الفلوس وصلت ومش لاقيين الملف خالص، والكنسة ختمتها.
U2 = _unact("cu-u2-8d9e0f1b", title="ملف للخبير", tier="written_session", amount=1000.0, expert_amount=650.0,
            paid_h=-30.0, client="كريم", activation_blocked_h=-28.0)


def detail_view(row, client_email):
    """شكل `bridge_view(f, full=True)` — الملف كله + الأسماء + ملخّص الفلوس (ما اتغيّرش في الجولة ٧)."""
    out = {k: v for k, v in row.items() if k not in ("candidates", "hours_left", "assign_overdue",
                                                     "client_first_name", "blocked", "needs_attention",
                                                     "release_amount", "reason_label",
                                                     "file_activation_blocked_at")}
    out.update({
        "client_email": client_email, "facts": [], "questions": [],
        "opinion": None, "revision": None, "previous_experts": [],
        "docs": [], "client_name": row["client_first_name"] + " عبد الله",
        "money": {"consultation_id": row["consultation_id"], "status": "held", "escrow_state": "held",
                  "held_at": row["paid_at"], "delivered_at": None, "auto_release_at": None,
                  "payment_id": "pay-" + row["id"][:8], "on_platform": row["status"] in PRE_CLAIM},
    })
    return out


def bridge_reply(f, *, consultation_id=None, previous_expert_email=None, refund_reason=None, closed_by=None):
    """`bridge_reply` بالحرف (ب٨): نجح + الحالة + اللي الداشبورد بيكتبه في سجله بس — ⛔ ولا بيانات العميل."""
    status = f.get("status")
    expert_name = _name(f.get("expert_email")) if f.get("expert_email") else ""
    return {
        "ok": True, "id": f.get("id"), "consultation_id": consultation_id or f.get("consultation_id"),
        "status": status, "status_label": STATUS_LABELS.get(str(status or ""), "").format(name=expert_name or "الخبير"),
        "title": f.get("title"), "file_no": f.get("file_no"), "amount": f.get("amount"),
        "currency": f.get("currency") or None, "expert_amount": f.get("expert_amount"),
        "platform_fee": f.get("platform_fee"),
        "release_amount": (_release_amount(status, f.get("expert_email"), f.get("expert_amount"), f.get("amount"))
                           if status not in TERMINAL else None),
        "assigned_to": f.get("assigned_to"), "assigned_name": _name(f.get("assigned_to")) if f.get("assigned_to") else "",
        "expert_email": f.get("expert_email"), "expert_name": expert_name,
        "previous_expert_email": previous_expert_email, "refund_reason": refund_reason, "closed_by": closed_by,
    }


# --------------------------------------------------------------------------- نزاعات الاستشارات
def _cons(cid, *, title, kind, amount, expert_amount, client, client_email, expert_email, expert_name,
          disputed_from, reason, disputed_h, manual_refund=False, cancel=False, verified_by="",
          expert_file_id=None, dispute_code=None, payee_email=None, payee_name=None):
    """صفّ `bridge_list_consultations` بالحرف — الجولة ٧ (ب٦): `payee_email` · `payee_name` · `release_amount`
    · `reason_label`. المستفيد بنفس قرار `resolve_disputed`: اللي الفلوس باسمه، ولو توثيق على بريد المنصة واتوثّق
    ⇒ اللي وثّق، ولو ملف على بريد المنصة ⇒ مفيش."""
    payee = expert_email if payee_email is None else payee_email
    if payee_name is None:
        payee_name = "المنصة" if payee == PLATFORM_EMAIL else (expert_name if payee == expert_email else _name(payee))
    share = expert_amount if expert_amount is not None else amount
    return {
        "id": cid, "title": title, "kind": kind, "amount": amount, "currency": "EGP",
        "expert_amount": expert_amount, "platform_fee": (amount - expert_amount) if expert_amount is not None else None,
        "member_email": client_email, "expert_email": expert_email, "client_first_name": client,
        "expert_name": expert_name, "status": "disputed", "disputed_from": disputed_from,
        "dispute_reason": reason, "disputed_at": iso(disputed_h), "held_at": iso(disputed_h - 60),
        "delivered_at": iso(disputed_h - 10) if disputed_from == "delivered" else "",
        "payment_id": "pay-" + cid[:8], "cancel_requested": cancel, "cancel_full_refund": False,
        "manual_refund_settled_at": iso(disputed_h + 1) if manual_refund else "",
        "verified_by_email": verified_by,
        "payee_email": payee or None, "payee_name": payee_name if payee else "",
        "release_amount": share if payee else None,
        "reason_label": REASON_LABELS.get(dispute_code or "", ""),
        "expert_file_id": expert_file_id, "created_at": iso(disputed_h - 70),
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
                expert_file_id=D1["id"], dispute_code="not_answered")


def resolve_reply(c, status):
    """`bridge_resolve_reply` بالحرف (ب٨) — ⛔ من غير إيميل العميل ولا اسمه ولا ملاحظة الحسم ولا رقم الدفع."""
    return {"ok": True, "id": c["id"], "status": status, "kind": c["kind"], "title": c["title"],
            "amount": c["amount"], "currency": c["currency"], "expert_amount": c["expert_amount"],
            "platform_fee": c["platform_fee"], "expert_email": c["expert_email"], "expert_name": c["expert_name"]}


# --------------------------------------------------------------------------- الطابور (ب٣)
def _base_queue():
    return {
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


def queue_payload(*, to_assign=3, sent=1, overdue=1, late=1, disputed=1, blocked=2, unactivated=2,
                  awaiting_payment=3, open_total=10, consultation_disputes=2, service_open=True, deployed=True):
    """`GET /api/bridge/ops/queue` — `ops_queue_snapshot` + `consultation_disputes` من `bridge_ops_queue`، والتنبيهات
    بالحرف (f-strings المنصة بأرقام لاتيني، وبنفس الترتيب: الملفات، وبعدين نزاعات الاستشارات).
    `deployed=False` ⇒ الإنتاج النهارده: من غير أي مفتاح ملفات ولا نزاعات."""
    q = _base_queue()
    if not deployed:
        q["alerts"] = []
        return q
    q.update({"expert_files_service_open": service_open,
              "expert_files_waiting": to_assign + sent, "expert_files_awaiting_assignment": to_assign,
              "expert_files_assigned_unclaimed": sent, "expert_files_assign_overdue": overdue,
              "expert_files_late": late, "expert_files_disputed": disputed, "expert_files_blocked": blocked,
              "expert_files_open_total": open_total, "expert_files_unactivated": unactivated,
              "expert_files_awaiting_payment": awaiting_payment})
    stuck = ([f"⚠️ {unactivated} ملف اتدفع وما وصلش لقايمة التوزيع — راجعه من الداشبورد"]
             if unactivated else [])
    if not service_open:
        alerts = ([f"⚠️ {open_total} ملف مدفوع والميزة مقفولة — رجّع الفلوس أو احسم من الداشبورد، أو افتح المفتاح"]
                  if open_total else []) + stuck
    else:
        alerts = []
        if to_assign:
            alerts.append(f"📁 {to_assign} ملف مستني توزيع")
        if overdue:
            alerts.append(f"⏰ {overdue} ملف اتبعت لخبير وما اتستلمش من ١٢ ساعة")
        if late:
            alerts.append(f"⚠️ {late} رأي متأخر")
        if disputed:
            alerts.append(f"🛑 {disputed} ملف فيه ملاحظة مستنية قرارك")
        if blocked:
            alerts.append(f"⚠️ {blocked} ملف فلوسه ما اتحرّكتش لوحدها — محتاج تدخّلك")
        alerts += stuck
    q["consultation_disputes"] = consultation_disputes
    if consultation_disputes:
        alerts.append(f"🛑 {consultation_disputes} نزاع على استشارة مستني قرارك")
    q["alerts"] = alerts
    return q


def list_payload(status, files, service_open=True):
    return {"status": status, "files": files, "count": len(files), "total": len(files), "service_open": service_open}


def cons_payload(rows):
    return {"status": "disputed", "consultations": rows, "count": len(rows), "total": len(rows)}


NOT_FOUND = {"detail": "Not Found"}


class EFPlatform(object):
    """منصّة «ملف للخبير» صغيرة في الذاكرة. `handle(method, path, params, body)` ⇒ (status, payload).
    `deployed=False` ⇒ كل `/bridge/expert-files*` ٤٠٤ (الجسر مش منشور) والطابور من غير مفاتيح الملفات.
    `service_open=False` ⇒ الخدمة مقفولة للناس والجسر شغّال بالسرّ (الجولة ٧ ب١).
    `delay[(method, path)]` ثواني تأخير. `calls` = كل اللي اتطلب، بالترتيب (والجسم بالحرف — فيه `by`)."""

    def __init__(self, deployed=True, empty=False, cons_enabled=True, service_open=True):
        self.deployed = deployed
        self.service_open = service_open
        self.cons_enabled = cons_enabled
        self.lock = threading.Lock()
        self.calls = []
        self.delay = {}
        if empty:
            self.waiting, self.late, self.disputed, self.delivered, self.cons, self.unact = [], [], [], [], [], []
        else:
            self.waiting = [copy.deepcopy(f) for f in (F7, F2, F4, F3, F1)]   # بـclaim_deadline_at ↑
            self.late = [copy.deepcopy(F5)]
            self.disputed = [copy.deepcopy(D1)]
            self.delivered = [copy.deepcopy(F6)]                              # بيظهر في `blocked` بس
            self.cons = [copy.deepcopy(D1_CONS), copy.deepcopy(D2), copy.deepcopy(D3)]
            self.unact = [copy.deepcopy(U2), copy.deepcopy(U1)]               # بـheld_at ↑
        self.unact_done = set()
        self.awaiting_payment = 0 if empty else 3
        # تعديل الخبير على D1 (None = لسه ما عدّلش) · `detail_fail` = قراية الملف الجاية ترجع ٥٠٠ (مرة).
        self.d1_revision = copy.deepcopy(D1_REVISION)
        self.detail_fail = False

    # ---------------------------------------------------------------- مساعدات
    def _lanes(self):
        return (self.waiting, self.late, self.disputed, self.delivered)

    def _find(self, fid):
        for lane in self._lanes():
            for f in lane:
                if f["id"] == fid:
                    return lane, f
        return None, None

    def _blocked_rows(self):
        return [f for lane in self._lanes() for f in lane
                if f["status"] not in TERMINAL and any(f.get(k) for k in FILE_BLOCK_STAMPS)]

    def _detail(self, f):
        d = detail_view(f, CLIENT_EMAILS.get(self._key(f), "client@clients.test"))
        if f["id"] == D1["id"]:
            d["opinion"] = copy.deepcopy(D1_OPINION)
            d["revision"] = copy.deepcopy(self.d1_revision)
            d["docs"] = [{"id": "doc-1", "name": "حكم الطلاق.pdf", "content_type": "application/pdf",
                          "size": 120000, "stage": "draft", "created_at": iso(-130)}]
        return d

    @staticmethod
    def _key(f):
        for k, v in (("F1", F1), ("F2", F2), ("F3", F3), ("F4", F4), ("F5", F5), ("F6", F6), ("F7", F7),
                     ("D1", D1)):
            if v["id"] == f["id"]:
                return k
        return ""

    def queue(self):
        if not self.deployed:
            return queue_payload(deployed=False)
        to_assign = sum(1 for f in self.waiting if f["status"] == "awaiting_assignment")
        sent = sum(1 for f in self.waiting if f["status"] == "assigned")
        overdue = sum(1 for f in self.waiting if f["status"] == "assigned" and f["assign_overdue"])
        late, disputed = len(self.late), len(self.disputed)
        open_total = len(self.waiting) + late + disputed + len(self.delivered) + len(self.unact)
        regular = sum(1 for c in self.cons if c["kind"] != "expert_file")
        return queue_payload(to_assign=to_assign, sent=sent, overdue=overdue, late=late, disputed=disputed,
                             blocked=len(self._blocked_rows()), unactivated=len(self.unact),
                             awaiting_payment=self.awaiting_payment, open_total=open_total,
                             consultation_disputes=regular, service_open=self.service_open)

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
            if not self.deployed:
                return 404, NOT_FOUND
            return self._files(method, path, params, body)
        return None   # مش من شغلنا — الأداة بترد عليه

    def _files(self, method, path, params, body):
        parts = path[len("/api/bridge/expert-files"):].strip("/").split("/")
        if method == "GET" and parts == [""]:
            s = params.get("status") or "waiting"
            if s == "unactivated":
                return 200, list_payload(s, copy.deepcopy(self.unact), self.service_open)
            if s == "blocked":
                return 200, list_payload(s, copy.deepcopy(self._blocked_rows()), self.service_open)
            lane = {"waiting": self.waiting, "late": self.late, "disputed": self.disputed}.get(s)
            if lane is None:
                return 422, {"detail": [{"loc": ["query", "status"], "msg": "bad"}]}
            return 200, list_payload(s, copy.deepcopy(lane), self.service_open)
        if method == "POST" and len(parts) == 3 and parts[0] == "unactivated" and parts[2] == "refund":
            return self._refund_unactivated(parts[1])
        fid = parts[0]
        lane, f = self._find(fid)
        if f is None:
            return 404, {"detail": E_NOT_FOUND}
        if method == "GET" and len(parts) == 1:
            if self.detail_fail:
                self.detail_fail = False
                return 500, {"detail": "Internal Server Error"}
            return 200, self._detail(f)
        act = parts[1] if len(parts) > 1 else ""
        if act in ("assign", "reassign") and not self.service_open:
            return 409, {"detail": E_SERVICE_OFF}
        if act == "assign":
            if f["status"] not in PRE_CLAIM:
                return 409, {"detail": "الملف ده مش مستني توزيع"}
            target = (body.get("expert_email") or "").lower()
            if target not in EXPERTS:
                return 404, {"detail": "الخبير غير موجود أو غير معتمد"}
            if f["hours_left"] <= 0:
                return 409, {"detail": "فات ميعاد استلام الملف"}
            f.update({"status": "assigned", "assigned_to": target, "assigned_name": EXPERTS[target][0],
                      "assigned_at": iso(0), "assign_overdue": False,
                      "status_label": STATUS_LABELS["assigned"]})
            return 200, bridge_reply(f)
        if act == "reassign":
            if f["status"] not in EXPERT_WORK:
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
                      "release_amount": None, "status_label": STATUS_LABELS["assigned"]})
            self.waiting.append(f)
            return 200, bridge_reply(f, previous_expert_email=old)
        if act == "refund":
            if f["status"] not in BEFORE_DELIVERY:
                return 409, {"detail": "الاسترداد من هنا قبل تسليم الرأي بس"}
            lane.remove(f)
            f.update({"status": "refunded", "status_label": STATUS_LABELS["refunded"]})
            return 200, bridge_reply(f, refund_reason="founder")
        if act == "resolve":
            if f["status"] != "disputed":
                return 409, {"detail": "الملف ده مفيهوش ملاحظة مستنية قرار"}
            action = body.get("action")
            lane.remove(f)
            self.cons = [c for c in self.cons if c.get("expert_file_id") != fid]
            f.update({"status": "closed" if action == "release" else "refunded"})
            return 200, bridge_reply(f, refund_reason=None if action == "release" else "dispute",
                                     closed_by="founder_release" if action == "release" else None)
        return 404, NOT_FOUND

    def _refund_unactivated(self, cid):
        """`bridge_refund_unactivated` — نفس الحرّاس (مرة واحدة): التانية ⇒ ٤٠٩ «الفلوس اتحرّكت…»."""
        if cid in self.unact_done:
            return 409, {"detail": E_MONEY_MOVED}
        u = next((x for x in self.unact if x["consultation_id"] == cid), None)
        if u is None:
            return 404, {"detail": E_NOT_FOUND}
        self.unact.remove(u)
        self.unact_done.add(cid)
        if u["file_on_this_payment"]:
            self.awaiting_payment = max(0, self.awaiting_payment - 1)
        row = {"id": u["file_id"], "title": u["title"], "status": "refunded" if u["file_on_this_payment"] else None,
               "amount": u["amount"], "currency": u["currency"], "expert_amount": u["expert_amount"] if u["file_found"] else None,
               "platform_fee": u["platform_fee"] if u["file_found"] else None}
        out = bridge_reply(row, consultation_id=cid, refund_reason="founder" if u["file_on_this_payment"] else None)
        out.update({"unactivated": True, "money_status": "refunded"})
        return 200, out

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
                return 404, {"detail": E_RESOLVE_MISSING}
            action = body.get("action")
            if action == "refund" and c.get("manual_refund_settled_at"):
                return 409, {"detail": E_RESOLVE_MANUAL}
            if action == "release" and not c.get("payee_email"):
                return 409, {"detail": "الملف ما اتسلّمش لخبير — اختار رجّع الفلوس"}
            self.cons.remove(c)
            if c.get("expert_file_id"):
                lane, f = self._find(c["expert_file_id"])
                if f is not None:
                    lane.remove(f)
            return 200, resolve_reply(c, "released" if action == "release" else "refunded")
        return 404, NOT_FOUND
