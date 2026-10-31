# -*- coding: utf-8 -*-
"""منصّة وهميّة لـ«كتبنا وأدلّتنا»: فوق `BooksPlatform` (الأسعار والعروض والمتجر) بتضيف جسور `/api/bridge/books/ours` و`/api/bridge/guides/codes`
بالعقد المكتوب في `docs/v2/books-ours/SPEC.md` (أشكاله بالحرف: `{books, types}` · `file{name,size,pages,uploaded,uploaded_at}` · `{codes, version, updated_at, updated_by}`).

⛔ صفر شبكة: كله في الذاكرة. الكتابة حالتها حقيقية والرفض بنفس رسائل العقد العربية:
  * أي كتابة بلا `by` أو بلا `confirmed:true` بالظبط ⇒ ٤٢٢ بنص عربي.
  * الرفع: PDF بس (أول `%PDF-`) وأكبر من `max_upload` ⇒ ٤١٣. الرفع الجديد بيبدّل القديم.
  * «اعرض في المتجر» من غير PDF ⇒ ٤٠٩ «ارفع ملف الـPDF الأول».
  * أكواد الأدلّة: ٣–٤٠ حرفًا `[a-z0-9_-]`.
`write_log` = [(الوقت, method, path, body)] لكل نداء كتابة (والرفع جسمه `{by, confirmed, __file__:{name, size, head}}`).
"""
import copy
import os
import re
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import v2s_books_fixtures as bfx   # noqa: E402

iso = bfx.iso
NEED_CONFIRM_AR = 'لازم تأكيد صريح قبل التنفيذ'
NEED_BY_AR = 'لازم اسم من نفّذ'
NEED_PDF_FIRST_AR = 'ارفع ملف الـPDF الأول'
PDF_ONLY_AR = 'الملف لازم يكون PDF'
TOO_BIG_AR = 'الملف أكبر من الحدّ المسموح'
BAD_CODE_AR = 'الكود من ٣ لـ٤٠ حرف: أحرف إنجليزية صغيرة وأرقام وشرطة'
TYPES = ['book', 'guide', 'research', 'other']
SLUG = re.compile(r'^/api/bridge/books/ours/([^/]+)(/file|/status)?$')


def _book(slug, title, type_='book', about='', status='draft', file=None, **kw):
    b = {'id': 'ob-' + slug, 'slug': slug, 'title': title, 'about': about, 'type': type_, 'status': status, 'file': file,
         'created_by': 'founder@example.test', 'created_at': iso(-24 * 20), 'updated_at': iso(-24 * 2)}
    b.update(kw)
    return b


def _file(name, size, pages, hours=-48):
    return {'name': name, 'size': size, 'pages': pages, 'uploaded': True, 'uploaded_at': iso(hours)}


def seed_books():
    return [
        _book('ours-contract-guide', 'دليل صياغة العقود للمبتدئين', 'guide', 'خطوات بسيطة لكتابة عقد واضح من الصفر.', 'live', _file('contract-guide.pdf', 2481920, 64)),
        _book('ours-startup-law', 'قانون الشركات الناشئة', 'book', 'مدخل عملي لتأسيس شركة ناشئة وحماية الفكرة.', 'draft', _file('startup-law.pdf', 1536000, 112)),
        _book('ours-arbitration', 'التحكيم التجاري: ورقة بحثية', 'research', '', 'draft', None),
        _book('ours-rent-notes', 'ملاحظات في عقود الإيجار', 'other', 'مذكرة قصيرة للقراءة السريعة.', 'draft', None),
    ]


def seed_codes():
    return [
        {'code': 'spring-26', 'note': 'حملة الربيع', 'max_uses': 50, 'active': True, 'uses': 18},
        {'code': 'partner-gift', 'note': 'هدية الشركاء', 'max_uses': None, 'active': True, 'uses': 4},
        {'code': 'old-launch', 'note': 'إطلاق قديم', 'max_uses': 10, 'active': False, 'uses': 10},
    ]


class OursPlatform(bfx.BooksPlatform):
    def __init__(self, empty=False, **kw):
        super(OursPlatform, self).__init__(empty=empty, **kw)
        self.ours = [] if empty else seed_books()
        self.codes = [] if empty else seed_codes()
        self.codes_meta = {'version': 3, 'updated_at': iso(-24 * 5), 'updated_by': 'founder@example.test'}
        self.max_upload = 50 * 1024 * 1024
        self.counter = 0
        self.idem = {}
        if not empty:
            self.prices['ours-contract-guide'] = {'title': 'دليل صياغة العقود للمبتدئين', 'visible': True, 'versions': {'pdf': {'eg': 120.0, 'default': 6.0}}}
            self.prices['_guides'] = {'title': 'الأدلّة', 'visible': True, 'versions': {'pdf': {'eg': 90.0, 'default': 5.0}}}
            for b in self.ours:
                self._ensure_price(b)

    def _ensure_price(self, b):
        """كتاب بلا سعر بعد: وثيقة سعر فاضية (الجسر الحقيقي بيرد على المسودة كده)، فالفورم يقدر يفتح ويحفظ."""
        self.prices.setdefault(b['slug'], {'title': b['title'], 'visible': False, 'versions': None})

    # ---------------------------------------------------------------- التوجيه
    def _route(self, method, path, params, body):
        forced = self.forced.get((method.upper(), path))
        if forced is not None:
            return forced
        if path in self.down:
            return 502, {"detail": "تعذر الاتصال"}
        out = self._ours(method.upper(), path, params, body or {})
        if out is not None:
            return out
        return super(OursPlatform, self)._route(method, path, params, body)

    def find(self, slug):
        return next((b for b in self.ours if b['slug'] == slug), None)

    @staticmethod
    def _gate(body):
        if body.get('confirmed') is not True:
            return 422, {'detail': NEED_CONFIRM_AR}
        if not str(body.get('by') or '').strip():
            return 422, {'detail': NEED_BY_AR}
        return None

    def _ours(self, method, path, params, body):
        if path == '/api/bridge/guides/codes':
            if method == 'GET':
                return 200, dict({'codes': copy.deepcopy(self.codes)}, **self.codes_meta)
            if method == 'PUT':
                bad = self._gate(body)
                if bad:
                    return bad
                rows = body.get('codes')
                if not isinstance(rows, list):
                    return 422, {'detail': 'قائمة الأكواد ناقصة'}
                old = {c['code']: c for c in self.codes}
                new = []
                for r in rows:
                    if not re.match(r'^[a-z0-9_-]{3,40}$', str(r.get('code') or '')):
                        return 422, {'detail': BAD_CODE_AR}
                    new.append({'code': r['code'], 'note': r.get('note', ''), 'max_uses': r.get('max_uses'), 'active': r.get('active', True),
                                'uses': (old.get(r['code']) or {}).get('uses', 0)})
                self.codes = new
                self.codes_meta = {'version': self.codes_meta['version'] + 1, 'updated_at': iso(0), 'updated_by': body['by']}
                return 200, dict({'ok': True, 'codes': copy.deepcopy(self.codes)}, **self.codes_meta)
            return None
        if path == '/api/bridge/books/ours':
            if method == 'GET':
                return 200, {'books': copy.deepcopy(self.ours), 'types': TYPES}
            if method == 'POST':
                bad = self._gate(body)
                if bad:
                    return bad
                if body.get('type') not in TYPES or not str(body.get('title') or '').strip():
                    return 422, {'detail': 'العنوان والنوع مطلوبان'}
                key = body.get('idem_key')
                if key and key in self.idem:
                    return 200, {'ok': True, 'book': copy.deepcopy(self.idem[key]), 'duplicate': True}
                self.counter += 1
                b = _book('ours-new-%d' % self.counter, body['title'], body['type'], body.get('about', ''), 'draft', None, created_by=body['by'], created_at=iso(0), updated_at=iso(0))
                self.ours.append(b)
                self._ensure_price(b)
                if key:
                    self.idem[key] = b
                return 200, {'ok': True, 'book': copy.deepcopy(b)}
            return None
        m = SLUG.match(path)
        if not m:
            return None
        slug, tail = m.group(1), m.group(2)
        b = self.find(slug)
        if b is None:
            return 404, {'detail': 'هذا الكتاب غير موجود'}
        if tail is None and method == 'PUT':
            bad = self._gate(body)
            if bad:
                return bad
            for k in ('title', 'about', 'type'):
                if k in body:
                    b[k] = body[k]
            b['updated_at'] = iso(0)
            return 200, {'ok': True, 'book': copy.deepcopy(b)}
        if tail == '/file' and method == 'POST':
            bad = self._gate(body)
            if bad:
                return bad
            f = body.get('__file__') or {}
            if not str(f.get('head') or '').startswith('%PDF-'):
                return 422, {'detail': PDF_ONLY_AR}
            if f.get('size', 0) > self.max_upload:
                return 413, {'detail': TOO_BIG_AR}
            b['file'] = _file(f.get('name') or 'book.pdf', f.get('size', 0), max(1, int(f.get('size', 0) // 30000)), 0)
            b['updated_at'] = iso(0)
            return 200, {'ok': True, 'book': copy.deepcopy(b)}
        if tail == '/status' and method == 'PUT':
            bad = self._gate(body)
            if bad:
                return bad
            if body.get('live') is True and not b.get('file'):
                return 409, {'detail': NEED_PDF_FIRST_AR}
            b['status'] = 'live' if body.get('live') else 'draft'
            b['updated_at'] = iso(0)
            return 200, {'ok': True, 'book': copy.deepcopy(b)}
        return None
