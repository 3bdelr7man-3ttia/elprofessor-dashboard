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

الجولة ٨ (قرارات المؤسس — ريبو المنصة `docs/expert-files/SPEC-R8-DECISIONS.md` §٣، والكود على فرع
`expert-file-r8-decisions` هو الحَكَم: routes/expert_files.py `_bridge_row` · `bridge_list_files` · `bridge_review` ·
`_review_view` · `_pending_opinion` · `_require_can_assign` · `E_TRIAL_ONLY` · `E_REVIEW_*` · `ops_queue_snapshot`،
routes/consultations.py `_dispute_rows` · `release_block_full` · `E_RELEASE_*` · `bridge_list_legacy` · `decide_legacy` ·
`E_LEGACY_*`، routes/ops_bridge.py `bridge_consultations_legacy` · `bridge_decide_legacy` · `bridge_ops_queue`):
  * `r8=True` — بيزرع «مستنية مراجعتك» (R1 · R2) و«استشارات قديمة» (L1–L3). من غيره القوايم دي فاضية (صور
    واختبارات الجولات ٦–٧ زي ما هي).
  * `mode='allowlist'` + `allowlist=` — الخدمة مفتوحة للتجربة بس: التوزيع لخبير **وعميل** من القايمة، وإلا ٤٠٩
    `E_TRIAL_ONLY`.
  ⚑ مراجعة الجولة ٧ (`aef748c` · `f03ae6d`: كود سبب ختم الرجوع `refund_blocked` · `refund_blocked_reason` ·
    `REFUND_BLOCK_LABELS`) اتدمجت فوق الجولة ٨ على المنصة (`83f03f9`)، ومعاها مراجعة الجولة ٨ (`fee_accepted.written_only_amount`
    · جملة ختم الجلسة «راجع الدفع قبل ما ترجّع الفرق») — الأشكال هنا على `83f03f9` بالحرف.
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
    "needs_info": "محتاجين ردّك", "in_review": "بنراجع رأيك قبل ما يوصلك", "delivered": "رأيك جاهز",
    "disputed": "بنراجعها معاك", "closed": "خلص", "refunded": "فلوسك رجعت", "cancelled": "اتلغى",
}
TIER_LABELS = {"written": "رأي مكتوب", "written_session": "رأي مكتوب + جلسة ٣٠ دقيقة"}
LAW_LABELS = {"eg": "القانون المصري", "sa": "القانون السعودي"}
NEXT_STEP_LABELS = {"self": "تقدر تكمّلها بنفسك", "specialist": "محتاج حد متخصص يكمّل معاك",
                    "none": "مش محتاج حاجة دلوقتي"}
REASON_LABELS = {"unclear": "فيه حاجة مش فاهمها", "not_answered": "الرأي ما ردّش على سؤالي",
                 "wrong_facts": "فيه غلط في الوقائع"}
BLOCK_LABELS = {
    "refund_blocked_at": "عدّت ٤٨ ساعة وما حدّش استلم الملف، والفلوس ما رجعتش لوحدها — راجع الدفع قبل ما ترجّعها",
    "release_blocked_at": "عدّت الـ٣ أيام والفلوس ما اتحوّلتش للخبير لوحدها — راجعها",
    "approval_blocked_at": "الخبير اعتمد الرأي والملف ما اتحرّكش — راجعه",
    "file_activation_blocked_at": "الفلوس وصلت ومش لاقيين الملف بتاعها — رجّعها للعميل",
    # الجولة ٨ (البند ٦)
    "lapse_blocked_at": "الجلسة ما اتعملتش والفرق ما رجعش للعميل لوحده — راجع الدفع قبل ما ترجّع الفرق",
}
FILE_BLOCK_STAMPS = ("refund_blocked_at", "release_blocked_at", "approval_blocked_at", "lapse_blocked_at")
# مراجعة الجولة ٧ (SPEC المنصة §١٨-و): كود سبب وقوف الرجوع بيتخزّن مع الختم (`refund_blocked`)، وكل سبب ليه جملته
# (`refund_blocked_reason` على الصفّ = نفس `blocked[].label`).
REFUND_BLOCK_LABELS = {
    "missing": "عدّت ٤٨ ساعة وما حدّش استلم الملف، ومش لاقيين فلوسه على المنصة — راجع الدفع قبل ما ترجّع أي حاجة",
    "not_held": "عدّت ٤٨ ساعة وما حدّش استلم الملف، والفلوس مش محجوزة على المنصة — راجع الدفع قبل ما ترجّع أي حاجة",
    "mismatch": "عدّت ٤٨ ساعة والملف حالته مش متسقة مع فلوسه — راجعه قبل ما ترجّع أي حاجة",
    "gateway_refund": "الفلوس رجعت للعميل من بوابة الدفع — ما ترجّعهاش تاني",
    "gateway_partial": "بوابة الدفع رجّعت جزء من الفلوس للعميل — راجع اللي رجع قبل ما ترجّع أي حاجة",
    "manual_refund": "الفلوس رجعت للعميل يدوي قبل كده — ما ترجّعهاش تاني",
}
UNACTIVATED_LABEL = "اتدفع وما وصلش لقايمة التوزيع"
PRE_CLAIM = ("awaiting_assignment", "assigned")
EXPERT_WORK = ("claimed", "writing", "needs_info")
BEFORE_DELIVERY = PRE_CLAIM + EXPERT_WORK + ("in_review",)          # الجولة ٨: الرجوع بيقبل `in_review`
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
E_RESOLVE_ACTION = "اختار: للخبير ولا للعميل"
E_CLOSED = "الملف ده اتقفل"
# الجولة ٨ (البند ٥): «للخبير» بعد ما العميل خد فلوسه ⇒ مرفوض والفلوس فاضلة محجوزة — consultations.py بالحرف.
E_RELEASE_MANUAL = ("العميل خد فلوسه يدوي قبل كده، فمفيش تحويل للخبير من هنا. "
                    "الفلوس فاضلة محجوزة لحد ما المشكلة تتحل")
E_RELEASE_GATEWAY = ("العميل خد فلوسه من بوابة الدفع قبل كده، فمفيش تحويل للخبير من هنا. "
                     "الفلوس فاضلة محجوزة لحد ما المشكلة تتحل")
E_RELEASE_UNCLAIMED = "الملف ما اتسلّمش لخبير — اختار رجّع الفلوس"
RELEASE_BLOCK_TEXT = {"manual_refund": E_RELEASE_MANUAL, "gateway_refund": E_RELEASE_GATEWAY,
                      "not_claimed": E_RELEASE_UNCLAIMED}
# الجولة ٨ (البند ٧): مراجعة المؤسس — expert_files.py بالحرف.
E_REVIEW_NOT_WAITING = "الملف ده مش مستني مراجعة — حدّث الصفحة"
E_REVIEW_NOTE = "اكتب ملاحظة للخبير"
E_REVIEW_RETURNED = "رجّعته للخبير قبل كده — وافق عليه أو رجّع الفلوس للعميل"
E_REVIEW_SLOTS = "مواعيد الجلسة قربت أو عدّت — رجّعه للخبير يحط مواعيد جديدة"
E_REVIEW_ACTION = "اختار: وافق ولا رجّعه للخبير"
REVIEW_SLOTS_NOTE = "مواعيد الجلسة قربت أو عدّت — حط ٣ مواعيد جديدة وابعته تاني"
# الجولة ٨ (البند ١٣): الخدمة مفتوحة للتجربة بس.
E_TRIAL_ONLY = "الخدمة مفتوحة للتجربة بس — ابعته لخبير من قايمة التجربة"
# الجولة ٨ (البند ١٤): «استشارات قديمة محتاجة قرارك» — consultations.py بالحرف.
E_LEGACY_MISSING = "الاستشارة دي مش موجودة — حدّث الصفحة"
E_LEGACY_SETTLED = "الاستشارة دي اتسوّت قبل كده — حدّث الصفحة"
E_LEGACY_NOT_LEGACY = "دي مش من الاستشارات القديمة — بتتحرّر لوحدها بعد مهلتها"
E_LEGACY_FILE = "ده ملف للخبير — قراره من صفّه"
E_LEGACY_CANCELLED = "الحجز ده اتلغى — فلوسه في قايمة الاسترداد اليدوي"

# الخبراء المعتمدين (pool) — `_candidates` بيرتّبهم: نفس بلد القانون الأول، بعدين اللي ما اعتذرش، بعدين بالاسم.
EXPERTS = {
    "hala@experts.test": ("أ. هالة سمير", "eg"),
    "nada@experts.test": ("د. ندى حسن", "eg"),
    "karim@experts.test": ("أ. كريم عادل", "eg"),
    "sami@experts.test": ("م. سامي فؤاد", "sa"),
    "faisal@experts.test": ("أ. فيصل العتيبي", "sa"),
}
# خبراء جداد (أول ملفاتهم بتعدّي على المؤسس — الجولة ٨ البند ٧). برّه `EXPERTS` عمدًا: قايمة المرشّحين في صفوف
# الجولات ٦–٧ تفضل زي ما هي.
NEW_EXPERTS = {
    "rana@experts.test": ("أ. رنا عادل", "eg"),
    "wael@experts.test": ("أ. وائل منصور", "eg"),
}
CLIENT_EMAILS = {"F1": "mona@clients.test", "F2": "ahmed@clients.test", "F3": "yasmin@clients.test",
                 "F4": "hassan@clients.test", "F5": "tarek@clients.test", "F6": "nour@clients.test",
                 "F7": "walid@clients.test", "D1": "reem@clients.test", "R1": "samar@clients.test",
                 "R2": "dina@clients.test"}
# قايمة التجربة (`EXPERT_FILES_ALLOWLIST` — الجولة ٨ البند ١٣): هالة وندى + عميلة F1 وعميلة F3.
ALLOWLIST = frozenset({"hala@experts.test", "nada@experts.test", "mona@clients.test", "yasmin@clients.test"})


def candidates(law_country, declined=(), pool=None):
    out = []
    for email in (pool or EXPERTS):
        name, country = EXPERTS[email]
        out.append({"email": email, "name": name, "declined": email in declined,
                    "same_country": country == law_country})
    out.sort(key=lambda c: (not c["same_country"], c["declined"], c["name"]))
    return out


def _name(email):
    if email in EXPERTS:
        return EXPERTS[email][0]
    return NEW_EXPERTS[email][0] if email in NEW_EXPERTS else ""


def _release_amount(status, expert_email, expert_amount, amount):
    """`_release_amount` بالحرف: الفلوس لسه على بريد المنصة (قبل الاستلام) ⇒ None؛ وإلا أجر الخبير، ولو
    فاضي المبلغ كله."""
    if status in PRE_CLAIM or not expert_email:
        return None
    return expert_amount if expert_amount is not None else amount


def block_label(row, key):
    """`_block_label` بالحرف: ختم الرجوع بجملة سببه، وسبب مش معروف ⇒ الجملة العامة."""
    if key == "refund_blocked_at":
        return REFUND_BLOCK_LABELS.get(row.get("refund_blocked") or "", BLOCK_LABELS[key])
    return BLOCK_LABELS[key]


def blocked_of(row, cons_stamp=None):
    """`_blocked` بالحرف — أختام الملف بالترتيب + ختم «مش لاقيين الملف» من الاستشارة."""
    out = [{"key": k, "at": row.get(k), "label": block_label(row, k)} for k in FILE_BLOCK_STAMPS if row.get(k)]
    if cons_stamp:
        out.append({"key": "file_activation_blocked_at", "at": cons_stamp,
                    "label": BLOCK_LABELS["file_activation_blocked_at"]})
    return out


def release_block(status, expert_email, money_back=None):
    """`release_block_full` بالحرف على صفّ ملف: الفلوس رجعت للعميل (يدوي / البوابة — البوابة بتتقري للمتنازع عليه بس)
    ⇒ السبب · الفلوس لسه على بريد المنصة (ما حدّش استلم) ⇒ `not_claimed` · غير كده ⇒ (None, None)."""
    if money_back == "manual_refund" or (money_back == "gateway_refund" and status == "disputed"):
        return money_back, RELEASE_BLOCK_TEXT[money_back]
    if status in PRE_CLAIM or not expert_email:
        return "not_claimed", E_RELEASE_UNCLAIMED
    return None, None


# أجر الرأي المكتوب لوحده في درجة الجلسة (من السعر المتثبّت — جدول المؤسس: مصر ٥٠٠/٣٠٠ · السعودية والإمارات وقطر ٣٠٠/١٨٠ ·
# الدولار ٥٠/٣٠) — مراجعة الجولة ٨ (م٧): `fee_accepted.written_only_amount` بيتختم وقت الاستلام.
WRITTEN_EXPERT_FEE = {"EGP": 300.0, "SAR": 180.0, "AED": 180.0, "QAR": 180.0, "USD": 30.0}


def _fee_accepted(tier, expert_amount, currency, paid_h, expert_email):
    """`fee_accepted` على الملف (الجولة ٨ البند ١٢ + مراجعتها م٧): الأجر الثابت اللي وافق عليه وقت الاستلام."""
    if not expert_email:
        return None
    out = {"amount": expert_amount, "currency": currency, "at": iso(paid_h + 6)}
    if tier == "written_session" and currency in WRITTEN_EXPERT_FEE:
        out["written_only_amount"] = WRITTEN_EXPERT_FEE[currency]
    return out


def review_view(review):
    """`_review_view` بالحرف."""
    if not review:
        return None
    return {"submitted_at": review.get("submitted_at"), "round": review.get("round") or 0,
            "returns": review.get("returns") or 0, "returned_at": review.get("returned_at"),
            "note": review.get("note") or "", "approved_at": review.get("approved_at")}


def _file(fid, *, title, status, law, tier, amount, currency, expert_amount, paid_h, deadline_h,
          client, counterparty="", flags=(), assigned_to=None, assigned_h=None, overdue=False,
          expert_email=None, writing_due_h=None, declined=(), dispute=None, pool=None, file_no=None,
          stamps=None, review=None, pending_opinion=None, delivered_count=0, money_back=None):
    """صفّ `_bridge_row` بنفس المفاتيح والترتيب (مفاتيح الجولة ٨ الأول — SPEC-R8-DECISIONS §٣-١)."""
    hours_left = round(max(0.0, deadline_h), 1)
    in_work = status in PRE_CLAIM + EXPERT_WORK + ("in_review",)
    expert_name = _name(expert_email) if expert_email else ""
    reason_label = REASON_LABELS.get((dispute or {}).get("reason") or "", "")
    stamps = dict(stamps or {})
    block_key, block_text = release_block(status, expert_email, money_back)
    row = {
        # الجولة ٨ — أشكال الجسر الجديدة
        "review": review_view(review),
        "pending_opinion": copy.deepcopy(pending_opinion) if status == "in_review" else None,
        "expert_delivered_count": delivered_count if expert_email else 0,
        "release_blocked": block_key, "release_blocked_reason": block_text,
        "session_refund": None, "fee_accepted": _fee_accepted(tier, expert_amount, currency, paid_h, expert_email),
        "lapse_blocked_at": stamps.get("lapse_blocked_at"),
        "price_source": "ip", "price_ip_country": law, "price_phone_country": law,
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
        "refund_blocked_at": stamps.get("refund_blocked_at"), "refund_blocked": stamps.get("refund_blocked"),
        "refund_blocked_reason": None, "release_blocked_at": stamps.get("release_blocked_at"),
        "approval_blocked_at": stamps.get("approval_blocked_at"), "file_activation_blocked_at": None,
        "blocked": [], "needs_attention": False,
        "candidates": candidates(law, [e for e, _ in declined], pool) if in_work else [],
    }
    row["blocked"] = blocked_of(row)
    row["needs_attention"] = bool(row["blocked"])
    if row["refund_blocked_at"]:
        row["refund_blocked_reason"] = block_label(row, "refund_blocked_at")
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
           stamps={"release_blocked_at": iso(-4.0)})
# F7 — عدّى ٤٨ ساعة وما حدّش استلمه، والرجوع التلقائي اتوقّف (الفلوس مش محجوزة): في حارة `waiting` (الميعاد عدّى) وفي `blocked`.
F7 = _file("ef-f7-6b7c8d9e", title="حدود أرض مع الجار", status="awaiting_assignment", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-54.0, deadline_h=-6.0, client="وليد",
           counterparty="", stamps={"refund_blocked_at": iso(-5.0), "refund_blocked": "not_held"})


def sent_inside_12h(row, expert="hala@experts.test", hours_ago=2.0):
    """نسخة من صفّ «مستني توزيع» اتبعت لخبير من ساعتين (لسه في الـ١٢ ساعة بتوعه) — شكل المنصة بعد `assign`."""
    out = copy.deepcopy(row)
    out.update({"status": "assigned", "assigned_to": expert, "assigned_name": _name(expert),
                "assigned_at": iso(-hours_ago), "assign_overdue": False, "status_label": STATUS_LABELS["assigned"]})
    return out


def money_already_back(row, reason="manual_refund", hours_ago=5.0):
    """نسخة من صفّ قبل الاستلام الكنسة ختمته لأن الفلوس رجعت للعميل قبل كده (يدوي/البوابة) — بجملة سببه."""
    out = copy.deepcopy(row)
    out.update({"refund_blocked_at": iso(-hours_ago), "refund_blocked": reason})
    out["refund_blocked_reason"] = block_label(out, "refund_blocked_at")
    out["blocked"] = blocked_of(out)
    out["needs_attention"] = bool(out["blocked"])
    return out


def release_locked(row, reason="manual_refund"):
    """الجولة ٨ (البند ٥): نسخة من صفّ نزاع (ملف أو استشارة) العميل خد فلوسه فيه قبل كده (يدوي/البوابة) ⇒ المنصة بتبعت
    `release_blocked` + جملته، و«للخبير» مرفوض والفلوس فاضلة محجوزة."""
    out = copy.deepcopy(row)
    out.update({"release_blocked": reason, "release_blocked_reason": RELEASE_BLOCK_TEXT[reason]})
    return out

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


# --------------------------------------------------------------------------- «مستنية مراجعتك» (الجولة ٨ البند ٧)
def _pending(answers, next_step, note="", slots=(), meeting_url=""):
    """`_pending_opinion` بالحرف (من `approval`): الإجابات · الخطوة الجاية بكلامها · المواعيد · اللينك."""
    return {"answers": [{"question_id": "q%d" % (k + 1), "question": q, "text": t} for k, (q, t) in enumerate(answers)],
            "next_step": next_step, "next_step_label": NEXT_STEP_LABELS.get(next_step, ""),
            "next_step_note": note,
            "slots": [{"start_at": iso(h), "end_at": iso(h + 0.5)} for h in slots], "meeting_url": meeting_url}


R1_OPINION = _pending(
    [("أقدر آخد تعويض من شركة التأمين ولا لازم من السواق؟",
      "التعويض بيترفع على شركة التأمين مباشرة بوثيقة التأمين الإجباري على العربية، ومش لازم الحكم الجنائي على "
      "السواق يصدر الأول. الوثيقة بتغطي الإصابة لحد مبلغ محدد، ولو الضرر أكبر من كده الباقي بيترفع على السواق "
      "وصاحب العربية."),
     ("فيه ميعاد لازم أرفع فيه الدعوى قبله؟",
      "أيوه. دعوى التعويض على شركة التأمين بتسقط بعد ٣ سنين من يوم الحادثة. تقرير المستشفى ومحضر الشرطة لازم "
      "يكونوا جاهزين لأنهم أساس الدعوى.")],
    "specialist", "محامي تعويضات يرفع الدعوى ويتابع تقرير الطب الشرعي.")
# R1 — أول ملف للخبيرة الجديدة رنا (اتسلّمها صفر قبل كده)، بعتته للمراجعة من ٣ ساعات.
R1 = _file("ef-r1-9a0b1c2d", title="تعويض عن حادثة عربية", status="in_review", law="eg", tier="written",
           amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-70.0, deadline_h=-22.0, client="سمر",
           counterparty="شركة التأمين الأهلية", expert_email="rana@experts.test", writing_due_h=20.0,
           review={"submitted_at": iso(-3.0), "round": 1, "returns": 0, "returned_at": None, "note": "",
                   "approved_at": None},
           pending_opinion=R1_OPINION, delivered_count=0)
R2_OPINION = _pending(
    [("لو الخطوبة اتفسخت، الشبكة بتفضل مع مين؟",
      "الشبكة في الغالب بتتعامل كهدية مرتبطة بالجواز. اللي فسخ من غير سبب مقبول ما يقدرش يطالب برجوعها، والطرف "
      "التاني يحتفظ بيها — وده اللي أغلب المحاكم ماشية عليه."),
     ("والهدايا التانية والمصاريف؟",
      "الهدايا اللي بتتستهلك (أكل وورد) ما بترجعش. الأجهزة والحاجات الغالية بتتعامل زي الشبكة: حسب مين اللي فسخ "
      "وليه. ومصاريف الفرح ممكن تتطالب بيها لو فيه ضرر واضح من الفسخ.")],
    "specialist", "محامي أحوال شخصية يقدّر قيمة الشبكة ويرفع دعوى الاسترداد لو احتاجت.",
    slots=(30.0, 54.0, 78.0), meeting_url="https://meet.example.test/wael-session")
# R2 — رأي + جلسة لخبير جديد (اتسلّمله ملف واحد قبل كده): المؤسس رجّعه مرة بملاحظة، والخبير عدّله وبعته تاني.
R2 = _file("ef-r2-0b1c2d3e", title="فسخ خطوبة واسترداد الشبكة", status="in_review", law="eg", tier="written_session",
           amount=1000.0, currency="EGP", expert_amount=650.0, paid_h=-96.0, deadline_h=-48.0, client="دينا",
           counterparty="أسرة الخطيب", expert_email="wael@experts.test", writing_due_h=10.0,
           review={"submitted_at": iso(-1.5), "round": 2, "returns": 1, "returned_at": iso(-20.0),
                   "note": "الإجابة التانية محتاجة توضّح مين اللي فسخ الخطوبة وده بيفرق إزاي في الشبكة.",
                   "approved_at": None},
           pending_opinion=R2_OPINION, delivered_count=1)
# رسالة الخبير الصوتية (الجولة ١٢) — بايتات webm مزيّفة (EBML في الأول بس، ولا مزوّد ولا تحويل). R1 فيها صوت،
# و R2 «ملف قديم» من غير صوت (بيتسلّم عادي ومفيش مشغّل). شكل `voice` في تفاصيل الجسر بالحرف من مواصفة R12 §١-د.
VOICE_BYTES = b"\x1aE\xdf\xa3" + b"fake-voice-bytes-for-tests" * 20
VOICE_META = {"duration_sec": 102, "size": len(VOICE_BYTES), "content_type": "audio/webm"}
VOICE_FILES = {R1["id"]}
# اللي الدرج محتاجه من قراية الملف كله (`bridge_view`) عشان «مبني على» — نفس `build_based_on` على المنصة.
REVIEW_DETAIL = {
    R1["id"]: {"facts_confirmed_at": iso(-74.0), "client_name": "سمر ماهر", "additions": [], "info": None,
               "docs": [{"id": "doc-r1-1", "name": "محضر الشرطة.pdf", "content_type": "application/pdf", "size": 90000,
                         "stage": "draft", "created_at": iso(-75.0), "reading": ""},
                        {"id": "doc-r1-2", "name": "تقرير المستشفى.jpg", "content_type": "image/jpeg", "size": 240000,
                         "stage": "draft", "created_at": iso(-75.0), "reading": ""}]},
    R2["id"]: {"facts_confirmed_at": iso(-100.0), "client_name": "دينا السيد",
               "additions": [{"at": iso(-60.0), "items": [{"question": "الخطوبة اتفسخت إمتى؟",
                                                            "answer_text": "من شهرين."}]}],
               "info": {"status": "answered", "questions": [{"id": "i1", "text": "الخطوبة اتفسخت إمتى؟"}]},
               "docs": []},
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
U2 = _unact("cu-u2-8d9e0f1b", title="فسخ عقد إيجار محل", tier="written_session", amount=1000.0, expert_amount=650.0,
            paid_h=-30.0, client="كريم", activation_blocked_h=-28.0)


_ROW_ONLY = ("candidates", "hours_left", "assign_overdue", "client_first_name", "blocked", "needs_attention",
             "release_amount", "reason_label", "file_activation_blocked_at",
             # مفاتيح صفّ الجولة ٨ اللي `_bridge_row` بيحسبها (مش على الملف نفسه)
             "expert_delivered_count", "release_blocked", "release_blocked_reason", "session_refund",
             "price_source", "price_ip_country", "price_phone_country")


def detail_view(row, client_email):
    """شكل `bridge_view(f, full=True)` — الملف كله (فيه `price` و`approval` الخام) + الأسماء + ملخّص الفلوس (فيه
    `release_blocked*` من الجولة ٨) + `review` + `pending_opinion`."""
    out = {k: v for k, v in row.items() if k not in _ROW_ONLY}
    po = row.get("pending_opinion")
    out.update({
        "client_email": client_email, "facts": [], "questions": [],
        "opinion": None, "revision": None, "previous_experts": [],
        "docs": [], "client_name": row["client_first_name"] + " عبد الله",
        "price": {"country": row["law_country"], "currency": row["currency"], "source": "ip",
                  "ip_country": row["law_country"], "phone_country": row["law_country"]},
        "facts_confirmed_at": iso(-80.0), "additions": [], "info": None,
        "money": {"consultation_id": row["consultation_id"], "status": "held", "escrow_state": "held",
                  "held_at": row["paid_at"], "delivered_at": None, "auto_release_at": None,
                  "payment_id": "pay-" + row["id"][:8], "on_platform": row["status"] in PRE_CLAIM,
                  "release_blocked": row.get("release_blocked"),
                  "release_blocked_reason": row.get("release_blocked_reason")},
        "review": copy.deepcopy(row.get("review")), "pending_opinion": copy.deepcopy(po),
    })
    if po:
        # الخام على الملف (`approval`) — `bridge_view` بيرجّع الملف كله.
        out["approval"] = {"answers": copy.deepcopy(po["answers"]), "next_step": po["next_step"],
                           "next_step_note": po["next_step_note"], "slots": copy.deepcopy(po["slots"]),
                           "meeting_url": po["meeting_url"], "at": (row.get("review") or {}).get("submitted_at")}
    out["voice"] = copy.deepcopy(VOICE_META) if row["id"] in VOICE_FILES else None
    out.update(copy.deepcopy(REVIEW_DETAIL.get(row["id"], {})))      # (REVIEW_DETAIL ممكن يفرض `voice` تاني لاختبار شكل غلط)
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
def cons_release_block(kind, expert_email, manual_refund=False, gateway=False):
    """`release_block_full(…, gateway=True)` بالحرف على صفّ استشارة: يدوي ⇒ البوابة ⇒ ملف لسه على بريد المنصة."""
    if manual_refund:
        return "manual_refund", E_RELEASE_MANUAL
    if gateway:
        return "gateway_refund", E_RELEASE_GATEWAY
    if kind == "expert_file" and expert_email == PLATFORM_EMAIL:
        return "not_claimed", E_RELEASE_UNCLAIMED
    return None, None


def _cons(cid, *, title, kind, amount, expert_amount, client, client_email, expert_email, expert_name,
          disputed_from, reason, disputed_h, manual_refund=False, cancel=False, verified_by="",
          expert_file_id=None, dispute_code=None, payee_email=None, payee_name=None, gateway=False):
    """صفّ `bridge_list_consultations` (`_dispute_rows`) بالحرف — الجولة ٧ (ب٦): `payee_email` · `payee_name` ·
    `release_amount` · `reason_label`. المستفيد بنفس قرار `resolve_disputed`: اللي الفلوس باسمه، ولو توثيق اتوثّق من
    حد تاني ⇒ اللي وثّق، ولو ملف على بريد المنصة ⇒ مفيش. الجولة ٨ (البند ٥): `release_blocked` + جملته."""
    payee = expert_email if payee_email is None else payee_email
    if payee_name is None:
        payee_name = "المنصة" if payee == PLATFORM_EMAIL else (expert_name if payee == expert_email else _name(payee))
    share = expert_amount if expert_amount is not None else amount
    block_key, block_text = cons_release_block(kind, expert_email, manual_refund, gateway)
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
        "release_blocked": block_key, "release_blocked_reason": block_text,
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


# --------------------------------------------------------------------------- «استشارات قديمة محتاجة قرارك» (الجولة ٨ البند ١٤)
LEGACY_SINCE = iso(-2.0)       # ختم أول تشغيل (النشر من ساعتين) — اللي اتمسك قبله قديم


def _legacy(cid, *, title, kind, amount, expert_amount, client, client_email, expert_email, expert_name,
            delivered_h, delivered_by="expert", manual_refund=False, gateway=False):
    """صفّ `bridge_list_legacy` بالحرف: نفس صفّ النزاع (`_dispute_rows`) + `legacy` · `delivered_by` ·
    `auto_release_at` · `due` · `refund_blocked` · `refund_blocked_reason`."""
    share = expert_amount if expert_amount is not None else amount
    block_key, block_text = cons_release_block(kind, expert_email, manual_refund, gateway)
    refund_key = "manual_refund" if manual_refund else ("gateway_refund" if block_key == "gateway_refund" else None)
    auto_h = delivered_h + 72.0
    return {
        "id": cid, "title": title, "kind": kind, "amount": amount, "currency": "EGP",
        "expert_amount": expert_amount, "platform_fee": (amount - expert_amount) if expert_amount is not None else None,
        "member_email": client_email, "expert_email": expert_email, "client_first_name": client,
        "expert_name": expert_name, "status": "delivered", "disputed_from": "", "dispute_reason": "",
        "disputed_at": "", "held_at": iso(delivered_h - 30.0), "delivered_at": iso(delivered_h),
        "payment_id": "pay-" + cid[:8], "cancel_requested": False, "cancel_full_refund": False,
        "manual_refund_settled_at": iso(delivered_h + 5.0) if manual_refund else "",
        "verified_by_email": expert_email if kind == "expert_opinion" else "",
        "payee_email": expert_email, "payee_name": expert_name, "release_amount": share,
        "release_blocked": block_key, "release_blocked_reason": block_text,
        "reason_label": "", "expert_file_id": None, "created_at": iso(delivered_h - 40.0),
        "legacy": True, "delivered_by": delivered_by, "auto_release_at": iso(auto_h), "due": auto_h <= 0,
        "refund_blocked": refund_key,
        "refund_blocked_reason": {"manual_refund": E_RESOLVE_MANUAL,
                                  "gateway_refund": E_RESOLVE_GATEWAY}.get(refund_key) if refund_key else None,
    }


# L1 — استشارة سوق اتسلّمت من ٩ أيام: ميعاد التحويل عدّى والفلوس ما اتحرّكتش (قديمة).
L1 = _legacy("cs-l1-1c2d3e4f", title="صياغة عقد عمل لموظف جديد", kind="consultation", amount=600, expert_amount=480,
             client="سلمى", client_email="salma@clients.test", expert_email="amr@experts.test",
             expert_name="أ. عمرو الشريف", delivered_h=-216.0)
# L2 — جلسة اتسلّمت والفلوس رجعت للعميل يدوي قبل كده ⇒ «للخبير» و«للعميل» الاتنين مقفولين بسبب المنصة.
L2 = _legacy("cs-l2-2d3e4f5a", title="جلسة عن تأسيس شركة ذات مسؤولية محدودة", kind="session", amount=400,
             expert_amount=320, client="مروان", client_email="marwan@clients.test", expert_email="hala@experts.test",
             expert_name="أ. هالة سمير", delivered_h=-120.0, manual_refund=True)
# L3 — توثيق رأي اتسلّم من يومين (ميعاد التحويل لسه ما جاش — بس قديمة فمش هتتحرّك لوحدها).
L3 = _legacy("cs-l3-3e4f5a6b", title="توثيق رأي في عقد بيع شقة", kind="expert_opinion", amount=250, expert_amount=150,
             client="ياسر", client_email="yasser@clients.test", expert_email="nada@experts.test",
             expert_name="د. ندى حسن", delivered_h=-40.0, delivered_by="verify_verdict")


def legacy_payload(rows):
    """`GET /api/bridge/consultations/legacy` بالحرف."""
    return {"since": LEGACY_SINCE, "consultations": rows, "count": len(rows), "total": len(rows)}


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
                  awaiting_payment=3, open_total=10, consultation_disputes=2, service_open=True, deployed=True,
                  in_review=0, legacy=0, mode=None, allowlist_size=0):
    """`GET /api/bridge/ops/queue` — `ops_queue_snapshot` + `consultation_disputes` + `consultations_legacy` من
    `bridge_ops_queue`، والتنبيهات بالحرف (f-strings المنصة بأرقام لاتيني، وبنفس الترتيب: الملفات، وبعدين نزاعات
    الاستشارات، وبعدين القديمة). `deployed=False` ⇒ الإنتاج النهارده: من غير أي مفتاح ملفات ولا نزاعات.
    الجولة ٨: `mode` = open | allowlist | closed (افتراضه من `service_open`) — القايمة المسموحة تنبيهاتها زي المفتوح."""
    q = _base_queue()
    if not deployed:
        q["alerts"] = []
        return q
    mode = mode or ("open" if service_open else "closed")
    q.update({"expert_files_service_open": service_open, "expert_files_service_mode": mode,
              "expert_files_allowlist_size": allowlist_size, "expert_files_in_review": in_review,
              "expert_files_waiting": to_assign + sent, "expert_files_awaiting_assignment": to_assign,
              "expert_files_assigned_unclaimed": sent, "expert_files_assign_overdue": overdue,
              "expert_files_late": late, "expert_files_disputed": disputed, "expert_files_blocked": blocked,
              "expert_files_open_total": open_total, "expert_files_unactivated": unactivated,
              "expert_files_awaiting_payment": awaiting_payment})
    stuck = ([f"⚠️ {unactivated} ملف اتدفع وما وصلش لقايمة التوزيع — راجعه من الداشبورد"]
             if unactivated else [])
    if mode == "closed":
        alerts = ([f"⚠️ {open_total} ملف مدفوع والميزة مقفولة — رجّع الفلوس أو احسم من الداشبورد، أو افتح المفتاح"]
                  if open_total else []) + stuck
    else:
        alerts = []
        if in_review:
            alerts.append(f"🔎 {in_review} رأي مستني مراجعتك قبل ما يوصل للعميل")
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
    q["consultations_legacy"] = legacy
    q["escrow_auto_release_since"] = LEGACY_SINCE
    if consultation_disputes:
        alerts.append(f"🛑 {consultation_disputes} نزاع على استشارة مستني قرارك")
    if legacy:
        alerts.append(f"🗂️ {legacy} استشارة قديمة اتسلّمت ومستنية قرارك — للخبير ولا للعميل")
    q["alerts"] = alerts
    return q


def list_payload(status, files, service_open=True, mode=None, allowlist_size=0):
    """`bridge_list_files` بالحرف — من الجولة ٨ فيه وضع الخدمة (`service_mode`) وعدد قايمة التجربة."""
    return {"status": status, "files": files, "count": len(files), "total": len(files), "service_open": service_open,
            "service_mode": mode or ("open" if service_open else "closed"), "allowlist_size": allowlist_size}


def cons_payload(rows):
    return {"status": "disputed", "consultations": rows, "count": len(rows), "total": len(rows)}


NOT_FOUND = {"detail": "Not Found"}

# --------------------------------------------------------------------------- الجولة ١٣: المستعجل + عرض سعر القضية
# أشكال الجسر الجديدة (ريبو المنصة docs/expert-files/SPEC-R13-URGENT-CASE.md §١ و§٣): `speed` و`urgent` على صفّ الملف،
# و`case` {quote, quotes[], milestones[]} على الملف، و`POST …/case/milestones/{n}/resolve`، وفلاتر القايمة
# `urgent` · `case_disputed` · `case_open`. الأسماء والأرقام متخيّلة. `EFPlatform(r13=True)` بيزرعهم.
E_CASE_MS_MISSING = "المرحلة دي مش موجودة"
E_CASE_NOT_DISPUTED = "المرحلة دي مفيهاش ملاحظة مستنية قرار — يمكن اتحسمت قبل كده، حدّث الصفحة"
E_CASE_RELEASE_MANUAL = "العميل خد فلوس المرحلة دي قبل كده، فمفيش تحويل للخبير من هنا"


def urgent_view(state, *, start_h, due_h, refunded=None, fell_back_h=None, started_h=None):
    """`urgent` على الملف (SPEC-R13 §١)."""
    return {"start_by": iso(start_h), "due_at": iso(due_h), "state": state, "refunded": refunded,
            "fell_back_at": iso(fell_back_h) if fell_back_h is not None else None,
            "started_at": iso(started_h) if started_h is not None else None}


def _quote(**kw):
    q = {"n": 1, "fee": 15000, "currency": "EGP", "includes": "رفع الدعوى وحضور الجلسات لحد الحكم الابتدائي.",
         "excludes": "الاستئناف ومصاريف الخبراء والرسوم القضائية.", "duration": "٦ أشهر تقريبًا", "plan": "two",
         "second_label": "عند رفع الدعوى", "status": "accepted", "sent_at": iso(-70.0), "accepted_at": iso(-60.0),
         "rejected_at": None, "question": None}
    q.update(kw)
    return q


def _milestones(amounts, labels, statuses, *, consult_prefix, notes=None):
    """مراحل القضية بالقسمة ٢٥٪ (`platform_fee = round(amount * 0.25)`)."""
    out = []
    for k, (amount, label, status) in enumerate(zip(amounts, labels, statuses), start=1):
        fee = int(round(amount * 0.25))
        done = status in ("expert_done", "disputed", "released")
        out.append({"n": k, "label": label, "amount": amount, "expert_amount": amount - fee, "platform_fee": fee,
                    "consultation_id": (consult_prefix + str(k)) if status not in ("due",) else None,
                    "status": status,
                    "paid_at": iso(-50.0) if status not in ("due", "awaiting_payment") else None,
                    "done_at": iso(-30.0) if done else None,
                    "done_note": (notes or {}).get(k) if done else None,
                    "confirmed_at": iso(-20.0) if status == "released" else None,
                    "released_at": iso(-20.0) if status == "released" else None,
                    "auto": False,
                    "auto_release_at": iso(4 * 24.0) if status == "expert_done" else None,
                    "problem": ({"text": "الخبير ما رفعش الدعوى زي ما اتفقنا، والتاريخ اتأخر.", "at": iso(-6.0)}
                                if status == "disputed" else None),
                    "disputed_at": iso(-6.0) if status == "disputed" else None})
    return out


def case_view(quote, milestones, quotes=()):
    return {"quote": quote, "quotes": list(quotes), "milestones": milestones}


def _r13(row, *, speed="normal", urgent=None, case=None):
    out = copy.deepcopy(row)
    out["speed"] = speed
    out["urgent"] = urgent
    if case is not None:
        out["case"] = case
    return out


# مستعجل مستني خبير (٨٠٠ يدفع، ٥٠٠ للخبير) — لازم يبدأ قبل بعد ٤ ساعات.
X1 = _r13(_file("ef-x1-1a2b3c4d", title="شيك بدون رصيد — محتاج رأي النهارده", status="awaiting_assignment", law="eg",
                tier="written", amount=800.0, currency="EGP", expert_amount=500.0, paid_h=-2.0, deadline_h=46.0,
                client="هبة", counterparty="مصنع الأمل",
                pool=["hala@experts.test", "nada@experts.test", "sami@experts.test"]),
          speed="urgent", urgent=urgent_view("waiting", start_h=4.0, due_h=22.0))
# ملف اتحوّل لعادي (ما بدأش خبير في ٦ ساعات) ورجع ٣٠٠.
X2 = _r13(_file("ef-x2-2b3c4d5e", title="فسخ عقد توريد بسبب التأخير", status="awaiting_assignment", law="eg",
                tier="written", amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-7.0, deadline_h=41.0,
                client="سلمى", counterparty="شركة الواحة",
                pool=["hala@experts.test", "nada@experts.test"]),
          speed="normal", urgent=urgent_view("fell_back", start_h=-1.0, due_h=17.0, refunded=300, fell_back_h=-1.0))
# مستعجل بدأه الخبير وميعاد رأيه عدّى (متأخر).
X3 = _r13(_file("ef-x3-3c4d5e6f", title="إنذار بالإخلاء من المالك", status="writing", law="eg", tier="written",
                amount=800.0, currency="EGP", expert_amount=500.0, paid_h=-26.0, deadline_h=0.0, client="رامي",
                counterparty="المالك — عادل نصر", expert_email="hala@experts.test", writing_due_h=-2.0,
                file_no=1160),
          speed="urgent", urgent=urgent_view("started", start_h=-20.0, due_h=-2.0, started_h=-24.0))

# قضية: المرحلة الأولى فيها ملاحظة من العميل، والتانية لسه ما اتفتحتش للدفع.
CS1 = _r13(_file("ef-cs1-4d5e6f7a", title="دعوى تعويض عن فسخ عقد", status="closed", law="eg", tier="written",
                 amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-200.0, deadline_h=0.0, client="دعاء",
                 counterparty="شركة المقاولات الحديثة", expert_email="nada@experts.test", file_no=1150),
           case=case_view(_quote(),
                          _milestones([7500, 7500], ["الدفعة الأولى: بدء العمل", "الدفعة الثانية: عند رفع الدعوى"],
                                      ["disputed", "due"], consult_prefix="cm-cs1-",
                                      notes={1: "جهّزت صحيفة الدعوى وسلّمتها للعميلة للمراجعة."})))
# قضية لسه العرض مبعوت (ومعاه سؤال من العميل) — بتظهر في فلتر `case_open` بس.
CS2 = _r13(_file("ef-cs2-5e6f7a8b", title="نزاع ملكية على أرض", status="closed", law="eg", tier="written",
                 amount=500.0, currency="EGP", expert_amount=300.0, paid_h=-100.0, deadline_h=0.0, client="مروة",
                 counterparty="ورثة السيد", expert_email="hala@experts.test", file_no=1151),
           case=case_view(_quote(plan="one", second_label=None, status="sent", accepted_at=None,
                                 question={"text": "هل الأتعاب بتشمل الخبير الهندسي؟", "asked_at": iso(-3.0),
                                           "answer": None, "answered_at": None}),
                          _milestones([15000], ["القضية كاملة"], ["due"], consult_prefix="cm-cs2-")))
CASE_FILES = {CS1["id"]: "CS1", CS2["id"]: "CS2"}



class EFPlatform(object):
    """منصّة «ملف للخبير» صغيرة في الذاكرة. `handle(method, path, params, body)` ⇒ (status, payload).
    `deployed=False` ⇒ كل `/bridge/expert-files*` ٤٠٤ (الجسر مش منشور) والطابور من غير مفاتيح الملفات.
    `service_open=False` ⇒ الخدمة مقفولة للناس والجسر شغّال بالسرّ (الجولة ٧ ب١).
    الجولة ٨: `r8=True` بيزرع «مستنية مراجعتك» و«استشارات قديمة» · `mode='allowlist'` (+ `allowlist`) = مفتوحة للتجربة
    بس · `legacy_enabled=False` = منصة قبل الجولة ٨ (جسر القديمة ٤٠٤).
    `delay[(method, path)]` ثواني تأخير. `calls` = كل اللي اتطلب، بالترتيب (والجسم بالحرف — فيه `by`)."""

    def __init__(self, deployed=True, empty=False, cons_enabled=True, service_open=True, r8=False, mode=None,
                 allowlist=None, legacy_enabled=True, r13=False):
        self.deployed = deployed
        # `service_open` = المفتاح نفسه (`expert_files_enabled`) — في وضع التجربة المفتاح مقفول. الوضع من غير ما يتحدد
        # بيمشي ورا المفتاح (اختبارات الجولة ٧ بتقفله بعد الإنشاء).
        self._mode = mode
        self.service_open = bool(service_open) and mode in (None, "open")
        self.allowlist = frozenset(allowlist if allowlist is not None else (ALLOWLIST if mode == "allowlist" else ()))
        self.cons_enabled = cons_enabled
        self.legacy_enabled = legacy_enabled
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
        # الجولة ٨: «مستنية مراجعتك» (بـreview.submitted_at ↑) و«استشارات قديمة» (بـdelivered_at ↑).
        seed = r8 and not empty
        self.review = [copy.deepcopy(R2), copy.deepcopy(R1)] if seed else []
        self.review.sort(key=lambda f: (f["review"] or {}).get("submitted_at") or "")
        self.legacy = [copy.deepcopy(L1), copy.deepcopy(L2), copy.deepcopy(L3)] if seed else []
        self.legacy_done = set()
        # الجولة ١٣: مستعجل (X1 مستني خبير · X2 اتحوّل لعادي) في «مستني توزيع»، X3 مستعجل متأخر، وقضايا (CS1 فيها ملاحظة
        # · CS2 عرضها مبعوت). من غير `r13=True` الصفوف القديمة زي ما هي بالحرف.
        seed13 = r13 and not empty
        if seed13:
            self.waiting = sorted(self.waiting + [copy.deepcopy(X1), copy.deepcopy(X2)], key=lambda f: f["claim_deadline_at"])
            self.late = self.late + [copy.deepcopy(X3)]
        self.case_files = [copy.deepcopy(CS1), copy.deepcopy(CS2)] if seed13 else []
        self.review_stale = set()          # ملفات درجة الجلسة مواعيدها قربت/عدّت (`_review_slots_stale`)
        self.next_file_no = 1100
        self.unact_done = set()
        self.awaiting_payment = 0 if empty else 3
        # تعديل الخبير على D1 (None = لسه ما عدّلش) · `detail_fail` = قراية الملف الجاية ترجع ٥٠٠ (مرة).
        self.d1_revision = copy.deepcopy(D1_REVISION)
        self.detail_fail = False

    @property
    def case_disputed(self):
        """فلتر `case_disputed`: فيه مرحلة `disputed`."""
        return [f for f in self.case_files if any(m["status"] == "disputed" for m in f["case"]["milestones"])]

    @property
    def case_open(self):
        """فلتر `case_open`: عرض مبعوت أو مراحل لسه ما خلصتش."""
        return [f for f in self.case_files if (f["case"]["quote"] or {}).get("status") == "sent"
                or any(m["status"] not in ("released", "refunded") for m in f["case"]["milestones"])]

    @property
    def mode(self):
        """`service_mode()` بالحرف: open | allowlist | closed."""
        return self._mode or ("open" if self.service_open else "closed")

    # ---------------------------------------------------------------- مساعدات
    def _lanes(self):
        return (self.waiting, self.late, self.disputed, self.delivered, self.review, self.case_files)

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
                     ("D1", D1), ("R1", R1), ("R2", R2), ("X1", X1), ("X2", X2), ("X3", X3), ("CS1", CS1), ("CS2", CS2)):
            if v["id"] == f["id"]:
                return k
        return ""

    def _list(self, status, rows):
        return list_payload(status, copy.deepcopy(rows), self.service_open, self.mode, len(self.allowlist))

    def queue(self):
        if not self.deployed:
            return queue_payload(deployed=False)
        to_assign = sum(1 for f in self.waiting if f["status"] == "awaiting_assignment")
        sent = sum(1 for f in self.waiting if f["status"] == "assigned")
        overdue = sum(1 for f in self.waiting if f["status"] == "assigned" and f["assign_overdue"])
        late, disputed = len(self.late), len(self.disputed)
        open_total = (len(self.waiting) + late + disputed + len(self.delivered) + len(self.unact)
                      + len(self.review))
        regular = sum(1 for c in self.cons if c["kind"] != "expert_file")
        return queue_payload(to_assign=to_assign, sent=sent, overdue=overdue, late=late, disputed=disputed,
                             blocked=len(self._blocked_rows()), unactivated=len(self.unact),
                             awaiting_payment=self.awaiting_payment, open_total=open_total,
                             consultation_disputes=regular, service_open=self.service_open,
                             in_review=len(self.review), legacy=len(self.legacy) if self.legacy_enabled else 0,
                             mode=self.mode, allowlist_size=len(self.allowlist))

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

    def _can_assign(self, f, target):
        """`_require_can_assign` بالحرف: مفتوحة ⇒ تعدّي · قايمة ⇒ الخبير **والعميل** فيها وإلا `E_TRIAL_ONLY`."""
        if self.mode == "open":
            return None
        if self.mode == "allowlist":
            client = CLIENT_EMAILS.get(self._key(f), "")
            if target in self.allowlist and client in self.allowlist:
                return None
            return 409, {"detail": E_TRIAL_ONLY}
        return 409, {"detail": E_SERVICE_OFF}

    def _files(self, method, path, params, body):
        parts = path[len("/api/bridge/expert-files"):].strip("/").split("/")
        if method == "GET" and parts == [""]:
            s = params.get("status") or "waiting"
            if s == "unactivated":
                return 200, self._list(s, self.unact)
            if s == "blocked":
                return 200, self._list(s, self._blocked_rows())
            if s == "urgent":
                rows = [f for lane_ in (self.waiting, self.late) for f in lane_ if f.get("speed") == "urgent"]
                return 200, self._list(s, rows)
            lane = {"waiting": self.waiting, "late": self.late, "disputed": self.disputed,
                    "review": self.review, "case_disputed": self.case_disputed,
                    "case_open": self.case_open}.get(s)
            if lane is None:
                return 422, {"detail": [{"loc": ["query", "status"], "msg": "bad"}]}
            return 200, self._list(s, lane)
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
        if method == "GET" and parts[1:] == ["voice"]:
            # `GET /bridge/expert-files/{id}/voice` — بايتات الصوت (مفيش صوت ⇒ نفس ٤٠٤ بتاع باقي الملف).
            if fid not in VOICE_FILES:
                return 404, {"detail": E_NOT_FOUND}
            return 200, VOICE_BYTES
        act = parts[1] if len(parts) > 1 else ""
        if act in ("assign", "reassign") and self.mode == "closed":
            return 409, {"detail": E_SERVICE_OFF}
        if act == "assign":
            if f["status"] not in PRE_CLAIM:
                return 409, {"detail": "الملف ده مش مستني توزيع"}
            target = (body.get("expert_email") or "").lower()
            if target not in EXPERTS:
                return 404, {"detail": "الخبير غير موجود أو غير معتمد"}
            refused = self._can_assign(f, target)
            if refused:
                return refused
            if f["hours_left"] <= 0:
                return 409, {"detail": "فات ميعاد استلام الملف"}
            f.update({"status": "assigned", "assigned_to": target, "assigned_name": EXPERTS[target][0],
                      "assigned_at": iso(0), "assign_overdue": False,
                      "status_label": STATUS_LABELS["assigned"]})
            return 200, bridge_reply(f)
        if act == "reassign":
            reviewing = f["status"] == "in_review" and not (f.get("review") or {}).get("approved_at")
            if f["status"] not in EXPERT_WORK and not reviewing:
                return 409, {"detail": "الملف ده مش عند خبير دلوقتي"}
            target = (body.get("expert_email") or "").lower()
            if target not in EXPERTS:
                return 404, {"detail": "الخبير غير موجود أو غير معتمد"}
            refused = self._can_assign(f, target)
            if refused:
                return refused
            if target == f["expert_email"]:
                return 409, {"detail": "الملف عند الخبير ده أصلًا"}
            old = f["expert_email"]
            lane.remove(f)
            f.update({"status": "assigned", "assigned_to": target, "assigned_name": EXPERTS[target][0],
                      "assigned_at": iso(0), "assign_overdue": False, "expert_email": None, "expert_name": "",
                      "writing_due_at": None, "claim_deadline_at": iso(48), "hours_left": 48.0,
                      "release_amount": None, "status_label": STATUS_LABELS["assigned"],
                      "review": None, "pending_opinion": None})
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
            back = f.get("release_blocked") if f.get("release_blocked") in ("manual_refund", "gateway_refund") else None
            if action == "release" and f.get("release_blocked"):
                return 409, {"detail": RELEASE_BLOCK_TEXT[f["release_blocked"]]}
            if action == "refund" and back:
                return 409, {"detail": E_RESOLVE_MANUAL if back == "manual_refund" else E_RESOLVE_GATEWAY}
            lane.remove(f)
            self.cons = [c for c in self.cons if c.get("expert_file_id") != fid]
            f.update({"status": "closed" if action == "release" else "refunded"})
            return 200, bridge_reply(f, refund_reason=None if action == "release" else "dispute",
                                     closed_by="founder_release" if action == "release" else None)
        if act == "review":
            return self._review(lane, f, body)
        if act == "case" and len(parts) == 5 and parts[2] == "milestones" and parts[4] == "resolve" and method == "POST":
            return self._case_resolve(lane, f, parts[3], body)
        return 404, NOT_FOUND

    def _case_resolve(self, lane, f, n, body):
        """`POST …/case/milestones/{n}/resolve` (SPEC-R13 §٣): المرحلة لازم `disputed`؛ «للخبير» ⇒ `released`، «للعميل» ⇒
        `refunded` (رصيد محفظة — مفيش رد على بوابة الدفع). مرة واحدة: التانية ⇒ ٤٠٩."""
        action = body.get("action")
        if action not in ("release", "refund"):
            return 422, {"detail": E_RESOLVE_ACTION}
        case = f.get("case") or {}
        ms = next((m for m in case.get("milestones") or [] if str(m["n"]) == str(n)), None)
        if ms is None:
            return 404, {"detail": E_CASE_MS_MISSING}
        if ms["status"] != "disputed":
            return 409, {"detail": E_CASE_NOT_DISPUTED}
        if action == "release" and ms.get("release_blocked"):
            return 409, {"detail": E_CASE_RELEASE_MANUAL}
        ms["status"] = "released" if action == "release" else "refunded"
        ms["released_at"] = iso(0) if action == "release" else None
        return 200, dict(bridge_reply(f), case=copy.deepcopy(case))

    def _review(self, lane, f, body):
        """`bridge_review` بالحرف (الترتيب والرسايل): الفعل ⇒ اتقفل ⇒ مش مستني مراجعة ⇒ approve / return."""
        act = str(body.get("action") or "").strip().lower()
        if act not in ("approve", "return"):
            return 422, {"detail": E_REVIEW_ACTION}
        if f["status"] in ("refunded", "cancelled"):
            return 409, {"detail": E_CLOSED}
        if f["status"] != "in_review":
            return 409, {"detail": E_REVIEW_NOT_WAITING}
        review = dict(f.get("review") or {})
        stale = f["id"] in self.review_stale
        if act == "approve":
            if stale:
                return 409, {"detail": E_REVIEW_SLOTS}
            lane.remove(f)
            review["approved_at"] = iso(0)
            f.update({"status": "delivered", "status_label": STATUS_LABELS["delivered"], "file_no": self.next_file_no,
                      "review": review_view(review), "pending_opinion": None})
            self.next_file_no += 1
            self.delivered.append(f)
            return 200, dict(bridge_reply(f), review=review_view(review))
        text = str(body.get("note") or "").strip()[:1000]
        if stale and not text:
            text = REVIEW_SLOTS_NOTE
        if not text:
            return 422, {"detail": E_REVIEW_NOTE}
        if int(review.get("returns") or 0) >= 1 and not stale:
            return 409, {"detail": E_REVIEW_RETURNED}
        lane.remove(f)
        review.update({"returns": int(review.get("returns") or 0) + 1, "returned_at": iso(0), "note": text})
        f.update({"status": "writing", "status_label": STATUS_LABELS["writing"], "review": review_view(review),
                  "pending_opinion": None})
        return 200, dict(bridge_reply(f), review=review_view(review))

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
        if path == "/api/bridge/consultations/legacy" or path.endswith("/legacy"):
            return self._legacy(method, path, body)
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
            if action == "release":
                # الجولة ٨ (البند ٥): العميل خد فلوسه ⇒ «للخبير» مرفوض والفلوس فاضلة محجوزة.
                if c.get("manual_refund_settled_at"):
                    return 409, {"detail": E_RELEASE_MANUAL}
                if c.get("release_blocked") == "gateway_refund":
                    return 409, {"detail": E_RELEASE_GATEWAY}
                if not c.get("payee_email"):
                    return 409, {"detail": E_RELEASE_UNCLAIMED}
            if action == "refund" and c.get("manual_refund_settled_at"):
                return 409, {"detail": E_RESOLVE_MANUAL}
            if action == "refund" and c.get("release_blocked") == "gateway_refund":
                return 409, {"detail": E_RESOLVE_GATEWAY}
            self.cons.remove(c)
            if c.get("expert_file_id"):
                lane, f = self._find(c["expert_file_id"])
                if f is not None:
                    lane.remove(f)
            return 200, resolve_reply(c, "released" if action == "release" else "refunded")
        return 404, NOT_FOUND

    def _legacy(self, method, path, body):
        """`bridge_consultations_legacy` + `bridge_decide_legacy` (`decide_legacy` بالحرف: مرة واحدة · ⛔ «للخبير»
        بعد ما العميل خد فلوسه). `legacy_enabled=False` ⇒ منصة قبل الجولة ٨ (٤٠٤)."""
        if not self.legacy_enabled:
            return 404, NOT_FOUND
        if method == "GET" and path == "/api/bridge/consultations/legacy":
            return 200, legacy_payload(copy.deepcopy(self.legacy))
        tail = path[len("/api/bridge/consultations/"):].split("/")
        if method != "POST" or len(tail) != 2 or tail[1] != "legacy":
            return 404, NOT_FOUND
        cid = tail[0]
        action = body.get("action")
        if action not in ("release", "refund"):
            return 422, {"detail": E_RESOLVE_ACTION}
        if cid in self.legacy_done:
            return 409, {"detail": E_LEGACY_SETTLED}
        c = next((x for x in self.legacy if x["id"] == cid), None)
        if c is None:
            return 404, {"detail": E_LEGACY_MISSING}
        if action == "release" and c.get("release_blocked"):
            return 409, {"detail": c["release_blocked_reason"]}
        if action == "refund" and c.get("refund_blocked"):
            return 409, {"detail": c["refund_blocked_reason"]}
        self.legacy.remove(c)
        self.legacy_done.add(cid)
        return 200, resolve_reply(c, "released" if action == "release" else "refunded")
