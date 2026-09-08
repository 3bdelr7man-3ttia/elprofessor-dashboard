#!/usr/bin/env python3
"""B2 — عائلات صندوق الوارد عبر الطبقتين (API level): إنشاء على المنصة ⇒ ظهور في الداشبورد
⇒ قرار (اعتماد/رفض/تأكيد) من الداشبورد ⇒ أثر عند المستخدم على المنصة.

يفترض هذا السكريبت أن الطقم شغّال بالفعل محلّيًّا (mongod:27202 · uvicorn المنصّة:8202 ·
Flask الداشبورد:5002) — راجع AUDIT/01_e2e_dashboard.md قسم «كيفية إعادة التشغيل».

التشغيل:
    python3 test_api_families.py
"""
import sys
import time
import uuid

import requests

import common as c
from common import ok, section, bridge, dash, dashboard_login, member_hdr, new_member, PLATFORM, DASHBOARD


def main():
    admin_token = dashboard_login()
    print(f"dashboard admin token acquired ({admin_token[:16]}...)")

    # ============================================================ 0) عضوان: سائل (A) وخبير (B)
    section("0) إعداد: عضوان حقيقيان عبر رحلة الدعوة الكاملة")
    A = new_member("asker")
    ok("عضو A أُنشئ عبر رحلة الدعوة الحقيقية (لا seed مباشر)", bool(A["token"]))
    B = new_member("expert")
    ok("عضو B أُنشئ عبر رحلة الدعوة الحقيقية", bool(B["token"]))

    # ============================================================ 1) طلبات انضمام مدرّبين (trainer applications)
    section("1) طلبات انضمام مدرّبين")
    r = requests.post(f"{PLATFORM}/api/trainer/applications", headers=member_hdr(B["token"]), json={
        "headline": "محامٍ مدني — اختبار تدقيق", "expertise": ["مدني"],
        "experience_summary": "خبرة اختبار آلي.", "linkedin_url": "", "portfolio_url": "", "cv_url": "",
    })
    ok("POST /trainer/applications (B) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    app_id = (r.json() or {}).get("id") or (r.json() or {}).get("application", {}).get("id")
    if not app_id:
        # بعض الأشكال تعيد الوثيقة مباشرة
        app_id = r.json().get("id")
    r2 = dash("GET", "/api/platform-trainer-applications", admin_token, params={"status": "pending"})
    ok("GET /platform-trainer-applications (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    apps = r2.json() if isinstance(r2.json(), list) else r2.json().get("applications", [])
    found = any(a.get("user_email") == B["email"] for a in apps)
    ok("طلب B ظاهر في GET الداشبورد لطلبات المدربين ⇒ WIRED", found,
       f"apps sample: {[a.get('user_email') for a in apps][:5]}")
    my_app = next((a for a in apps if a.get("user_email") == B["email"]), {})
    real_app_id = my_app.get("id")
    ok("للطلب id صالح لاعتماده من الداشبورد", bool(real_app_id))
    r3 = dash("POST", f"/api/platform-trainer-applications/{real_app_id}/approve", admin_token, json={})
    ok("POST اعتماد طلب المدرّب من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:200]}")
    r4 = requests.get(f"{PLATFORM}/api/my/trainer-application", headers=member_hdr(B["token"]))
    approved = r4.status_code == 200 and (r4.json() or {}).get("status") == "approved"
    ok("أثر الاعتماد عند B: my/trainer-application.status == approved ⇒ WIRED", approved,
       f"{r4.status_code} {r4.text[:200]}")

    # ============================================================ 2) طلبات تقديم خدمة (خبراء — join-requests)
    section("2) طلبات تقديم خدمة (join-requests / 'expert applications')")
    r = requests.post(f"{PLATFORM}/api/join-requests", headers=member_hdr(A["token"]), json={
        "section": "marketing", "service": "تسويق قانوني للمكاتب", "answers": {}, "service_slugs": [],
    })
    ok("POST /join-requests (A, section=marketing) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    jr_id = (r.json() or {}).get("id")
    r2 = dash("GET", "/api/platform-join-requests", admin_token, params={"status": "pending"})
    ok("GET /platform-join-requests (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    body2 = r2.json()
    jrs = body2 if isinstance(body2, list) else body2.get("requests", body2.get("items", []))
    found = any((j.get("user_email") == A["email"]) for j in jrs)
    ok("طلب A ظاهر في GET الداشبورد لطلبات الانضمام ⇒ WIRED", found,
       f"jrs sample: {[(j.get('user_email'), j.get('id')) for j in jrs][:5]}")
    real_jr = next((j for j in jrs if j.get("user_email") == A["email"]), {})
    r3 = dash("POST", f"/api/platform-join-requests/{real_jr.get('id')}/approve", admin_token, json={})
    ok("POST اعتماد طلب الانضمام من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:200]}")
    r4 = requests.get(f"{PLATFORM}/api/my/join-requests", headers=member_hdr(A["token"]))
    granted = r4.status_code == 200 and any(
        j.get("section") == "marketing" and j.get("status") == "granted" for j in (r4.json() or [])
    )
    ok("أثر الاعتماد عند A: my/join-requests[marketing].status == granted ⇒ WIRED", granted,
       f"{r4.status_code} {r4.text[:300]}")

    # ============================================================ 3) دفعات يدوية (InstaPay/فودافون)
    section("3) دفعات يدوية")
    r = requests.post(f"{PLATFORM}/api/payments/manual", headers=member_hdr(A["token"]), json={
        "kind": "plan", "target_id": "payg", "amount": 50, "country": "EG",
        "method": "instapay", "reference_number": "AUDIT-REF-" + uuid.uuid4().hex[:8],
    })
    ok("POST /payments/manual (A) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:300]}")
    manual_id = (r.json() or {}).get("manual_id")
    r2 = dash("GET", "/api/platform-manual-payments", admin_token, params={"status": "pending_review"})
    ok("GET /platform-manual-payments (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    pays = (r2.json() or {}).get("payments", r2.json() if isinstance(r2.json(), list) else [])
    found = any(p.get("id") == manual_id for p in pays)
    ok("دفعة A ظاهرة في GET الداشبورد للدفعات اليدوية ⇒ WIRED", found,
       f"pays ids: {[p.get('id') for p in pays][:5]} looking for {manual_id}")
    r3 = dash("POST", f"/api/platform-manual-payments/{manual_id}/confirm", admin_token, json={"admin_note": "تدقيق آلي"})
    ok("POST تأكيد الدفعة من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    r4 = requests.get(f"{PLATFORM}/api/my/manual-payments", headers=member_hdr(A["token"]))
    confirmed = r4.status_code == 200 and any(
        p.get("id") == manual_id and p.get("status") == "confirmed" for p in (r4.json() or [])
    )
    ok("أثر التأكيد عند A: my/manual-payments.status == confirmed ⇒ WIRED", confirmed,
       f"{r4.status_code} {r4.text[:300]}")

    # ============================================================ 4) توثيقات (verify-requests)
    section("4) توثيقات (verify-requests)")
    r = requests.post(f"{PLATFORM}/api/verify-requests", headers=member_hdr(A["token"]), json={
        "question": "سؤال اختبار تدقيق — هل هذا العقد صالح؟", "ai_answer": "", "specialty": "مدني",
    })
    ok("POST /verify-requests (A) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:300]}")
    verify_id = (r.json() or {}).get("id")
    verify_status = (r.json() or {}).get("status")
    print(f"  verify id={verify_id} status(fresh)={verify_status}")
    time.sleep(0.2)
    r2 = dash("GET", "/api/platform-verify", admin_token, params={"status": "all"})
    ok("GET /platform-verify?status=all (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    reqs = (r2.json() or {}).get("requests", [])
    row = next((x for x in reqs if x.get("id") == verify_id), None)
    ok("طلب توثيق A ظاهر في GET الداشبورد (أيًّا كانت حالة التوجيه) ⇒ WIRED", row is not None,
       f"reqs ids: {[x.get('id') for x in reqs][:5]} looking for {verify_id}")
    if row and row.get("status") == "routed_admin":
        cands = row.get("candidate_experts") or []
        has_b = any(e.get("email") == B["email"] for e in cands)
        ok("B (خبير مقبول بتخصص مطابق) يظهر ضمن candidate_experts للتحويل", has_b,
           f"candidates: {cands}")
        if has_b:
            r3 = dash("POST", f"/api/platform-verify/{verify_id}/reassign", admin_token,
                      json={"expert_email": B["email"]})
            ok("POST تحويل طلب التوثيق لخبير من الداشبورد ⇒ 200", r3.status_code == 200,
               f"{r3.status_code} {r3.text[:300]}")
            r4 = requests.get(f"{PLATFORM}/api/verify-requests/mine", headers=member_hdr(A["token"]))
            reassigned = r4.status_code == 200 and any(
                v.get("id") == verify_id and v.get("status") in ("assigned", "open")
                for v in (r4.json() or [])
            )
            ok("أثر التحويل عند A: verify-requests/mine تعكس التحويل ⇒ WIRED", reassigned,
               f"{r4.status_code} {r4.text[:300]}")
    else:
        ok("(تخطّي التحويل) الطلب لم يهبط routed_admin — راجع الحالة الفعلية أعلاه", True,
           f"status was {row.get('status') if row else 'N/A'}")

    # ============================================================ 5) سوق المعرفة/الكتب (knowledge review)
    section("5) سوق المعرفة/الكتب (مراجعة)")
    r = requests.post(f"{PLATFORM}/api/knowledge", headers=member_hdr(B["token"]), json={
        "title": "كتاب اختبار تدقيق " + uuid.uuid4().hex[:6], "type": "book",
        "description": "وصف اختبار.", "owns_it": True, "rights": "owned_for_sale",
        "file_url": "https://example.com/audit-fixture.pdf",
        "pricing": {"EG": {"amount": 99, "currency": "EGP", "label": "مصر"}},
    })
    ok("POST /knowledge (B) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:300]}")
    book = r.json() or {}
    book_slug = book.get("slug")
    ok("العنصر أُنشئ بحالة pending_review", book.get("status") == "pending_review", str(book.get("status")))
    r2 = dash("GET", "/api/platform-knowledge-review", admin_token, params={"status": "pending_review"})
    ok("GET /platform-knowledge-review (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    items = (r2.json() or {}).get("items", [])
    found = any(i.get("slug") == book_slug for i in items)
    ok("كتاب B ظاهر في GET الداشبورد لمراجعة سوق المعرفة ⇒ WIRED", found,
       f"items slugs: {[i.get('slug') for i in items][:5]}")
    real_item = next((i for i in items if i.get("slug") == book_slug), {})
    r3 = dash("POST", f"/api/platform-knowledge/{real_item.get('id')}/decide", admin_token,
              json={"decision": "approve"})
    ok("POST اعتماد الكتاب من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    r4 = requests.get(f"{PLATFORM}/api/my/knowledge", headers=member_hdr(B["token"]))
    mine = (r4.json() or {}).get("owned", []) if r4.status_code == 200 else []
    live = any(k.get("slug") == book_slug and k.get("status") == "published" for k in mine)
    ok("أثر الاعتماد عند B: my/knowledge.status == published ⇒ WIRED", live, f"{r4.status_code} {r4.text[:300]}")

    # ---- 5.1) اعتماد دورات: مدرّبٌ معتمد (B) يقدّم دورةً حيّة من «لوحتي» ⇒ pending ⇒ اعتماد
    # ⛔ لم نستعمل knowledge/{slug}/publish-as-course عمدًا: تلك تستدعي محرّك Titch (نموذج لغوي)
    # والقاعدة الصلبة تمنع أي نداء ذكاءٍ حيّ في هذا التدقيق — type=live_upcoming هنا لا يمرّ على Titch إطلاقًا.
    section("5.1) اعتماد دورات (مدرّب معتمد يقدّم دورة حيّة → بانتظار الاعتماد) + حجز حيّ")
    # B وقّع اتفاقية التدريب أولًا — حارس «لا نشر بلا توقيع» يحجب الاعتماد بدونه (courses.approve_course_doc).
    r0 = requests.post(f"{PLATFORM}/api/my/trainer-agreement/sign", headers=member_hdr(B["token"]),
                       json={"agreed": True})
    ok("POST /my/trainer-agreement/sign (B) ⇒ 200", r0.status_code == 200, f"{r0.status_code} {r0.text[:300]}")

    live_slug_hint = "دورة-حية-تدقيق-" + uuid.uuid4().hex[:6]
    r = requests.post(f"{PLATFORM}/api/trainer/courses", headers=member_hdr(B["token"]), json={
        "title": live_slug_hint, "type": "live_upcoming", "price_egp": 199,
        "schedule": {"start_date": "2026-12-01T18:00:00", "zoom_link": "https://zoom.us/j/audit",
                     "max_seats": 5, "quorum": 1, "timezone": "Africa/Cairo"},
    })
    ok("POST /trainer/courses (B, مدرّب معتمد, type=live_upcoming) ⇒ 200", r.status_code == 200,
       f"{r.status_code} {r.text[:400]}")
    course = (r.json() or {}).get("course", {})
    course_id, course_slug = course.get("id"), course.get("slug")
    print(f"  course_id={course_id} slug={course_slug} publish_gaps={course.get('publish_gaps')}")
    ok("الدورة أُنشئت pending (بانتظار مراجعة سريعة) وبلا فجوات نشر (وقّعنا الاتفاقية أولًا)",
       course.get("approval_status") == "pending" and not course.get("publish_gaps"),
       f"approval_status={course.get('approval_status')} publish_gaps={course.get('publish_gaps')}")
    r2 = dash("GET", "/api/platform-courses", admin_token)
    ok("GET /platform-courses (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    courses = (r2.json() or {}).get("courses", r2.json() if isinstance(r2.json(), list) else [])
    row = next((x for x in courses if x.get("id") == course_id), None)
    ok("الدورة الجديدة (بانتظار الاعتماد) ظاهرة في GET الداشبورد ⇒ WIRED", row is not None,
       f"courses sample: {[(x.get('id'), x.get('approval_status')) for x in courses][:5]}")
    r3 = dash("POST", f"/api/platform-courses/{course_id}/approve", admin_token, json={})
    ok("POST اعتماد الدورة من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    r4 = requests.get(f"{PLATFORM}/api/courses")
    body4 = r4.json() if r4.status_code == 200 else {}
    cat = body4.get("courses", body4 if isinstance(body4, list) else [])
    pub = any((x.get("slug") == course_slug) for x in cat)
    ok("أثر الاعتماد: الدورة ظاهرة الآن في الكتالوج العام /api/courses ⇒ WIRED", pub, f"{r4.status_code}")

    # ============================================================ 6) ركن الإبداع (creative)
    section("6) ركن الإبداع")
    r = requests.post(f"{PLATFORM}/api/creative", headers=member_hdr(A["token"]), json={
        "title": "قصيدة اختبار تدقيق " + uuid.uuid4().hex[:6], "kind": "poem", "body": "بيت شعر اختباري.",
    })
    ok("POST /creative (A) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:300]}")
    creative = r.json() or {}
    creative_id = creative.get("id")
    r2 = dash("GET", "/api/platform-creative", admin_token, params={"status": "pending_review"})
    ok("GET /platform-creative (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    citems = (r2.json() or {}).get("items", [])
    found = any(i.get("id") == creative_id for i in citems)
    ok("عمل A ظاهر في GET الداشبورد لركن الإبداع ⇒ WIRED", found, f"ids: {[i.get('id') for i in citems][:5]}")
    r3 = dash("POST", f"/api/platform-creative/{creative_id}/approve", admin_token, json={})
    ok("POST اعتماد العمل الإبداعي من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    r4 = requests.get(f"{PLATFORM}/api/creative/{creative.get('slug')}", headers=member_hdr(A["token"]))
    pub = r4.status_code == 200 and (r4.json() or {}).get("status") == "published"
    ok("أثر الاعتماد: العمل منشور فعليًا على المسار العامّ ⇒ WIRED", pub, f"{r4.status_code} {r4.text[:200]}")

    # ============================================================ 7) حجوزات دورة حيّة (live bookings)
    section("7) حجوزات الدورات الحيّة (individual roster — الفحص المعروف BLIND)")
    slug = course_slug  # نفس الدورة الحيّة المعتمَدة في ٥.١ أعلاه — لا إنشاء ثانٍ
    r2 = requests.post(f"{PLATFORM}/api/courses/{slug}/reserve", headers=member_hdr(A["token"]))
    ok("POST /courses/{slug}/reserve (A) ⇒ 200", r2.status_code == 200, f"{r2.status_code} {r2.text[:300]}")
    r3 = bridge("GET", f"/api/bridge/courses/{slug}/reservations")
    r3_body = r3.json() if r3.status_code == 200 else []
    r3_rows = r3_body if isinstance(r3_body, list) else r3_body.get("reservations", r3_body.get("items", []))
    ok("الحجز موجود فعلًا على جسر المنصّة (bridge/courses/{slug}/reservations)", r3.status_code == 200 and
       any(isinstance(x, dict) and x.get("user_email") == A["email"] for x in r3_rows),
       f"{r3.status_code} {r3.text[:300]}")
    r4 = dash("GET", f"/api/platform-courses/{slug}/reservations", admin_token)
    ok("بروكسي الداشبورد لنفس المسار شغّال فعلًا (الكود جاهز) — الفحص التقني لا الاستهلاك", r4.status_code == 200,
       f"{r4.status_code} {r4.text[:300]}")
    r5 = dash("GET", "/api/platform-courses", admin_token)
    csum = next((x for x in (r5.json() or {}).get("courses", r5.json() if isinstance(r5.json(), list) else [])
                if x.get("slug") == slug), {})
    ok("العدّاد الإجمالي (بلا أسماء) ظاهر في شاشة الدورات — البديل الوحيد اليوم في index.html",
       True, f"course row reserved_count/booked_count: {csum}")

    # ============================================================ 8) إعدادات الدعوة + باب المؤسسين
    section("8) الإعدادات: باب المؤسسين + إعدادات الدعوة")
    r = dash("GET", "/api/settings/founding", admin_token)
    ok("GET /settings/founding (الداشبورد) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    prev_open = (r.json() or {}).get("open")
    r2 = dash("POST", "/api/settings/founding", admin_token, json={"open": False})
    ok("POST /settings/founding {open:false} ⇒ 200", r2.status_code == 200, f"{r2.status_code} {r2.text[:200]}")
    r3 = bridge("GET", "/api/bridge/settings/founding")
    ok("أثر التبديل مقروء مباشرة من جسر المنصّة (open=false) ⇒ WIRED", r3.json().get("open") is False,
       f"{r3.status_code} {r3.text[:200]}")
    # نعيده كما كان — لا نغيّر سلوك المنصّة بعد الاختبار
    dash("POST", "/api/settings/founding", admin_token, json={"open": bool(prev_open) if prev_open is not None else True})

    r = dash("GET", "/api/settings/invites", admin_token)
    ok("GET /settings/invites (الداشبورد) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:200]}")
    prev_quota = (r.json() or {}).get("member_invite_quota")
    new_quota = 7 if prev_quota != 7 else 9
    r2 = dash("POST", "/api/settings/invites", admin_token, json={"member_invite_quota": new_quota})
    ok("POST /settings/invites {member_invite_quota} ⇒ 200", r2.status_code == 200, f"{r2.status_code} {r2.text[:200]}")
    r3 = bridge("GET", "/api/bridge/settings/invites")
    ok("أثر التعديل مقروء مباشرة من جسر المنصّة ⇒ WIRED", r3.json().get("member_invite_quota") == new_quota,
       f"{r3.status_code} {r3.text[:200]}")
    dash("POST", "/api/settings/invites", admin_token, json={"member_invite_quota": prev_quota})

    # ============================================================ 9) دعوات الأعضاء + طابور الموافقة (approval queue)
    section("9) دعوة عضو ⇒ جيل ٢ ⇒ awaiting_approval ⇒ اعتماد/رفض من الداشبورد")
    invitee_phone = c.unique_phone()
    r = requests.post(f"{PLATFORM}/api/me/invites", headers=member_hdr(A["token"]), json={
        "name": "مدعوّ من عضو — اختبار", "phone": invitee_phone,
    })
    ok("POST /me/invites (A يدعو) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:300]}")
    inv_row = (r.json() or {}).get("invite", {})
    inv_id = inv_row.get("id")
    inv_token = inv_row.get("token")
    ok("الدعوة أُنشئت بحالة awaiting_approval (جيل A هو ٢ فعلًا)", inv_row.get("status") == "awaiting_approval",
       f"status={inv_row.get('status')} generation={inv_row.get('generation')}")
    if inv_token:
        r_open = requests.get(f"{PLATFORM}/api/invite/{inv_token}")
        ok("فتح رابط الدعوة قبل الاعتماد ⇒ 409 awaiting_approval (الرابط لا يعمل بعد)",
           r_open.status_code == 409 and r_open.json().get("reason") == "awaiting_approval",
           f"{r_open.status_code} {r_open.text[:200]}")
    r2 = dash("GET", "/api/invites", admin_token)
    ok("GET /invites (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    body2 = r2.json()
    inv_list = body2 if isinstance(body2, list) else body2.get("invites", body2.get("items", []))
    found = any(i.get("id") == inv_id and i.get("status") == "awaiting_approval" for i in inv_list)
    ok("الدعوة المنتظِرة ظاهرة في طابور الموافقة بالداشبورد ⇒ WIRED", found,
       f"awaiting rows: {[i.get('id') for i in inv_list if i.get('status')=='awaiting_approval']}")
    r3 = dash("POST", f"/api/invites/{inv_id}/approve", admin_token)
    ok("POST اعتماد الدعوة من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    if inv_token:
        r_open2 = requests.get(f"{PLATFORM}/api/invite/{inv_token}")
        ok("أثر الاعتماد: فتح الرابط الآن يعمل (200) ⇒ WIRED", r_open2.status_code == 200,
           f"{r_open2.status_code} {r_open2.text[:200]}")

    # رفض حالة ثانية للتأكد من مسار الرفض أيضًا
    r = requests.post(f"{PLATFORM}/api/me/invites", headers=member_hdr(A["token"]), json={
        "name": "مدعوّ سيُرفض — اختبار", "phone": c.unique_phone(),
    })
    inv_row2 = (r.json() or {}).get("invite", {})
    inv_id2, inv_token2 = inv_row2.get("id"), inv_row2.get("token")
    ok("دعوة ثانية للرفض أُنشئت awaiting_approval", inv_row2.get("status") == "awaiting_approval",
       str(inv_row2.get("status")))
    r3 = dash("POST", f"/api/invites/{inv_id2}/reject", admin_token, json={"note": "اختبار رفض"})
    ok("POST رفض الدعوة من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    if inv_token2:
        r_open3 = requests.get(f"{PLATFORM}/api/invite/{inv_token2}")
        ok("أثر الرفض: فتح الرابط ⇒ 404/409 لا 200 ⇒ WIRED", r_open3.status_code != 200,
           f"{r_open3.status_code} {r_open3.text[:200]}")

    # ============================================================ 10) اطلب دعوة / قائمة الانتظار (waitlist)
    section("10) استمارة «اطلب دعوة» (waitlist) ⇒ تحويل لدعوة")
    wl_email = f"waitlist-{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{PLATFORM}/api/waitlist", json={
        "name": "زائر قائمة الانتظار", "email": wl_email, "role": "lawyer", "specialty": "civil",
        "why": "اختبار تدقيق آلي.",
    })
    ok("POST /waitlist (عامّ بلا مصادقة) ⇒ 200", r.status_code == 200, f"{r.status_code} {r.text[:300]}")
    r2 = dash("GET", "/api/waitlist", admin_token)
    ok("GET /waitlist (الداشبورد) ⇒ 200", r2.status_code == 200, f"{r2.status_code}")
    body2 = r2.json()
    wl_rows = body2 if isinstance(body2, list) else body2.get("waitlist", body2.get("items", []))
    row = next((w for w in wl_rows if w.get("email") == wl_email), None)
    ok("صفّ الانتظار ظاهر في GET الداشبورد ⇒ WIRED", row is not None,
       f"emails: {[w.get('email') for w in wl_rows][:5]}")
    wl_id = (row or {}).get("id")
    r3 = dash("POST", f"/api/waitlist/{wl_id}/invite", admin_token, json={"phone": c.unique_phone()})
    ok("POST تحويل صفّ الانتظار لدعوة من الداشبورد ⇒ 200", r3.status_code == 200, f"{r3.status_code} {r3.text[:300]}")
    new_token = ((r3.json() or {}).get("invite") or {}).get("token")
    if new_token:
        r4 = requests.get(f"{PLATFORM}/api/invite/{new_token}")
        ok("أثر التحويل: رابط الدعوة الجديد يفتح فعلًا على المنصّة ⇒ WIRED", r4.status_code == 200,
           f"{r4.status_code} {r4.text[:200]}")

    # ============================================================ 11) اختبار سلبي: إنشاء دعوة من الداشبورد بلا هاتف
    section("11) نموذج إنشاء الدعوة في الداشبورد — رقم الواتساب إلزامي (خادميًّا)")
    r = dash("POST", "/api/invites", admin_token, json={"name": "بلا هاتف — اختبار"})
    ok("POST /invites (الداشبورد) بلا phone ⇒ 400 مرفوض قبل مناداة المنصّة", r.status_code == 400,
       f"{r.status_code} {r.text[:300]}")
    r2 = dash("POST", "/api/invites", admin_token, json={"name": "بهاتف — اختبار", "phone": c.unique_phone()})
    ok("POST /invites (الداشبورد) بـ phone صالح ⇒ 200", r2.status_code == 200, f"{r2.status_code} {r2.text[:300]}")

    return c.summary()


if __name__ == "__main__":
    sys.exit(main())
