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
    return articles, (data.get("source") or "")


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

    # 8) المتن + المقالات ذات الصلة
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

    txt = strip_to_text(html)
    if len(txt) < 1500:
        bad("script/style-stripped text is only %d chars" % len(txt))

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

    article_code = extract_inline(art_tpl, '</script>\n<script src="/content-loader.js',
                                  "article.html")
    blog_code = extract_inline(blog_doc, '</script>\n<script src="content-loader.js', "blog.html")

    # كل السلاسل العربية في التحقق مأخوذة من المصدر، لا مكتوبة يدويًّا
    soft404 = re.search(r"var nfTitle=DATA\.length\?'([^']*)':'([^']*)'", article_code)
    ctx = {
        "renderer_has_faq": "faqHtml" in article_code,
        "soft404": list(soft404.groups()) if soft404 else [],
        "placeholder": unique_line(art_tpl, r"^<title>.*</title>$", "title")[len("<title>"):-len("</title>")],
    }
    if not ctx["soft404"]:
        log("warn: could not locate the soft-404 titles in article.html; that check is off")
    log("renderer: article inline script %d chars, visible FAQ rendering %s"
        % (len(article_code), "ON" if ctx["renderer_has_faq"] else "OFF (JSON-LD only)"))

    articles, source = fetch_feed(args.feed_file, args.feed_url, args.min_articles)
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

    blog_html = build_blog(blog_doc, res["blog"])
    berrs, blog_len = verify_blog(blog_html, articles)
    errors.extend(berrs)
    pending[blog_path] = blog_html

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
        "pruned": len(stale),
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
