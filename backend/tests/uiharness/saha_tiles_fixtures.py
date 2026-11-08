# -*- coding: utf-8 -*-
"""منصّة وهميّة لمربّعات «الساحة» و«الديوان» في الداشبورد (docs/v2/saha-tiles/SPEC.md): فوق `V2Platform` بتضيف جسور
`SAHA-DIWAN-API.md` بأشكالها بالحرف (أخبار · نقاشات وآراء · فرص · إعداد · استيراد · تذكير · أعمال · تعليقات · تحديات · تقرير).

  GET  /api/bridge/news[?status]          PUT  /api/bridge/news/{id}               POST /api/bridge/news/run
  GET  /api/bridge/topics[?status]        GET  /api/bridge/opinions?status&topic_id
  POST /api/bridge/opinions/{id}/reject|approve
  GET  /api/bridge/jobs?review_status&kind   GET|PUT|DELETE /api/bridge/jobs/{id}   POST /api/bridge/jobs   POST /api/bridge/jobs/{id}/decide
  GET|PUT /api/bridge/opportunities/settings   POST /api/bridge/opportunities/import-seed[?dry_run=true]   POST /api/bridge/opportunities/run-reminders
  GET /api/bridge/creative?status&challenge_id   POST /api/bridge/creative/{id}/decide   PUT /api/bridge/creative/{id}
  GET /api/bridge/diwan/comments?status   POST /api/bridge/diwan/comments/{id}/hide
  GET|POST /api/bridge/diwan/challenges   PUT /api/bridge/diwan/challenges/{id}   POST /api/bridge/diwan/challenges/{id}/winners
  GET /api/bridge/diwan/report?days

⛔ صفر شبكة: كله في الذاكرة، والكتابة حالتها حقيقية ورفضها بنفس رسائل المنصة العربية. `writes` = [(method, path, params, body)].
`down = {path}` ⇒ ٥٠٣ · `missing = {path}` ⇒ ٤٠٤ «Not Found» · `forced[(method, path)] = (status, payload)` يفرض ردًّا.
⛔ الأرقام والأسماء كلها عربية ولا رقم لاتيني ظاهر (الشاشة تعرض الروابط والإيميلات بلا أرقام).
"""
import copy
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import v2_fixtures as v2fx      # noqa: E402

NOT_FOUND = {"detail": "Not Found"}


def _news(i, title, status="draft", category="أخرى", **kw):
    row = {"id": "n-%s" % i, "title": title, "summary": "ملخص قصير للخبر عن " + title, "body": "نص الخبر الكامل عن " + title + " كما وصل من المصدر.", "source_name": "جريدة الأهرام",
           "source_url": "https://source.example.test/news-%s" % i, "extra_sources": [], "country": "EG", "specialty": "", "target_audience": "عام", "status": status,
           "is_published": status == "published", "created_at": "2026-11-01T08:00:00Z", "published_at": "", "category": category, "featured": False, "cover_url": "",
           "related_product": None, "topic_id": None}
    row.update(kw)
    return row


def _job(i, title, kind="grant", review="pending", **kw):
    row = {"id": "job-%s" % i, "title": title, "title_en": "", "employer": "", "place": "لندن", "country": "GB", "employment_type": "", "specialty": "", "body": "",
           "source_url": "https://grants.example.test/s-%s" % i, "official_url": "https://grants.example.test/o-%s" % i, "source_label": "", "posted_at": "",
           "expires_at": "", "expired": False, "logo_initial": "", "status": "open", "opp_status": "draft", "created_at": "2026-10-30T09:00:00Z", "updated_at": "",
           "kind": kind, "provider": "مؤسسة التعليم الدولي", "language": "en", "funding": "full", "eligibility_ar": ["خريج حقوق", "إجادة الإنجليزية"],
           "covers_ar": "الرسوم والإقامة", "deadline": "2026-12-08", "deadline_text": "", "days_left": 37, "source_name": "grants.example.test",
           "verified_at": "2026-10-30", "image": "", "featured": False, "review_status": review, "reject_reason": "", "submitted_by": "sender@example.test", "note": "",
           "decided_at": "", "seed_id": ""}
    row.update(kw)
    return row


def _work(i, title, kind="story", status="pending_review", **kw):
    row = {"id": "CR_%s" % i, "slug": "w-%s" % i, "title": title, "kind": kind, "creator_email": "writer%s@example.test" % "abc"[i % 3], "creator_name": "كاتب من الديوان",
           "pen_name": "", "publish_as": "name", "body": "نص العمل: " + title + " وفيه سطور كثيرة تُقرأ قبل القرار.", "about": "كلمة قصيرة عن العمل", "book_store_slug": "", "ai_assisted": False,
           "duration_minutes": None, "status": status, "reject_reason": "", "review_note": "", "reviewed_by": "", "reviewed_at": "", "comments_locked": False, "likes": 4,
           "comments_count": 2, "views": 30, "featured": False, "featured_until": "", "member_submitted": True, "challenge_id": "", "is_active": True,
           "created_at": "2026-10-31T10:00:00Z", "updated_at": "", "media_url": "", "cover_url": "", "media": None}
    row.update(kw)
    return row


def _challenge(i, title, status, **kw):
    row = {"id": "CH_%s" % i, "slug": "ch-%s" % i, "title": title, "brief": "اكتب قصة قصيرة عن لحظة عدل لا تُنسى.", "kind_allowed": ["story", "poem"], "word_cap": 800,
           "opens_at": "2026-10-01T00:00:00+00:00", "closes_at": "2026-10-25T00:00:00+00:00", "results_at": "", "status": status,
           "prizes": [{"type": "certificate", "label": "شهادة التميّز", "ref": "", "place": 1}], "jury": [{"name": "د. سلمى", "title": "أستاذة قانون"}, {"name": "أ. هاني", "title": "محامٍ"}, {"name": "أ. دينا", "title": "كاتبة"}],
           "sponsor": None, "cover_url": "", "created_by": "dashboard", "created_at": "2026-09-30T00:00:00Z", "updated_at": "", "winners": [], "awards": [], "entries_count": 3}
    row.update(kw)
    return row


NEWS = [_news(1, "قانون جديد للعمل المرن", category="قوانين جديدة"), _news(2, "مسابقة تعيين معاونين للنيابة", category="مسابقات وتعيينات", featured=True),
        _news(3, "حكم مهم في التعويض عن الضرر المعنوي", category="أحكام"), _news(9, "خبر منشور من أسبوع", status="published", category="أخرى", published_at="2026-10-25T08:00:00Z")]

TOPICS = [{"id": "tp-1", "title": "هل تكفي الشهادة وحدها للعمل في التحكيم؟", "status": "open", "source": "human", "opinions_count": 3, "expert_opinions_count": 1, "created_at": "2026-10-20T00:00:00Z", "news_id": None, "source_article_slug": None},
          {"id": "tp-2", "title": "مستقبل المحاماة مع الأتمتة", "status": "open", "source": "human", "opinions_count": 2, "expert_opinions_count": 0, "created_at": "2026-10-22T00:00:00Z", "news_id": None, "source_article_slug": None}]

OPINIONS = [
    {"id": "op-1", "topic_id": "tp-1", "topic_title": TOPICS[0]["title"], "author_email": "member.one@example.test", "body": "الشهادة بداية، لكن الخبرة العملية هي الفاصل في هذا المجال.", "status": "pending", "is_expert": False, "author_kind": "member", "kind": "opinion", "created_at": "2026-10-31T09:00:00Z", "edited": False, "side": "a"},
    {"id": "op-2", "topic_id": "tp-2", "topic_title": TOPICS[1]["title"], "author_email": "member.two@example.test", "body": "الأتمتة تغيّر شكل العمل لا جوهره، ولا غنى عن القرار البشري.", "status": "pending", "is_expert": True, "author_kind": "expert", "kind": "opinion", "created_at": "2026-10-31T11:00:00Z", "edited": False, "side": "b"},
    {"id": "op-3", "topic_id": "tp-1", "topic_title": TOPICS[0]["title"], "author_email": "member.three@example.test", "body": "رأي ظاهر للقرّاء عن تجربة التحكيم الأولى.", "status": "approved", "is_expert": False, "author_kind": "member", "kind": "opinion", "created_at": "2026-10-29T09:00:00Z", "edited": False, "side": "a"},
    {"id": "op-4", "topic_id": "tp-2", "topic_title": TOPICS[1]["title"], "author_email": "member.four@example.test", "body": "رأي آخر ظاهر عن الأتمتة في المكاتب.", "status": "approved", "is_expert": False, "author_kind": "member", "kind": "opinion", "created_at": "2026-10-28T09:00:00Z", "edited": False, "side": "a"},
    {"id": "op-5", "topic_id": "tp-1", "topic_title": TOPICS[0]["title"], "author_email": "member.five@example.test", "body": "رأي مخفي سابقًا.", "status": "rejected", "is_expert": False, "author_kind": "member", "kind": "opinion", "created_at": "2026-10-27T09:00:00Z", "edited": False, "side": "a"},
]

JOBS = [
    _job(1, "منحة ماجستير القانون الدولي", kind="grant"), _job(2, "زمالة بحثية في حقوق الإنسان", kind="fellowship", country="CH"),
    _job(3, "محامٍ للشركات في مكتب كبير", kind="job", employer="مكتب الحكمة", provider="", place="القاهرة", country="EG", funding="", language="ar", employment_type="دوام كامل"),
    _job(4, "دورة تدريبية في التحكيم", kind="training", country="online"), _job(5, "مسابقة المرافعات الدولية", kind="competition", country="FR", deadline_text="في مارس"),
    _job(6, "ورشة غير مصنَّفة", kind="other", official_url="", source_url="", country="DE"),
    _job(7, "منحة الدكتوراه المميّزة", kind="grant", review="published", featured=True, image="https://img.example.test/cover.jpg", opp_status="published"),
    _job(8, "مساعد قانوني في شركة ناشئة", kind="job", review="published", employer="شركة ناشئة", provider="", place="الرياض", country="SA", opp_status="published"),
    _job(9, "ورشة صياغة العقود", kind="training", review="published", opp_status="published"),
    _job(10, "فرصة ما زالت مسودة", kind="grant", review="draft"), _job(11, "إعلان مرفوض قديم", kind="job", review="rejected", reject_reason="مكرر"),
]

WORKS = [
    _work(1, "ليلة في المحكمة", kind="story"), _work(2, "فيلم قصير عن العدالة", kind="film", media_url="https://video.example.test/watch", ai_assisted=True),
    _work(3, "قصيدة الميزان", kind="poem", creator_name="شاعر"),
    _work(4, "حكاية القاضي", kind="story", status="published", challenge_id="CH_2", featured=False), _work(5, "رسالة إلى العدالة", kind="story", status="published", challenge_id="CH_2"),
    _work(6, "دفتر محامٍ شاب", kind="book", status="published", challenge_id="CH_2", featured=True, featured_until="2026-11-20", comments_locked=True),
    _work(7, "عمل مخفي", kind="story", status="hidden"), _work(8, "عمل مرفوض", kind="story", status="rejected", reject_reason="لا يناسب التحدّي"),
]

COMMENTS = [
    {"id": "cm-1", "work_id": "CR_4", "work_title": "حكاية القاضي", "user_email": "reader.one@example.test", "display_name": "قارئ متابع", "body": "نص جميل ومؤثر، شكرًا لك.", "status": "visible", "created_at": "2026-10-31T12:00:00Z", "hidden_at": ""},
    {"id": "cm-2", "work_id": "CR_5", "work_title": "رسالة إلى العدالة", "user_email": "reader.two@example.test", "display_name": "قارئة", "body": "تعليق مسيء يستحق الإخفاء.", "status": "visible", "created_at": "2026-10-31T13:00:00Z", "hidden_at": ""},
    {"id": "cm-3", "work_id": "CR_6", "work_title": "دفتر محامٍ شاب", "user_email": "reader.three@example.test", "display_name": "", "body": "أحببت هذا العمل كثيرًا.", "status": "visible", "created_at": "2026-10-30T13:00:00Z", "hidden_at": ""},
    {"id": "cm-4", "work_id": "CR_4", "work_title": "حكاية القاضي", "user_email": "reader.four@example.test", "display_name": "قارئ", "body": "تعليق مخفي سابقًا.", "status": "hidden", "created_at": "2026-10-29T13:00:00Z", "hidden_at": "2026-10-30T00:00:00Z"},
]

CHALLENGES = [
    _challenge(1, "تحدّي القصة القصيرة", "draft", jury=[{"name": "د. سلمى", "title": "أستاذة قانون"}], entries_count=0),
    _challenge(2, "تحدّي لحظة العدل", "closed"), _challenge(3, "تحدّي الشعر القانوني", "open", closes_at="2026-12-25T00:00:00+00:00", opens_at="2026-11-01T00:00:00+00:00"),
    _challenge(4, "تحدّي العام الماضي", "results", winners=[{"place": 1, "work_id": "CR_4", "jury_line": "أجمل نص"}]),
]

REPORT = {"window_days": 30, "visitors": None, "legal_open_share": None, "signups": None, "share_card_clicks": 0, "return_7d": None,
          "entries_per_challenge": [{"challenge_id": "CH_2", "slug": "ch-2", "title": "تحدّي لحظة العدل", "entries": 3}],
          "works_acceptance": {"submitted": 4, "accepted": 3, "ratio": 0.75}, "generated_at": "2026-11-01T08:00:00Z"}
REPORT_FULL = dict(REPORT, visitors=1240, legal_open_share=0.35, signups=18, share_card_clicks=57, return_7d=0.31)


ENG_SOURCES = [
    {"id": "eu-grants", "name": "منح الاتحاد الأوروبي", "kind": "html", "url": "https://grants.example.test/eu", "item": {"item_xpath": "//li", "title_xpath": ".//a"},
     "kind_default": "grant", "country": "various", "trusted": False, "enabled": True, "max_items": 15, "notes": "",
     "last_run": {"at": "2026-11-01T05:00:00Z", "ok": True, "fetched": 9, "new": 3, "published": 0, "drafts": 3, "error": ""}},
    {"id": "un-jobs", "name": "وظائف الأمم المتحدة", "kind": "rss", "url": "https://jobs.example.test/un", "item": {}, "kind_default": "job", "country": "various",
     "trusted": True, "enabled": True, "max_items": 15, "notes": "", "last_run": {"at": "2026-11-01T05:00:00Z", "ok": False, "fetched": 0, "error": "timeout"}},
    {"id": "law-fellows", "name": "زمالات كليات القانون", "kind": "rss", "url": "https://fellows.example.test/feed", "item": {}, "kind_default": "fellowship",
     "country": "GB", "trusted": False, "enabled": False, "max_items": 15, "notes": "", "last_run": None},
]
ENG_REVIEW = [
    {"id": "job-30", "title": "منحة دراسات القانون الدولي في لايدن", "kind": "grant", "provider": "جامعة لايدن", "deadline": "2026-12-15", "source_id": "eu-grants",
     "tracks": ["intl"], "possible_duplicate_of": "", "legal_reason": "", "created_at": "2026-11-01T05:01:00Z"},
    {"id": "job-31", "title": "زمالة حقوق الإنسان", "kind": "fellowship", "provider": "مركز جنيف", "deadline": "", "source_id": "eu-grants",
     "tracks": [], "possible_duplicate_of": "job-1", "legal_reason": "weak-legal-signal", "created_at": "2026-11-01T05:02:00Z"},
]


class SahaTilesPlatform(v2fx.V2Platform):
    def __init__(self, empty=False, **kw):
        super(SahaTilesPlatform, self).__init__(empty=empty, **kw)
        self.sd_empty = empty
        self.sd_news = [] if empty else copy.deepcopy(NEWS)
        self.sd_topics = [] if empty else copy.deepcopy(TOPICS)
        self.sd_opinions = [] if empty else copy.deepcopy(OPINIONS)
        self.sd_jobs = [] if empty else copy.deepcopy(JOBS)
        self.sd_works = [] if empty else copy.deepcopy(WORKS)
        self.sd_comments = [] if empty else copy.deepcopy(COMMENTS)
        self.sd_challenges = [] if empty else copy.deepcopy(CHALLENGES)
        self.sd_settings = {"prep_course_url": "https://courses.example.test/prep", "updated_at": "2026-10-20T00:00:00Z"}
        self.sd_report = copy.deepcopy(REPORT)
        self.reminders_enabled = False
        self.sd_writes = []
        self.sd_calls = []
        self.missing = set()
        self.down = set()
        self.made = 0
        # R18 «محرّك الفرص»
        self.eng_autorun = {"enabled": False, "source": "default", "hours": "7", "running": False,
                            "last_result": None if empty else {"ok": True, "ran_at": "2026-11-01T05:00:00Z", "fetched": 24, "new": 7, "published": 2, "drafts": 5, "filled": 1,
                                                               "expired": 0, "skipped": {"not-legal": 9, "source-error": 1}}}
        self.eng_sources = [] if empty else copy.deepcopy(ENG_SOURCES)
        self.eng_review = [] if empty else copy.deepcopy(ENG_REVIEW)
        self.eng_digest = {"enabled": False, "day": "sun", "hour": 10, "last_sent_at": None, "last_count": 0}
        self.eng_test_reason = "sample-track"     # بريد بلا مسار ⇒ فرص مسار آخر (رمز المنصة الحقيقي)

    # ---------------------------------------------------------------- التوجيه
    def _route(self, method, path, params, body):
        m = method.upper()
        if path.startswith(("/api/bridge/news", "/api/bridge/jobs", "/api/bridge/opinions", "/api/bridge/opportunities", "/api/bridge/creative",
                            "/api/bridge/diwan", "/api/bridge/topics", "/api/bridge/legal-gate")):
            forced = self.forced.get((m, path))
            if forced is not None:
                return forced
            if path in self.down:
                return 503, {"detail": "تعذر الاتصال"}
            if path in self.missing:
                return 404, NOT_FOUND
            out = self._sd(m, path, params or {}, body or {})
            if out is not None:
                return out
        return super(SahaTilesPlatform, self)._route(method, path, params, body)

    @staticmethod
    def _by(body):
        return None if str(body.get("by") or "").strip() else (422, {"detail": "لازم نعرف مين اللي بيقرّر"})

    def _rec(self, m, path, params, body):
        self.sd_writes.append((m, path, dict(params), copy.deepcopy(body)))

    @staticmethod
    def _find(rows, rid):
        return next((r for r in rows if r["id"] == rid), None)

    def _sd(self, m, path, params, body):
        eng = self._sd_engine(m, path, params, body)
        if eng is not None:
            return eng
        if path == "/api/bridge/news" and m == "GET":
            rows = [n for n in self.sd_news if not params.get("status") or n["status"] == params["status"]]
            return 200, {"news": copy.deepcopy(rows), "count": len(rows)}
        if path == "/api/bridge/news/run" and m == "POST":
            self._rec(m, path, params, body)
            return 200, {"ok": True, "ran_at": "2026-11-01T09:00:00Z", "total_created": 2, "per_country": [{"country": "EG", "fetched": 9, "created": 2, "errors": 0}]}
        mm = re.match(r"^/api/bridge/news/([^/]+)$", path)
        if mm and m == "PUT":
            n = self._find(self.sd_news, mm.group(1))
            if n is None:
                return 404, {"detail": "News item not found"}
            self._rec(m, path, params, body)
            for k, v in body.items():
                if k == "status":
                    n["status"] = v
                    n["is_published"] = v == "published"
                elif k != "by":
                    n[k] = v
            return 200, copy.deepcopy(n)
        if path == "/api/bridge/topics" and m == "GET":
            return 200, [t for t in copy.deepcopy(self.sd_topics) if not params.get("status") or t["status"] == params["status"]]
        mm = re.match(r"^/api/bridge/topics/([^/]+)/(hide|restore)$", path)
        if mm and m == "POST":       # R17: ختم بشري على النقاش (إخفاء/إرجاع) بلا تغيير حالة
            t = self._find(self.sd_topics, mm.group(1))
            if t is None:
                return 404, {"detail": "Topic not found"}
            self._rec(m, path, params, body)
            t["legal_gate"] = {"ok": mm.group(2) == "restore", "by": "human", "reason": "human:" + mm.group(2)}
            return 200, copy.deepcopy(t)
        if path == "/api/bridge/legal-gate/backfill" and m == "POST":   # R17: فحص الصلة (تجربة) أو إخفاء المختار
            self._rec(m, path, params, body)
            applied = body.get("apply") is True
            picked = set(body.get("ids") or [])
            off = [t for t in self.sd_topics if t["id"] in ("tp-2",)]
            news_off = [{"id": "nw-off", "title": "نتيجة مباراة الأمس في الدوري", "reason": "off-theme", "status": "published"}]
            rows = [{"id": t["id"], "title": t["title"], "reason": "off-theme", "status": t["status"]} for t in off]
            if applied:
                for t in off:
                    if t["id"] in picked:
                        t["legal_gate"] = {"ok": False, "by": "rule", "reason": "off-theme"}
            un_t = len([r for r in rows if applied and r["id"] not in picked])
            un_n = len([r for r in news_off if applied and r["id"] not in picked])
            return 200, {"ok": True, "dry_run": not applied, "applied": applied, "archive": False, "version": "lg1", "collections": {
                "news": {"scanned": 4, "would_hide": 1, "would_pass": 3, "skipped_unselected": un_n, "hidden": news_off},
                "topics": {"scanned": len(self.sd_topics), "would_hide": len(rows), "would_pass": len(self.sd_topics) - len(rows),
                           "skipped_unselected": un_t, "hidden": rows},
                "articles": {"scanned": 0, "would_hide": 0, "would_pass": 0, "hidden": []}}}
        if path == "/api/bridge/opinions" and m == "GET":
            rows = [o for o in self.sd_opinions if (params.get("status") in (None, "all") or o["status"] == params["status"]) and (not params.get("topic_id") or o["topic_id"] == params["topic_id"])]
            return 200, copy.deepcopy(rows)
        mm = re.match(r"^/api/bridge/opinions/([^/]+)/(reject|approve)$", path)
        if mm and m == "POST":
            o = self._find(self.sd_opinions, mm.group(1))
            if o is None:
                return 404, {"detail": "Opinion not found"}
            self._rec(m, path, params, body)
            o["status"] = "rejected" if mm.group(2) == "reject" else "approved"
            return 200, copy.deepcopy(o)
        return self._sd_jobs(m, path, params, body) or self._sd_diwan(m, path, params, body)

    def _sd_jobs(self, m, path, params, body):
        if path == "/api/bridge/jobs" and m == "GET":
            rows = [j for j in self.sd_jobs if (not params.get("review_status") or j["review_status"] == params["review_status"])
                    and (not params.get("kind") or params["kind"] == "all" or j["kind"] == params["kind"] or (params["kind"] == "grants" and j["kind"] in ("grant", "fellowship")))]
            return 200, {"jobs": copy.deepcopy(rows), "count": len(rows)}
        if path == "/api/bridge/jobs" and m == "POST":
            bad = self._by(body)
            if bad:
                return bad
            if not (body.get("official_url") or body.get("source_url")):
                return 422, {"detail": "الرابط الرسمي مطلوب"}
            self.made += 1
            row = _job(100 + self.made, body["title"], kind=body.get("kind", "job"), review="published" if body.get("publish") else "draft")
            for k in ("provider", "employer", "place", "country", "language", "funding", "deadline", "covers_ar", "official_url", "source_url", "image", "featured", "eligibility_ar", "title_en"):
                if k in body:
                    row[k] = body[k]
            self.sd_jobs.append(row)
            self._rec(m, path, params, body)
            return 200, copy.deepcopy(row)
        mm = re.match(r"^/api/bridge/jobs/([^/]+)(/decide)?$", path)
        if mm:
            j = self._find(self.sd_jobs, mm.group(1))
            if j is None:
                return 404, {"detail": "Job not found"}
            if m == "GET":
                return 200, copy.deepcopy(j)
            bad = self._by(body)
            if bad:
                return bad
            if mm.group(2) and m == "POST":
                if body.get("decision") == "approve" and not j["official_url"]:
                    return 422, {"detail": "أكمل عنوان الإعلان قبل النشر"}
                if j["review_status"] != "pending":
                    return 409, {"detail": "اتقرّر في هذا الإعلان قبل كده"}
                self._rec(m, path, params, body)
                j["review_status"] = "published" if body["decision"] == "approve" else "rejected"
                j["reject_reason"] = body.get("reason", "")
                return 200, copy.deepcopy(j)
            if m == "PUT":
                self._rec(m, path, params, body)
                for k, v in body.items():
                    if k == "publish":
                        j["review_status"] = "published" if v else "draft"
                    elif k != "by":
                        j[k] = v
                return 200, copy.deepcopy(j)
            if m == "DELETE":
                if j["kind"] == "job":
                    return 409, {"detail": "الوظائف تُقفل ولا تُحذف"}
                self._rec(m, path, params, body)
                self.sd_jobs = [x for x in self.sd_jobs if x["id"] != j["id"]]
                return 200, {"ok": True, "deleted": j["id"]}
        if path == "/api/bridge/opportunities/settings":
            if m == "GET":
                return 200, copy.deepcopy(self.sd_settings)
            if m == "PUT":
                bad = self._by(body)
                if bad:
                    return bad
                self._rec(m, path, params, body)
                self.sd_settings = {"prep_course_url": body["prep_course_url"], "updated_at": "2026-11-01T09:00:00Z"}
                return 200, copy.deepcopy(self.sd_settings)
        if path == "/api/bridge/opportunities/import-seed" and m == "POST":
            dry = params.get("dry_run") == "true"
            n = len(body["items"]) if isinstance(body.get("items"), list) else 34
            self.sd_calls.append((m, path, dict(params), copy.deepcopy(body)))
            if not dry:
                self._rec(m, path, params, body)
            return 200, {"created": n, "filled": 1, "skipped_unverified": 4, "unchanged": 2, "warnings": ["الصف ٧: لا تاريخ تحقق", "الصف ١٢: رابط غير آمن"], "dry_run": dry}
        if path == "/api/bridge/opportunities/run-reminders" and m == "POST":
            bad = self._by(body)
            if bad:
                return bad
            self._rec(m, path, params, body)
            if not self.reminders_enabled:
                return 200, {"enabled": False, "opportunities": 0, "sent": 0, "skipped_already": 0, "skipped_toggle_off": 0, "errors": 0}
            return 200, {"enabled": True, "opportunities": 3, "sent": 5, "skipped_already": 1, "skipped_toggle_off": 2, "errors": 0}
        return None

    def _sd_engine(self, m, path, params, body):
        """R18 — جسور «محرّك الفرص» بالعقد: الكتابات بلا `by` (الجسم بالعقد بالظبط)."""
        B = "/api/bridge/opportunities"
        mj = re.match(r"^/api/bridge/jobs/(job-3\d)(/decide)?$", path)        # مسودات المحرّك: نفس جسر القرار (المسودة تُنشر مباشرة)
        if mj:
            r = self._find(self.eng_review, mj.group(1))
            if r is None:
                return 404, {"detail": "Job not found"}
            row = _job(mj.group(1).split("-")[1], r["title"], kind=r["kind"], review="draft", provider=r["provider"], deadline=r["deadline"] or None)
            if m == "GET" and not mj.group(2):
                return 200, row
            if m == "POST" and mj.group(2):
                bad = self._by(body)
                if bad:
                    return bad
                self._rec(m, path, params, body)
                self.eng_review = [x for x in self.eng_review if x["id"] != r["id"]]
                row["review_status"] = "published" if body["decision"] == "approve" else "rejected"
                return 200, row
            return None
        if path == B + "/autorun":
            if m == "PUT":
                self._rec(m, path, params, body)
                self.eng_autorun.update({"enabled": body["enabled"], "source": "settings"})
                if "hours" in body:
                    self.eng_autorun["hours"] = body["hours"]
            return 200, copy.deepcopy(self.eng_autorun)
        if path == B + "/sources" and m == "GET":
            return 200, {"sources": copy.deepcopy(self.eng_sources), "count": len(self.eng_sources)}
        mm = re.match(r"^/api/bridge/opportunities/sources/([a-z0-9_-]+)$", path)
        if mm and m == "PUT" and mm.group(1) != "import-seed":
            src = self._find(self.eng_sources, mm.group(1))
            if src is None:
                return 404, {"detail": "Source not found"}
            self._rec(m, path, params, body)
            src.update({k: body[k] for k in ("trusted", "enabled") if k in body})
            return 200, copy.deepcopy(src)
        if path == B + "/sources/import-seed" and m == "POST":
            self._rec(m, path, params, body)
            added = [s for s in ENG_SOURCES if not self._find(self.eng_sources, s["id"])]
            self.eng_sources.extend(copy.deepcopy(added))
            return 200, {"created": len(added), "kept": len(ENG_SOURCES) - len(added), "errors": []}
        if path == B + "/run" and m == "POST":
            self._rec(m, path, params, body)
            res = {"ok": True, "ran_at": "2026-11-01T09:00:00Z", "fetched": 11, "new": 4, "published": 1, "drafts": 3, "filled": 0, "expired": 0,
                   "skipped": {"not-legal": 5}}
            self.eng_autorun["last_result"] = res
            return 200, res
        if path == B + "/summary" and m == "GET":
            return 200, {"drafts_waiting": len(self.eng_review), "possible_duplicates": len([r for r in self.eng_review if r["possible_duplicate_of"]]),
                         "published_24h": 0 if self.sd_empty else 2, "held_news_24h": 0 if self.sd_empty else 1,
                         "autorun": {"enabled": self.eng_autorun["enabled"], "source": self.eng_autorun["source"]},
                         "last_run": None, "digest": copy.deepcopy(self.eng_digest)}
        if path == B + "/review" and m == "GET":
            return 200, {"items": copy.deepcopy(self.eng_review)}
        if path == B + "/digest":
            if m == "PUT":
                self._rec(m, path, params, body)
                self.eng_digest["enabled"] = body["enabled"]
            return 200, copy.deepcopy(self.eng_digest)
        if path == B + "/digest/preview" and m == "GET":
            # شكل `opp_digest.preview` الحقيقي: رمز المسار + اسمه العربي + السبب + هل هتتبعت
            if str(params.get("email") or "").startswith("unsub"):
                return 200, {"subject": "فرص الأسبوع في مسارك", "count": 2, "track": "intl-law", "track_title": "القانون الدولي",
                             "reason": "unsubscribed", "will_send": False, "html": "<p>منحة دراسات القانون الدولي في لايدن</p>"}
            if str(params.get("email") or "").startswith("nobody"):
                return 200, {"subject": "فرص الأسبوع في مسارك", "html": "", "count": 0, "track": "", "reason": "no-user", "will_send": False}
            return 200, {"subject": "فرص الأسبوع في مسارك", "count": 2, "track": "intl-law", "track_title": "القانون الدولي", "reason": "", "will_send": True,
                         "html": "<div dir=\"rtl\" style=\"font-family:sans-serif;padding:16px\"><h2>فرص الأسبوع في مسارك</h2><p>منحة دراسات القانون الدولي في لايدن</p>"
                                 "<p>زمالة حقوق الإنسان</p><script>document.title='x'</script></div>"}
        if path == B + "/digest/send-test" and m == "POST":
            self._rec(m, path, params, body)
            ok = self.eng_test_reason in ("", "sample-track")
            return 200, {"sent": ok, "reason": self.eng_test_reason}
        return None

    def _sd_diwan(self, m, path, params, body):
        if path == "/api/bridge/creative" and m == "GET":
            rows = [w for w in self.sd_works if w["status"] == params.get("status") and (not params.get("challenge_id") or w["challenge_id"] == params["challenge_id"])]
            return 200, {"items": copy.deepcopy(rows), "count": len(rows)}
        mm = re.match(r"^/api/bridge/creative/([^/]+)(/decide)?$", path)
        if mm and m in ("POST", "PUT"):
            w = self._find(self.sd_works, mm.group(1))
            if w is None:
                return 404, {"detail": "العمل غير موجود"}
            bad = self._by(body)
            if bad:
                return bad
            if mm.group(2):
                if w["status"] != "pending_review":
                    return 409, {"detail": "اتقرّر في هذا العمل قبل كده"}
                self._rec(m, path, params, body)
                w["status"] = "published" if body["decision"] == "approve" else "rejected"
                w["reject_reason"] = body.get("reason", "")
                return 200, copy.deepcopy(w)
            if body.get("status") == "hidden" and w["status"] != "published":
                return 409, {"detail": "الإخفاء للأعمال المنشورة فقط"}
            self._rec(m, path, params, body)
            for k, v in body.items():
                if k != "by":
                    w[k] = v
            return 200, copy.deepcopy(w)
        if path == "/api/bridge/diwan/comments" and m == "GET":
            rows = [c for c in self.sd_comments if c["status"] == params.get("status")]
            return 200, {"items": copy.deepcopy(rows), "count": len(rows)}
        mm = re.match(r"^/api/bridge/diwan/comments/([^/]+)/hide$", path)
        if mm and m == "POST":
            c = self._find(self.sd_comments, mm.group(1))
            if c is None:
                return 404, {"detail": "التعليق غير موجود"}
            self._rec(m, path, params, body)
            c["status"] = "hidden"
            return 200, {"ok": True, "comment": copy.deepcopy(c)}
        if path == "/api/bridge/diwan/challenges" and m == "GET":
            rows = [c for c in self.sd_challenges if not params.get("status") or c["status"] == params["status"]]
            return 200, {"items": copy.deepcopy(rows), "count": len(rows)}
        if path == "/api/bridge/diwan/challenges" and m == "POST":
            bad = self._by(body)
            if bad:
                return bad
            self.made += 1
            row = _challenge(100 + self.made, body["title"], body.get("status", "draft"), entries_count=0)
            for k in ("brief", "kind_allowed", "word_cap", "opens_at", "closes_at", "results_at", "prizes", "jury", "sponsor", "cover_url"):
                if k in body:
                    row[k] = body[k]
            self.sd_challenges.append(row)
            self._rec(m, path, params, body)
            return 200, copy.deepcopy(row)
        mm = re.match(r"^/api/bridge/diwan/challenges/([^/]+)(/winners)?$", path)
        if mm and m in ("PUT", "POST"):
            c = self._find(self.sd_challenges, mm.group(1))
            if c is None:
                return 404, {"detail": "التحدّي غير موجود"}
            bad = self._by(body)
            if bad:
                return bad
            if mm.group(2):
                if c["status"] == "results":
                    return 200, {"ok": True, "already": True, "challenge": copy.deepcopy(c), "certificates": [], "emails_sent": 0}
                if c["status"] != "closed":
                    return 409, {"detail": "يجب أن يكون التحدّي مغلقًا قبل اختيار الفائزين"}
                self._rec(m, path, params, body)
                c["status"] = "results"
                c["winners"] = copy.deepcopy(body["winners"])
                return 200, {"ok": True, "already": False, "challenge": copy.deepcopy(c),
                             "certificates": [{"place": w["place"], "work_id": w["work_id"], "code": "CERT%d" % w["place"]} for w in body["winners"]], "emails_sent": len(body["winners"])}
            if c["status"] == "results":
                return 409, {"detail": "أُعلنت النتائج، لا تعديل غير الغلاف والوصف"}
            self._rec(m, path, params, body)
            for k, v in body.items():
                if k != "by":
                    c[k] = v
            return 200, copy.deepcopy(c)
        if path == "/api/bridge/diwan/report" and m == "GET":
            return 200, copy.deepcopy(self.sd_report)
        return None
