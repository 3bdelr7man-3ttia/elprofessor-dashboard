#!/usr/bin/env python3
"""B2 — نفس عائلات صندوق الوارد، بعين المتصفّح الحقيقية (Playwright، Chromium):
تسجيل دخول حقيقي في نموذج الداشبورد ⇒ فتح شاشة «الوارد» و«الدعوات» على عرض ديسكتوب (1280×800)
وهاتف RTL (390×844) ⇒ التحقق أن كل بند اختباري ظاهر في الـDOM فعليًا (لا مجرّد في استجابة API) ⇒
تفاعل حيّ واحد كامل (تحويل صفّ قائمة انتظار إلى دعوة عبر الأزرار الحقيقية) ⇒ فحص RTL/أخطاء الكونسول.

يفترض هذا السكريبت طقمًا شغّالًا فعلًا (راجع AUDIT/01_e2e_dashboard.md) ومتصفّحات Playwright
مثبَّتة داخل .venv الخاص بريبو المنصّة (`elprofessor/.venv`) — لذلك نستورد الحزمة من هناك.

التشغيل:
    PYTHONPATH=/Users/abdelrhman/Documents/Playground/elprofessor/.venv/lib/python3.11/site-packages \
        /Users/abdelrhman/Documents/Playground/elprofessor/.venv/bin/python test_ui_screens.py
"""
import sys
import time
import uuid

import requests
from playwright.sync_api import sync_playwright

import common as c
from common import ok, section, bridge, dash, dashboard_login, member_hdr, new_member, PLATFORM, DASHBOARD

DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 390, "height": 844}


def ui_login(page):
    """تسجيل دخول حقيقي بالنموذج. ⛔ فخّ مكتشَف أثناء بناء هذا السكريبت: `#pageTitle` عنصرٌ ثابتٌ
    موجود في هيكل الصفحة قبل الدخول أصلًا (خلف طبقة `#epLogin` المُعلَّقة فوقه) — انتظاره لا يثبت
    نجاح الدخول أبدًا، وكان يمرّ فورًا حتى مع فشل الدخول فيترك الصفحة كلها فارغة من نداءات API لاحقًا.
    الدليل الصحيح الوحيد: طبقة `#epLogin` نفسها تُزال من الـDOM بـ`hideLogin()` بعد نجاح `/api/auth/login`."""
    for attempt in range(3):
        page.goto(DASHBOARD + "/", wait_until="domcontentloaded")
        page.wait_for_selector("#epEmail", timeout=10000)
        page.fill("#epEmail", c.ADMIN_EMAIL)
        page.fill("#epPass", c.ADMIN_PASSWORD)
        page.click("#epLoginBtn")
        try:
            page.wait_for_selector("#epLogin", state="detached", timeout=8000)
            return
        except Exception:
            if attempt == 2:
                raise
            page.wait_for_timeout(1500)  # محاولة أخرى — انظر تعليق «فخّ» أعلاه: قد يكون سباقًا عابرًا لا عطلًا


def goto_hash(page, mod):
    page.evaluate(f"window.location.hash = '{mod}'; if(window.go) go('{mod}');")
    page.wait_for_timeout(500)


def wait_settled(page, timeout_ms=10000):
    """ينتظر حتى تهدأ كل نداءات EP.ensure المعلَّقة لهذه الشاشة (لا زمنًا ثابتًا قد يقصر أحيانًا).
    EP.state[key] يتحوّل من 'loading'/'idle' إلى 'ready'/'error' عند اكتمال كل جلب — ولا اعتماد
    عليه لو window.EP غائب (صفحة لم تُحمَّل)."""
    try:
        page.wait_for_function(
            "() => !window.EP || !Object.values(EP.state||{}).some(s => s==='loading')",
            timeout=timeout_ms,
        )
    except Exception:
        pass
    page.wait_for_timeout(300)


def main():
    console_errors = []
    admin_token = dashboard_login()

    # ============================================================ بيانات اختبارية حقيقية طازجة
    section("0) بيانات اختبارية حيّة لكل عائلة (نفس common.py المستعمل في الفحص الآلي)")
    A = new_member("uiA")
    B = new_member("uiB")

    r = requests.post(f"{PLATFORM}/api/trainer/applications", headers=member_hdr(B["token"]), json={
        "headline": "خبير UI — اختبار عرض", "expertise": ["مدني"], "experience_summary": "test",
    })
    ok("(إعداد) trainer application", r.status_code == 200, str(r.status_code))

    r = requests.post(f"{PLATFORM}/api/join-requests", headers=member_hdr(A["token"]), json={
        "section": "marketing", "service": "خدمة تسويق — اختبار عرض", "answers": {}, "service_slugs": [],
    })
    ok("(إعداد) join request", r.status_code == 200, str(r.status_code))

    r = requests.post(f"{PLATFORM}/api/payments/manual", headers=member_hdr(A["token"]), json={
        "kind": "plan", "target_id": "payg", "amount": 50, "country": "EG",
        "method": "instapay", "reference_number": "UI-REF-" + uuid.uuid4().hex[:6],
    })
    ok("(إعداد) manual payment", r.status_code == 200, str(r.status_code))

    r = requests.post(f"{PLATFORM}/api/creative", headers=member_hdr(A["token"]), json={
        "title": "عمل إبداعي — اختبار عرض", "kind": "poem", "body": "بيت شعر.",
    })
    ok("(إعداد) creative item", r.status_code == 200, str(r.status_code))

    r = requests.post(f"{PLATFORM}/api/knowledge", headers=member_hdr(B["token"]), json={
        "title": "كتاب — اختبار عرض", "type": "book", "description": "وصف.", "owns_it": True,
        "rights": "owned_for_sale", "file_url": "https://example.com/ui-fixture.pdf",
        "pricing": {"EG": {"amount": 50, "currency": "EGP", "label": "مصر"}},
    })
    ok("(إعداد) knowledge item", r.status_code == 200, str(r.status_code))

    # دعوة عضو ⇒ awaiting_approval (لطابور الموافقة)
    r = requests.post(f"{PLATFORM}/api/me/invites", headers=member_hdr(A["token"]), json={
        "name": "مدعوّ اختبار عرض", "phone": c.unique_phone(),
    })
    ok("(إعداد) member invite ⇒ awaiting_approval", r.status_code == 200 and
       (r.json().get("invite") or {}).get("status") == "awaiting_approval", str(r.json()))

    # صفّ قائمة انتظار جديد — هذا سيُحوَّل فعليًا من داخل المتصفّح لاحقًا
    wl_email = f"ui-waitlist-{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{PLATFORM}/api/waitlist", json={
        "name": "زائر اختبار عرض", "email": wl_email, "role": "lawyer", "specialty": "civil",
    })
    ok("(إعداد) waitlist row", r.status_code == 200, str(r.status_code))

    time.sleep(0.3)

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for viewport_name, viewport in (("desktop-1280x800", DESKTOP), ("mobile-390x844", MOBILE)):
            section(f"شاشة الوارد (#inbox) — {viewport_name}")
            page = browser.new_page(viewport=viewport)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda exc: console_errors.append(str(exc)))
            ui_login(page)
            ok(f"دخول حقيقي بالنموذج نجح ({viewport_name}) — طبقة الدخول اختفت فعليًا",
               page.locator("#epLogin").count() == 0, "")
            goto_hash(page, "inbox")
            wait_settled(page)
            # HTML الخام (page.content) لا inner_text: الأخيرة تتبع رؤية CSS، وطيّ عمود على الهاتف
            # كان سيقرأ «مش ظاهر» زورًا رغم أن العنصر في الـDOM فعلًا — الفحص هنا هو الوجود لا التخطيط.
            body_text = page.content()
            for label, needle in (
                ("طلب انضمام مدرّب B", B["full_name"]),
                ("طلب انضمام خدمة A", A["full_name"]),
                ("دفعة يدوية A", A["full_name"]),
                ("عمل إبداعي A", A["full_name"]),
                ("كتاب B", B["full_name"]),
            ):
                ok(f"({viewport_name}) {label} ظاهر فعليًا في DOM شاشة الوارد", needle in body_text,
                   f"looked for '{needle}'")
            # لا انسكاب أفقي على الهاتف — الفحص المذكور صراحة في مبدأ الاستجابة
            if viewport is MOBILE:
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                ok("(mobile) لا يوجد انسكاب أفقي في شاشة الوارد", not overflow,
                   f"scrollWidth vs clientWidth overflow={overflow}")
            page.close()

        for viewport_name, viewport in (("desktop-1280x800", DESKTOP), ("mobile-390x844", MOBILE)):
            section(f"شاشة الدعوات (#invites) — طابور الموافقة + قائمة الانتظار + الإعدادات + باب المؤسسين — {viewport_name}")
            page = browser.new_page(viewport=viewport)
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            ui_login(page)
            goto_hash(page, "invites")
            wait_settled(page)
            body_text = page.content()
            ok(f"({viewport_name}) طابور الموافقة: اسم المدعوّ ظاهر", "مدعوّ اختبار عرض" in body_text, "")
            ok(f"({viewport_name}) قائمة الانتظار: الزائر ظاهر", "زائر اختبار عرض" in body_text, "")
            ok(f"({viewport_name}) باب المؤسسين ظاهر (النصّ الثابت)", "باب المؤسسين" in body_text, "")
            ok(f"({viewport_name}) لوحة إعدادات الدعوة ظاهرة (دعوات لكل عضو)", "دعوات لكل عضو" in body_text, "")
            if viewport is MOBILE:
                overflow = page.evaluate(
                    "document.documentElement.scrollWidth > document.documentElement.clientWidth + 2")
                ok("(mobile) لا يوجد انسكاب أفقي في شاشة الدعوات", not overflow, f"overflow={overflow}")
            if viewport is DESKTOP:
                # ---- نموذج إنشاء الدعوة: رقم الواتساب حقل HTML5 required (تحقّق من الخاصيّة الفعلية في الـDOM)
                required = page.eval_on_selector("#inv_ph", "el => el.required")
                ok("حقل رقم الواتساب في نموذج إنشاء الدعوة يحمل خاصيّة required فعليًا", required is True,
                   f"required={required}")
                page.fill("#inv_nm", "بلا هاتف — واجهة")
                page.click("#inv_go")
                page.wait_for_timeout(500)
                validity = page.eval_on_selector("#inv_ph", "el => el.checkValidity()")
                ok("إرسال النموذج بلا رقم هاتف تمنعه صحّة الحقل في المتصفّح (checkValidity=false)",
                   validity is False, f"checkValidity={validity}")

                # ---- تفاعل حيّ كامل: تحويل صفّ قائمة الانتظار إلى دعوة (زرّ حقيقي ⇒ مودال ⇒ رقم ⇒ إرسال)
                section("تفاعل حيّ: تحويل صفّ قائمة الانتظار (زرّ «ابعت دعوة») — نقرات حقيقية")
                btn = page.locator(f'button.wl-inv[data-wl-em="{wl_email}"]')
                ok("زرّ «ابعت دعوة» لصفّ الاختبار موجود في الـDOM", btn.count() == 1, f"count={btn.count()}")
                if btn.count() == 1:
                    btn.click()
                    page.wait_for_selector("#wl_ph", timeout=5000)
                    phone_val = c.unique_phone()
                    page.fill("#wl_ph", phone_val)
                    page.click("#wl_y")
                    page.wait_for_selector("#inv_lk", timeout=5000)
                    link_value = page.input_value("#inv_lk")  # قيمة input[readonly] — لا تظهر في inner_text
                    ok("بعد التحويل: مودال رابط الدعوة الجاهز ظهر فعليًا برابطٍ حقيقي (https)",
                       link_value.startswith("https://"), f"link value = {link_value!r}")
            page.close()

        browser.close()

    js_errors = [e for e in console_errors if e.strip()]
    ok("لا أخطاء JavaScript غير متوقّعة في الكونسول عبر كل الزيارات", len(js_errors) == 0,
       f"{len(js_errors)} error(s): {js_errors[:5]}")

    return c.summary()


if __name__ == "__main__":
    sys.exit(main())
