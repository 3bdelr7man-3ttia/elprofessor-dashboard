# -*- coding: utf-8 -*-
"""«كتبنا وأدلّتنا» من الداشبورد — مسارات `/api/v2/books/ours/*` و`/api/v2/books/guide-codes` (docs/v2/books-ours/SPEC.md).

بروكسيات رفيعة فوق جسور المنصة `/api/bridge/books/ours` و`/api/bridge/guides/codes`. نفس قواعد `v2_courses2_routes.py`:
  * أدمن بس + المفتاح (`DASH_V2_ENABLED`) مفتوح، وإلا ٤٠٤ قبل أي رحلة للمنصة. `Cache-Control: no-store` على كل رد.
  * كل كتابة على المنصة تطلب `confirmed: true` بالظبط من المتصفح (في الرفع: حقل `confirmed=true` في النموذج)، وإلا ٤٠٠ قبل أي نداء.
    الجسم المبعوت للمنصة من قايمة بيضا بالحقول، و`by` من التوكن وحده (اللي في جسم المتصفح بيتجاهل)، و`confirmed:true` بيتحط هنا للجسر.
  * ⛔ ولا سعر من هنا أبدًا: أي مفتاح `price*` / `pricing` / `versions` / `is_free` / نسبة بيتشال من الجسم. السعر من مسار الأسعار الموجود وفورمه بس.
  * ⛔ نداء واحد ولا إعادة محاولة. رد ضاع (٥٠٠/٥٠٢/٥٠٣/٥٠٤) على كتابة ⇒ ٥٠٢ و`no_reply:true` بنص «لم يصل رد…»،
    مش «اترفض». نص `detail` العربي من المنصة بيوصل كما هو في `error` بنفس الكود (٤٠٠ · ٤٠٤ · ٤٠٩ · ٤١٣ · ٤٢٢).
  * تدقيق عند النجاح بس باسم `book_ours.<إجراء>` أو `guide_codes.update` وبما **حدث** (مفاتيح وأعداد لا محتوى).
  * رفع الملف: المتصفح يرسل multipart؛ هنا نتأكد إنه PDF فعلًا (الامتداد وأول `%PDF-`) وإنه تحت السقف قبل ما نبعت للمنصة.

«العقل يكتب الكتاب» (القسم ب في المواصفة):
  * `POST .../brain/draft` ⇒ نداء كاتب واحد (`brain2.engine`: الكاتب الحالي بمفتاحه، وسقوف العقل اليومية) يكتب مسودة `{title, about, chapters}`
    تتحفظ في جدول الداشبورد `v2_books_ours_drafts` ويعدّلها المؤسس. ⛔ مفيش أي كتابة على المنصة من هنا.
  * `POST .../brain/pdf` ⇒ يحوّل المسودة المحفوظة لـPDF عربي RTL بهوية البروفيسور ثم يرفعه بنفس مسار الرفع (يطلب `confirmed:true`).
    مكتبة weasyprint بتتحمّل كسول جوه الدالة: غيابها ⇒ رسالة عربية واضحة والسيرفر ما يقعش.

`register(app, g)` بتتنادى من app.py بسطر واحد، و`g` = globals() بتاعته (الديكوريترز والمساعدات والموديلات).
"""
import datetime
import html as _html
import json
import os
import re
from urllib.parse import quote

NO_REPLY_AR = 'لم يصل رد. حدّث الصفحة وتأكّد مما حدث قبل أن تضغط مرة أخرى.'
BAD_ID_AR = 'معرّف غير صالح'
TITLE_MAX = 160
ABOUT_MAX = 2000
TYPES = ('book', 'guide', 'research', 'other')
IDEM_RE = re.compile(r'^[A-Za-z0-9_.:-]{8,80}$')
CODE_RE = re.compile(r'^[a-z0-9_-]{3,40}$')
CODES_MAX = 200
NOTE_MAX = 200

BASE = '/api/bridge/books/ours'
CODES_PATH = '/api/bridge/guides/codes'

# ⛔ مفاتيح السعر والنسبة: تُشال من أول مستوى في أي جسم (ومش بنبعتها للجسر أصلًا).
_MONEY_EXACT = {'pricing', 'versions', 'visible', 'is_free', 'trainer_share_pct', 'share_pct', 'owner_pct', 'platform_pct', 'commission', 'amount', 'currency'}

BOOK_FIELDS = ('id', 'slug', 'title', 'about', 'type', 'status', 'author', 'free', 'created_by', 'created_at', 'updated_at')
AUTHOR_MAX = 200
FILE_FIELDS = ('name', 'size', 'pages', 'uploaded', 'uploaded_at')
CODE_FIELDS = ('code', 'note', 'max_uses', 'active', 'uses')

UPLOAD_MAX_MB_DEFAULT = 50
PDF_NEEDS_AR = 'ارفع ملف PDF فقط'
PDF_BAD_AR = 'هذا الملف ليس PDF سليمًا. اختر ملف PDF آخر'
PDF_EMPTY_AR = 'الملف فارغ'
PDF_NONE_AR = 'اختر ملف PDF أولًا'

# ---- العقل
DRAFT_STALE_MIN = 6
INSTRUCTION_MAX = 2000
OUTLINE_MAX = 3000
CHAPTERS_MAX = 12
CHAPTER_TITLE_MAX = 120
CHAPTER_BODY_MAX = 8000
ERR_WRITING_AR = 'العقل يكتب الآن. جرّب بعد قليل'
ERR_OFF_AR = 'كتابة العقل متوقّفة الآن'
ERR_NO_WRITER_AR = 'لا يوجد كاتب متاح الآن'
ERR_CAP_AR = 'وصل العقل لحدّه اليومي. يعود غدًا'
ERR_FAILED_AR = 'تعذّرت الكتابة الآن. حاول بعد قليل'
ERR_INVALID_AR = 'جاء المكتوب غير صالح فلم يُحفظ. غيّر التعليمات وحاول مرة أخرى'
ERR_NO_DRAFT_AR = 'اكتب المسودة أولًا'
ERR_DRAFT_SHAPE_AR = 'المسودة ناقصة: اكتب عنوانًا وفصلًا واحدًا على الأقل، ولكل فصل عنوان ونص'
ERR_PDF_OFF_AR = 'إنشاء ملف PDF غير متاح على الخادم الآن'
ERR_PDF_FAIL_AR = 'تعذّر إنشاء ملف PDF الآن'

BOOK_RULES_AR = (
    'أنت تكتب مسودة كتاب أو دليل لمنصة «البروفيسور». القواعد: عربية فصحى بسيطة، بصيغة محايدة لا تخاطب مذكرًا ولا مؤنثًا، لجمهور دولي، '
    'بلا مصطلحات تقنية. لا تذكر مصدرًا ولا اقتباسًا ولا رقم مادة قانونية ولا إحصاءً ولا تاريخًا إلا إذا ورد في التعليمات نفسها. '
    'لا تستعمل أرقامًا ولا كلمات لاتينية إلا إذا وردت في التعليمات. لا تبدأ أي عنوان بكلمة «الذكاء»، ولا تذكر أن النص كتبه برنامج. '
    'لا ترقّم عناوين الفصول. اجعل لكل فصل فكرة واحدة واضحة، وفقراته قصيرة تفصلها سطور فارغة.')
BOOK_SHAPE_AR = (
    'أعد JSON صالحًا فقط بالشكل: {"title": "عنوان الكتاب", "about": "نبذة من جملتين أو ثلاث", '
    '"chapters": [{"title": "عنوان الفصل", "body": "نص الفصل"}]}. '
    'من ٤ إلى ٨ فصول، ونص كل فصل بين ١٥٠ و٣٠٠ كلمة.')


def strip_money(body):
    """نسخة من الجسم بلا أي مفتاح سعر/نسبة في المستوى الأول (حساس لحالة الحروف)."""
    out = {}
    for k, v in (body or {}).items():
        lk = str(k).lower()
        if lk.startswith('price') or lk in _MONEY_EXACT:
            continue
        out[k] = v
    return out


def _clip(s, n):
    return s.strip()[:n] if isinstance(s, str) else ''


def upload_cap_bytes():
    try:
        mb = int((os.environ.get('BOOKS_UPLOAD_MAX_MB') or '').strip() or UPLOAD_MAX_MB_DEFAULT)
    except (TypeError, ValueError):
        mb = UPLOAD_MAX_MB_DEFAULT
    return max(1, mb) * 1024 * 1024


def too_big_ar(cap):
    mb = str(cap // (1024 * 1024)).translate(str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩'))
    return 'الملف أكبر من الحدّ المسموح (%s ميغا)' % mb


def check_pdf(filename, data):
    """(None | رسالة عربية). الامتداد `.pdf` وأول الملف `%PDF-` وغير فارغ."""
    name = (filename or '').strip().lower()
    if not name.endswith('.pdf'):
        return PDF_NEEDS_AR
    if not data:
        return PDF_EMPTY_AR
    if not data.startswith(b'%PDF-'):
        return PDF_BAD_AR
    return None


def safe_filename(name):
    base = re.split(r'[\\/]', name or '')[-1]
    base = re.sub(r'[\x00-\x1f\x7f"<>|:*?]', '', base).strip()
    if not base.lower().endswith('.pdf'):
        base += '.pdf'
    return base[-120:] if len(base) > 120 else base


def view_book(b):
    """كتاب واحد من رد المنصة ⇒ القايمة البيضا بس (الملف بحقوله الخمسة، أو None)."""
    if not isinstance(b, dict):
        return None
    out = {k: b[k] for k in BOOK_FIELDS if k in b}
    f = b.get('file')
    out['file'] = {k: f[k] for k in FILE_FIELDS if k in f} if isinstance(f, dict) else None
    return out


def view_codes(d):
    if not isinstance(d, dict) or not isinstance(d.get('codes'), list):
        return None
    codes = [{k: c[k] for k in CODE_FIELDS if k in c} for c in d['codes'] if isinstance(c, dict)]
    out = {'codes': codes}
    for k in ('version', 'updated_at', 'updated_by'):
        if k in d:
            out[k] = d[k]
    return out


# ------------------------------------------------------------------ المسودة: التحقق (نقي)

def _norm(g_engine, s):
    return g_engine.norm_digits(s) if isinstance(s, str) else ''


def validate_draft(data, engine, source_text=None):
    """(مسودة نظيفة | None، رمز العلّة | None).
    الرفض الصارم: الشكل والحدود · «يقوّم» · عنوان يبدأ بالذكاء/AI (والأخيرة بس لمسودة العقل `source_text is not None`).
    ⛔ الأرقام والكلمات اللاتينية ما بتترفضش (كتاب قانون فيه أرقام مواد وسنين وأسماء قوانين): بتتعلّم بـ`review_marks` (تحت)."""
    if not isinstance(data, dict):
        return None, 'shape'
    title = engine.clean_text(data.get('title'), keep_newlines=False)
    about = engine.clean_text(data.get('about'), keep_newlines=True) if data.get('about') is not None else ''
    chapters = data.get('chapters')
    if not title or len(title) > TITLE_MAX or len(about) > ABOUT_MAX or not isinstance(chapters, list) or not 1 <= len(chapters) <= CHAPTERS_MAX:
        return None, 'shape'
    out = []
    for c in chapters:
        if not isinstance(c, dict):
            return None, 'shape'
        ct = engine.clean_text(c.get('title'), keep_newlines=False)
        cb = engine.clean_text(c.get('body'), keep_newlines=True)
        if not ct or not cb or len(ct) > CHAPTER_TITLE_MAX or len(cb) > CHAPTER_BODY_MAX:
            return None, 'shape'
        out.append({'title': ct, 'body': cb})
    clean = {'title': title, 'about': about, 'chapters': out}
    strings = [title, about] + [x for c in out for x in (c['title'], c['body'])]
    if any(engine.has_banned(s) for s in strings):
        return None, 'banned'
    if source_text is not None and any(engine._AI_START_RE.match(t) for t in [title] + [c['title'] for c in out]):
        return None, 'lead'
    return clean, None


def _tokens_in(engine, text):
    """(الرمز كما كُتب) لكل رقم أو كلمة لاتينية في النص. الأرقام العربية تُقارَن بصيغتها اللاتينية لكن يُرجَع النص الأصلي."""
    n = _norm(engine, text)
    out = []
    for rx in (engine._DIGITS_RE, engine._LATIN_RE):
        for m in rx.finditer(n):
            out.append((m.start(), text[m.start():m.end()], m.group(0)))
    out.sort()
    return out


def review_marks(draft, engine, source_text):
    """[{chapter_index, token}] لكل رقم/كلمة لاتينية في المسودة مش موجودة في التعليمات. chapter_index = ‏-١ للعنوان والنبذة. بلا تكرار داخل الفصل الواحد."""
    src = _norm(engine, source_text or '')
    src_lower = src.lower()
    marks, seen = [], set()
    fields = [(-1, draft.get('title', '')), (-1, draft.get('about', ''))]
    for i, c in enumerate(draft.get('chapters') or []):
        fields += [(i, c.get('title', '')), (i, c.get('body', ''))]
    for idx, text in fields:
        for _pos, tok, norm in _tokens_in(engine, text):
            known = (norm in src) if norm.isdigit() else (norm.lower() in src_lower)
            if known or (idx, tok) in seen:
                continue
            seen.add((idx, tok))
            marks.append({'chapter_index': idx, 'token': tok})
    return marks


def remap_marks(draft, tokens):
    """بعد تعديل المؤسس: كل رمز كان معلَّمًا يبقى معلَّمًا ما دام موجودًا في النص (الفصل الذي هو فيه الآن)."""
    marks = []
    for tok in tokens:
        if draft.get('title', '').find(tok) >= 0 or draft.get('about', '').find(tok) >= 0:
            marks.append({'chapter_index': -1, 'token': tok})
        for i, c in enumerate(draft.get('chapters') or []):
            if tok in c.get('title', '') or tok in c.get('body', ''):
                marks.append({'chapter_index': i, 'token': tok})
    return marks


def draft_prompt(instruction, outline):
    user = 'التعليمات:\n%s\n' % instruction
    if outline:
        user += '\nالمخطّط المطلوب:\n%s\n' % outline
    return user


def norm_outline(v):
    """المخطّط نصًّا أو قايمة سطور ⇒ نص بسطر لكل بند (حتى ٢٠ سطرًا)، وإلا ''."""
    if isinstance(v, list):
        v = '\n'.join(str(x) for x in v if isinstance(x, (str, int)))
    if not isinstance(v, str):
        return ''
    lines = [l.strip() for l in v.replace('\r', '').split('\n') if l.strip()][:20]
    return '\n'.join(lines)[:OUTLINE_MAX]


# ------------------------------------------------------------------ الـPDF (نقي · weasyprint كسول)

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(HERE, 'assets', 'fonts')
ORDINALS = ('الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع', 'الثامن', 'التاسع', 'العاشر', 'الحادي عشر', 'الثاني عشر')
PAPER, INK, WINE = '#FBFAF7', '#21262E', '#9E2B4E'


def _paras(text):
    esc = _html.escape
    blocks = [b.strip() for b in re.split(r'\n\s*\n', text or '') if b.strip()]
    return ''.join('<p>%s</p>' % esc(b).replace('\n', '<br>') for b in blocks)


def build_book_html(draft, fonts_dir=FONTS_DIR):
    """HTML واحد RTL: غلاف · فهرس · فصول. الخط Cairo من ملفات الريبو (لا يعتمد على خطوط الخادم)."""
    from pathlib import Path
    esc = _html.escape
    reg = Path(fonts_dir, 'Cairo-Regular.ttf').resolve().as_uri()
    bold = Path(fonts_dir, 'Cairo-Bold.ttf').resolve().as_uri()
    chapters = draft.get('chapters') or []
    toc = ''.join('<li><a href="#c%d"><span class="n">%s</span><span class="t">%s</span></a></li>' % (i + 1, esc(ORDINALS[i] if i < len(ORDINALS) else str(i + 1)), esc(c.get('title', '')))
                  for i, c in enumerate(chapters))
    body = ''.join('<section class="ch" id="c%d"><p class="lab">الفصل %s</p><h2>%s</h2>%s</section>'
                   % (i + 1, esc(ORDINALS[i] if i < len(ORDINALS) else str(i + 1)), esc(c.get('title', '')), _paras(c.get('body', '')))
                   for i, c in enumerate(chapters))
    about = _paras(draft.get('about', ''))
    css = '''
@font-face{font-family:"Cairo";src:url("%(reg)s");font-weight:400}
@font-face{font-family:"Cairo";src:url("%(bold)s");font-weight:700}
@page{size:A5;margin:20mm 17mm 22mm;background:%(paper)s;
  @bottom-center{content:counter(page, arabic-indic);font:700 9pt "Cairo";color:%(wine)s}}
@page cover{margin:0;background:%(paper)s;@bottom-center{content:none}}
html{direction:rtl}
body{margin:0;font-family:"Cairo",sans-serif;font-weight:400;color:%(ink)s;font-size:11pt;line-height:2;text-align:right}
.cover{page:cover;height:210mm;position:relative;break-after:page}
.cover .band{background:%(wine)s;color:#fff;height:56mm;padding:20mm 17mm 0;box-sizing:border-box}
.cover .brand{font-weight:700;font-size:15pt;letter-spacing:0}
.cover .main{padding:26mm 17mm 0}
.cover h1{font-size:27pt;line-height:1.55;font-weight:700;margin:0 0 8mm;color:%(ink)s}
.cover .rule{width:34mm;height:2.2mm;background:%(wine)s;margin:0 0 9mm}
.cover .about{font-size:11.5pt;line-height:2;color:#4A4F57;margin:0}
.cover .foot{position:absolute;right:17mm;bottom:14mm;font-size:9pt;color:%(wine)s;font-weight:700}
.tocp{break-after:page}
.tocp h2{font-size:18pt;color:%(wine)s;font-weight:700;margin:0 0 8mm}
.tocp ol{list-style:none;margin:0;padding:0}
.tocp li{margin:0 0 4mm}
.tocp a{display:block;color:%(ink)s;text-decoration:none}
.tocp a .n{color:%(wine)s;font-weight:700;margin-left:3mm}
.tocp a::after{content:leader(".") " " target-counter(attr(href), page, arabic-indic);color:%(wine)s}
.ch{break-before:page}
.ch .lab{margin:0 0 2mm;color:%(wine)s;font-weight:700;font-size:10pt}
.ch h2{margin:0 0 7mm;padding-bottom:4mm;border-bottom:1.4mm solid %(wine)s;font-size:19pt;line-height:1.6;font-weight:700}
.ch p{margin:0 0 4.2mm;orphans:3;widows:3}
''' % {'reg': reg, 'bold': bold, 'paper': PAPER, 'ink': INK, 'wine': WINE}
    return ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><title>%s</title><style>%s</style></head><body>'
            '<div class="cover"><div class="band"><div class="brand">البروفيسور</div></div><div class="main"><h1>%s</h1><div class="rule"></div><div class="about">%s</div></div>'
            '<div class="foot">البروفيسور</div></div>'
            '<div class="tocp"><h2>الفهرس</h2><ol>%s</ol></div>%s</body></html>'
            % (esc(draft.get('title', '')), css, esc(draft.get('title', '')), about, toc, body))


def render_pdf(draft, fonts_dir=FONTS_DIR):
    """بايتات PDF. weasyprint بيتحمّل هنا بس: غيابه ⇒ RuntimeError('missing') والمنادي يرد برسالة عربية."""
    try:
        from weasyprint import HTML
    except Exception as exc:   # noqa: BLE001  (غياب المكتبة أو مكتبات النظام تحتها)
        raise RuntimeError('missing') from exc
    return HTML(string=build_book_html(draft, fonts_dir), base_url=HERE).write_pdf()


# ------------------------------------------------------------------ المسارات

def register(app, g):
    token_required = g['token_required']
    roles_required = g['roles_required']
    jsonify = g['jsonify']
    request = g['request']
    ID_RE = g['V2_ID_RE']
    db = g['db']
    state = {'model': None, 'ready': False}

    def ns(resp):
        return g['_v2_ns'](resp)

    def err(msg, code=400):
        return ns((jsonify({'error': msg}), code))

    def engine():
        from brain2 import engine as eng
        return eng

    # ---- جدول المسودات (مرة واحدة، كسول)
    def Draft():
        if state['model'] is None:
            class V2BooksOursDraft(db.Model):
                __tablename__ = 'v2_books_ours_drafts'
                __table_args__ = {'extend_existing': True}
                slug = db.Column(db.String(200), primary_key=True)
                status = db.Column(db.String(10), nullable=False, default='ready')      # writing | ready | failed
                instruction = db.Column(db.Text)
                outline = db.Column(db.Text)
                data_json = db.Column(db.Text)
                error = db.Column(db.String(300))
                writer = db.Column(db.String(8))                                         # main | backup
                updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
                updated_by = db.Column(db.String(255))
                pdf_at = db.Column(db.DateTime)
            state['model'] = V2BooksOursDraft
        if not state['ready']:
            try:
                state['model'].__table__.create(db.engine, checkfirst=True)
                state['ready'] = True
            except Exception:   # noqa: BLE001
                g['logger'].exception('books_ours: draft table failed')
        return state['model']

    def iso(dt):
        return dt.replace(microsecond=0).isoformat() + 'Z' if dt else None

    def draft_view(row):
        if row is None:
            return {'status': 'none', 'draft': None, 'review_marks': []}
        status = row.status
        if status == 'writing' and row.updated_at and datetime.datetime.utcnow() - row.updated_at > datetime.timedelta(minutes=DRAFT_STALE_MIN):
            status = 'failed'
        try:
            data = json.loads(row.data_json) if row.data_json else None
        except (TypeError, ValueError):
            data = None
        marks = []
        if isinstance(data, dict):
            marks = data.pop('review_marks', None) or []
        return {'status': status, 'draft': data, 'review_marks': marks, 'instruction': row.instruction or '', 'outline': row.outline or '',
                'error': (row.error or ERR_FAILED_AR) if status == 'failed' else '',
                'writer': row.writer, 'updated_at': iso(row.updated_at), 'pdf_at': iso(row.pdf_at)}

    # ---- حرّاس مشتركة
    def guard(ids=(), write=True):
        closed = g['_v2_closed']()
        if closed:
            return closed, None
        for i in ids:
            if not ID_RE.match(i or ''):
                return err(BAD_ID_AR), None
        body = g['_v2_body']() if write else {}
        if write:
            bad = g['_v2_confirmed'](body)
            if bad:
                return bad, None
        return None, body

    def no_reply(action, target):
        g['_audit']('book_ours.no_reply', target=target, meta={'attempt': action})
        return ns((jsonify({'error': NO_REPLY_AR, 'no_reply': True}), 502))

    def finish(resp, action, target, meta, audit=True):
        if g['_resp_ok'](resp):
            if audit:
                g['_audit'](action, target=target, meta=meta)
            return ns(resp)
        if g['_ef_no_reply'](resp):
            return no_reply(action, target)
        return ns(g['_v2_mask_auth'](resp))

    def write(method, path, fields, action, target, meta):
        body = dict(fields)
        body['confirmed'] = True
        body['by'] = g['_actor_email']()
        return finish(g['_platform_proxy'](method, path, json_body=body, timeout=40), action, target, meta)

    def read(path):
        return g['_platform_proxy']('GET', path, timeout=15)

    def q(x):
        return quote(x, safe='')

    def clean_book_fields(b, partial):
        """(حقول نظيفة، رسالة خطأ | None) من قايمة بيضا: العنوان · النبذة · النوع · المؤلف · مجاني."""
        b = strip_money(b)
        out = {}
        if 'title' in b or not partial:
            t = _clip(b.get('title'), TITLE_MAX + 1)
            if not t or len(t) > TITLE_MAX:
                return None, 'اكتب عنوان الكتاب (حتى ١٦٠ حرفًا)'
            out['title'] = t
        if 'about' in b:
            a = b.get('about')
            if not isinstance(a, str) or len(a.strip()) > ABOUT_MAX:
                return None, 'النبذة طويلة (حتى ٢٠٠٠ حرف)'
            out['about'] = a.strip()
        elif not partial:
            out['about'] = ''
        if 'type' in b or not partial:
            if b.get('type') not in TYPES:
                return None, 'اختر نوعًا من القائمة'
            out['type'] = b['type']
        # كتاب قديم صار ملكًا عامًا: باسم مؤلفه الحقيقي، ومجاني (فارغ ⇒ «البروفيسور»)
        if 'author' in b:
            a = b.get('author')
            if not isinstance(a, str) or len(' '.join(a.split())) > AUTHOR_MAX:
                return None, 'اسم المؤلف طويل (حتى ٢٠٠ حرف)'
            out['author'] = ' '.join(a.split())
        if 'free' in b:
            if not isinstance(b.get('free'), bool):
                return None, 'اختر «مجاني» أو اتركه'
            out['free'] = b['free']
        return out, None

    # ------------------------------------------------------------------ ١ · القايمة
    @app.route('/api/v2/books/ours', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2bo_list():
        bad, _ = guard(write=False)
        if bad:
            return bad
        resp = read(BASE)
        if not g['_resp_ok'](resp):
            return ns(g['_v2_mask_auth'](resp))
        data = resp.get_json(silent=True)
        rows = data.get('books') if isinstance(data, dict) else None
        if not isinstance(rows, list):
            return err('تعذر قراءة رد المنصة', 502)
        drafts = {}
        try:
            for d in Draft().query.all():
                drafts[d.slug] = draft_view(d)['status']
        except Exception:   # noqa: BLE001
            db.session.rollback()
        books = []
        for r in rows:
            v = view_book(r)
            if v is not None:
                v['draft'] = drafts.get(v.get('slug'))
                books.append(v)
        types = data.get('types') if isinstance(data.get('types'), list) else list(TYPES)
        return ns(jsonify({'books': books, 'types': [t for t in types if isinstance(t, str)][:12]}))

    # ------------------------------------------------------------------ ٢ · إنشاء مسودة
    @app.route('/api/v2/books/ours', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2bo_create():
        bad, b = guard()
        if bad:
            return bad
        out, e = clean_book_fields(b, partial=False)
        if e:
            return err(e)
        idem = b.get('idem_key')
        if idem is not None:
            if not isinstance(idem, str) or not IDEM_RE.match(idem):
                return err('مفتاح منع التكرار غير صالح')
            out['idem_key'] = idem
        return write('POST', BASE, out, 'book_ours.create', idem or out['title'][:80], {'title': out['title'][:80], 'type': out['type']})

    # ------------------------------------------------------------------ ٣ · تعديل البيانات
    @app.route('/api/v2/books/ours/<slug>', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2bo_update(slug):
        bad, b = guard([slug])
        if bad:
            return bad
        out, e = clean_book_fields(b, partial=True)
        if e:
            return err(e)
        if not out:
            return err('لا يوجد تغيير')
        return write('PUT', '%s/%s' % (BASE, q(slug)), out, 'book_ours.update', slug, {'keys': sorted(out.keys())})

    # ------------------------------------------------------------------ ٤ · رفع الملف (PDF بس)
    def push_file(slug, filename, data, meta):
        """نداء واحد multipart للجسر. الرفع الجديد بيبدّل القديم عند المنصة."""
        resp = g['_platform_proxy']('POST', '%s/%s/file' % (BASE, q(slug)), data={'by': g['_actor_email'](), 'confirmed': 'true'},
                                    files={'file': (safe_filename(filename), data, 'application/pdf')}, timeout=90)
        m = dict(meta)
        m['size'] = len(data)
        return finish(resp, 'book_ours.file', slug, m)

    @app.route('/api/v2/books/ours/<slug>/file', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2bo_file(slug):
        closed = g['_v2_closed']()
        if closed:
            return closed
        if not ID_RE.match(slug or ''):
            return err(BAD_ID_AR)
        if (request.form.get('confirmed') or '').strip() != 'true':
            return g['_v2_confirmed']({})
        cap = upload_cap_bytes()
        if (request.content_length or 0) > cap + 1024 * 1024:
            return err(too_big_ar(cap), 413)
        f = request.files.get('file')
        if f is None or not (f.filename or '').strip():
            return err(PDF_NONE_AR)
        data = f.read(cap + 1)
        if len(data) > cap:
            return err(too_big_ar(cap), 413)
        bad = check_pdf(f.filename, data)
        if bad:
            return err(bad)
        return push_file(slug, f.filename, data, {'source': 'upload'})

    # ------------------------------------------------------------------ ٥ · اعرض في المتجر / اسحب
    @app.route('/api/v2/books/ours/<slug>/status', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2bo_status(slug):
        bad, b = guard([slug])
        if bad:
            return bad
        if not isinstance(b.get('live'), bool):
            return err('حدّد: عرض في المتجر أم سحب منه')
        return write('PUT', '%s/%s/status' % (BASE, q(slug)), {'live': b['live']}, 'book_ours.status', slug, {'live': b['live']})

    # ------------------------------------------------------------------ ٦ · أكواد فتح الأدلّة
    @app.route('/api/v2/books/guide-codes', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2bo_codes_get():
        bad, _ = guard(write=False)
        if bad:
            return bad
        resp = read(CODES_PATH)
        if not g['_resp_ok'](resp):
            return ns(g['_v2_mask_auth'](resp))
        body = view_codes(resp.get_json(silent=True))
        if body is None:
            return err('تعذر قراءة رد المنصة', 502)
        return ns(jsonify(body))

    @app.route('/api/v2/books/guide-codes', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2bo_codes_put():
        bad, b = guard()
        if bad:
            return bad
        rows = b.get('codes')
        if not isinstance(rows, list) or len(rows) > CODES_MAX:
            return err('قائمة الأكواد غير صالحة')
        out, seen = [], set()
        for r in rows:
            if not isinstance(r, dict):
                return err('كود غير صالح')
            code = r.get('code')
            code = code.strip().lower() if isinstance(code, str) else ''
            if not CODE_RE.match(code):
                return err('الكود من ٣ إلى ٤٠ حرفًا: أحرف إنجليزية صغيرة وأرقام وشرطة فقط')
            if code in seen:
                return err('الكود مكرر: %s' % code)
            seen.add(code)
            note = r.get('note')
            note = note.strip()[:NOTE_MAX] if isinstance(note, str) else ''
            mu = r.get('max_uses')
            if mu is not None:
                if isinstance(mu, bool) or not isinstance(mu, int) or not 1 <= mu <= 1000000:
                    return err('أقصى عدد استعمال رقم صحيح أكبر من صفر، أو اتركه فارغًا')
            active = r.get('active', True)
            if not isinstance(active, bool):
                return err('حدّد: الكود مفعّل أم لا')
            out.append({'code': code, 'note': note, 'max_uses': mu, 'active': active})
        return write('PUT', CODES_PATH, {'codes': out}, 'guide_codes.update', 'codes', {'count': len(out), 'active': sum(1 for c in out if c['active'])})

    # ------------------------------------------------------------------ ٧ · العقل يكتب: مسودة (بلا أي نداء للمنصة)
    @app.route('/api/v2/books/ours/<slug>/brain/draft', methods=['GET'])
    @token_required
    @roles_required('admin')
    def v2bo_draft_get(slug):
        bad, _ = guard([slug], write=False)
        if bad:
            return bad
        return ns(jsonify(draft_view(Draft().query.get(slug))))

    @app.route('/api/v2/books/ours/<slug>/brain/draft', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2bo_draft_make(slug):
        bad, b = guard([slug], write=False)
        if bad:
            return bad
        b = g['_v2_body']()
        instruction = engine().clean_text(b.get('instruction'), keep_newlines=True)
        if not instruction:
            return err('اكتب ما تريده من العقل')
        if len(instruction) > INSTRUCTION_MAX:
            return err('التعليمات طويلة (حتى ٢٠٠٠ حرف)')
        outline = norm_outline(b.get('outline'))
        eng = engine()
        M = Draft()
        row = M.query.get(slug)
        now = datetime.datetime.utcnow()
        if row is not None and row.status == 'writing' and row.updated_at and now - row.updated_at < datetime.timedelta(minutes=DRAFT_STALE_MIN):
            return err(ERR_WRITING_AR, 409)
        if not eng.writes_enabled():
            return err(ERR_OFF_AR, 409)
        writer = eng.writer_of(g)
        if writer is None:
            return err(ERR_NO_WRITER_AR, 503)
        if eng.brain_today(db) >= eng.day_cap():
            return err(ERR_CAP_AR, 429)
        try:
            remaining = g['ai_daily_usage_state']().get('remaining')
        except Exception:   # noqa: BLE001
            remaining = None
        if remaining is not None and remaining < eng.RESERVE_MIN:
            return err(ERR_CAP_AR, 429)
        actor = g['_actor_email']()
        keep = row.data_json if row is not None else None
        if row is None:
            row = M(slug=slug)
            db.session.add(row)
        row.status, row.instruction, row.outline, row.error, row.writer = 'writing', instruction, outline, None, writer
        row.updated_at, row.updated_by = now, actor
        db.session.commit()
        eng._bump_day(db)          # نداء واحد يُحسب قبل خروجه، فلا يضيع نداءٌ فشل

        def job():
            r = M.query.get(slug)
            if r is None:
                return
            clean, why = None, None
            try:
                text = g['ai_call'](eng.SYSTEM_AR + '\n' + BOOK_RULES_AR + '\n' + BOOK_SHAPE_AR, draft_prompt(instruction, outline), purpose='books_ours.draft')
            except Exception as exc:   # noqa: BLE001
                kind = getattr(exc, 'kind', None)
                why = 'cap' if kind == 'cap' else ('no_key' if kind == 'no_key' else 'ai')
                text = None
            if why is None:
                try:
                    data = g['_extract_json_block'](text)
                except Exception:   # noqa: BLE001
                    data = None
                clean, why = validate_draft(data, eng, instruction + '\n' + outline)
            r.updated_at = datetime.datetime.utcnow()
            if clean is None:
                r.status = 'failed'
                r.error = {'cap': ERR_CAP_AR, 'no_key': ERR_NO_WRITER_AR, 'ai': ERR_FAILED_AR}.get(why, ERR_INVALID_AR)
                r.data_json = keep            # المسودة القديمة (لو فيه) ما بتضيعش بفشل جديد
                db.session.commit()
                return
            r.status, r.error = 'ready', None
            marks = review_marks(clean, eng, instruction + '\n' + outline)
            r.data_json = json.dumps(dict(clean, review_marks=marks), ensure_ascii=False)
            r.pdf_at = None
            db.session.commit()
            g['_audit']('book_ours.brain_draft', target=slug, meta={'chapters': len(clean['chapters']), 'writer': writer, 'review_marks': len(marks)}, actor=actor)

        sub = eng.submit(g, 'books_ours:' + slug, job)
        if not sub.get('queued'):
            row = M.query.get(slug)
            row.status, row.error = 'failed', ERR_WRITING_AR
            db.session.commit()
            return err(ERR_WRITING_AR, 409)
        return ns((jsonify(draft_view(M.query.get(slug))), 202))

    # ------------------------------------------------------------------ ٨ · تعديل المؤسس للمسودة (حفظ محلي، بلا منصة)
    @app.route('/api/v2/books/ours/<slug>/brain/draft', methods=['PUT'])
    @token_required
    @roles_required('admin')
    def v2bo_draft_save(slug):
        bad, _ = guard([slug], write=False)
        if bad:
            return bad
        clean, why = validate_draft(g['_v2_body'](), engine(), None)
        if clean is None:
            return err('هذه الصيغة غير مقبولة: لا تستعمل هذه الكلمة' if why == 'banned' else ERR_DRAFT_SHAPE_AR)
        M = Draft()
        row = M.query.get(slug)
        if row is None:
            row = M(slug=slug, instruction='', outline='')
            db.session.add(row)
        row.status, row.error = 'ready', None
        old = draft_view(row).get('review_marks') or []
        marks = remap_marks(clean, sorted(set(m['token'] for m in old)))
        row.data_json = json.dumps(dict(clean, review_marks=marks), ensure_ascii=False)
        row.updated_at, row.updated_by, row.pdf_at = datetime.datetime.utcnow(), g['_actor_email'](), None
        db.session.commit()
        return ns(jsonify(draft_view(row)))

    # ------------------------------------------------------------------ ٩ · المسودة ⇒ PDF ⇒ رفع (بتأكيد)
    @app.route('/api/v2/books/ours/<slug>/brain/pdf', methods=['POST'])
    @token_required
    @roles_required('admin')
    def v2bo_pdf(slug):
        bad, _ = guard([slug])
        if bad:
            return bad
        row = Draft().query.get(slug)
        view = draft_view(row)
        if row is None or not view.get('draft') or row.status == 'writing':
            return err(ERR_NO_DRAFT_AR, 409 if row is not None and row.status == 'writing' else 400)
        clean, _why = validate_draft(view['draft'], engine(), None)
        if clean is None:
            return err(ERR_DRAFT_SHAPE_AR)
        try:
            data = render_pdf(clean)
        except RuntimeError:
            return err(ERR_PDF_OFF_AR, 503)
        except Exception:   # noqa: BLE001
            g['logger'].exception('books_ours: pdf render failed')
            return err(ERR_PDF_FAIL_AR, 500)
        if len(data) > upload_cap_bytes():
            return err(too_big_ar(upload_cap_bytes()), 413)
        resp = push_file(slug, clean['title'][:60] + '.pdf', data, {'source': 'brain', 'chapters': len(clean['chapters'])})
        code = resp[1] if isinstance(resp, tuple) else getattr(resp, 'status_code', 200)
        if 200 <= int(code) < 300:
            row.pdf_at = datetime.datetime.utcnow()
            db.session.commit()
        return resp

    return app
