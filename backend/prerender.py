#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prerender.py — يجعل مقالات elprofessor.net مقروءة لمن لا يُشغّل JavaScript.

المشكلة: /blog/<slug> اليوم = قشرة فارغة (~582 حرفًا) لأن المتن يُحقن بالـJS.
جوجل يُصيّر الصفحة فيقرأها، لكن GPTBot و ClaudeBot و PerplexityBot و Bingbot
(مسار بلا تصيير) وكل زواحف المشاركة (فيسبوك/واتساب/لينكدإن/تويتر/تليجرام)
ترى صفحة خاوية.

الحل: نولّد نسخة ثابتة مُسبقة العرض لكل مقال في blog/_pre/<id>.html، ويقدّمها
Apache على نفس الرابط تمامًا وبلا أي تحويل (القاعدة في blog/.htaccess).
الـJS يبقى يعمل فوقها (hydration) ويعيد رسم نفس المحتوى.

  WHAT IT WRITES  (relative to --site)
    blog/_pre/<id>.html     نسخة مُسبقة العرض لكل مقال منشور  (اسم ASCII بالمعرّف)
    blog/_pre/manifest.txt  معرّفات المقالات المنشورة — خطوة النشر تحذف ما ليس فيها
    blog.html               قائمة المقالات مكتوبة في الـHTML الخام (الـJS يظل يُحدّثها)
    feed.xml                RSS 2.0 بالنص الكامل داخل content:encoded
    blog/_topic/<slug>.html صفحة «دليل موضوع» لكل محور في سجلّ الموضوعات له مقال منشور
                            (تُقدَّم على /blog/topic/<slug> بقاعدة blog/.htaccess)

  WHY THE FILE NAME IS THE ARTICLE ID, NOT THE ARABIC SLUG
    مسار النشر = tar على macOS ثم فك على Linux. ماك قد يسلّم الاسم العربي بصيغة
    NFD بينما الخادم/الرابط يتوقّع NFC (٤٩ من ٧٢ سلَجًا يختلف تطبيعهما) — فينتج
    404 صامت ومتقطّع. المعرّف ASCII يُلغي هذه الفئة من الأعطال بالكامل، ويُبسّط
    اختبار وجود الملف في RewriteCond.

  WHY IT EXECUTES article.html'S OWN RENDERER INSTEAD OF REIMPLEMENTING IT
    نستخرج السكربت الداخلي من article.html ونشغّله كما هو داخل node:vm فوق
    قشرة DOM صغيرة. النتيجة ليست «شبيهة» بما يعرضه المتصفح — هي نفس السلسلة
    حرفًا بحرف، بنفس الهروب (escaping) ونفس ترتيب العناصر. وأي تعديل مستقبلي
    على دالة العرض في article.html ينتقل تلقائيًّا إلى كل الملفات المولَّدة،
    فلا تتفرّع نسختان من المُصيِّر أبدًا.

  SAFETY CONTRACT (all-or-nothing)
    نُصيّر كل المقالات في الذاكرة، نتحقق منها جميعًا، ثم نكتب. أي فشل ⇒ خروج
    بكود غير صفري وصفر تعديل على القرص. لا يجوز أبدًا أن يستبدل تشغيلٌ فاشل
    ٧٢ صفحة سليمة بصفحات فارغة — لأن قاعدة .htaccess ستقدّمها بكل رضا.

  USAGE
    python3 prerender.py --site /path/to/site            # كل المقالات
    python3 prerender.py --site /path/to/site --id 77    # يكتب ملف مقال واحد
    python3 prerender.py --site /path/to/site --dry-run  # تحقّق بلا كتابة
    python3 prerender.py --site /path/to/site --feed-file feed.json   # بلا شبكة

    يُصيَّر كل المقالات دائمًا (فالفهرس والـRSS يحتاجانها، والتحقّق يشمل الجميع)،
    و--id يحصر ما يُكتب على القرص في ملف ذلك المقال + blog.html + feed.xml.

    n8n: شغّله كآخر خطوة بعد كل نشر، وأيضًا عند التعديل وإلغاء النشر، مع
    تشغيل يومي كامل للأمان. blog.html و feed.xml يبليان مع كل نشر (المقال
    المميّز = أحدث مقال)، لا مع تعديل مقال واحد.

  REQUIREMENTS: python3 (بلا حزم خارجية) + node (موجود أصلًا مع n8n).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import format_datetime
from html import unescape as html_unescape

# ---------------------------------------------------------------------------
# ثوابت
# ---------------------------------------------------------------------------
FEED_URL = "https://dashboard.elprofessor.net/api/content/articles?status=published"
ORIGIN = "https://elprofessor.net"
DEFAULT_OG = ORIGIN + "/assets/og-default-v2.jpg"
MIN_ARTICLES = 60                # فيد أقصر من هذا = عطل، لا «إلغاء نشر ١٢ مقالًا»
FETCH_TIMEOUT = 30
FETCH_RETRIES = 3
USER_AGENT = "elprofessor-prerender/1.0 (+https://elprofessor.net)"
GTM_ID = "GTM-N5G8ZRBV"

# طوابع الـCMS بلا منطقة زمنية («2026-07-21T11:06:00.338665»). وهي UTC:
# فتحات النشر ٠٦:٠٦ و ٠٨:٠٦ و ١١:٠٦ و ١٦:٠٦ UTC = ٠٩:٠٦ و ١١:٠٦ و ١٤:٠٦ و ١٩:٠٦
# بتوقيت القاهرة، وفتحة الـ١٦:٠٦ لم تكن قد ظهرت بعدُ الساعة ١٧:٢٠ بتوقيت القاهرة.
# بدون تثبيتها يحسب كل قارئ لحظةً مختلفة — وأحيانًا يومًا مختلفًا (مقالان اليوم).
# لو تبيّن أن الـCMS يكتب بتوقيت القاهرة فهذا هو التعديل الوحيد المطلوب:
CMS_TZ = timezone.utc

MARK_FEAT_OPEN, MARK_FEAT_CLOSE = "<!--EP:FEAT-->", "<!--/EP:FEAT-->"
MARK_GRID_OPEN, MARK_GRID_CLOSE = "<!--EP:GRID-->", "<!--/EP:GRID-->"

# ---------------------------------------------------------------------------
# صندوق النموذج المجاني (lead magnet) — مكانه article.html، لا هنا.
#
# ⛔ لا تحقن صندوقًا من هذا الملف. القالب يحمل واحدًا (<section id="leadMagnet">)
#    بعد </article> مباشرةً وقبل «مقالات ذات صلة»، وهذا المولّد ينسخ القالب كما
#    هو ولا يغيّر منه إلا المراسي المذكورة أدناه — فالصندوق يصل إلى كل صفحة
#    مُسبقة العرض تلقائيًّا. حقن نسخة ثانية هنا = صندوقان متلاصقان على ~١٤٠
#    صفحة، ومصدرا حقيقة للنموذج نفسه يتفرّعان مع الوقت (نفس علّة «مُصيِّرين»
#    التي يمنعها هذا الملف أصلًا).
#
# موضعه في القالب صحيح ومقصود: خارج #art و#relatedWrap. الترطيب يعيد كتابة
# innerHTML لهذين العنصرين فقط، وما بينهما يبقى كما هو فلا يمحوه الـJS.
#
# دورنا هنا التحقق فقط — عند كل مقال، قبل أن يُكتب أي بايت:
#   • لا صندوق أصلًا ⇒ تحذير لا فشل (قد يكون حذفًا مقصودًا من القالب؛ إسقاط
#     ١٤٠ صفحة بسبب عنصر تسويقي اختياري عقوبة أكبر من الذنب — منطق «keywords»).
#   • صندوق موجود ⇒ لا بد أن يكون سليمًا: مرّة واحدة، بمصيدة، وبالأصل الصحيح.
#
# ⚠️ عدّادان لا واحد، وهذا مقصود:
#   URL يعدّ *المعالِجات* (يرد مرّة واحدة في السكربت)، والمصيدة تعدّ *الصناديق*
#   (حقل في كل نموذج). تكرار قسم الصندوق في القالب يعطي صندوقين ظاهرين بمعالِج
#   واحد ⇒ عدّاد الـURL وحده يراها «واحدة» ويمرّرها. المصيدة هي ما يكشفها.
#   المصيدة أيضًا جزء من عقد الخادم (يُسقط من يملأ «website») لا زينة، فتغيّر
#   اسمها عطل حقيقي يستحق الفشل لا التحذير.
# ---------------------------------------------------------------------------
LEAD_MAGNET_URL = "https://api.elprofessor.net/api/lead-magnet"
LEAD_MAGNET_ASSET = "fee-contract-template"
LEAD_MAGNET_HONEYPOT = 'name="website"'


class Fail(Exception):
    """فشل قاتل — لا يُكتب شيء على القرص."""


def log(msg):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


# ---------------------------------------------------------------------------
# الهروب — ثلاث دوال منفصلة عمدًا. خلطها = إفساد ٧٢ مقالًا عربيًّا.
# ---------------------------------------------------------------------------
def esc_text(s):
    """نص داخل HTML."""
    return (str("" if s is None else s)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def esc_attr(s):
    """قيمة سِمة HTML (نطابق esc() في article.html فنهرب ' أيضًا)."""
    return (str("" if s is None else s)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&#39;"))


def esc_ldjson(obj):
    """JSON-LD داخل <script>: «</» واحدة تُنهي العنصر وتكسر الصفحة."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    return (s.replace("<", "\\u003C").replace(">", "\\u003E")
             .replace("&", "\\u0026")
             # فاصلا السطر U+2028/U+2029 مسموحان في JSON ويكسران السكربت في JS
             .replace(chr(0x2028), "\\u2028").replace(chr(0x2029), "\\u2029"))


def esc_jsstr(s):
    """سلسلة نصية داخل <script> عادي."""
    return json.dumps(str(s), ensure_ascii=False).replace("<", "\\u003C")


def esc_xml_text(s):
    return (str("" if s is None else s)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def cdata(s):
    """CDATA محصّنة ضد «]]>» حرفية داخل المتن."""
    return "<![CDATA[" + str(s).replace("]]>", "]]]]><![CDATA[>") + "]]>"


# ---------------------------------------------------------------------------
# أدوات نصية — كلها literal replace. لا re.sub بنص المقال في بديلها أبدًا:
# «$&» و«\1» داخل نص عربي حرّ تفسدان الصفحة (بايثون آمن، لكن القاعدة واحدة).
# ---------------------------------------------------------------------------
def replace_once(doc, old, new, what):
    n = doc.count(old)
    if n != 1:
        raise Fail("anchor %s occurs %d times (expected 1): %r" % (what, n, old[:70]))
    return doc.replace(old, new, 1)


def unique_line(doc, pattern, what):
    """السطر الكامل الوحيد المطابق — نطابق الوسم كاملًا لا سلسلة عارية.
    («مقال — البروفيسور» ترد مرّتين في article.html؛ مطابقة السطر تمنع الخلط.)"""
    hits = [ln for ln in doc.split("\n") if re.match(pattern, ln)]
    if len(hits) != 1:
        raise Fail("line anchor %s matched %d lines (expected 1)" % (what, len(hits)))
    if doc.count(hits[0]) != 1:
        raise Fail("line anchor %s is not unique as a substring" % what)
    return hits[0]


def strip_to_text(html):
    """نص خام كما يراه مستخرِج نصوص: يُسقط <script> و<style> أولًا — وهذه
    بالضبط الخطوة التي تجعل الصفحة الحالية ٥٨٢ حرفًا."""
    s = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    s = re.sub(r"(?is)<style\b.*?</style>", " ", s)
    s = re.sub(r"(?s)<!--.*?-->", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# التواريخ
# ---------------------------------------------------------------------------
def parse_cms_dt(value):
    """طابع الـCMS (بلا منطقة) → datetime واعية بالمنطقة، أو None."""
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CMS_TZ)
    return dt.astimezone(timezone.utc)


def iso_z(dt):
    """2026-07-21T11:06:00Z — نُسقط الكسور لثبات المخرجات."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rfc822(dt):
    """Tue, 21 Jul 2026 11:06:00 +0000 — أسماء إنجليزية مستقلة عن الـlocale."""
    return format_datetime(dt)


# ---------------------------------------------------------------------------
# الفيد
# ---------------------------------------------------------------------------
def fetch_feed(feed_file=None, url=FEED_URL, min_articles=MIN_ARTICLES):
    if feed_file:
        with open(feed_file, "rb") as fh:
            raw = fh.read()
        log("feed: read from file %s (%d bytes)" % (feed_file, len(raw)))
    else:
        last, raw = None, None
        for attempt in range(1, FETCH_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as res:
                    if res.status != 200:
                        raise Fail("feed HTTP %s" % res.status)
                    raw = res.read()
                break
            except Exception as exc:            # noqa: BLE001 — نُبلّغ ونعيد المحاولة
                last = exc
                log("feed: attempt %d/%d failed: %s" % (attempt, FETCH_RETRIES, exc))
                if attempt < FETCH_RETRIES:
                    time.sleep(2 * attempt)
        if raw is None:
            raise Fail("feed unreachable after %d attempts: %s" % (FETCH_RETRIES, last))
        log("feed: fetched %d bytes" % len(raw))

    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:                    # noqa: BLE001
        raise Fail("feed is not valid UTF-8 JSON: %s" % exc)

    articles = data.get("articles") if isinstance(data, dict) else None
    if not isinstance(articles, list):
        raise Fail("feed shape is wrong: no articles[] array")
    if not articles:
        raise Fail("feed returned ZERO articles — refusing to touch disk")
    if len(articles) < min_articles:
        raise Fail("feed has only %d articles (< min %d) — looks truncated; refusing to run "
                   "(a short feed would prune live pages)" % (len(articles), min_articles))

    seen = set()
    for a in articles:
        if not isinstance(a, dict):
            raise Fail("feed row is not an object")
        if a.get("id") is None or not str(a.get("id")).isdigit():
            raise Fail("feed row has a non-numeric id: %r" % (a.get("id"),))
        if not a.get("slug"):
            raise Fail("feed row id=%s has no slug" % a.get("id"))
        if not a.get("title"):
            raise Fail("feed row id=%s has no title" % a.get("id"))
        key = str(a["id"])
        if key in seen:
            raise Fail("duplicate article id %s in feed" % key)
        seen.add(key)
        # الثابت الذي تقوم عليه قاعدة .htaccess كلها: السلَج ينتهي بـ«-<id>»
        m = re.search(r"(\d+)$", str(a["slug"]))
        if not m or m.group(1) != key:
            raise Fail("slug/id invariant broken for id=%s (slug=%r): the .htaccess rule "
                       "resolves the article from the slug's trailing id" % (key, a["slug"]))
    log("feed: %d articles, ids %s..%s, source=%r"
        % (len(articles), articles[-1].get("id"), articles[0].get("id"), data.get("source")))
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    return articles, (data.get("source") or ""), topics


# ---------------------------------------------------------------------------
# استخراج سكربت الصفحة + تشغيله في node
# ---------------------------------------------------------------------------
def extract_inline(doc, end_marker, what):
    start = "<script>\nvar ELE="
    if doc.count(start) != 1 or doc.count(end_marker) != 1:
        raise Fail("cannot locate the inline renderer in %s" % what)
    i = doc.index(start)
    j = doc.index(end_marker, i)
    return doc[i + len("<script>\n"):j]


NODE_RUNNER = r"""
'use strict';
// قشرة DOM أدنى ما يلزم لتشغيل سكربت الصفحة كما هو (بلا أي حزمة خارجية).
const fs = require('fs'), vm = require('vm');
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));

function makeEl(tag) {
  return {
    tagName: tag, _attrs: Object.create(null), innerHTML: '', textContent: '',
    id: '', type: '', style: {}, dataset: {},
    setAttribute(k, v) { this._attrs[k] = String(v); if (k === 'id') this.id = String(v); },
    getAttribute(k) { return Object.prototype.hasOwnProperty.call(this._attrs, k) ? this._attrs[k] : null; },
    removeAttribute(k) { delete this._attrs[k]; },
    remove() {},
    appendChild(c) { return c; },
    insertAdjacentHTML(pos, html) {
      if (pos === 'afterbegin') { this.innerHTML = html + this.innerHTML; }
      else { this.innerHTML += html; }
    },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    closest() { return makeEl('div'); },
    addEventListener() {},
    classList: { toggle() { return true; }, add() {}, remove() {}, contains() { return false; } }
  };
}

function runPage(code, els, ctxExtra) {
  const headSink = [], selCache = Object.create(null);
  const document = {
    title: '',
    head: { appendChild(c) { headSink.push(c); return c; } },
    body: makeEl('body'),
    getElementById(id) { return Object.prototype.hasOwnProperty.call(els, id) ? els[id] : null; },
    createElement(t) { return makeEl(t); },
    // كل استدعاء querySelector يعيد نفس العنصر الوهمي لنفس المُحدِّد، فنلتقط ما
    // كتبه injectMeta فعلًا بدل إعادة حسابه — وبهذا لا تختلف الصفحة الثابتة
    // عمّا سيكتبه الـJS وقت التشغيل ولو بحرف.
    querySelector(sel) {
      if (!Object.prototype.hasOwnProperty.call(selCache, sel)) selCache[sel] = makeEl('meta');
      return selCache[sel];
    },
    querySelectorAll() { return []; },
    addEventListener() {}
  };
  const win = { document: document, addEventListener() {}, removeEventListener() {},
                setTimeout() { return 0; }, clearTimeout() {},
                navigator: { clipboard: { writeText() {} } } };
  Object.assign(win, ctxExtra);
  win.window = win;
  const ctx = vm.createContext(win);          // مجال جديد ⇒ كل الـbuilt-ins حاضرة
  vm.runInContext(code, ctx, { filename: 'page-inline.js' });
  if (typeof ctx.EP_RENDER !== 'function') throw new Error('EP_RENDER is not defined');
  ctx.EP_RENDER();
  const sel = {};
  for (const k in selCache) sel[k] = selCache[k]._attrs;
  const ld = {};
  headSink.forEach(function (n) { if (n && n.id) ld[n.id] = n.textContent; });
  return { title: document.title, sel: sel, ld: ld };
}

const out = { articles: {}, blog: null };

payload.articles.forEach(function (a) {
  const els = { art: makeEl('article'), relatedWrap: makeEl('section') };
  const r = runPage(payload.articleCode, els, {
    SITE_CONTENT: { source: payload.source, articles: payload.articles },
    // نطابق ما ستكون عليه الصفحة المنشورة بالضبط
    EP_PRERENDERED: true, EP_ID: String(a.id), EP_SLUG: String(a.slug),
    location: { search: '', hash: '', pathname: '/blog/' + String(a.slug),
                href: 'https://elprofessor.net/blog/' + encodeURIComponent(String(a.slug)),
                replace: function () {
                  throw new Error('render() called location.replace for id=' + a.id
                                  + ' — the article did not resolve'); } }
  });
  out.articles[String(a.id)] = { art: els.art.innerHTML, related: els.relatedWrap.innerHTML,
                                 title: r.title, sel: r.sel, ld: r.ld };
});

const bels = { filters: makeEl('div'), featuredWrap: makeEl('div'), grid: makeEl('div') };
runPage(payload.blogCode, bels, {
  SITE_CONTENT: { source: payload.source, articles: payload.articles },
  EP_PRERENDERED: true,
  location: { search: '', hash: '', pathname: '/blog.html',
              href: 'https://elprofessor.net/blog.html', replace: function () {} }
});
out.blog = { featured: bels.featuredWrap.innerHTML, grid: bels.grid.innerHTML,
             filters: bels.filters.innerHTML };

fs.writeFileSync(process.argv[3], JSON.stringify(out));
"""


def run_node(article_code, blog_code, articles, source):
    node = shutil.which("node")
    if not node:
        raise Fail("node not found on PATH. The generator executes article.html's own "
                   "renderer so the output matches the browser byte for byte; a Python "
                   "re-implementation would be a second renderer that silently drifts. "
                   "Install node (n8n already ships one).")
    tmp = tempfile.mkdtemp(prefix="ep-prerender-")
    try:
        runner = os.path.join(tmp, "runner.js")
        pay = os.path.join(tmp, "payload.json")
        res = os.path.join(tmp, "out.json")
        with open(runner, "w", encoding="utf-8") as fh:
            fh.write(NODE_RUNNER)
        with open(pay, "w", encoding="utf-8") as fh:
            json.dump({"articleCode": article_code, "blogCode": blog_code,
                       "articles": articles, "source": source}, fh, ensure_ascii=False)
        env = dict(os.environ)
        env["TZ"] = "UTC"            # ثبات المخرجات مهما كانت منطقة الجهاز
        env["NODE_OPTIONS"] = ""
        proc = subprocess.run([node, runner, pay, res], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if proc.returncode != 0:
            raise Fail("node renderer failed (rc=%d):\n%s"
                       % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-4000:]))
        with open(res, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# بناء صفحة المقال
# ---------------------------------------------------------------------------
def article_url(slug):
    return ORIGIN + "/blog/" + urllib.parse.quote(str(slug), safe="")


def build_article(tpl, a, r):
    aid = str(a["id"])
    sel = r.get("sel") or {}

    def picked(selector, attr="content"):
        v = (sel.get(selector) or {}).get(attr)
        return v if v else None

    # نأخذ ما كتبه injectMeta فعلًا (قصّ الوصف، ضمّ الكلمات المفتاحية، ترميز
    # الرابط) بدل إعادة حسابه — فلا تتغيّر أي قيمة عند الترطيب.
    title = r.get("title") or ""
    desc = (picked('meta[name="description"]')
            or str(a.get("meta_description") or a.get("excerpt") or a.get("title") or "")[:300])
    keywords = picked('meta[name="keywords"]')
    canonical = picked('link[rel="canonical"]', "href") or article_url(a["slug"])
    og_url = picked('meta[property="og:url"]') or canonical
    og_title = picked('meta[property="og:title"]') or str(a.get("title") or "")
    og_desc = picked('meta[property="og:description"]') or desc
    og_image = picked('meta[property="og:image"]')          # يُكتب فقط لو للمقال صورة

    pub_dt = parse_cms_dt(a.get("published_at")) or parse_cms_dt(a.get("date"))
    mod_dt = parse_cms_dt(a.get("updated_at")) or pub_dt

    # ---- JSON-LD: نأخذ ما بناه injectMeta ونثبّت التواريخ فقط -----------------
    lds = []
    for key in ("ld-article", "ld-bc", "ld-faq"):
        raw = (r.get("ld") or {}).get(key)
        if raw is None:
            continue
        try:
            obj = json.loads(raw)
        except Exception as exc:                # noqa: BLE001
            raise Fail("id=%s: %s is not valid JSON: %s" % (aid, key, exc))
        if key == "ld-article" and pub_dt:
            obj["datePublished"] = iso_z(pub_dt)
            obj["dateModified"] = iso_z(mod_dt or pub_dt)
        if key == "ld-article":
            # E4 — الفيد يقرّر نوع الكاتب حين يعرفه (author_type)؛ غيابه = ما بناه القالب كما هو.
            if a.get("author_type") == "Organization":
                obj["author"] = {"@type": "Organization", "name": a.get("author_name") or "البروفيسور"}
            # reviewedBy فقط لمراجعة بشرية حقيقية مسجّلة — لا يُدّعى أبدًا.
            if a.get("reviewed_by"):
                obj["reviewedBy"] = {"@type": "Person", "name": str(a["reviewed_by"])}
        lds.append((key, obj))
    have = [k for k, _ in lds]
    if "ld-article" not in have or "ld-bc" not in have:
        raise Fail("id=%s: missing JSON-LD (%s)" % (aid, have))
    if bool(a.get("faq")) != ("ld-faq" in have):
        raise Fail("id=%s: ld-faq present=%s but faq in feed=%s"
                   % (aid, "ld-faq" in have, bool(a.get("faq"))))

    out = tpl

    # 1) العنوان — من document.title كما ضبطه المُصيِّر (لا نُعيد كتابة العربية)
    ln = unique_line(out, r"^<title>.*</title>$", "title")
    out = replace_once(out, ln, "<title>" + esc_text(title) + "</title>", "title")

    # 2) الوصف + الكلمات المفتاحية
    ln = unique_line(out, r'^<meta name="description" content=".*">$', "description")
    new = '<meta name="description" content="%s">' % esc_attr(desc)
    if keywords:
        new += '\n<meta name="keywords" content="%s">' % esc_attr(keywords)
    out = replace_once(out, ln, new, "description")

    # 3) الأصل (canonical) و og:url ووقت النشر — مكان تعليق «لا يُكتب ثابتًا هنا»
    ln = unique_line(out, r"^<!-- canonical/og:url", "canonical-comment")
    new = ("<!-- EP:PRERENDER — canonical/og:url مكتوبان ثابتين هنا، وinjectMeta "
           "يعيد كتابتهما بنفس القيمة وقت التشغيل -->\n"
           '<link rel="canonical" href="%s">\n'
           '<meta property="og:url" content="%s">' % (esc_attr(canonical), esc_attr(og_url)))
    if pub_dt:
        new += '\n<meta property="article:published_time" content="%s">' % esc_attr(iso_z(pub_dt))
        if mod_dt and iso_z(mod_dt) != iso_z(pub_dt):
            new += '\n<meta property="article:modified_time" content="%s">' % esc_attr(iso_z(mod_dt))
    if a.get("cat"):
        new += '\n<meta property="article:section" content="%s">' % esc_attr(a["cat"])
    out = replace_once(out, ln, new, "canonical-comment")

    # 4) og:title / og:description
    ln = unique_line(out, r'^<meta property="og:title" content=".*">$', "og:title")
    out = replace_once(out, ln, '<meta property="og:title" content="%s">' % esc_attr(og_title),
                       "og:title")
    ln = unique_line(out, r'^<meta property="og:description" content=".*">$', "og:description")
    out = replace_once(out, ln, '<meta property="og:description" content="%s">' % esc_attr(og_desc),
                       "og:description")

    # 5) og:image — صورة المقال إن وُجدت، وإلا نُبقي الافتراضية ونعلن مقاسها
    ln = unique_line(out, r'^<meta property="og:image" content="https://elprofessor\.net/assets/'
                          r'og-default-v2\.jpg">$', "og:image")
    share_img = og_image or DEFAULT_OG
    new = '<meta property="og:image" content="%s">' % esc_attr(share_img)
    if not og_image:
        new += ('\n<meta property="og:image:width" content="1200">'
                '\n<meta property="og:image:height" content="630">')
    out = replace_once(out, ln, new, "og:image")

    # 6) twitter:* — لا يلمسها injectMeta إطلاقًا، فتبقى عامّة بلا هذا
    ln = unique_line(out, r'^<meta name="twitter:card" content="summary_large_image">$',
                     "twitter:card")
    out = replace_once(out, ln, ln
                       + '\n<meta name="twitter:title" content="%s">' % esc_attr(og_title)
                       + '\n<meta name="twitter:description" content="%s">' % esc_attr(og_desc)
                       + '\n<meta name="twitter:image" content="%s">' % esc_attr(share_img),
                       "twitter:card")

    # 7) JSON-LD بعد رسم Organization/WebSite وقبل <style> — كي يبقى GTM
    #    وpixel.js في آخر الـ<head> بنفس ترتيبهما الحالي تمامًا.
    blocks = "".join('<script type="application/ld+json" id="%s">%s</script>\n'
                     % (k, esc_ldjson(o)) for k, o in lds)
    out = replace_once(out, "</script>\n<style>\n:root{",
                       "</script>\n" + blocks + "<style>\n:root{", "ld-insert")

    # 8) المتن + المقالات ذات الصلة. صندوق النموذج المجاني بينهما في القالب
    #    ويمرّ كما هو — لا نحقنه هنا (انظر تعليق LEAD_MAGNET_URL أعلاه).
    out = replace_once(out, '<article class="art" id="art"></article>',
                       '<article class="art" id="art">' + r["art"] + "</article>", "art")
    out = replace_once(out, '<section class="wrap related" id="relatedWrap"></section>',
                       '<section class="wrap related" id="relatedWrap">' + r["related"] + "</section>",
                       "relatedWrap")

    # 9) علَم الترطيب — قبل site-content.js مباشرةً. EP_PRERENDERED هو ما يمنع
    #    الـJS من مسح صفحة سليمة (أو إلغاء فهرستها) لو تعذّر الفيد.
    #    EP_SLUG بترميز \u كي لا تتوقّف المطابقة على كيفية فكّ ترميز المستند.
    anchor = '<script src="/site-content.js?v=20260703a"></script>'
    out = replace_once(out, anchor,
                       "<script>window.EP_PRERENDERED=true;window.EP_ID=%s;window.EP_SLUG=%s;</script>\n%s"
                       % (esc_jsstr(aid), esc_jsstr(a["slug"]), anchor), "site-content")

    return out, {"canonical": canonical, "title": title, "desc": desc,
                 "pub": iso_z(pub_dt) if pub_dt else None, "img": share_img}


# ---------------------------------------------------------------------------
# التحقق — كل مقال وكل ملف، قبل أن يُكتب أي بايت
# ---------------------------------------------------------------------------
def verify_article(html, a, r, meta, ctx):
    aid = str(a["id"])
    errs = []

    def bad(msg):
        errs.append("id=%s: %s" % (aid, msg))

    art = r["art"]
    if len(art) < 1500:
        bad("rendered #art is only %d chars" % len(art))
    if "<h1>" not in art:
        bad("no <h1> in #art")
    if esc_text(a["title"]) not in art and esc_attr(a["title"]) not in art:
        bad("the article's own title is not in #art")
    # فاصل معلّق بلا تاريخ — ٦ مقالات حقل date فيها فارغ، وfmtDate يشتقّه من
    # published_at. لو رجع العيب ظهر «<span>·</span><span></span>» هنا.
    if "<span>·</span><span></span>" in art:
        bad("empty date chip (dangling separator) — fmtDate returned nothing")
    for t in ctx["soft404"]:
        if t and t in meta["title"]:
            bad("document.title is the soft-404 title %r" % t)
    if ctx["placeholder"] in html:
        bad("the template's placeholder title is still in the page")

    # وسوم الرأس مرّة واحدة فقط: الترطيب يُحدّثها في مكانها، فالتكرار = عقدتان
    for tag, pat in (("<title>", r"<title>"),
                     ("canonical", r'<link rel="canonical"'),
                     ("og:url", r'<meta property="og:url"'),
                     ("og:title", r'<meta property="og:title"'),
                     ("og:description", r'<meta property="og:description"'),
                     ("og:image", r'<meta property="og:image" '),
                     ("description", r'<meta name="description"'),
                     ("keywords", r'<meta name="keywords"')):
        n = len(re.findall(pat, html))
        if tag == "keywords" and n == 0:
            continue
        if n != 1:
            bad("%s appears %d times (expected 1)" % (tag, n))
    for lid in ("ld-article", "ld-bc"):
        if html.count('id="%s"' % lid) != 1:
            bad("%s block count != 1" % lid)
    if html.count('id="ld-faq"') != (1 if a.get("faq") else 0):
        bad("ld-faq block count wrong")
    for m in re.finditer(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', html):
        try:
            json.loads(m.group(1))
        except Exception as exc:                # noqa: BLE001
            bad("a JSON-LD block does not parse: %s" % exc)

    # القياس/التتبّع: gtag('config') من pixel.js فقط، ولا Meta داخل GTM
    if html.count(GTM_ID) != 2:
        bad("%s appears %d times (expected 2: head snippet + noscript iframe)"
            % (GTM_ID, html.count(GTM_ID)))
    if html.count("googletagmanager.com/ns.html") != 1:
        bad("GTM noscript iframe count != 1")
    if html.count("/pixel.js?v=") != 1:
        bad("pixel.js count != 1")
    if "gtag('config'" in html or 'gtag("config"' in html:
        bad("an inline gtag('config') leaked into the page")
    if html.count("facebook.com/tr?id=") != 1:
        bad("Meta noscript pixel count != 1")

    # الترميز: <meta charset> لا بد أن يبقى داخل أول ١٠٢٤ بايت (استنتاج الترميز)
    pos = html.encode("utf-8").find(b'<meta charset="UTF-8">')
    if pos < 0 or pos > 1024:
        bad("<meta charset> missing or beyond byte 1024 (found at %d)" % pos)
    if "window.EP_PRERENDERED=true" not in html:
        bad("EP_PRERENDERED flag missing")

    # صندوق النموذج المجاني — يأتي من القالب؛ نتحقق فقط (التفصيل عند الثابت)
    n_post = html.count(LEAD_MAGNET_URL)            # معالِجات الإرسال
    n_box = html.count(LEAD_MAGNET_HONEYPOT)        # صناديق ظاهرة
    if n_post > 1:
        bad("lead-magnet posts to %s from %d places (expected 1) — article.html must hold "
            "exactly one box and this generator must not inject one" % (LEAD_MAGNET_URL, n_post))
    if n_post == 1 or n_box:
        if n_box > 1:
            bad("lead-magnet box appears %d times (expected 1) — the boxes stack on the "
                "page; counted by the honeypot field %s" % (n_box, LEAD_MAGNET_HONEYPOT))
        elif n_box == 0:
            bad("lead-magnet box has no honeypot field (%s) — the form would be bot-farmed, "
                "and the server drops submissions by that field name"
                % LEAD_MAGNET_HONEYPOT)
        if n_post != 1:
            bad("lead-magnet box is present but posts to %s %d times — a form with no "
                "handler collects nothing" % (LEAD_MAGNET_URL, n_post))
        if LEAD_MAGNET_ASSET not in html:
            bad("lead-magnet posts without asset %r — the wrong file would be sent"
                % LEAD_MAGNET_ASSET)

    txt = strip_to_text(html)
    if len(txt) < 1500:
        bad("script/style-stripped text is only %d chars" % len(txt))

    # «ضمن موضوع: …» — يتسلّح فور أن يقرأ مُصيِّر article.html الحقل topic_slug
    ts = str(a.get("topic_slug") or "")
    if ctx.get("renderer_has_topic") and TOPIC_SLUG_RE.match(ts) and a.get("role") in ("hub", "support"):
        if ('href="/blog/topic/%s"' % ts) not in art:
            bad("topic link /blog/topic/%s missing from #art (renderer reads topic_slug)" % ts)

    # يتسلّح تلقائيًّا فور إضافة عرض الأسئلة الشائعة إلى المُصيِّر في article.html
    if ctx["renderer_has_faq"] and a.get("faq"):
        q = str((a["faq"][0] or {}).get("q") or "")
        if q and esc_text(q) not in art and esc_attr(q) not in art:
            bad("renderer declares FAQ rendering but the first question is not in #art")
    return errs, len(txt)


# ---------------------------------------------------------------------------
# blog.html
# ---------------------------------------------------------------------------
def build_blog(doc, blog):
    def splice(d, open_m, close_m, clean_anchor, payload):
        block = open_m + "\n" + payload + "\n" + close_m
        if open_m in d:
            if d.count(open_m) != 1 or d.count(close_m) != 1:
                raise Fail("blog.html markers %s are not unique" % open_m)
            i = d.index(open_m)
            j = d.index(close_m, i)
            return d[:i] + block + d[j + len(close_m):]
        close_tag = "</div>"
        if not clean_anchor.endswith(close_tag):
            raise Fail("bad blog anchor %r" % clean_anchor)
        return replace_once(d, clean_anchor,
                            clean_anchor[:-len(close_tag)] + block + close_tag,
                            clean_anchor[:30])

    out = splice(doc, MARK_FEAT_OPEN, MARK_FEAT_CLOSE,
                 '<div id="featuredWrap"></div>', blog["featured"])
    out = splice(out, MARK_GRID_OPEN, MARK_GRID_CLOSE,
                 '<div class="bgrid" id="grid"></div>', blog["grid"])
    flag = "<script>window.EP_PRERENDERED=true;</script>"
    anchor = '<script src="site-content.js?v=20260703a"></script>'
    if flag not in out:
        out = replace_once(out, anchor, flag + "\n" + anchor, "blog site-content")
    return out


def verify_blog(html, articles):
    errs = []
    if html.count('<a class="post" href="/blog/') != len(articles) - 1:
        errs.append("blog.html grid has %d cards (expected %d)"
                    % (html.count('<a class="post" href="/blog/'), len(articles) - 1))
    if html.count('<a class="feat" href="/blog/') != 1:
        errs.append("blog.html featured card count != 1")
    if html.count(GTM_ID) != 2:
        errs.append("blog.html %s count != 2" % GTM_ID)
    if "gtag('config'" in html:
        errs.append("blog.html has an inline gtag('config')")
    if html.count("<script>window.EP_PRERENDERED=true;</script>") != 1:
        errs.append("blog.html EP_PRERENDERED flag count != 1")
    # الرقائق (#filters) لا تُصدَّر عمدًا: معالجات النقر تُربط عند العرض فقط،
    # فرقائق ثابتة أثناء عطل الفيد = عناصر تبدو تفاعلية وهي ميتة.
    i = html.find('<div class="filters" id="filters">')
    j = html.find("</div>", i) if i >= 0 else -1
    if i < 0 or "fchip" in html[i:j]:
        errs.append("blog.html #filters region is missing or contains prerendered chips")
    for m in re.finditer(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', html):
        try:
            json.loads(m.group(1))
        except Exception as exc:                # noqa: BLE001
            errs.append("blog.html JSON-LD does not parse: %s" % exc)
    txt = strip_to_text(html)
    if len(txt) < 5000:
        errs.append("blog.html stripped text is only %d chars" % len(txt))
    return errs, len(txt)


# ---------------------------------------------------------------------------
# RSS
# ---------------------------------------------------------------------------
def rss_body(art_html, aid):
    """المتن كما صيّرته الصفحة: من فقرة المقدّمة حتى ملاحظة الخبير (فيشمل
    الأسئلة الشائعة تلقائيًّا فور إضافتها للمُصيِّر)، بلا فتات المسار ولا أزرار
    المشاركة. حدّان حرفيّان — لو تغيّرا نفشل بصوت عالٍ بدل شحن متن ناقص."""
    i = art_html.find('<p class="lead-p">')
    j = art_html.find('<div class="expert-note">')
    if i < 0 or j <= i:
        raise Fail("id=%s: cannot slice the RSS body out of the rendered article" % aid)
    return art_html[i:j].strip()


def build_rss(articles, rendered, blog_doc, feed_url, limit=0):
    m = re.search(r"<title>(.*?)</title>", blog_doc, re.S)
    d = re.search(r'<meta name="description" content="(.*?)">', blog_doc, re.S)
    if not m or not d:
        raise Fail("cannot read the channel title/description out of blog.html")
    chan_title = html_unescape(m.group(1))
    chan_desc = html_unescape(d.group(1))

    rows = articles if not limit else articles[:limit]
    newest, items = None, []
    for a in rows:
        aid = str(a["id"])
        r = rendered.get(aid)
        if not r:
            continue
        dt = parse_cms_dt(a.get("published_at")) or parse_cms_dt(a.get("date"))
        if dt and (newest is None or dt > newest):
            newest = dt
        url = article_url(a["slug"])
        parts = ["<item>",
                 "<title>%s</title>" % esc_xml_text(a.get("title")),
                 "<link>%s</link>" % esc_xml_text(url),
                 '<guid isPermaLink="true">%s</guid>' % esc_xml_text(url)]
        if dt:
            parts.append("<pubDate>%s</pubDate>" % esc_xml_text(rfc822(dt)))
        if a.get("cat"):
            parts.append("<category>%s</category>" % esc_xml_text(a["cat"]))
        if a.get("by"):
            parts.append("<dc:creator>%s</dc:creator>" % esc_xml_text(a["by"]))
        parts.append("<description>%s</description>"
                     % esc_xml_text(a.get("meta_description") or a.get("excerpt") or ""))
        parts.append("<content:encoded>%s</content:encoded>" % cdata(rss_body(r["art"], aid)))
        parts.append("</item>")
        items.append("\n".join(parts))
    if not items:
        raise Fail("RSS would be empty")

    head = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"'
            ' xmlns:dc="http://purl.org/dc/elements/1.1/"'
            ' xmlns:atom="http://www.w3.org/2005/Atom">',
            "<channel>",
            "<title>%s</title>" % esc_xml_text(chan_title),
            "<link>%s/blog.html</link>" % ORIGIN,
            '<atom:link href="%s" rel="self" type="application/rss+xml"/>' % esc_xml_text(feed_url),
            "<description>%s</description>" % esc_xml_text(chan_desc),
            "<language>ar</language>",
            "<generator>elprofessor prerender</generator>"]
    # lastBuildDate من أحدث مقال لا من لحظة التشغيل — وإلا لما تطابق تشغيلان
    # بنفس المدخلات بايتًا ببايت.
    if newest:
        head.append("<lastBuildDate>%s</lastBuildDate>" % esc_xml_text(rfc822(newest)))
    head.append("<image><url>%s/logo.png</url><title>%s</title><link>%s/blog.html</link></image>"
                % (ORIGIN, esc_xml_text(chan_title), ORIGIN))
    return "\n".join(head) + "\n" + "\n".join(items) + "\n</channel>\n</rss>\n"


# ---------------------------------------------------------------------------
# صفحات الموضوعات — /blog/topic/<slug>  ⇐  blog/_topic/<slug>.html
#
# صفحة «دليل موضوع» ثابتة لكل محور في سجلّ الموضوعات (الداشبورد) له مقال منشور:
# H1 = اسم الموضوع، ثم وصفه، ثم مقال المحور (hub) أولًا، ثم التفصيلية (support)، ثم
# مقالات مستقلّة قريبة إن وُجدت. القالب = blog.html نفسه (الترويسة والتذييل والأنماط
# والقياس كما هي) — نستبدل الرأس والهيرو ومنطقة المحتوى بمراسٍ حرفية، ونشيل مُصيِّر
# المدوّنة (لا شيء يُرسم هنا بالـJS).
#
# ⛔ الصفحة تُقدَّم على /blog/topic/<slug> لا على الجذر ⇒ كل مسار نسبي في القالب
#    (mobile-fixes.css · pixel.js · favicon…) يُحوَّل لمسار مطلق، وإلا ٤٠٤ صامت
#    (نفس فخّ article.html المسجّل مرّتين في CLAUDE.md الموقع).
# ⛔ فشل بناء الموضوعات لا يُسقط التشغيل كله: المقالات أهم، فنسجّل بصوت عالٍ
#    ونكمل بلا صفحات موضوعات (ولا نمسح القديمة — المسح يشترط توليدًا غير فارغ).
# ---------------------------------------------------------------------------
TOPIC_DIR = "_topic"
TOPIC_SLUG_RE = re.compile(r"^[a-z](?:[a-z0-9-]{0,62}[a-z])?$")
TOPIC_PAGE_RE = re.compile(r"^[a-z](?:[a-z0-9-]{0,62}[a-z])?\.html$")
MARK_TOPICS_OPEN, MARK_TOPICS_CLOSE = "<!--EP:TOPICS-->", "<!--/EP:TOPICS-->"
TONES = ("t1", "t2", "t3", "t4", "t5", "t6")
AR_MONTHS = ("يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس",
             "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر")
_AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# تطبيع عربي لمطابقة «مقالات قريبة» — نفس قواعد بحث blog.html (الألف/التاء المربوطة/الياء/التشكيل).
# ⛔ \uXXXX فقط داخل أصناف التعبير النمطي (فخّ الـbidi في ذاكرة المشروع).
_AR_TASHKEEL = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_AR_SPLIT = re.compile("[^0-9a-zء-ي]+")
_AR_STOP = frozenset(
    "في من على الى عن مع او ان ما ماذا كيف لماذا متى هل هو هي هذا هذه ذلك التي الذي بين بعد قبل "
    "عند كل اي لا لم لن قد ثم حتى دليل عملي عمليه خطوه بخطوه اهم اول كامل شامل جديد الجديد "
    "مصر المصري المصريه قانون القانون قانوني القانوني القانونيه محامي المحامي محامين ازاي يعني "
    "وكيف اللي مش بدل علشان".split())


def _ar_norm(s):
    s = _AR_TASHKEEL.sub("", str(s or "").lower())
    s = re.sub("[آأإٱ]", "ا", s)
    s = s.replace("ة", "ه").replace("ى", "ي")
    s = s.replace("ؤ", "و").replace("ئ", "ي")
    return s


def _ar_tokens(*texts):
    out = set()
    for t in texts:
        for w in _AR_SPLIT.split(_ar_norm(t)):
            if len(w) >= 5 and w.startswith("ال"):
                w = w[2:]
            if len(w) >= 3 and w not in _AR_STOP:
                out.add(w)
    return out


def _ar_count(n):
    """العدد مع المعدود: مقال واحد · مقالان · ٣–١٠ مقالات · ١١+ مقالًا (نفس epCount في blog.html)."""
    if n == 1:
        return "مقال واحد"
    if n == 2:
        return "مقالان"
    return ("%d %s" % (n, "مقالات" if 3 <= n % 100 <= 10 else "مقالًا")).translate(_AR_DIGITS)


def topic_url(slug):
    return ORIGIN + "/blog/topic/" + slug


def _href(a):
    return "/blog/" + urllib.parse.quote(str(a["slug"]), safe="")


def _ar_date(a):
    t = str(a.get("date") or "").strip()
    if t:
        return t
    dt = parse_cms_dt(a.get("published_at"))
    if not dt:
        return ""
    return ("%d %s %d" % (dt.day, AR_MONTHS[dt.month - 1], dt.year)).translate(_AR_DIGITS)


def _safe_http(u):
    u = str(u or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


def _pub_key(a):
    dt = parse_cms_dt(a.get("published_at"))
    return (dt.timestamp() if dt else 0.0, int(a["id"]))


def topic_groups(topics, articles):
    """[(topic, hub|None, [supports], [related standalone])] — بترتيب السجلّ. محور بلا مقال منشور يسقط."""
    by_c = {}
    for a in articles:
        if a.get("cluster_id"):
            by_c.setdefault(a["cluster_id"], []).append(a)
    # «مقالات قريبة» صارمة عمدًا: المستقلّ غالبًا خبر أو صفحة منتج، ورابطٌ غير ذي صلة على دليل
    # منسَّق أسوأ من لا رابط. نعدّ فقط الكلمات النادرة في المدوّنة (تظهر في ≤ ٦ مقالات) من عنوان
    # الموضوع وكلمات مقالاته المفتاحية، ونشترط ٣ تقاطعات، ونستبعد صفحات «عن المنصة».
    df = {}
    for a in articles:
        for w in _ar_tokens(a.get("title"), *(a.get("keywords") or [])):
            df[w] = df.get(w, 0) + 1
    rare = lambda toks: {w for w in toks if df.get(w, 0) <= 6}   # noqa: E731
    loose = [a for a in articles if not a.get("cluster_id") and (a.get("cat") or "") != "عن المنصة"]
    out, seen = [], set()
    for t in topics:
        if not isinstance(t, dict):
            continue
        slug, cid = str(t.get("slug") or ""), t.get("cluster_id")
        if not TOPIC_SLUG_RE.match(slug) or slug in seen or not t.get("label"):
            if slug and not TOPIC_SLUG_RE.match(slug):
                log("WARN: topic %r has a non-ASCII/invalid slug %r — skipped" % (cid, slug))
            continue
        members = by_c.get(cid) or []
        if not members:
            continue
        seen.add(slug)
        hubs = [a for a in members if (a.get("role") or "") == "hub"]
        hubs.sort(key=lambda a: (str(a["id"]) != str(t.get("hub_id") or ""), _pub_key(a)))
        hub = hubs[0] if hubs else None
        sups = sorted((a for a in members if a is not hub), key=_pub_key)
        mine = rare(_ar_tokens(t.get("label"), *[m.get("primary_kw") or "" for m in members],
                               *[k for m in members for k in (m.get("keywords") or [])]))
        scored = []
        for a in loose:
            sc = len(mine & rare(_ar_tokens(a.get("title"), *(a.get("keywords") or []))))
            if sc >= 3:
                scored.append((sc, _pub_key(a), a))
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        out.append((t, hub, sups, [a for _s, _k, a in scored[:3]]))
    return out


def _icons(blog_code):
    ele = re.search(r"var ELE='([^']*)';", blog_code)
    bell = re.search(r"var BELL='([^']*)';", blog_code)
    return (ele.group(1) if ele else ""), (bell.group(1) if bell else "")


def _card(a, i, ele, bell):
    tone = a.get("tone") if a.get("tone") in TONES else TONES[i % 6]
    img = _safe_http(a.get("image_url"))
    inner = ('<img class="thumb-img" loading="lazy" alt="%s" src="%s">' % (esc_attr(a["title"]), esc_attr(img))
             if img else ele)
    return ('<a class="post" href="%s"><div class="thumb %s">%s<span class="badge">%s</span></div>'
            '<div class="body"><div class="meta"><span class="cat">%s</span>·<span>%s</span></div>'
            '<h3>%s</h3><p>%s</p><div class="by">%s%s</div></div></a>'
            % (esc_attr(_href(a)), tone, inner, esc_text(a.get("cat") or ""),
               esc_text(a.get("kicker") or "مقال"), esc_text(_ar_date(a)),
               esc_text(a["title"]), esc_text(a.get("excerpt") or ""), bell, esc_text(a.get("by") or "")))


def _feat(a, ele, bell):
    tone = a.get("tone") if a.get("tone") in TONES else "t1"
    img = _safe_http(a.get("image_url"))
    inner = ('<img class="ft-img" loading="lazy" alt="%s" src="%s">' % (esc_attr(a["title"]), esc_attr(img))
             if img else ele)
    return ('<a class="feat" href="%s"><div class="ft-thumb %s">%s</div><div class="ft-body">'
            '<div class="ft-tag">دليل الموضوع — ابدأ من هنا</div><h2>%s</h2><p>%s</p>'
            '<div class="ft-meta"><span class="ft-by">%s%s</span>·<span>%s</span></div></div></a>'
            % (esc_attr(_href(a)), tone, inner, esc_text(a["title"]), esc_text(a.get("excerpt") or ""),
               bell, esc_text(a.get("by") or ""), esc_text(_ar_date(a))))


TOPIC_CSS = """<style id="epTopicCss">
.tp-desc{font-size:17px;color:var(--ink-2);margin-top:16px;max-width:680px;line-height:1.8}
.tp-count{display:inline-block;margin-top:16px;font-size:13px;font-weight:800;color:var(--human);background:var(--human-bg);border-radius:999px;padding:4px 16px}
.tp-main{padding:32px 0 48px}
.tp-h2{font-family:Cairo,'IBM Plex Sans Arabic',sans-serif;font-size:20px;font-weight:800;color:var(--ink);margin:8px 0 24px;line-height:1.5}
.tp-h2 span{color:var(--muted);font-weight:700;font-size:15px}
.tp-main .bgrid{padding-bottom:32px}
.tp-more{border-top:1px solid var(--line);padding-top:32px;margin-top:8px}
.tp-more ul{list-style:none;display:flex;flex-wrap:wrap;gap:8px}
.tp-more a{display:inline-flex;align-items:center;min-height:44px;font-size:14px;font-weight:700;border:1.5px solid var(--line);background:var(--surface);border-radius:999px;padding:8px 16px;color:var(--ink-2)}
.tp-more a:hover{border-color:var(--human);color:var(--human)}
.tp-back{margin-top:32px}
.tp-back a{display:inline-flex;align-items:center;min-height:44px;font-weight:800;color:var(--human)}
@media(max-width:760px){.tp-desc{font-size:16px}.tp-main{padding:24px 0 32px}}
</style>"""

_REL_URL = re.compile(r'\b(href|src)="(?!/|#|https?:|mailto:|tel:|data:|javascript:)([^"]+)"')


def _script_open_tags(doc):
    """متن الصفحة خارج السكربتات + الوسوم الافتتاحية للسكربتات (فيها src) — ما يجب أن يكون مطلقًا."""
    parts = re.split(r"(?is)(<script\b.*?</script>)", doc)
    return "".join(p[:p.find(">") + 1] if p[:7].lower() == "<script" else p for p in parts)


def _absolutize(doc):
    """مسارات نسبية ⇒ مطلقة: في كل الوسوم، وفي الوسم الافتتاحي لـ<script src=…> (pixel.js نسبي في
    القالب!) — أمّا متن السكربتات الداخلية فلا نلمسه."""
    parts = re.split(r"(?is)(<script\b.*?</script>)", doc)
    out = []
    for p in parts:
        if p[:7].lower() == "<script":
            k = p.find(">") + 1
            out.append(_REL_URL.sub(r'\1="/\2"', p[:k]) + p[k:])
        else:
            out.append(_REL_URL.sub(r'\1="/\2"', p))
    return "".join(out)


def build_topic_page(blog_doc, blog_code, topic, hub, sups, related, all_topics):
    slug, label = topic["slug"], str(topic["label"]).strip()
    desc = str(topic.get("description") or "").strip() or (
        "كل مقالات البروفيسور عن «%s» في مكان واحد: الدليل الأساسي أولًا ثم التفاصيل." % label)
    url = topic_url(slug)
    members = ([hub] if hub else []) + list(sups)
    ele, bell = _icons(blog_code)
    out = blog_doc

    def line(pattern, new, what):
        nonlocal out
        out = replace_once(out, unique_line(out, pattern, what), new, what)

    title = "%s — دليل موضوع | البروفيسور" % label
    line(r"^<title>.*</title>$", "<title>%s</title>" % esc_text(title), "title")
    line(r'^<meta name="description" content=".*">$',
         '<meta name="description" content="%s">' % esc_attr(desc[:300]), "description")
    line(r'^<link rel="canonical" href=".*">$', '<link rel="canonical" href="%s">' % esc_attr(url), "canonical")
    line(r'^<meta property="og:title" content=".*">$',
         '<meta property="og:title" content="%s">' % esc_attr(title), "og:title")
    line(r'^<meta property="og:description" content=".*">$',
         '<meta property="og:description" content="%s">' % esc_attr(desc[:300]), "og:description")
    line(r'^<meta property="og:url" content=".*">$', '<meta property="og:url" content="%s">' % esc_attr(url),
         "og:url")
    line(r'^<meta name="twitter:title" content=".*">$',
         '<meta name="twitter:title" content="%s">' % esc_attr(title), "twitter:title")
    line(r'^<meta name="twitter:description" content=".*">$',
         '<meta name="twitter:description" content="%s">' % esc_attr(desc[:300]), "twitter:description")

    items = [{"@type": "ListItem", "position": i + 1, "url": article_url(a["slug"]), "name": str(a["title"])}
             for i, a in enumerate(members)]
    coll = {"@context": "https://schema.org", "@type": "CollectionPage", "@id": url + "#page", "url": url,
            "name": label, "description": desc, "inLanguage": "ar",
            "isPartOf": {"@id": ORIGIN + "/#website"}, "about": {"@type": "Thing", "name": label},
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(items), "itemListElement": items}}
    bc = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "الرئيسية", "item": ORIGIN + "/"},
        {"@type": "ListItem", "position": 2, "name": "المقالات", "item": ORIGIN + "/blog.html"},
        {"@type": "ListItem", "position": 3, "name": label, "item": url}]}
    lds = ('<script type="application/ld+json" id="ld-topic">%s</script>\n'
           '<script type="application/ld+json" id="ld-topic-bc">%s</script>\n'
           % (esc_ldjson(coll), esc_ldjson(bc)))
    out = replace_once(out, "</script>\n<style>\n:root{", "</script>\n" + lds + "<style>\n:root{", "ld-insert")
    out = replace_once(out, "</head>", TOPIC_CSS + "\n</head>", "head-close")

    # الهيرو: فتات المسار + H1 + الوصف
    out = replace_once(out, '<div class="crumbs"><a href="/">الرئيسية</a> · المقالات</div>',
                       '<nav class="crumbs" aria-label="مسار التنقّل"><a href="/">الرئيسية</a> · '
                       '<a href="/blog.html">المقالات</a> · <span aria-current="page">%s</span></nav>'
                       % esc_text(label), "hero-crumbs")
    h1 = unique_line(out, r"^\s*<h1>.*</h1>$", "hero-h1")
    indent = h1[:len(h1) - len(h1.lstrip())]
    out = replace_once(out, h1, '%s<h1>%s</h1>\n%s<p class="tp-desc">%s</p>\n%s<span class="tp-count">%s</span>'
                       % (indent, esc_text(label), indent, esc_text(desc), indent,
                          esc_text(_ar_count(len(members)) + " في هذا الموضوع")),
                       "hero-h1")

    # المحتوى: من «FILTERS + CONTENT» حتى «CTA»
    sec = ['<section class="wrap tp-main" id="topicMain">']
    if hub:
        sec.append(_feat(hub, ele, bell))
    if sups:
        sec.append('<h2 class="tp-h2">%s <span>(%s)</span></h2>'
                   % ("تفاصيل في هذا الموضوع" if hub else "مقالات هذا الموضوع",
                      str(len(sups)).translate(_AR_DIGITS)))
        sec.append('<div class="bgrid">' + "".join(_card(a, i, ele, bell) for i, a in enumerate(sups)) + "</div>")
    if related:
        sec.append('<h2 class="tp-h2">مقالات قريبة من الموضوع</h2>')
        sec.append('<div class="bgrid">' + "".join(_card(a, i + 3, ele, bell) for i, a in enumerate(related))
                   + "</div>")
    others = [t for t in all_topics if t["slug"] != slug]
    if others:
        sec.append('<nav class="tp-more" aria-label="موضوعات أخرى"><h2 class="tp-h2">موضوعات أخرى</h2><ul>'
                   + "".join('<li><a href="/blog/topic/%s">%s</a></li>' % (esc_attr(t["slug"]), esc_text(t["label"]))
                             for t in others) + "</ul></nav>")
    sec.append('<p class="tp-back"><a href="/blog.html">← كل المقالات</a></p></section>')
    i = out.find("<!-- FILTERS + CONTENT -->")
    j = out.find("<!-- CTA -->")
    if i < 0 or j <= i or out.count("<!-- FILTERS + CONTENT -->") != 1 or out.count("<!-- CTA -->") != 1:
        raise Fail("topic page: blog.html content anchors (FILTERS + CONTENT / CTA) not found exactly once")
    out = out[:i] + "<!-- TOPIC: %s -->\n" % slug + "\n".join(sec) + "\n\n" + out[j:]

    # مُصيِّر المدوّنة لا مكان له هنا (لا #grid ولا #filters) — نشيله مع علَمه ومحمّل الفيد
    pat = (r'(?s)(?:<script>window\.EP_PRERENDERED=true;</script>\n)?<script src="site-content\.js[^"]*">'
           r'</script>\n<script>\nvar ELE=.*?</script>\n<script src="content-loader\.js[^"]*"></script>\n?')
    found = re.findall(pat, out)
    if len(found) != 1:
        raise Fail("topic page: blog renderer block matched %d times (expected 1)" % len(found))
    out = out.replace(found[0], "", 1)
    return _absolutize(out), {"url": url, "members": members, "related": related, "label": label}


def verify_topic_page(html, topic, meta):
    errs = []
    slug = topic["slug"]

    def bad(m):
        errs.append("topic=%s: %s" % (slug, m))

    h1s = re.findall(r"<h1>(.*?)</h1>", html)
    if len(h1s) != 1 or h1s[0] != esc_text(meta["label"]):
        bad("H1 is %r (expected exactly one = the topic label)" % h1s)
    if html.count('<link rel="canonical"') != 1 or ('<link rel="canonical" href="%s">' % meta["url"]) not in html:
        bad("canonical missing/duplicated or not %s" % meta["url"])
    for a in meta["members"] + meta["related"]:
        if ('href="%s"' % esc_attr(_href(a))) not in html:
            bad("member article id=%s has no link on the page" % a["id"])
    ids = re.findall(r'<script type="application/ld\+json" id="([^"]+)"', html)
    for need in ("ld-topic", "ld-topic-bc"):
        if ids.count(need) != 1:
            bad("%s block count != 1" % need)
    for m in re.finditer(r'(?s)<script type="application/ld\+json"[^>]*>(.*?)</script>', html):
        try:
            json.loads(m.group(1))
        except Exception as exc:                # noqa: BLE001
            bad("a JSON-LD block does not parse: %s" % exc)
    if html.count(GTM_ID) != 2:
        bad("%s count != 2" % GTM_ID)
    if html.count("pixel.js?v=") != 1:
        bad("pixel.js count != 1")
    for leak in ("content-loader.js", "var ELE=", "EP_RENDER", 'id="grid"', 'id="filters"'):
        if leak in html:
            bad("blog renderer leftover %r on a static topic page" % leak)
    rel = _REL_URL.findall(_script_open_tags(html))
    if rel:
        bad("relative URL(s) on a /blog/topic/ page (404 there): %r" % rel[:3])
    if len(strip_to_text(html)) < 400:
        bad("stripped text too short")
    return errs


def build_topics_dir(topics, groups):
    """فهرس ثابت لروابط صفحات الموضوعات داخل blog.html — الزاحف يصلها من صفحة المقالات."""
    if not groups:
        return ""
    return ('<h2 class="tdir-h">تصفّح حسب الموضوع</h2><ul class="tdir-list">'
            + "".join('<li><a href="/blog/topic/%s">%s</a></li>' % (esc_attr(t["slug"]), esc_text(t["label"]))
                      for t, _h, _s, _r in groups) + "</ul>")


# ---------------------------------------------------------------------------
# الكتابة
# ---------------------------------------------------------------------------
FILE_MODE = 0o644        # محتوى ويب: لا بد أن يقرأه مستخدم الخادم


def write_atomic(path, text):
    """يكتب فقط عند اختلاف المحتوى (فيبقى التشغيل المتكرر بلا أثر على القرص).
    الصلاحيات مقصودة: mkstemp يُنشئ الملف بـ0600، ولو تُرك هكذا لشُحنت ٧٢ صفحة
    لا يستطيع خادم الويب قراءتها (403) — ولنُقلت الصلاحية مع الـtar إلى الإنتاج."""
    data = text.encode("utf-8")                 # UTF-8 بلا BOM
    mode = FILE_MODE
    if os.path.exists(path):
        st = os.stat(path)
        mode = stat.S_IMODE(st.st_mode)         # لا نغيّر صلاحية ملف قائم
        with open(path, "rb") as fh:
            if fh.read() == data:
                return False
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d or ".", prefix=".ep-tmp-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


# ---------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(
        description="Prerender elprofessor.net articles for crawlers that do not run JS.")
    p.add_argument("--site", default=os.environ.get("EP_SITE_DIR"),
                   help="جذر الموقع (يحوي article.html و blog.html) أو متغيّر EP_SITE_DIR")
    p.add_argument("--id", action="append", default=None,
                   help="اكتب ملف هذا المقال فقط (يُكرَّر). بدونه: كل المقالات")
    p.add_argument("--feed-file", default=None, help="ملف JSON بدل الشبكة (اختبار/بلا اتصال)")
    p.add_argument("--feed-url", default=FEED_URL)
    p.add_argument("--min-articles", type=int, default=MIN_ARTICLES)
    p.add_argument("--rss-limit", type=int, default=0, help="0 = كل المقالات")
    p.add_argument("--feed-name", default="feed.xml",
                   help="اسم ملف الـRSS في جذر الموقع — لا بد أن يطابق ما تعلنه "
                        "وسوم <link rel=alternate> في article.html و blog.html")
    p.add_argument("--dry-run", action="store_true", help="تحقّق واطبع، بلا كتابة")
    p.add_argument("--no-prune", action="store_true",
                   help="لا تحذف ملفات _pre لمقالات لم تعد منشورة")
    args = p.parse_args(argv)

    if not args.site:
        raise Fail("--site is required (or set EP_SITE_DIR)")
    site = os.path.abspath(args.site)
    art_tpl_path = os.path.join(site, "article.html")
    blog_path = os.path.join(site, "blog.html")
    pre_dir = os.path.join(site, "blog", "_pre")
    for f in (art_tpl_path, blog_path):
        if not os.path.isfile(f):
            raise Fail("not found: %s (is --site the web root?)" % f)

    with open(art_tpl_path, encoding="utf-8") as fh:
        art_tpl = fh.read()
    with open(blog_path, encoding="utf-8") as fh:
        blog_doc = fh.read()
    if "\r" in art_tpl or "\r" in blog_doc:
        raise Fail("template has CRLF line endings; the anchors assume LF")

    # الصندوق يُنسخ من القالب. غيابه ليس عطلًا قاتلًا، لكنه يمرّ صامتًا على ١٤٠
    # صفحة ولا يلاحظه أحد — فنقوله بصوت مسموع في السجل وفي مخرجات التشغيل.
    lm_in_tpl = art_tpl.count(LEAD_MAGNET_HONEYPOT)
    if lm_in_tpl == 0 and LEAD_MAGNET_URL not in art_tpl:
        log("WARN: article.html has no lead-magnet box (no POST to %s) — every prerendered "
            "page will ship without it. Deploy the site template first, then push."
            % LEAD_MAGNET_URL)
    elif lm_in_tpl != 1:
        log("WARN: article.html has a lead-magnet box but %d honeypot field(s) named %s "
            "(expected 1) — verification will fail" % (lm_in_tpl, LEAD_MAGNET_HONEYPOT))

    article_code = extract_inline(art_tpl, '</script>\n<script src="/content-loader.js',
                                  "article.html")
    blog_code = extract_inline(blog_doc, '</script>\n<script src="content-loader.js', "blog.html")

    # كل السلاسل العربية في التحقق مأخوذة من المصدر، لا مكتوبة يدويًّا
    soft404 = re.search(r"var nfTitle=DATA\.length\?'([^']*)':'([^']*)'", article_code)
    ctx = {
        "renderer_has_faq": "faqHtml" in article_code,
        "renderer_has_topic": "topic_slug" in article_code,
        "soft404": list(soft404.groups()) if soft404 else [],
        "placeholder": unique_line(art_tpl, r"^<title>.*</title>$", "title")[len("<title>"):-len("</title>")],
    }
    if not ctx["soft404"]:
        log("warn: could not locate the soft-404 titles in article.html; that check is off")
    log("renderer: article inline script %d chars, visible FAQ rendering %s"
        % (len(article_code), "ON" if ctx["renderer_has_faq"] else "OFF (JSON-LD only)"))

    articles, source, feed_topics = fetch_feed(args.feed_file, args.feed_url, args.min_articles)
    by_id = {str(a["id"]): a for a in articles}

    if args.id:
        write_ids = [str(i).strip() for i in args.id]
        missing = [t for t in write_ids if t not in by_id]
        if missing:
            raise Fail("id(s) %s are not in the published feed (unpublished, or wrong id). "
                       "Nothing written. Run without --id to prune them." % missing)
    else:
        write_ids = [str(a["id"]) for a in articles]

    t0 = time.time()
    res = run_node(article_code, blog_code, articles, source or "")
    log("render: %d article(s) + the index in %.1fs" % (len(res["articles"]), time.time() - t0))

    # نُصيّر ونتحقق من الجميع دائمًا؛ --id يحصر ما يُكتب فقط.
    pending, errors, lengths = {}, [], {}
    for a in articles:
        aid = str(a["id"])
        r = res["articles"].get(aid)
        if not r:
            raise Fail("renderer returned nothing for id=%s" % aid)
        html, meta = build_article(art_tpl, a, r)
        errs, textlen = verify_article(html, a, r, meta, ctx)
        errors.extend(errs)
        lengths[aid] = textlen
        if aid in write_ids:
            pending[os.path.join(pre_dir, "%s.html" % aid)] = html

    # صفحات الموضوعات — فشلها لا يُسقط المقالات (انظر التعليق عند TOPIC_DIR)
    topic_dir = os.path.join(site, "blog", TOPIC_DIR)
    topic_pages, topics_error, groups = {}, None, []
    try:
        groups = topic_groups(feed_topics, articles)
        all_t = [g[0] for g in groups]
        for t, hub, sups, rel in groups:
            thtml, tmeta = build_topic_page(blog_doc, blog_code, t, hub, sups, rel, all_t)
            terrs = verify_topic_page(thtml, t, tmeta)
            if terrs:
                raise Fail("; ".join(terrs[:6]))
            topic_pages[os.path.join(topic_dir, t["slug"] + ".html")] = thtml
    except Fail as exc:
        topics_error = str(exc)[:600]
        topic_pages, groups = {}, []
        log("WARN: topic pages skipped (articles unaffected): %s" % topics_error)
    if feed_topics and not groups and not topics_error:
        log("WARN: the feed carries %d topic(s) but none has a published article" % len(feed_topics))

    blog_html = build_blog(blog_doc, res["blog"])
    if MARK_TOPICS_OPEN in blog_html and groups:
        if blog_html.count(MARK_TOPICS_OPEN) != 1 or blog_html.count(MARK_TOPICS_CLOSE) != 1:
            raise Fail("blog.html markers %s are not unique" % MARK_TOPICS_OPEN)
        ti = blog_html.index(MARK_TOPICS_OPEN) + len(MARK_TOPICS_OPEN)
        tj = blog_html.index(MARK_TOPICS_CLOSE, ti)
        blog_html = blog_html[:ti] + "\n" + build_topics_dir(feed_topics, groups) + "\n" + blog_html[tj:]
    berrs, blog_len = verify_blog(blog_html, articles)
    errors.extend(berrs)
    pending[blog_path] = blog_html
    pending.update(topic_pages)

    feed_url = ORIGIN + "/" + args.feed_name.lstrip("/")
    rss = build_rss(articles, res["articles"], blog_doc, feed_url, args.rss_limit)
    pending[os.path.join(site, args.feed_name.lstrip("/"))] = rss

    # رابط تغذية معلَن لا يوجد له ملف = رابط ميّت. نكشفه بدل أن يُشحن صامتًا.
    declared = set()
    for name, doc in (("article.html", art_tpl), ("blog.html", blog_html)):
        for m in re.finditer(r'<link[^>]+rel="alternate"[^>]*>', doc):
            h = re.search(r'href="([^"]+)"', m.group(0))
            if h and "rss+xml" in m.group(0):
                declared.add((name, h.group(1)))
    mismatch = sorted("%s -> %s" % (n, h) for n, h in declared if h.rstrip("/") != feed_url)
    for d in mismatch:
        log("WARN: declared RSS link does not match the generated feed (%s): %s" % (feed_url, d))
    pending[os.path.join(pre_dir, "manifest.txt")] = (
        "\n".join(sorted((str(a["id"]) for a in articles), key=int)) + "\n")

    if errors:
        for e in errors[:40]:
            log("VERIFY FAIL: " + e)
        raise Fail("%d verification failure(s) — NOTHING was written" % len(errors))

    stale = []
    if os.path.isdir(pre_dir) and not args.no_prune:
        for name in sorted(os.listdir(pre_dir)):
            if name.endswith(".html") and name[:-5] not in by_id:
                stale.append(os.path.join(pre_dir, name))
    # موضوع اختفى من السجلّ (أو فقد آخر مقالاته المنشورة) ⇒ صفحته تُمسح. توليدٌ بلا أي صفحة = لا مسح.
    if topic_pages and os.path.isdir(topic_dir) and not args.no_prune:
        for name in sorted(os.listdir(topic_dir)):
            pth = os.path.join(topic_dir, name)
            if TOPIC_PAGE_RE.match(name) and pth not in topic_pages:
                stale.append(pth)

    if args.dry_run:
        log("DRY RUN — would write %d file(s), prune %d stale" % (len(pending), len(stale)))
    else:
        changed = sum(1 for pth, txt in sorted(pending.items()) if write_atomic(pth, txt))
        for pth in stale:
            os.unlink(pth)
        log("wrote %d file(s) (%d unchanged), pruned %d stale"
            % (changed, len(pending) - changed, len(stale)))

    vals = sorted(lengths.values())
    print(json.dumps({
        "articles": len(articles),
        "files_written": len(pending),
        "text_chars_min": vals[0],
        "text_chars_median": vals[len(vals) // 2],
        "text_chars_max": vals[-1],
        "blog_text_chars": blog_len,
        "rss_bytes": len(rss.encode("utf-8")),
        "faq_rendered_visibly": ctx["renderer_has_faq"],
        "lead_magnet_per_page": lm_in_tpl,
        "pruned": len(stale),
        "topics": sorted(os.path.basename(p)[:-5] for p in topic_pages),
        "topics_error": topics_error,
        "feed_url": feed_url,
        "feed_link_mismatch": mismatch,
        "dry_run": bool(args.dry_run),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fail as e:
        log("FATAL: %s" % e)
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
