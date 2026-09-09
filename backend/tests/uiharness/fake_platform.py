# -*- coding: utf-8 -*-
"""منصّةٌ وهميّة تقف مكان `api.elprofessor.net` أثناء اختبار الواجهة وحدها.

تُشغَّل كعمليةٍ منفصلة:  python3 fake_platform.py <port>

⛔ صفر اتصالٍ بالإنتاج: كل جسرٍ يُنادى هنا يردّ حمولةً ثابتةً مكتوبةً بيدنا، فالمقاس الذي
يخرج من الاختبار مقاسُ **الواجهة** لا مقاسُ حالة الخادم الحيّ. الحمولتان المهمّتان هما
`ops/queue` و`ops/pnl` — الجسران اللذان لم يكن أحدٌ يقرؤهما قبل هذه الموجة.
"""
import datetime
import json
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUEUE = {
    "generated_at": "2026-09-09T08:00:00+00:00",
    "trainer_applications_pending": {"count": 3, "oldest_hours": 51.2, "names": ["أحمد", "منى", "خالد"]},
    "courses_pending": {"count": 1, "titles": ["عقود المقاولات"]},
    "manual_payments_pending": {"count": 2, "oldest_hours": 30.0, "ages_hours": [30.0, 4.0]},
    "wallet_payouts_pending": {"count": 1, "total_amount": 1200.0, "oldest_hours": 9.0},
    # أمرا دفعٍ **واردان** عالقان عند `created` — اتجاهٌ معاكس تمامًا لسحوبات المحافظ، ولهما
    # تبويبهما في «المالية». وجودهما في الطقم هو ما يجعل اختبارَ الوجهة قابلًا للسقوط أصلًا:
    # بصفرٍ كانت الشارة والتبويب يتّفقان على «لا شيء» فيمرّ الخطأ صامتًا.
    "stuck_card_payments": {"count": 2, "orders": [
        {"id": "pay-stuck-1", "user_email": "nour@example.test", "amount": 750.0,
         "currency": "EGP", "kind": "course", "gateway": "paytabs",
         "created_at": "2026-09-07T10:00:00+00:00"},
        {"id": "pay-stuck-2", "user_email": "omar@example.test", "amount": 149.0,
         "currency": "EGP", "kind": "verify", "gateway": "stripe",
         "created_at": "2026-09-08T14:30:00+00:00"},
    ]},
    "course_interests_24h": 7,
    "training_interests_24h": 2,
    "course_split_pending": {"count": 0, "rows": []},
    "testimonials_pending": 0,
    "topics_drafts": 311,
    "founding_leads_new": {"count": 9, "oldest_hours": 1600.0},
    "lead_magnet_24h": {"count_24h": 4, "awaiting_asset": 6},
    "lead_magnet_awaiting_asset": 6,
    "live_needs_decision": [{"slug": "live-1", "title": "ورشة حيّة", "live_status": "needs_decision",
                             "reserved_count": 4, "quorum": 8}],
    "heartbeats": {"tick_last": "2026-09-09T07:00:00", "remind_last": None,
                   "sla_last": None, "backup_last": None},
    "alerts": ["⏰ طلب بلا أول رد منذ 40 ساعة: مراجعة عقد إيجار"],
}

PNL = {
    "ok": True,
    "month": "2026-09",
    "revenue_lines": [
        {"key": "consults", "label": "استشارات", "currency": "EGP", "amount": 0.0, "count": 0},
        {"key": "courses", "label": "دورات", "currency": "SAR", "amount": 750.0, "count": 2},
        {"key": "verify", "label": "توثيق إجابات", "currency": "EGP", "amount": 0.0, "count": 0},
    ],
    "totals_by_currency": {"EGP": 0.0, "SAR": 750.0},
    "total": {"amount": 0.0, "currency": "EGP", "label": "إجمالي الإيراد بالجنيه"},
    "revenue_other_currencies": {"SAR": 750.0},
    "refunds_by_currency": {},
    "costs": {"lines": [
        {"key": "infra", "label": "بنية تحتية واستضافة (تقديري/شهري)", "amount": 800.0},
        {"key": "ai", "label": "تكلفة الذكاء الاصطناعي (تقديري — 4 سؤال × 0.35 ج)", "amount": 1.4},
    ], "total": 801.4, "currency": "EGP"},
    "net": {"amount": -801.4, "currency": "EGP", "label": "الصافي بالجنيه (بعد التكاليف التقديرية)"},
    "notes": ["الإيراد = مدفوعات حالتها «مدفوع» تمّت خلال الشهر (تاريخ التحصيل).",
              "العملات لا تُجمع ولا تُحوَّل تلقائيًا — الصافي بالجنيه فقط."],
}

# دفعتان يدويّتان بانتظار التأكيد: هما ما يوجّهه الوارد إلى «الضمان والنزاعات».
MANUAL_PAYMENTS = {"payments": [
    {"id": "mp-1", "user_name": "سلمى عبد الله", "user_email": "salma@example.test",
     "product_label": "استشارة عقود", "amount": 450, "currency": "EGP", "method": "InstaPay",
     "reference_number": "IP-99120", "screenshot_url": "https://example.test/receipt-1.png"},
    {"id": "mp-2", "user_name": "ياسر فؤاد", "user_email": "yasser@example.test",
     "product_label": "دورة التحكيم", "amount": 1200, "currency": "EGP", "method": "فودافون كاش",
     "reference_number": "VF-3311", "screenshot_url": ""},
]}

# سحب محفظةٍ **واحد** معلَّق — هو نفسه الذي يعدّه `wallet_payouts_pending` في الطابور أعلاه
# (نفس المجموعة ونفس الفلتر ونفس المبلغ). العدد هنا هو الحارس الحقيقي لعطل «الشارة ١
# والقائمة ٠»: أي عودةٍ لمصدرين مختلفين تُسقط الاختبار فورًا.
WALLET_PAYOUTS = {"count": 1, "payouts": [
    {"id": "po-1", "user_email": "hala@example.test", "user_name": "د. هالة سمير",
     "user_phone": "01000000001", "amount": 1200.0, "currency": "EGP", "status": "pending",
     "method": "إنستاباي", "destination": "hala@instapay", "reason": "طلب سحب",
     "created_at": "2026-09-09T00:00:00+00:00", "age_hours": 9.0, "fx_alert": False},
]}

# باقتان حيّتان من المنصّة (`/bridge/plans`): بدونهما شبكة الباقات فارغة، ولا كارت يُفتح،
# ولا مسار حذفٍ يُختبَر — فيمرّ عطل «الباقات تهرب من تبويب المالية» بلا حارس.
PLANS = {"plans": [
    {"id": "free", "name": "المجانية", "is_free": True, "active": True,
     "features": ["تصفّح المواضيع", "سؤال واحد يوميًّا"], "prices": {}},
    {"id": "pro", "name": "الاحترافية", "is_free": False, "active": True,
     "features": ["أسئلة بلا حدّ", "أولوية في الردّ"],
     "prices": {"EG": {"amount": 199.0, "currency": "EGP"},
                "SA": {"amount": 39.0, "currency": "SAR"},
                "default": {"amount": 12.0, "currency": "USD"}}},
]}

# طلب مدرّبٍ واحد: يضمن وجود شريحة «قرارات» بجانب «رسائل» و«فلوس».
TRAINER_APPS = {"applications": [
    {"id": "ta-1", "full_name": "د. هالة سمير", "user_email": "hala@example.test",
     "headline": "محكّمة معتمدة — ١٢ سنة"},
]}

# دعوات: **ثلاث** بانتظار الموافقة (`awaiting_approval`) وواحدة مُرسَلة. الشارة على «الدعوات»
# لازم تقرأ الثلاثة وحدها لا الأربعة — «فيه شغل عندك» مش «فيه دعوات في الدنيا». والأقدم منها
# عمرها ٣ أيام، فشرط «تنبيه» (أقدم من ٢٤ ساعة) يتحقّق ويُختبَر.
_NOW = datetime.datetime.now(datetime.timezone.utc)


def _iso(hours_ago):
    return (_NOW - datetime.timedelta(hours=hours_ago)).isoformat()


INVITES = {"count": 4, "invites": [
    {"id": "inv-1", "name": "منال حسن", "email": "manal@example.test",
     "status": "awaiting_approval", "created_at": _iso(72), "generation": 2},
    {"id": "inv-2", "name": "طارق سيد", "email": "tarek@example.test",
     "status": "awaiting_approval", "created_at": _iso(5), "generation": 2},
    {"id": "inv-3", "name": "رنا مجدي", "email": "rana@example.test",
     "status": "awaiting_approval", "created_at": _iso(2), "generation": 3},
    {"id": "inv-4", "name": "سيف الدين", "email": "saif@example.test",
     "status": "sent", "created_at": _iso(10), "generation": 1,
     "link": "https://example.test/i/abc"},
]}

# ⛔ الشركاء **ليسوا** من المنصّة: `/api/partners` دفترُ الداشبورد نفسه في SQLite —
# فبذرُهم يحدث في `run_dash.py` لا هنا. خطأٌ سهل: صفٌّ يُكتب هنا يبقى غير مقروء للأبد.
ROUTES = {
    "/api/bridge/invites": INVITES,
    "/api/bridge/ops/queue": QUEUE,
    "/api/bridge/ops/pnl": PNL,
    "/api/bridge/manual-payments": MANUAL_PAYMENTS,
    "/api/bridge/wallet-payouts": WALLET_PAYOUTS,
    "/api/bridge/plans": PLANS,
    "/api/bridge/trainer-applications": TRAINER_APPS,
    "/api/admin/metrics": {"customers": {"total": 10}},
}


class H(BaseHTTPRequestHandler):
    def _send(self, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ROUTES:
            return self._send(ROUTES[path])
        # أي جسرٍ آخر: فارغٌ صادق (لا صفوف مخترعة) — الشاشات تعرض «مفيش» لا بيانات وهمية.
        return self._send([])

    def do_POST(self):
        return self._send({"ok": True})

    def do_PUT(self):
        return self._send({"ok": True})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    # ⛔ خادمٌ أحاديّ الخيط كان يُسلسِل نداءات الجسر: اللوحة تطلب عشرة طوابير معًا، فتقف
    # الصفحة عند `networkidle` وتسقط الاختبارات لسببٍ لا علاقة له بما تقيسه.
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
