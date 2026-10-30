# -*- coding: utf-8 -*-
"""منصّة وهميّة لقسم «المحتوى» (الجولة الأخيرة): فوق `V2Platform` بتضيف جسور الموضوعات والتعليقات والأخبار ومقالات المنصة وركن الإبداع وآراء
المتعلّمين والدليل — كلها في الذاكرة (صفر شبكة). الأشكال بالحرف من جسور المنصة (`routes/topics.py` · `routes/creative.py` · `routes/engagement.py`)،
والأسماء والأرقام مخترعة. كل كتابة تتسجّل في `self.writes` وتغيّر الحالة فعلًا (الاعتماد يشيل الصف من الطابور… إلخ).

`forced[(method, path)] = (status, payload)` يفرض ردًّا (لاختبار المصدر الفاشل أو رفض المنصة).
`opinions_summarize` = قائمة قيم `summarize` اللي وصلت المنصة (الشاشة لازم تبعت `false` إلا بعد تأكيد «اكتب خلاصة»).
`seed_site(appmod)` يزرع مقالات الموقع في SQLite الداشبورد (الدفتر المحلي) — مسودات ومنشور اليوم وهذا الأسبوع وقديم.
"""
import copy
import datetime
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ef_fixtures as fx          # noqa: E402
import v2_fixtures as v2fx        # noqa: E402

iso = fx.iso

SEGMENTS = [
    {"id": "new_grads", "label": "خريجون جدد وبداية المهنة", "count": 2}, {"id": "admin_prosecution", "label": "النيابة الإدارية والتحقيق", "count": 0},
    {"id": "criminal", "label": "جنائي", "count": 3}, {"id": "family", "label": "أحوال شخصية", "count": 4}, {"id": "labor", "label": "عمل وتأمينات", "count": 5},
    {"id": "commercial", "label": "تجاري وشركات", "count": 2}, {"id": "realestate", "label": "عقاري", "count": 1}, {"id": "corporate_hr", "label": "شركات وموارد بشرية", "count": 0},
    {"id": "students", "label": "طلاب حقوق", "count": 1}, {"id": "general", "label": "عام", "count": 6},
]


def topic(tid, title, status, source="human", cat="قانون عمل", at_h=-5.0, **kw):
    row = {"id": tid, "title": title, "question": kw.pop("question", "ما حقوق صاحب العمل والعامل في هذه الحالة؟"), "summary": "", "specialty": cat, "category": cat,
           "target_audience": "", "segment": kw.pop("segment", ""), "segment_label": kw.pop("segment_label", ""), "segment_auto": kw.pop("segment_auto", True),
           "country": kw.pop("country", "مصر"), "source": source, "ai_answer": kw.pop("ai_answer", ""), "merged_article": kw.pop("merged_article", ""),
           "linked_article_id": kw.pop("linked_article_id", None), "article_made_at": None, "has_article": False, "author_email": kw.pop("author_email", ""),
           "engagement": {"comments": kw.pop("comments", 0), "reactions": 0}, "status": status, "created_at": iso(at_h), "updated_at": iso(at_h)}
    row.update(kw)
    return row


TOPICS = [
    topic("tp-p1", "هل يجوز إنهاء عقد الإيجار قبل مدته؟", "pending_review", cat="عقاري", at_h=-70.0, author_email="member1@example.test", segment="realestate", segment_label="عقاري", segment_auto=True,
          question="استأجرت شقة بعقد ثلاث سنوات وأريد إنهاءه بعد سنة، فهل يلزمني دفع باقي المدة؟"),
    topic("tp-p2", "كيف أسجّل علامة تجارية لمشروع ناشئ؟", "pending_review", cat="تجاري", at_h=-8.0, author_email="member2@example.test"),
    topic("tp-p3", "مدة التقادم في دعاوى النفقة", "pending_review", cat="أحوال شخصية", at_h=-3.0, author_email="member3@example.test", segment="family", segment_label="أحوال شخصية", segment_auto=False),
    topic("tp-w1", "حقوق العامل عند الفصل التعسفي", "merged", source="human", cat="قانون عمل", at_h=-30.0, ai_answer="إجابة مقترحة مفصلة عن حقوق العامل…", merged_article="نص مدموج جاهز للمراجعة"),
    topic("tp-w2", "شروط صحة العقد الإلكتروني", "merged", source="idea", cat="تجاري", at_h=-12.0),
    topic("tp-i1", "الفرق بين الشركة ذات المسؤولية المحدودة والتضامن", "draft", source="idea", cat="تجاري", at_h=-20.0, ai_answer="مسوّدة مقترحة…", segment="commercial", segment_label="تجاري وشركات"),
    topic("tp-i2", "حق الشفعة في العقارات", "draft", source="news", cat="عقاري", at_h=-40.0),
    topic("tp-i3", "مراجعة بند عدم المنافسة في عقود العمل", "draft", source="expert", cat="قانون عمل", at_h=-50.0, ai_answer="رأي الخبير مختصرًا"),
    topic("tp-b1", "ضوابط الفصل التأديبي للعاملين", "open", source="human", cat="قانون عمل", at_h=-100.0, comments=6, segment="labor", segment_label="عمل وتأمينات", linked_article_id="9001"),
    topic("tp-b2", "الطلاق للضرر: متى تقبله المحكمة؟", "published", source="news", cat="أحوال شخصية", at_h=-200.0, comments=11, segment="family", segment_label="أحوال شخصية"),
    topic("tp-r1", "موضوع خارج النطاق القانوني", "rejected", source="human", cat="عام", at_h=-90.0),
    topic("tp-a1", "موضوع مؤرشف قديم", "archived", source="human", cat="عام", at_h=-500.0),
]


def opinion(oid, body, topic_id, topic_title, author, status="pending", mod=None, at_h=-4.0, **kw):
    row = {"id": oid, "topic_id": topic_id, "topic_title": topic_title, "author_email": author, "body": body, "status": status, "is_expert": False,
           "author_kind": "member", "kind": "opinion", "ai_moderation": mod, "created_at": iso(at_h), "edited": False, "editor_reply": kw.pop("editor_reply", ""),
           "editor_reply_by": kw.pop("editor_reply_by", ""), "editor_reply_at": ""}
    row.update(kw)
    return row


def _mod(abusive=None, on_topic=None, checked=True, by="ai", at_h=-4.0, reason=""):
    return {"ai_checked": checked, "on_topic": on_topic, "abusive": abusive, "reason": reason, "decided_by": by, "decided_at": iso(at_h), "note": ""}


OPINIONS = [
    opinion("op-1", "هذا كلام فارغ وكل من يكتبه لا يفهم شيئًا في القانون.", "tp-b1", "ضوابط الفصل التأديبي للعاملين", "angry@example.test", mod=_mod(abusive=True, on_topic=True, reason="عبارات مهينة"), at_h=-3.0),
    opinion("op-2", "هل يمكنكم مساعدتي في بيع سيارتي؟ السعر مناسب جدًا.", "tp-b2", "الطلاق للضرر: متى تقبله المحكمة؟", "spam@example.test", mod=_mod(abusive=False, on_topic=False, reason="إعلان لا علاقة له بالموضوع"), at_h=-9.0),
    opinion("op-3", "أرى أن المحكمة تنظر إلى مدة الخدمة أيضًا عند تقدير التعويض، وهذا ما لم يذكره الموضوع.", "tp-b1", "ضوابط الفصل التأديبي للعاملين", "thoughtful@example.test", mod=_mod(checked=False), at_h=-14.0),
]
APPROVED = [
    opinion("oa-1", "تجربتي مع هذه الحالة أن الإثبات هو أصعب ما في الدعوى.", "tp-b1", "ضوابط الفصل التأديبي للعاملين", "reader1@example.test", status="approved",
            mod=_mod(abusive=False, on_topic=True, by="human", at_h=-30.0), at_h=-60.0, editor_reply="شكرًا لك، سنضيف فقرة عن الإثبات.", editor_reply_by="هيئة التحرير"),
    opinion("oa-2", "موضوع مفيد جدًا وشرح واضح.", "tp-b2", "الطلاق للضرر: متى تقبله المحكمة؟", "reader2@example.test", status="approved", mod=_mod(abusive=False, on_topic=True, by="ai", at_h=-20.0), at_h=-20.0),
    opinion("oa-3", "ما رأيكم في تعديل مدة الحضانة؟", "tp-b2", "الطلاق للضرر: متى تقبله المحكمة؟", "reader3@example.test", status="approved", mod=_mod(abusive=False, on_topic=True, by="human", at_h=-24 * 12.0), at_h=-24 * 12.0),
]

NEWS = [
    {"id": "nw-1", "title": "تعديل جديد على قانون العمل بشأن الإجازات", "summary": "صدر تعديل يمنح العامل إجازة إضافية، وهذا يهم أصحاب الأعمال أيضًا.", "country": "مصر", "specialty": "قانون عمل",
     "source_name": "الجريدة الرسمية", "source_url": "https://example.test/gazette/1", "extra_sources": [{"name": "صحيفة اليوم", "url": "https://example.test/today/9"}], "status": "draft", "created_at": iso(-6.0)},
    {"id": "nw-2", "title": "حكم جديد في نزاعات الإيجار القديم", "summary": "", "country": "مصر", "specialty": "عقاري", "source_name": "", "source_url": "", "extra_sources": [], "status": "draft", "created_at": iso(-30.0)},
    {"id": "nw-3", "title": "قواعد جديدة لتسجيل الشركات الناشئة", "summary": "تسهيلات في التسجيل وتخفيض الرسوم لسنة أولى.", "country": "السعودية", "specialty": "تجاري",
     "source_name": "وزارة التجارة", "source_url": "https://example.test/moc/5", "extra_sources": [], "status": "published", "created_at": iso(-50.0), "published_at": iso(-20.0)},
    {"id": "nw-4", "title": "خبر قديم منشور", "summary": "ملخص", "country": "مصر", "specialty": "جنائي", "source_name": "مصدر", "source_url": "https://example.test/old", "extra_sources": [],
     "status": "published", "created_at": iso(-24 * 20), "published_at": iso(-24 * 19)},
]
NEWS_SOURCES = {"feeds": [{"country": "مصر", "url": "https://example.test/feed.xml"}, {"country": "السعودية", "url": "https://example.test/sa.xml"}],
                "club_keywords": {"نادي العمل": ["فصل", "أجور", "تأمينات"], "نادي العقاري": ["إيجار", "تسجيل"]}}

PLATFORM_ARTICLES = [
    {"id": "pa-1", "title": "كيف تعمل المنصة خطوة بخطوة", "category": "feature", "excerpt": "شرح مختصر لرحلة طلب الرأي القانوني.", "status": "draft", "created_at": iso(-10.0),
     "body": "مقدمة قصيرة.\n\n## الخطوة الأولى\n\nاكتب سؤالك بوضوح.\n\n## الخطوة الثانية\n\nاختر الخبير المناسب."},
    {"id": "pa-2", "title": "كيف تقرأ عقد الإيجار", "category": "news", "excerpt": "تحليل لخبر حديث.", "status": "draft", "created_at": iso(-26.0), "body": "فقرة أولى.\n\nفقرة ثانية."},
    {"id": "pa-3", "title": "مقال منشور على المنصة", "category": "law", "excerpt": "ملخص", "status": "published", "created_at": iso(-100.0), "published_at": iso(-90.0), "body": "نص."},
]
CREATIVE = [
    {"id": "cr-1", "title": "أغنية العدالة", "kind": "song", "creator_email": "artist@example.test", "creator_name": "سلمى الفنانة", "media_url": "https://example.test/song", "body": "", "cover_url": "https://img.example.test/cover-song.jpg", "status": "pending_review", "created_at": iso(-12.0)},
    {"id": "cr-2", "title": "قصيدة الميزان", "kind": "poem", "creator_email": "poet@example.test", "creator_name": "", "media_url": "", "body": "يا ميزانَ الحقّ…\nيا ميزانَ الحقّ يا ميزان\nأنصفْ مَن ضاق به الزمان", "cover_url": "", "status": "pending_review", "created_at": iso(-52.0)},
    {"id": "cr-3", "title": "عمل برابط غير صالح", "kind": "video", "creator_email": "video@example.test", "creator_name": "كريم المصوّر", "media_url": "javascript:alert(1)", "body": "", "cover_url": "https://img.example.test/cover-video.jpg", "status": "pending_review", "created_at": iso(-70.0)},
]
TESTIMONIALS = [
    {"id": "TST_A1", "course_slug": "contract-basics", "course_title": "أساسيات صياغة العقود", "user_email": "learner1@example.test", "name": "منى سعيد", "text": "دورة مرتبة وأفادتني كثيرًا في عملي اليومي.",
     "rating": 5, "consent_public": True, "status": "pending", "created_at": iso(-20.0)},
    {"id": "TST_A2", "course_slug": "lease-review", "course_title": "مراجعة عقود الإيجار", "user_email": "learner2@example.test", "name": "", "text": "شرح جيد لكن أتمنى أمثلة أكثر.",
     "rating": None, "consent_public": False, "status": "pending", "created_at": iso(-6.0)},
]
TESTIMONIALS_APPROVED = [
    {"id": "TST_B1", "course_slug": "contract-basics", "course_title": "أساسيات صياغة العقود", "user_email": "learner3@example.test", "name": "هبة", "text": "ممتازة.", "rating": 4,
     "consent_public": True, "status": "approved", "created_at": iso(-80.0), "decided_at": iso(-40.0)},
]
TUTORIALS = [
    {"id": "tu-1", "title": "كيف تطلب رأيًا قانونيًا", "section": "ابدأ من هنا", "order": 1, "body": "اكتب سؤالك ثم اختر الخبير.", "video_url": "https://www.youtube.com/watch?v=abc", "is_published": True},
    {"id": "tu-2", "title": "كيف تتابع ملفك", "section": "ابدأ من هنا", "order": 2, "body": "من صفحة ملفاتي.", "video_url": "", "is_published": True},
    {"id": "tu-3", "title": "دليل الدفع والفواتير", "section": "الدفع", "order": 1, "body": "قريبًا.", "video_url": "", "is_published": False},
]
ANALYSIS = {
    "total_topics": 12, "total_comments": 17, "total_reactions": 0,
    "top_topics": [{"id": "tp-b2", "title": "الطلاق للضرر: متى تقبله المحكمة؟", "source": "news", "category": "أحوال شخصية", "status": "published", "segment": "family", "engagement": {"comments": 11, "reactions": 0}},
                   {"id": "tp-b1", "title": "ضوابط الفصل التأديبي للعاملين", "source": "human", "category": "قانون عمل", "status": "open", "segment": "labor", "engagement": {"comments": 6, "reactions": 0}}],
    "by_category": [{"category": "قانون عمل", "count": 5}, {"category": "تجاري", "count": 3}, {"category": "أحوال شخصية", "count": 2}, {"category": "عقاري", "count": 2}],
    "by_audience": [], "by_source": [{"source": "human", "count": 6}, {"source": "news", "count": 3}],
    "by_segment": [{"segment": s["id"], "label": s["label"], "count": s["count"]} for s in SEGMENTS],
    "categories_in_demand": [{"category": "قانون عمل", "count": 31}, {"category": "عقاري", "count": 22}], "engagement_note": "comments = approved opinions; reactions = real upvotes on them.",
}
OPINIONS_ANALYSIS = {
    "status_counts": {"pending": 3, "approved": 3, "rejected": 1}, "total_opinions": 7,
    "top_topics": [{"id": "tp-b2", "title": "الطلاق للضرر: متى تقبله المحكمة؟", "count": 2, "category": "أحوال شخصية"}, {"id": "tp-b1", "title": "ضوابط الفصل التأديبي للعاملين", "count": 1, "category": "قانون عمل"}],
    "by_category": [{"category": "أحوال شخصية", "count": 2}, {"category": "قانون عمل", "count": 1}], "insights": "", "insights_note": "",
    "engagement_note": "comment-only: no reaction/vote field on opinions yet (honest 0).",
}
SUMMARY_TEXT = "أكثر ما يشغل المعلّقين هو إثبات الواقعة أمام المحكمة، ثم مدة التقادم."
BLOG_POSTS = [  # أجسام المقالات المزروعة في SQLite الداشبورد
    ("مقال مسودة مكتمل", "draft", 840, True, True, "أ. نادية فؤاد", -2.0, None),
    ("مسودة بلا وصف ولا صورة", "draft", 210, False, False, None, -9.0, None),
    ("دليل الشركات الناشئة", "draft", 500, True, True, None, -30.0, None),        # عنوانها يطابق منشورًا أدناه
    ("دليل الشركات الناشئة", "published", 650, True, True, "أ. نادية فؤاد", -80.0, -1.0),    # منشور اليوم
    ("كيف تقرأ عقد الإيجار", "published", 720, True, True, None, -120.0, -52.0),             # منذ يومين
    ("حقوق العامل في الإجازات", "published", 480, True, False, None, -160.0, -24 * 5.0),     # منذ ٥ أيام
    ("مقال قديم في الأرشيف", "published", 390, False, False, None, -900.0, -24 * 20.0),
]


class ContentPlatform(v2fx.V2Platform):
    def __init__(self, empty=False, **kw):
        super(ContentPlatform, self).__init__(empty=empty, **kw)
        self.cempty = empty
        self.topics = [] if empty else copy.deepcopy(TOPICS)
        self.opinions = [] if empty else copy.deepcopy(OPINIONS)
        self.approved = [] if empty else copy.deepcopy(APPROVED)
        self.news = [] if empty else copy.deepcopy(NEWS)
        self.plat_articles = [] if empty else copy.deepcopy(PLATFORM_ARTICLES)
        self.creative = [] if empty else copy.deepcopy(CREATIVE)
        self.testimonials = [] if empty else copy.deepcopy(TESTIMONIALS)
        self.testimonials_approved = [] if empty else copy.deepcopy(TESTIMONIALS_APPROVED)
        self.tutorials = [] if empty else copy.deepcopy(TUTORIALS)
        self.writes = []
        self.opinions_summarize = []
        self.daily_runs = []
        self.generated = []

    def queue(self):
        q = super(ContentPlatform, self).queue()
        if not self.cempty:
            q["testimonials_pending"] = len([t for t in self.testimonials if t["status"] == "pending"])
            q["topics_drafts"] = len([t for t in self.topics if t["status"] == "draft"])
        return q

    # —— مساعدات
    def _rec(self, method, path, body):
        self.writes.append((method, path, copy.deepcopy(body)))

    def _find(self, rows, rid):
        return next((r for r in rows if r["id"] == rid), None)

    def _extra(self, method, path, params, body):
        out = super(ContentPlatform, self)._extra(method, path, params, body)
        if out is not None and not path.startswith(("/api/bridge/topics", "/api/bridge/market")):
            return out
        method = method.upper()
        if method == "GET":
            return self._get(path, params)
        return self._write(method, path, body)

    def _get(self, path, params):
        if path == "/api/bridge/topics":
            st = params.get("status")
            rows = [t for t in self.topics if (t["status"] == st if st else True)]
            return 200, {"topics": copy.deepcopy(rows)}
        if path == "/api/bridge/topics/segments":
            return 200, copy.deepcopy(SEGMENTS)
        if path == "/api/bridge/topics/analysis":
            return 200, copy.deepcopy(ANALYSIS)
        if path == "/api/bridge/opinions":
            st = params.get("status") or "pending"
            rows = self.opinions if st == "pending" else self.approved if st == "approved" else []
            return 200, {"opinions": copy.deepcopy(rows)}
        if path == "/api/bridge/opinions/analysis":
            self.opinions_summarize.append(str(params.get("summarize")))
            r = copy.deepcopy(OPINIONS_ANALYSIS)
            if str(params.get("summarize")) == "true":
                r["insights"] = SUMMARY_TEXT
            return 200, r
        if path == "/api/bridge/news":
            return 200, copy.deepcopy(self.news)
        if path == "/api/bridge/news-sources":
            return 200, copy.deepcopy(NEWS_SOURCES)
        if path == "/api/bridge/articles":
            return 200, {"articles": copy.deepcopy(self.plat_articles)}
        if path == "/api/bridge/creative":
            return 200, {"items": copy.deepcopy([c for c in self.creative if c["status"] == "pending_review"]), "count": len(self.creative)}
        if path == "/api/bridge/testimonials":
            st = params.get("status") or "pending"
            rows = self.testimonials if st == "pending" else self.testimonials_approved if st == "approved" else []
            return 200, {"testimonials": copy.deepcopy(rows), "count": len(rows)}
        if path == "/api/tutorials":
            return 200, copy.deepcopy(self.tutorials)
        return None

    def _write(self, method, path, body):
        parts = path.strip("/").split("/")
        if (len(parts) > 2 and parts[2] in ("topics", "opinions", "news", "articles", "creative", "testimonials", "content", "news-sources", "tutorials")):
            self._rec(method, path, body)
        # الموضوعات
        if parts[:3] == ["api", "bridge", "topics"]:
            if len(parts) == 3 and method == "POST":
                t = topic("tp-new%d" % (len(self.topics) + 1), body.get("title", ""), "draft", source=body.get("source", "human"), cat=body.get("specialty", ""), at_h=0.0, ai_answer="إجابة مقترحة مكتوبة آليًا")
                self.topics.insert(0, t)
                return 200, copy.deepcopy(t)
            tid = parts[3] if len(parts) > 3 else ""
            t = self._find(self.topics, tid)
            if t is None:
                return 404, {"detail": "الموضوع غير موجود"}
            act = parts[4] if len(parts) > 4 else ""
            if act == "approve":
                t["status"] = "open"
            elif act == "reject":
                t["status"] = "rejected"
            elif act == "publish":
                t["status"] = "published"
            elif act == "segment":
                seg = next((s for s in SEGMENTS if s["id"] == body.get("segment")), None)
                if seg is None:
                    return 422, {"detail": {"error": "unknown_segment", "message": "فئة غير معروفة"}}
                t.update({"segment": seg["id"], "segment_label": seg["label"], "segment_auto": False})
            elif act == "generate-article":
                self.generated.append(tid)
                return 200, {"title": "مقال جديد مكتوب من الموضوع", "excerpt": "ملخص قصير.", "cat": "قانوني", "kicker": "تحليل", "body": ["مقدمة.", "## قسم أول", "نص القسم."],
                             "meta_description": "وصف.", "keywords": [], "faq": []}
            elif method == "PUT":
                for k in ("title", "specialty", "question", "ai_answer", "source", "status", "merged_article", "linked_article_id"):
                    if k in body:
                        t[k] = body[k]
                if "specialty" in body:
                    t["category"] = body["specialty"]
            elif method == "DELETE":
                self.topics = [x for x in self.topics if x["id"] != tid]
            return 200, copy.deepcopy(t)
        # الآراء (التعليقات)
        if parts[:3] == ["api", "bridge", "opinions"] and len(parts) >= 4:
            oid = parts[3]
            o = self._find(self.opinions, oid) or self._find(self.approved, oid)
            if o is None:
                return 404, {"detail": "التعليق غير موجود"}
            act = parts[4] if len(parts) > 4 else ""
            if act == "approve":
                self.opinions = [x for x in self.opinions if x["id"] != oid]
                o["status"] = "approved"
                o["ai_moderation"] = _mod(abusive=False, on_topic=True, by="human", at_h=0.0)
                self.approved.insert(0, o)
            elif act == "reject":
                self.opinions = [x for x in self.opinions if x["id"] != oid]
            elif act == "reply":
                o["editor_reply"] = body.get("reply") or "رد آلي: شكرًا لمشاركتك."
                o["editor_reply_by"] = "هيئة التحرير"
            elif method == "DELETE":
                self.opinions = [x for x in self.opinions if x["id"] != oid]
                self.approved = [x for x in self.approved if x["id"] != oid]
            return 200, {"ok": True}
        # الأخبار
        if parts[:3] == ["api", "bridge", "news"] and len(parts) == 3 and method == "POST":
            n = {"id": "nw-new%d" % (len(self.news) + 1), "title": body.get("title", ""), "summary": body.get("summary", ""), "country": body.get("country", ""),
                 "specialty": body.get("specialty", ""), "source_name": body.get("source_name", ""), "source_url": body.get("source_url", ""),
                 "extra_sources": body.get("extra_sources", []), "status": "published" if body.get("publish") else "draft", "created_at": iso(0.0)}
            self.news.insert(0, n)
            return 200, n
        if parts[:3] == ["api", "bridge", "news"] and len(parts) >= 4:
            n = self._find(self.news, parts[3])
            if n is None:
                return 404, {"detail": "الخبر غير موجود"}
            if len(parts) == 5 and parts[4] == "derive-topic":
                t = topic("tp-from-news", n["title"], "open", source="news", cat=n.get("specialty", ""), at_h=0.0)
                self.topics.insert(0, t)
                return 200, copy.deepcopy(t)
            if method == "PUT":
                for k in ("title", "summary", "country", "specialty", "source_name", "source_url", "extra_sources", "status"):
                    if k in body:
                        n[k] = body[k]
                if body.get("status") == "published":
                    n["published_at"] = iso(0.0)
            elif method == "DELETE":
                self.news = [x for x in self.news if x["id"] != parts[3]]
            return 200, copy.deepcopy(n)
        if path == "/api/bridge/news-sources":
            return 200, {"ok": True}
        # مقالات المنصة
        if parts[:3] == ["api", "bridge", "articles"] and len(parts) >= 4:
            a = self._find(self.plat_articles, parts[3])
            if a is None:
                return 404, {"detail": "المقال غير موجود"}
            act = parts[4] if len(parts) > 4 else ""
            if act == "publish":
                a["status"] = "published"
            elif act == "unpublish":
                a["status"] = "draft"
            elif method == "DELETE":
                self.plat_articles = [x for x in self.plat_articles if x["id"] != parts[3]]
            return 200, {"ok": True}
        if path == "/api/bridge/content/daily-run":
            self.daily_runs.append(copy.deepcopy(body))
            return 200, {"started": True}
        # ركن الإبداع
        if parts[:3] == ["api", "bridge", "creative"] and len(parts) == 5 and parts[4] == "decide":
            c = self._find(self.creative, parts[3])
            if c is None:
                return 404, {"detail": "العمل غير موجود"}
            c["status"] = "published" if body.get("decision") == "approve" else "rejected"
            return 200, {"ok": True}
        # آراء المتعلّمين
        if parts[:3] == ["api", "bridge", "testimonials"] and len(parts) == 5:
            r = self._find(self.testimonials, parts[3])
            if r is None:
                return 404, {"detail": "التقييم غير موجود"}
            self.testimonials = [x for x in self.testimonials if x["id"] != parts[3]]
            r["status"] = "approved" if parts[4] == "approve" else "rejected"
            r["decided_at"] = iso(0.0)
            if parts[4] == "approve":
                self.testimonials_approved.insert(0, r)
            return 200, {"ok": True, "testimonial": copy.deepcopy(r)}
        # الدليل
        if parts[:3] == ["api", "bridge", "tutorials"]:
            if method == "POST" and len(parts) == 3:
                t = dict(body)
                t["id"] = "tu-new%d" % (len(self.tutorials) + 1)
                self.tutorials.append(t)
                return 200, t
            t = self._find(self.tutorials, parts[3]) if len(parts) > 3 else None
            if t is None:
                return 404, {"detail": "القسم غير موجود"}
            if method == "PUT":
                t.update(body)
            elif method == "DELETE":
                self.tutorials = [x for x in self.tutorials if x["id"] != parts[3]]
            return 200, copy.deepcopy(t)
        return None


def seed_site(appmod):
    """مقالات الموقع في SQLite الداشبورد: مسودات ومنشور اليوم وهذا الأسبوع وقديم. يعيد معرّفاتها بالترتيب."""
    m = appmod
    ids = []
    with m.app.app_context():
        m.Article.query.delete()
        m.db.session.commit()
        now = datetime.datetime.utcnow()
        for title, status, words, img, meta, rev, created_h, pub_h in BLOG_POSTS:
            paras = ["## عنوان فرعي"] + [" ".join(["كلمة"] * 40) for _ in range(max(1, words // 40))]
            a = m.Article(title=title, excerpt="مقتطف قصير عن " + title, cat="قانون الشركات", kicker="تشريعات", date="٣٠ أكتوبر ٢٠٢٦", by="الإدارة", status=status,
                          body=json.dumps(paras, ensure_ascii=False), image_url=("https://img.example.test/article-cover.jpg" if img else None),
                          meta_description=("وصف لمحركات البحث يبدأ بالإجابة." if meta else None), reviewed_by=rev,
                          created_at=now + datetime.timedelta(hours=created_h),
                          published_at=(now + datetime.timedelta(hours=pub_h)) if pub_h is not None else None)
            m.db.session.add(a)
            m.db.session.flush()
            ids.append(a.id)
        m.BlogTopic.query.delete()
        for i, (cid, slug, label) in enumerate((("contracts", "contracts", "العقود"), ("companies", "companies", "الشركات"))):
            m.db.session.add(m.BlogTopic(cluster_id=cid, slug=slug, label=label, description="وصف موضوع " + label, sort_order=i))
        m.db.session.commit()
    return ids
