# -*- coding: utf-8 -*-
"""تعديل نصوص موقع elprofessor.net من اللوحة (SPEC docs/v2/brain2/SPEC-B.md §B6).

القراءة: GET https://elprofessor.net/<صفحة> (نداء قابل للحقن) ⇒ مستخرِج صارم بـ`html.parser` يُخرج «كتل» نصية فقط:
h1–h3 · p · li · نص a · نص button · title · وصف meta. السكربتات والأنماط والسمات لا تُعدَّل أبدًا
(الاستثناء الوحيد المذكور في المواصفة: قيمة `content` في `meta name=description`).

التنفيذ (صفحة واحدة، الكل أو لا شيء):
  1. تنزيل الملف الحي بـSFTP إلى جدول `site_backups` (آخر ٢٠ لكل صفحة).
  2. بصمة النصوص الحيّة ≠ بصمة لحظة الاقتراح ⇒ ٤٠٩ «تغيّرت الصفحة منذ الاقتراح؛ أعد التوليد».
  3. استبدال عُقد النص فقط؛ كل `old` يطابق مرة واحدة بالضبط (صفر أو أكثر من واحدة ⇒ خطأ).
  4. رفع باسم مؤقت ثم إعادة تسمية.
  5. تحقّق بنداء HTTPS أن النص الجديد ظاهر؛ وإلا نُرجع النسخة ونقول «لم يظهر التعديل؛ أعدنا الصفحة كما كانت».

⛔ لا يُلمس `.htaccess` ولا ملف خارج قائمة الصفحات المسموحة، ولا يُحذف أي ملف من الاستضافة (لا `remove` ولا `rmdir` هنا أبدًا).
⛔ صفر شبكة في الاختبارات: `getter` (نداء HTTPS) و`sftp_factory` (الاتصال) قابلان للحقن، والافتراضيان الحقيقيان يُستدعيان في الإنتاج فقط.
⛔ ملف مستقل عن `app.py` (لا يستورده). الإعداد من نفس متغيرات الرفع الموجودة: PRERENDER_SSH_HOST/PORT/USER/PASSWORD و PRERENDER_SITE_ROOT.

ملاحظة عن «البصمة»: بصمة الاقتراح = SHA-256 لقائمة (مسار، نص) للكتل، لا لبايتات الملف؛ فنسخة HTTPS (قد يعدّلها الـCDN) ونسخة SFTP
تتطابقان ما دامت النصوص نفسها. أما `site_backups.sha256` فبصمة بايتات الملف الحي كما نُزِّل.
"""
import datetime
import gzip
import hashlib
import html as _html
import json
import logging
import os
import posixpath
import re
import threading
import time
from html.parser import HTMLParser

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ قائمة الصفحات المسموحة (الرئيسية = Company-Site.html)
PAGES = (
    ('Company-Site.html', 'الصفحة الرئيسية'),
    ('contact.html', 'صفحة التواصل'),
    ('founders.html', 'صفحة المؤسسين'),
    ('platform.html', 'صفحة المنصة'),
    ('pricing.html', 'صفحة الأسعار'),
    ('training.html', 'صفحة التدريب'),
    ('privacy.html', 'سياسة الخصوصية'),
    ('terms.html', 'الشروط والأحكام'),
    ('404.html', 'صفحة الخطأ'),
    ('haq-masr/index.html', 'حق مصر: الرئيسية'),
    ('haq-masr/qanoneen.html', 'حق مصر: قانونين'),
    ('haq-masr/sign.html', 'حق مصر: التوقيع'),
)
ALLOWED = tuple(p for p, _ in PAGES)
LABELS = dict(PAGES)

BACKUP_KEEP = 20
MAX_EDITS = 10
NEW_MAX = 600
OLD_MAX = 1200
DEFAULT_ORIGIN = 'https://elprofessor.net'
TMP_SUFFIX = '.siteedit-tmp'

ERR_NOT_ALLOWED = 'هذه الصفحة غير مسموح بتعديلها من اللوحة'
ERR_FETCH = 'تعذّر قراءة الصفحة الآن. حاول بعد قليل'
ERR_STALE = 'تغيّرت الصفحة منذ الاقتراح؛ أعد التوليد'
ERR_VERIFY = 'لم يظهر التعديل؛ أعدنا الصفحة كما كانت'
ERR_VERIFY_RESTORE_FAILED = 'لم يظهر التعديل، وتعذّر إرجاع الصفحة. راجع النسخ السابقة وأرجِعها بنفسك'
ERR_NOT_CONFIGURED = 'ربط الاستضافة غير مضبوط، فلا يمكن حفظ التعديل الآن'
ERR_REMOTE = 'تعذّر الاتصال بالاستضافة الآن. لم يتغيّر شيء'
ERR_BUSY = 'يجري تعديل آخر على الموقع الآن. جرّب بعد قليل'
ERR_NO_MATCH = 'النص القديم لم يعد موجودًا في الصفحة'
ERR_MULTI_MATCH = 'النص القديم يتكرر في الصفحة أكثر من مرة، فلا يمكن تحديد موضعه'
ERR_BAD_EDIT = 'التعديل غير صالح'
ERR_NO_BACKUP = 'هذه النسخة غير موجودة'
ERR_ENCODING = 'تعذّرت قراءة ترميز الصفحة'


class SiteError(Exception):
    """خطأ عربي جاهز للعرض + رمز آلي + حالة HTTP مقترحة."""

    def __init__(self, code, message, status=400):
        super(SiteError, self).__init__(message)
        self.code = code
        self.message = message
        self.status = status


# ------------------------------------------------------------------ أدوات نصية
_WS_RE = re.compile(r'\s+')
_CTRL_RE = re.compile('[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]')


def collapse(s):
    """نص الكتلة كما يراه القارئ: الفراغات المتتالية فراغ واحد، بلا فراغ في الطرفين."""
    return _WS_RE.sub(' ', s if isinstance(s, str) else '').strip()


def page_allowed(page):
    """الصفحة في القائمة المسموحة بالضبط، وليست ملفًا مخفيًا (.htaccess…)، ولا مسارًا يخرج من الجذر."""
    if not isinstance(page, str) or page not in ALLOWED:
        return False
    parts = page.split('/')
    return all(p and not p.startswith('.') and p != '..' for p in parts)


def require_page(page):
    if not page_allowed(page):
        raise SiteError('not_allowed', ERR_NOT_ALLOWED, 400)
    return page


def clean_new_text(new, tag=''):
    """النص الجديد: سطر واحد نظيف بلا وسوم. يرفع SiteError لو غير صالح."""
    if not isinstance(new, str):
        raise SiteError('bad_edit', ERR_BAD_EDIT)
    t = collapse(_CTRL_RE.sub('', new))
    if not t or len(t) > NEW_MAX:
        raise SiteError('bad_edit', 'اكتب نصًا من حرف إلى %d حرف' % NEW_MAX)
    if '<' in t or '>' in t:
        raise SiteError('bad_edit', 'لا يُقبل في النص رمزا الأقواس الزاوية')
    return t


# ------------------------------------------------------------------ المستخرِج
EDITABLE_TAGS = ('h1', 'h2', 'h3', 'p', 'li', 'a', 'button', 'title')
SKIP_TAGS = ('script', 'style', 'template', 'textarea', 'noscript', 'svg')
VOID_TAGS = frozenset(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param',
                       'source', 'track', 'wbr'])
_CONTENT_ATTR_RE = re.compile(r'(?<![\w:-])content\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)
BLOCK_NOTE_DUP = 'النص مكرر في الصفحة'


class _Scan(HTMLParser):
    """يمشي على المصدر الخام ويسجّل مواضع (بداية، نهاية) كل «شريحة نص» بين الوسوم. المصدر نفسه لا يُغيَّر."""

    def __init__(self, src):
        HTMLParser.__init__(self, convert_charrefs=False)
        self.src = src
        self._ls = [0] + [m.end() for m in re.finditer('\n', src)]
        self._stack = []                 # [{'name', 'path', 'kids'}]
        self._root_kids = {}
        self._cur = None                 # شريحة نص مفتوحة
        self.runs = []
        self.metas = []

    def _abs(self):
        line, off = self.getpos()
        return self._ls[line - 1] + off

    def _kids(self):
        return self._stack[-1]['kids'] if self._stack else self._root_kids

    def _path_for(self, name):
        kids = self._kids()
        kids[name] = kids.get(name, 0) + 1
        base = self._stack[-1]['path'] + '>' if self._stack else ''
        return '%s%s[%d]' % (base, name, kids[name])

    def _owner(self):
        for n in self._stack:
            if n['name'] in SKIP_TAGS:
                return None
        for n in reversed(self._stack):
            if n['name'] in EDITABLE_TAGS:
                return n
        return None

    def _flush(self, pos):
        c = self._cur
        self._cur = None
        if c is None or c['owner'] is None:
            return
        raw = self.src[c['start']:pos]
        text = collapse(_html.unescape(raw))
        if text:
            self.runs.append({'owner': c['owner'], 'start': c['start'], 'end': pos, 'text': text, 'kind': 'text'})

    def _text_event(self):
        if self._cur is None:
            self._cur = {'start': self._abs(), 'owner': self._owner()}

    # —— أحداث النص
    def handle_data(self, data):
        self._text_event()

    def handle_entityref(self, name):
        self._text_event()

    def handle_charref(self, name):
        self._text_event()

    # —— حدود (وسوم وتعليقات)
    def handle_comment(self, data):
        self._flush(self._abs())

    def handle_decl(self, decl):
        self._flush(self._abs())

    def handle_pi(self, data):
        self._flush(self._abs())

    def unknown_decl(self, data):
        self._flush(self._abs())

    def _meta(self, attrs, pos):
        d = dict((k.lower(), v) for k, v in attrs if k)
        if (d.get('name') or '').strip().lower() != 'description' or d.get('content') is None:
            return
        raw_tag = self.get_starttag_text() or ''
        m = _CONTENT_ATTR_RE.search(raw_tag)
        if not m:
            return                       # قيمة بلا علامات اقتباس: لا تُعدَّل
        g = 1 if m.group(1) is not None else 2
        start, end = pos + m.start(g), pos + m.end(g)
        text = collapse(_html.unescape(self.src[start:end]))
        if text:
            self.metas.append({'owner': {'name': 'meta', 'path': self._meta_path}, 'start': start, 'end': end,
                               'text': text, 'kind': 'meta'})

    def handle_starttag(self, tag, attrs):
        pos = self._abs()
        self._flush(pos)
        if tag in ('p', 'li') and self._stack and self._stack[-1]['name'] == tag:
            self._stack.pop()            # إغلاق ضمني (<li>…<li>)
        path = self._path_for(tag)
        if tag == 'meta':
            self._meta_path = path
            self._meta(attrs, pos)
        if tag in VOID_TAGS:
            return
        self._stack.append({'name': tag, 'path': path, 'kids': {}})

    def handle_startendtag(self, tag, attrs):
        pos = self._abs()
        self._flush(pos)
        path = self._path_for(tag)
        if tag == 'meta':
            self._meta_path = path
            self._meta(attrs, pos)

    def handle_endtag(self, tag):
        self._flush(self._abs())
        if tag in VOID_TAGS:
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]['name'] == tag:
                del self._stack[i:]
                break

    def done(self):
        self.close()
        self._flush(len(self.src))
        return self.runs + self.metas


def _scan(src):
    """كل الكتل بمواضعها (داخلي): path · tag · text · start · end · kind · editable · note."""
    sc = _Scan(src)
    sc.feed(src)
    raw = sc.done()
    per_owner = {}
    for r in raw:
        per_owner[id(r['owner'])] = per_owner.get(id(r['owner']), 0) + 1
    seen = {}
    out = []
    for r in sorted(raw, key=lambda x: x['start']):
        o = r['owner']
        n = per_owner[id(o)]
        k = seen.get(id(o), 0) + 1
        seen[id(o)] = k
        path = o['path'] + ('#%d' % k if n > 1 else '')
        out.append({'path': path, 'tag': o['name'], 'text': r['text'], 'start': r['start'], 'end': r['end'],
                    'kind': r['kind']})
    counts = {}
    for b in out:
        counts[b['text']] = counts.get(b['text'], 0) + 1
    for b in out:
        dup = counts[b['text']] > 1
        b['editable'] = not dup
        b['note'] = BLOCK_NOTE_DUP if dup else ''
    return out


def extract_blocks(src):
    """الكتل القابلة للقراءة للواجهة: path · tag · text · editable · note. (بلا مواضع.)"""
    return [{'path': b['path'], 'tag': b['tag'], 'text': b['text'], 'editable': b['editable'], 'note': b['note']}
            for b in _scan(src)]


def blocks_sha(blocks):
    payload = json.dumps([[b['path'], b['text']] for b in blocks], ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


# ------------------------------------------------------------------ الاستبدال (عُقد النص فقط)
def replace_edits(src, edits):
    """يرجع المصدر الجديد. كل `old` يطابق نص كتلة واحدة بالضبط؛ المسار (إن وُجد) يجب أن يطابق تلك الكتلة.
    ⛔ لا يلمس إلا شرائح النص المطابقة (وقيمة وصف meta)؛ كل بايت آخر يبقى كما هو."""
    if not isinstance(edits, (list, tuple)) or not edits or len(edits) > MAX_EDITS:
        raise SiteError('bad_edit', ERR_BAD_EDIT)
    scan = _scan(src)
    plan = []
    used = set()
    for e in edits:
        if not isinstance(e, dict) or not isinstance(e.get('old'), str):
            raise SiteError('bad_edit', ERR_BAD_EDIT)
        old = collapse(e['old'])
        if not old or len(old) > OLD_MAX:
            raise SiteError('bad_edit', ERR_BAD_EDIT)
        hits = [b for b in scan if b['text'] == old]
        if not hits:
            raise SiteError('no_match', ERR_NO_MATCH, 422)
        if len(hits) > 1:
            raise SiteError('multi_match', ERR_MULTI_MATCH, 422)
        b = hits[0]
        path = e.get('path')
        if path is not None and path != '' and path != b['path']:
            raise SiteError('path_mismatch', ERR_NO_MATCH, 422)
        if b['start'] in used:
            raise SiteError('bad_edit', ERR_BAD_EDIT)
        used.add(b['start'])
        new = clean_new_text(e.get('new'), b['tag'])
        if new == old:
            raise SiteError('bad_edit', 'النص الجديد مطابق للقديم')
        plan.append((b, new))
    out = src
    for b, new in sorted(plan, key=lambda x: x[0]['start'], reverse=True):
        raw = out[b['start']:b['end']]
        if b['kind'] == 'meta':
            rep = _html.escape(new, quote=True)
        else:
            m = re.match(r'^(\s*)(.*?)(\s*)$', raw, re.S)
            rep = m.group(1) + _html.escape(new, quote=False) + m.group(3)
        out = out[:b['start']] + rep + out[b['end']:]
    # حارس أخير: عدد الكتل لم يتغيّر، والنصوص الجديدة ظاهرة فعلًا
    after = _scan(out)
    if len(after) != len(scan):
        raise SiteError('bad_edit', ERR_BAD_EDIT, 422)
    texts = set(b['text'] for b in after)
    if any(collapse(new) not in texts for _, new in plan):
        raise SiteError('bad_edit', ERR_BAD_EDIT, 422)
    return out


# ------------------------------------------------------------------ القراءة الحية
def origin():
    return (os.environ.get('PRERENDER_ORIGIN') or DEFAULT_ORIGIN).rstrip('/')


def page_url(page):
    return '%s/%s' % (origin(), require_page(page))


def default_getter(url):
    """(status, text). ⛔ الإنتاج فقط: كاسر كاش لأن الـCDN أمام الموقع يقدّم نسخة قديمة بعد الرفع."""
    import requests
    r = requests.get(url, params={'nocache': str(int(time.time()))}, timeout=30,
                     headers={'User-Agent': 'elprofessor-dashboard-site/1.0', 'Cache-Control': 'no-cache',
                              'Pragma': 'no-cache'})
    return r.status_code, r.content.decode('utf-8', errors='replace')


_HOOKS = {'getter': None, 'sftp_factory': None, 'sleep': None}


def set_hooks(getter=None, sftp_factory=None, sleep=None):
    """للاختبارات: يحقن الناقل المزيّف لكل الاستدعاءات التي لا تمرّره صراحة. بلا وسائط ⇒ يعيد الافتراضي."""
    _HOOKS['getter'], _HOOKS['sftp_factory'], _HOOKS['sleep'] = getter, sftp_factory, sleep


def _getter(g):
    return g or _HOOKS['getter'] or default_getter


def _factory(f):
    return f or _HOOKS['sftp_factory'] or default_sftp_factory


def _sleep(s):
    return s or _HOOKS['sleep'] or time.sleep


def fetch_live(page, getter=None):
    """يقرأ الصفحة الحية: {page, html, blocks, sha}. أي فشل ⇒ SiteError(502)."""
    url = page_url(page)
    try:
        status, text = _getter(getter)(url)
    except Exception:   # noqa: BLE001
        logger.warning('site_edit: live fetch failed for %s', page)
        raise SiteError('fetch', ERR_FETCH, 502)
    if status != 200 or not isinstance(text, str) or not text.strip():
        raise SiteError('fetch', ERR_FETCH, 502)
    blocks = extract_blocks(text)
    return {'page': page, 'html': text, 'blocks': blocks, 'sha': blocks_sha(blocks)}


# ------------------------------------------------------------------ SFTP
class Session(object):
    """اتصال SFTP + جذر الموقع + إغلاق. الاختبارات تبني واحدًا حول SFTP مزيّف."""

    def __init__(self, sftp, root, close=None):
        self.sftp = sftp
        self.root = root.rstrip('/')
        self._close = close

    def close(self):
        try:
            if self._close:
                self._close()
        except Exception:   # noqa: BLE001
            logger.warning('site_edit: closing sftp failed')


def default_sftp_factory():
    """⛔ الإنتاج فقط. نفس متغيرات رفع صفحات المقالات: PRERENDER_SSH_* و PRERENDER_SITE_ROOT."""
    host = os.environ.get('PRERENDER_SSH_HOST', '')
    user = os.environ.get('PRERENDER_SSH_USER', '')
    password = os.environ.get('PRERENDER_SSH_PASSWORD', '')
    if not (host and user and password):
        raise SiteError('not_configured', ERR_NOT_CONFIGURED, 503)
    site_root = os.environ.get('PRERENDER_SITE_ROOT', 'domains/elprofessor.net/public_html').strip('/')
    try:
        port = int(os.environ.get('PRERENDER_SSH_PORT', '65002') or 65002)
    except ValueError:
        port = 65002
    try:
        import paramiko
        cl = paramiko.SSHClient()
        cl.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        cl.connect(host, port=port, username=user, password=password, timeout=30, allow_agent=False,
                   look_for_keys=False)
        sftp = cl.open_sftp()
        home = sftp.normalize('.')
    except Exception:   # noqa: BLE001
        logger.warning('site_edit: sftp connect failed')
        raise SiteError('remote', ERR_REMOTE, 502)
    return Session(sftp, '%s/%s' % (home.rstrip('/'), site_root), cl.close)


def _remote_path(session, page):
    require_page(page)
    return '%s/%s' % (session.root, page)


def remote_read(session, page):
    path = _remote_path(session, page)
    try:
        fh = session.sftp.open(path, 'rb')
        try:
            data = fh.read()
        finally:
            fh.close()
    except Exception:   # noqa: BLE001
        logger.warning('site_edit: remote read failed for %s', page)
        raise SiteError('remote', ERR_REMOTE, 502)
    if not isinstance(data, bytes) or not data:
        raise SiteError('remote', ERR_REMOTE, 502)
    return data


def remote_write(session, page, data):
    """رفع باسم مؤقت (بجوار الملف) ثم إعادة تسمية ذرّية. ⛔ لا حذف: لو فشلت إعادة التسمية يبقى المؤقت."""
    path = _remote_path(session, page)
    tmp = path + TMP_SUFFIX
    sftp = session.sftp
    mode = None
    try:
        mode = sftp.stat(path).st_mode & 0o777
    except Exception:   # noqa: BLE001
        mode = None
    try:
        fh = sftp.open(tmp, 'wb')
        try:
            fh.write(data)
        finally:
            fh.close()
        if mode:
            try:
                sftp.chmod(tmp, mode)
            except Exception:   # noqa: BLE001
                pass
        sftp.posix_rename(tmp, path)
    except Exception:   # noqa: BLE001
        logger.warning('site_edit: remote write failed for %s', page)
        raise SiteError('remote', ERR_REMOTE, 502)


# ------------------------------------------------------------------ النسخ الاحتياطية
_MODEL = {}


def models(db):
    """جدول `site_backups` (page · sha256 · html مضغوط · created_at). يُعرَّف مرة واحدة."""
    if 'cls' in _MODEL:
        return _MODEL['cls']

    class SiteBackup(db.Model):
        __tablename__ = 'site_backups'
        __table_args__ = {'extend_existing': True}
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        page = db.Column(db.String(80), nullable=False, index=True)
        sha256 = db.Column(db.String(64), nullable=False)
        html_gz = db.Column(db.LargeBinary, nullable=False)
        created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, index=True)
        created_by = db.Column(db.String(255))
        note = db.Column(db.String(20))

    _MODEL['cls'] = SiteBackup
    return SiteBackup


def save_backup(db, page, data, actor='', note='apply'):
    """يحفظ بايتات الملف الحي. نفس محتوى أحدث نسخة ⇒ لا نسخة جديدة (محاولات فاشلة متكررة لا تُخرج القديم).
    يُبقي آخر ٢٠ لكل صفحة. يرجع صف النسخة."""
    require_page(page)
    B = models(db)
    sha = sha_bytes(data)
    last = B.query.filter_by(page=page).order_by(B.created_at.desc(), B.id.desc()).first()
    if last is not None and last.sha256 == sha:
        return last
    row = B(page=page, sha256=sha, html_gz=gzip.compress(data), created_at=datetime.datetime.utcnow(),
            created_by=str(actor or '')[:255], note=note[:20])
    db.session.add(row)
    db.session.commit()
    keep = [r.id for r in B.query.filter_by(page=page).order_by(B.created_at.desc(), B.id.desc()).limit(BACKUP_KEEP).all()]
    if keep:
        B.query.filter(B.page == page, ~B.id.in_(keep)).delete(synchronize_session=False)
        db.session.commit()
    return row


def list_backups(db, page):
    require_page(page)
    B = models(db)
    rows = B.query.filter_by(page=page).order_by(B.created_at.desc(), B.id.desc()).limit(BACKUP_KEEP).all()
    return [{'id': r.id, 'sha256': r.sha256, 'created_at': r.created_at, 'created_by': r.created_by or '',
             'note': r.note or '', 'size': len(r.html_gz or b'')} for r in rows]


def get_backup(db, page, backup_id):
    require_page(page)
    B = models(db)
    try:
        bid = int(backup_id)
    except (TypeError, ValueError):
        raise SiteError('no_backup', ERR_NO_BACKUP, 404)
    r = B.query.filter_by(id=bid, page=page).first()
    if r is None:
        raise SiteError('no_backup', ERR_NO_BACKUP, 404)
    return r


# ------------------------------------------------------------------ التنفيذ
_LOCK = threading.Lock()


def _decode(data):
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        raise SiteError('encoding', ERR_ENCODING, 422)


def _verify(page, edits, getter, attempts, delay, sleep):
    want = [collapse(e['new']) for e in edits]
    url = page_url(page)
    for i in range(max(1, attempts)):
        try:
            status, text = getter(url)
            if status == 200 and isinstance(text, str):
                texts = set(b['text'] for b in _scan(text))
                if all(w in texts for w in want):
                    return True
        except Exception:   # noqa: BLE001
            pass
        if i < attempts - 1:
            sleep(delay)
    return False


def apply_edits(db, page, expected_sha, edits, actor='', sftp_factory=None, getter=None, verify_attempts=3,
                verify_delay=2.0, sleep=None):
    """صفحة واحدة، الكل أو لا شيء. يرجع dict: ok · status · error · (backup_id · sha · restored · unknown).
    لا يرفع استثناء توقعًا؛ الأخطاء المعروفة تُرجَع في الـdict."""
    try:
        require_page(page)
        if not isinstance(edits, (list, tuple)) or not edits or len(edits) > MAX_EDITS:
            raise SiteError('bad_edit', ERR_BAD_EDIT)
    except SiteError as e:
        return {'ok': False, 'status': e.status, 'error': e.message, 'code': e.code}
    if not _LOCK.acquire(timeout=5):
        return {'ok': False, 'status': 409, 'error': ERR_BUSY, 'code': 'busy'}
    session = None
    try:
        session = _factory(sftp_factory)()
        data = remote_read(session, page)                                   # ١) تنزيل الحي
        src = _decode(data)
        backup = save_backup(db, page, data, actor, 'apply')                #    ثم نسخة قبل أي تغيير
        live_sha = blocks_sha(extract_blocks(src))
        if expected_sha and live_sha != expected_sha:                       # ٢) بصمة الاقتراح
            return {'ok': False, 'status': 409, 'error': ERR_STALE, 'code': 'stale'}
        new_src = replace_edits(src, edits)                                 # ٣) استبدال عُقد النص
        remote_write(session, page, new_src.encode('utf-8'))                # ٤) مؤقت ثم إعادة تسمية
        ok = _verify(page, edits, _getter(getter), verify_attempts, verify_delay, _sleep(sleep))   # ٥) تحقق
        if ok:
            return {'ok': True, 'status': 200, 'backup_id': backup.id, 'sha': blocks_sha(extract_blocks(new_src)),
                    'edits': len(edits)}
        try:
            remote_write(session, page, data)
        except SiteError:
            return {'ok': False, 'status': 502, 'error': ERR_VERIFY_RESTORE_FAILED, 'code': 'restore_failed',
                    'unknown': True, 'backup_id': backup.id}
        return {'ok': False, 'status': 502, 'error': ERR_VERIFY, 'code': 'verify', 'restored': True,
                'backup_id': backup.id}
    except SiteError as e:
        return {'ok': False, 'status': e.status, 'error': e.message, 'code': e.code}
    finally:
        if session is not None:
            session.close()
        _LOCK.release()


def restore_backup(db, page, backup_id, actor='', sftp_factory=None):
    """يعيد صفحة إلى إحدى آخر ٢٠ نسخة. قبل الإرجاع تُحفظ نسخة من الحي الآن (فالإرجاع نفسه قابل للتراجع)."""
    try:
        require_page(page)
        row = get_backup(db, page, backup_id)
        data = gzip.decompress(row.html_gz)
    except SiteError as e:
        return {'ok': False, 'status': e.status, 'error': e.message, 'code': e.code}
    except Exception:   # noqa: BLE001
        return {'ok': False, 'status': 422, 'error': ERR_NO_BACKUP, 'code': 'no_backup'}
    if not _LOCK.acquire(timeout=5):
        return {'ok': False, 'status': 409, 'error': ERR_BUSY, 'code': 'busy'}
    session = None
    try:
        session = _factory(sftp_factory)()
        current = remote_read(session, page)
        save_backup(db, page, current, actor, 'before_restore')
        remote_write(session, page, data)
        back = remote_read(session, page)
        if sha_bytes(back) != row.sha256:
            return {'ok': False, 'status': 502, 'error': 'لم تتطابق الصفحة بعد الإرجاع. راجع الموقع', 'code': 'readback',
                    'unknown': True}
        return {'ok': True, 'status': 200, 'backup_id': row.id, 'sha256': row.sha256}
    except SiteError as e:
        return {'ok': False, 'status': e.status, 'error': e.message, 'code': e.code}
    finally:
        if session is not None:
            session.close()
        _LOCK.release()
