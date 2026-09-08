"""مساعدات مشتركة لسكريبتات B2 (صناديق الأدمن عبر الطبقتين — المنصّة والداشبورد).

لا تُشغَّل بـ pytest مباشرة (كل ملف سكريبت قابل للتشغيل بمفرده بـ ``python3 xxx.py``)؛
هذا الملف مجرّد عدّة اتصال HTTP + طباعة موحّدة. راجع AUDIT/01_e2e_dashboard.md للسياق.

البيئة المطلوبة قبل التشغيل (شغّالة بالفعل وقت كتابة هذا الملف — راجع التقرير):
  * mongod على 127.0.0.1:27202
  * uvicorn (المنصّة) على 127.0.0.1:8202  — METRICS_SECRET=test-secret
  * Flask (الداشبورد) على 127.0.0.1:5002 — PLATFORM_API_URL=http://127.0.0.1:8202,
    METRICS_SECRET=test-secret, ADMIN_EMAIL/ADMIN_PASSWORD كما في السكريبت.
"""
import json
import sys
import time
import uuid

import requests

PLATFORM = "http://127.0.0.1:8202"
DASHBOARD = "http://127.0.0.1:5002"
METRICS_SECRET = "test-secret"
BRIDGE_HDR = {"X-ELP-Metrics-Secret": METRICS_SECRET}

ADMIN_EMAIL = "audit-admin@elprofessor.net"
ADMIN_PASSWORD = "Audit-Admin-Pass-123"

PASS = []
FAIL = []


def ok(label, cond, detail=""):
    if cond:
        PASS.append(label)
        print(f"  [OK]   {label}" + (f" — {detail}" if detail else ""))
    else:
        FAIL.append(label)
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))
    return cond


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def summary():
    print("\n" + "-" * 70)
    print(f"TOTAL: {len(PASS)} OK / {len(FAIL)} FAIL")
    if FAIL:
        print("FAILED:")
        for f in FAIL:
            print(f"  - {f}")
    print("-" * 70)
    return 1 if FAIL else 0


# --------------------------------------------------------------------------- platform bridge (no auth — shared secret)
def bridge(method, path, **kw):
    r = requests.request(method, f"{PLATFORM}{path}", headers=BRIDGE_HDR, timeout=15, **kw)
    return r


# --------------------------------------------------------------------------- dashboard admin session
def dashboard_login(email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    r = requests.post(f"{DASHBOARD}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]


def dash(method, path, token, **kw):
    hdrs = kw.pop("headers", {})
    hdrs["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{DASHBOARD}{path}", headers=hdrs, timeout=15, **kw)


# --------------------------------------------------------------------------- member journeys (invite ⇒ account)
def unique_phone():
    # Egyptian-looking mobile, unique enough per run to avoid phone_key collisions across reruns.
    return "+2010" + str(uuid.uuid4().int)[:8]


def create_founder_invite(name, phone=None, email=None):
    phone = phone or unique_phone()
    body = {"name": name, "phone": phone}
    if email:
        body["email"] = email
    r = bridge("POST", "/api/bridge/invites", json=body)
    r.raise_for_status()
    data = r.json()
    return data["invite"], data["link"], phone


def complete_invite_journey(token, *, email, password, phone, full_name, roles=None):
    """أقصر مسارٍ حقيقيّ ينشئ حسابًا: فتح ⇒ صفات (فارغة = خريج) ⇒ pain-seen ⇒ complete."""
    roles = roles if roles is not None else ["graduate"]  # لا تمرين توثيق (ق٨) — أقصر مسار
    r = requests.get(f"{PLATFORM}/api/invite/{token}")
    r.raise_for_status()
    r = requests.post(f"{PLATFORM}/api/invite/{token}/roles", json={"roles": roles})
    r.raise_for_status()
    r = requests.post(f"{PLATFORM}/api/invite/{token}/pain-seen", json={})
    r.raise_for_status()
    r = requests.post(
        f"{PLATFORM}/api/invite/{token}/complete",
        json={
            "email": email, "password": password, "phone": phone,
            "full_name": full_name, "accept_terms": True,
        },
    )
    if r.status_code != 200:
        raise RuntimeError(f"complete failed {r.status_code}: {r.text[:400]}")
    return r.json()


def member_login(email, password):
    r = requests.post(f"{PLATFORM}/api/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def member_hdr(token):
    return {"Authorization": f"Bearer {token}"}


def new_member(tag):
    """يصنع دعوةً من المؤسس ويكمّلها ⇒ (email, password, access_token, phone, full_name)."""
    uid = uuid.uuid4().hex[:8]
    name = f"مستخدم اختبار {tag} {uid}"
    invite, link, phone = create_founder_invite(name)
    email = f"audit-{tag}-{uid}@example.com"
    password = "Str0ng-Audit-Pass-1"
    complete_invite_journey(invite["token"], email=email, password=password, phone=phone, full_name=name)
    token = member_login(email, password)
    return {"email": email, "password": password, "token": token, "phone": phone,
            "full_name": name, "invite_token": invite["token"]}
