# -*- coding: utf-8 -*-
"""منصّة وهميّة لـ«الأدوات / الاستوديو» في الداشبورد (docs/v2/tools/SPEC.md): فوق `Market4Platform` (باقي الجسور اللي بتحتاجها اللوحة عند الإقلاع)
بتضيف جسور `docs/TOOLS-API.md` على المنصة بأشكالها بالحرف (`routes/tools_bridge.py` + `services/tools_engine.py` + `services/tools_catalog.py` في r4-int@8c3810a):

  GET  /api/bridge/tools/overview             GET  /api/bridge/tools/recipes             PUT  /api/bridge/tools/recipes/{id}  {by, recipe}
  POST /api/bridge/tools/styles (multipart)   PUT|DELETE /api/bridge/tools/styles/{id}  {by, style}
  GET|PUT /api/bridge/tools/settings {by, settings}                                      POST /api/bridge/tools/test-render/{id} {style_id, real}
  GET  /api/bridge/tools/samples              POST /api/bridge/tools/samples/{id} {action, by}
  GET  /api/bridge/tools/report?from&to       POST /api/bridge/tools/sweep

⛔ صفر شبكة ولا مزوّد: كله في الذاكرة، والصور من PIL (معاينات أماكن فاضية وظلال، لا وجوه). الكتابة حالتها حقيقية والرفض بنفس رسائل المنصة العربية
(حارس السعر وفحوص الإعدادات منسوخة بالمنطق). `writes` = [(method, path, body)]. `down = {path}` ⇒ ٥٠٢ · `tools_missing` ⇒ كل جسور الأدوات ٤٠٤ ·
`forced[(method, path)] = (status, payload)` يفرض ردًّا.
"""
import base64
import copy
import io
import math
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import m4_fixtures as m4fx      # noqa: E402

iso = m4fx.iso
NOT_FOUND = {"detail": "Not Found"}
CURRENCIES = ["EGP", "SAR", "AED", "QAR", "KWD", "OMR", "USD"]
DEFAULT_RATES = {"EGP": 50.0, "SAR": 3.75, "AED": 3.67, "QAR": 3.64, "KWD": 0.31, "OMR": 0.385, "USD": 1.0}
TOPUP_MIN = {"EGP": 100, "SAR": 15, "AED": 15, "QAR": 15, "KWD": 1, "OMR": 1, "USD": 3}
ROLES = ("all", "verified_expert", "judge_prosecutor_masked")
GROUPS = ("photo", "social", "video_cards")
FREE_FIXED = ("none", "once_per_verified_account", "always")
ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
BLOCKED = ["re:(نسبه|معدل)\\s*(ال)?(نجاح|فوز|كسب|ربح)", "re:(ال)?(افضل|اقوي|اشهر|اكبر)\\s", "مجاني", "ميزان العداله"]


def _price(egp, sar, aed, qar, kwd, omr, usd):
    return {"EGP": egp, "SAR": sar, "AED": aed, "QAR": qar, "KWD": kwd, "OMR": omr, "USD": usd}


def _jpeg_data(draw_fn, size=(360, 450), quality=78):
    """معاينة JPEG بـPIL (مكان فاضٍ أو ظل). بلا PIL ⇒ صورة 1×1 صالحة."""
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", size, "#EFE7DA")
        draw_fn(ImageDraw.Draw(im), size)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=quality)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:   # noqa: BLE001
        return "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="


def _office(d, s):
    w, h = s
    d.rectangle([0, 0, w, h], fill="#E9DFD0")
    d.rectangle([w * 0.08, h * 0.1, w * 0.52, h * 0.55], fill="#CFE0E6")          # نافذة
    d.line([w * 0.3, h * 0.1, w * 0.3, h * 0.55], fill="#E9DFD0", width=6)
    d.rectangle([0, h * 0.72, w, h], fill="#8A5A44")                                # مكتب
    d.rectangle([w * 0.62, h * 0.18, w * 0.92, h * 0.34], fill="#B9A58A")          # رف
    d.ellipse([w * 0.7, h * 0.52, w * 0.9, h * 0.72], fill="#6E7F5C")               # نبتة


def _library(d, s):
    w, h = s
    d.rectangle([0, 0, w, h], fill="#7A4B3A")
    cols = ["#9E2B4E", "#C9A25F", "#41566B", "#B5603C", "#3F6A5A", "#E3D3B2"]
    for row in range(5):
        y = h * (0.06 + row * 0.19)
        d.rectangle([0, y + h * 0.15, w, y + h * 0.17], fill="#4B2C20")
        x = 6
        i = row
        while x < w - 14:
            bw = 14 + (i * 7) % 16
            bh = h * (0.09 + ((i * 5) % 6) * 0.012)
            d.rectangle([x, y + h * 0.15 - bh, x + bw, y + h * 0.15], fill=cols[i % len(cols)])
            x += bw + 3
            i += 1


def _entrance(d, s):
    w, h = s
    d.rectangle([0, 0, w, h], fill="#F2EEE7")
    d.rectangle([w * 0.22, h * 0.12, w * 0.78, h * 0.88], fill="#CFE0E6", outline="#8A8F94", width=8)
    d.line([w * 0.5, h * 0.12, w * 0.5, h * 0.88], fill="#8A8F94", width=6)
    d.rectangle([0, h * 0.88, w, h], fill="#BDB3A3")


def _plain(d, s):
    w, h = s
    for i in range(h):
        c = 200 - int(i / h * 40)
        d.line([0, i, w, i], fill=(c, c - 4, c - 10))


def _silhouette(d, s):
    w, h = s
    d.rectangle([0, 0, w, h], fill="#DCD3C4")
    d.ellipse([w * 0.34, h * 0.2, w * 0.66, h * 0.5], fill="#8C8578")
    d.rounded_rectangle([w * 0.18, h * 0.5, w * 0.82, h * 1.05], radius=60, fill="#8C8578")


PLACE_DRAW = {"hs_office": _office, "hs_library": _library, "hs_entrance": _entrance, "hs_plain": _plain}


def place_png(kind="office", size=(600, 450)):
    """صورة مكان فاضٍ (PNG) تُرفع من الاختبار والصور: غرفة اجتماعات فاضية. بلا وجوه."""
    from PIL import Image, ImageDraw
    im = Image.new("RGB", size, "#EFE7DA")
    d = ImageDraw.Draw(im)
    (PLACE_DRAW.get(kind) or _office)(d, size)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def render_png(label_lines=("معاينة تجريبية",), size=(432, 540)):
    """صورة معاينة تجريبية (PNG) للرسم التجريبي: خلفية هادئة وشريط سفلي."""
    try:
        from PIL import Image, ImageDraw
        im = Image.new("RGB", size, "#F2EBDD")
        d = ImageDraw.Draw(im)
        _silhouette(d, size)
        d.rectangle([0, size[1] - 56, size[0], size[1]], fill="#9E2B4E")
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:   # noqa: BLE001
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAHnOcQAAAAABJRU5ErkJggg=="


_HEADSHOT_PROMPT = "Professional headshot of the person in the reference. Setting: {place_prompt}. {touch} No text."
_LINKEDIN_PROMPT = "Wide calm cover scene. Setting: {place_prompt}. {touch} No people, no text."
_POST_PROMPT = "Abstract quiet background. Mood: {place_prompt}. {touch} No people, no text."
_VIDEO_PROMPT = "Gentle motion for 8 seconds. Setting: {place_prompt}. {touch} Keep the face unchanged."


def seed_recipes():
    """الوصفات الخمس بحقولها كما في `seed_recipes()` على المنصة. الإطلاق: «صورتك المهنية» و«كارت خبير أو شهادة» شغّالتين."""
    def mk(rid, title, sub, group, kind, provider, model, mp, tpl, styles, overlay, sizes, variants, est, price, free, wm, allowed, blocked, enabled, sort, inputs):
        return {"id": rid, "title_ar": title, "sub_ar": sub, "group": group, "output_kind": kind, "provider": provider, "model": model, "model_params": mp,
                "prompt_template": tpl, "styles": styles, "inputs": inputs, "overlay_kind": overlay, "sizes": sizes, "variants": variants, "est_cost_usd": est,
                "price": price, "free_rule": free, "watermark_free": wm, "allowed_roles": allowed, "blocked_roles": blocked, "enabled": enabled, "sort": sort,
                "created_at": iso(-200), "updated_at": iso(-100), "updated_by": "system"}
    return [
        mk("headshot", "صورتك المهنية", "من سيلفي إلى صورة في مكتب أو مكتبة", "photo", "image", "openai_image", "gpt-image-1", {"quality": "medium"}, _HEADSHOT_PROMPT,
           ["hs_office", "hs_library", "hs_entrance", "hs_plain"], "headshot_mark", [{"key": "4x5", "w": 1080, "h": 1350}, {"key": "square", "w": 1080, "h": 1080}], 2, 0.12,
           _price(20, 5, 5, 5, 0.4, 0.5, 1), "once_per_verified_account", True, ["all"], [], True, 10, [{"key": "photo", "type": "face_image", "required": True}]),
        mk("card", "كارت خبير أو شهادة", "بطاقة جاهزة للمشاركة، برمز تحقق", "video_cards", "card", "none", "", {}, "", ["card_expert", "card_cert", "card_winner"],
           "expert_card", [{"key": "4x5", "w": 1080, "h": 1350}, {"key": "square", "w": 1080, "h": 1080}], 1, 0.0, _price(0, 0, 0, 0, 0, 0, 0), "always", False, ["all"], [], True, 40,
           [{"key": "name", "type": "auto_name"}]),
        mk("linkedin", "لينكدإن قوي", "صورة غلاف باسمك وصفتك", "social", "image", "openai_image", "gpt-image-1", {"quality": "medium"}, _LINKEDIN_PROMPT,
           ["li_office", "li_library", "li_calm"], "linkedin_cover", [{"key": "linkedin_cover", "w": 1584, "h": 396}], 2, 0.12, _price(40, 10, 10, 10, 0.8, 1, 2), "none", False,
           ["all"], [], False, 20, [{"key": "name", "type": "auto_name"}]),
        mk("post", "بوست جاهز", "نص باسمك على تصميم هادئ", "social", "image", "openai_image", "gpt-image-1", {"quality": "low"}, _POST_PROMPT,
           ["post_quote", "post_answer", "post_bg"], "post_frame", [{"key": "square", "w": 1080, "h": 1080}, {"key": "story", "w": 1080, "h": 1920}], 1, 0.04,
           _price(15, 4, 4, 4, 0.3, 0.4, 0.8), "daily:1", True, ["all"], ["judge_prosecutor_masked"], False, 30, [{"key": "text", "type": "text", "max": 200}]),
        mk("trend_video", "فيديو ترند", "ثمانية ثوانٍ من صورتك بحركة هادئة", "video_cards", "video", "higgsfield_video", "image-to-video", {"duration_s": 8}, _VIDEO_PROMPT,
           ["tv_calm", "tv_light"], "video_mark", [{"key": "story", "w": 1080, "h": 1920}], 1, 0.6, _price(150, 38, 37, 37, 3, 3.8, 10), "none", True, ["all"],
           ["judge_prosecutor_masked"], False, 50, [{"key": "photo", "type": "face_image", "required": True}]),
    ]


def seed_styles():
    def st(sid, rid, title, place, sort, judge_ok=True, roles=None, uses_provider=True, hidden=False, kind="scene", preview=True):
        return {"id": sid, "recipe_id": rid, "title_ar": title, "place_prompt": place, "preview_asset_id": "seed" if sid in PLACE_DRAW else "",
                "preview_data": _jpeg_data(PLACE_DRAW[sid]) if (preview and sid in PLACE_DRAW) else "", "allowed_roles": roles or ["all"], "blocked_roles": [],
                "judge_ok": judge_ok, "uses_provider": uses_provider, "hidden": hidden, "kind": kind, "sort": sort, "enabled": True,
                "created_at": iso(-200), "updated_at": iso(-100), "updated_by": "system"}
    return [
        st("hs_office", "headshot", "مكتب", "a modern lawyer's office with a desk and soft window light", 1, judge_ok=False),
        st("hs_library", "headshot", "مكتبة", "a quiet law library with tall bookshelves and warm light", 2),
        st("hs_entrance", "headshot", "مدخل المكتب", "the bright entrance hall of a professional office", 3, judge_ok=False),
        st("hs_plain", "headshot", "خلفية بسيطة", "a plain softly lit neutral studio backdrop in warm grey", 4),
        st("li_office", "linkedin", "مكتب هادئ", "a calm office interior with a desk and window", 1),
        st("li_library", "linkedin", "مكتبة", "a long law library corridor with warm lamps", 2),
        st("li_calm", "linkedin", "خلفية هادئة", "a quiet abstract gradient in warm wine and paper tones", 3),
        st("post_quote", "post", "اقتباس بسيط", "", 1, uses_provider=False, kind="text"),
        st("post_answer", "post", "سؤال وجواب", "", 2, uses_provider=False, kind="text", roles=["verified_expert"], hidden=True),
        st("post_bg", "post", "خلفية هادئة", "calm, warm, paper-like and professional", 3, kind="background"),
        st("card_expert", "card", "كارت خبير", "", 1, judge_ok=False, uses_provider=False, roles=["verified_expert"], kind="expert_card"),
        st("card_cert", "card", "بطاقة شهادة", "", 2, uses_provider=False, kind="certificate_card"),
        st("card_winner", "card", "بطاقة الفوز", "", 3, uses_provider=False, hidden=True, kind="winner_card"),
        st("tv_calm", "trend_video", "حركة هادئة", "a calm professional office, gentle camera drift", 1),
        st("tv_light", "trend_video", "ضوء دافئ", "warm window light slowly shifting across the scene", 2),
    ]


def seed_samples():
    pv = _jpeg_data(_silhouette)
    return [
        {"id": "ou-a1b2c3d4", "email": "hala.nasr@example.test", "recipe_id": "headshot", "style_id": "hs_library", "created_at": iso(-2), "preview": pv, "sizes": ["4x5", "square"], "paid": True},
        {"id": "ou-e5f6a7b8", "email": "karim.adel@example.test", "recipe_id": "headshot", "style_id": "hs_office", "created_at": iso(-5), "preview": _jpeg_data(_office), "sizes": ["4x5", "square"], "paid": False},
        {"id": "ou-c9d0e1f2", "email": "mona.sami@example.test", "recipe_id": "card", "style_id": "card_expert", "created_at": iso(-9), "preview": pv, "sizes": ["4x5"], "paid": False},
        {"id": "ou-13572468", "email": "yousef.h@example.test", "recipe_id": "headshot", "style_id": "hs_plain", "created_at": iso(-26), "preview": _jpeg_data(_plain), "sizes": ["4x5", "square"], "paid": True},
    ]


def seed_report_rows():
    def row(rid, title, count, ok, fail, cost, rev_cur, rev_usd, guard=False):
        avg = round(cost / count, 4) if count else 0.0
        return {"recipe_id": rid, "title": title, "count": count, "succeeded": ok, "failures": fail, "cost_usd": cost, "revenue_usd": rev_usd,
                "revenue_by_currency": rev_cur, "margin_usd": round(rev_usd - cost, 4), "guard_flag": guard, "avg_cost_usd": avg}
    return [row("headshot", "صورتك المهنية", 31, 29, 2, 3.72, {"EGP": 460, "SAR": 20}, 14.92),
            row("card", "كارت خبير أو شهادة", 12, 12, 0, 0.0, {}, 0.0),
            row("linkedin", "لينكدإن قوي", 0, 0, 0, 0.0, {}, 0.0),
            row("post", "بوست جاهز", 0, 0, 0, 0.0, {}, 0.0),
            row("trend_video", "فيديو ترند", 0, 0, 0, 0.0, {}, 0.0)]


def default_settings():
    return {"daily_cap_usd": 10.0, "daily_cap_max_usd": 20.0, "kill": False, "image_min_multiple": 3.0, "video_min_multiple": 2.5, "rates": dict(DEFAULT_RATES),
            "blocked_terms": list(BLOCKED), "per_user_daily": 10, "per_ip_daily": 30, "free_posts_daily": 1, "next_line": "", "topup_min_by_currency": dict(TOPUP_MIN),
            "topup_max_egp": 10000, "sample_pct": 5, "retry_limit": 3}


def _num(v):
    if isinstance(v, bool):
        raise ValueError("رقم")
    n = float(v)
    if n != n or n in (float("inf"), float("-inf")):
        raise ValueError("رقم")
    return n


class ToolsPlatform(m4fx.Market4Platform):
    def __init__(self, empty=False, **kw):
        super(ToolsPlatform, self).__init__(empty=empty, **kw)
        self.tools_missing = False
        self.tools_settings = default_settings()
        self.tools_recipes = [] if empty else seed_recipes()
        self.tools_styles = [] if empty else seed_styles()
        self.tools_samples = [] if empty else seed_samples()
        self.tools_report = [] if empty else seed_report_rows()
        self.tools_flags = {"tools_enabled": False, "provider": "mock", "topup_enabled": False}
        self.tools_spent = 0.0 if empty else 2.4
        self.tools_ffmpeg = True
        self.tools_raqm = True
        self.tools_legacy = False           # True ⇒ منصة أقدم (قبل r4-int@a5e1e6b): بلا `jobs_today` ولا `topups` ولا `attach_to`، والمنع عند الحذف بلا ٤٠٩
        self.tools_topups = {"by_currency": {"EGP": 1500, "SAR": 45}, "count": 7, "label": "رصيد عملاء مشحون (التزام، مش إيراد)", "is_revenue": False}
        self.attach_fail = False            # True ⇒ ربط المكان بالأداة يفشل: ٥٠٣ والنمط يتشال
        self.sweep_result = {"inputs": 0, "outputs_expired": 0, "outputs_removed": 0, "jobs_stale": 0}
        self.sweeps = []
        self.renders = []
        self._n = 0

    # ---------------------------------------------------------------- التوجيه
    def _route(self, method, path, params, body):
        m = method.upper()
        forced = self.forced.get((m, path))
        if forced is not None:
            return forced
        if path in self.down:
            return 502, {"detail": "تعذر الاتصال"}
        if path.startswith("/api/bridge/tools/"):
            if self.tools_missing:
                return 404, NOT_FOUND
            out = self._tools(m, path, params or {}, body or {})
            if out is not None:
                return out
        return super(ToolsPlatform, self)._route(method, path, params, body)

    def _stamp(self):
        self._n += 1
        return iso(-1 + self._n / 3600.0)

    @staticmethod
    def _by(body):
        return None if str(body.get("by") or "").strip() else (422, {"detail": "لازم نعرف مين اللي بيقرّر"})

    def _recipe(self, rid):
        return next((r for r in self.tools_recipes if r["id"] == rid), None)

    def _style(self, sid):
        return next((s for s in self.tools_styles if s["id"] == sid), None)

    # ---------------------------------------------------------------- الجسور
    def _tools(self, m, path, params, body):
        if path == "/api/bridge/tools/overview" and m == "GET":
            out = {"ok": True, "flags": dict(self.tools_flags), "today": self._cap_state(), "currencies": list(CURRENCIES), "ffmpeg": self.tools_ffmpeg, "raqm": self.tools_raqm}
            if not self.tools_legacy:
                out["jobs_today"] = {"day": iso(0)[:10], "count": sum(r["count"] for r in self.tools_report), "succeeded": sum(r["succeeded"] for r in self.tools_report),
                                     "failures": sum(r["failures"] for r in self.tools_report)}
            return 200, out
        if path == "/api/bridge/tools/recipes" and m == "GET":
            rs = sorted(copy.deepcopy(self.tools_recipes), key=lambda r: (int(r.get("sort") or 0), r["id"]))
            return 200, {"ok": True, "recipes": rs, "styles": copy.deepcopy(self.tools_styles), "roles": list(ROLES), "groups": list(GROUPS),
                         "providers": ["openai_image", "higgsfield_image", "higgsfield_video", "none"], "overlay_kinds": [], "size_keys": [],
                         "free_rules": list(FREE_FIXED) + ["daily:N"]}
        mm = re.match(r"^/api/bridge/tools/recipes/([^/]+)$", path)
        if mm and m == "PUT":
            return self._put_recipe(mm.group(1), body)
        if path == "/api/bridge/tools/styles" and m == "POST":
            return self._create_style(body)
        mm = re.match(r"^/api/bridge/tools/styles/([^/]+)$", path)
        if mm and m == "PUT":
            return self._put_style(mm.group(1), body)
        if mm and m == "DELETE":
            return self._delete_style(mm.group(1))
        if path == "/api/bridge/tools/settings" and m == "GET":
            return 200, {"ok": True, "settings": copy.deepcopy(self.tools_settings), "limits": {"daily_cap_absolute_max_usd": 50.0}}
        if path == "/api/bridge/tools/settings" and m == "PUT":
            return self._put_settings(body)
        mm = re.match(r"^/api/bridge/tools/test-render/([^/]+)$", path)
        if mm and m == "POST":
            return self._test_render(mm.group(1), body)
        if path == "/api/bridge/tools/samples" and m == "GET":
            limit = int(params.get("limit") or 50)
            rows = [{k: v for k, v in s.items() if k != "paid"} for s in self.tools_samples][:limit]
            return 200, {"ok": True, "samples": copy.deepcopy(rows)}
        mm = re.match(r"^/api/bridge/tools/samples/([^/]+)$", path)
        if mm and m == "POST":
            return self._moderate(mm.group(1), body)
        if path == "/api/bridge/tools/report" and m == "GET":
            return self._report(params)
        if path == "/api/bridge/tools/sweep" and m == "POST":
            self.sweeps.append(1)
            return 200, dict({"ok": True}, **self.sweep_result)
        return None

    def _cap_state(self):
        s = self.tools_settings
        cap = min(float(s["daily_cap_usd"]), float(s["daily_cap_max_usd"]), 50.0)
        out = {"cap_usd": cap, "spent_usd": round(self.tools_spent, 4), "remaining_usd": round(max(0.0, cap - self.tools_spent), 4), "kill": bool(s["kill"]), "paused": False, "reason": None}
        if s["kill"]:
            out.update(paused=True, reason="kill")
            return out
        ests = [float(r["est_cost_usd"]) for r in self.tools_recipes if r["enabled"] and r["provider"] != "none" and float(r["est_cost_usd"]) > 0]
        if ests and cap - self.tools_spent < min(ests):
            out.update(paused=True, reason="cap")
        return out

    # —— الوصفات
    def _guard(self, r):
        est = float(r.get("est_cost_usd") or 0)
        if est <= 0 or r.get("provider") in (None, "", "none"):
            return None
        s = self.tools_settings
        video = r.get("output_kind") == "video" or str(r.get("provider") or "").endswith("video")
        mult = float(s["video_min_multiple"] if video else s["image_min_multiple"])
        rule = r.get("free_rule", "none")
        free_ok = rule in FREE_FIXED or re.fullmatch(r"daily:\d{1,3}", str(rule)) is not None
        for cur, val in (r.get("price") or {}).items():
            v = float(val or 0)
            if v <= 0:
                if not free_ok or rule == "none":
                    return "سعر %s صفر والتكلفة أكبر من صفر" % cur
                continue
            if v / float(s["rates"].get(cur) or 1.0) + 1e-9 < est * mult:
                return "سعر %s أقل من الحد الأدنى (التكلفة × %g)" % (cur, mult)
        return None

    def _put_recipe(self, rid, body):
        bad = self._by(body)
        if bad:
            return bad
        r = body.get("recipe")
        if not isinstance(r, dict):
            return 422, {"detail": "recipe مطلوب"}
        if str(r.get("id") or rid) != rid:
            return 422, {"detail": "معرّف الوصفة لا يطابق المسار"}
        r = copy.deepcopy(r)
        r["id"] = rid
        if r.get("group") not in GROUPS:
            return 422, {"detail": "المجموعة غير معروفة"}
        for k in ("allowed_roles", "blocked_roles"):
            if any(x not in ROLES for x in (r.get(k) or [])):
                return 422, {"detail": "دور غير معروف"}
        known = {s["id"] for s in self.tools_styles}
        missing = [x for x in (r.get("styles") or []) if x not in known]
        if missing:
            return 422, {"detail": "نمط غير موجود: " + ", ".join(missing)}
        for cur in (r.get("price") or {}):
            if cur not in CURRENCIES:
                return 422, {"detail": "عملة غير معروفة: " + str(cur)}
        prev = self._recipe(rid)
        turning_off = (not self.tools_legacy) and r.get("enabled") is False and prev is not None and r.get("price") == prev.get("price")
        gmsg = None if turning_off else self._guard(r)          # الإيقاف بلا تغيير سعر ما يتحرسش (r4-int@a5e1e6b)
        if gmsg:
            return 422, {"detail": gmsg}
        r["updated_at"], r["updated_by"] = self._stamp(), body["by"]
        r["created_at"] = (prev or {}).get("created_at") or r["updated_at"]
        self.writes.append(("PUT", "/api/bridge/tools/recipes/%s" % rid, copy.deepcopy(body)))
        if prev is None:
            self.tools_recipes.append(r)
        else:
            prev.update(r)
        return 200, {"ok": True, "recipe": copy.deepcopy(self._recipe(rid))}

    # —— الأنماط
    @staticmethod
    def _sniff_ok(head):
        return head.startswith("\x89PNG") or head.startswith("\xff\xd8\xff") or head.startswith("RIFF")

    def _create_style(self, body):
        bad = self._by(body)
        if bad:
            return bad
        sid, rid = str(body.get("id") or ""), str(body.get("recipe_id") or "")
        if self._style(sid):
            return 409, {"detail": "نمط بنفس المعرّف موجود"}
        if not ID_RE.match(sid):
            return 422, {"detail": "معرّف النمط حروف إنجليزية صغيرة وأرقام وشرطة سفلية"}
        if not self._recipe(rid):
            return 422, {"detail": "الوصفة غير موجودة"}
        title = str(body.get("title_ar") or "").strip()
        if not title or len(title) > 60:
            return 422, {"detail": "اكتب اسم النمط (أقل من ٦٠ حرفًا)"}
        f = body.get("__file__")
        row = {"id": sid, "recipe_id": rid, "title_ar": title, "place_prompt": str(body.get("place_prompt") or ""), "allowed_roles": ["all"], "blocked_roles": [],
               "judge_ok": str(body.get("judge_ok")).lower() != "false", "uses_provider": str(body.get("uses_provider")).lower() != "false", "hidden": False,
               "kind": str(body.get("kind") or "scene"), "sort": int(body.get("sort") or 0), "enabled": True, "preview_data": "", "preview_asset_id": "",
               "created_at": self._stamp(), "updated_at": self._stamp(), "updated_by": body["by"]}
        if f:
            if not self._sniff_ok(f.get("head") or ""):
                return 422, {"detail": "الملف ليس صورة صالحة (JPG أو PNG أو WebP)"}
            row["preview_data"] = _jpeg_data(_plain)       # المنصة بتصغّر الصورة المرفوعة ٤٨٠px — هنا معاينة بديلة
            row["preview_asset_id"] = "v1"
        attach = str(body.get("attach_to") or "").strip() if not self.tools_legacy else ""
        if attach and attach != rid:
            return 422, {"detail": "الربط لازم يكون بنفس الأداة (attach_to = recipe_id)"}
        self.writes.append(("POST", "/api/bridge/tools/styles", copy.deepcopy(body)))
        if attach and self.attach_fail:
            return 503, {"detail": "تعذّر ربط المكان بالأداة، لم يُحفظ شيء. حاول مرة أخرى"}      # المنصة بتشيل النمط: لا نمط يتيم
        self.tools_styles.append(row)
        out = {"ok": True, "style": copy.deepcopy(row), "attached": False}
        if attach:
            rec = self._recipe(attach)
            if sid not in rec["styles"]:
                rec["styles"].append(sid)
            rec["updated_at"], rec["updated_by"] = self._stamp(), body["by"]
            out.update(attached=True, recipe=copy.deepcopy(rec))
        return 200, out

    def _put_style(self, sid, body):
        bad = self._by(body)
        if bad:
            return bad
        cur = self._style(sid)
        if cur is None:
            return 404, {"detail": "النمط غير موجود"}
        st = body.get("style") or {}
        if "title_ar" in st and (not str(st["title_ar"]).strip() or len(str(st["title_ar"])) > 60):
            return 422, {"detail": "اكتب اسم النمط (أقل من ٦٠ حرفًا)"}
        if len(str(st.get("place_prompt") or "")) > 400:
            return 422, {"detail": "وصف المكان أقصر من ٤٠٠ حرف"}
        if st.get("preview_data"):
            d = str(st["preview_data"])
            if not d.startswith("data:image/") or "," not in d:
                return 422, {"detail": "صورة المعاينة غير صالحة"}
        self.writes.append(("PUT", "/api/bridge/tools/styles/%s" % sid, copy.deepcopy(body)))
        for k in ("title_ar", "place_prompt", "judge_ok", "sort", "preview_data"):
            if k in st:
                cur[k] = st[k]
        if st.get("preview_data"):
            cur["preview_asset_id"] = "v%d" % (int(str(cur.get("preview_asset_id") or "v0").lstrip("vseed") or 0) + 1)
        cur["updated_at"], cur["updated_by"] = self._stamp(), body["by"]
        return 200, {"ok": True, "style": copy.deepcopy(cur)}

    def _delete_style(self, sid):
        cur = self._style(sid)
        if cur is None:
            return 404, {"detail": "النمط غير موجود"}
        if not self.tools_legacy:
            if cur.get("kind") in ("expert_card", "certificate_card", "winner_card"):
                return 409, {"detail": {"code": "style_protected", "message": "هذا النمط مربوط بشاشات المنصة ولا يُحذف. يمكنك إخفاؤه"}}
            if cur.get("enabled", True) is not False:
                for r in self.tools_recipes:
                    if r["enabled"] and sid in r["styles"] and not [o for o in r["styles"] if o != sid and (self._style(o) or {}).get("enabled", True) is not False]:
                        return 409, {"detail": {"code": "last_style", "message": "هذا آخر مكان شغّال في أداة شغّالة. أوقف الأداة أولًا أو أضف مكانًا آخر"}}
        self.writes.append(("DELETE", "/api/bridge/tools/styles/%s" % sid, None))
        self.tools_styles = [s for s in self.tools_styles if s["id"] != sid]
        for r in self.tools_recipes:
            r["styles"] = [x for x in r["styles"] if x != sid]
        return 200, {"ok": True}

    # —— الإعدادات
    def _put_settings(self, body):
        bad = self._by(body)
        if bad:
            return bad
        patch = body.get("settings")
        if not isinstance(patch, dict):
            return 422, {"detail": "settings مطلوب"}
        cur = self.tools_settings
        allowed = set(default_settings())
        for k in patch:
            if k not in allowed:
                return 422, {"detail": "حقل غير معروف: " + str(k)}
        clean = {}
        try:
            if "daily_cap_max_usd" in patch:
                v = _num(patch["daily_cap_max_usd"])
                if not (0 < v <= 50):
                    return 422, {"detail": "أعلى سقف مسموح به لا يزيد على ٥٠ دولارًا"}
                clean["daily_cap_max_usd"] = v
            cap_max = clean.get("daily_cap_max_usd", float(cur["daily_cap_max_usd"]))
            if "daily_cap_usd" in patch:
                v = _num(patch["daily_cap_usd"])
                if not (0 < v <= cap_max):
                    return 422, {"detail": "السقف اليومي لا يتجاوز %g دولارًا" % cap_max}
                clean["daily_cap_usd"] = v
            elif "daily_cap_max_usd" in clean and float(cur["daily_cap_usd"]) > cap_max:
                clean["daily_cap_usd"] = cap_max
            if "kill" in patch:
                if not isinstance(patch["kill"], bool):
                    return 422, {"detail": "kill يجب أن تكون صح أو خطأ"}
                clean["kill"] = patch["kill"]
            for k in ("image_min_multiple", "video_min_multiple"):
                if k in patch:
                    v = _num(patch[k])
                    if not (1.0 <= v <= 20.0):
                        return 422, {"detail": "المضاعِف بين ١ و٢٠"}
                    clean[k] = v
            for k, lo, hi in (("per_user_daily", 1, 200), ("per_ip_daily", 1, 1000), ("free_posts_daily", 0, 50), ("sample_pct", 0, 100), ("retry_limit", 0, 10)):
                if k in patch:
                    v = patch[k]
                    if isinstance(v, bool) or not isinstance(v, int) or not (lo <= v <= hi):
                        return 422, {"detail": "%s بين %d و%d" % (k, lo, hi)}
                    clean[k] = v
            if "next_line" in patch:
                s = str(patch["next_line"] or "").strip()
                if len(s) > 80:
                    return 422, {"detail": "سطر «الجاي» أقصر من ٨٠ حرفًا"}
                clean["next_line"] = s
            if "rates" in patch:
                r = {}
                for c, v in patch["rates"].items():
                    if c not in CURRENCIES:
                        return 422, {"detail": "عملة غير معروفة: " + str(c)}
                    n = _num(v)
                    if n <= 0:
                        return 422, {"detail": "سعر الصرف لازم يكون أكبر من صفر"}
                    r[c] = n
                clean["rates"] = dict(cur["rates"], **r)
            if "topup_min_by_currency" in patch:
                r = {}
                for c, v in patch["topup_min_by_currency"].items():
                    if c not in CURRENCIES:
                        return 422, {"detail": "عملة غير معروفة: " + str(c)}
                    n = _num(v)
                    if n <= 0 or n != int(n):
                        return 422, {"detail": "أقل شحنة رقم صحيح أكبر من صفر"}
                    r[c] = int(n)
                clean["topup_min_by_currency"] = dict(cur["topup_min_by_currency"], **r)
            if "topup_max_egp" in patch:
                n = _num(patch["topup_max_egp"])
                if n < 100 or n != int(n):
                    return 422, {"detail": "سقف الشحن رقم صحيح لا يقل عن ١٠٠ جنيه"}
                clean["topup_max_egp"] = int(n)
        except (ValueError, TypeError):
            return 422, {"detail": "قيمة غير صالحة"}
        self.writes.append(("PUT", "/api/bridge/tools/settings", copy.deepcopy(body)))
        cur.update(clean)
        return 200, {"ok": True, "settings": copy.deepcopy(cur)}

    # —— المعاينة والعيّنات والتقرير
    def _test_render(self, rid, body):
        r = self._recipe(rid)
        if r is None:
            return 404, {"detail": {"code": "not_found", "message": "غير موجود"}}
        if body.get("real"):
            return 422, {"detail": {"code": "mock_only", "message": "المعاينة الحقيقية تحتاج وضع المزوّد الحيّ"}}
        sid = body.get("style_id") or ""
        if sid and not self._style(sid):
            return 422, {"detail": {"code": "style_unknown", "message": "اختر مكانًا من القائمة"}}
        self.renders.append((rid, sid))
        ai = r["provider"] != "none"
        imgs = [] if r["output_kind"] == "video" else [render_png() for _ in range(max(1, int(r.get("variants") or 1)))]
        return 200, {"ok": True, "images": imgs, "real": False, "provider": "mock", "cost_usd": 0.0, "uses_provider": ai}

    def _moderate(self, oid, body):
        bad = self._by(body)
        if bad:
            return bad
        o = next((s for s in self.tools_samples if s["id"] == oid), None)
        if o is None:
            return 404, {"detail": {"code": "not_found", "message": "غير موجود"}}
        act = body.get("action")
        if act not in ("ok", "hide", "ban_user"):
            return 422, {"detail": {"code": "bad_action", "message": "إجراء غير معروف"}}
        self.writes.append(("POST", "/api/bridge/tools/samples/%s" % oid, copy.deepcopy(body)))
        gone = [s for s in self.tools_samples if (s["email"] == o["email"] if act == "ban_user" else s["id"] == oid)]
        refunded = sum(1 for s in gone if s.get("paid")) if act != "ok" else 0
        self.tools_samples = [s for s in self.tools_samples if s not in gone]
        return 200, {"ok": True, "id": oid, "status": "ok" if act == "ok" else "hidden", "banned": act == "ban_user", "refunded": refunded}

    def _report(self, params):
        frm, to = params.get("from") or "", params.get("to") or ""
        rows = copy.deepcopy(self.tools_report)
        if frm and to and frm != to:                       # أسبوع: أعداد أكبر
            for r in rows:
                for k in ("count", "succeeded", "failures"):
                    r[k] = r[k] * 6
                for k in ("cost_usd", "revenue_usd", "margin_usd"):
                    r[k] = round(r[k] * 6, 4)
                r["revenue_by_currency"] = {c: v * 6 for c, v in r["revenue_by_currency"].items()}
        out = {"ok": True, "recipes": rows, "today": self._cap_state(), "from": frm, "to": to}
        if self.tools_topups is not None and not self.tools_legacy:
            out["topups"] = copy.deepcopy(self.tools_topups)
        return 200, out
